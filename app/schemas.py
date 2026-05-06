from enum import Enum
from pydantic import BaseModel, ConfigDict
from datetime import date, datetime
from typing import Optional

class InvoiceLineResponse(BaseModel):
    id: int
    product_id: Optional[int] = None
    sku: Optional[str] = None
    product_name: str
    hsn_sac_code: Optional[str] = None
    unit_of_measure: Optional[str] = None
    quantity: float
    unit_price: float
    tax_rate: float
    taxable_value: float
    tax_amount: float
    line_total: float

    model_config = ConfigDict(from_attributes=True)


class InvoiceTaxSummaryResponse(BaseModel):
    tax_component: str
    tax_rate: float
    taxable_value: float
    tax_amount: float

    model_config = ConfigDict(from_attributes=True)


class InvoiceResponse(BaseModel):
    id: int
    invoice_number: Optional[str] = None
    invoice_template_key: Optional[str] = None
    order_id: int
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_gstin: Optional[str] = None
    customer_place_of_supply: Optional[str] = None
    seller_state: Optional[str] = None
    subtotal: float
    tax: float
    total: float
    due_date: date
    status: str
    discount_type: Optional[str] = None
    discount_value: float
    created_at: datetime
    lines: list[InvoiceLineResponse] = []
    tax_summary: list[InvoiceTaxSummaryResponse] = []

    model_config = ConfigDict(from_attributes=True)


class InvoiceStatus(str, Enum):
    UNPAID = "UNPAID"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class InvoiceStatusUpdate(BaseModel):
    status: InvoiceStatus
