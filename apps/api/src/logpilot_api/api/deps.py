"""FastAPI dependency injection providers and authorization dependencies."""

import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from logpilot_api.core.config import Settings, get_settings
from logpilot_api.core.errors import ForbiddenError, NotFoundError, UnauthorizedError
from logpilot_api.core.security import decode_access_token
from logpilot_api.db.session import get_db_session
from logpilot_api.modules.identity.models import User
from logpilot_api.modules.identity.repository import UserRepository
from logpilot_api.modules.projects.models import ProjectMembership
from logpilot_api.modules.projects.repository import ProjectMembershipRepository


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing database sessions."""
    async for session in get_db_session():
        yield session


def get_current_settings(settings: Settings = Depends(get_settings)) -> Settings:
    """Dependency for injecting settings."""
    return settings


async def get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Resolve and authenticate caller identity from Bearer token (D06 § 3.1 & D11 § 7.1)."""
    if not authorization:
        raise UnauthorizedError(
            message="Authentication required. Missing 'Authorization' header.",
            code="UNAUTHORIZED",
        )

    parts = authorization.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise UnauthorizedError(
            message="Invalid authorization format. Expected 'Bearer <token>'.",
            code="UNAUTHORIZED",
        )

    token = parts[1].strip()
    payload = decode_access_token(token)

    try:
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, KeyError) as exc:
        raise UnauthorizedError(
            message="Invalid subject identifier in authentication token.",
            code="UNAUTHORIZED",
        ) from exc

    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_id)
    if not user or not user.is_active:
        raise UnauthorizedError(
            message="User account not found or inactive.",
            code="UNAUTHORIZED",
        )

    return user


async def verify_bearer_token(
    current_user: User = Depends(get_current_user),
) -> str:
    """Backward-compatible token verification returning authenticated user ID string."""
    return str(current_user.id)


def require_project_role(*allowed_roles: str):
    """Dependency factory enforcing project membership and role permissions (D06 § 3.2)."""

    async def _dependency(
        project_id: uuid.UUID,
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
    ) -> ProjectMembership:
        repo = ProjectMembershipRepository(session)
        membership = await repo.get_membership(project_id, current_user.id)
        if not membership:
            # Uniform 404 to prevent cross-tenant enumeration (D06 § 4.3 & D11 § 7.3)
            raise NotFoundError(
                message="The requested project was not found.",
                code="RESOURCE_NOT_FOUND",
            )

        if membership.role not in allowed_roles:
            raise ForbiddenError(
                message="You do not have permission to perform this action in this project.",
                code="FORBIDDEN",
            )

        return membership

    return _dependency


# Standard role-scoped dependencies conforming to D06 § 3.2
require_project_member = require_project_role("OWNER", "ENGINEER", "VIEWER")
require_project_engineer = require_project_role("OWNER", "ENGINEER")
require_project_owner = require_project_role("OWNER")
