from sqlalchemy import Column, Integer, Numeric, Date, String, DateTime, CheckConstraint, ForeignKey
from datetime import datetime, timezone
from app.database import Base

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(Integer, nullable=False, index=True)

    # Plain reference, no FK
    order_id = Column(Integer, nullable=False, unique=True)
    invoice_number = Column(String(50), nullable=True)
    invoice_template_key = Column(String(100), nullable=True)
    seller_state = Column(String(100), nullable=True)

    customer_id = Column(Integer, nullable=True)
    customer_name = Column(String(255), nullable=True)
    customer_email = Column(String(255), nullable=True)
    customer_gstin = Column(String(20), nullable=True)
    customer_place_of_supply = Column(String(100), nullable=True)
    billing_address_line1 = Column(String(255), nullable=True)
    billing_address_line2 = Column(String(255), nullable=True)
    billing_city = Column(String(100), nullable=True)
    billing_state = Column(String(100), nullable=True)
    billing_postal_code = Column(String(30), nullable=True)
    billing_country = Column(String(100), nullable=True)

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


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    order_item_id = Column(Integer, nullable=True)
    product_id = Column(Integer, nullable=True)
    sku = Column(String(80), nullable=True)
    product_name = Column(String(150), nullable=False)
    hsn_sac_code = Column(String(20), nullable=True)
    unit_of_measure = Column(String(30), nullable=True)
    quantity = Column(Numeric(12, 2), nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)
    tax_rate = Column(Numeric(5, 2), nullable=False, default=0)
    taxable_value = Column(Numeric(12, 2), nullable=False)
    tax_amount = Column(Numeric(12, 2), nullable=False)
    line_total = Column(Numeric(12, 2), nullable=False)


class InvoiceTaxSummary(Base):
    __tablename__ = "invoice_tax_summaries"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    tax_component = Column(String(20), nullable=False, default="IGST")
    tax_rate = Column(Numeric(5, 2), nullable=False)
    taxable_value = Column(Numeric(12, 2), nullable=False)
    tax_amount = Column(Numeric(12, 2), nullable=False)
