import sys
import json
import urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database.connection import SessionLocal
from app.models.scheme import Scheme
from sqlalchemy import func

print("=================================================================")
print("=== LIVE CATALOGUE AUDIT & RECONCILIATION ===")
print("=================================================================")

with SessionLocal() as db:
    total_db = db.query(func.count(Scheme.id)).scalar()
    unique_names = db.query(func.count(func.distinct(Scheme.name))).scalar()
    
    active_count = db.query(func.count(Scheme.id)).filter(Scheme.is_active == True).scalar()
    inactive_count = db.query(func.count(Scheme.id)).filter(Scheme.is_active == False).scalar()
    
    verified_count = db.query(func.count(Scheme.id)).filter(Scheme.verification_status == "verified").scalar()
    pending_count = db.query(func.count(Scheme.id)).filter(Scheme.verification_status == "pending").scalar()
    unverified_count = db.query(func.count(Scheme.id)).filter(Scheme.verification_status == "unverified").scalar()
    none_status_count = db.query(func.count(Scheme.id)).filter(Scheme.verification_status == None).scalar()

print(f"Total database schemes: {total_db}")
print(f"Unique scheme names: {unique_names}")
print(f"Operational breakdown: Active={active_count}, Inactive={inactive_count}")
print(f"Verification breakdown: Verified={verified_count}, Pending={pending_count}, Unverified={unverified_count}, None={none_status_count}")

# Check reference JSON
ref_json_path = BACKEND_DIR.parent / "data" / "schemes" / "scheme_catalogue_reference.json"
with open(ref_json_path, "r", encoding="utf-8") as f:
    ref_json = json.load(f)

ref_schemes = ref_json.get("schemes", [])
print(f"Reference JSON metadata: {ref_json.get('metadata')}")
print(f"Reference JSON schemes list length: {len(ref_schemes)}")
assert len(ref_schemes) == total_db, f"Mismatch: JSON has {len(ref_schemes)} records, DB has {total_db}"

# Check live API /api/schemes/search?active_only=false&limit=200
url_all = "http://127.0.0.1:8000/api/schemes/search?active_only=false&limit=200"
req_all = urllib.request.urlopen(url_all)
api_all = json.loads(req_all.read().decode("utf-8"))
api_all_schemes = api_all.get("results", [])
print(f"Live API (active_only=false, limit=200): {len(api_all_schemes)} schemes returned")
assert len(api_all_schemes) == total_db

# Check live API /api/schemes/search?active_only=true&limit=200 (Explore view default)
url_active = "http://127.0.0.1:8000/api/schemes/search?active_only=true&limit=200"
req_active = urllib.request.urlopen(url_active)
api_active = json.loads(req_active.read().decode("utf-8"))
api_active_schemes = api_active.get("results", [])
print(f"Live API (active_only=true, limit=200): {len(api_active_schemes)} schemes returned")
assert len(api_active_schemes) == active_count

# Check inactive schemes:
inactive_ids = [s["id"] for s in api_all_schemes if not s.get("is_active")]
print(f"Inactive schemes in API: {inactive_ids}")
for iid in inactive_ids:
    s_obj = next(s for s in api_all_schemes if s["id"] == iid)
    print(f"  - ID {s_obj['id']}: '{s_obj['name']}' (verification_status: {s_obj['verification_status']})")

print("\nAll catalogue counts reconciled 100% with live API and reports!")
