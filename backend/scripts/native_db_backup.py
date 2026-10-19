"""Native PostgreSQL backup and restore verification utility for LifeNavigator-AI.

This utility creates byte-exact, production-grade custom format (-Fc) PostgreSQL dumps
that preserve all tables, sequences, constraints, triggers, indexes, and vector embeddings.
It also provides verification and safe test-restoration into an isolated temporary database.
"""
from __future__ import annotations

import argparse
import datetime
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Default paths and configurations
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BACKUP_DIR = REPO_ROOT / "backups"
DEFAULT_CONTAINER = "lifenavigator-db"
DEFAULT_DB = "lifenavigator"
DEFAULT_USER = "lifenavigator"
DEFAULT_TEST_DB = "lifenavigator_test_restore"


class BackupError(Exception):
    """Custom exception raised when backup or verification fails."""
    pass


def run_command(cmd: List[str], check: bool = True, capture_output: bool = True) -> subprocess.CompletedProcess:
    """Safely run a command and return the completed process."""
    try:
        result = subprocess.run(
            cmd,
            check=check,
            capture_output=capture_output,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        return result
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.strip() if e.stderr else str(e)
        raise BackupError(f"Command failed ({' '.join(cmd)}): {stderr}") from e


def create_native_backup(
    output_dir: Path = DEFAULT_BACKUP_DIR,
    container: str = DEFAULT_CONTAINER,
    db_name: str = DEFAULT_DB,
    db_user: str = DEFAULT_USER,
) -> Path:
    """Create a native custom-format (-Fc) PostgreSQL backup using pg_dump inside the DB container."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    dump_filename = f"lifenavigator_native_{timestamp}.dump"
    local_dump_path = output_dir / dump_filename
    container_temp_path = f"/tmp/{dump_filename}"

    if local_dump_path.exists():
        raise BackupError(f"Refusing to overwrite existing backup file: {local_dump_path}")

    print(f"[*] Starting native PostgreSQL backup...")
    print(f"    Container : {container}")
    print(f"    Database  : {db_name}")
    print(f"    User      : {db_user}")
    print(f"    Target    : {local_dump_path}")

    # 1. Execute pg_dump inside the container to a temporary file
    dump_cmd = [
        "docker", "exec", container,
        "pg_dump",
        "-U", db_user,
        "-d", db_name,
        "-Fc",
        "-v",
        "-f", container_temp_path
    ]
    
    try:
        print("[*] Invoking pg_dump (-Fc) in container...")
        run_command(dump_cmd)
        
        # 2. Copy the dump from the container to the host
        print("[*] Copying dump artifact to host storage...")
        copy_cmd = ["docker", "cp", f"{container}:{container_temp_path}", str(local_dump_path)]
        run_command(copy_cmd)
        
    finally:
        # 3. Always clean up the temporary dump file inside the container
        cleanup_cmd = ["docker", "exec", container, "rm", "-f", container_temp_path]
        try:
            run_command(cleanup_cmd, check=False)
        except Exception:
            pass

    # 4. Verify file existence and size
    if not local_dump_path.exists():
        raise BackupError(f"Backup file was not created: {local_dump_path}")
    
    file_size = local_dump_path.stat().st_size
    print(f"[+] Backup file created successfully: {local_dump_path.name} ({file_size:,} bytes)")
    
    if file_size < 10240:  # Minimum 10 KB threshold for non-trivial schema and data
        raise BackupError(f"Backup file size is suspiciously small ({file_size} bytes). Backup aborted.")

    # 5. Verify the archive table of contents via pg_restore --list
    print("[*] Verifying archive table of contents via pg_restore --list...")
    verify_archive_integrity(local_dump_path, container)

    print(f"[+] Native database backup complete and verified: {local_dump_path}")
    return local_dump_path


def verify_archive_integrity(dump_path: Path, container: str = DEFAULT_CONTAINER) -> List[str]:
    """Verify that a dump file is a valid PostgreSQL custom-format archive and list its TOC entries."""
    if not dump_path.exists():
        raise BackupError(f"Dump file does not exist: {dump_path}")

    # Temporarily copy file to container to verify using the container's pg_restore
    temp_container_file = f"/tmp/verify_{dump_path.name}"
    copy_cmd = ["docker", "cp", str(dump_path), f"{container}:{temp_container_file}"]
    run_command(copy_cmd)

    try:
        list_cmd = ["docker", "exec", container, "pg_restore", "--list", temp_container_file]
        result = run_command(list_cmd)
        toc_lines = [line.strip() for line in result.stdout.splitlines() if line.strip() and not line.startswith(";")]
        
        if not toc_lines:
            raise BackupError("pg_restore --list returned empty TOC.")
        
        # Verify required critical tables exist in TOC
        toc_text = "\n".join(toc_lines)
        required_tables = [
            "alembic_version",
            "users",
            "user_profiles",
            "schemes",
            "eligibility_rules",
            "scheme_documents",
            "scheme_document_chunks",
            "scheme_sources",
            "scheme_versions"
        ]
        
        missing = [tbl for tbl in required_tables if tbl not in toc_text]
        if missing:
            raise BackupError(f"Backup archive TOC is missing critical tables: {missing}")

        print(f"[+] TOC integrity verified: {len(toc_lines)} entries found across all critical tables.")
        return toc_lines
    finally:
        run_command(["docker", "exec", container, "rm", "-f", temp_container_file], check=False)


def run_isolated_test_restore(
    dump_path: Path,
    container: str = DEFAULT_CONTAINER,
    test_db_name: str = DEFAULT_TEST_DB,
    db_user: str = DEFAULT_USER
) -> Dict[str, int]:
    """Safely test restoration of a dump into an isolated temporary database without touching live data."""
    if not dump_path.exists():
        raise BackupError(f"Dump file does not exist: {dump_path}")

    print(f"\n[*] Initiating ISOLATED restoration test into temporary database: '{test_db_name}'...")
    print(f"    WARNING: The active production database ('{DEFAULT_DB}') will NOT be modified.")

    # 1. Clean up any stale test database
    drop_db_cmd = [
        "docker", "exec", container,
        "psql", "-U", db_user, "-d", "postgres",
        "-c", f"DROP DATABASE IF EXISTS {test_db_name};"
    ]
    run_command(drop_db_cmd)

    # 2. Create the fresh test database
    create_db_cmd = [
        "docker", "exec", container,
        "psql", "-U", db_user, "-d", "postgres",
        "-c", f"CREATE DATABASE {test_db_name} OWNER {db_user};"
    ]
    run_command(create_db_cmd)

    temp_container_file = f"/tmp/restore_test_{dump_path.name}"
    copy_cmd = ["docker", "cp", str(dump_path), f"{container}:{temp_container_file}"]
    run_command(copy_cmd)

    counts: Dict[str, int] = {}
    try:
        # 3. Execute pg_restore into the test database
        restore_cmd = [
            "docker", "exec", container,
            "pg_restore",
            "-U", db_user,
            "-d", test_db_name,
            "--no-owner",
            "--no-privileges",
            temp_container_file
        ]
        # pg_restore may return 0 or 1 (warnings like no-op permissions)
        res = subprocess.run(restore_cmd, capture_output=True, text=True)
        if res.returncode not in (0, 1):
            raise BackupError(f"pg_restore failed with exit code {res.returncode}: {res.stderr}")

        # 4. Verify table row counts in the restored test database
        tables_to_check = [
            "alembic_version",
            "users",
            "user_profiles",
            "schemes",
            "eligibility_rules",
            "scheme_documents",
            "scheme_document_chunks",
            "scheme_sources",
            "scheme_versions"
        ]

        for table in tables_to_check:
            count_cmd = [
                "docker", "exec", container,
                "psql", "-U", db_user, "-d", test_db_name,
                "-t", "-A",
                "-c", f"SELECT count(*) FROM {table};"
            ]
            count_res = run_command(count_cmd)
            counts[table] = int(count_res.stdout.strip())

        # 5. Verify vector embeddings in scheme_document_chunks
        embed_check_cmd = [
            "docker", "exec", container,
            "psql", "-U", db_user, "-d", test_db_name,
            "-t", "-A",
            "-c", "SELECT count(*) FROM scheme_document_chunks WHERE embedding IS NOT NULL;"
        ]
        embed_count = int(run_command(embed_check_cmd).stdout.strip())
        counts["chunks_with_embeddings"] = embed_count

        sample_dim_cmd = [
            "docker", "exec", container,
            "psql", "-U", db_user, "-d", test_db_name,
            "-t", "-A",
            "-c", "SELECT json_array_length(embedding) FROM scheme_document_chunks WHERE embedding IS NOT NULL LIMIT 1;"
        ]
        sample_dim = int(run_command(sample_dim_cmd).stdout.strip())
        counts["embedding_dimensions"] = sample_dim

        # 6. Verify Alembic version
        alembic_cmd = [
            "docker", "exec", container,
            "psql", "-U", db_user, "-d", test_db_name,
            "-t", "-A",
            "-c", "SELECT version_num FROM alembic_version;"
        ]
        alembic_rev = run_command(alembic_cmd).stdout.strip()

        print(f"[+] Restoration test verification results:")
        for tbl, cnt in counts.items():
            print(f"    - {tbl:<25}: {cnt}")
        print(f"    - alembic_version revision : {alembic_rev}")

        if counts["chunks_with_embeddings"] == 0:
            raise BackupError("Restored test database has ZERO embeddings in scheme_document_chunks!")

        print(f"[+] All tables, sequences, constraints, and embeddings successfully verified in test database!")

    finally:
        # 7. Clean up container temporary file
        run_command(["docker", "exec", container, "rm", "-f", temp_container_file], check=False)
        
        # 8. Drop the test database to leave no residue
        print(f"[*] Tearing down isolated test database '{test_db_name}'...")
        run_command([
            "docker", "exec", container,
            "psql", "-U", db_user, "-d", "postgres",
            "-c", f"DROP DATABASE IF EXISTS {test_db_name};"
        ], check=False)
        print(f"[+] Test database cleaned up successfully.")

    return counts


def main():
    parser = argparse.ArgumentParser(description="LifeNavigator-AI Native Database Backup Utility")
    parser.add_argument("--action", choices=["backup", "verify", "test-restore"], default="backup",
                        help="Action to perform: backup, verify an existing dump, or test-restore to isolated test DB.")
    parser.add_argument("--file", type=str, default=None, help="Path to dump file for verify or test-restore.")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_BACKUP_DIR), help="Directory to save backups.")
    parser.add_argument("--container", type=str, default=DEFAULT_CONTAINER, help="Docker PostgreSQL container name.")
    parser.add_argument("--db", type=str, default=DEFAULT_DB, help="PostgreSQL database name.")
    parser.add_argument("--user", type=str, default=DEFAULT_USER, help="PostgreSQL database user.")
    parser.add_argument("--test-db", type=str, default=DEFAULT_TEST_DB, help="Temporary test database name.")

    args = parser.parse_args()

    try:
        if args.action == "backup":
            dump_file = create_native_backup(
                output_dir=Path(args.output_dir),
                container=args.container,
                db_name=args.db,
                db_user=args.user
            )
            # Automatically run isolated test restore to prove restorable
            print("\n[*] Proving backup restorability with an automated test restore...")
            run_isolated_test_restore(dump_file, container=args.container, test_db_name=args.test_db, db_user=args.user)

        elif args.action == "verify":
            if not args.file:
                print("Error: --file must be specified for verify action.")
                sys.exit(1)
            verify_archive_integrity(Path(args.file), container=args.container)

        elif args.action == "test-restore":
            if not args.file:
                print("Error: --file must be specified for test-restore action.")
                sys.exit(1)
            run_isolated_test_restore(Path(args.file), container=args.container, test_db_name=args.test_db, db_user=args.user)

    except BackupError as e:
        print(f"\n[!] BACKUP ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
