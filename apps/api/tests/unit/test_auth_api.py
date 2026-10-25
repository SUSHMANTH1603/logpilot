import uuid

import pytest
from httpx import AsyncClient

from logpilot_api.core.errors import ConflictError
from logpilot_api.db import session as db_session
from logpilot_api.modules.identity.repository import UserRepository
from logpilot_api.modules.identity.schemas import UserRegisterRequest
from logpilot_api.modules.identity.service import IdentityService


async def test_user_registration_happy_path_and_normalization(client: AsyncClient) -> None:
    """Validate registration creates user, normalizes email, and omits credentials in response."""
    payload = {
        "email": "  Ada.Lovelace@AnalyticalEngine.ORG  ",
        "password": "ValidPassword123!",
        "full_name": "  Ada Lovelace  ",
    }

    res = await client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201

    data = res.json()
    assert data["email"] == "ada.lovelace@analyticalengine.org"
    assert data["full_name"] == "Ada Lovelace"
    assert data["is_active"] is True
    assert "id" in data
    assert "password" not in data
    assert "password_hash" not in data

    # Verify database persistence
    sessionmaker = db_session.get_async_sessionmaker()
    async with sessionmaker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_email("ada.lovelace@analyticalengine.org")
        assert user is not None
        assert user.password_hash.startswith("$argon2id$")
        assert "ValidPassword123!" not in user.password_hash


async def test_user_registration_duplicate_email_conflict(client: AsyncClient) -> None:
    """Validate duplicate email returns canonical 409 Conflict with EMAIL_ALREADY_EXISTS."""
    payload = {
        "email": "duplicate@logpilot.io",
        "password": "ValidPassword123!",
        "full_name": "First User",
    }

    res1 = await client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    # Second registration with case variation
    payload2 = {
        "email": "  DUPLICATE@LOGPILOT.IO  ",
        "password": "DifferentPassword123!",
        "full_name": "Second User",
    }
    res2 = await client.post("/api/v1/auth/register", json=payload2)
    assert res2.status_code == 409
    err = res2.json()["error"]
    assert err["code"] == "EMAIL_ALREADY_EXISTS"
    assert "already exists" in err["message"]


async def test_user_registration_password_boundaries_and_validation(client: AsyncClient) -> None:
    """Validate password length constraints (8-128 chars) and email format."""
    # Too short (< 8 chars) -> 422
    res_short = await client.post(
        "/api/v1/auth/register",
        json={"email": "short@a.com", "password": "short", "full_name": "Name"},
    )
    assert res_short.status_code == 422

    # Too long (> 128 chars) -> 422
    res_long = await client.post(
        "/api/v1/auth/register",
        json={"email": "long@a.com", "password": "A" * 129, "full_name": "Name"},
    )
    assert res_long.status_code == 422

    # Malformed email -> 422
    res_bad_email = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "ValidPassword123!", "full_name": "Name"},
    )
    assert res_bad_email.status_code == 422


async def test_user_login_happy_path_and_token_exchange(client: AsyncClient) -> None:
    """Validate login returns bearer access token with 24h expiry and user profile."""
    # 1. Register
    reg_payload = {
        "email": "login.test@logpilot.io",
        "password": "CorrectHorseBatteryStaple123!",
        "full_name": "Test Operator",
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201

    # 2. Login with uppercase email (proves normalization on login)
    login_payload = {
        "email": "  LOGIN.TEST@LOGPILOT.IO  ",
        "password": "CorrectHorseBatteryStaple123!",
    }
    login_res = await client.post("/api/v1/auth/login", json=login_payload)
    assert login_res.status_code == 200

    token_data = login_res.json()
    assert token_data["token_type"] == "bearer"
    assert token_data["expires_in"] == 86400  # 24h default
    assert "access_token" in token_data
    assert token_data["user"]["email"] == "login.test@logpilot.io"

    # 3. Use access token on protected endpoint
    token = token_data["access_token"]
    proj_res = await client.post(
        "/api/v1/projects",
        json={"name": "Auth Test Project", "slug": f"auth-test-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert proj_res.status_code == 201


async def test_user_login_credential_failures_and_inactive_rejection(client: AsyncClient) -> None:
    """Validate wrong password, non-existent email, and deactivated accounts fail with 401."""
    # Register active user
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "active@logpilot.io",
            "password": "Password123!",
            "full_name": "Active User",
        },
    )

    # Wrong password -> 401
    res_wrong_pw = await client.post(
        "/api/v1/auth/login",
        json={"email": "active@logpilot.io", "password": "WrongPassword123!"},
    )
    assert res_wrong_pw.status_code == 401
    assert res_wrong_pw.json()["error"]["code"] == "UNAUTHORIZED"

    # Unknown email -> 401
    res_unknown = await client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@logpilot.io", "password": "Password123!"},
    )
    assert res_unknown.status_code == 401
    assert res_unknown.json()["error"]["code"] == "UNAUTHORIZED"

    # Deactivate user in database
    sessionmaker = db_session.get_async_sessionmaker()
    async with sessionmaker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_email("active@logpilot.io")
        assert user is not None
        user.is_active = False
        await session.commit()

    # Login with deactivated account -> 401
    res_inactive = await client.post(
        "/api/v1/auth/login",
        json={"email": "active@logpilot.io", "password": "Password123!"},
    )
    assert res_inactive.status_code == 401
    assert res_inactive.json()["error"]["code"] == "UNAUTHORIZED"
    assert "inactive" in res_inactive.json()["error"]["message"].lower()


async def test_user_registration_concurrent_integrity_error_mapped_to_409(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validate database-level email uniqueness collision maps to HTTP 409 EMAIL_ALREADY_EXISTS."""
    sessionmaker = db_session.get_async_sessionmaker()
    async with sessionmaker() as session:
        service = IdentityService(session)
        payload1 = UserRegisterRequest(
            email="collision@logpilot.io",
            password="Password123!",
            full_name="User 1",
        )
        await service.register_user(payload1)

        # Force bypass pre-check to simulate race condition where concurrent requests pass pre-check
        async def fake_get_by_email(_email: str):
            return None

        monkeypatch.setattr(service.repo, "get_by_email", fake_get_by_email)

        # Attempt registering same email should fail with ConflictError EMAIL_ALREADY_EXISTS
        with pytest.raises(ConflictError) as exc_info:
            await service.register_user(payload1)

        assert exc_info.value.code == "EMAIL_ALREADY_EXISTS"
        assert exc_info.value.status_code == 409
