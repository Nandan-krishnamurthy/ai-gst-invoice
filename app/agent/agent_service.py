"""
Agent service for handling conversational draft invoice creation.
"""
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from datetime import datetime, timezone
from app.agent import session_service, draft_service
from app.agent.schemas import AgentResponse
from app.agent.agent_state import AgentState
from app.db.models import Invoice, InvoiceStatus
from app.models import company
from app.models.company import Company
from app.services.pdf_generator import generate_invoice_pdf
from invoice.invoice_engine import generate_invoice
from invoice.model import InvoiceRequest, Party, InvoiceItem
from app.llm.llm_service import extract_invoice_data
from app.utils.location_utils import infer_state_from_address, is_valid_indian_state, normalize_text
from sqlalchemy import text
import re
import os
import copy
import logging
from app.agent.invoice_helpers import (
    _normalize_party_payload,
    _get_items_missing_hsn,
    _build_invoice_preview,
    _get_missing_party_fields,
    _check_critical_validation_errors,
    _get_non_critical_warnings,
)


logger = logging.getLogger(__name__)


def handle_message(session_id: str, message: str, db: Session) -> AgentResponse:
    """
    Handle agent message for draft invoice creation.
    
    Args:
        session_id: Session ID for the conversation
        message: User message
        db: Database session
    
    Returns:
        AgentResponse object with standardized response structure
    
    Note: This function ALWAYS returns a valid AgentResponse. No code path returns None.
    """
    message_lower = message.lower()
    logger.info("handle_message_start session_id=%s message_snippet=%s", session_id, message[:50])

    # Ensure session exists before any database operations
    session_id = session_service.get_or_create_session(session_id, db)

    # ALWAYS ensure an active draft exists for the session
    # This aligns with production AI workflow: draft must always exist
    active_draft_id = session_service.get_active_draft(session_id, db)
    draft = None
    
    if active_draft_id:
        # Load existing draft
        try:
            draft = db.query(Invoice).filter(Invoice.id == int(active_draft_id)).first()
            if not draft or draft.status != InvoiceStatus.draft:
                # Draft not found or not in draft state - create new one
                draft = None
                active_draft_id = None
        except (ValueError, TypeError):
            draft = None
            active_draft_id = None
    
    # If no active draft exists, create an empty one immediately
    if not draft:
        logger.info("no_active_draft_creating_new session_id=%s", session_id)
        empty_draft_data = {
            "invoice_date": datetime.now(timezone.utc),
            "seller": {"name": None, "address": None, "state": None, "gstin": None},
            "buyer": {"name": None, "address": None, "state": None, "gstin": None},
            "items": []
        }
        new_draft = draft_service.create_draft(
            session_id=session_id,
            invoice_data=empty_draft_data,
            db=db
        )
        active_draft_id = new_draft["draft_id"]
        session_service.set_active_draft(session_id, str(active_draft_id), db)
        draft = db.query(Invoice).filter(Invoice.id == active_draft_id).first()
        logger.info("empty_draft_created session_id=%s draft_id=%s", session_id, active_draft_id)

    if message_lower in ["confirm", "accept", "yes"]:
        # Accept/confirm behavior: transition awaiting_confirmation -> draft_created
        # using the SAME draft (do not create a new draft)
        logger.info("branch_confirm session_id=%s active_draft_id=%s", session_id, active_draft_id)

        if not draft:
            logger.error("confirm_no_draft session_id=%s", session_id)
            return AgentResponse(
                message="No active draft found. Please provide invoice details.",
                agent_state=AgentState.COLLECTING_INFO,
                draft_invoice_id=None
            )

        logger.info("confirm_draft_loaded session_id=%s draft_id=%s status=%s", session_id, draft.id, draft.status)

        # Check CRITICAL validation only (soft validation for drafts)
        critical_errors = _check_critical_validation_errors(draft)
        
        if critical_errors:
            logger.warning(
                "confirm_critical_validation_failed session_id=%s draft_id=%s errors=%s",
                session_id,
                draft.id,
                critical_errors,
            )
            draft_preview = _build_invoice_preview(draft)
            warnings = _get_non_critical_warnings(draft)
            return AgentResponse(
                message="Draft has critical issues: " + " ".join(critical_errors),
                agent_state=AgentState.AWAITING_CONFIRMATION,
                draft_invoice_id=draft.id,
                invoice=draft_preview,
                missing_fields=critical_errors,
                warnings=warnings if warnings else None,
                next_expected_input="Please fix the critical issues and try again."
            )

        # Collect non-critical warnings (don't block transition)
        warnings = _get_non_critical_warnings(draft)
        
        logger.info(
            "draft_confirmed session_id=%s draft_id=%s agent_state=%s non_critical_warnings=%s",
            session_id,
            draft.id,
            AgentState.DRAFT_CREATED,
            warnings,
        )

        draft_preview = _build_invoice_preview(draft)

        return AgentResponse(
            message="Draft invoice confirmed. Ready to finalize.",
            agent_state=AgentState.DRAFT_CREATED,
            draft_invoice_id=draft.id,
            invoice=draft_preview,
            warnings=warnings if warnings else None,
            next_expected_input="Click Finalize Invoice to complete."
        )
    
    # Logic 1: Create invoice (explicit command phrase)
    # Since draft already exists, this command just confirms the empty draft state
    handled_create_invoice = False
    if "create invoice" in message_lower:
        logger.info("branch_create_invoice session_id=%s using_existing_draft_id=%s", session_id, active_draft_id)

        # Lightweight one-line extraction for mixed messages while preserving existing flow.
        create_update_payload = {}
        create_existing_buyer = copy.deepcopy(draft.buyer) if draft and draft.buyer else {}
        create_existing_items = copy.deepcopy(draft.items) if draft and draft.items else []
        create_has_composite_entities = False

        # Buyer name after "create invoice for", but stop at known entity markers.
        buyer_name_match = re.search(
            r"create\s+invoice\s+for\s+([A-Za-z0-9\s&.,()-]+?)(?=\s+\d+\.?\d*\s+[A-Za-z]|\s+hsn\b|\s+gst\b|\s+buyer\s+address\b|$)",
            message,
            re.IGNORECASE,
        )
        if buyer_name_match:
            buyer_name = " ".join(word.capitalize() for word in buyer_name_match.group(1).strip().split())
            create_existing_buyer["name"] = buyer_name

        # Buyer address in the same line: "buyer address <text>"
        buyer_address_match = re.search(r"\bbuyer\s+address\s+(.+)$", message, re.IGNORECASE)
        if buyer_address_match:
            buyer_address = " ".join(word.capitalize() for word in buyer_address_match.group(1).strip().split())
            create_existing_buyer["address"] = buyer_address

        if create_existing_buyer:
            create_update_payload["buyer"] = _normalize_party_payload(create_existing_buyer)

        # Single-line item extraction: "<qty> <item> at <price> [each]"
        item_match = re.search(
            r"\b(\d+\.?\d*)\s+([A-Za-z0-9\s&.,()-]+?)\s+at\s+(\d+\.?\d*)(?:\s+each)?\b",
            message,
            re.IGNORECASE,
        )
        if item_match:
            quantity = float(item_match.group(1))
            description = " ".join(word.capitalize() for word in item_match.group(2).strip().split())
            price = float(item_match.group(3))

            # Accept GST formats: "gst 18", "18 gst", "18% gst", "gst 18%"
            create_gst_match = re.search(r"\bgst\s*(\d+)\s*%?\b", message_lower)
            if create_gst_match:
                gst_rate = int(create_gst_match.group(1))
            else:
                # Guard against "hsn 8471 gst" collision by ignoring numeric-prefix GST
                # when it is directly prefixed by "hsn ".
                create_gst_suffix_match = re.search(r"(?<!hsn\s)\b(\d+)\s*%?\s*gst\b", message_lower)
                gst_rate = int(create_gst_suffix_match.group(1)) if create_gst_suffix_match else 0

            create_hsn_match = re.search(r"\bhsn\s+(?:code\s+)?(?:is\s+)?(\d{4,8})\b", message_lower)
            hsn_code = create_hsn_match.group(1) if create_hsn_match else None

            create_existing_items.append(
                {
                    "description": description,
                    "quantity": quantity,
                    "price": price,
                    "gst_rate": gst_rate,
                    "hsn_code": hsn_code,
                }
            )
            create_update_payload["items"] = create_existing_items
            create_has_composite_entities = True

        # If regex extraction did NOT find items, attempt LLM extraction fallback
        if not create_has_composite_entities:
            logger.info("create_invoice_regex_no_items_trying_llm session_id=%s", session_id)
            try:
                extracted_data = extract_invoice_data(message)
                llm_items = extracted_data.get("items") if extracted_data else None
                if llm_items:
                    logger.info("create_invoice_llm_items_found session_id=%s count=%s", session_id, len(llm_items))
                    # Merge LLM-extracted items with existing items
                    create_existing_items.extend(llm_items)
                    create_update_payload["items"] = create_existing_items
                    create_has_composite_entities = True
                    
                    # Also merge any LLM-extracted buyer data with regex-extracted buyer data
                    llm_buyer = extracted_data.get("buyer")
                    if llm_buyer:
                        # Merge: LLM buyer data fills in missing fields from regex extraction
                        merged_buyer = copy.deepcopy(create_existing_buyer)
                        for key in ["name", "gstin", "address", "state"]:
                            if not merged_buyer.get(key) and llm_buyer.get(key):
                                merged_buyer[key] = llm_buyer[key]
                        create_update_payload["buyer"] = _normalize_party_payload(merged_buyer)
            except Exception as llm_err:
                logger.error("create_invoice_llm_extraction_failed session_id=%s error=%s", session_id, llm_err)

        # Apply a single merged draft update for create-invoice extraction.
        if create_update_payload:
            draft_service.update_draft(
                draft_id=active_draft_id,
                invoice_data=create_update_payload,
                db=db,
            )
            draft = db.query(Invoice).filter(Invoice.id == active_draft_id).first()

        handled_create_invoice = True
        # Execution continues — do NOT return here
        # Fall through to next handlers or final response

        # If the create line already carried multiple entities or LLM found items, return immediately
        # so downstream party/GST handlers do not override this merged extraction.
        if create_has_composite_entities:
            logger.info("create_invoice_composite_extracted session_id=%s draft_id=%s", session_id, active_draft_id)
            preview = _build_invoice_preview(draft)
            warnings = _get_non_critical_warnings(draft)
            critical_errors = _check_critical_validation_errors(draft)
            return AgentResponse(
                message="Invoice draft updated from your input.",
                agent_state=AgentState.AWAITING_CONFIRMATION,
                draft_invoice_id=active_draft_id,
                invoice=preview,
                warnings=warnings if warnings else None,
                missing_fields=critical_errors if critical_errors else None,
                next_expected_input="Add more details if needed, then confirm or finalize."
            )

    # If "create invoice" was the only keyword and no other handler matched,
    # return a response asking for next action
    if handled_create_invoice and not ("seller" in message_lower or "buyer" in message_lower or 
                                       "gst" in message_lower or "hsn" in message_lower or 
                                       "add" in message_lower or "finalize" in message_lower):
        logger.info("create_invoice_standalone session_id=%s draft_id=%s returning_confirmation", session_id, active_draft_id)
        preview = _build_invoice_preview(draft)
        warnings = _get_non_critical_warnings(draft)
        return AgentResponse(
            message="Invoice created. You can now add items or update details.",
            agent_state=AgentState.AWAITING_CONFIRMATION,
            draft_invoice_id=active_draft_id,
            invoice=preview,
            warnings=warnings if warnings else None,
            next_expected_input="Add items using 'add <quantity> <item> at <price>' or update details"
        )

    # Logic 2: Update seller or buyer details
    elif "seller" in message_lower or "buyer" in message_lower:
        logger.info("branch_seller_buyer_update session_id=%s draft_id=%s", session_id, active_draft_id)
        if not draft:
            return AgentResponse(
                message="No active invoice found. Please create an invoice first using 'create invoice'.",
                agent_state=AgentState.COLLECTING_INFO,
                next_expected_input="Use 'create invoice' to start a new invoice"
            )
        
        # Determine if updating seller or buyer
        party_type = "seller" if "seller" in message_lower else "buyer"
        current_party = draft.seller if party_type == "seller" else draft.buyer
        
        # Extract party details from message
        updated_party = current_party.copy() if current_party else {}
        
        # Check if message uses colon-based format for strict parsing
        if ":" in message:
            # Strict key-value parsing using colon
            # Split message on colon to get key and value
            parts = message.split(":", 1)
            if len(parts) == 2:
                key_part = parts[0].strip().lower()
                value_part = parts[1].strip()
                
                # Map supported keys explicitly
                if "seller state" in key_part or (party_type == "seller" and "state" in key_part):
                    updated_party["state"] = " ".join(word.capitalize() for word in value_part.split())
                elif "seller gstin" in key_part or (party_type == "seller" and "gstin" in key_part):
                    updated_party["gstin"] = value_part.upper()
                elif "seller name" in key_part or (party_type == "seller" and "name" in key_part):
                    updated_party["name"] = " ".join(word.capitalize() for word in value_part.split())
                elif "buyer state" in key_part or (party_type == "buyer" and "state" in key_part):
                    updated_party["state"] = " ".join(word.capitalize() for word in value_part.split())
                elif "buyer gstin" in key_part or (party_type == "buyer" and "gstin" in key_part):
                    updated_party["gstin"] = value_part.upper()
                elif "buyer name" in key_part or (party_type == "buyer" and "name" in key_part):
                    updated_party["name"] = " ".join(word.capitalize() for word in value_part.split())
                elif "address" in key_part:
                    updated_party["address"] = " ".join(word.capitalize() for word in value_part.split())
        else:
            # Fallback to NLP/regex extraction if no colon present
            is_address_update = bool(re.search(rf'\b{party_type}\s+address\b', message_lower, re.IGNORECASE))

            # Extract name
            if not is_address_update:
                name_match = re.search(rf'{party_type}\s+(?:name\s+(?:is\s+)?)?([A-Za-z0-9\s&.,()-]+?)(?:\s+gstin|\s+state|$)', message_lower, re.IGNORECASE)
                if name_match:
                    name_value = name_match.group(1).strip()
                    # Capitalize properly
                    updated_party["name"] = " ".join(word.capitalize() for word in name_value.split())
            
            # Extract GSTIN
            gstin_match = re.search(r'gstin\s*[:=]?\s*([A-Z0-9]{15})', message, re.IGNORECASE)
            if gstin_match:
                updated_party["gstin"] = gstin_match.group(1).upper()
            
            # Extract state
            state_match = re.search(r'state\s+(?:is\s+)?([A-Za-z\s]+?)(?:\s+gstin|\s+address|$)', message_lower, re.IGNORECASE)
            if state_match:
                state_value = state_match.group(1).strip()
                updated_party["state"] = " ".join(word.capitalize() for word in state_value.split())
            
            # Extract address
            address_match = re.search(r'address\s+(?:is\s+)?(.+?)(?:\s+state|\s+gstin|$)', message_lower, re.IGNORECASE)
            if address_match:
                address_value = address_match.group(1).strip()
                updated_party["address"] = " ".join(word.capitalize() for word in address_value.split())
        
        # Update draft with new party details
        invoice_data = {party_type: _normalize_party_payload(updated_party)}
        updated_draft = draft_service.update_draft(
            draft_id=active_draft_id,
            invoice_data=invoice_data,
            db=db
        )
        
        # If updating buyer, also set denormalized buyer columns
        if party_type == "buyer":
            draft_obj = db.query(Invoice).filter(Invoice.id == active_draft_id).first()
            if draft_obj:
                buyer_data = draft_obj.buyer or {}
                draft_obj.buyer_name = buyer_data.get("name")
                draft_obj.buyer_gstin = buyer_data.get("gstin")
                draft_obj.buyer_address = buyer_data.get("address")
                draft_obj.buyer_state = buyer_data.get("state")
                db.flush()
                db.refresh(draft_obj)
                # Refresh updated_draft dict from database
                updated_draft["buyer"] = draft_obj.buyer
        
        # Check completeness at field level (address is optional)
        missing = []
        
        # Check seller required fields
        seller = updated_draft["seller"]
        for field in ["name", "state", "gstin"]:
            if not seller.get(field) or seller.get(field) == "TBD":
                missing.append(f"seller.{field}")
        
        # Check buyer required fields
        buyer = updated_draft["buyer"]
        for field in ["name", "state", "gstin"]:
            if not buyer.get(field) or buyer.get(field) == "TBD":
                missing.append(f"buyer.{field}")
        
        # Check items
        if len(updated_draft.get("items", [])) == 0:
            missing.append("items")
        else:
            # Check for items missing HSN codes
            missing_hsn = _get_items_missing_hsn(updated_draft["items"])
            for item in missing_hsn:
                missing.append(f"hsn_code[{item['description']}]")
        
        # Always return AWAITING_CONFIRMATION (never block draft preview)
        agent_state = AgentState.AWAITING_CONFIRMATION
        if missing:
            # Prioritize HSN code messages if that's what's missing
            hsn_missing = [m for m in missing if m.startswith("hsn_code[")]
            if hsn_missing and len(hsn_missing) == len(missing):
                hsn_items = [m.split('[')[1].rstrip(']') for m in hsn_missing]
                next_input = f"Please provide HSN codes for: {', '.join(hsn_items)}"
            else:
                next_input = f"Please provide: {', '.join(missing)}"
        else:
            next_input = "All required details complete. Say 'finalize' to complete the invoice."
        
        return AgentResponse(
            message=f"{party_type.capitalize()} details updated successfully.",
            agent_state=agent_state,
            draft_invoice_id=updated_draft["draft_id"],
            invoice={
                "invoice_no": updated_draft["invoice_no"],
                "seller": updated_draft["seller"],
                "buyer": updated_draft["buyer"],
                "items": updated_draft["items"],
                "subtotal": updated_draft["subtotal"],
                "total_gst": updated_draft["total_gst"],
                "grand_total": updated_draft["grand_total"]
            },
            missing_fields=missing if missing else None,
            next_expected_input=next_input
        )
    
    # Logic 3: Update GST rate for items
    elif "gst" in message_lower and "add" not in message_lower:
        logger.info("branch_gst_update session_id=%s draft_id=%s", session_id, active_draft_id)
        if not draft:
            return AgentResponse(
                message="No active invoice found. Please create an invoice first using 'create invoice'.",
                agent_state=AgentState.COLLECTING_INFO,
                next_expected_input="Use 'create invoice' to start a new invoice"
            )
        
        current_items = draft.items or []
        if not current_items:
            return AgentResponse(
                message="No items found in the invoice. Please add items first.",
                agent_state=AgentState.AWAITING_CONFIRMATION,
                draft_invoice_id=draft.id,
                invoice=_build_invoice_preview(draft),
                missing_fields=["items"],
                next_expected_input="Add items using 'add <quantity> <item> at <price>'"
            )
        
        # Extract GST rate from message
        gst_match = re.search(r'\bgst\s*(\d+)\s*%?\b|\b(\d+)\s*%?\s*gst\b', message_lower)
        if not gst_match:
            warnings = _get_non_critical_warnings(draft)
            return AgentResponse(
                message="Could not extract GST rate. Please provide GST rate in format '<rate>% GST' or 'GST <rate>'",
                agent_state=AgentState.AWAITING_CONFIRMATION,
                draft_invoice_id=draft.id,
                invoice=_build_invoice_preview(draft),
                warnings=warnings if warnings else None,
                next_expected_input="Provide GST rate like '18% GST' or 'GST 18'"
            )
        
        gst_rate = int(gst_match.group(1) or gst_match.group(2))
        
        # Deep-copy items list to ensure SQLAlchemy detects changes to JSONB column
        current_items = copy.deepcopy(current_items)
        
        # Update the last item's GST rate
        current_items[-1]["gst_rate"] = gst_rate
        
        # Update draft with modified items
        updated_draft = draft_service.update_draft(
            draft_id=active_draft_id,
            invoice_data={"items": current_items},
            db=db
        )
        
        # Check for items missing HSN codes
        missing_hsn = _get_items_missing_hsn(updated_draft["items"])
        
        # Check overall completeness
        missing = []
        seller = updated_draft["seller"]
        for field in ["name", "state", "gstin"]:
            if not seller.get(field) or seller.get(field) == "TBD":
                missing.append(f"seller.{field}")
        
        buyer = updated_draft["buyer"]
        for field in ["name", "state", "gstin"]:
            if not buyer.get(field) or buyer.get(field) == "TBD":
                missing.append(f"buyer.{field}")
        
        if len(updated_draft.get("items", [])) == 0:
            missing.append("items")
        
        # Add missing HSN codes to missing fields
        for item in missing_hsn:
            missing.append(f"hsn_code[{item['description']}]")
        
        # Always return AWAITING_CONFIRMATION (never block draft preview)
        agent_state = AgentState.AWAITING_CONFIRMATION
        if missing:
            if missing_hsn:
                next_input = f"Please provide HSN codes for: {', '.join([item['description'] for item in missing_hsn])}"
            else:
                next_input = f"Please provide: {', '.join(missing)}"
        else:
            next_input = "All required details complete. Say 'finalize' to complete the invoice."
        
        return AgentResponse(
            message=f"GST rate {gst_rate}% updated for {current_items[-1].get('description', 'last item')}.",
            agent_state=agent_state,
            draft_invoice_id=updated_draft["draft_id"],
            invoice={
                "invoice_no": updated_draft["invoice_no"],
                "seller": updated_draft["seller"],
                "buyer": updated_draft["buyer"],
                "items": updated_draft["items"],
                "subtotal": updated_draft["subtotal"],
                "total_gst": updated_draft["total_gst"],
                "grand_total": updated_draft["grand_total"]
            },
            missing_fields=missing if missing else None,
            next_expected_input=next_input
        )
    
    # Logic 4: Update HSN code for items
    elif "hsn" in message_lower:
        logger.info("branch_hsn_update session_id=%s draft_id=%s", session_id, active_draft_id)
        if not draft:
            return AgentResponse(
                message="No active invoice found. Please create an invoice first using 'create invoice'.",
                agent_state=AgentState.COLLECTING_INFO,
                next_expected_input="Use 'create invoice' to start a new invoice"
            )
        
        current_items = draft.items or []
        if not current_items:
            return AgentResponse(
                message="No items found in the invoice. Please add items first.",
                agent_state=AgentState.AWAITING_CONFIRMATION,
                draft_invoice_id=draft.id,
                invoice=_build_invoice_preview(draft),
                missing_fields=["items"],
                next_expected_input="Add items using 'add <quantity> <item> at <price>'"
            )
        
        # Make a deep copy of items to ensure SQLAlchemy detects changes to JSONB column
        current_items = copy.deepcopy(current_items)
        
        # Extract HSN code from message
        hsn_match = re.search(r'hsn\s+(?:code\s+)?(?:is\s+)?(\d{4,8})', message_lower)
        if not hsn_match:
            warnings = _get_non_critical_warnings(draft)
            return AgentResponse(
                message="Could not extract HSN code. Please provide HSN code in format 'HSN for <item> is <code>' or 'HSN code is <code>'",
                agent_state=AgentState.AWAITING_CONFIRMATION,
                draft_invoice_id=draft.id,
                invoice=_build_invoice_preview(draft),
                warnings=warnings if warnings else None,
                next_expected_input="Provide HSN code like 'HSN for laptops is 8471'"
            )
        
        hsn_code = hsn_match.group(1)
        
        # Try to match specific item description
        # Pattern: "HSN for <item description> is <code>"
        item_match = re.search(r'hsn\s+for\s+(.+?)\s+is', message_lower)
        
        if item_match:
            # Explicit item specified
            target_description = item_match.group(1).strip()
            
            # Find matching item
            matched_indices = []
            for idx, item in enumerate(current_items):
                item_desc = item.get("description", "").lower()
                if target_description in item_desc or item_desc in target_description:
                    matched_indices.append(idx)
            
            if len(matched_indices) == 0:
                warnings = _get_non_critical_warnings(draft)
                return AgentResponse(
                    message=f"No item found matching '{target_description}'. Available items: {', '.join([item.get('description', 'unknown') for item in current_items])}",
                    agent_state=AgentState.AWAITING_CONFIRMATION,
                    draft_invoice_id=draft.id,
                    invoice=_build_invoice_preview(draft),
                    warnings=warnings if warnings else None,
                    next_expected_input="Provide correct item name"
                )
            elif len(matched_indices) > 1:
                warnings = _get_non_critical_warnings(draft)
                return AgentResponse(
                    message=f"Multiple items match '{target_description}'. Please be more specific.",
                    agent_state=AgentState.AWAITING_CONFIRMATION,
                    draft_invoice_id=draft.id,
                    invoice=_build_invoice_preview(draft),
                    warnings=warnings if warnings else None,
                    next_expected_input="Specify exact item description"
                )
            
            # Update the matched item
            current_items[matched_indices[0]]["hsn_code"] = hsn_code
            
        else:
            # Generic HSN input - only accept if exactly one item is missing HSN
            missing_hsn = _get_items_missing_hsn(current_items)
            
            if len(missing_hsn) == 0:
                warnings = _get_non_critical_warnings(draft)
                return AgentResponse(
                    message="All items already have HSN codes assigned.",
                    agent_state=AgentState.AWAITING_CONFIRMATION,
                    draft_invoice_id=draft.id,
                    invoice=_build_invoice_preview(draft),
                    warnings=warnings if warnings else None,
                    next_expected_input="Say 'finalize' to complete the invoice if all details are ready"
                )
            elif len(missing_hsn) > 1:
                item_list = ', '.join([item['description'] for item in missing_hsn])
                warnings = _get_non_critical_warnings(draft)
                return AgentResponse(
                    message=f"Multiple items need HSN codes: {item_list}. Please specify which item using 'HSN for <item> is <code>'",
                    agent_state=AgentState.AWAITING_CONFIRMATION,
                    draft_invoice_id=draft.id,
                    invoice=_build_invoice_preview(draft),
                    warnings=warnings if warnings else None,
                    missing_fields=[f"hsn_code[{item['description']}]" for item in missing_hsn],
                    next_expected_input=f"Provide HSN like 'HSN for {missing_hsn[0]['description']} is <code>'"
                )
            
            # Exactly one item missing HSN - assign it
            current_items[missing_hsn[0]["index"]]["hsn_code"] = hsn_code
        
        # Update draft with new items
        updated_draft = draft_service.update_draft(
            draft_id=active_draft_id,
            invoice_data={"items": current_items},
            db=db
        )
        
        # Check for remaining missing HSN codes
        remaining_missing_hsn = _get_items_missing_hsn(updated_draft["items"])
        
        # Check overall completeness
        missing = []
        seller = updated_draft["seller"]
        for field in ["name", "state", "gstin"]:
            if not seller.get(field) or seller.get(field) == "TBD":
                missing.append(f"seller.{field}")
        
        buyer = updated_draft["buyer"]
        for field in ["name", "state", "gstin"]:
            if not buyer.get(field) or buyer.get(field) == "TBD":
                missing.append(f"buyer.{field}")
        
        if len(updated_draft.get("items", [])) == 0:
            missing.append("items")
        
        # Add missing HSN codes to missing fields
        for item in remaining_missing_hsn:
            missing.append(f"hsn_code[{item['description']}]")
        
        # Always return AWAITING_CONFIRMATION (never block draft preview)
        agent_state = AgentState.AWAITING_CONFIRMATION
        if missing:
            if remaining_missing_hsn:
                next_input = f"Please provide HSN codes for: {', '.join([item['description'] for item in remaining_missing_hsn])}"
            else:
                next_input = f"Please provide: {', '.join(missing)}"
        else:
            next_input = "All required details complete. Say 'finalize' to complete the invoice."
        
        return AgentResponse(
            message=f"HSN code {hsn_code} assigned successfully.",
            agent_state=agent_state,
            draft_invoice_id=updated_draft["draft_id"],
            invoice={
                "invoice_no": updated_draft["invoice_no"],
                "seller": updated_draft["seller"],
                "buyer": updated_draft["buyer"],
                "items": updated_draft["items"],
                "subtotal": updated_draft["subtotal"],
                "total_gst": updated_draft["total_gst"],
                "grand_total": updated_draft["grand_total"]
            },
            missing_fields=missing if missing else None,
            next_expected_input=next_input
        )
    
    # Logic 5: Add item
    elif "add" in message_lower:
        logger.info("branch_add_item session_id=%s draft_id=%s", session_id, active_draft_id)
        if not draft:
            return AgentResponse(
                message="No active invoice found. Please create an invoice first using 'create invoice'.",
                agent_state=AgentState.COLLECTING_INFO,
                next_expected_input="Use 'create invoice' to start a new invoice"
            )
        
        # Parse item details from message
        # Supports both formats:
        # 1. "add <quantity> <product> at <price>" (explicit)
        # 2. "add <quantity> <product> <price>" (implicit - last number is price)
        # Examples: "add 1 laptop at 50000" or "add 1 laptop 50000"
        
        # Extract quantity
        quantity_match = re.search(r'add\s+(\d+\.?\d*)', message_lower)
        quantity = float(quantity_match.group(1)) if quantity_match else 1.0
        
        # Try to extract price with "at" keyword first
        price_match = re.search(r'at\s+(\d+\.?\d*)', message_lower)
        if price_match:
            # Format: "add <qty> <desc> at <price>"
            price = float(price_match.group(1))
            # Extract description (between quantity and "at")
            product_match = re.search(r'add\s+\d+\.?\d*\s+(.+?)\s+at', message_lower)
            description = product_match.group(1).strip() if product_match else "Item"
        else:
            # Format: "add <qty> <desc> <price> [gst <rate>]"
            # Extract last number as price and text between quantity and price as description
            match = re.search(r'add\s+\d+\.?\d*\s+(.+?)\s+(\d+\.?\d*)\s*(?:gst|$)', message_lower)
            if match:
                description = match.group(1).strip()
                price = float(match.group(2))
            else:
                # Couldn't parse - use defaults
                description = "Item"
                price = 0.0

        # LLM fallback: if regex produced an empty/default description or zero price,
        # ask the LLM to extract the item from the raw message.
        gst_rate = 0  # default; may be overwritten by LLM fallback or message-level keyword below
        if not description or description == "Item" or price <= 0:
            try:
                extracted_data = extract_invoice_data(message)
                llm_items = extracted_data.get("items") if extracted_data else None
                if llm_items:
                    first = llm_items[0]
                    description = first.get("description") or description
                    price = float(first.get("price") or first.get("unit_price") or price)
                    quantity = float(first.get("quantity") or quantity)
                    gst_rate = int(first.get("gst_rate") or 0)
                    # hsn_code captured below after gst_rate block; store temporarily
                    _llm_hsn = first.get("hsn_code")
                else:
                    _llm_hsn = None
            except Exception as _llm_err:
                logger.error("llm_fallback_add_item_failed session_id=%s error=%s", session_id, _llm_err)
                _llm_hsn = None
        else:
            _llm_hsn = None

        # Message-level GST keyword always wins over the LLM-extracted value.
        gst_match = re.search(r'gst\s+(\d+)(?:%)?', message_lower)
        if gst_match:
            gst_rate = int(gst_match.group(1))
        
        # Validate parsed item fields before adding to the draft
        if not description or description == "Item":
            return AgentResponse(
                message="Invalid item description. Use: add 2 laptops at 50000",
                agent_state=AgentState.COLLECTING_INFO,
                draft_invoice_id=active_draft_id,
                next_expected_input="Use format: add <quantity> <description> at <price>"
            )
        if quantity <= 0:
            return AgentResponse(
                message="Invalid quantity. Use: add 2 laptops at 50000",
                agent_state=AgentState.COLLECTING_INFO,
                draft_invoice_id=active_draft_id,
                next_expected_input="Use format: add <quantity> <description> at <price>"
            )
        if price <= 0:
            return AgentResponse(
                message="Invalid price. Use: add 2 laptops at 50000",
                agent_state=AgentState.COLLECTING_INFO,
                draft_invoice_id=active_draft_id,
                next_expected_input="Use format: add <quantity> <description> at <price>"
            )

        # Deep-copy items list to ensure SQLAlchemy detects changes to JSONB column
        current_items = copy.deepcopy(draft.items) if draft.items else []
        new_item = {
            "description": description,
            "quantity": quantity,
            "price": price,
            "gst_rate": gst_rate,  # Override with message value if specified
            "hsn_code": _llm_hsn  # Populated by LLM fallback when available, else None
        }
        current_items.append(new_item)
        
        # Update draft with new items
        add_update_payload = {"items": current_items}
        if draft and draft.buyer:
            add_update_payload["buyer"] = _normalize_party_payload(copy.deepcopy(draft.buyer))

        updated_draft = draft_service.update_draft(
            draft_id=active_draft_id,
            invoice_data=add_update_payload,
            db=db
        )
        
        # Check for items missing HSN codes and get warnings
        missing_hsn = _get_items_missing_hsn(updated_draft["items"])
        warnings = _get_non_critical_warnings(db.query(Invoice).filter(Invoice.id == active_draft_id).first())
        
        # Always return AWAITING_CONFIRMATION (never block draft preview)
        agent_state = AgentState.AWAITING_CONFIRMATION
        if missing_hsn:
            missing_fields = [f"hsn_code[{item['description']}]" for item in missing_hsn]
            if len(missing_hsn) == 1:
                next_input = f"Please provide HSN code for {missing_hsn[0]['description']} using 'HSN code is <code>'"
            else:
                next_input = f"Please provide HSN codes using 'HSN for <item> is <code>'"
            message = f"Item added: {quantity} x {description} @ {price}. HSN code required (GST > 0)."
        else:
            missing_fields = None
            next_input = "Add more items or say 'finalize' to complete the invoice"
            message = f"Item added: {quantity} x {description} @ {price}."
        
        return AgentResponse(
            message=message,
            agent_state=agent_state,
            draft_invoice_id=updated_draft["draft_id"],
            invoice={
                "invoice_no": updated_draft["invoice_no"],
                "seller": updated_draft["seller"],
                "buyer": updated_draft["buyer"],
                "items": updated_draft["items"],
                "subtotal": updated_draft["subtotal"],
                "total_gst": updated_draft["total_gst"],
                "grand_total": updated_draft["grand_total"]
            },
            missing_fields=missing_fields,
            next_expected_input=next_input
        )
    
    # Logic 6: Finalize invoice
    elif "finalize" in message_lower:
        logger.info("branch_finalize session_id=%s draft_id=%s", session_id, active_draft_id)
        if not draft:
            logger.info("finalize_no_draft session_id=%s agent_state=%s", session_id, AgentState.COLLECTING_INFO)
            return AgentResponse(
                message="No active draft found for this session.",
                agent_state=AgentState.COLLECTING_INFO,
                next_expected_input="Create an invoice first using 'create invoice'"
            )
        
        # Check if already finalized (idempotent behavior)
        if draft.status == InvoiceStatus.finalized:
            # Return existing finalized invoice data without re-running validation or PDF generation
            pdf_dir = "invoices/pdfs"
            pdf_filename = f"invoice_{draft.invoice_no}.pdf"
            pdf_path = os.path.join(pdf_dir, pdf_filename)
            
            return AgentResponse(
                message=f"Invoice {draft.invoice_no} was already finalized.",
                agent_state=AgentState.FINALIZED,
                draft_invoice_id=draft.id,
                invoice={
                    "invoice_id": draft.id,
                    "invoice_no": draft.invoice_no,
                    "pdf_path": pdf_path,
                    "invoice_date": str(draft.invoice_date),
                    "grand_total": draft.grand_total
                }
            )
        
        # Ensure it's a draft (not in an invalid state)
        if draft.status != InvoiceStatus.draft:
            return AgentResponse(
                message=f"Invoice {active_draft_id} has an invalid status: {draft.status.value}.",
                agent_state=AgentState.ERROR
            )
        
        # Load seller from companies table
        company = db.query(Company).first()
        if company:
            draft.seller = {
                "name": company.name,
                "gstin": company.gstin,
                "address": company.address,
                "state": company.state
            }
        
        # Ensure buyer block exists with all required keys
        buyer = draft.buyer or {}
        
        draft.buyer = {
            "name": buyer.get("name"),
            "gstin": buyer.get("gstin"),
            "address": buyer.get("address"),
            "state": buyer.get("state"),
        }
        
        # Validate draft before finalization
        try:
            draft_service.validate_draft_for_finalization(draft, db)
        except ValueError as e:
            return AgentResponse(
                message=f"Cannot finalize invoice: {str(e)}",
                agent_state=AgentState.ERROR,
                draft_invoice_id=draft.id,
                missing_fields=["validation_failed"]
            )
        
        # Convert draft to finalized invoice using existing invoice engine
        # Build InvoiceRequest from draft data
        invoice_request = InvoiceRequest(
            invoice_date=draft.invoice_date.date() if hasattr(draft.invoice_date, 'date') else draft.invoice_date,
            seller=Party(**draft.seller),
            buyer=Party(**draft.buyer),
            items=[
                InvoiceItem(
                    description=item["description"],
                    quantity=item["quantity"],
                    unit_price=item.get("price", item.get("unit_price", 0)),
                    gst_rate=item["gst_rate"]
                )
                for item in draft.items
            ]
        )
        
        # Generate finalized invoice data
        finalized_data = generate_invoice(invoice_request)

        logger.info(
            "finalize_complete session_id=%s agent_state=%s invoice_no=%s",
            session_id,
            AgentState.FINALIZED,
            finalized_data.get("invoice_no"),
        )
        
        # Update draft to finalized status
        draft.status = InvoiceStatus.finalized
        draft.invoice_no = finalized_data["invoice_no"]
        draft.invoice_datetime = finalized_data["invoice_datetime"]
        draft.seller = finalized_data["seller"]
        draft.buyer = finalized_data["buyer"]
        draft.items = finalized_data["items"]
        draft.subtotal = finalized_data["taxable_total"]
        draft.total_gst = finalized_data["gst_total"]
        draft.grand_total = finalized_data["grand_total"]
        
        # Assign full buyer details (production-safe)
        buyer = draft.buyer or {}

        buyer_name = buyer.get("name")
        buyer_gstin = buyer.get("gstin")
        buyer_address = buyer.get("address") or buyer.get("state")
        buyer_state_raw = buyer.get("state")

        draft.buyer_name = normalize_text(buyer_name)
        draft.buyer_gstin = buyer_gstin
        draft.buyer_address = buyer_address

        # Infer state from address
        full_text = buyer.get("address", "") + " " + buyer.get("state", "") + " " + message
        inferred_state = infer_state_from_address(full_text)

        if inferred_state:
            draft.buyer_state = inferred_state

        elif is_valid_indian_state(buyer_state_raw):
            draft.buyer_state = normalize_text(buyer_state_raw)

        else:
            logger.error("finalize_unable_infer_state session_id=%s draft_id=%s", session_id, draft.id)
            return AgentResponse(
                message="Unable to determine buyer state. Please provide a valid Indian state.",
                agent_state=AgentState.AWAITING_CONFIRMATION,
                draft_invoice_id=draft.id,
                missing_fields=["buyer_state"],
            )
    

        # VERY IMPORTANT: assign seller fields LAST
        draft.seller_name = company.name
        draft.seller_gstin = company.gstin
        draft.seller_address = company.address
        draft.seller_state = company.state

        db.flush()
        db.refresh(draft)

        
        # Generate PDF
        pdf_bytes = generate_invoice_pdf(draft)
        
        # Save PDF to file
        pdf_dir = "invoices/pdfs"
        os.makedirs(pdf_dir, exist_ok=True)
        pdf_filename = f"invoice_{draft.invoice_no}.pdf"
        pdf_path = os.path.join(pdf_dir, pdf_filename)
        
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        
        # Clear active draft ID from session (for multiple invoices workflow)
        session_service.clear_active_draft(session_id, db)
        logger.info("active_draft_cleared session_id=%s after_finalization", session_id)
        
        return AgentResponse(
            message=f"Invoice {draft.invoice_no} finalized successfully.",
            agent_state=AgentState.FINALIZED,
            draft_invoice_id=draft.id,
            invoice={
                "invoice_id": draft.id,
                "invoice_no": draft.invoice_no,
                "pdf_path": pdf_path,
                "invoice_date": str(draft.invoice_date),
                "grand_total": draft.grand_total
            }
        )
    
    # Logic 7: LLM extraction fallback
    # Only runs if none of the explicit rule-based handlers matched
    else:
        logger.info("branch_llm_extraction_fallback session_id=%s draft_id=%s", session_id, active_draft_id)
        # LLM extraction: extract structured data and merge into existing draft
        # Pipeline: rule-based extraction → LLM extraction → merge → update draft
        extracted_data = {}
        try:
            extracted_data = extract_invoice_data(message)
        except Exception:
            extracted_data = {}

        # Merge extracted data into existing draft
        if extracted_data and (extracted_data.get("buyer") or extracted_data.get("items")):
            logger.info("extracted_data_found session_id=%s merging_into_draft_id=%s", session_id, active_draft_id)
            
            # Build update payload from extracted data
            update_payload = {}
            if extracted_data.get("buyer"):
                update_payload["buyer"] = _normalize_party_payload(extracted_data["buyer"])
            if extracted_data.get("items"):
                # Merge items: append new items to existing ones
                existing_items = draft.items or []
                new_items = extracted_data["items"]
                update_payload["items"] = existing_items + new_items
            
            # Update existing draft with merged data
            updated_draft = draft_service.update_draft(
                draft_id=active_draft_id,
                invoice_data=update_payload,
                db=db
            )
            
            # Reload draft object
            db.refresh(draft)
            logger.info("draft_updated_from_extraction session_id=%s draft_id=%s", session_id, active_draft_id)
            
            # Build preview from updated draft
            preview_payload = _build_invoice_preview(draft)
            warnings = _get_non_critical_warnings(draft)
            critical_errors = _check_critical_validation_errors(draft)

            logger.info(
                "extraction_merged session_id=%s draft_id=%s agent_state=%s",
                session_id,
                active_draft_id,
                AgentState.AWAITING_CONFIRMATION,
            )

            return AgentResponse(
                agent_state=AgentState.AWAITING_CONFIRMATION,
                message="I've updated the draft. Please review and confirm.",
                invoice=preview_payload,
                draft_invoice_id=active_draft_id,
                warnings=warnings if warnings else None,
                missing_fields=critical_errors if critical_errors else None,
                next_expected_input="Edit details if needed, then confirm to proceed."
            )
        
        # Default response if LLM extraction finds nothing
        return AgentResponse(
            message="I can help you create invoices. Try 'create invoice' to start. You can then update seller/buyer details or 'add <quantity> <item> at <price>' to add items.",
            agent_state=AgentState.COLLECTING_INFO,
            next_expected_input="Use 'create invoice' to start creating a new invoice"
        )
