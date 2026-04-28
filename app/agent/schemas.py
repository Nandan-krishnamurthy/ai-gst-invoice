from typing import Optional
from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import date
from .agent_state import AgentState


class AgentResponse(BaseModel):
    """
    Standard response format for all agent endpoints.
    Provides consistent structure for agent interactions.
    """
    model_config = ConfigDict(use_enum_values=False)
    
    message: str  # Human-readable message for the user
    agent_state: AgentState  # Current agent state
    draft_invoice_id: Optional[int] = None  # Draft invoice ID if draft was created
    invoice: Optional[Dict[str, Any]] = None  # Invoice data/preview
    missing_fields: Optional[List[str]] = None  # Critical fields that block finalization
    warnings: Optional[List[str]] = None  # Non-critical fields that can be filled later
    next_expected_input: Optional[str] = None  # Hint for what user should provide next


class AgentDraftRequest(BaseModel):
    session_id: str
    message: str


class InvoiceEditRequest(BaseModel):
    """Request body for editing an existing draft invoice."""
    draft_invoice_id: int
    updates: Dict[str, Any]  # Partial update: seller, buyer, items, or any top-level field


class InvoiceItemInput(BaseModel):
    description: str
    quantity: float
    price: float
    gst_rate: int


class InvoiceDraftRequest(BaseModel):
    session_id: Optional[str] = None
    invoice_date: date
    seller: Dict[str, Any]
    buyer: Dict[str, Any]
    items: List[InvoiceItemInput]


class InvoiceDraftResponse(BaseModel):
    session_id: str
    draft_id: int
    preview: Dict[str, Any]
    message: str


class FinalizeInvoiceRequest(BaseModel):
    session_id: str
    confirm: bool
    invoice_data: Optional[dict] = None


class FinalizeInvoiceResponse(BaseModel):
    invoice_id: int
    invoice_no: str
    pdf_path: str
    message: str
