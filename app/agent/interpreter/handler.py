from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.agent import draft_service, session_service
from app.customer.handler import CustomerContact, normalize_phone_number
from app.customer.crud import Customer
from app.db.database import get_db
from app.agent.interpreter.service import interpret_conversation
from app.services.ocr_service import mistral_ocr
from app.models.company import Company


router = APIRouter(tags=["Interpreter"])


def _extract_text_from_image(file_bytes: bytes, mime_type: Optional[str]) -> str:
	return mistral_ocr(file_bytes=file_bytes, mime_type=mime_type or "image/png")


@router.post("/interpreter")
async def run_interpreter(
	session_id: Optional[str] = Form(default=None),
	text: Optional[str] = Form(default=None),
	image: Optional[UploadFile] = File(default=None),
	db: Session = Depends(get_db),
):
	"""Interpret conversation text/image and return preview actions only."""
	if not text and not image:
		raise HTTPException(status_code=400, detail="Provide either text or image.")

	raw_text = (text or "").strip()

	if image is not None:
		try:
			file_bytes = await image.read()
			raw_text = _extract_text_from_image(file_bytes, image.content_type)
		except Exception as exc:
			raise HTTPException(status_code=400, detail=f"OCR failed: {exc}") from exc

	if not raw_text:
		raise HTTPException(status_code=400, detail="Could not extract conversation text.")

	result = interpret_conversation(raw_text)
	customer = result.get("customer") or {}
	phone = customer.get("phone")
	existing_customer = None

	if phone:
		normalized_phone = normalize_phone_number(phone)
		if normalized_phone:
			contact = db.query(CustomerContact).filter(CustomerContact.phone == normalized_phone).first()
			if contact:
				customer_record = db.query(Customer).filter(
					Customer.id == contact.customer_id
				).first()
				existing_customer = {
					"id": contact.customer_id,
					"name": contact.contact_name,
					"phone": contact.phone,
					"state": getattr(customer_record, "state", None),
					"address": getattr(customer_record, "address", None),
					"gstin": getattr(customer_record, "gstin", None),
					"city": getattr(customer_record, "city", None),
				}

	if existing_customer:
		customer["type"] = "existing"
		customer["details"] = existing_customer
		customer["state"] = existing_customer.get("state")
		customer["city"] = customer.get("city") or existing_customer.get("city")
		customer["gstin"] = customer.get("gstin") or existing_customer.get("gstin")
		customer["address"] = customer.get("address") or existing_customer.get("address")
		result["customer"] = customer

	active_session_id = session_service.get_or_create_session(session_id=session_id, db=db)
	invoice_payload = result.get("invoice") or {}
	raw_items = invoice_payload.get("items") or []
	gst_rate = int(invoice_payload.get("gst") or 0)

	draft_items = []
	for item in raw_items:
		draft_items.append(
			{
				"description": item.get("name") or item.get("description") or "",
				"quantity": float(item.get("quantity") or 0),
				"price": float(item.get("price") or item.get("unit_price") or 0),
				"gst_rate": gst_rate,
			}
		)

	draft_payload = {
		"buyer": {
			"name": customer.get("name"),
			"gstin": customer.get("gstin"),
			"address": customer.get("address"),
			"state": customer.get("state"),
		},
		"items": draft_items,
	}

	# Populate seller from company profile so validation passes at finalize.
	company = db.query(Company).first()
	if company:
		draft_payload["seller"] = {
			"name": company.name,
			"gstin": company.gstin,
			"address": company.address,
			"state": company.state,
		}

	draft = draft_service.create_draft(
		session_id=active_session_id,
		invoice_data=draft_payload,
		db=db,
	)
	session_service.set_active_draft(active_session_id, str(draft["draft_id"]), db)
	db.commit()
	result["draft_invoice_id"] = draft["draft_id"]
	result["session_id"] = active_session_id

	return result
