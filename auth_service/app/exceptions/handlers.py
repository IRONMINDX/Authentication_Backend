"""Global exception handlers registered on the FastAPI app in main.py."""
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.constants import ErrorCode
from app.exceptions.custom import AppException

logger = logging.getLogger("app")


def _error_body(code: ErrorCode | str, message: str, details: object | None = None) -> dict:
    # `ErrorCode` is a `class X(str, Enum)`. `str(ErrorCode.X)` yields
    # "ErrorCode.X", not the plain value — use `.value` explicitly instead.
    code_str = code.value if isinstance(code, ErrorCode) else str(code)
    body = {"error": {"code": code_str, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return body


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.error_code, exc.message),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_error_body(
                ErrorCode.VALIDATION_ERROR,
                "Request validation failed.",
                details=exc.errors(),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(ErrorCode.INTERNAL_ERROR, str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(ErrorCode.INTERNAL_ERROR, "Internal server error."),
        )
