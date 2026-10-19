"""add source registry, scheme version history and sync audit

Revision ID: 4f31b2c8a601
Revises: c35b18d90a42
Create Date: 2026-10-07
"""
from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4f31b2c8a601"
down_revision: Union[str, Sequence[str], None] = "c35b18d90a42"
branch_labels = None
depends_on = None


def _json_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def upgrade() -> None:
    op.add_column(
        "schemes",
        sa.Column("eligibility_verification_status", sa.String(30), nullable=False, server_default="unverified"),
    )
    op.create_table(
        "scheme_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_name", sa.String(200), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("api_url", sa.String(1000), nullable=True),
        sa.Column("provider", sa.String(300), nullable=True),
        sa.Column("source_type", sa.String(40), nullable=False, server_default="official_portal"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_checked", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful_sync", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("source_name", "source_url", name="uq_scheme_source_name_url"),
    )
    with op.batch_alter_table("schemes") as batch_op:
        batch_op.add_column(sa.Column("source_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_schemes_source_id_scheme_sources", "scheme_sources", ["source_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_schemes_source_id", "schemes", ["source_id"])
    op.create_table(
        "scheme_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scheme_id", sa.Integer(), sa.ForeignKey("schemes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("scheme_sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column("verification_status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("eligibility_verification_status", sa.String(30), nullable=False, server_default="unverified"),
        sa.Column("verified_at", sa.Date(), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_until", sa.Date(), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("scheme_id", "version_number", name="uq_scheme_version_number"),
        sa.UniqueConstraint("scheme_id", "content_hash", name="uq_scheme_version_hash"),
    )
    op.create_index("ix_scheme_versions_scheme_id", "scheme_versions", ["scheme_id"])
    op.create_index("ix_scheme_versions_source_id", "scheme_versions", ["source_id"])
    op.add_column("eligibility_rules", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    with op.batch_alter_table("eligibility_rules") as batch_op:
        batch_op.add_column(sa.Column("source_version_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_eligibility_rules_source_version_id", "scheme_versions", ["source_version_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_eligibility_rules_source_version_id", "eligibility_rules", ["source_version_id"])
    op.create_table(
        "scheme_import_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("scheme_sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_name", sa.String(200), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="running"),
        sa.Column("discovered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("added", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unchanged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("details", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_scheme_import_history_source_id", "scheme_import_history", ["source_id"])

    # Seed an immutable baseline version for every existing record. Preserve
    # existing source and rule data; the snapshot is an audit baseline only.
    bind = op.get_bind()
    schemes = sa.Table("schemes", sa.MetaData(), autoload_with=bind)
    rules = sa.Table("eligibility_rules", sa.MetaData(), autoload_with=bind)
    sources = sa.Table("scheme_sources", sa.MetaData(), autoload_with=bind)
    versions = sa.Table("scheme_versions", sa.MetaData(), autoload_with=bind)
    for row in bind.execute(sa.select(schemes)).mappings():
        snapshot = {key: _json_value(value) for key, value in row.items() if key not in {"id", "source_id"}}
        rule_rows = bind.execute(sa.select(rules).where(rules.c.scheme_id == row["id"])).mappings().all()
        snapshot["eligibility_rules"] = [
            {key: value for key, value in rule.items() if key not in {"id", "scheme_id"}}
            for rule in rule_rows
        ]
        source_id = None
        if row.get("source_name") and row.get("source_url"):
            source_id = bind.execute(
                sa.select(sources.c.id).where(
                    sources.c.source_name == row["source_name"],
                    sources.c.source_url == row["source_url"],
                )
            ).scalar_one_or_none()
            if source_id is None:
                source_id = bind.execute(
                    sa.insert(sources).values(
                        source_name=row["source_name"],
                        source_url=row["source_url"],
                        provider=row.get("ministry"),
                        source_type="official_portal",
                        is_active=True,
                        notes="Backfilled from an existing scheme record during migration.",
                    )
                ).inserted_primary_key[0]
            bind.execute(sa.update(schemes).where(schemes.c.id == row["id"]).values(source_id=source_id))
        canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        bind.execute(
            sa.insert(versions).values(
                scheme_id=row["id"],
                source_id=source_id,
                version_number=1,
                snapshot=snapshot,
                source_url=row.get("source_url"),
                verification_status=row.get("verification_status") or "pending",
                eligibility_verification_status="unverified",
                verified_at=row.get("verified_at"),
                change_summary="Baseline snapshot created by additive scheme-data migration.",
                content_hash=sha256(canonical.encode("utf-8")).hexdigest(),
            )
        )
        baseline_version_id = bind.execute(
            sa.select(versions.c.id).where(versions.c.scheme_id == row["id"], versions.c.version_number == 1)
        ).scalar_one()
        if rule_rows:
            bind.execute(sa.update(rules).where(rules.c.scheme_id == row["id"]).values(source_version_id=baseline_version_id))


def downgrade() -> None:
    op.drop_index("ix_scheme_import_history_source_id", table_name="scheme_import_history")
    op.drop_table("scheme_import_history")
    op.drop_index("ix_eligibility_rules_source_version_id", table_name="eligibility_rules")
    with op.batch_alter_table("eligibility_rules") as batch_op:
        batch_op.drop_constraint("fk_eligibility_rules_source_version_id", type_="foreignkey")
        batch_op.drop_column("source_version_id")
    op.drop_column("eligibility_rules", "is_active")
    op.drop_index("ix_scheme_versions_source_id", table_name="scheme_versions")
    op.drop_index("ix_scheme_versions_scheme_id", table_name="scheme_versions")
    op.drop_table("scheme_versions")
    op.drop_index("ix_schemes_source_id", table_name="schemes")
    with op.batch_alter_table("schemes") as batch_op:
        batch_op.drop_constraint("fk_schemes_source_id_scheme_sources", type_="foreignkey")
        batch_op.drop_column("source_id")
    op.drop_table("scheme_sources")
    op.drop_column("schemes", "eligibility_verification_status")
