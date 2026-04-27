from sqlalchemy.orm import Session
from .models import Invoice

def create_invoice(db: Session, invoice_data: dict):
    print("CRUD RECEIVED DATA:", invoice_data)
    invoice = Invoice(
        invoice_no=invoice_data["invoice_no"],
        invoice_date=invoice_data["invoice_date"],
        invoice_datetime=invoice_data["invoice_datetime"],
        seller=invoice_data["seller"],
        buyer=invoice_data["buyer"],
        items=invoice_data["items"],
        gst_summary=invoice_data["gst_summary"],
        subtotal=invoice_data["subtotal"],
        total_gst=invoice_data["total_gst"],
        grand_total=invoice_data["grand_total"],
        buyer_name=invoice_data.get("buyer_name"),
        buyer_gstin=invoice_data.get("buyer_gstin"),
        buyer_address=invoice_data.get("buyer_address"),
        buyer_state=invoice_data.get("buyer_state"),
        seller_name=invoice_data.get("seller_name"),
        seller_gstin=invoice_data.get("seller_gstin"),
        seller_address=invoice_data.get("seller_address"),
        seller_state=invoice_data.get("seller_state")
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice

def get_invoice_by_id(db: Session, invoice_id: int):
    return db.query(Invoice).filter(Invoice.id == invoice_id).first()

def get_all_invoices(db: Session):
    return db.query(
        Invoice.id,
        Invoice.invoice_no,
        Invoice.invoice_date,
        Invoice.subtotal,
        Invoice.total_gst,
        Invoice.grand_total
    ).order_by(Invoice.invoice_date.desc()).all()

def get_finalized_invoices(db: Session):
    from .models import InvoiceStatus
    return db.query(Invoice).filter(
        Invoice.status == InvoiceStatus.finalized
    ).order_by(Invoice.invoice_datetime.desc()).all()