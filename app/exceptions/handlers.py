import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.exceptions.custom_exception import AppException

logger = logging.getLogger(__name__)


def _error_response(status_code: int, error: str, details: object | None = None) -> JSONResponse:
    content = {"error": error}
    if details is not None:
        content["details"] = details
    return JSONResponse(status_code=status_code, content=content)


async def app_exception_handler(_request: Request, exc: AppException) -> JSONResponse:
    return _error_response(exc.status_code, exc.message, exc.details)


async def http_exception_handler(
    _request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    return _error_response(exc.status_code, str(exc.detail))


async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    return _error_response(422, "Validation error", exc.errors())


async def generic_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled application error", exc_info=exc)
    return _error_response(500, "Internal server error")