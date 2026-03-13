from typing import List, Literal, Optional
from pydantic import BaseModel


class Item(BaseModel):
    """Represents a line item in the invoice."""
    name: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    confidence: Literal["high", "medium", "low"]


class Understanding(BaseModel):
    """Represents what an AI agent understands from a business conversation."""
    buyer_name: Optional[str] = None
    buyer_gstin: Optional[str] = None
    items: List[Item]
    gst_discussed: bool
    gst_inclusive: Optional[bool] = None
    intent_state: Literal["inquiry", "negotiation", "agreement", "not_ready"]
    missing_info: List[str]
    assumptions: List[str]
