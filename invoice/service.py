from datetime import date, datetime, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.db.crud import create_invoice as db_create_invoice
from invoice.invoice_engine import generate_invoice
from invoice.model import InvoiceItem, InvoiceRequest, Party


def _coerce_invoice_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        # Accept both YYYY-MM-DD and full ISO datetime strings.
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            return datetime.now(timezone.utc).date()
    return datetime.now(timezone.utc).date()


def create_invoice_service(db: Session, request_data: Dict[str, Any]):
    seller_payload = request_data.get("seller") or {}
    buyer_payload = request_data.get("buyer") or {}
    items_payload = request_data.get("items") or []

    invoice_date = _coerce_invoice_date(request_data.get("invoice_date"))

    invoice_items = []
    for item in items_payload:
        invoice_items.append(
            InvoiceItem(
                description=item.get("description") or "",
                quantity=float(item.get("quantity") or 0),
                unit_price=float(item.get("unit_price", item.get("price", 0)) or 0),
                gst_rate=int(item.get("gst_rate") or 0),
            )
        )

    invoice_request = InvoiceRequest(
        invoice_date=invoice_date,
        seller=Party(
            name=seller_payload.get("name"),
            state=(seller_payload.get("state") or ""),
        ),
        buyer=Party(
            name=buyer_payload.get("name"),
            state=(buyer_payload.get("state") or ""),
        ),
        items=invoice_items,
    )

    invoice_data = generate_invoice(invoice_request)
    invoice_data["invoice_datetime"] = datetime.now(timezone.utc)

    buyer_name = request_data.get("buyer_name") or (request_data.get("buyer") or {}).get("name")
    seller_name = request_data.get("seller_name") or (request_data.get("seller") or {}).get("name")
    buyer_state = request_data.get("buyer_state") or (request_data.get("buyer") or {}).get("state")
    seller_state = request_data.get("seller_state") or (request_data.get("seller") or {}).get("state")

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
        "grand_total": invoice_data["grand_total"],
        "buyer_name": buyer_name,
        "buyer_state": buyer_state,
        "seller_name": seller_name,
        "seller_state": seller_state,
    }

    return db_create_invoice(db, db_data)
