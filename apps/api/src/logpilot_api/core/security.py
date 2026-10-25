"""Security primitives and hashing helpers.

Note: In accordance with Phase 1 scope and ADR-001/D11, full authentication
middleware and RBAC enforcement will be established with the Identity domain module.
This file provides foundational helpers without claiming premature auth implementation.
"""

import hmac
import secrets


def generate_request_id() -> str:
    """Generate a high-entropy URL-safe request ID for request tracing."""
    return f"req_{secrets.token_hex(10)}"


def secure_compare(a: str, b: str) -> bool:
    """Perform constant-time comparison to prevent timing attacks."""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def generate_source_key() -> str:
    """Generate high-entropy source key for telemetry emitters (D11 § 7.1)."""
    return f"lp_sk_{secrets.token_urlsafe(32)}"


def hash_source_key(key: str) -> str:
    """Compute cryptographic SHA-256 hash of a source key for safe storage (D11 § 7.1)."""
    import hashlib

    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def verify_source_key(raw_key: str, key_hash: str) -> bool:
    """Verify raw source key against stored cryptographic hash in constant time."""
    computed_hash = hash_source_key(raw_key)
    return secure_compare(computed_hash, key_hash)
