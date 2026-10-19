import sys
import json
from pathlib import Path
from datetime import datetime, date

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database.connection import engine
from sqlalchemy import text

BACKUP_DIR = BACKEND_DIR / "backend" / "backups" / "pg_backup_post_expansion"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

TABLES = [
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

def default_json(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return str(obj)

with engine.connect() as conn:
    for table in TABLES:
        # Dump all columns including vector embeddings (JSON array) for complete fidelity
        query = text(f"SELECT * FROM {table} ORDER BY 1")
        
        result = conn.execute(query)
        rows = [dict(row._mapping) for row in result]
        out_file = BACKUP_DIR / f"{table}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2, default=default_json, ensure_ascii=False)
        print(f"Backed up {len(rows)} rows from {table} -> {out_file.name}")

print(f"\nAll tables backed up successfully to: {BACKUP_DIR}")
