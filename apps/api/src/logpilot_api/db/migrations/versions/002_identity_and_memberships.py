"""Identity and project memberships migration conforming to D05 § 8.1 and § 8.3.

Revision ID: 002_identity_and_memberships
Revises: 001_initial_ingestion_schema
Create Date: 2026-10-26 01:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_identity_and_memberships"
down_revision: str | None = "001_initial_ingestion_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. users table (D05 § 8.1)
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )

    # 2. project_memberships table (D05 § 8.3)
    op.create_table(
        "project_memberships",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_project_memberships_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_project_memberships_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_memberships")),
        sa.UniqueConstraint(
            "project_id",
            "user_id",
            name=op.f("uq_project_memberships_project_id_user_id"),
        ),
        sa.CheckConstraint(
            "role IN ('OWNER', 'ENGINEER', 'VIEWER')",
            name=op.f("ck_project_memberships_role"),
        ),
    )
    op.create_index(
        op.f("ix_project_memberships_project_id"),
        "project_memberships",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_memberships_user_id"),
        "project_memberships",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_project_memberships_user_id"), table_name="project_memberships")
    op.drop_index(op.f("ix_project_memberships_project_id"), table_name="project_memberships")
    op.drop_table("project_memberships")
    op.drop_table("users")
