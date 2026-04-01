"""Initial migration - create all tables

Revision ID: 001
Revises:
Create Date: 2026-03-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "teams",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(128), unique=True, nullable=False, index=True),
        sa.Column("display_name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("owner_email", sa.String(256), nullable=False),
        sa.Column("owner_keycloak_id", sa.String(256), nullable=True),
        sa.Column("cost_center", sa.String(128), nullable=True),
        sa.Column("tags", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "team_members",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "team_id",
            UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(256), nullable=False),
        sa.Column("keycloak_id", sa.String(256), nullable=True),
        sa.Column("role", sa.String(32), nullable=False, server_default="developer"),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_team_members_team_id", "team_members", ["team_id"])
    op.create_index("ix_team_members_email", "team_members", ["email"])

    op.create_table(
        "environments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "team_id",
            UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tier", sa.String(32), nullable=False),
        sa.Column("resource_quota", JSONB, nullable=True),
        sa.Column("limit_range", JSONB, nullable=True),
        sa.Column("network_policy", JSONB, nullable=True),
        sa.Column("policies", JSONB, nullable=True),
        sa.Column("argocd_config", JSONB, nullable=True),
        sa.Column("namespace_name", sa.String(256), unique=True, nullable=False, index=True),
        sa.Column("phase", sa.String(64), nullable=False, server_default="Pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_environments_team_id", "environments", ["team_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("user_email", sa.String(256), nullable=False),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(256), nullable=True),
        sa.Column("team_slug", sa.String(128), nullable=True),
        sa.Column("request_body", JSONB, nullable=True),
        sa.Column("response_status", sa.Integer, nullable=True),
    )
    op.create_index("ix_audit_log_team_slug", "audit_log", ["team_slug"])
    op.create_index("ix_audit_log_timestamp", "audit_log", ["timestamp"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("environments")
    op.drop_table("team_members")
    op.drop_table("teams")
