from celery import Celery
import os

RABBITMQ_URL = os.getenv(
    "RABBITMQ_URL",
    "amqp://guest:guest@rabbitmq:5672//"
)

celery = Celery(
    "invoice_service",
    broker=RABBITMQ_URL,
    backend="rpc://"
)

celery.conf.update(
    task_routes={
        "notification.send_invoice_created_email": {"queue": "notification_queue"},
        "notification.send_invoice_paid_email": {"queue": "notification_queue"},
        "notification.send_invoice_cancelled_email": {"queue": "notification_queue"},
        "notification.send_invoice_refunded_email": {"queue": "notification_queue"},
    },
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)