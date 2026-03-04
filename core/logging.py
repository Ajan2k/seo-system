# core/logging.py
"""
Production-Grade Logging Configuration
Features:
  - Rotating file handler with size limits
  - JSON-structured log format for machine parsing
  - Human-readable console format with color
  - Named loggers per module (prevents "root" logger pollution)
  - Request/Response correlation IDs via context variables
"""
import logging
import logging.handlers
import os
import sys
import json
import traceback
from datetime import datetime, timezone
from contextvars import ContextVar
from pathlib import Path
from typing import Optional

from core.config import settings

# ── Context Variables for per-request correlation ────────────────────────────
_request_id_var: ContextVar[str] = ContextVar("request_id", default="")
_user_id_var: ContextVar[str] = ContextVar("user_id", default="")


def set_request_id(request_id: str) -> None:
    _request_id_var.set(request_id)


def get_request_id() -> str:
    return _request_id_var.get()


# ── Custom JSON Formatter ────────────────────────────────────────────────────

class JSONFormatter(logging.Formatter):
    """
    Emit logs as single-line JSON objects.
    Ideal for log aggregation tools (Datadog, ELK, CloudWatch).
    """

    LEVEL_MAP = {
        logging.DEBUG: "DEBUG",
        logging.INFO: "INFO",
        logging.WARNING: "WARNING",
        logging.ERROR: "ERROR",
        logging.CRITICAL: "CRITICAL",
    }

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        payload: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": self.LEVEL_MAP.get(record.levelno, "UNKNOWN"),
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "request_id": get_request_id() or None,
        }

        # Attach exception info when present
        if record.exc_info:
            payload["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # Merge any extra fields attached to the record
        for key, value in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
            ):
                if not key.startswith("_"):
                    payload[key] = value

        return json.dumps(payload, default=str, ensure_ascii=True)


# ── Human-Readable Console Formatter ─────────────────────────────────────────

class ColorConsoleFormatter(logging.Formatter):
    """
    Colorized console formatter for development readability.
    Falls back to plain-text when colors not supported.
    """

    GREY   = "\x1b[38;5;245m"
    CYAN   = "\x1b[36m"
    GREEN  = "\x1b[32m"
    YELLOW = "\x1b[33m"
    RED    = "\x1b[31m"
    BOLD_RED = "\x1b[1;31m"
    RESET  = "\x1b[0m"

    COLORS = {
        logging.DEBUG:    GREY,
        logging.INFO:     GREEN,
        logging.WARNING:  YELLOW,
        logging.ERROR:    RED,
        logging.CRITICAL: BOLD_RED,
    }

    _FMT = "%(asctime)s │ {color}%(levelname)-8s{reset} │ %(name)-30s │ %(message)s"

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        color = self.COLORS.get(record.levelno, self.RESET)
        fmt = self._FMT.format(color=color, reset=self.RESET)
        formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


# ── Setup Function ────────────────────────────────────────────────────────────

def setup_logging() -> None:
    """
    Configure root logger and all handlers.
    Call this ONCE at application startup (inside lifespan or main).
    """
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    # Remove any pre-existing handlers (avoids duplicates on reload)
    root_logger.handlers.clear()

    # -- Console handler -------------------------------------------------------
    # sys.stdout encoding is fixed to UTF-8 by app/main.py at startup via
    # reconfigure(); we just use a standard StreamHandler here.
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    console_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(console_handler)


    # ── Rotating file handler (all levels) ────────────────────────────────────
    app_log_path = log_dir / "app.log"
    file_handler = logging.handlers.RotatingFileHandler(
        filename=app_log_path,
        maxBytes=settings.LOG_MAX_FILE_SIZE_MB * 1024 * 1024,
        backupCount=settings.LOG_RETENTION_DAYS,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(file_handler)

    # ── Error-only file handler ───────────────────────────────────────────────
    error_log_path = log_dir / "errors.log"
    error_handler = logging.handlers.RotatingFileHandler(
        filename=error_log_path,
        maxBytes=settings.LOG_MAX_FILE_SIZE_MB * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(error_handler)

    # ── Suppress noisy third-party loggers ────────────────────────────────────
    for noisy in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    root_logger.info(
        "Logging initialized",
        extra={
            "log_dir": str(log_dir),
            "log_level": settings.LOG_LEVEL,
            "environment": settings.ENVIRONMENT,
        },
    )


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger.
    Usage:
        from core.logging import get_logger
        logger = get_logger(__name__)
        logger.info("Something happened", extra={"post_id": 42})
    """
    return logging.getLogger(name)
