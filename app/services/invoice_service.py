from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
import logging

from app.models.invoice import Invoice, InvoiceLine, InvoiceTaxSummary
from app.exceptions.custom_exceptions import NotFoundException, ConflictException
from app.utils.service_client import authenticated_get
from app.core.celery_app import celery
from app.core.logging_config import request_id_ctx
from app.core.config import settings
from app.services.invoice_templates import DEFAULT_TEMPLATE_KEY, get_invoice_template

logger = logging.getLogger(__name__)

ORDER_SERVICE_URL = settings.order_service_url
AUTH_SERVICE_URL = settings.auth_service_url
API_VERSION = settings.api_version

# -----------------------------
# FETCH ORDER
# -----------------------------
def fetch_order(order_id: int, auth_header: str):

    url = f"{ORDER_SERVICE_URL}{API_VERSION}/orders/{order_id}"

    logger.info("Fetching order", extra={"order_id": order_id, "url": url})

    response = authenticated_get(url, auth_header)

    if response.status_code != 200:
        raise NotFoundException("Order not found")

    data = response.json()
    required_fields = ("status", "customer_email", "customer_name", "items")
    if any(data.get(field) in (None, "") for field in required_fields):
        raise ConflictException("Invalid order service response")

    if not isinstance(data["items"], list) or not data["items"]:
        raise ConflictException("Invalid order service response")

    for item in data["items"]:
        if item.get("product_name") in (None, ""):
            raise ConflictException("Invalid order service response")
        if item.get("quantity") is None or item.get("unit_price") is None:
            raise ConflictException("Invalid order service response")

    return data


def fetch_organization_settings(auth_header: str):
    url = f"{AUTH_SERVICE_URL}{API_VERSION}/settings/organization"
    logger.info("Fetching organization settings", extra={"url": url})
    response = authenticated_get(url, auth_header)

    if response.status_code != 200:
        raise ConflictException("Failed to fetch organization settings")

    data = response.json()
    return {
        "invoice_prefix": data.get("invoice_prefix") or "INV",
        "next_invoice_sequence": data.get("next_invoice_sequence") or 1,
        "default_due_days": data.get("default_due_days") or 30,
        "default_invoice_template": data.get("default_invoice_template") or DEFAULT_TEMPLATE_KEY,
        "seller_state": data.get("state"),
        "legal_name": data.get("legal_name"),
        "display_name": data.get("display_name"),
        "email": data.get("email"),
        "phone": data.get("phone"),
        "tax_id": data.get("tax_id"),
        "address": data.get("address"),
        "country": data.get("country"),
        "default_invoice_terms": data.get("default_invoice_terms"),
        "default_invoice_footer": data.get("default_invoice_footer"),
        "round_off_enabled": bool(data.get("round_off_enabled")),
    }


def _money(value) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.01"))


def _tax_rate(value) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.01"))


def _build_invoice_number(prefix: str, sequence: int, invoice_id: int) -> str:
    return f"{prefix}-{sequence:06d}-{invoice_id:06d}"


def _normalize_state(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().lower()


def _tax_components(seller_state: str | None, buyer_state: str | None, tax_rate: Decimal):
    if tax_rate == Decimal("0.00"):
        return [("NONE", Decimal("0.00"))]

    if _normalize_state(seller_state) and _normalize_state(seller_state) == _normalize_state(buyer_state):
        split_rate = (tax_rate / Decimal("2")).quantize(Decimal("0.01"))
        return [("CGST", split_rate), ("SGST", split_rate)]

    return [("IGST", tax_rate)]


def attach_invoice_details(db: Session, invoice: Invoice):
    invoice.lines = (
        db.query(InvoiceLine)
        .filter(InvoiceLine.invoice_id == invoice.id)
        .order_by(InvoiceLine.id.asc())
        .all()
    )
    invoice.tax_summary = (
        db.query(InvoiceTaxSummary)
        .filter(InvoiceTaxSummary.invoice_id == invoice.id)
        .order_by(InvoiceTaxSummary.tax_rate.asc())
        .all()
    )
    return invoice


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
    invoice_template_key: str | None = None,
):

    logger.info("Creating invoice", extra={"order_id": order_id})

    order_data = fetch_order(order_id, auth_header)
    org_settings = fetch_organization_settings(auth_header)
    selected_template = get_invoice_template(invoice_template_key or org_settings["default_invoice_template"])

    if order_data["status"] != "CONFIRMED":
        raise ConflictException("Invoice can be created only for CONFIRMED orders")

    existing = db.query(Invoice).filter(
        Invoice.order_id == order_id,
        Invoice.organization_id == organization_id
    ).first()

    if existing:
        raise ConflictException("Invoice already exists for this order")

    invoice_lines = []
    tax_groups: dict[tuple[str, Decimal], dict[str, Decimal]] = {}
    buyer_state = order_data.get("customer_place_of_supply") or order_data.get("billing_state")
    seller_state = org_settings["seller_state"]

    for item in order_data["items"]:
        quantity = _money(item["quantity"])
        unit_price = _money(item["unit_price"])
        tax_rate = _tax_rate(item.get("tax_rate"))
        taxable_value = (quantity * unit_price).quantize(Decimal("0.01"))
        tax_amount = (taxable_value * tax_rate / Decimal("100")).quantize(Decimal("0.01"))
        line_total = (taxable_value + tax_amount).quantize(Decimal("0.01"))

        invoice_lines.append(
            {
                "order_item_id": item.get("id"),
                "product_id": item.get("product_id"),
                "sku": item.get("sku"),
                "product_name": item["product_name"],
                "hsn_sac_code": item.get("hsn_sac_code"),
                "unit_of_measure": item.get("unit_of_measure"),
                "quantity": quantity,
                "unit_price": unit_price,
                "tax_rate": tax_rate,
                "taxable_value": taxable_value,
                "tax_amount": tax_amount,
                "line_total": line_total,
            }
        )
        for component, component_rate in _tax_components(seller_state, buyer_state, tax_rate):
            component_tax_amount = (taxable_value * component_rate / Decimal("100")).quantize(Decimal("0.01"))
            group = tax_groups.setdefault(
                (component, component_rate),
                {"taxable_value": Decimal("0.00"), "tax_amount": Decimal("0.00")},
            )
            group["taxable_value"] += taxable_value
            group["tax_amount"] += component_tax_amount

    subtotal = sum(line["taxable_value"] for line in invoice_lines).quantize(Decimal("0.01"))
    tax = sum(line["tax_amount"] for line in invoice_lines).quantize(Decimal("0.01"))

    discount_amount = Decimal("0.00")
    discount_value = _money(discount_value)

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
        invoice_template_key=selected_template.key,
        seller_legal_name=org_settings.get("legal_name"),
        seller_display_name=org_settings.get("display_name"),
        seller_email=org_settings.get("email"),
        seller_phone=org_settings.get("phone"),
        seller_tax_id=org_settings.get("tax_id"),
        seller_address=org_settings.get("address"),
        seller_country=org_settings.get("country"),
        seller_state=seller_state,
        invoice_terms=org_settings.get("default_invoice_terms"),
        invoice_footer=org_settings.get("default_invoice_footer"),
        round_off_enabled=org_settings.get("round_off_enabled", False),
        customer_id=order_data.get("customer_id"),
        customer_name=order_data.get("customer_name"),
        customer_email=order_data.get("customer_email"),
        customer_gstin=order_data.get("customer_gstin"),
        customer_place_of_supply=order_data.get("customer_place_of_supply"),
        billing_address_line1=order_data.get("billing_address_line1"),
        billing_address_line2=order_data.get("billing_address_line2"),
        billing_city=order_data.get("billing_city"),
        billing_state=order_data.get("billing_state"),
        billing_postal_code=order_data.get("billing_postal_code"),
        billing_country=order_data.get("billing_country"),
        subtotal=subtotal,
        tax=tax,
        total=total,
        discount_type=discount_type,
        discount_value=discount_value,
        status="UNPAID",
        due_date=(datetime.now(timezone.utc) + timedelta(days=org_settings["default_due_days"])).date(),
        created_by_user_id=created_by_user_id,
        created_at=datetime.now(timezone.utc),
    )

    db.add(invoice)
    db.flush()
    invoice.invoice_number = _build_invoice_number(
        org_settings["invoice_prefix"],
        org_settings["next_invoice_sequence"],
        invoice.id,
    )

    for line in invoice_lines:
        db.add(InvoiceLine(invoice_id=invoice.id, **line))

    for (component, rate), summary in tax_groups.items():
        db.add(
            InvoiceTaxSummary(
                invoice_id=invoice.id,
                tax_component=component,
                tax_rate=rate,
                taxable_value=summary["taxable_value"].quantize(Decimal("0.01")),
                tax_amount=summary["tax_amount"].quantize(Decimal("0.01")),
            )
        )

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

    return attach_invoice_details(db, invoice)



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

    return attach_invoice_details(db, invoice)


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

    return attach_invoice_details(db, invoice)


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

    return attach_invoice_details(db, invoice)

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

    return [attach_invoice_details(db, invoice) for invoice in query.order_by(Invoice.id.desc()).all()]
