from typing import Optional
from uuid import UUID
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.agent.agent_state import AgentState
from app.agent.schemas import AgentResponse
from app.customer.crud import find_by_gstin_or_name
from app.customer.handler import _save_customer
from app.db.database import get_db


router = APIRouter(prefix="/customer", tags=["Customer"])


class CustomerCreateRequest(BaseModel):
	name: str
	phone: Optional[str] = None
	email: Optional[str] = None
	address: Optional[str] = None
	gstin: Optional[str] = None
	city: Optional[str] = None
	state: Optional[str] = None

	@field_validator("name")
	@classmethod
	def validate_required_text(cls, value: str) -> str:
		normalized = value.strip()
		if not normalized:
			raise ValueError("field is required")
		return normalized

	@field_validator("phone", "email", "address", "gstin", "city", "state", mode="before")
	@classmethod
	def normalize_optional_text(cls, value):
		if value is None:
			return None
		if isinstance(value, str):
			normalized = value.strip()
			return normalized or None
		return value


@router.post("/create", response_model=AgentResponse)
def create_customer_endpoint(
	payload: CustomerCreateRequest,
	db: Session = Depends(get_db),
):
	"""
	Reuses existing customer persistence logic in app.customer.handler._save_customer,
	which internally calls app.customer.crud.create_customer.
	"""
	session_id = f"api-customer-create-{uuid4()}"

	try:
		save_response = _save_customer(
			session_id=session_id,
			customer_state={
				"name": payload.name,
				"gstin": payload.gstin,
				"address": payload.address,
				"phone": payload.phone,
				"email": payload.email,
				"city": payload.city,
				"state": payload.state,
			},
			db=db,
		)

		if save_response.message == "Customer already exists":
			return save_response

		customer = find_by_gstin_or_name(db=db, name=payload.name, gstin=payload.gstin)
		if customer is None:
			raise HTTPException(status_code=500, detail="Customer was not persisted")

		customer_data = {
			"id": customer.id,
			"name": customer.name,
			"phone": payload.phone,
			"email": payload.email,
			"address": payload.address,
			"gstin": customer.gstin,
			"city": customer.city,
			"state": customer.state,
		}

		return AgentResponse(
			message="Customer created successfully",
			agent_state=AgentState.AWAITING_CONFIRMATION,
			invoice={
				"type": "customer_created",
				"data": customer_data,
			},
		)
	except HTTPException:
		raise
	except ValueError as exc:
		db.rollback()
		raise HTTPException(status_code=400, detail=str(exc)) from exc
	except Exception as exc:
		db.rollback()
		raise HTTPException(status_code=500, detail=str(exc)) from exc
