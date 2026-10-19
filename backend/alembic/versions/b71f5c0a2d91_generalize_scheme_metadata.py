"""generalize scheme metadata and beneficiary profile attributes

Revision ID: b71f5c0a2d91
Revises: a618c63f8521
Create Date: 2026-10-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b71f5c0a2d91"
down_revision: Union[str, Sequence[str], None] = "f4a2b8c91d0e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("schemes", sa.Column("government_level", sa.String(length=30), nullable=True))
    op.add_column("schemes", sa.Column("ministry", sa.String(length=200), nullable=True))
    op.add_column("schemes", sa.Column("department", sa.String(length=200), nullable=True))
    op.add_column("schemes", sa.Column("beneficiary_groups", sa.JSON(), nullable=True))
    op.add_column("schemes", sa.Column("source_url", sa.String(length=500), nullable=True))
    op.add_column("schemes", sa.Column("source_name", sa.String(length=200), nullable=True))
    op.add_column("schemes", sa.Column("verified_at", sa.Date(), nullable=True))
    op.add_column("schemes", sa.Column("verification_status", sa.String(length=30), nullable=True))
    op.add_column("schemes", sa.Column("subcategory", sa.String(length=100), nullable=True))
    # SQLite does not enforce VARCHAR length and cannot alter a column type
    # with this DDL. PostgreSQL receives the intended widening operation.
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("schemes", "category", existing_type=sa.String(length=50), type_=sa.String(length=100), existing_nullable=True)
    op.add_column("user_profiles", sa.Column("beneficiary_group", sa.String(length=100), nullable=True))
    op.add_column("user_profiles", sa.Column("fisher_activity", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("user_profiles", "fisher_activity")
    op.drop_column("user_profiles", "beneficiary_group")
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("schemes", "category", existing_type=sa.String(length=100), type_=sa.String(length=50), existing_nullable=True)
    op.drop_column("schemes", "subcategory")
    op.drop_column("schemes", "verification_status")
    op.drop_column("schemes", "verified_at")
    op.drop_column("schemes", "source_name")
    op.drop_column("schemes", "source_url")
    op.drop_column("schemes", "beneficiary_groups")
    op.drop_column("schemes", "department")
    op.drop_column("schemes", "ministry")
    op.drop_column("schemes", "government_level")
