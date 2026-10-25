"""Unit tests for telemetry normalizer and secret scrubbing (D07 & D11)."""

import uuid
from datetime import UTC, datetime

from logpilot_api.modules.ingestion.normalizer import (
    compute_event_hash,
    normalize_severity,
    normalize_timestamp,
    redact_secrets,
    sanitize_attributes,
)


def test_normalize_severity_canonical_and_synonyms() -> None:
    """Verify canonical severity mapping taxonomy conforming to D07 § 5.1."""
    # Canonical levels
    assert normalize_severity("DEBUG", {})[0] == "DEBUG"
    assert normalize_severity("INFO", {})[0] == "INFO"
    assert normalize_severity("WARNING", {})[0] == "WARNING"
    assert normalize_severity("ERROR", {})[0] == "ERROR"
    assert normalize_severity("CRITICAL", {})[0] == "CRITICAL"

    # Synonyms and case-insensitivity
    assert normalize_severity("trace", {})[0] == "DEBUG"
    assert normalize_severity("verbose", {})[0] == "DEBUG"
    assert normalize_severity("warn", {})[0] == "WARNING"
    assert normalize_severity("alert", {})[0] == "WARNING"
    assert normalize_severity("err", {})[0] == "ERROR"
    assert normalize_severity("exception", {})[0] == "ERROR"
    assert normalize_severity("fatal", {})[0] == "CRITICAL"
    assert normalize_severity("panic", {})[0] == "CRITICAL"


def test_normalize_severity_syslog_numeric() -> None:
    """Verify RFC 5424 syslog numerical severity mapping (D07 § 5.1)."""
    assert normalize_severity("0", {})[0] == "CRITICAL"
    assert normalize_severity("1", {})[0] == "CRITICAL"
    assert normalize_severity("2", {})[0] == "ERROR"
    assert normalize_severity("3", {})[0] == "ERROR"
    assert normalize_severity("4", {})[0] == "WARNING"
    assert normalize_severity("5", {})[0] == "INFO"
    assert normalize_severity("6", {})[0] == "INFO"
    assert normalize_severity("7", {})[0] == "DEBUG"


def test_normalize_severity_unknown_fallback() -> None:
    """Verify unknown severity maps to INFO and preserves original level (D07 § 5.1)."""
    attrs: dict[str, str] = {}
    level, updated_attrs = normalize_severity("AUDIT_CUSTOM_EVENT", attrs)
    assert level == "INFO"
    assert updated_attrs["original_level"] == "AUDIT_CUSTOM_EVENT"


def test_normalize_timestamp_utc_and_naive() -> None:
    """Verify timestamp normalization and timezone-awareness rules (D07 § 5.2)."""
    # UTC datetime
    utc_dt = datetime(2026, 10, 25, 16, 0, 0, tzinfo=UTC)
    res_dt, attrs = normalize_timestamp(utc_dt, {})
    assert res_dt == utc_dt
    assert "_tz_assumed" not in attrs

    # Naive datetime
    naive_dt = datetime(2026, 10, 25, 16, 0, 0)
    res_naive, attrs_naive = normalize_timestamp(naive_dt, {})
    assert res_naive.tzinfo == UTC
    assert attrs_naive["_tz_assumed"] is True


def test_redact_secrets_in_flight() -> None:
    """Verify pre-ingress regex scrubbing of credentials (D07 § 10.2 / D11 § 10.2)."""
    # AWS Access Key
    msg1 = "Failed to upload to S3 using key AKIAIOSFODNN7EXAMPLE in bucket."
    assert "AKIAIOSFODNN7EXAMPLE" not in redact_secrets(msg1)
    assert "[REDACTED_SECRET:AWS_KEY]" in redact_secrets(msg1)

    # Database URI
    msg2 = "Connection failed to postgresql://postgres:mypassword123@db.prod.internal:5432/core"
    assert "mypassword123" not in redact_secrets(msg2)
    assert "[REDACTED_SECRET:DB_URI]" in redact_secrets(msg2)

    # Bearer Token
    msg3 = "Authorization header: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.t-IDcnhZrQq9WgOT"
    redacted = redact_secrets(msg3)
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in redacted
    assert "[REDACTED_SECRET:BEARER_TOKEN]" in redacted or "[REDACTED_SECRET:JWT]" in redacted

    # Private Key block
    msg4 = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0\n-----END RSA PRIVATE KEY-----"
    assert "MIIEowIBAAKCAQEA0" not in redact_secrets(msg4)
    assert "[REDACTED_SECRET:PRIVATE_KEY]" in redact_secrets(msg4)


def test_sanitize_attributes() -> None:
    """Verify recursive secret scrubbing in structured attributes dictionary."""
    attrs = {
        "service": "billing",
        "connection": "postgres://user:secretpass@host:5432/db",
        "meta": {
            "key": "AKIA1111222233334444",
        },
        "tags": ["env:prod", "token:Bearer supersecretvalue1234567890"],
    }
    sanitized = sanitize_attributes(attrs)
    assert "secretpass" not in str(sanitized)
    assert "AKIA1111222233334444" not in str(sanitized)
    assert "supersecretvalue1234567890" not in str(sanitized)


def test_compute_event_hash_deterministic() -> None:
    """Verify event hash is deterministic and strips message whitespace (D07 § 9.3)."""
    pid = uuid.uuid4()
    src_id = uuid.uuid4()
    ts = datetime(2026, 10, 25, 16, 4, 12, 102000, tzinfo=UTC)
    msg = "  Connection dropped after 3000ms  "

    h1 = compute_event_hash(pid, src_id, ts, msg)
    h2 = compute_event_hash(pid, src_id, ts, "Connection dropped after 3000ms")
    assert h1 == h2
    assert len(h1) == 64
