"""Add applications, application_deployments, application_deployment_events

Revision ID: 005
Revises: 004
Create Date: 2026-04-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- applications ---
    op.create_table(
        "applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("display_name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("repo_url", sa.String(512), nullable=True),
        sa.Column("chart_path", sa.String(256), nullable=True),
        sa.Column("chart_repo_url", sa.String(512), nullable=True),
        sa.Column("owner_email", sa.String(256), nullable=False),
        sa.Column(
            "default_strategy",
            sa.String(32),
            nullable=False,
            server_default="rolling",
        ),
        sa.Column("canary_steps", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("app_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("team_id", "name", name="uq_applications_team_name"),
    )
    op.create_index(
        "ix_applications_team_id",
        "applications",
        ["team_id"],
    )

    # --- application_deployments ---
    op.create_table(
        "application_deployments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "application_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "environment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("environments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("argocd_app_name", sa.String(256), nullable=False),
        sa.Column("image_tag", sa.String(256), nullable=True),
        sa.Column("chart_version", sa.String(64), nullable=True),
        sa.Column("git_sha", sa.String(64), nullable=True),
        sa.Column("health_status", sa.String(32), nullable=True),
        sa.Column("sync_status", sa.String(32), nullable=True),
        sa.Column(
            "strategy",
            sa.String(32),
            nullable=False,
            server_default="rolling",
        ),
        sa.Column(
            "deployed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deployed_by", sa.String(256), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_status", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.UniqueConstraint(
            "application_id", "environment_id", name="uq_app_deployments_app_env"
        ),
    )
    op.create_index(
        "ix_application_deployments_app_id",
        "application_deployments",
        ["application_id"],
    )
    op.create_index(
        "ix_application_deployments_env_id",
        "application_deployments",
        ["environment_id"],
    )

    # --- application_deployment_events ---
    op.create_table(
        "application_deployment_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column(
            "deployment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("application_deployments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("from_version", sa.String(256), nullable=True),
        sa.Column("to_version", sa.String(256), nullable=True),
        sa.Column("actor", sa.String(256), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_deployment_events_deployment_id_time",
        "application_deployment_events",
        ["deployment_id", sa.text("occurred_at DESC")],
    )

    # --- updated_at trigger on applications ---
    op.execute("""
        CREATE TRIGGER trg_applications_updated_at
        BEFORE UPDATE ON applications
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_applications_updated_at ON applications")

    op.drop_index(
        "ix_deployment_events_deployment_id_time",
        table_name="application_deployment_events",
    )
    op.drop_table("application_deployment_events")

    op.drop_index(
        "ix_application_deployments_env_id", table_name="application_deployments"
    )
    op.drop_index(
        "ix_application_deployments_app_id", table_name="application_deployments"
    )
    op.drop_table("application_deployments")

    op.drop_index("ix_applications_team_id", table_name="applications")
    op.drop_table("applications")
