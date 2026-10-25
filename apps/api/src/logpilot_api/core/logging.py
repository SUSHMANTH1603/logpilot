"""Structured logging configuration and correlation tracking."""

import contextvars
import json
import logging
import sys
from typing import Any

correlation_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)

SENSITIVE_KEYS = {
    "password",
    "secret",
    "token",
    "authorization",
    "api_key",
    "access_token",
    "refresh_token",
    "private_key",
}


class JSONFormatter(logging.Formatter):
    """Custom JSON log formatter including timestamp, level, correlation ID, and sanitization."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Attach request correlation ID if present
        req_id = correlation_id_ctx.get()
        if req_id:
            log_obj["request_id"] = req_id

        # Attach extra metadata if passed
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            sanitized = {}
            for k, v in record.extra_data.items():
                if any(sens in k.lower() for sens in SENSITIVE_KEYS):
                    sanitized[k] = "[REDACTED]"
                else:
                    sanitized[k] = v
            log_obj["data"] = sanitized

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def configure_logging(log_level: str = "INFO") -> None:
    """Configure root logger with structured JSON formatting."""
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())

    # Remove existing handlers to avoid duplicates
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)

    # Silence overly noisy third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
