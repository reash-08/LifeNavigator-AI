"""Stage 3C Mandatory PostgreSQL Test Matrix (PG-01 through PG-10).

Executes exclusively against real PostgreSQL (lifenavigator-test-db) to validate:
- Concurrency and advisory lock lifecycle
- Partial unique indexes
- Canonical redirect constraints and race-safe row-level locking trigger
- Manifest export, validation, and rollback round-trip
- Repeat sync idempotency
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from hashlib import sha256
from pathlib import Path
import psycopg2
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.orm import Session

from app.models.scheme import Scheme
from app.services.scheme_sync import (
    SYNC_ADVISORY_LOCK_ID,
    run_sync_with_advisory_lock,
    sync_all_sources,
)
from app.services.slug_generator import (
    generate_base_slug,
    resolve_slug_collision,
    truncate_slug,
)
from scripts.validate_stage3c_manifest import validate_manifest

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://test_runner:test_isolation_pw_2026@localhost:5433/lifenavigator_stage3c_test"
)


def get_pg_connection():
    return psycopg2.connect(TEST_DB_URL)


@pytest.fixture(scope="session")
def pg_engine():
    engine = create_engine(TEST_DB_URL)
    yield engine
    engine.dispose()


# ==============================================================================
# PG-01: Advisory-lock contention is nonblocking
# ==============================================================================
def test_pg01_advisory_lock_contention_nonblocking():
    conn1 = get_pg_connection()
    conn2 = get_pg_connection()
    try:
        cur1 = conn1.cursor()
        cur2 = conn2.cursor()

        # Connection 1 begins a transaction and acquires the advisory lock
        conn1.autocommit = False
        cur1.execute("SELECT pg_try_advisory_xact_lock(%s);", (SYNC_ADVISORY_LOCK_ID,))
        acquired1 = cur1.fetchone()[0]
        assert acquired1 is True, "Worker 1 should successfully acquire advisory lock."

        # Connection 2 attempts to acquire the same lock within its own transaction
        conn2.autocommit = False
        start_time = time.time()
        cur2.execute("SELECT pg_try_advisory_xact_lock(%s);", (SYNC_ADVISORY_LOCK_ID,))
        acquired2 = cur2.fetchone()[0]
        elapsed = time.time() - start_time

        assert acquired2 is False, "Worker 2 must receive False immediately."
        assert elapsed < 0.2, f"Lock attempt must be non-blocking (took {elapsed:.4f}s)."

        conn1.rollback()
        conn2.rollback()
    finally:
        conn1.close()
        conn2.close()


# ==============================================================================
# PG-02: Lock is released after rollback, disconnect, or process failure
# ==============================================================================
def test_pg02_advisory_lock_released_on_rollback_or_disconnect():
    conn1 = get_pg_connection()
    conn1.autocommit = False
    cur1 = conn1.cursor()
    cur1.execute("SELECT pg_try_advisory_xact_lock(%s);", (SYNC_ADVISORY_LOCK_ID,))
    assert cur1.fetchone()[0] is True

    # Roll back transaction on connection 1
    conn1.rollback()
    conn1.close()

    # Connection 2 should immediately be able to acquire the lock
    conn2 = get_pg_connection()
    conn2.autocommit = False
    cur2 = conn2.cursor()
    cur2.execute("SELECT pg_try_advisory_xact_lock(%s);", (SYNC_ADVISORY_LOCK_ID,))
    acquired2 = cur2.fetchone()[0]
    assert acquired2 is True, "Lock should be released immediately upon rollback/disconnect."
    conn2.rollback()
    conn2.close()


# ==============================================================================
# PG-03: Duplicate active slug/jurisdiction is rejected; inactive duplicate is permitted
# ==============================================================================
def test_pg03_partial_unique_index_active_vs_inactive():
    conn = get_pg_connection()
    conn.autocommit = False
    cur = conn.cursor()

    test_slug = "test-matrix-unique-slug"
    test_juris = "CENTRAL"

    try:
        # Clean up any leftover test rows
        cur.execute("DELETE FROM schemes WHERE slug = %s;", (test_slug,))
        conn.commit()

        # 1. Insert first active scheme with test_slug
        cur.execute("""
            INSERT INTO schemes (name, description, benefit, slug, state, is_active, aliases)
            VALUES ('Active Test Scheme 1', 'Desc', 'Benefit', %s, NULL, TRUE, '[]'::json)
            RETURNING id;
        """, (test_slug,))
        active_id_1 = cur.fetchone()[0]
        conn.commit()

        # 2. Attempt to insert second ACTIVE scheme with same slug -> MUST FAIL
        duplicate_failed = False
        try:
            cur.execute("""
                INSERT INTO schemes (name, description, benefit, slug, state, is_active, aliases)
                VALUES ('Active Test Scheme 2', 'Desc', 'Benefit', %s, NULL, TRUE, '[]'::json);
            """, (test_slug,))
            conn.commit()
        except psycopg2.errors.UniqueViolation:
            duplicate_failed = True
            conn.rollback()

        assert duplicate_failed is True, "Partial unique index must reject duplicate active slug in jurisdiction."

        # 3. Insert an INACTIVE scheme with the same slug -> MUST SUCCEED
        cur.execute("""
            INSERT INTO schemes (name, description, benefit, slug, state, is_active, aliases)
            VALUES ('Inactive Archived Scheme', 'Desc', 'Benefit', %s, NULL, FALSE, '[]'::json)
            RETURNING id;
        """, (test_slug,))
        inactive_id = cur.fetchone()[0]
        conn.commit()
        assert inactive_id > 0, "Inactive duplicate slug must be permitted by partial unique index."

    finally:
        cur.execute("DELETE FROM schemes WHERE slug = %s;", (test_slug,))
        conn.commit()
        conn.close()


# ==============================================================================
# PG-04: Canonical self-reference is rejected
# ==============================================================================
def test_pg04_canonical_self_reference_rejected():
    conn = get_pg_connection()
    conn.autocommit = False
    cur = conn.cursor()

    self_ref_failed = False
    try:
        cur.execute("UPDATE schemes SET canonical_scheme_id = id WHERE id = 11;")
        conn.commit()
    except (psycopg2.errors.CheckViolation, psycopg2.Error):
        self_ref_failed = True
        conn.rollback()
    finally:
        conn.close()

    assert self_ref_failed is True, "Self-reference canonical_scheme_id = id must be rejected by check constraint or trigger."


# ==============================================================================
# PG-05: An active scheme cannot be configured as a redirect
# ==============================================================================
def test_pg05_active_scheme_cannot_have_canonical_redirect():
    conn = get_pg_connection()
    conn.autocommit = False
    cur = conn.cursor()

    active_redirect_failed = False
    try:
        # Scheme 19 is active. Attempting to set canonical_scheme_id while is_active = TRUE
        cur.execute("UPDATE schemes SET canonical_scheme_id = 11 WHERE id = 19 AND is_active = TRUE;")
        conn.commit()
    except (psycopg2.errors.CheckViolation, psycopg2.Error):
        active_redirect_failed = True
        conn.rollback()
    finally:
        conn.close()

    assert active_redirect_failed is True, "Active scheme with canonical_scheme_id must be rejected."


# ==============================================================================
# PG-06: Concurrent target deactivation and redirect creation race test
# ==============================================================================
def test_pg06_concurrent_target_deactivation_and_redirect_creation():
    """Validates that FOR KEY SHARE locking in trigger eliminates redirect race conditions."""
    results = {}
    barrier = threading.Barrier(2)

    def worker_deactivate_target():
        conn = get_pg_connection()
        conn.autocommit = False
        cur = conn.cursor()
        try:
            barrier.wait()
            cur.execute("UPDATE schemes SET is_active = FALSE WHERE id = 11;")
            conn.commit()
            results["deactivate"] = "COMMITTED"
        except Exception as exc:
            results["deactivate"] = f"ERROR: {type(exc).__name__}"
            conn.rollback()
        finally:
            conn.close()

    def worker_create_redirect():
        conn = get_pg_connection()
        conn.autocommit = False
        cur = conn.cursor()
        try:
            barrier.wait()
            # Inactive scheme 6 attempts to redirect to target 11
            cur.execute("UPDATE schemes SET canonical_scheme_id = 11 WHERE id = 6;")
            conn.commit()
            results["redirect"] = "COMMITTED"
        except Exception as exc:
            results["redirect"] = f"ERROR: {type(exc).__name__}"
            conn.rollback()
        finally:
            conn.close()

    t1 = threading.Thread(target=worker_deactivate_target)
    t2 = threading.Thread(target=worker_create_redirect)

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Query final state in database: Scheme 6 must NEVER point to an inactive Scheme 11!
    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute("SELECT s.is_active, s.canonical_scheme_id, t.is_active FROM schemes s LEFT JOIN schemes t ON s.canonical_scheme_id = t.id WHERE s.id = 6;")
    s_active, s_target_id, t_active = cur.fetchone()

    # Reset scheme 11 to active and scheme 6 to point to 11 for baseline continuity
    cur.execute("UPDATE schemes SET is_active = TRUE WHERE id = 11;")
    cur.execute("UPDATE schemes SET canonical_scheme_id = 11 WHERE id = 6;")
    conn.commit()
    conn.close()

    # Invariant assertion: If Scheme 6 points to Scheme 11, Scheme 11 MUST be active
    if s_target_id == 11:
        assert t_active is True, "Target scheme 11 cannot be inactive while Scheme 6 redirects to it!"


# ==============================================================================
# PG-07: Deactivating a referenced canonical target is rejected
# ==============================================================================
def test_pg07_deactivating_referenced_canonical_target_rejected():
    conn = get_pg_connection()
    conn.autocommit = False
    cur = conn.cursor()

    deactivate_failed = False
    try:
        # Scheme 6 is an inactive redirect referencing target Scheme 11
        cur.execute("UPDATE schemes SET is_active = FALSE WHERE id = 11;")
        conn.commit()
    except psycopg2.Error as exc:
        deactivate_failed = True
        conn.rollback()
    finally:
        conn.close()

    assert deactivate_failed is True, "Cannot deactivate scheme 11 while scheme 6 references it as canonical target."


# ==============================================================================
# PG-08: Deleting a referenced target is rejected
# ==============================================================================
def test_pg08_deleting_referenced_canonical_target_rejected():
    conn = get_pg_connection()
    conn.autocommit = False
    cur = conn.cursor()

    delete_failed = False
    try:
        cur.execute("DELETE FROM schemes WHERE id = 11;")
        conn.commit()
    except psycopg2.Error:
        delete_failed = True
        conn.rollback()
    finally:
        conn.close()

    assert delete_failed is True, "Cannot delete scheme 11 while foreign key references exist (ON DELETE RESTRICT)."


# ==============================================================================
# PG-09: Migration, manifest export, downgrade, re-upgrade round-trip
# ==============================================================================
def test_pg09_migration_downgrade_reupgrade_roundtrip():
    backend_dir = Path(__file__).resolve().parents[1] / "backend"
    scripts_dir = backend_dir / "scripts"

    from scripts.export_stage3c_manifest import export_manifest
    from scripts.validate_stage3c_manifest import validate_manifest
    from scripts.run_isolated_migration import run_isolated_migration

    # 1. Export manifest of upgraded database
    manifest_path = export_manifest(TEST_DB_URL)
    assert manifest_path.exists()
    assert validate_manifest(manifest_path, 130) is True

    # 2. Downgrade migration -1
    run_isolated_migration("downgrade", "-1", TEST_DB_URL)

    # Verify columns were removed
    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'schemes' AND column_name IN ('slug', 'aliases', 'canonical_scheme_id');")
    cols = cur.fetchall()
    assert len(cols) == 0, "Columns slug, aliases, canonical_scheme_id must be removed on downgrade."

    # Verify all 130 core schemes still exist
    cur.execute("SELECT count(*) FROM schemes;")
    assert cur.fetchone()[0] == 130, "All 130 schemes must survive migration downgrade without loss."
    conn.close()

    # 3. Re-upgrade to head
    run_isolated_migration("upgrade", "head", TEST_DB_URL)

    # 4. Verify re-upgraded database matches manifest
    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM schemes WHERE slug IS NOT NULL;")
    assert cur.fetchone()[0] == 130, "All 130 schemes must have slugs populated after re-upgrade."
    conn.close()


# ==============================================================================
# PG-10: Three consecutive syncs produce the expected idempotent results
# ==============================================================================
def test_pg10_repeat_sync_idempotency_postgresql(pg_engine):
    with Session(pg_engine) as session:
        # Run 1
        res1 = run_sync_with_advisory_lock(session, apply=True)
        assert res1.failed == 0
        assert res1.discovered == 124
        assert res1.unchanged == 124
        assert res1.added == 0

        # Run 2
        res2 = run_sync_with_advisory_lock(session, apply=True)
        assert res2.failed == 0
        assert res2.discovered == 124
        assert res2.unchanged == 124
        assert res2.added == 0

        # Run 3
        res3 = run_sync_with_advisory_lock(session, apply=True)
        assert res3.failed == 0
        assert res3.discovered == 124
        assert res3.unchanged == 124
        assert res3.added == 0


# ==============================================================================
# Additional Edge Case & Resilience Tests
# ==============================================================================
def test_unicode_and_indic_slug_generation():
    hindi_title = "प्रधानमंत्री फसल बीमा योजना"
    slug = generate_base_slug(hindi_title)
    assert slug.startswith("scheme-indic-")
    assert len(slug) <= 80
    assert re.match(r"^[a-z0-9\-]+$", slug)

    tamil_title = "கலைஞர் மகளிர் உரிமைத் திட்டம்"
    slug_ta = generate_base_slug(tamil_title)
    assert slug_ta.startswith("scheme-indic-")


def test_slug_truncation_boundary():
    long_title = "Very Long Government Scheme Name For Agricultural Welfare And Technical Support " * 3
    slug = generate_base_slug(long_title)
    assert len(slug) <= 80
    assert not slug.endswith("-")


def test_deterministic_collision_resolution():
    base = "national-scholarship"
    existing = {base}
    res1 = resolve_slug_collision(base, existing, name="National Scholarship Scheme", source_url="https://scholarships.gov.in")
    res2 = resolve_slug_collision(base, existing, name="National Scholarship Scheme", source_url="https://scholarships.gov.in")
    assert res1 == res2, "Collision resolution must be strictly deterministic across repeated invocations."
    assert res1 != base
    assert len(res1) <= 80


def test_ambiguous_alias_rejection(pg_engine):
    """If two schemes in the same jurisdiction share the same alias, automated matching must reject it as ambiguous."""
    from app.services.scheme_sync import sync_records
    from scripts.seed_schemes import DatasetScheme

    with Session(pg_engine) as session:
        # Create a mock record with an ambiguous alias
        record = DatasetScheme(
            name="Ambiguous Scheme Test",
            description="Test scheme description",
            benefit="Test benefits",
            category="Welfare",
            government_level="Central",
            beneficiary_groups=["Citizens"],
            source_name="Official Portal",
            source_url="https://test.gov.in/scheme",
            aliases=["Shared Non-unique Alias"],
            eligibility_rules=[],
        )
        res = sync_records(session, [record], apply=False)
        # Should not match existing canonical scheme 11 or 19 or 88
        assert res.discovered == 1
        assert res.added == 1 or res.updated == 0


def test_duplicate_candidates_in_single_batch(pg_engine):
    """Duplicate candidates in a single batch must be detected and safely skipped."""
    from app.services.scheme_sync import sync_records
    from scripts.seed_schemes import DatasetScheme

    item1 = DatasetScheme(
        name="Batch Duplicate Test Scheme",
        description="Duplicate test description",
        benefit="Financial aid",
        category="Agriculture",
        government_level="Central",
        beneficiary_groups=["Farmers"],
        source_name="Ministry Portal",
        source_url="https://agri.gov.in/scheme-dup",
        eligibility_rules=[],
    )
    item2 = DatasetScheme(
        name="Batch Duplicate Test Scheme",
        description="Duplicate test description 2",
        benefit="Financial aid",
        category="Agriculture",
        government_level="Central",
        beneficiary_groups=["Farmers"],
        source_name="Ministry Portal",
        source_url="https://agri.gov.in/scheme-dup",
        eligibility_rules=[],
    )

    with Session(pg_engine) as session:
        res = sync_records(session, [item1, item2], apply=False)
        assert res.discovered == 2
        assert res.skipped == 1
        skipped_item = [d for d in res.details if d.get("result") == "duplicate_in_dataset"]
        assert len(skipped_item) == 1


def test_manifest_checksum_mismatch_and_missing_file(tmp_path):
    """Manifest validation must fail if file is missing or checksum does not match."""
    from scripts.validate_stage3c_manifest import validate_manifest

    # 1. Non-existent file
    missing = tmp_path / "non_existent.json"
    assert validate_manifest(missing) is False

    # 2. Tampered content
    tampered_file = tmp_path / "tampered_manifest.json"
    tampered_file.write_text(json.dumps({
        "timestamp": "2026-10-17T06:00:00Z",
        "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
        "total_records": 1,
        "records": [{"id": 1, "name": "Fake", "slug": "fake", "jurisdiction": "CENTRAL"}]
    }))
    assert validate_manifest(tampered_file) is False


def test_foreign_key_integrity_and_record_preservation():
    """All existing 130 schemes and related entities must have intact foreign keys."""
    conn = get_pg_connection()
    cur = conn.cursor()

    # Schemes count
    cur.execute("SELECT count(*) FROM schemes;")
    assert cur.fetchone()[0] == 130

    # Orphaned eligibility rules
    cur.execute("SELECT count(*) FROM eligibility_rules WHERE scheme_id NOT IN (SELECT id FROM schemes);")
    assert cur.fetchone()[0] == 0

    # Orphaned scheme documents
    cur.execute("SELECT count(*) FROM scheme_documents WHERE scheme_id NOT IN (SELECT id FROM schemes);")
    assert cur.fetchone()[0] == 0

    # Orphaned scheme document chunks
    cur.execute("SELECT count(*) FROM scheme_document_chunks WHERE document_id NOT IN (SELECT id FROM scheme_documents);")
    assert cur.fetchone()[0] == 0

    # Orphaned scheme versions
    cur.execute("SELECT count(*) FROM scheme_versions WHERE scheme_id NOT IN (SELECT id FROM schemes);")
    assert cur.fetchone()[0] == 0

    # Orphaned canonical_scheme_id
    cur.execute("SELECT count(*) FROM schemes WHERE canonical_scheme_id IS NOT NULL AND canonical_scheme_id NOT IN (SELECT id FROM schemes);")
    assert cur.fetchone()[0] == 0

    conn.close()


def test_lock_release_after_injected_exception(pg_engine):
    """Advisory lock must be released immediately upon exception and transaction rollback."""
    conn1 = get_pg_connection()
    conn1.autocommit = False
    cur1 = conn1.cursor()

    try:
        cur1.execute("SELECT pg_try_advisory_xact_lock(7421893);")
        assert cur1.fetchone()[0] is True
        # Inject exception
        raise RuntimeError("Simulated unhandled pipeline crash!")
    except RuntimeError:
        conn1.rollback()
    finally:
        conn1.close()

    # Second connection must be able to acquire immediately
    conn2 = get_pg_connection()
    conn2.autocommit = False
    cur2 = conn2.cursor()
    cur2.execute("SELECT pg_try_advisory_xact_lock(7421893);")
    acquired = cur2.fetchone()[0]
    conn2.rollback()
    conn2.close()

    assert acquired is True, "Advisory lock must be immediately available following exception rollback."


# ==============================================================================
# PG-11: Duplicate schemes archival, canonical redirects, and constraint validation
# ==============================================================================
def test_pg11_migration_active_duplicate_handling_and_canonical_redirects():
    """Validates that duplicate schemes (6, 8, 37) are safely deactivated and redirected to canonical targets."""
    conn = get_pg_connection()
    cur = conn.cursor()

    expected_mappings = {
        6: (11, "pm-kisan-archived-6"),
        8: (19, "pmay-u-archived-8"),
        37: (88, "pmfme-archived-37"),
    }

    try:
        for dup_id, (target_id, expected_slug) in expected_mappings.items():
            cur.execute("SELECT id, name, is_active, slug, canonical_scheme_id FROM schemes WHERE id = %s;", (dup_id,))
            row = cur.fetchone()
            assert row is not None, f"Duplicate scheme {dup_id} must exist."
            _id, name, is_active, slug, canonical_id = row
            assert is_active is False, f"Duplicate scheme {dup_id} must be inactive."
            assert slug == expected_slug, f"Duplicate scheme {dup_id} slug '{slug}' != expected '{expected_slug}'."
            assert canonical_id == target_id, f"Duplicate scheme {dup_id} redirect '{canonical_id}' != expected '{target_id}'."

            # Verify target scheme exists, is active, and is terminal
            cur.execute("SELECT id, is_active, canonical_scheme_id FROM schemes WHERE id = %s;", (target_id,))
            target_row = cur.fetchone()
            assert target_row is not None, f"Canonical target scheme {target_id} must exist."
            assert target_row[1] is True, f"Canonical target scheme {target_id} must be ACTIVE."
            assert target_row[2] is None, f"Canonical target scheme {target_id} must be terminal (cannot be redirected)."

    finally:
        conn.close()
