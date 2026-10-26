"""Anomaly detection domain models conforming to D05 § 8.10 and D08 § 4.3."""

import enum
import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from logpilot_api.db.base import Base


class AnomalyType(enum.StrEnum):
    """Approved union taxonomy of anomaly types conforming to D05 § 8.10 and D08 § 4.3."""

    ERROR_RATE_SPIKE = "ERROR_RATE_SPIKE"
    FREQUENCY_SPIKE = "FREQUENCY_SPIKE"
    NEW_LOG_TEMPLATE = "NEW_LOG_TEMPLATE"
    NEW_TEMPLATE_ERROR = "NEW_TEMPLATE_ERROR"
    VOLUME_DROP = "VOLUME_DROP"
    BURST_DEVIATION = "BURST_DEVIATION"
    SEQUENCE_DEVIATION = "SEQUENCE_DEVIATION"


APPROVED_ANOMALY_TYPES = tuple(t.value for t in AnomalyType)


class AnomalySignal(Base):
    """AnomalySignal entity representing mathematical and statistical detections in PostgreSQL."""

    __tablename__ = "anomaly_signals"

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
    anomaly_type: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
    )
    confidence_score: Mapped[float] = mapped_column(
        sa.Float,
        nullable=False,
    )
    window_start: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
    )
    window_end: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
    )
    feature_vector: Mapped[dict[str, Any] | None] = mapped_column(
        sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=True,
    )
    detected_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["log_source_id", "project_id"],
            ["log_sources.id", "log_sources.project_id"],
            name="fk_anomaly_signals_source_project",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "confidence_score >= 0.0 AND confidence_score <= 1.0",
            name="ck_anomaly_signals_confidence",
        ),
        sa.CheckConstraint(
            f"anomaly_type IN {APPROVED_ANOMALY_TYPES}",
            name="ck_anomaly_signals_type",
        ),
        sa.Index(
            "ix_anomaly_signals_project_detected_at",
            "project_id",
            "detected_at",
        ),
        sa.Index(
            "ix_anomaly_signals_source_window",
            "log_source_id",
            "window_start",
            "window_end",
        ),
    )

    # Relationships
    project = relationship("Project", foreign_keys=[project_id])
    log_source = relationship(
        "LogSource",
        foreign_keys=[log_source_id, project_id],
        overlaps="project",
    )
