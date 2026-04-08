from enum import Enum
from pydantic import BaseModel, ConfigDict
from datetime import date, datetime
from typing import Optional

class InvoiceResponse(BaseModel):
    id: int
    order_id: int
    subtotal: float
    tax: float
    total: float
    due_date: date
    status: str
    discount_type: Optional[str]
    discount_value: float
    created_at: datetime

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