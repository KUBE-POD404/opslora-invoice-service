from dataclasses import dataclass

from app.exceptions.custom_exceptions import ConflictException


DEFAULT_TEMPLATE_KEY = "opslora_default"


@dataclass(frozen=True)
class InvoiceTemplate:
    key: str
    name: str
    description: str
    version: str
    supports_logo: bool = True
    supports_tax_summary: bool = True
    supports_bank_details: bool = False


TEMPLATES: tuple[InvoiceTemplate, ...] = (
    InvoiceTemplate(
        key=DEFAULT_TEMPLATE_KEY,
        name="Opslora Default",
        description="Balanced GST-ready invoice for inventory-backed orders.",
        version="2026.06.01",
        supports_bank_details=True,
    ),
    InvoiceTemplate(
        key="opslora_compact",
        name="Opslora Compact",
        description="Dense layout for invoices with many line items.",
        version="2026.06.01",
    ),
    InvoiceTemplate(
        key="opslora_tax_detailed",
        name="Tax Detailed",
        description="Highlights HSN/SAC, taxable value, and tax component summaries.",
        version="2026.06.01",
        supports_bank_details=True,
    ),
    InvoiceTemplate(
        key="opslora_service",
        name="Service Invoice",
        description="Cleaner service-oriented layout with lighter inventory detail.",
        version="2026.06.01",
        supports_tax_summary=False,
    ),
)


def list_invoice_templates() -> list[InvoiceTemplate]:
    return list(TEMPLATES)


def get_invoice_template(key: str | None) -> InvoiceTemplate:
    normalized_key = (key or DEFAULT_TEMPLATE_KEY).strip() or DEFAULT_TEMPLATE_KEY

    for template in TEMPLATES:
        if template.key == normalized_key:
            return template

    raise ConflictException("Invalid invoice template")
