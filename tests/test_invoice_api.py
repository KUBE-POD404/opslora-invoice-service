from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import get_current_user
from app.main import app
from app.models.invoice import Invoice  # noqa: F401
from app.models.invoice import InvoiceLine, InvoiceTaxSummary  # noqa: F401
from app.security.jwt import TokenPayload


def test_invoice_api_create_list_status_and_duplicate_rule(monkeypatch, no_op_celery):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_current_user():
        return TokenPayload(
            user_id=10,
            org_id=20,
            permissions=[
                "invoice.create",
                "invoice.read",
                "invoice.update",
                "invoice.cancel",
            ],
        )

    def fake_fetch_order(order_id, auth_header):
        return {
            "id": order_id,
            "status": "CONFIRMED",
            "customer_email": "buyer@example.com",
            "customer_name": "Acme Buyer",
            "customer_gstin": "29ABCDE1234F1Z5",
            "customer_place_of_supply": "Karnataka",
            "items": [
                {"id": 1, "product_name": "Steel Bolt", "quantity": 2, "unit_price": 100, "tax_rate": 18},
                {"id": 2, "product_name": "Washer", "quantity": 1, "unit_price": 50, "tax_rate": 5},
            ],
        }

    def fake_fetch_settings(auth_header):
        return {
            "invoice_prefix": "SMK",
            "next_invoice_sequence": 9,
            "default_due_days": 15,
            "default_invoice_template": "opslora_standard",
            "seller_state": "Karnataka",
        }

    monkeypatch.setattr("app.services.invoice_service.fetch_order", fake_fetch_order)
    monkeypatch.setattr("app.services.invoice_service.fetch_organization_settings", fake_fetch_settings)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        client = TestClient(app)

        create_response = client.post("/api/v1/invoices/orders/101")
        assert create_response.status_code == 201
        invoice = create_response.json()
        assert invoice["order_id"] == 101
        assert invoice["subtotal"] == 250.0
        assert invoice["tax"] == 38.5
        assert invoice["total"] == 288.5
        assert invoice["invoice_number"] == "SMK-000009-000001"
        assert invoice["invoice_template_key"] == "opslora_standard"
        assert invoice["customer_gstin"] == "29ABCDE1234F1Z5"
        assert len(invoice["lines"]) == 2
        assert len(invoice["tax_summary"]) == 4
        assert invoice["status"] == "UNPAID"
        assert len(no_op_celery.tasks) == 1

        list_response = client.get("/api/v1/invoices/")
        assert list_response.status_code == 200
        assert [item["id"] for item in list_response.json()] == [invoice["id"]]

        status_response = client.post(
            f"/api/v1/invoices/{invoice['id']}/status",
            json={"status": "PAID"},
        )
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "PAID"

        duplicate_response = client.post("/api/v1/invoices/orders/101")
        assert duplicate_response.status_code == 409
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
