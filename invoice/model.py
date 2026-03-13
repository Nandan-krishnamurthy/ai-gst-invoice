from pydantic import BaseModel
from typing import List
from datetime import date, datetime


class Party(BaseModel):
    state: str


class InvoiceItem(BaseModel):
    description: str
    quantity: float
    unit_price: float
    gst_rate: int


class InvoiceRequest(BaseModel):
    invoice_date: date
    seller: Party
    buyer: Party
    items: List[InvoiceItem]


class InvoiceItemResponse(BaseModel):
    description: str
    quantity: float
    unit_price: float
    taxable_value: float
    gst_rate: int
    cgst: float
    sgst: float
    igst: float
    gst_amount: float
    total_amount: float


class InvoiceResponse(BaseModel):
    invoice_no: str
    invoice_date: date
    invoice_datetime: datetime
    seller: Party
    buyer: Party
    items: List[InvoiceItemResponse]
    taxable_total: float
    gst_total: float
    grand_total: float
