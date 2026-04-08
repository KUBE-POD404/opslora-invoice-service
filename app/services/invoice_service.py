from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
import os
import logging

from app.models.invoice import Invoice
from app.exceptions.custom_exceptions import NotFoundException, ConflictException
from app.utils.service_client import authenticated_get
from app.core.celery_app import celery
from app.core.logging_config import request_id_ctx

logger = logging.getLogger(__name__)

ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL")
API_VERSION = os.getenv("API_VERSION", "/api/v1")

TAX_RATE = Decimal("0.18")


# -----------------------------
# FETCH ORDER
# -----------------------------
def fetch_order(order_id: int, auth_header: str):

    url = f"{ORDER_SERVICE_URL}{API_VERSION}/orders/{order_id}"

    logger.info("Fetching order", extra={"order_id": order_id, "url": url})

    response = authenticated_get(url, auth_header)

    if response.status_code != 200:
        raise NotFoundException("Order not found")

    return response.json()


# -----------------------------
# CREATE INVOICE
# -----------------------------
def create_invoice(
    db: Session,
    order_id: int,
    organization_id: int,
    created_by_user_id: int,
    auth_header: str,
    discount_type: str | None = None,
    discount_value: Decimal = Decimal("0.00"),
):

    logger.info("Creating invoice", extra={"order_id": order_id})

    order_data = fetch_order(order_id, auth_header)

    if order_data["status"] != "CONFIRMED":
        raise ConflictException("Invoice can be created only for CONFIRMED orders")

    existing = db.query(Invoice).filter(
        Invoice.order_id == order_id,
        Invoice.organization_id == organization_id
    ).first()

    if existing:
        raise ConflictException("Invoice already exists for this order")

    subtotal = sum(
        Decimal(item["quantity"]) * Decimal(item["unit_price"])
        for item in order_data["items"]
    ).quantize(Decimal("0.01"))

    tax = (subtotal * TAX_RATE).quantize(Decimal("0.01"))

    discount_amount = Decimal("0.00")

    if discount_type == "FLAT":
        discount_amount = discount_value
    elif discount_type == "PERCENT":
        discount_amount = (
            subtotal * discount_value / Decimal("100")
        ).quantize(Decimal("0.01"))

    if discount_amount > subtotal:
        raise ConflictException("Discount cannot exceed subtotal")

    total = (subtotal + tax - discount_amount).quantize(Decimal("0.01"))

    invoice = Invoice(
        organization_id=organization_id,
        order_id=order_id,
        subtotal=subtotal,
        tax=tax,
        total=total,
        discount_type=discount_type,
        discount_value=discount_value,
        status="UNPAID",
        due_date=(datetime.now(timezone.utc) + timedelta(days=30)).date(),
        created_by_user_id=created_by_user_id,
        created_at=datetime.now(timezone.utc),
    )

    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    request_id = request_id_ctx.get()

    celery.send_task(
        "notification.send_invoice_created_email",
        kwargs={
            "payload": {
                "invoice_id": invoice.id,
                "order_id": invoice.order_id,
                "email": order_data.get("customer_email"),
                "customer_name": order_data.get("customer_name"),
                "total": str(invoice.total),
                "status": invoice.status,
            },
            "request_id": request_id,
        },
        queue="notification_queue"
    )

    logger.info("Invoice created event published", extra={"invoice_id": invoice.id})

    return invoice



def get_invoice(db: Session, invoice_id: int, organization_id: int):

    invoice = (
        db.query(Invoice)
        .filter(
            Invoice.id == invoice_id,
            Invoice.organization_id == organization_id
        )
        .first()
    )

    if not invoice:
        raise NotFoundException("Invoice not found")

    return invoice


# -----------------------------
# CANCEL INVOICE
# -----------------------------
def cancel_invoice(db: Session, invoice_id: int, organization_id: int, auth_header: str):

    invoice = get_invoice(db, invoice_id, organization_id)

    if invoice.status != "UNPAID":
        raise ConflictException("Only unpaid invoices can be cancelled")

    order_data = fetch_order(invoice.order_id, auth_header)

    invoice.status = "CANCELLED"
    db.commit()
    db.refresh(invoice)

    celery.send_task(
        "notification.send_invoice_cancelled_email",
        kwargs={
            "payload": {
                "invoice_id": invoice.id,
                "order_id": invoice.order_id,
                "email": order_data.get("customer_email"),
                "customer_name": order_data.get("customer_name"),
            },
            "request_id": request_id_ctx.get(),
        },
        queue="notification_queue"
    )

    return invoice


# -----------------------------
# UPDATE STATUS
# -----------------------------
def update_invoice_status(
    db: Session,
    invoice_id: int,
    organization_id: int,
    status: str,
    auth_header: str
):

    invoice = get_invoice(db, invoice_id, organization_id)

    invoice.status = status
    db.commit()
    db.refresh(invoice)

    logger.info(
        "Invoice status updated",
        extra={"invoice_id": invoice.id, "status": status}
    )

    order_data = fetch_order(invoice.order_id, auth_header)

    payload = {
        "invoice_id": invoice.id,
        "order_id": invoice.order_id,
        "email": order_data.get("customer_email"),
        "customer_name": order_data.get("customer_name"),
        "total": str(invoice.total),
    }

    request_id = request_id_ctx.get()


    if status == "PAID":

        logger.info("Publishing INVOICE_PAID event", extra={"invoice_id": invoice.id})

        celery.send_task(
            "notification.send_invoice_paid_email",
            kwargs={
                "payload": payload,
                "request_id": request_id,
            },
            queue="notification_queue"
        )



    elif status == "REFUNDED":

        logger.info("Publishing INVOICE_REFUNDED event", extra={"invoice_id": invoice.id})

        celery.send_task(
            "notification.send_invoice_refunded_email",
            kwargs={
                "payload": payload,
                "request_id": request_id,
            },
            queue="notification_queue"
        )

    return invoice

# -----------------------------
# LIST INVOICES
# -----------------------------
def list_invoices(db: Session, organization_id, status=None, order_id=None):

    query = db.query(Invoice).filter(
        Invoice.organization_id == organization_id
    )

    if status:
        query = query.filter(Invoice.status == status)

    if order_id:
        query = query.filter(Invoice.order_id == order_id)

    return query.order_by(Invoice.id.desc()).all()