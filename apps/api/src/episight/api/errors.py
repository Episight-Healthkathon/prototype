"""Error envelope — API Contract v1 §2. Every error response has the shape `ApiError`."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from episight.contracts.api import ApiError, ApiErrorBody
from episight.contracts.enums import ErrorCode
from episight.log import request_id_var

log = logging.getLogger(__name__)


class ApiException(Exception):
    def __init__(self, status_code: int, code: ErrorCode, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def not_found(code: ErrorCode, message: str, **details: Any) -> ApiException:
    return ApiException(404, code, message, details or None)


def error_response(
    status_code: int, code: ErrorCode, message: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    body = ApiError(
        error=ApiErrorBody(code=code, message=message, details=details, request_id=request_id_var.get() or "")
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json", exclude_none=True))


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiException)
    async def _api_exception(_: Request, exc: ApiException) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
        return error_response(422, ErrorCode.VALIDATION_ERROR, "Request validation failed", {"errors": errors})

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Unknown routes / methods. The contract has no route-level code, so 4xx maps to
        # VALIDATION_ERROR and keeps the envelope shape.
        code = ErrorCode.INTERNAL_ERROR if exc.status_code >= 500 else ErrorCode.VALIDATION_ERROR
        return error_response(exc.status_code, code, str(exc.detail))

    @app.exception_handler(OperationalError)
    async def _db_down(_: Request, exc: OperationalError) -> JSONResponse:
        log.error("database unavailable", extra={"fields": {"error": str(exc.orig)}})
        return error_response(503, ErrorCode.SERVICE_UNAVAILABLE, "Database unavailable")
