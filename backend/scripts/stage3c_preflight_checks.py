"""Stage 3C Preflight Verification Script.

Validates that the target database is in a consistent, expected starting state
prior to executing Stage 3C schema migrations.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
import psycopg2

def run_preflight_checks(connection_url: str, post_migration: bool = False) -> bool:
    print(f"Connecting to database to run Stage 3C preflight checks...")
    conn = psycopg2.connect(connection_url)
    cur = conn.cursor()

    cur.execute("SELECT current_database(), current_user, inet_server_port();")
    db_name, db_user, db_port = cur.fetchone()
    print(f"Target Database: {db_name} | User: {db_user} | Port: {db_port}")

    passed = True

    # 1. Check scheme counts
    cur.execute("SELECT is_active, count(*) FROM schemes GROUP BY is_active ORDER BY is_active;")
    counts = dict(cur.fetchall())
    inactive_count = counts.get(False, 0)
    active_count = counts.get(True, 0)
    total_count = inactive_count + active_count

    print(f"Scheme counts: Total={total_count}, Active={active_count}, Inactive={inactive_count}")
    if total_count != 130 or active_count != 125 or inactive_count != 5:
        print(f"FAIL: Expected 130 total (125 active, 5 inactive), got Total={total_count}, Active={active_count}, Inactive={inactive_count}")
        passed = False
    else:
        print("PASS: Scheme counts match baseline (130 total, 125 active, 5 inactive).")

    # 2. Check foreign key integrity (zero orphaned records)
    tables_to_check = [
        ("eligibility_rules", "scheme_id", "schemes", "id"),
        ("scheme_documents", "scheme_id", "schemes", "id"),
        ("scheme_document_chunks", "document_id", "scheme_documents", "id"),
        ("scheme_versions", "scheme_id", "schemes", "id"),
    ]
    for child_tbl, child_fk, parent_tbl, parent_pk in tables_to_check:
        query = f"SELECT count(*) FROM {child_tbl} WHERE {child_fk} NOT IN (SELECT {parent_pk} FROM {parent_tbl});"
        cur.execute(query)
        orphan_count = cur.fetchone()[0]
        if orphan_count != 0:
            print(f"FAIL: Found {orphan_count} orphaned records in {child_tbl}.{child_fk}")
            passed = False
        else:
            print(f"PASS: 0 orphans in {child_tbl}.{child_fk}")

    # 3. Canonical target scheme sanity
    cur.execute("SELECT id, is_active FROM schemes WHERE id IN (6, 8, 11, 19, 22, 37, 88, 114) ORDER BY id;")
    status_map = dict(cur.fetchall())
    expected_active = {11: True, 19: True, 88: True, 6: False, 8: False, 37: False, 22: False, 114: False}
    for sid, exp in expected_active.items():
        actual = status_map.get(sid)
        if actual != exp:
            print(f"FAIL: Scheme {sid} expected is_active={exp}, got {actual}")
            passed = False
        else:
            print(f"PASS: Scheme {sid} is_active={actual} as expected.")

    # 4. Check for column / index conflicts
    target_cols = ['slug', 'aliases', 'canonical_scheme_id']
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'schemes' AND column_name IN ('slug', 'aliases', 'canonical_scheme_id');
    """)
    existing_cols = [r[0] for r in cur.fetchall()]

    expected_indexes = ['uq_schemes_active_slug_jurisdiction', 'ix_schemes_active_lower_name']
    cur.execute("""
        SELECT indexname FROM pg_indexes 
        WHERE tablename = 'schemes' AND indexname IN (
            'uq_schemes_active_slug_jurisdiction', 
            'ix_schemes_active_lower_name'
        );
    """)
    existing_idx = [r[0] for r in cur.fetchall()]

    if post_migration:
        missing_cols = [c for c in target_cols if c not in existing_cols]
        if missing_cols:
            print(f"FAIL: Missing expected columns in post-migration database: {missing_cols}")
            passed = False
        else:
            print("PASS: Stage 3C columns exist in upgraded database (slug, aliases, canonical_scheme_id present).")

        missing_idx = [i for i in expected_indexes if i not in existing_idx]
        if missing_idx:
            print(f"FAIL: Missing expected indexes in post-migration database: {missing_idx}")
            passed = False
        else:
            print("PASS: Stage 3C indexes exist in upgraded database.")
    else:
        if existing_cols:
            print(f"WARNING / CONFLICT: Columns already exist in schemes table: {existing_cols}")
            passed = False
        else:
            print("PASS: No Stage 3C column conflicts (slug, aliases, canonical_scheme_id not present).")

        if existing_idx:
            print(f"WARNING / CONFLICT: Indexes already exist: {existing_idx}")
            passed = False
        else:
            print("PASS: No Stage 3C index conflicts.")

    cur.close()
    conn.close()

    print(f"\nChecks result: {'SUCCESS (PASS)' if passed else 'FAILURE'}")
    return passed

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Stage 3C preflight checks.")
    parser.add_argument("--db-url", default=os.getenv("DATABASE_URL"), help="PostgreSQL connection URL")
    parser.add_argument("--post-migration", action="store_true", help="Verify post-migration integrity instead of preflight")
    args = parser.parse_args()

    if not args.db_url:
        print("Error: DATABASE_URL must be provided via --db-url or environment variable.")
        sys.exit(1)

    success = run_preflight_checks(args.db_url, post_migration=args.post_migration)
    sys.exit(0 if success else 1)
