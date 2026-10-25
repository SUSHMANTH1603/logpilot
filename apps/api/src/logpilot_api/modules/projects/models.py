"""Project and ProjectMembership domain models conforming to D05 § 8.2 and § 8.3."""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from logpilot_api.db.base import Base


class Project(Base):
    """Project domain entity representing the primary multi-tenant isolation unit."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        sa.String(100),
        unique=True,
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
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
        back_populates="project",
        cascade="all, delete-orphan",
    )
    log_sources = relationship(
        "LogSource",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    log_events = relationship(
        "LogEvent",
        back_populates="project",
        cascade="all, delete-orphan",
        overlaps="log_events,log_source",
    )


class ProjectMembership(Base):
    """Project membership entity mapping users to projects with roles (D05 § 8.3)."""

    __tablename__ = "project_memberships"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "project_id", "user_id", name="uq_project_memberships_project_id_user_id"
        ),
        sa.CheckConstraint(
            "role IN ('OWNER', 'ENGINEER', 'VIEWER')",
            name="ck_project_memberships_role",
        ),
    )

    # Relationships
    project = relationship("Project", back_populates="memberships")
    user = relationship("User", back_populates="memberships")
