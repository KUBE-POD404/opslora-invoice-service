from sqlalchemy import Column, Integer, Numeric, Date, String, DateTime, CheckConstraint
from datetime import datetime, timezone
from app.database import Base

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(Integer, nullable=False, index=True)

    # Plain reference, no FK
    order_id = Column(Integer, nullable=False, unique=True)

    subtotal = Column(Numeric(10, 2), nullable=False)
    tax = Column(Numeric(10, 2), nullable=False)
    total = Column(Numeric(10, 2), nullable=False)

    discount_type = Column(String(10), nullable=True)
    discount_value = Column(Numeric(10, 2), default=0)

    due_date = Column(Date, nullable=False)

    status = Column(String(20), nullable=False, default="UNPAID")
    created_by_user_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint(
            "status IN ('UNPAID','PARTIALLY_PAID','PAID','OVERDUE','CANCELLED','REFUNDED')",
            name="check_invoice_status"
        ),
        CheckConstraint(
            "discount_type IN ('FLAT','PERCENT')",
            name="check_discount_type"
        ),
    )