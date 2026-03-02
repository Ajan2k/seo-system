# core/middleware.py
"""
Custom FastAPI middleware stack.
  - RequestID middleware      (injects X-Request-ID header)
  - RequestLogging middleware (structured request/response logs)
  - ProcessTime middleware    (adds X-Process-Time header)
"""
import time
import uuid
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from core.logging import set_request_id, get_logger

logger = get_logger("middleware")


# ─── Request ID ──────────────────────────────────────────────────────────────

class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Adds a unique X-Request-ID header to every request & response.
    Also sets the context variable so all log lines for this request
    carry the same correlation ID.
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        set_request_id(request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ─── Timing ──────────────────────────────────────────────────────────────────

class ProcessTimeMiddleware(BaseHTTPMiddleware):
    """
    Measures end-to-end wall-clock time per request and adds
    X-Process-Time (ms) to the response headers.
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Process-Time"] = f"{elapsed_ms}ms"
        return response


# ─── Request / Response Logging ──────────────────────────────────────────────

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs every inbound request and its outcome.
    Skips /health and /static/* to avoid log spam.
    """

    SKIP_PATHS = {"/health", "/favicon.ico"}
    SKIP_PREFIXES = ("/static/",)

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        path = request.url.path

        # ── Skip health / static ──────────────────────────────────────────────
        if path in self.SKIP_PATHS or any(path.startswith(p) for p in self.SKIP_PREFIXES):
            return await call_next(request)

        start = time.perf_counter()
        logger.info(
            "HTTP request started",
            extra={
                "http_method": request.method,
                "http_path": path,
                "http_query": str(request.url.query),
                "client_host": request.client.host if request.client else "unknown",
            },
        )

        try:
            response = await call_next(request)
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.exception(
                "HTTP request failed with unhandled exception",
                extra={
                    "http_method": request.method,
                    "http_path": path,
                    "elapsed_ms": elapsed_ms,
                },
            )
            raise

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        level = logging.WARNING if response.status_code >= 400 else logging.INFO
        logger.log(
            level,
            "HTTP request completed",
            extra={
                "http_method": request.method,
                "http_path": path,
                "http_status": response.status_code,
                "elapsed_ms": elapsed_ms,
            },
        )

        return response
