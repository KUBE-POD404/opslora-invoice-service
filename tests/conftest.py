import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough")
os.environ.setdefault("RABBITMQ_URL", "memory://")
os.environ.setdefault("ORDER_SERVICE_URL", "http://order-service:3000")
os.environ.setdefault("API_VERSION", "/api/v1")

from app.database import Base  # noqa: E402
from app.models.invoice import Invoice, InvoiceLine, InvoiceTaxSummary  # noqa: F401,E402


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def no_op_celery(monkeypatch):
    class CeleryStub:
        def __init__(self):
            self.tasks = []

        def send_task(self, *args, **kwargs):
            self.tasks.append((args, kwargs))

    stub = CeleryStub()
    monkeypatch.setattr("app.services.invoice_service.celery", stub)
    return stub
