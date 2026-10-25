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
