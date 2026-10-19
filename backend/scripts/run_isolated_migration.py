"""Run Alembic migrations against the isolated test database."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
import psycopg2

def run_isolated_migration(action: str, revision: str, db_url: str):
    # Mandatory Safety Verification: Check database identity before doing anything
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute("SELECT current_database(), current_user, inet_server_port();")
    db_name, db_user, db_port = cur.fetchone()
    cur.close()
    conn.close()

    print("=== ISOLATED MIGRATION RUNNER ===")
    print(f"Target Database: {db_name}")
    print(f"Target User:     {db_user}")
    print(f"Target Port:     {db_port}")
    print(f"Action:          {action} {revision}")

    # Safety assertion: Must be the test database
    if "test" not in db_name.lower():
        print(f"ABORT: Target database '{db_name}' does not contain 'test'. Refusing to migrate non-test database!")
        sys.exit(1)

    # Set environment variables for Alembic / Pydantic settings
    os.environ["DATABASE_URL"] = db_url

    backend_dir = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(backend_dir))

    from alembic.config import Config
    from alembic import command

    ini_path = backend_dir / "alembic.ini"
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))

    if action == "upgrade":
        print(f"Executing alembic upgrade {revision}...")
        command.upgrade(alembic_cfg, revision)
        print("Alembic upgrade completed successfully.")
    elif action == "downgrade":
        print(f"Executing alembic downgrade {revision}...")
        command.downgrade(alembic_cfg, revision)
        print("Alembic downgrade completed successfully.")
    else:
        print(f"Unknown action: {action}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run isolated Alembic migration.")
    parser.add_argument("action", choices=["upgrade", "downgrade"], help="Migration action")
    parser.add_argument("revision", help="Target revision (e.g. head, -1, 3c1a2b3c4d5e)")
    parser.add_argument("--db-url", required=True, help="Isolated test database URL")
    args = parser.parse_args()

    run_isolated_migration(args.action, args.revision, args.db_url)
