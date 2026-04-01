"""Add catalog_templates, quota_presets, and policy_profiles tables

Revision ID: 003
Revises: 002
Create Date: 2026-03-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "catalog_templates",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), unique=True, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("chart_repo", sa.String(512), nullable=True),
        sa.Column("chart_name", sa.String(128), nullable=True),
        sa.Column("chart_version", sa.String(64), nullable=True),
        sa.Column("default_values", postgresql.JSONB(), nullable=True),
        sa.Column("values_schema", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "quota_presets",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(64), unique=True, nullable=False),
        sa.Column("cpu_request", sa.String(32), nullable=False, server_default="2"),
        sa.Column("cpu_limit", sa.String(32), nullable=False, server_default="4"),
        sa.Column("memory_request", sa.String(32), nullable=False, server_default="4Gi"),
        sa.Column("memory_limit", sa.String(32), nullable=False, server_default="8Gi"),
        sa.Column("pods", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("services", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("pvcs", sa.Integer(), nullable=False, server_default="5"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "policy_profiles",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(64), unique=True, nullable=False),
        sa.Column("max_critical_cves", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_high_cves", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("require_non_root", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("require_read_only_root", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("require_resource_limits", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("policy_profiles")
    op.drop_table("quota_presets")
    op.drop_table("catalog_templates")
