"""Add cluster column to environments

Revision ID: 002
Revises: 001
Create Date: 2026-03-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("environments", sa.Column("cluster", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("environments", "cluster")
