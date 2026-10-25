"""FastAPI dependency injection providers."""

from collections.abc import AsyncGenerator

from fastapi import Depends
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
