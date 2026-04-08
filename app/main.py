import os
from app.core.logging_config import setup_logging
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.routers.v1 import invoices
from app.core.middleware import RequestContextMiddleware

from app.exceptions.custom_exceptions import AppException
from app.exceptions.handlers import (
    app_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    generic_exception_handler
)

setup_logging()

if os.getenv("ENVIRONMENT") == "production":
    docs_url = None
    redoc_url = None
    openapi_url = None
else:
    docs_url = "/invoices/docs"
    redoc_url = "/invoices/redoc"
    openapi_url = "/invoices/openapi.json"

app = FastAPI(
    title="Invoice Service",
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url,
)

app.add_middleware(RequestContextMiddleware)


app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

app.include_router(invoices.router, prefix="/api/v1",)