import pytest

from app.exceptions.custom_exceptions import ConflictException, NotFoundException
from app.services import invoice_service


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def order_payload():
    return {
        "id": 101,
        "customer_id": 42,
        "customer_email": "buyer@example.com",
        "customer_name": "Acme Buyer",
        "status": "CONFIRMED",
        "total": 250.0,
        "items": [
            {"id": 1, "product_name": "Steel Bolt", "quantity": 2, "unit_price": 100.0},
            {"id": 2, "product_name": "Washer", "quantity": 1, "unit_price": 50.0},
        ],
    }


def test_order_contract_accepts_required_order_shape(monkeypatch):
    calls = []

    def fake_get(url, auth_header):
        calls.append((url, auth_header))
        return FakeResponse(200, order_payload())

    monkeypatch.setattr(invoice_service, "authenticated_get", fake_get)

    order = invoice_service.fetch_order(101, "Bearer token")

    assert order["status"] == "CONFIRMED"
    assert order["customer_email"] == "buyer@example.com"
    assert order["items"][0]["product_name"] == "Steel Bolt"
    assert calls == [
        ("http://order-service:3000/api/v1/orders/101", "Bearer token")
    ]


def test_order_contract_missing_order_returns_not_found(monkeypatch):
    monkeypatch.setattr(
        invoice_service,
        "authenticated_get",
        lambda *_args: FakeResponse(404, {"error": {"code": "NOT_FOUND"}}),
    )

    with pytest.raises(NotFoundException):
        invoice_service.fetch_order(101, "Bearer token")


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "CONFIRMED", "customer_email": "buyer@example.com", "items": []},
        {"status": "CONFIRMED", "customer_name": "Acme Buyer", "items": []},
        {
            "status": "CONFIRMED",
            "customer_email": "buyer@example.com",
            "customer_name": "Acme Buyer",
            "items": [{"product_name": "Steel Bolt", "quantity": 2}],
        },
    ],
)
def test_order_contract_rejects_incomplete_success_payload(monkeypatch, payload):
    monkeypatch.setattr(
        invoice_service,
        "authenticated_get",
        lambda *_args: FakeResponse(200, payload),
    )

    with pytest.raises(ConflictException):
        invoice_service.fetch_order(101, "Bearer token")
