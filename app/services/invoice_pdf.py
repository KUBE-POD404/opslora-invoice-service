from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
import logging
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.core.config import settings
from app.models.invoice import Invoice
from app.utils.service_client import authenticated_get

logger = logging.getLogger(__name__)

MONEY_PREFIX = "Rs"
PAYMENT_LOOKUP_UNAVAILABLE = "Payment transactions unavailable"


def money(value: Any) -> str:
    amount = Decimal(str(value or "0")).quantize(Decimal("0.01"))
    return f"{MONEY_PREFIX} {amount}"


def date_label(value: datetime | date | str | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    return value.strftime("%d %b %Y")


def safe_text(value: Any, fallback: str = "-") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def fetch_invoice_payments(invoice_id: int, auth_header: str | None) -> list[dict[str, Any]]:
    base_url = settings.payment_service_url
    if not base_url or not auth_header:
        return []

    url = f"{base_url}{settings.api_version}/payments/invoice/{invoice_id}"
    response = authenticated_get(url, auth_header)
    if response.status_code != 200:
        logger.warning(
            "payment_lookup_failed_for_invoice_pdf",
            extra={"invoice_id": invoice_id, "status_code": response.status_code},
        )
        return []
    payload = response.json()
    return payload if isinstance(payload, list) else []


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "OpsloraInvoiceTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=26,
            leading=30,
            textColor=colors.HexColor("#141821"),
            spaceAfter=3 * mm,
        ),
        "label": ParagraphStyle(
            "OpsloraInvoiceLabel",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=9,
            textColor=colors.HexColor("#6f6a5d"),
            uppercase=True,
        ),
        "body": ParagraphStyle(
            "OpsloraInvoiceBody",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.2,
            leading=10.5,
            textColor=colors.HexColor("#141821"),
        ),
        "body_bold": ParagraphStyle(
            "OpsloraInvoiceBodyBold",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.4,
            leading=10.5,
            textColor=colors.HexColor("#141821"),
        ),
        "small": ParagraphStyle(
            "OpsloraInvoiceSmall",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7.2,
            leading=9,
            textColor=colors.HexColor("#6f6a5d"),
        ),
        "right": ParagraphStyle(
            "OpsloraInvoiceRight",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.2,
            leading=10.5,
            alignment=TA_RIGHT,
            textColor=colors.HexColor("#141821"),
        ),
    }


def _paragraph(style: ParagraphStyle, value: Any, fallback: str = "-") -> Paragraph:
    return Paragraph(safe_text(value, fallback).replace("\n", "<br/>"), style)


def _address_block(invoice: Invoice) -> str:
    parts = [
        invoice.customer_email,
        invoice.customer_gstin and f"GSTIN {invoice.customer_gstin}",
        invoice.billing_address_line1,
        invoice.billing_address_line2,
        invoice.billing_city,
        invoice.billing_state,
        invoice.billing_postal_code,
        invoice.billing_country,
        invoice.customer_place_of_supply and f"Place of supply: {invoice.customer_place_of_supply}",
    ]
    return "\n".join(str(part) for part in parts if part) or "-"


def _seller_block(invoice: Invoice) -> str:
    parts = [
        invoice.seller_legal_name,
        invoice.seller_tax_id and f"GSTIN {invoice.seller_tax_id}",
        invoice.seller_address,
        invoice.seller_state,
        invoice.seller_country,
        invoice.seller_email,
        invoice.seller_phone,
    ]
    return "\n".join(str(part) for part in parts if part) or "-"


def _invoice_header(invoice: Invoice, styles: dict[str, ParagraphStyle]) -> list[Any]:
    invoice_number = invoice.invoice_number or f"INV-{invoice.id}"
    seller_name = invoice.seller_display_name or invoice.seller_legal_name or "Opslora"
    meta_rows = [
        ["Invoice #", invoice_number],
        ["Order #", f"Order #{invoice.order_id}"],
        ["Status", safe_text(invoice.status)],
        ["Issued", date_label(invoice.created_at)],
        ["Due", date_label(invoice.due_date)],
    ]
    meta_table = Table(
        [[_paragraph(styles["small"], label), _paragraph(styles["right"], value)] for label, value in meta_rows],
        colWidths=[28 * mm, 42 * mm],
    )
    meta_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
    ]))
    return [
        Table(
            [[
                [_paragraph(styles["small"], "Opslora default template"), Paragraph("Invoice", styles["title"]), _paragraph(styles["body_bold"], seller_name)],
                meta_table,
            ]],
            colWidths=[105 * mm, 70 * mm],
        ),
        Spacer(1, 5 * mm),
    ]


def _party_section(invoice: Invoice, styles: dict[str, ParagraphStyle]) -> Table:
    rows = [
        [
            _paragraph(styles["label"], "From"),
            _paragraph(styles["label"], "Bill to"),
        ],
        [
            _paragraph(styles["body_bold"], invoice.seller_display_name or invoice.seller_legal_name or "Seller"),
            _paragraph(styles["body_bold"], invoice.customer_name or "Customer"),
        ],
        [
            _paragraph(styles["body"], _seller_block(invoice)),
            _paragraph(styles["body"], _address_block(invoice)),
        ],
    ]
    table = Table(rows, colWidths=[86 * mm, 86 * mm])
    table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#d8d2c3")),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d8d2c3")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eee7d7")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _line_items_table(invoice: Invoice, styles: dict[str, ParagraphStyle]) -> Table:
    rows: list[list[Any]] = [["Item", "HSN/SAC", "Qty", "Rate", "Taxable", "Tax", "Total"]]
    for line in invoice.lines:
        item_bits = [safe_text(line.product_name)]
        meta = " · ".join(part for part in [line.sku, line.unit_of_measure] if part)
        if meta:
            item_bits.append(f"<font color='#6f6a5d' size='7'>{meta}</font>")
        rows.append([
            Paragraph("<br/>".join(item_bits), styles["body_bold"]),
            safe_text(line.hsn_sac_code),
            safe_text(line.quantity),
            money(line.unit_price),
            money(line.taxable_value),
            f"{money(line.tax_amount)}\n{safe_text(line.tax_rate)}%",
            money(line.line_total),
        ])
    table = Table(rows, colWidths=[48 * mm, 20 * mm, 14 * mm, 23 * mm, 25 * mm, 22 * mm, 24 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eee7d7")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#6f6a5d")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.2),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#d8d2c3")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d8d2c3")),
        ("PADDING", (0, 0), (-1, -1), 4.4),
    ]))
    return table


def _tax_summary_table(invoice: Invoice) -> Table:
    rows = [["Component", "Rate", "Taxable", "Tax"]]
    for tax in invoice.tax_summary:
        rows.append([tax.tax_component, f"{tax.tax_rate}%", money(tax.taxable_value), money(tax.tax_amount)])
    if len(rows) == 1:
        rows.append(["No tax summary", "-", "-", "-"])
    table = Table(rows, colWidths=[28 * mm, 18 * mm, 30 * mm, 28 * mm])
    table.setStyle(_compact_table_style())
    return table


def _payment_table(payments: list[dict[str, Any]] | None) -> Table:
    rows = [["Date", "Method", "Reference", "Status", "Amount"]]
    if payments is None:
        rows.append([PAYMENT_LOOKUP_UNAVAILABLE, "-", "-", "-", "-"])
    elif not payments:
        rows.append(["No payments recorded", "-", "-", "-", "-"])
    else:
        for payment in payments:
            rows.append([
                date_label(payment.get("paid_at")),
                safe_text(payment.get("payment_method")).replace("_", " "),
                safe_text(payment.get("reference_number") or payment.get("gateway_provider")),
                safe_text(payment.get("status")),
                money(payment.get("amount")),
            ])
    table = Table(rows, colWidths=[26 * mm, 28 * mm, 46 * mm, 26 * mm, 28 * mm])
    table.setStyle(_compact_table_style())
    return table


def _compact_table_style() -> TableStyle:
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eee7d7")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.1),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.35, colors.HexColor("#d8d2c3")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d8d2c3")),
        ("PADDING", (0, 0), (-1, -1), 4),
    ])


def _totals_table(invoice: Invoice, payments: list[dict[str, Any]] | None) -> Table:
    paid = Decimal("0.00")
    if payments:
        paid = sum(Decimal(str(item.get("amount") or "0")) for item in payments if item.get("status") != "REFUNDED")
    balance = max(Decimal(str(invoice.total or "0")) - paid, Decimal("0.00"))
    rows = [
        ["Subtotal", money(invoice.subtotal)],
        ["Tax", money(invoice.tax)],
    ]
    if invoice.discount_type or invoice.discount_value:
        rows.append([f"Discount {safe_text(invoice.discount_type, '')}".strip(), f"-{money(invoice.discount_value)}"])
    rows.extend([
        ["Total", money(invoice.total)],
        ["Paid", money(paid)],
        ["Balance", money(balance)],
    ])
    table = Table(rows, colWidths=[34 * mm, 34 * mm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, 2), (-1, 2), 0.45, colors.HexColor("#d8d2c3")),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _footer_blocks(invoice: Invoice, styles: dict[str, ParagraphStyle]) -> KeepTogether:
    terms = invoice.invoice_terms or "Payment accepted by bank transfer, UPI, or card."
    footer = invoice.invoice_footer or "Thank you for your business."
    table = Table(
        [[
            [_paragraph(styles["label"], "Terms"), _paragraph(styles["body"], terms)],
            [_paragraph(styles["label"], "Footer"), _paragraph(styles["body"], footer)],
        ]],
        colWidths=[86 * mm, 86 * mm],
    )
    table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.35, colors.HexColor("#d8d2c3")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d8d2c3")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fffdf6")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    return KeepTogether([table])


def build_invoice_pdf(invoice: Invoice, payments: list[dict[str, Any]] | None) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=invoice.invoice_number or f"Invoice {invoice.id}",
    )
    styles = _styles()
    story: list[Any] = []
    story.extend(_invoice_header(invoice, styles))
    story.extend([
        _party_section(invoice, styles),
        Spacer(1, 5 * mm),
        _line_items_table(invoice, styles),
        Spacer(1, 5 * mm),
        Table(
            [[_tax_summary_table(invoice), _totals_table(invoice, payments)]],
            colWidths=[105 * mm, 69 * mm],
        ),
        Spacer(1, 5 * mm),
        _footer_blocks(invoice, styles),
        Spacer(1, 5 * mm),
        _paragraph(styles["label"], "Payment transactions"),
        _payment_table(payments),
    ])
    document.build(story)
    return buffer.getvalue()


def invoice_pdf_response_bytes(invoice: Invoice, auth_header: str | None) -> bytes:
    try:
        payments = fetch_invoice_payments(invoice.id, auth_header)
    except Exception:
        logger.exception("payment_lookup_unavailable_for_invoice_pdf", extra={"invoice_id": invoice.id})
        payments = None
    return build_invoice_pdf(invoice, payments)
