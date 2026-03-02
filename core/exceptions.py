# core/exceptions.py
"""
Centralized Custom Exceptions and global FastAPI exception handlers.
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.logging import get_logger

logger = get_logger("exceptions")


# ─── Domain Exceptions ────────────────────────────────────────────────────────

class AppBaseException(Exception):
    """Base exception for all application-level errors."""
    status_code: int = 500
    detail: str = "An internal server error occurred."

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.__class__.detail
        super().__init__(self.detail)


class ResourceNotFoundException(AppBaseException):
    status_code = 404
    detail = "The requested resource was not found."


class ValidationException(AppBaseException):
    status_code = 422
    detail = "Validation error."


class AIServiceException(AppBaseException):
    status_code = 503
    detail = "The AI generation service is temporarily unavailable."


class CMSPublishException(AppBaseException):
    status_code = 502
    detail = "Failed to publish to the CMS."


class DatabaseException(AppBaseException):
    status_code = 500
    detail = "A database error occurred."


class ConfigurationException(AppBaseException):
    status_code = 500
    detail = "Application configuration error."


# ─── FastAPI Exception Handlers ──────────────────────────────────────────────

def _error_response(status_code: int, detail: str, request_path: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": detail,
            "status_code": status_code,
            "path": request_path,
        },
    )


async def app_exception_handler(request: Request, exc: AppBaseException) -> JSONResponse:
    logger.error(
        "Application exception",
        extra={
            "exception_type": type(exc).__name__,
            "detail": exc.detail,
            "path": request.url.path,
        },
    )
    return _error_response(exc.status_code, exc.detail, request.url.path)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    logger.warning(
        "HTTP exception",
        extra={
            "status_code": exc.status_code,
            "detail": exc.detail,
            "path": request.url.path,
        },
    )
    return _error_response(exc.status_code, str(exc.detail), request.url.path)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    logger.warning(
        "Request validation error",
        extra={
            "errors": errors,
            "path": request.url.path,
        },
    )
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": "Request validation failed",
            "details": errors,
            "status_code": 422,
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "Unhandled exception",
        extra={"path": request.url.path},
    )
    return _error_response(500, "Internal server error", request.url.path)


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers with the FastAPI app."""
    app.add_exception_handler(AppBaseException, app_exception_handler)          # type: ignore
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)   # type: ignore
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore
    app.add_exception_handler(Exception, unhandled_exception_handler)          # type: ignore
