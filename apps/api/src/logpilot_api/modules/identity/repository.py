"""Database access repository for User entities."""

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from logpilot_api.modules.identity.models import User


class UserRepository:
    """Async repository for querying and persisting User records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, email: str, password_hash: str, full_name: str) -> User:
        """Create and add a new user to the database session."""
        user = User(
            email=email,
            password_hash=password_hash,
            full_name=full_name,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Query user record by primary key UUID."""
        stmt = sa.select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Query user record by normalized email address."""
        stmt = sa.select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
