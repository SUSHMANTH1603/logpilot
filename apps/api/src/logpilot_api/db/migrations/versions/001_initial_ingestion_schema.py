"""Initial migration creating projects, log_sources, ingestion_runs, log_templates, and log_events.

Revision ID: 001_initial_ingestion_schema
Revises:
Create Date: 2026-10-25 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial_ingestion_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. projects table (D05 § 8.2)
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
        sa.UniqueConstraint("slug", name=op.f("uq_projects_slug")),
    )
    op.create_index(op.f("ix_projects_slug"), "projects", ["slug"], unique=True)

    # 2. log_sources table (D05 § 8.6 & D11 § 7.1)
    op.create_table(
        "log_sources",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("environment", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("ingestion_key_hash", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_log_sources_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_log_sources")),
        sa.UniqueConstraint(
            "project_id",
            "name",
            "environment",
            name=op.f("uq_log_sources_project_id_name_environment"),
        ),
        sa.UniqueConstraint(
            "id",
            "project_id",
            name=op.f("uq_log_sources_id_project_id"),
        ),
    )
    op.create_index(op.f("ix_log_sources_project_id"), "log_sources", ["project_id"], unique=False)

    # 3. ingestion_runs table (D05 § 8.7 & D07 § 8.2)
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("log_source_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("events_processed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("errors_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "events_processed >= 0",
            name=op.f("ck_ingestion_runs_events_processed"),
        ),
        sa.CheckConstraint(
            "errors_count >= 0",
            name=op.f("ck_ingestion_runs_errors_count"),
        ),
        sa.ForeignKeyConstraint(
            ["log_source_id"],
            ["log_sources.id"],
            name=op.f("fk_ingestion_runs_log_source_id_log_sources"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingestion_runs")),
    )
    op.create_index(
        op.f("ix_ingestion_runs_log_source_id"),
        "ingestion_runs",
        ["log_source_id"],
        unique=False,
    )

    # 4. log_templates table (D05 § 8.8)
    op.create_table(
        "log_templates",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("template_hash", sa.String(length=64), nullable=False),
        sa.Column("pattern_raw", sa.Text(), nullable=False),
        sa.Column("occurrence_count", sa.BigInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_log_templates_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_log_templates")),
        sa.UniqueConstraint(
            "project_id",
            "template_hash",
            name=op.f("uq_log_templates_project_id_template_hash"),
        ),
        sa.UniqueConstraint(
            "id",
            "project_id",
            name=op.f("uq_log_templates_id_project_id"),
        ),
    )
    op.create_index(
        op.f("ix_log_templates_project_id"),
        "log_templates",
        ["project_id"],
        unique=False,
    )

    # 5. log_events table (D05 § 8.9 & D07 § 3/9)
    op.create_table(
        "log_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("log_source_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("template_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("message_raw", sa.Text(), nullable=False),
        sa.Column(
            "attributes",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_log_events_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["log_source_id", "project_id"],
            ["log_sources.id", "log_sources.project_id"],
            name=op.f("fk_log_events_source_project"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["template_id", "project_id"],
            ["log_templates.id", "log_templates.project_id"],
            name=op.f("fk_log_events_template_project"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_log_events")),
        sa.UniqueConstraint(
            "project_id",
            "log_source_id",
            "event_hash",
            "timestamp",
            name=op.f("uq_log_events_project_id_log_source_id_event_hash_timestamp"),
        ),
    )
    op.create_index(op.f("ix_log_events_event_hash"), "log_events", ["event_hash"], unique=False)
    op.create_index(op.f("ix_log_events_level"), "log_events", ["level"], unique=False)
    op.create_index(op.f("ix_log_events_log_source_id"), "log_events", ["log_source_id"], unique=False)
    op.create_index(op.f("ix_log_events_project_id"), "log_events", ["project_id"], unique=False)
    op.create_index(op.f("ix_log_events_template_id"), "log_events", ["template_id"], unique=False)
    op.create_index(op.f("ix_log_events_timestamp"), "log_events", ["timestamp"], unique=False)
    op.create_index(
        "ix_log_events_project_timestamp",
        "log_events",
        ["project_id", "timestamp"],
        unique=False,
    )
    op.create_index(
        "ix_log_events_source_timestamp",
        "log_events",
        ["log_source_id", "timestamp"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_log_events_source_timestamp", table_name="log_events")
    op.drop_index("ix_log_events_project_timestamp", table_name="log_events")
    op.drop_index(op.f("ix_log_events_timestamp"), table_name="log_events")
    op.drop_index(op.f("ix_log_events_template_id"), table_name="log_events")
    op.drop_index(op.f("ix_log_events_project_id"), table_name="log_events")
    op.drop_index(op.f("ix_log_events_log_source_id"), table_name="log_events")
    op.drop_index(op.f("ix_log_events_level"), table_name="log_events")
    op.drop_index(op.f("ix_log_events_event_hash"), table_name="log_events")
    op.drop_table("log_events")

    op.drop_index(op.f("ix_log_templates_project_id"), table_name="log_templates")
    op.drop_table("log_templates")

    op.drop_index(op.f("ix_ingestion_runs_log_source_id"), table_name="ingestion_runs")
    op.drop_table("ingestion_runs")

    op.drop_index(op.f("ix_log_sources_project_id"), table_name="log_sources")
    op.drop_table("log_sources")

    op.drop_index(op.f("ix_projects_slug"), table_name="projects")
    op.drop_table("projects")
