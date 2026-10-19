"""Stage 3C Pre-Rollback and Post-Migration Manifest Export Script.

Exports a verified snapshot of scheme identity, slug, alias, and canonical link data
to ensure 100% data preservation during migration testing, downgrade, and recovery.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import psycopg2

def get_git_revision() -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL)
        return out.decode("utf-8").strip()
    except Exception:
        return "unknown"

def export_manifest(connection_url: str, output_path: Path | None = None) -> Path:
    conn = psycopg2.connect(connection_url)
    cur = conn.cursor()

    cur.execute("SELECT current_database(), current_user, inet_server_port();")
    db_name, db_user, db_port = cur.fetchone()
    print(f"Exporting manifest from DB: {db_name} | User: {db_user} | Port: {db_port}")

    cur.execute("""
        SELECT id, name, slug, state, is_active, aliases, canonical_scheme_id
        FROM schemes
        ORDER BY id;
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    records = []
    for r in rows:
        records.append({
            "id": r[0],
            "name": r[1],
            "slug": r[2],
            "jurisdiction": (r[3] or "CENTRAL").upper(),
            "is_active": r[4],
            "aliases": r[5] if isinstance(r[5], list) else (json.loads(r[5]) if r[5] else []),
            "canonical_scheme_id": r[6],
        })

    # Canonical serialization for checksum
    canonical_payload = json.dumps(records, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    payload_hash = sha256(canonical_payload.encode("utf-8")).hexdigest()

    manifest = {
        "schema_version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_revision(),
        "database": db_name,
        "total_records": len(records),
        "sha256": payload_hash,
        "records": records,
    }

    if output_path is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        repo_root = Path(__file__).resolve().parents[2]
        manifest_dir = repo_root / "backups" / "manifests"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        output_path = manifest_dir / f"stage3c_manifest_{timestamp}.json"
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Manifest successfully exported ({len(records)} records) to: {output_path}")
    print(f"Manifest SHA-256 Checksum: {payload_hash}")
    return output_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export Stage 3C scheme identity manifest.")
    parser.add_argument("--db-url", default=os.getenv("DATABASE_URL"), help="PostgreSQL connection URL")
    parser.add_argument("--output", default=None, help="Output file path for manifest JSON")
    args = parser.parse_args()

    if not args.db_url:
        print("Error: DATABASE_URL must be provided via --db-url or environment variable.")
        sys.exit(1)

    out_p = Path(args.output) if args.output else None
    export_manifest(args.db_url, out_p)
