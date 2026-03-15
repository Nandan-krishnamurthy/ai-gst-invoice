from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from io import BytesIO
from sqlalchemy.orm import Session
from invoice.model import InvoiceRequest, InvoiceResponse
from invoice.invoice_engine import generate_invoice
from app.db.database import get_db
from app.db.crud import create_invoice as db_create_invoice, get_invoice_by_id, get_all_invoices, get_finalized_invoices
from app.services.pdf_generator import generate_invoice_pdf


router = APIRouter(prefix="/invoice", tags=["Invoice"])


@router.get("/")
def list_invoices(
    db: Session = Depends(get_db)
):
    """
    List finalized invoices only, sorted by newest first.
    Use GET /invoice/{invoice_id}/pdf to download a PDF.
    """
    invoices = get_finalized_invoices(db)
    return [
        {
            "invoice_id": inv.id,
            "invoice_number": inv.invoice_no,
            "buyer_name": (inv.buyer or {}).get("name") or inv.buyer_name,
            "total_amount": inv.grand_total,
            "finalized_at": inv.invoice_datetime,
        }
        for inv in invoices
    ]


@router.post("/create", response_model=InvoiceResponse)
def create_invoice(
    invoice_request: InvoiceRequest,
    db: Session = Depends(get_db)
) -> InvoiceResponse:
    """
    Create an invoice with GST calculations and save to database.
    """
    # DIAGNOSTIC: Check request parsing
    print("STEP 1 RAW REQUEST seller:", type(invoice_request.seller), invoice_request.seller)
    print("STEP 1 RAW REQUEST buyer:", type(invoice_request.buyer), invoice_request.buyer)
    print("STEP 1 RAW REQUEST items:", type(invoice_request.items), invoice_request.items)
    
    # Generate invoice with GST calculations (existing logic)
    invoice_data = generate_invoice(invoice_request)
    
    # Transform data to match Invoice model schema
    db_data = {
        "invoice_no": invoice_data["invoice_no"],
        "invoice_date": invoice_data["invoice_date"],
        "invoice_datetime": invoice_data["invoice_datetime"],
        "seller": invoice_data["seller"],
        "buyer": invoice_data["buyer"],
        "items": invoice_data["items"],
        "gst_summary": {},
        "subtotal": invoice_data["taxable_total"],
        "total_gst": invoice_data["gst_total"],
        "grand_total": invoice_data["grand_total"]
    }
    
    # DIAGNOSTIC: Check data before save
    print("STEP 2 BEFORE SAVE seller:", type(db_data["seller"]), db_data["seller"])
    print("STEP 2 BEFORE SAVE buyer:", type(db_data["buyer"]), db_data["buyer"])
    print("STEP 2 BEFORE SAVE items:", type(db_data["items"]), db_data["items"])
    
    # Save to database
    db_create_invoice(db, db_data)
    
    return InvoiceResponse(**invoice_data)


@router.get("/{invoice_id}")
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db)
):
    """
    Fetch a single invoice by ID.
    """
    invoice = get_invoice_by_id(db, invoice_id)
    
    if invoice is None:
        raise HTTPException(status_code=404, detail=f"Invoice with ID {invoice_id} not found")
    
    return invoice


@router.get("/{invoice_id}/pdf")
def download_invoice_pdf(
    invoice_id: int,
    db: Session = Depends(get_db)
):
    """
    Download invoice as PDF file.
    """
    # Fetch invoice from database
    invoice = get_invoice_by_id(db, invoice_id)
    
    if invoice is None:
        raise HTTPException(status_code=404, detail=f"Invoice with ID {invoice_id} not found")
    
    # Generate PDF
    pdf_bytes = generate_invoice_pdf(invoice)
    
    # Create streaming response
    pdf_stream = BytesIO(pdf_bytes)
    
    return StreamingResponse(
        pdf_stream,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=invoice_{invoice.invoice_no}.pdf"
        }
    )
