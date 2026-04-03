"""Add unique constraints, indexes, and updated_at triggers

Revision ID: 004
Revises: 003
Create Date: 2026-04-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Unique constraints (prevent race-condition duplicates) ---

    # Remove any existing duplicates before adding constraints
    op.execute("""
        DELETE FROM team_members a USING team_members b
        WHERE a.id > b.id
          AND a.team_id = b.team_id
          AND a.email = b.email
    """)
    op.create_unique_constraint(
        "uq_team_members_team_email",
        "team_members",
        ["team_id", "email"],
    )

    op.execute("""
        DELETE FROM environments a USING environments b
        WHERE a.id > b.id
          AND a.team_id = b.team_id
          AND a.tier = b.tier
    """)
    op.create_unique_constraint(
        "uq_environments_team_tier",
        "environments",
        ["team_id", "tier"],
    )

    # --- Audit log indexes ---

    op.create_index(
        "ix_audit_log_team_slug_timestamp",
        "audit_log",
        ["team_slug", sa.text("timestamp DESC")],
    )
    op.create_index(
        "ix_audit_log_user_email",
        "audit_log",
        ["user_email"],
    )

    # --- updated_at trigger function ---

    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_teams_updated_at
        BEFORE UPDATE ON teams
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
    """)

    op.execute("""
        CREATE TRIGGER trg_environments_updated_at
        BEFORE UPDATE ON environments
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_environments_updated_at ON environments")
    op.execute("DROP TRIGGER IF EXISTS trg_teams_updated_at ON teams")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")

    op.drop_index("ix_audit_log_user_email", table_name="audit_log")
    op.drop_index("ix_audit_log_team_slug_timestamp", table_name="audit_log")

    op.drop_constraint("uq_environments_team_tier", "environments")
    op.drop_constraint("uq_team_members_team_email", "team_members")
