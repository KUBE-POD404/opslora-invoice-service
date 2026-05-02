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
        "items": [
            {"product_name": "Item A", "quantity": 2, "unit_price": 100.0},
            {"product_name": "Item B", "quantity": 1, "unit_price": 50.0},
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
    assert invoice.tax == Decimal("45.00")
    assert invoice.total == Decimal("295.00")
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
