"""Restore the complete expanded catalogue and data from JSON backup into the database.

Safely populates tables only if empty (or skips existing rows), computes vector embeddings
deterministically for chunks, and resets PostgreSQL auto-increment sequences.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from sqlalchemy import text

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database.connection import engine
from app.services.embedding import get_embedding_provider

BACKUP_DIR = BACKEND_DIR / "backend" / "backups" / "pg_backup_post_expansion"

TABLE_ORDER = [
    "alembic_version",
    "users",
    "user_profiles",
    "scheme_sources",
    "schemes",
    "scheme_versions",
    "eligibility_rules",
    "scheme_documents",
    "scheme_document_chunks",
    "scheme_import_history",
]


def restore():
    print(f"Reading backup from: {BACKUP_DIR}")
    embedding_provider = get_embedding_provider()
    
    with engine.begin() as conn:
        for table in TABLE_ORDER:
            json_file = BACKUP_DIR / f"{table}.json"
            if not json_file.exists():
                print(f"Warning: {json_file.name} not found, skipping.")
                continue
            
            # Check current row count
            current_count = conn.execute(text(f"SELECT count(*) FROM {table}")).scalar()
            if current_count > 0:
                print(f"Table '{table}' already contains {current_count} rows. Skipping insert.")
                continue
            
            with open(json_file, "r", encoding="utf-8") as f:
                rows = json.load(f)
            
            if not rows:
                print(f"Table '{table}': 0 rows in backup.")
                continue
            
            # Prepare rows
            for r in rows:
                if table == "schemes":
                    if r.get("beneficiary_groups") is not None and not isinstance(r.get("beneficiary_groups"), str):
                        r["beneficiary_groups"] = json.dumps(r["beneficiary_groups"])
                elif table == "scheme_document_chunks":
                    if r.get("embedding") is not None:
                        if isinstance(r["embedding"], list):
                            r["embedding"] = json.dumps(r["embedding"])
                    else:
                        chunk_text = r.get("text", "")
                        r["embedding"] = json.dumps(embedding_provider.embed_text(chunk_text))
                elif table == "scheme_documents":
                    if r.get("metadata_json") is not None and not isinstance(r.get("metadata_json"), str):
                        r["metadata_json"] = json.dumps(r["metadata_json"])
                elif table == "scheme_versions":
                    if r.get("snapshot") is not None and not isinstance(r.get("snapshot"), str):
                        r["snapshot"] = json.dumps(r["snapshot"])
                elif table == "scheme_import_history":
                    if r.get("details") is not None and not isinstance(r.get("details"), str):
                        r["details"] = json.dumps(r["details"])

            # Bulk insert using SQLAlchemy text with bind params
            first = rows[0]
            columns = list(first.keys())
            col_names = ", ".join(columns)
            param_placeholders = ", ".join(f":{c}" for c in columns)
            insert_stmt = text(f"INSERT INTO {table} ({col_names}) VALUES ({param_placeholders})")
            
            conn.execute(insert_stmt, rows)
            print(f"Restored {len(rows)} rows into '{table}'.")

            # Update Postgres sequence
            try:
                conn.execute(text(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), coalesce(max(id), 1)) FROM {table}"))
            except Exception:
                pass

    print("\nDatabase restore complete!")


if __name__ == "__main__":
    restore()
