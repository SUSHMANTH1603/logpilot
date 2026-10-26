"""Anomaly detection and incident lifecycle schema conforming to D05 § 8.10-8.12.

Revision ID: 003_anomalies_and_incidents
Revises: 002_identity_and_memberships
Create Date: 2026-10-26 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003_anomalies_and_incidents"
down_revision: str | None = "002_identity_and_memberships"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPROVED_ANOMALY_TYPES = (
    "ERROR_RATE_SPIKE",
    "FREQUENCY_SPIKE",
    "NEW_LOG_TEMPLATE",
    "NEW_TEMPLATE_ERROR",
    "VOLUME_DROP",
    "BURST_DEVIATION",
    "SEQUENCE_DEVIATION",
)


def upgrade() -> None:
    # 1. anomaly_signals table (D05 § 8.10)
    op.create_table(
        "anomaly_signals",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("log_source_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("anomaly_type", sa.String(length=50), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "feature_vector",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_anomaly_signals_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["log_source_id", "project_id"],
            ["log_sources.id", "log_sources.project_id"],
            name="fk_anomaly_signals_source_project",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_anomaly_signals")),
        sa.CheckConstraint(
            "confidence_score >= 0.0 AND confidence_score <= 1.0",
            name="ck_anomaly_signals_confidence",
        ),
        sa.CheckConstraint(
            f"anomaly_type IN {APPROVED_ANOMALY_TYPES}",
            name="ck_anomaly_signals_type",
        ),
    )
    op.create_index(
        op.f("ix_anomaly_signals_project_id"),
        "anomaly_signals",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_anomaly_signals_log_source_id"),
        "anomaly_signals",
        ["log_source_id"],
        unique=False,
    )
    op.create_index(
        "ix_anomaly_signals_project_detected_at",
        "anomaly_signals",
        ["project_id", "detected_at"],
        unique=False,
    )
    op.create_index(
        "ix_anomaly_signals_source_window",
        "anomaly_signals",
        ["log_source_id", "window_start", "window_end"],
        unique=False,
    )

    # 2. incidents table (D05 § 8.11)
    op.create_table(
        "incidents",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("incident_number", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column(
            "state",
            sa.String(length=50),
            nullable=False,
            server_default="DETECTED",
        ),
        sa.Column(
            "severity",
            sa.String(length=20),
            nullable=False,
            server_default="MEDIUM",
        ),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_incidents_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incidents")),
        sa.UniqueConstraint(
            "project_id",
            "incident_number",
            name=op.f("uq_incidents_project_id_incident_number"),
        ),
        sa.UniqueConstraint(
            "id",
            "project_id",
            name=op.f("uq_incidents_id_project_id"),
        ),
        sa.CheckConstraint(
            "state IN ('DETECTED', 'INVESTIGATING', 'RESOLVED', 'IGNORED')",
            name="ck_incidents_state",
        ),
        sa.CheckConstraint(
            "severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_incidents_severity",
        ),
    )
    op.create_index(
        op.f("ix_incidents_project_id"),
        "incidents",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_incidents_project_state",
        "incidents",
        ["project_id", "state"],
        unique=False,
    )
    op.create_index(
        "ix_incidents_project_created",
        "incidents",
        ["project_id", "created_at"],
        unique=False,
    )

    # 3. Composite unique constraint on log_events for incident_events FK reference
    op.create_unique_constraint(
        "uq_log_events_id_project_id",
        "log_events",
        ["id", "project_id"],
    )

    # 4. incident_events table (D05 § 8.12)
    op.create_table(
        "incident_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("incident_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("log_event_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "event_role",
            sa.String(length=50),
            nullable=False,
            server_default="EVIDENCE",
        ),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["incident_id", "project_id"],
            ["incidents.id", "incidents.project_id"],
            name="fk_incident_events_incident_project",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_incident_events_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["log_event_id", "project_id"],
            ["log_events.id", "log_events.project_id"],
            name="fk_incident_events_log_event_project",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incident_events")),
        sa.UniqueConstraint(
            "incident_id",
            "log_event_id",
            name="uq_incident_events_incident_log_event",
        ),
        sa.CheckConstraint(
            "event_role IN ('TRIGGER', 'EVIDENCE', 'CORRELATED_CONTEXT')",
            name="ck_incident_events_role",
        ),
    )
    op.create_index(
        op.f("ix_incident_events_incident_id"),
        "incident_events",
        ["incident_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_incident_events_project_id"),
        "incident_events",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_incident_events_log_event_id"),
        "incident_events",
        ["log_event_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_incident_events_log_event_id"), table_name="incident_events")
    op.drop_index(op.f("ix_incident_events_project_id"), table_name="incident_events")
    op.drop_index(op.f("ix_incident_events_incident_id"), table_name="incident_events")
    op.drop_table("incident_events")
    op.drop_constraint("uq_log_events_id_project_id", "log_events", type_="unique")

    op.drop_index("ix_incidents_project_created", table_name="incidents")
    op.drop_index("ix_incidents_project_state", table_name="incidents")
    op.drop_index(op.f("ix_incidents_project_id"), table_name="incidents")
    op.drop_table("incidents")

    op.drop_index("ix_anomaly_signals_source_window", table_name="anomaly_signals")
    op.drop_index("ix_anomaly_signals_project_detected_at", table_name="anomaly_signals")
    op.drop_index(op.f("ix_anomaly_signals_log_source_id"), table_name="anomaly_signals")
    op.drop_index(op.f("ix_anomaly_signals_project_id"), table_name="anomaly_signals")
    op.drop_table("anomaly_signals")
