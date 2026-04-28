from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from io import BytesIO
from sqlalchemy.orm import Session
from invoice.model import InvoiceResponse
from app.db.database import get_db
from app.db.crud import get_invoice_by_id, get_all_invoices
from app.services.pdf_generator import generate_invoice_pdf
from invoice.service import create_invoice_service


router = APIRouter(prefix="/invoice", tags=["Invoice"])


@router.get("/")
def list_invoices(
    db: Session = Depends(get_db)
):
    """
    List all invoices, sorted by newest first.
    Use GET /invoice/{invoice_id}/pdf to download a PDF.
    """
    invoices = get_all_invoices(db)
    return [
        {
            "invoice_id": inv.id,
            "invoice_number": inv.invoice_no,
            "buyer_name": None,
            "total_amount": inv.grand_total,
            "finalized_at": inv.invoice_date,
        }
        for inv in invoices
    ]


@router.post("/create", response_model=InvoiceResponse)
async def create_invoice(
    request: Request,
    db: Session = Depends(get_db)
) -> InvoiceResponse:
    """
    Create an invoice with GST calculations and save to database.
    """
    request_data = await request.json()
    print("RAW REQUEST DATA:", request_data)

    try:
        invoice = create_invoice_service(db, request_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return InvoiceResponse(
        invoice_no=invoice.invoice_no,
        invoice_date=invoice.invoice_date,
        invoice_datetime=invoice.invoice_datetime,
        seller=invoice.seller,
        buyer=invoice.buyer,
        items=invoice.items,
        taxable_total=invoice.subtotal,
        gst_total=invoice.total_gst,
        grand_total=invoice.grand_total,
        buyer_name=invoice.buyer_name,
        seller_name=invoice.seller_name,
        buyer_state=invoice.buyer_state,
        seller_state=invoice.seller_state,
    )


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
