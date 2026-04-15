"""Add promotion_gates, promotion_requests, promotion_gate_results

Revision ID: 006
Revises: 005
Create Date: 2026-04-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- promotion_gates ---
    op.create_table(
        "promotion_gates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "application_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("tier", sa.String(32), nullable=False),
        sa.Column("gate_type", sa.String(64), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "enforcement",
            sa.String(16),
            nullable=False,
            server_default="blocking",
        ),
        sa.Column("created_by", sa.String(256), nullable=False),
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
        sa.CheckConstraint(
            "scope IN ('platform','team')",
            name="ck_promotion_gates_scope",
        ),
        sa.CheckConstraint(
            "enforcement IN ('blocking','advisory')",
            name="ck_promotion_gates_enforcement",
        ),
    )
    op.create_index(
        "ix_promotion_gates_scope_tier",
        "promotion_gates",
        ["scope", "tier"],
    )
    op.create_index(
        "ix_promotion_gates_team_id",
        "promotion_gates",
        ["team_id"],
    )
    op.create_index(
        "ix_promotion_gates_application_id",
        "promotion_gates",
        ["application_id"],
    )

    # --- promotion_requests ---
    op.create_table(
        "promotion_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "application_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "from_deployment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("application_deployments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "to_environment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("environments.id"),
            nullable=False,
        ),
        sa.Column("source_tier", sa.String(32), nullable=True),
        sa.Column("target_tier", sa.String(32), nullable=False),
        sa.Column("requested_by", sa.String(256), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("image_tag", sa.String(256), nullable=True),
        sa.Column("chart_version", sa.String(64), nullable=True),
        sa.Column("git_sha", sa.String(64), nullable=True),
        sa.Column("value_overrides", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "strategy",
            sa.String(32),
            nullable=False,
            server_default="rolling",
        ),
        sa.Column("canary_steps", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("force_reason", sa.Text(), nullable=True),
        sa.Column("forced_by", sa.String(256), nullable=True),
        sa.Column("approver_email", sa.String(256), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_reason", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rollback_revision", sa.String(256), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending_gates','pending_approval','approved','rejected',"
            "'executing','completed','failed','rolled_back','cancelled')",
            name="ck_promotion_requests_status",
        ),
        sa.CheckConstraint(
            "strategy IN ('rolling','bluegreen','canary')",
            name="ck_promotion_requests_strategy",
        ),
    )
    op.create_index(
        "ix_promotion_requests_status_time",
        "promotion_requests",
        ["status", sa.text("requested_at DESC")],
    )
    op.create_index(
        "ix_promotion_requests_app_id_time",
        "promotion_requests",
        ["application_id", sa.text("requested_at DESC")],
    )

    # --- promotion_gate_results ---
    op.create_table(
        "promotion_gate_results",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column(
            "promotion_request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("promotion_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "gate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("promotion_gates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("gate_type", sa.String(64), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_gate_results_request_id",
        "promotion_gate_results",
        ["promotion_request_id"],
    )

    # --- updated_at trigger on promotion_gates ---
    op.execute("""
        CREATE TRIGGER trg_promotion_gates_updated_at
        BEFORE UPDATE ON promotion_gates
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
    """)

    # --- Seed platform mandatory gates ---
    op.execute("""
        INSERT INTO promotion_gates
            (id, scope, team_id, application_id, tier, gate_type, config, enforcement, created_by)
        VALUES
            (gen_random_uuid(), 'platform', NULL, NULL, 'staging', 'deployed_in_prior_env', NULL, 'blocking', 'system'),
            (gen_random_uuid(), 'platform', NULL, NULL, 'staging', 'health_passing', NULL, 'blocking', 'system'),
            (gen_random_uuid(), 'platform', NULL, NULL, 'production', 'deployed_in_prior_env', NULL, 'blocking', 'system'),
            (gen_random_uuid(), 'platform', NULL, NULL, 'production', 'health_passing', NULL, 'blocking', 'system'),
            (gen_random_uuid(), 'platform', NULL, NULL, 'production', 'min_time_in_prior_env', '{"hours": 24}'::jsonb, 'blocking', 'system'),
            (gen_random_uuid(), 'platform', NULL, NULL, 'production', 'no_critical_cves', NULL, 'blocking', 'system'),
            (gen_random_uuid(), 'platform', NULL, NULL, 'production', 'compliance_score_min', '{"min": 80}'::jsonb, 'blocking', 'system'),
            (gen_random_uuid(), 'platform', NULL, NULL, 'production', 'manual_approval', '{"required_role": "admin", "count": 1}'::jsonb, 'blocking', 'system')
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_promotion_gates_updated_at ON promotion_gates")

    op.drop_index("ix_gate_results_request_id", table_name="promotion_gate_results")
    op.drop_table("promotion_gate_results")

    op.drop_index("ix_promotion_requests_app_id_time", table_name="promotion_requests")
    op.drop_index("ix_promotion_requests_status_time", table_name="promotion_requests")
    op.drop_table("promotion_requests")

    op.drop_index("ix_promotion_gates_application_id", table_name="promotion_gates")
    op.drop_index("ix_promotion_gates_team_id", table_name="promotion_gates")
    op.drop_index("ix_promotion_gates_scope_tier", table_name="promotion_gates")
    op.drop_table("promotion_gates")
