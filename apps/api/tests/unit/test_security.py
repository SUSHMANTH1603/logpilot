"""Unit tests for cryptographic security primitives, Argon2id hashing, and JWT tokens."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from logpilot_api.core.config import Settings
from logpilot_api.core.errors import UnauthorizedError
from logpilot_api.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_argon2id_password_hashing_and_verification() -> None:
    """Validate Argon2id hashing conforms to RFC 9106 baseline and verifies correctly."""
    plain = "SuperSecretPassword123!"
    hashed = hash_password(plain)

    # 1. Verify standard Argon2id PHC prefix and parameters
    assert hashed.startswith("$argon2id$v=19$m=65536,t=3,p=4$")
    assert plain not in hashed

    # 2. Verify correct password matches
    assert verify_password(plain, hashed) is True

    # 3. Verify incorrect password fails
    assert verify_password("WrongPassword123!", hashed) is False

    # 4. Verify corrupted hash fails gracefully
    assert verify_password(plain, "corrupted_invalid_hash_string") is False


def test_jwt_token_minting_and_claims_verification() -> None:
    """Validate JWT token generation includes minimal required claims (D06 & D11)."""
    user_id = uuid.uuid4()
    email = "developer@logpilot.io"

    token = create_access_token(user_id=user_id, email=email)
    payload = decode_access_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["email"] == email
    assert payload["iss"] == "logpilot-api"
    assert payload["aud"] == "logpilot"
    assert isinstance(payload["iat"], int)
    assert isinstance(payload["exp"], int)
    assert payload["exp"] > payload["iat"]


def test_jwt_strict_algorithm_allowlist_enforcement() -> None:
    """Validate decoder rejects non-allowed algorithms (algorithm confusion defense)."""
    user_id = uuid.uuid4()
    # Craft token with "none" algorithm
    untrusted_token = jwt.encode(
        {"sub": str(user_id), "email": "a@b.com", "iss": "logpilot-api", "aud": "logpilot"},
        key="",
        algorithm="none",
    )

    with pytest.raises(UnauthorizedError, match="Invalid authentication token"):
        decode_access_token(untrusted_token)


def test_jwt_signature_verification_failure() -> None:
    """Validate decoder rejects tokens signed with a different key."""
    user_id = uuid.uuid4()
    forged_token = jwt.encode(
        {
            "sub": str(user_id),
            "email": "a@b.com",
            "iss": "logpilot-api",
            "aud": "logpilot",
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
            "iat": int(datetime.now(UTC).timestamp()),
        },
        key="wrong-secret-key-with-at-least-32-characters-for-test",
        algorithm="HS256",
    )

    with pytest.raises(UnauthorizedError, match="Invalid authentication token"):
        decode_access_token(forged_token)


def test_jwt_expired_token_failure() -> None:
    """Validate decoder rejects tokens whose expiration timestamp has passed."""
    user_id = uuid.uuid4()
    expired_token = create_access_token(
        user_id=user_id,
        email="dev@logpilot.io",
        expires_delta=timedelta(seconds=-10),  # expired 10s ago
    )

    with pytest.raises(UnauthorizedError, match="Authentication token has expired"):
        decode_access_token(expired_token)


def test_jwt_invalid_issuer_and_audience() -> None:
    """Validate decoder rejects tokens with mismatched issuer or audience."""
    dev_key = "dev-insecure-jwt-secret-key-change-in-production-min-32-chars"
    now = datetime.now(UTC)

    # Bad issuer
    bad_iss = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "email": "a@b.com",
            "iss": "evil-issuer",
            "aud": "logpilot",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        key=dev_key,
        algorithm="HS256",
    )
    with pytest.raises(UnauthorizedError, match="Invalid authentication token"):
        decode_access_token(bad_iss)

    # Bad audience
    bad_aud = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "email": "a@b.com",
            "iss": "logpilot-api",
            "aud": "wrong-service",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        key=dev_key,
        algorithm="HS256",
    )
    with pytest.raises(UnauthorizedError, match="Invalid authentication token"):
        decode_access_token(bad_aud)


def test_jwt_missing_subject_failure() -> None:
    """Validate decoder rejects tokens lacking 'sub' claim."""
    dev_key = "dev-insecure-jwt-secret-key-change-in-production-min-32-chars"
    now = datetime.now(UTC)

    missing_sub = jwt.encode(
        {
            "email": "a@b.com",
            "iss": "logpilot-api",
            "aud": "logpilot",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        key=dev_key,
        algorithm="HS256",
    )
    with pytest.raises(UnauthorizedError, match="missing subject"):
        decode_access_token(missing_sub)


def test_settings_jwt_key_isolation_and_production_validation() -> None:
    """Validate Settings enforces separate JWT_SECRET_KEY and rejects insecure configuration."""
    # 1. Dev environment assigns separate dev default and rejects reuse of secret_key
    dev_settings = Settings(app_env="development")
    assert dev_settings.jwt_secret_key is not None
    assert dev_settings.jwt_secret_key != dev_settings.secret_key

    # 2. Reject secret_key reuse
    with pytest.raises(ValueError, match="must not reuse or fall back"):
        Settings(
            app_env="development",
            secret_key="shared-secret-key-at-least-32-characters-long",
            jwt_secret_key="shared-secret-key-at-least-32-characters-long",
        )

    # 3. Production rejects missing jwt_secret_key
    with pytest.raises(ValueError, match="JWT_SECRET_KEY is mandatory"):
        Settings(
            app_env="production",
            secret_key="some-production-secret-key-min-32-chars",
            jwt_secret_key="",
        )

    # 4. Production rejects short jwt_secret_key (<32 chars)
    with pytest.raises(ValueError, match="at least 32 characters"):
        Settings(
            app_env="production",
            secret_key="some-production-secret-key-min-32-chars",
            jwt_secret_key="too-short-key",
        )

    # 5. Production accepts valid strong keys
    prod_settings = Settings(
        app_env="production",
        secret_key="production-app-secret-key-min-32-characters-long",
        jwt_secret_key="production-jwt-signing-key-min-32-characters-long",
    )
    assert prod_settings.jwt_secret_key == "production-jwt-signing-key-min-32-characters-long"
