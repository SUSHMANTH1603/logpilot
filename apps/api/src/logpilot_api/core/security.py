"""Security primitives, Argon2id hashing, and JWT token management conforming to D06/D11."""

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from logpilot_api.core.config import get_settings
from logpilot_api.core.errors import UnauthorizedError

_password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


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
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def verify_source_key(raw_key: str, key_hash: str) -> bool:
    """Verify raw source key against stored cryptographic hash in constant time."""
    computed_hash = hash_source_key(raw_key)
    return secure_compare(computed_hash, key_hash)


def hash_password(password: str) -> str:
    """Hash plaintext password using Argon2id with RFC 9106 baseline parameters."""
    return _password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plaintext password against stored Argon2id hash using library verification API."""
    try:
        return _password_hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_access_token(
    user_id: uuid.UUID | str,
    email: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a cryptographically signed JWT bearer token using strict HS256."""
    settings = get_settings()
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.access_token_expire_minutes)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "iss": "logpilot-api",
        "aud": "logpilot",
    }

    if not settings.jwt_secret_key:
        raise ValueError("JWT_SECRET_KEY is not configured.")

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and strictly verify JWT bearer token against fixed HS256 allowlist."""
    settings = get_settings()
    if not settings.jwt_secret_key:
        raise UnauthorizedError("Authentication system key configuration is missing.")

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer="logpilot-api",
            audience="logpilot",
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iss": True,
                "verify_aud": True,
            },
        )
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Authentication token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("Invalid authentication token.") from exc

    if not payload.get("sub"):
        raise UnauthorizedError("Authentication token payload is missing subject identifier.")

    return payload
