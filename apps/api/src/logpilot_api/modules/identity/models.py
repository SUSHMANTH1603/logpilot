"""User identity model conforming to D05 § 8.1."""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from logpilot_api.db.base import Base


class User(Base):
    """User account entity representing an authenticated operator (D05 § 8.1)."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        sa.String(255),
        unique=True,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        default=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    memberships = relationship(
        "ProjectMembership",
        back_populates="user",
        cascade="all, delete-orphan",
    )
