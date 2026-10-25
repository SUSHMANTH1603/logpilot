"""Log normalization, severity mapping, secret redaction, and event hashing (D07 & D11)."""

import hashlib
import re
import uuid
from datetime import UTC, datetime
from typing import Any

# Canonical severity mapping taxonomy (D07 § 5.1)
SEVERITY_MAP: dict[str, str] = {
    # DEBUG
    "TRACE": "DEBUG",
    "VERBOSE": "DEBUG",
    "FINE": "DEBUG",
    "FINER": "DEBUG",
    "FINEST": "DEBUG",
    "DEBUG": "DEBUG",
    # INFO
    "INFO": "INFO",
    "NOTICE": "INFO",
    "STATUS": "INFO",
    "INFORMATIONAL": "INFO",
    "LOG": "INFO",
    # WARNING
    "WARN": "WARNING",
    "WARNING": "WARNING",
    "ALERT": "WARNING",
    "CAUTION": "WARNING",
    # ERROR
    "ERR": "ERROR",
    "ERROR": "ERROR",
    "EXCEPTION": "ERROR",
    "SEVERE": "ERROR",
    "FAIL": "ERROR",
    "FAILURE": "ERROR",
    # CRITICAL
    "FATAL": "CRITICAL",
    "CRIT": "CRITICAL",
    "CRITICAL": "CRITICAL",
    "EMERGENCY": "CRITICAL",
    "PANIC": "CRITICAL",
    "CAT": "CRITICAL",
}

# Pre-compiled secret redaction regex patterns (D07 § 10.2 / D11 § 10.2)
SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"-----BEGIN[ A-Z0-9_-]*PRIVATE KEY-----"
            r"[\s\S]*?-----END[ A-Z0-9_-]*PRIVATE KEY-----"
        ),
        "[REDACTED_SECRET:PRIVATE_KEY]",
    ),
    (
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "[REDACTED_SECRET:AWS_KEY]",
    ),
    (
        re.compile(r"\bBearer\s+[A-Za-z0-9-._~+/]+=*\b", re.IGNORECASE),
        "[REDACTED_SECRET:BEARER_TOKEN]",
    ),
    (
        re.compile(r"\b[a-zA-Z]+://[^:\s]+:[^@\s]+@[^/\s]+/[^\s]*\b"),
        "[REDACTED_SECRET:DB_URI]",
    ),
    (
        re.compile(r"\bey[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+(?:\.[A-Za-z0-9-_.+/=]*)?\b"),
        "[REDACTED_SECRET:JWT]",
    ),
]


def redact_secrets(text: str) -> str:
    """Scrub recognized credentials and sensitive tokens from text in-flight."""
    sanitized = text
    for pattern, replacement in SECRET_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def sanitize_attributes(attrs: dict[str, Any]) -> dict[str, Any]:
    """Recursively scrub secrets from attribute values."""
    sanitized: dict[str, Any] = {}
    for key, value in attrs.items():
        if isinstance(value, str):
            sanitized[key] = redact_secrets(value)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_attributes(value)
        elif isinstance(value, list):
            sanitized[key] = [redact_secrets(v) if isinstance(v, str) else v for v in value]
        else:
            sanitized[key] = value
    return sanitized


def normalize_severity(raw_level: str, attributes: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Normalize heterogeneous source severity string into canonical 5-level taxonomy."""
    trimmed = raw_level.strip()
    upper = trimmed.upper()

    # Numeric syslog check
    if trimmed.isdigit():
        code = int(trimmed)
        if code in (0, 1):
            return "CRITICAL", attributes
        elif code in (2, 3):
            return "ERROR", attributes
        elif code == 4:
            return "WARNING", attributes
        elif code in (5, 6):
            return "INFO", attributes
        elif code == 7:
            return "DEBUG", attributes

    if upper in SEVERITY_MAP:
        return SEVERITY_MAP[upper], attributes

    # Fallback to INFO and preserve original in attributes (D07 § 5.1)
    attributes["original_level"] = trimmed
    return "INFO", attributes


def normalize_timestamp(
    dt: datetime, attributes: dict[str, Any]
) -> tuple[datetime, dict[str, Any]]:
    """Normalize datetime to UTC timezone-aware datetime."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
        attributes["_tz_assumed"] = True
    else:
        dt = dt.astimezone(UTC)
    return dt, attributes


def compute_event_hash(
    project_id: uuid.UUID,
    log_source_id: uuid.UUID,
    timestamp: datetime,
    message_raw: str,
) -> str:
    """Compute deterministic SHA-256 event hash for idempotency deduplication (D07 § 9.3)."""
    # Standardize timestamp to ISO 8601 UTC microsecond representation
    ts_str = timestamp.isoformat()
    raw = f"{project_id}:{log_source_id}:{ts_str}:{message_raw.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
