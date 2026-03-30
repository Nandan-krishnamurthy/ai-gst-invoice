from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Invoice, InvoiceStatus
from app.agent import session_service, draft_service, agent_service
from app.agent.schemas import (
    AgentDraftRequest,
    InvoiceDraftRequest,
    InvoiceDraftResponse,
    FinalizeInvoiceRequest,
    FinalizeInvoiceResponse,
    InvoiceEditRequest,
    AgentResponse
)
from app.services.pdf_generator import generate_invoice_pdf
from invoice.invoice_engine import generate_invoice
from invoice.model import InvoiceRequest, Party, InvoiceItem
from app.agent.agent_state import AgentState
from app.customer.intent import is_customer_intent
from app.customer.handler import handle_customer_message, has_active_customer_session
import os
import copy


router = APIRouter(prefix="/agent", tags=["Agent"])


@router.post("/invoice/draft", response_model=AgentResponse)
def create_or_update_draft(
    payload: AgentDraftRequest,
    db: Session = Depends(get_db)
):
    """
    Handle agent message for draft invoice creation.
    """
    try:
        # Router-level domain interception: customer intents bypass invoice agent.
        # Active customer sessions always route to customer handler regardless of message content.
        if has_active_customer_session(payload.session_id) or is_customer_intent(payload.message):
            result = handle_customer_message(
                session_id=payload.session_id,
                message=payload.message,
                db=db,
            )
            db.commit()
            return result

        result = agent_service.handle_message(
            session_id=payload.session_id,
            message=payload.message,
            db=db
        )
        
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


@router.patch("/invoice/edit", response_model=AgentResponse)
def edit_draft(
    request: InvoiceEditRequest,
    db: Session = Depends(get_db)
):
    """
    Edit an existing draft invoice in-place.
    Accepts partial updates: seller, buyer, items, or any top-level field.
    Does not create a new draft — updates the existing one.
    """
    try:
        # Load the draft
        draft = db.query(Invoice).filter(Invoice.id == request.draft_invoice_id).first()

        if not draft:
            raise HTTPException(
                status_code=404,
                detail=f"Draft with ID {request.draft_invoice_id} not found."
            )

        if draft.status != InvoiceStatus.draft:
            raise HTTPException(
                status_code=400,
                detail=f"Invoice {request.draft_invoice_id} is not a draft (status: {draft.status.value})."
            )

        # Preserve existing buyer fields on partial buyer updates (e.g., address-only, gstin-only).
        safe_updates = copy.deepcopy(request.updates)
        if isinstance(safe_updates.get("buyer"), dict):
            existing_buyer = copy.deepcopy(draft.buyer) if isinstance(draft.buyer, dict) else {}
            existing_buyer.update(safe_updates["buyer"])
            safe_updates["buyer"] = existing_buyer

        # Apply the partial update
        updated = draft_service.update_draft(
            draft_id=request.draft_invoice_id,
            invoice_data=safe_updates,
            db=db
        )

        # Sync denormalized buyer columns if buyer was updated
        if "buyer" in safe_updates:
            buyer_data = draft.buyer or {}
            draft.buyer_name = buyer_data.get("name")
            draft.buyer_gstin = buyer_data.get("gstin")
            draft.buyer_address = buyer_data.get("address")
            draft.buyer_state = buyer_data.get("state")
            db.flush()
            db.refresh(draft)

        db.commit()
        db.refresh(draft)

        # Build preview and collect warnings
        from app.agent.agent_service import _build_invoice_preview, _check_critical_validation_errors, _get_non_critical_warnings
        preview_payload = _build_invoice_preview(draft)
        critical_errors = _check_critical_validation_errors(draft)
        warnings = _get_non_critical_warnings(draft)

        return AgentResponse(
            message="Draft updated successfully.",
            agent_state=AgentState.AWAITING_CONFIRMATION,
            draft_invoice_id=draft.id,
            invoice=preview_payload,
            missing_fields=critical_errors if critical_errors else None,
            warnings=warnings if warnings else None,
            next_expected_input="Review the updated invoice and confirm when ready."
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


@router.post("/invoice/finalize", response_model=AgentResponse)
def finalize_invoice(
    request: FinalizeInvoiceRequest,
    db: Session = Depends(get_db)
):
    """
    Finalize a draft invoice and generate PDF.
    """
    # Check confirmation
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation required. Set 'confirm' to true to finalize the invoice."
        )
    
    # Fetch active draft
    active_draft_id = session_service.get_active_draft(request.session_id, db)
    
    if not active_draft_id:
        raise HTTPException(
            status_code=404,
            detail="No active draft found for this session."
        )
    
    # Load the draft invoice
    draft = db.query(Invoice).filter(Invoice.id == active_draft_id).first()
    
    if not draft:
        raise HTTPException(
            status_code=404,
            detail=f"Draft invoice with ID {active_draft_id} not found."
        )
    
    # Ensure it's a draft
    if draft.status != InvoiceStatus.draft:
        raise HTTPException(
            status_code=400,
            detail=f"Invoice {active_draft_id} is not a draft (status: {draft.status.value})."
        )
    
    # Convert draft to finalized invoice using existing invoice engine
    # Build InvoiceRequest from draft data
    invoice_request = InvoiceRequest(
        invoice_date=draft.invoice_date.date() if hasattr(draft.invoice_date, 'date') else draft.invoice_date,
        seller=Party(
            name=draft.seller_name,
            gstin=draft.seller_gstin,
            address=draft.seller_address,
            state=draft.seller_state,
        ),
        
        buyer=Party(
            name=draft.buyer_name,
            gstin=draft.buyer_gstin,
            address=draft.buyer_address,
            state=draft.buyer_state,
        ),
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
    
    db.commit()
    db.refresh(draft)
    
    # Generate PDF
    pdf_bytes = generate_invoice_pdf(draft)
    
    # Save PDF to file (or return bytes - adjust based on your needs)
    pdf_dir = "invoices/pdfs"
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_filename = f"invoice_{draft.invoice_no}.pdf"
    pdf_path = os.path.join(pdf_dir, pdf_filename)
    
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)
    
    # Clear active draft ID from session (for multiple invoices workflow)
    session_service.clear_active_draft(request.session_id, db)
    db.commit()
    
    from app.agent.agent_state import AgentState
    
    return AgentResponse(
        message=f"Invoice {draft.invoice_no} finalized successfully.",
        agent_state=AgentState.FINALIZED,
        draft_invoice_id=draft.id,
        invoice={
            "invoice_id": draft.id,
            "invoice_no": draft.invoice_no,
            "pdf_path": pdf_path,
            "invoice_date": str(draft.invoice_date),
            "items": finalized_data["items"],
            "subtotal": finalized_data["taxable_total"],
            "cgst_amount": sum(item.get("cgst", 0) for item in finalized_data["items"]),
            "sgst_amount": sum(item.get("sgst", 0) for item in finalized_data["items"]),
            "igst_amount": sum(item.get("igst", 0) for item in finalized_data["items"]),
            "total_tax": finalized_data["gst_total"],
            "grand_total": finalized_data["grand_total"]
        }
    )
