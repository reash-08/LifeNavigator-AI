import sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import json
from app.database.connection import SessionLocal
from app.models.scheme import Scheme
from app.services.scheme_sync import normalize_name

with open(BACKEND_DIR / "backend" / "backups" / "pg_backup_pre_expansion" / "schemes.json", "r", encoding="utf-8") as f:
    backup_schemes = json.load(f)

with SessionLocal() as db:
    current_schemes = db.query(Scheme).all()

backup_norm = {normalize_name(s["name"]): s for s in backup_schemes}
current_norm = {normalize_name(s.name): s for s in current_schemes}

pre_existing = []
newly_added = []
updated = []

for s in current_schemes:
    n = normalize_name(s.name)
    if n in backup_norm:
        orig = backup_norm[n]
        pre_existing.append((s, orig))
        # check if updated
        if s.verification_status != orig.get("verification_status") or s.benefit != orig.get("benefit"):
            updated.append((s, orig))
    else:
        newly_added.append(s)

print(f"Total current schemes in DB: {len(current_schemes)}")
print(f"Pre-existing schemes in backup: {len(backup_schemes)}")
print(f"Pre-existing matched in current DB: {len(pre_existing)}")
print(f"Updated among pre-existing: {len(updated)}")
print(f"Newly added unique schemes: {len(newly_added)}")

# Check if any backup scheme was removed
backup_not_in_current = [s for s in backup_schemes if normalize_name(s["name"]) not in current_norm]
print(f"Backup schemes removed/missing: {len(backup_not_in_current)}")

print("\nPre-existing schemes:")
for cur, orig in pre_existing:
    print(f"  Current ID {cur.id} | Orig ID {orig['id']} | {cur.name} | Status: {orig.get('verification_status')} -> {cur.verification_status}")
