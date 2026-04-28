from typing import Dict
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.db.models import Invoice, InvoiceStatus
from app.agent import session_service
from app.utils.location_utils import infer_state_from_address, normalize_text
CITY_STATE_MAP = {
    "mumbai": "Maharashtra",
    "pune": "Maharashtra",
    "nagpur": "Maharashtra",
    "bangalore": "Karnataka",
    "bengaluru": "Karnataka",
    "mysore": "Karnataka",
    "delhi": "Delhi",
    "new delhi": "Delhi",
    "chennai": "Tamil Nadu",
    "coimbatore": "Tamil Nadu",
    "hyderabad": "Telangana",
    "secunderabad": "Telangana",
    "kolkata": "West Bengal",
    "ahmedabad": "Gujarat",
    "surat": "Gujarat",
    "jaipur": "Rajasthan",
    "lucknow": "Uttar Pradesh",
    "indore": "Madhya Pradesh",
    "bhopal": "Madhya Pradesh",
    "chandigarh": "Chandigarh",
    "kochi": "Kerala",
    "cochin": "Kerala",
}


def _normalize_invoice_items(items: list) -> list:
    normalized_items = []
    for item in items or []:
        normalized_items.append({
            "description": item.get("description") or "",
            "quantity": item.get("quantity") or 0,
            "unit_price": item.get("unit_price") or item.get("price") or 0,
            "gst_rate": item.get("gst_rate") or 0,
            "hsn_code": item.get("hsn_code") or item.get("hsn"),
        })
    return normalized_items


def _normalize_party_data(party: dict) -> dict:
    party = party or {}
    name = party.get("name")
    gstin = party.get("gstin")
    address = party.get("address")
    state = party.get("state")
    return {
        "name": name if name else None,
        "gstin": gstin if gstin else None,
        "address": address if address else None,
        "state": state if state else None,
    }


def _infer_state_from_city(text: str) -> str:
    if not text:
        return None
    lowered = text.lower()
    for city, state in CITY_STATE_MAP.items():
        if city in lowered:
            return state
    return None


def _infer_buyer_state(buyer: dict) -> str:
    combined_text = ((buyer.get("address") or "") + " " + (buyer.get("state") or "")).strip()
    inferred = infer_state_from_address(combined_text.lower()) if combined_text else None
    if not inferred:
        inferred = infer_state_from_address(buyer.get("state"))
    if not inferred:
        inferred = _infer_state_from_city(combined_text)
    if not inferred:
        inferred = _infer_state_from_city(buyer.get("address") or "")
    if inferred:
        return normalize_text(inferred)
    return None
from engine.gst_calculator import calculate_gst


def create_draft(
    session_id: str,
    invoice_data: dict,
    db: Session
) -> dict:
    """
    Create a new draft invoice.
    
    Args:
        session_id: Session ID to link the draft to
        invoice_data: Dictionary containing invoice details (seller, buyer, items, etc.)
        db: Database session
    
    Returns:
        Dictionary with draft_id and preview data
    """
    # Generate a temporary invoice number for the draft
    draft_invoice_no = f"DRAFT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    
    from app.models.company import Company

    # Extract data from invoice_data
    seller = _normalize_party_data(invoice_data.get("seller", {}))
    buyer = _normalize_party_data(invoice_data.get("buyer", {}))
    items = _normalize_invoice_items(invoice_data.get("items", []))
    invoice_date = invoice_data.get("invoice_date", datetime.now(timezone.utc))
    
    # Load seller from companies table (source of truth)
    company = db.query(Company).first()
    if company:
        seller = {
            "name": company.name,
            "gstin": company.gstin,
            "address": company.address,
            "state": company.state
        }

    # Infer correct buyer state from address/state/city
    inferred_buyer_state = _infer_buyer_state(buyer)
    if inferred_buyer_state and not buyer.get("state"):
        buyer["state"] = inferred_buyer_state
    if not inferred_buyer_state:
        inferred_buyer_state = normalize_text(buyer.get("state"))
    if not inferred_buyer_state:
        inferred_buyer_state = "TBD"

    # Calculate GST summary
    gst_summary = _calculate_gst_summary(seller, buyer, items)
    
    # Create draft invoice
    draft = Invoice(
        invoice_no=draft_invoice_no,
        invoice_date=invoice_date,
        invoice_datetime=datetime.now(timezone.utc),
        seller=seller,
        buyer=buyer,
        items=items,
        gst_summary=gst_summary,
        subtotal=gst_summary["subtotal"],
        total_gst=gst_summary["total_gst"],
        grand_total=gst_summary["grand_total"],
        seller_name=seller.get("name"),
        seller_gstin=seller.get("gstin"),
        seller_address=seller.get("address"),
        seller_state=seller.get("state"),
        buyer_name=buyer.get("name"),
        buyer_gstin=buyer.get("gstin"),
        buyer_address=buyer.get("address"),
        buyer_state=inferred_buyer_state,
        status=InvoiceStatus.draft,
        session_id=session_id
    )
    
    db.add(draft)
    db.flush()
    db.refresh(draft)
    
    return {
        "draft_id": draft.id,
        "invoice_no": draft.invoice_no,
        "status": draft.status.value,
        "seller": draft.seller,
        "buyer": draft.buyer,
        "items": draft.items,
        "subtotal": draft.subtotal,
        "total_gst": draft.total_gst,
        "grand_total": draft.grand_total,
        "gst_summary": draft.gst_summary
    }


def update_draft(
    draft_id: str,
    invoice_data: dict,
    db: Session
) -> dict:
    """
    Update an existing draft invoice.
    
    Args:
        draft_id: ID of the draft to update
        invoice_data: Dictionary containing updated invoice details
        db: Database session
    
    Returns:
        Dictionary with updated preview data
    
    Raises:
        ValueError: If draft not found or invoice is not a draft
    """
    # Load invoice by draft_id
    draft = db.query(Invoice).filter(Invoice.id == draft_id).first()
    
    if not draft:
        raise ValueError(f"Draft with ID {draft_id} not found")
    
    if draft.status != InvoiceStatus.draft:
        raise ValueError(f"Invoice {draft_id} is not a draft (status: {draft.status.value})")
    
    # Update fields if provided
    if "seller" in invoice_data:
        normalized_seller = _normalize_party_data(invoice_data["seller"])
        draft.seller = normalized_seller
        # Persist seller details to denormalized columns for database storage
        draft.seller_name = normalized_seller.get("name")
        draft.seller_gstin = normalized_seller.get("gstin")
        draft.seller_address = normalized_seller.get("address")
        draft.seller_state = normalized_seller.get("state")
    if "buyer" in invoice_data:
        normalized_buyer = _normalize_party_data(invoice_data["buyer"])
        # Try to infer state from address or city information if not provided
        inferred_buyer_state = _infer_buyer_state(normalized_buyer)
        if inferred_buyer_state and not normalized_buyer.get("state"):
            # Use inferred state if no explicit state was provided
            normalized_buyer["state"] = inferred_buyer_state
        
        draft.buyer = normalized_buyer
        # Always set buyer_state to a value: either from buyer data, inferred, or existing
        new_buyer_state = normalized_buyer.get("state") or inferred_buyer_state or draft.buyer_state
        draft.buyer_state = new_buyer_state if new_buyer_state else "TBD"
        
        # Persist buyer details to denormalized columns for database storage
        draft.buyer_name = normalized_buyer.get("name")
        draft.buyer_gstin = normalized_buyer.get("gstin")
        draft.buyer_address = normalized_buyer.get("address")
        # buyer_state is already set above
    if "items" in invoice_data:
        draft.items = _normalize_invoice_items(invoice_data["items"])
    if "invoice_date" in invoice_data:
        draft.invoice_date = invoice_data["invoice_date"]
    
    # Recalculate GST
    gst_summary = _calculate_gst_summary(draft.seller, draft.buyer, draft.items)
    draft.gst_summary = gst_summary
    draft.subtotal = gst_summary["subtotal"]
    draft.total_gst = gst_summary["total_gst"]
    draft.grand_total = gst_summary["grand_total"]
    
    db.flush()
    db.refresh(draft)
    
    return {
        "draft_id": draft.id,
        "invoice_no": draft.invoice_no,
        "status": draft.status.value,
        "seller": draft.seller,
        "buyer": draft.buyer,
        "items": draft.items,
        "subtotal": draft.subtotal,
        "total_gst": draft.total_gst,
        "grand_total": draft.grand_total,
        "gst_summary": draft.gst_summary
    }


def get_or_create_draft_for_session(
    session_id: str,
    invoice_data: dict,
    db: Session
) -> dict:
    """
    Get active draft for session or create a new one.
    
    Args:
        session_id: Session ID
        invoice_data: Dictionary containing invoice details
        db: Database session
    
    Returns:
        Dictionary with draft preview data
    """
    # Check for active draft
    active_draft_id = session_service.get_active_draft(session_id, db)
    
    if active_draft_id:
        # Update existing draft
        try:
            return update_draft(active_draft_id, invoice_data, db)
        except ValueError:
            # If draft not found or not a draft anymore, create new one
            pass
    
    # Create new draft
    draft = create_draft(session_id, invoice_data, db)
    
    # Set as active draft
    session_service.set_active_draft(session_id, str(draft["draft_id"]), db)
    
    return draft


def _calculate_gst_summary(seller: dict, buyer: dict, items: list) -> Dict[str, float]:
    """
    Calculate GST summary for invoice items.
    
    Args:
        seller: Seller information with state
        buyer: Buyer information with state
        items: List of invoice items
    
    Returns:
        Dictionary with subtotal, total_gst, and grand_total
    """
    # Determine supply type
    seller_state = normalize_text(seller.get("state")) or ""
    buyer_state = normalize_text(buyer.get("state")) or ""
    if not buyer_state:
        buyer_state = _infer_buyer_state(buyer) or ""
    is_inter_state = seller_state != buyer_state
    supply_type = "inter" if is_inter_state else "intra"
    
    # Initialize totals
    subtotal = 0.0
    total_gst = 0.0
    total_cgst = 0.0
    total_sgst = 0.0
    total_igst = 0.0
    
    # Calculate for each item
    for item in items:
        quantity = item.get("quantity") or 0
        price = item.get("unit_price") or item.get("price") or 0
        gst_rate = item.get("gst_rate") or 0
        
        taxable_value = quantity * price
        
        # Calculate GST using the GST engine (skip if gst_rate is 0)
        if gst_rate > 0:
            gst_result = calculate_gst(
                taxable_value=taxable_value,
                gst_rate=gst_rate,
                supply_type=supply_type
            )
            subtotal += taxable_value
            total_gst += gst_result["total_tax"]
            total_cgst += gst_result["cgst_amount"]
            total_sgst += gst_result["sgst_amount"]
            total_igst += gst_result["igst_amount"]
        else:
            # No GST for 0% items
            subtotal += taxable_value
    
    grand_total = subtotal + total_gst
    
    return {
        "subtotal": round(subtotal, 2),
        "total_gst": round(total_gst, 2),
        "cgst": round(total_cgst, 2),
        "sgst": round(total_sgst, 2),
        "igst": round(total_igst, 2),
        "grand_total": round(grand_total, 2),
        "supply_type": supply_type
    }


def validate_draft_for_finalization(draft: Invoice, db: Session) -> None:
    """
    Validate whether a draft invoice can be finalized.
    
    Args:
        draft: The draft invoice to validate
        db: Database session
    
    Raises:
        ValueError: If the draft is missing mandatory fields, has invalid data,
                   incorrect GST calculations, or is already finalized
    """
    # Check if already finalized
    if draft.status != InvoiceStatus.draft:
        raise ValueError(
            f"Invoice {draft.id} is already finalized or has status: {draft.status.value}"
        )
    
    # Validate seller information (address is optional)
    seller = draft.seller or {}
    missing_seller_fields = []
    
    if not seller.get("name") or seller.get("name") == "TBD":
        missing_seller_fields.append("seller.name")
    if not seller.get("state") or seller.get("state") == "TBD":
        missing_seller_fields.append("seller.state")
    if not seller.get("gstin") or seller.get("gstin") == "TBD":
        missing_seller_fields.append("seller.gstin")
    
    if missing_seller_fields:
        raise ValueError(
            f"Missing or incomplete seller information: {', '.join(missing_seller_fields)}"
        )
    
    # Validate buyer information (address is optional)
    buyer = draft.buyer or {}
    missing_buyer_fields = []
    
    if not buyer.get("name") or buyer.get("name") == "TBD":
        missing_buyer_fields.append("buyer.name")
    if not buyer.get("state") or buyer.get("state") == "TBD":
        missing_buyer_fields.append("buyer.state")
    if not buyer.get("gstin") or buyer.get("gstin") == "TBD":
        missing_buyer_fields.append("buyer.gstin")
    
    if missing_buyer_fields:
        raise ValueError(
            f"Missing or incomplete buyer information: {', '.join(missing_buyer_fields)}"
        )
    
    # Validate items
    items = draft.items or []
    
    if not items or len(items) == 0:
        raise ValueError("Invoice must have at least one item")
    
    # Validate each item
    for idx, item in enumerate(items):
        item_errors = []
        
        # Check required fields
        if not item.get("description"):
            item_errors.append("description")
        
        # Validate quantity
        quantity = item.get("quantity") or 0
        if quantity <= 0:
            item_errors.append(f"quantity (must be > 0, got {quantity})")
        
        # Validate price
        price = item.get("unit_price") or item.get("price") or 0
        if price < 0:
            item_errors.append(f"price (must be >= 0, got {price})")
        
        # Validate GST rate
        gst_rate = item.get("gst_rate")
        if gst_rate is None:
            item_errors.append("gst_rate (missing)")
        elif gst_rate not in [0, 5, 12, 18, 28]:
            item_errors.append(f"gst_rate (invalid rate: {gst_rate}%, must be 0, 5, 12, 18, or 28)")
        
        # Validate HSN code for taxable items
        if gst_rate is not None and gst_rate > 0:
            hsn_code = item.get("hsn_code")
            if not hsn_code:
                item_errors.append(f"hsn_code (required for items with GST rate > 0)")
        
        if item_errors:
            raise ValueError(
                f"Item {idx + 1} ({item.get('description', 'unknown')}) has invalid data: {', '.join(item_errors)}"
            )
    
    # Validate GST calculations
    expected_gst_summary = _calculate_gst_summary(seller, buyer, items)
    
    # Allow small rounding differences (up to 0.02)
    tolerance = 0.02
    
    if abs(draft.subtotal - expected_gst_summary["subtotal"]) > tolerance:
        raise ValueError(
            f"GST calculation mismatch: subtotal is {draft.subtotal}, "
            f"but should be {expected_gst_summary['subtotal']}"
        )
    
    if abs(draft.total_gst - expected_gst_summary["total_gst"]) > tolerance:
        raise ValueError(
            f"GST calculation mismatch: total GST is {draft.total_gst}, "
            f"but should be {expected_gst_summary['total_gst']}"
        )
    
    if abs(draft.grand_total - expected_gst_summary["grand_total"]) > tolerance:
        raise ValueError(
            f"GST calculation mismatch: grand total is {draft.grand_total}, "
            f"but should be {expected_gst_summary['grand_total']}"
        )

