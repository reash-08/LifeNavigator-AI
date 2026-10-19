import sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import json
import csv
from collections import Counter
from app.database.connection import SessionLocal
from app.models.scheme import Scheme
from app.models.scheme_source import SchemeSource, SchemeVersion
from app.models.scheme_document import SchemeDocument, SchemeDocumentChunk

REPO_DIR = BACKEND_DIR.parent

# 1. Load backup schemes
backup_path = BACKEND_DIR / "backend" / "backups" / "pg_backup_pre_expansion" / "schemes.json"
backup_schemes = []
if backup_path.exists():
    with open(backup_path, "r", encoding="utf-8") as f:
        backup_schemes = json.load(f)
print(f"Backup schemes count: {len(backup_schemes)}")
backup_ids = {s["id"]: s for s in backup_schemes}
backup_names = {s["name"]: s for s in backup_schemes}

# 2. Load starter.json
starter_path = REPO_DIR / "data" / "schemes" / "starter.json"
with open(starter_path, "r", encoding="utf-8") as f:
    starter_data = json.load(f)
starter_schemes = starter_data["schemes"]
print(f"starter.json schemes count: {len(starter_schemes)}")
starter_names = {s["name"]: s for s in starter_schemes}

# 3. Load audit_verified_schemes.json
audit_json_path = REPO_DIR / "data" / "schemes" / "audit_verified_schemes.json"
with open(audit_json_path, "r", encoding="utf-8") as f:
    audit_data = json.load(f)
audit_schemes = audit_data["schemes"]
print(f"audit_verified_schemes.json count: {len(audit_schemes)}")
audit_names = {s["name"]: s for s in audit_schemes}

# 4. Load audit_verified_schemes.csv
audit_csv_path = REPO_DIR / "data" / "schemes" / "audit_verified_schemes.csv"
with open(audit_csv_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    csv_schemes = list(reader)
print(f"audit_verified_schemes.csv count: {len(csv_schemes)}")
csv_names = {s["name"]: s for s in csv_schemes}

# 5. Load DB schemes
with SessionLocal() as db:
    db_schemes = db.query(Scheme).all()
    print(f"Current PostgreSQL schemes count: {len(db_schemes)}")
    db_ids = {s.id: s for s in db_schemes}
    db_names = {s.name: s for s in db_schemes}

    # Count statuses in DB
    db_status_counts = Counter(s.verification_status for s in db_schemes)
    db_active_counts = Counter(s.is_active for s in db_schemes)
    print(f"DB verification statuses: {dict(db_status_counts)}")
    print(f"DB active statuses: {dict(db_active_counts)}")

    # Starter status counts
    starter_status_counts = Counter(s.get("verification_status") for s in starter_schemes)
    starter_active_counts = Counter(s.get("is_active") for s in starter_schemes)
    print(f"starter.json verification statuses: {dict(starter_status_counts)}")
    print(f"starter.json active statuses: {dict(starter_active_counts)}")

    # Check differences
    db_not_in_starter = [s for s in db_schemes if s.name not in starter_names]
    print(f"\nDB schemes NOT in starter.json ({len(db_not_in_starter)}):")
    for s in db_not_in_starter:
        print(f"  ID {s.id}: '{s.name}' | status={s.verification_status} | active={s.is_active} | level={s.government_level} | source_id={s.source_id}")

    starter_not_in_db = [s for s in starter_schemes if s["name"] not in db_names]
    print(f"\nstarter.json schemes NOT in DB ({len(starter_not_in_db)}):")
    for s in starter_not_in_db:
        print(f"  '{s['name']}'")

    # Check verified counts
    starter_verified = [s for s in starter_schemes if s.get("verification_status") == "verified"]
    db_verified = [s for s in db_schemes if s.verification_status == "verified"]
    print(f"\nVerified count: starter.json={len(starter_verified)}, DB={len(db_verified)}")
    
    # Why is there 1 extra verified in DB?
    extra_verified_in_db = [s for s in db_verified if s.name not in {x["name"]: x for x in starter_verified}]
    print(f"Extra verified schemes in DB ({len(extra_verified_in_db)}):")
    for s in extra_verified_in_db:
        print(f"  ID {s.id}: '{s.name}' | status={s.verification_status} | in starter?={s.name in starter_names}")
