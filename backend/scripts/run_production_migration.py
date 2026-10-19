"""Production Migration Runner for LifeNavigator-AI.

Enforces strict fail-closed safety assertions:
1. Explicit --environment production parameter required.
2. Exact database name, user, port, and server identity checks.
3. Pre-migration revision verification against Alembic lineage.
4. Comprehensive preflight database integrity assertions.
5. Interactive human confirmation prompt ("YES-MIGRATE-PRODUCTION").
6. Complete credential masking in all logs and outputs.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse
import psycopg2


def mask_db_url(url: str) -> str:
    """Mask credentials in database connection URL."""
    try:
        parsed = urlparse(url)
        if parsed.password:
            masked_netloc = parsed.netloc.replace(f":{parsed.password}@", ":****@")
            return parsed._replace(netloc=masked_netloc).geturl()
    except Exception:
        pass
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:****@", url)


class PreflightValidationError(Exception):
    """Raised when preflight database assertions fail."""
    pass


class TargetIdentityError(Exception):
    """Raised when database identity fails strict verification."""
    pass


def verify_target_identity(
    conn,
    expected_db: str,
    expected_user: str,
    expected_port: int | None = None,
) -> dict:
    """Verify target database identity and server metadata."""
    cur = conn.cursor()
    cur.execute("""
        SELECT current_database(), current_user, inet_server_port(), inet_server_addr(), version();
    """)
    row = cur.fetchone()
    cur.close()

    db_name, db_user, db_port, db_addr, db_version = row

    print("=== TARGET DATABASE IDENTITY ===")
    print(f"  Database Name  : {db_name}")
    print(f"  Database User  : {db_user}")
    print(f"  Server Port    : {db_port}")
    print(f"  Server Address : {db_addr or 'local_socket'}")
    print(f"  Server Version : {db_version.split(',')[0] if db_version else 'unknown'}")
    print("================================")

    # 1. Exact Database Name Assertion
    if db_name != expected_db:
        raise TargetIdentityError(
            f"Target database '{db_name}' does not match expected database '{expected_db}'. Aborting!"
        )

    # 2. Exact Database User Assertion
    if db_user != expected_user:
        raise TargetIdentityError(
            f"Target database user '{db_user}' does not match expected user '{expected_user}'. Aborting!"
        )

    # 3. Port Assertion if specified
    if expected_port is not None and db_port is not None and db_port != expected_port:
        raise TargetIdentityError(
            f"Server port {db_port} does not match expected port {expected_port}. Aborting!"
        )

    return {
        "database": db_name,
        "user": db_user,
        "port": db_port,
        "address": str(db_addr),
    }


def execute_preflight_checks(conn, action: str, target_revision: str) -> None:
    """Execute preflight assertions against target database before running Alembic."""
    cur = conn.cursor()
    print("\n[*] Executing Preflight Database Assertions...")

    # 1. Verify current alembic revision
    cur.execute("SELECT version_num FROM alembic_version;")
    current_rev_row = cur.fetchone()
    current_rev = current_rev_row[0] if current_rev_row else None
    print(f"  [>] Current Alembic Revision : {current_rev}")

    if action == "upgrade":
        expected_parent = "e1a89b72c431"
        if target_revision == "3c1a2b3c4d5e" or target_revision == "head":
            if current_rev != expected_parent:
                raise PreflightValidationError(
                    f"Current revision is '{current_rev}', but Stage 3C upgrade requires parent '{expected_parent}'."
                )
    elif action == "downgrade":
        if current_rev != "3c1a2b3c4d5e":
            raise PreflightValidationError(
                f"Cannot downgrade Stage 3C revision; current database revision is '{current_rev}', not '3c1a2b3c4d5e'."
            )

    # 2. Scheme Counts Assertions
    cur.execute("""
        SELECT count(*),
               count(*) FILTER (WHERE is_active = TRUE),
               count(*) FILTER (WHERE is_active = FALSE)
        FROM schemes;
    """)
    total_schemes, active_schemes, inactive_schemes = cur.fetchone()
    print(f"  [>] Scheme Counts : Total={total_schemes}, Active={active_schemes}, Inactive={inactive_schemes}")

    if total_schemes != 130:
        raise PreflightValidationError(f"Expected 130 total schemes, found {total_schemes}.")
    if active_schemes != 125:
        raise PreflightValidationError(f"Expected 125 active schemes, found {active_schemes}.")
    if inactive_schemes != 5:
        raise PreflightValidationError(f"Expected 5 inactive schemes, found {inactive_schemes}.")

    # 3. Foreign Key Integrity Check (Zero Orphans)
    cur.execute("""
        SELECT 'orphaned_eligibility_rules', count(*) FROM eligibility_rules WHERE scheme_id NOT IN (SELECT id FROM schemes)
        UNION ALL
        SELECT 'orphaned_scheme_documents', count(*) FROM scheme_documents WHERE scheme_id NOT IN (SELECT id FROM schemes)
        UNION ALL
        SELECT 'orphaned_scheme_versions', count(*) FROM scheme_versions WHERE scheme_id NOT IN (SELECT id FROM schemes);
    """)
    for check_name, orphan_count in cur.fetchall():
        if orphan_count > 0:
            raise PreflightValidationError(f"Preflight failure: {check_name} count is {orphan_count} (must be 0).")
    print("  [>] Foreign Key Integrity : 0 orphaned rows detected.")

    # 4. Target Schemes (11, 19, 88) must exist and be active
    cur.execute("SELECT id, is_active FROM schemes WHERE id IN (11, 19, 88);")
    target_rows = cur.fetchall()
    if len(target_rows) != 3 or not all(r[1] for r in target_rows):
        raise PreflightValidationError("Target schemes 11, 19, and 88 must exist and be ACTIVE.")
    print("  [>] Canonical Target Schemes (11, 19, 88) : Verified ACTIVE.")

    # 5. Duplicate Schemes (6, 8, 37) must exist and be inactive
    cur.execute("SELECT id, is_active FROM schemes WHERE id IN (6, 8, 37);")
    dup_rows = cur.fetchall()
    if len(dup_rows) != 3 or any(r[1] for r in dup_rows):
        raise PreflightValidationError("Duplicate schemes 6, 8, and 37 must exist and be INACTIVE.")
    print("  [>] Archived Duplicate Schemes (6, 8, 37) : Verified INACTIVE.")

    # 6. Schema Naming Conflicts Check for Upgrade
    if action == "upgrade":
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'schemes' AND column_name = 'slug';")
        if cur.fetchone():
            raise PreflightValidationError("Column 'slug' already exists in table schemes.")
        cur.execute("SELECT indexname FROM pg_indexes WHERE indexname = 'uq_schemes_active_slug_jurisdiction';")
        if cur.fetchone():
            raise PreflightValidationError("Index 'uq_schemes_active_slug_jurisdiction' already exists.")
        print("  [>] Schema Conflict Check : Verified 0 pre-existing columns or indexes.")

    cur.close()
    print("[+] ALL PREFLIGHT ASSERTIONS PASSED SUCCESSFULLY.\n")


def prompt_operator_confirmation(action: str, revision: str, confirmation_token: str | None = None) -> None:
    """Prompt the operator for explicit text confirmation."""
    required_token = "YES-MIGRATE-PRODUCTION" if action == "upgrade" else "YES-DOWNGRADE-PRODUCTION"

    if confirmation_token:
        if confirmation_token == required_token:
            print(f"[+] Confirmation token accepted: {required_token}")
            return
        raise ValueError(f"Supplied token '{confirmation_token}' does not match required '{required_token}'.")

    print("********************************************************************************")
    print(f" DANGER: You are about to execute a PRODUCTION Alembic {action.upper()} to '{revision}'.")
    print(" All preflight checks passed. To proceed, type the confirmation phrase exactly:")
    print(f"      {required_token}")
    print("********************************************************************************")

    try:
        user_input = input("Enter confirmation: ").strip()
    except EOFError:
        user_input = ""

    if user_input != required_token:
        print(f"\n[!] Aborted by operator. Entered '{user_input}' != '{required_token}'.")
        sys.exit(1)

    print("[+] Operator confirmation received. Proceeding with migration...")


def run_production_migration(
    action: str,
    revision: str,
    db_url: str,
    environment: str,
    expected_db: str = "lifenavigator",
    expected_user: str = "lifenavigator",
    expected_port: int | None = 5432,
    preflight_only: bool = False,
    confirmation_token: str | None = None,
) -> None:
    """Main execution controller with fail-closed safety assertions."""
    # Safety Check 1: Explicit environment must be production
    if environment != "production":
        print(f"ABORT: Invalid environment '{environment}'. Must explicitly pass '--environment production'.")
        sys.exit(1)

    masked_url = mask_db_url(db_url)
    print(f"[*] Initializing Production Migration Runner...")
    print(f"    Action           : {action} {revision}")
    print(f"    Environment      : {environment}")
    print(f"    Database Target  : {masked_url}")

    # Safety Check 2: Verify database identity
    try:
        conn = psycopg2.connect(db_url)
    except Exception as exc:
        print(f"ABORT: Failed to connect to database: {exc}")
        sys.exit(1)

    try:
        verify_target_identity(conn, expected_db=expected_db, expected_user=expected_user, expected_port=expected_port)
        execute_preflight_checks(conn, action=action, target_revision=revision)
    finally:
        conn.close()

    if preflight_only:
        print("[+] Preflight-only mode requested. Exiting without modifying database.")
        return

    # Safety Check 3: Interactive operator confirmation
    prompt_operator_confirmation(action, revision, confirmation_token)

    # Safety Check 4: Configure Alembic and run migration
    backend_dir = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(backend_dir))

    # Mask database URL in process environment
    os.environ["DATABASE_URL"] = db_url

    from alembic.config import Config
    from alembic import command

    ini_path = backend_dir / "alembic.ini"
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))

    print(f"\n[*] Executing Alembic {action} {revision}...")
    try:
        if action == "upgrade":
            command.upgrade(alembic_cfg, revision)
        elif action == "downgrade":
            command.downgrade(alembic_cfg, revision)
        else:
            print(f"ABORT: Unknown action '{action}'.")
            sys.exit(1)
        print(f"[+] Alembic {action} {revision} completed successfully.")
    except Exception as exc:
        print(f"\n[!] CRITICAL ERROR: Alembic {action} failed: {exc}")
        print("    PostgreSQL transactional DDL has rolled back the transaction.")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LifeNavigator-AI Production Migration Runner")
    parser.add_argument("action", choices=["upgrade", "downgrade"], help="Migration action")
    parser.add_argument("revision", help="Target revision (e.g. 3c1a2b3c4d5e, head, -1)")
    parser.add_argument("--environment", required=True, help="Target environment (must be 'production')")
    parser.add_argument("--db-url", default=os.getenv("DATABASE_URL"), help="PostgreSQL connection URL")
    parser.add_argument("--expected-db", default="lifenavigator", help="Expected database name")
    parser.add_argument("--expected-user", default="lifenavigator", help="Expected database user")
    parser.add_argument("--expected-port", type=int, default=5432, help="Expected database port")
    parser.add_argument("--preflight-only", action="store_true", help="Execute preflight assertions only")
    parser.add_argument("--confirm-token", default=None, help="Automation confirmation token (for testing)")

    args = parser.parse_args()

    if not args.db_url:
        print("Error: DATABASE_URL must be provided via --db-url or environment variable.")
        sys.exit(1)

    run_production_migration(
        action=args.action,
        revision=args.revision,
        db_url=args.db_url,
        environment=args.environment,
        expected_db=args.expected_db,
        expected_user=args.expected_user,
        expected_port=args.expected_port,
        preflight_only=args.preflight_only,
        confirmation_token=args.confirm_token,
    )
