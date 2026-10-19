"""store source-backed application instructions on scheme records

Revision ID: d93812ca7b6a
Revises: 4f31b2c8a601
Create Date: 2026-10-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d93812ca7b6a"
down_revision: Union[str, Sequence[str], None] = "4f31b2c8a601"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("schemes", sa.Column("application_process", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("schemes", "application_process")
