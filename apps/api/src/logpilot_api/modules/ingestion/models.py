"""Ingestion domain models conforming to D05 § 8.6, § 8.7, § 8.8, § 8.9 and D07."""

import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from logpilot_api.db.base import Base


class LogSource(Base):
    """LogSource entity representing an external telemetry emitter under a project."""

    __tablename__ = "log_sources"

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
    name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
    )
    environment: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        default="production",
    )
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
    )
    ingestion_key_hash: Mapped[str | None] = mapped_column(
        sa.String(255),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "project_id",
            "name",
            "environment",
            name="uq_log_sources_project_name_env",
        ),
        sa.UniqueConstraint(
            "id",
            "project_id",
            name="uq_log_sources_id_project_id",
        ),
    )

    # Relationships
    project = relationship("Project", back_populates="log_sources")
    ingestion_runs = relationship(
        "IngestionRun",
        back_populates="log_source",
        cascade="all, delete-orphan",
    )
    log_events = relationship(
        "LogEvent",
        back_populates="log_source",
        cascade="all, delete-orphan",
    )


class IngestionRun(Base):
    """IngestionRun entity recording discrete ingestion batches and status metrics."""

    __tablename__ = "ingestion_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    log_source_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("log_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        default="STARTED",
    )
    events_processed: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=0,
    )
    errors_count: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=0,
    )
    started_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        sa.CheckConstraint("events_processed >= 0", name="ck_ingestion_runs_events_processed"),
        sa.CheckConstraint("errors_count >= 0", name="ck_ingestion_runs_errors_count"),
    )

    # Relationships
    log_source = relationship("LogSource", back_populates="ingestion_runs")


class LogTemplate(Base):
    """LogTemplate entity representing mined structural log patterns."""

    __tablename__ = "log_templates"

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
    template_hash: Mapped[str] = mapped_column(
        sa.String(64),
        nullable=False,
    )
    pattern_raw: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
    )
    occurrence_count: Mapped[int] = mapped_column(
        sa.BigInteger,
        nullable=False,
        default=1,
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "project_id",
            "template_hash",
            name="uq_log_templates_project_hash",
        ),
        sa.UniqueConstraint(
            "id",
            "project_id",
            name="uq_log_templates_id_project_id",
        ),
    )


class LogEvent(Base):
    """Normalized LogEvent entity representing an authoritative telemetry record in PostgreSQL."""

    __tablename__ = "log_events"

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
    log_source_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=False,
        index=True,
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=True,
        index=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    level: Mapped[str] = mapped_column(
        sa.String(20),
        nullable=False,
    )
    message_raw: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
    )
    attributes: Mapped[dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )
    event_hash: Mapped[str] = mapped_column(
        sa.String(64),
        nullable=False,
        index=True,
    )
    ingested_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["log_source_id", "project_id"],
            ["log_sources.id", "log_sources.project_id"],
            name="fk_log_events_source_project",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["template_id", "project_id"],
            ["log_templates.id", "log_templates.project_id"],
            name="fk_log_events_template_project",
        ),
        sa.UniqueConstraint(
            "project_id",
            "log_source_id",
            "event_hash",
            "timestamp",
            name="uq_log_events_dedup",
        ),
        sa.Index(
            "ix_log_events_project_timestamp",
            "project_id",
            "timestamp",
        ),
        sa.Index(
            "ix_log_events_source_timestamp",
            "log_source_id",
            "timestamp",
        ),
    )

    # Relationships
    project = relationship("Project", back_populates="log_events", overlaps="log_events")
    log_source = relationship(
        "LogSource",
        back_populates="log_events",
        foreign_keys=[log_source_id, project_id],
        overlaps="project",
    )
