from sqlalchemy import Column, Integer, String, Float, DateTime, Enum
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, timezone
from app.db.database import Base
import enum


class InvoiceStatus(enum.Enum):
    draft = "draft"
    finalized = "finalized"
    deleted = "deleted"


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    session_id = Column(String, primary_key=True, index=True)
    active_draft_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_no = Column(String, unique=True, index=True)
    invoice_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    invoice_datetime = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    seller = Column(JSONB)
    buyer = Column(JSONB)
    items = Column(JSONB)
    gst_summary = Column(JSONB)
    subtotal = Column(Float)
    total_gst = Column(Float)
    grand_total = Column(Float)
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.draft, nullable=False)
    session_id = Column(String, nullable=True, index=True)

    # Seller details (denormalized for PDF and reporting)
    seller_name = Column(String, nullable=True)
    seller_gstin = Column(String, nullable=True)
    seller_address = Column(String, nullable=True)
    seller_state = Column(String, nullable=True)

    # Buyer details (denormalized for PDF and reporting)
    buyer_name = Column(String, nullable=True)
    buyer_gstin = Column(String, nullable=True)
    buyer_address = Column(String, nullable=True)
    buyer_state = Column(String, nullable=True)