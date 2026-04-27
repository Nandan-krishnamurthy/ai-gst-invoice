from typing import Optional, Dict, Any

from sqlalchemy import Column, Integer, String, func
from sqlalchemy.orm import Session

from app.db.database import Base

try:
    # Preferred path when a shared Customer model exists in app.db.models
    from app.db.models import Customer  # type: ignore
except ImportError:
    class Customer(Base):
        __tablename__ = "customers"

        id = Column(Integer, primary_key=True, index=True)
        name = Column(String, nullable=False, index=True)
        gstin = Column(String, nullable=True, unique=True, index=True)
        address = Column(String, nullable=True)
        city = Column(String, nullable=True)
        state = Column(String, nullable=True)
        customer_type = Column(String, nullable=False)


def map_customer_state_to_customer_payload(customer_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize customer_state and return a payload compatible with Customer ORM.
    """
    name = (customer_state.get("name") or "").strip()
    gstin = (customer_state.get("gstin") or "").strip().upper() or None
    address = (customer_state.get("address") or "").strip() or None
    city = (customer_state.get("city") or "").strip() or None
    state = (customer_state.get("state") or "").strip() or None

    if not name:
        raise ValueError("Customer name is required")

    return {
        "name": name,
        "gstin": gstin,
        "address": address,
        "city": city,
        "state": state,
        "customer_type": "B2B" if gstin else "B2C",
    }


def create_customer(db: Session, customer_state: Dict[str, Any], auto_commit: bool = True):
    payload = map_customer_state_to_customer_payload(customer_state)

    customer = Customer(
        name=payload["name"],
        gstin=payload["gstin"],
        address=payload["address"],
        city=payload["city"],
        state=payload["state"],
        customer_type=payload["customer_type"],
    )
    db.add(customer)
    db.flush()

    if auto_commit:
        db.commit()

    db.refresh(customer)
    return customer


def find_by_gstin_or_name(db: Session, name: str, gstin: Optional[str]):
    normalized_name = name.strip()
    normalized_gstin = gstin.strip().upper() if gstin else None

    if normalized_gstin:
        return db.query(Customer).filter(Customer.gstin == normalized_gstin).first()

    return (
        db.query(Customer)
        .filter(func.lower(Customer.name) == normalized_name.lower())
        .first()
    )
