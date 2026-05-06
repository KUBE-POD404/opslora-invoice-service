from decimal import Decimal

import pytest

from app.exceptions.custom_exceptions import ConflictException, NotFoundException
from app.services import invoice_service


def confirmed_order():
    return {
        "id": 10,
        "status": "CONFIRMED",
        "customer_email": "buyer@example.com",
        "customer_name": "Buyer",
        "customer_id": 42,
        "customer_gstin": "29ABCDE1234F1Z5",
        "customer_place_of_supply": "Karnataka",
        "items": [
            {
                "id": 1,
                "product_id": 7,
                "sku": "SKU-A",
                "product_name": "Item A",
                "hsn_sac_code": "998311",
                "unit_of_measure": "PCS",
                "quantity": 2,
                "unit_price": 100.0,
                "tax_rate": 18.0,
            },
            {"id": 2, "product_name": "Item B", "quantity": 1, "unit_price": 50.0, "tax_rate": 5.0},
        ],
    }


def test_create_invoice_calculates_subtotal_tax_total(db_session, monkeypatch, no_op_celery):
    monkeypatch.setattr(invoice_service, "fetch_order", lambda order_id, auth_header: confirmed_order())

    invoice = invoice_service.create_invoice(
        db_session,
        order_id=10,
        organization_id=1,
        created_by_user_id=100,
        auth_header="Bearer token",
    )

    assert invoice.subtotal == Decimal("250.00")
    assert invoice.tax == Decimal("38.50")
    assert invoice.total == Decimal("288.50")
    assert invoice.invoice_number == "INV-1-000001"
    assert invoice.customer_gstin == "29ABCDE1234F1Z5"
    assert len(invoice.lines) == 2
    assert invoice.lines[0].sku == "SKU-A"
    assert len(invoice.tax_summary) == 2
    assert invoice.status == "UNPAID"
    assert no_op_celery.tasks[0][0][0] == "notification.send_invoice_created_email"


def test_invoice_requires_confirmed_order(db_session, monkeypatch, no_op_celery):
    order = confirmed_order()
    order["status"] = "CREATED"
    monkeypatch.setattr(invoice_service, "fetch_order", lambda order_id, auth_header: order)

    with pytest.raises(ConflictException):
        invoice_service.create_invoice(db_session, 10, 1, 100, "Bearer token")


def test_duplicate_invoice_for_order_is_rejected(db_session, monkeypatch, no_op_celery):
    monkeypatch.setattr(invoice_service, "fetch_order", lambda order_id, auth_header: confirmed_order())
    invoice_service.create_invoice(db_session, 10, 1, 100, "Bearer token")

    with pytest.raises(ConflictException):
        invoice_service.create_invoice(db_session, 10, 1, 100, "Bearer token")


def test_invoice_reads_are_tenant_scoped(db_session, monkeypatch, no_op_celery):
    monkeypatch.setattr(invoice_service, "fetch_order", lambda order_id, auth_header: confirmed_order())
    invoice = invoice_service.create_invoice(db_session, 10, 1, 100, "Bearer token")

    with pytest.raises(NotFoundException):
        invoice_service.get_invoice(db_session, invoice.id, organization_id=2)


def test_update_invoice_status_publishes_paid_event(db_session, monkeypatch, no_op_celery):
    monkeypatch.setattr(invoice_service, "fetch_order", lambda order_id, auth_header: confirmed_order())
    invoice = invoice_service.create_invoice(db_session, 10, 1, 100, "Bearer token")

    updated = invoice_service.update_invoice_status(db_session, invoice.id, 1, "PAID", "Bearer token")

    assert updated.status == "PAID"
    assert no_op_celery.tasks[-1][0][0] == "notification.send_invoice_paid_email"
