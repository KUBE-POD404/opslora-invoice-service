from fastapi.testclient import TestClient

from app.main import app


def test_health_live_startup_and_ready_routes():
    client = TestClient(app)

    assert client.get("/api/v1/invoices/health").json() == {"status": "ok"}
    assert client.get("/api/v1/invoices/live").json() == {"status": "ok"}
    assert client.get("/api/v1/invoices/startup").json() == {"status": "ok"}

    ready_response = client.get("/api/v1/invoices/ready")
    assert ready_response.status_code == 200
    assert ready_response.json() == {
        "status": "ready",
        "checks": {"database": "ok"},
    }
