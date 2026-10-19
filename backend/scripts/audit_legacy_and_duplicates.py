import sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database.connection import SessionLocal
from app.models.scheme import Scheme
from app.models.eligibility_rule import EligibilityRule
from app.models.scheme_source import SchemeVersion
from app.models.scheme_document import SchemeDocument

target_ids = [6, 11, 8, 19, 37, 71, 9, 10, 14]

with SessionLocal() as db:
    print("=== AUDIT OF DUPLICATE PAIRS AND LEGACY FIXTURES ===")
    for sid in target_ids:
        s = db.get(Scheme, sid)
        if not s:
            print(f"Scheme ID {sid}: NOT FOUND")
            continue
        rules = db.query(EligibilityRule).filter_by(scheme_id=sid).count()
        active_rules = db.query(EligibilityRule).filter_by(scheme_id=sid, is_active=True).count()
        versions = db.query(SchemeVersion).filter_by(scheme_id=sid).count()
        docs = db.query(SchemeDocument).filter_by(scheme_id=sid).count()
        print(f"\nScheme ID {s.id}: '{s.name}'")
        print(f"  Verification Status: {s.verification_status} | Active: {s.is_active}")
        print(f"  Source URL: {s.source_url} | Source ID: {s.source_id}")
        print(f"  Category: {s.category} | State: {s.state}")
        print(f"  Dependencies -> Rules: {rules} ({active_rules} active) | Versions: {versions} | Docs: {docs}")
