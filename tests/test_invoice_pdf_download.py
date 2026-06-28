from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import get_current_user
from app.main import app
from app.models.invoice import Invoice  # noqa: F401
from app.models.invoice import InvoiceLine, InvoiceTaxSummary  # noqa: F401
from app.security.jwt import TokenPayload
from app.services import invoice_service


def _extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(BytesIO(content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


from io import BytesIO


def test_invoice_download_returns_compact_pdf_with_live_invoice_content(monkeypatch, no_op_celery):
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
            permissions=["invoice.create", "invoice.read"],
        )

    def fake_fetch_order(order_id, auth_header):
        return {
            "id": order_id,
            "status": "CONFIRMED",
            "customer_email": "buyer@example.com",
            "customer_name": "Acme Buyer",
            "customer_gstin": "29ABCDE1234F1Z5",
            "customer_place_of_supply": "Karnataka",
            "billing_address_line1": "22 Buyer Street",
            "billing_city": "Bengaluru",
            "billing_state": "Karnataka",
            "billing_postal_code": "560001",
            "billing_country": "India",
            "items": [
                {
                    "id": 1,
                    "sku": "RTX-4070",
                    "product_name": "RTX 4070 Super",
                    "hsn_sac_code": "868686",
                    "unit_of_measure": "PCS",
                    "quantity": 2,
                    "unit_price": 50000,
                    "tax_rate": 3,
                }
            ],
        }

    def fake_fetch_settings(auth_header):
        return {
            "invoice_prefix": "INV",
            "next_invoice_sequence": 1,
            "default_due_days": 30,
            "default_invoice_template": "opslora_default",
            "seller_state": "Karnataka",
            "legal_name": "UST Test Org Pvt Ltd",
            "display_name": "ust",
            "email": "billing@ust.example",
            "phone": "+91 90000 11111",
            "tax_id": "29SELLER1234F1Z1",
            "address": "99 Market Road, Bengaluru",
            "country": "India",
            "default_invoice_terms": "Payment due within 30 days.",
            "default_invoice_footer": "Thank you for choosing Opslora.",
            "round_off_enabled": False,
        }

    monkeypatch.setattr(invoice_service, "fetch_order", fake_fetch_order)
    monkeypatch.setattr(invoice_service, "fetch_organization_settings", fake_fetch_settings)
    monkeypatch.setattr(
        "app.services.invoice_pdf.fetch_invoice_payments",
        lambda invoice_id, auth_header: [
            {
                "id": 44,
                "invoice_id": invoice_id,
                "amount": 1000.0,
                "currency": "INR",
                "payment_method": "UPI",
                "payment_type": "MANUAL",
                "status": "SUCCEEDED",
                "reference_number": "UPI-REF-44",
                "paid_at": "2026-06-28T10:00:00Z",
                "note": "Advance",
            }
        ],
        raising=False,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        client = TestClient(app)
        create_response = client.post("/api/v1/invoices/orders/4")
        assert create_response.status_code == 201
        invoice = create_response.json()

        download_response = client.get(
            f"/api/v1/invoices/{invoice['id']}/download",
            headers={"Authorization": "Bearer test-token"},
        )

        assert download_response.status_code == 200
        assert download_response.headers["content-type"] == "application/pdf"
        assert "attachment" in download_response.headers["content-disposition"]
        assert "INV-000001-000001" in download_response.headers["content-disposition"]
        assert download_response.content.startswith(b"%PDF")

        reader = PdfReader(BytesIO(download_response.content))
        assert len(reader.pages) == 1
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        assert "INV-000001-000001" in text
        assert "Order #4" in text
        assert "Acme Buyer" in text
        assert "RTX 4070 Super" in text
        assert "Rs 103000.00" in text
        assert "UPI-REF-44" in text
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_invoice_download_still_returns_pdf_when_payment_lookup_fails(monkeypatch, no_op_celery):
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
            permissions=["invoice.create", "invoice.read"],
        )

    monkeypatch.setattr(invoice_service, "fetch_order", lambda order_id, auth_header: {
        "id": order_id,
        "status": "CONFIRMED",
        "customer_email": "buyer@example.com",
        "customer_name": "Acme Buyer",
        "items": [{"id": 1, "product_name": "Service Retainer", "quantity": 1, "unit_price": 1000, "tax_rate": 18}],
    })
    monkeypatch.setattr(invoice_service, "fetch_organization_settings", lambda auth_header: {
        "invoice_prefix": "INV",
        "next_invoice_sequence": 2,
        "default_due_days": 30,
        "default_invoice_template": "opslora_default",
        "seller_state": "Karnataka",
        "legal_name": "UST Test Org Pvt Ltd",
        "display_name": "ust",
        "round_off_enabled": False,
    })
    monkeypatch.setattr(
        "app.services.invoice_pdf.fetch_invoice_payments",
        lambda invoice_id, auth_header: (_ for _ in ()).throw(RuntimeError("payment service down")),
        raising=False,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        client = TestClient(app)
        invoice = client.post("/api/v1/invoices/orders/8").json()
        response = client.get(f"/api/v1/invoices/{invoice['id']}/download")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        text = _extract_pdf_text(response.content)
        assert "Payment transactions unavailable" in text
        assert "Service Retainer" in text
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
