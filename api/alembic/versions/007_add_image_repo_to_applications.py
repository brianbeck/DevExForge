"""Add image_repo column to applications

Revision ID: 007
Revises: 006
Create Date: 2026-04-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column("image_repo", sa.String(512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("applications", "image_repo")
