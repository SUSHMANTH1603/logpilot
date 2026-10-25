"""FastAPI dependency injection providers."""

from collections.abc import AsyncGenerator

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from logpilot_api.core.config import Settings, get_settings
from logpilot_api.db.session import get_db_session


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing database sessions."""
    async for session in get_db_session():
        yield session


def get_current_settings(settings: Settings = Depends(get_settings)) -> Settings:
    """Dependency for injecting settings."""
    return settings


def verify_bearer_token(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> str:
    """Validate user session bearer token (D06 § 3.1 & D11 § 7.1).

    Enforces canonical 401 Unauthorized for missing, malformed, invalid,
    or unrecognized tokens. A syntactically valid but arbitrary token is NOT
    treated as authenticated. Real user identity and ProjectMembership RBAC
    require the Identity module (D05 § 8.1 / § 8.3).
    """
    from logpilot_api.core.errors import UnauthorizedError

    if not authorization:
        raise UnauthorizedError("Authentication required. Missing 'Authorization' header.")
    parts = authorization.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise UnauthorizedError("Invalid authorization format. Expected 'Bearer <token>'.")

    # Real authentication requires validating cryptographic signatures, resolving
    # User identity, and checking ProjectMembership RBAC (D06 § 3.1, D11 § 7.1).
    # Since the Identity module is not yet implemented, arbitrary tokens cannot be authenticated.
    raise UnauthorizedError(
        "Invalid or unrecognized authentication token. User identity and session validation "
        "require the Identity module (D05 § 8.1 / § 8.3)."
    )
