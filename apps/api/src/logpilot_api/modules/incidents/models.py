"""Incident domain models conforming to D05 § 8.11 and § 8.12."""

import enum
import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from logpilot_api.db.base import Base


class IncidentState(enum.StrEnum):
    """Incident lifecycle state machine enumeration (D05 § 5)."""

    DETECTED = "DETECTED"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    IGNORED = "IGNORED"


class IncidentSeverity(enum.StrEnum):
    """Incident operational severity classification."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentEventRole(enum.StrEnum):
    """Role of an associated log event within an incident (D05 § 8.12)."""

    TRIGGER = "TRIGGER"
    EVIDENCE = "EVIDENCE"
    CORRELATED_CONTEXT = "CORRELATED_CONTEXT"


class Incident(Base):
    """Incident entity representing an operational failure or anomaly cluster (D05 § 8.11)."""

    __tablename__ = "incidents"

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
    incident_number: Mapped[str] = mapped_column(
        sa.String(64),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        sa.String(512),
        nullable=False,
    )
    state: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        default=IncidentState.DETECTED.value,
    )
    severity: Mapped[str] = mapped_column(
        sa.String(20),
        nullable=False,
        default=IncidentSeverity.MEDIUM.value,
    )
    window_start: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
    )
    window_end: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
    )
    detected_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
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
    )

    __table_args__ = (
        sa.CheckConstraint(
            "state IN ('DETECTED', 'INVESTIGATING', 'RESOLVED', 'IGNORED')",
            name="ck_incidents_state",
        ),
        sa.CheckConstraint(
            "severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_incidents_severity",
        ),
        sa.UniqueConstraint(
            "project_id",
            "incident_number",
            name="uq_incidents_project_incident_number",
        ),
        sa.UniqueConstraint(
            "id",
            "project_id",
            name="uq_incidents_id_project_id",
        ),
        sa.Index("ix_incidents_project_state", "project_id", "state"),
        sa.Index("ix_incidents_project_created", "project_id", "created_at"),
    )

    # Relationships
    project = relationship("Project")
    events = relationship(
        "IncidentEvent",
        back_populates="incident",
        cascade="all, delete-orphan",
        foreign_keys="[IncidentEvent.incident_id, IncidentEvent.project_id]",
    )


class IncidentEvent(Base):
    """Associative entity linking normalized LogEvents to an Incident (D05 § 8.12)."""

    __tablename__ = "incident_events"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    log_event_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=False,
        index=True,
    )
    event_role: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        default=IncidentEventRole.EVIDENCE.value,
    )
    linked_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["incident_id", "project_id"],
            ["incidents.id", "incidents.project_id"],
            name="fk_incident_events_incident_project",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["log_event_id", "project_id"],
            ["log_events.id", "log_events.project_id"],
            name="fk_incident_events_log_event_project",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "event_role IN ('TRIGGER', 'EVIDENCE', 'CORRELATED_CONTEXT')",
            name="ck_incident_events_role",
        ),
        sa.UniqueConstraint(
            "incident_id",
            "log_event_id",
            name="uq_incident_events_incident_log_event",
        ),
    )

    # Relationships
    incident = relationship(
        "Incident",
        back_populates="events",
        foreign_keys=[incident_id, project_id],
    )
    log_event = relationship(
        "LogEvent",
        foreign_keys=[log_event_id, project_id],
        overlaps="incident,events",
    )
