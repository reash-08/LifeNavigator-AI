"""add scheme slug, aliases, canonical redirect and uniqueness constraints

Revision ID: 3c1a2b3c4d5e
Revises: e1a89b72c431
Create Date: 2026-10-17
"""
from __future__ import annotations

import json
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

from app.services.slug_generator import generate_base_slug, resolve_slug_collision

revision: str = "3c1a2b3c4d5e"
down_revision: Union[str, Sequence[str], None] = "e1a89b72c431"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Add columns (slug nullable initially for backfill)
    op.add_column("schemes", sa.Column("slug", sa.String(length=80), nullable=True))
    op.add_column("schemes", sa.Column("aliases", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column(
        "schemes",
        sa.Column("canonical_scheme_id", sa.Integer(), sa.ForeignKey("schemes.id", ondelete="RESTRICT"), nullable=True)
    )

    # 2. Deterministic backfill of existing records
    # Specific historical overrides for duplicate / archived schemes:
    # Scheme ID -> (archive_slug, canonical_target_id)
    archived_overrides = {
        6: ("pm-kisan-archived-6", 11),
        8: ("pmay-u-archived-8", 19),
        37: ("pmfme-archived-37", 88),
        22: ("avyay", None),
        114: ("pmvvy", None),
    }

    # Validate canonical redirect targets and deactivate duplicate schemes before redirect assignment
    for dup_id, (_slug, canonical_target_id) in archived_overrides.items():
        if canonical_target_id is not None:
            # Fresh databases have no historical scheme rows to archive. Keep the
            # migration usable before catalogue data has been seeded, while still
            # validating the target whenever the duplicate row is present.
            duplicate = conn.execute(
                text("SELECT id FROM schemes WHERE id = :dup_id;"),
                {"dup_id": dup_id}
            ).fetchone()
            if not duplicate:
                continue

            # 1. Target scheme must exist, be active, and must NOT be redirected itself
            target = conn.execute(
                text("SELECT id, is_active, canonical_scheme_id FROM schemes WHERE id = :target_id;"),
                {"target_id": canonical_target_id}
            ).fetchone()
            if not target:
                raise ValueError(f"Canonical target scheme {canonical_target_id} does not exist.")
            if not target[1]:  # is_active
                raise ValueError(
                    f"Canonical target scheme {canonical_target_id} is inactive. Redirects must reference an ACTIVE scheme."
                )
            if target[2] is not None:  # canonical_scheme_id
                raise ValueError(
                    f"Canonical target scheme {canonical_target_id} is itself redirected to {target[2]}. Chained redirects are forbidden."
                )

            # 2. Duplicate scheme must be deactivated before receiving canonical redirect
            conn.execute(
                text("UPDATE schemes SET is_active = FALSE WHERE id = :dup_id AND is_active = TRUE;"),
                {"dup_id": dup_id}
            )

    # Initial known aliases for canonical schemes
    seed_aliases = {
        11: ["PM-KISAN Samman Nidhi", "PM Kisan Samman Nidhi"],
        19: ["Pradhan Mantri Awas Yojana - Urban 2.0 (PMAY-U 2.0)", "PMAY-Urban"],
        88: ["Pradhan Mantri Formalisation of Micro Food Processing Enterprises Scheme (PMFME)", "PMFME Scheme"],
    }

    used_slugs_by_jurisdiction: dict[str, set[str]] = {}

    rows = conn.execute(text("SELECT id, name, state, is_active FROM schemes ORDER BY id;")).fetchall()

    for row in rows:
        sid, sname, sstate, sactive = row[0], row[1], row[2], row[3]
        jurisdiction = (sstate or "CENTRAL").upper()
        existing_in_juris = used_slugs_by_jurisdiction.setdefault(jurisdiction, set())

        if sid in archived_overrides:
            slug, canonical_id = archived_overrides[sid]
            if canonical_id is not None:
                sactive = False  # Deactivated duplicate
        else:
            base = generate_base_slug(sname)
            slug = resolve_slug_collision(base, existing_in_juris, name=sname, jurisdiction=jurisdiction)
            canonical_id = None

        if sactive:
            existing_in_juris.add(slug)

        aliases_json = json.dumps(seed_aliases.get(sid, []))
        conn.execute(
            text("""
                UPDATE schemes 
                SET slug = :slug, aliases = CAST(:aliases AS json), canonical_scheme_id = :canonical_id
                WHERE id = :id;
            """),
            {"slug": slug, "aliases": aliases_json, "canonical_id": canonical_id, "id": sid}
        )

    # 3. Enforce NOT NULL on slug
    op.alter_column("schemes", "slug", nullable=False)
    op.create_index("ix_schemes_slug", "schemes", ["slug"])

    # 4. Partial unique index on (slug, COALESCE(state, 'CENTRAL')) WHERE is_active = TRUE
    op.execute("""
        CREATE UNIQUE INDEX uq_schemes_active_slug_jurisdiction 
        ON schemes (slug, COALESCE(state, 'CENTRAL')) 
        WHERE is_active = TRUE;
    """)

    # 5. Non-unique name search index on (lower(trim(name)), COALESCE(state, 'CENTRAL')) WHERE is_active = TRUE
    op.execute("""
        CREATE INDEX ix_schemes_active_lower_name 
        ON schemes (lower(trim(name)), COALESCE(state, 'CENTRAL')) 
        WHERE is_active = TRUE;
    """)

    # 6. Database constraints
    op.create_check_constraint(
        "ck_schemes_canonical_not_self",
        "schemes",
        "canonical_scheme_id IS NULL OR canonical_scheme_id != id"
    )
    op.create_check_constraint(
        "ck_schemes_canonical_only_when_inactive",
        "schemes",
        "is_active = FALSE OR canonical_scheme_id IS NULL"
    )

    # 7. PostgreSQL trigger with row-level locking (FOR KEY SHARE)
    op.execute("""
        CREATE OR REPLACE FUNCTION fn_canonical_target_integrity()
        RETURNS TRIGGER AS $$
        DECLARE
            v_target_active BOOLEAN;
        BEGIN
            -- Guard 1: Prevent self-reference
            IF (NEW.canonical_scheme_id IS NOT NULL AND NEW.canonical_scheme_id = NEW.id) THEN
                RAISE EXCEPTION 'Integrity Violation: Scheme ID % cannot reference itself as a canonical target.', NEW.id
                    USING ERRCODE = 'check_violation';
            END IF;

            -- Guard 2: Prevent deactivating an active scheme if others redirect to it
            IF (TG_OP = 'UPDATE' AND OLD.is_active = TRUE AND NEW.is_active = FALSE) THEN
                IF EXISTS (SELECT 1 FROM schemes WHERE canonical_scheme_id = OLD.id) THEN
                    RAISE EXCEPTION 'Integrity Violation: Cannot deactivate scheme ID % because one or more inactive schemes reference it as their canonical target.', OLD.id
                        USING ERRCODE = 'restrict_violation';
                END IF;
            END IF;

            -- Guard 3: When setting or updating canonical_scheme_id, LOCK target row FOR KEY SHARE
            IF (NEW.canonical_scheme_id IS NOT NULL) THEN
                SELECT is_active INTO v_target_active 
                FROM schemes 
                WHERE id = NEW.canonical_scheme_id 
                FOR KEY SHARE;

                IF NOT FOUND THEN
                    RAISE EXCEPTION 'Integrity Violation: Target canonical_scheme_id % does not exist.', NEW.canonical_scheme_id
                        USING ERRCODE = 'foreign_key_violation';
                END IF;

                IF v_target_active IS NOT TRUE THEN
                    RAISE EXCEPTION 'Integrity Violation: Target canonical_scheme_id % is inactive. Redirects must reference an ACTIVE scheme.', NEW.canonical_scheme_id
                        USING ERRCODE = 'restrict_violation';
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS trg_canonical_target_integrity ON schemes;
        CREATE TRIGGER trg_canonical_target_integrity
        BEFORE INSERT OR UPDATE OF is_active, canonical_scheme_id ON schemes
        FOR EACH ROW
        EXECUTE FUNCTION fn_canonical_target_integrity();
    """)


def downgrade() -> None:
    # 1. Drop trigger and function
    op.execute("DROP TRIGGER IF EXISTS trg_canonical_target_integrity ON schemes;")
    op.execute("DROP FUNCTION IF EXISTS fn_canonical_target_integrity();")

    # 2. Drop constraints
    op.drop_constraint("ck_schemes_canonical_only_when_inactive", "schemes", type_="check")
    op.drop_constraint("ck_schemes_canonical_not_self", "schemes", type_="check")

    # 3. Drop indexes
    op.execute("DROP INDEX IF EXISTS ix_schemes_active_lower_name;")
    op.execute("DROP INDEX IF EXISTS uq_schemes_active_slug_jurisdiction;")
    op.drop_index("ix_schemes_slug", table_name="schemes")

    # 4. Drop columns
    op.drop_column("schemes", "canonical_scheme_id")
    op.drop_column("schemes", "aliases")
    op.drop_column("schemes", "slug")
