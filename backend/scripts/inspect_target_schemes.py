"""Inspect current baseline data for the 5 target schemes."""
import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database.connection import SessionLocal
from app.models.scheme import Scheme
from app.models.scheme_source import SchemeSource
from app.models.eligibility_rule import EligibilityRule

db = SessionLocal()
target_ids = [116, 30, 55, 11, 25]
schemes = db.query(Scheme).filter(Scheme.id.in_(target_ids)).order_by(Scheme.id).all()

print(f"Found {len(schemes)} target schemes:")
for s in schemes:
    rules = db.query(EligibilityRule).filter(EligibilityRule.scheme_id == s.id).all()
    print("=" * 70)
    print(f"ID: {s.id} | Name: {s.name}")
    print(f"Ministry: {s.ministry} | Department: {s.department}")
    print(f"Category: {s.category} | Subcategory: {s.subcategory} | State: {s.state}")
    print(f"Beneficiary Groups: {s.beneficiary_groups}")
    print(f"Verification Status: {s.verification_status}")
    print(f"Eligibility Verification Status: {s.eligibility_verification_status}")
    print(f"Source ID: {s.source_id} | Source Name: {s.source_name}")
    print(f"Source URL: {s.source_url}")
    print(f"Application URL: {s.application_url}")
    print(f"Min Age: {s.min_age} | Max Age: {s.max_age} | Education: {s.education}")
    print(f"Employment Status: {s.employment_status} | Max Income: {s.max_annual_income}")
    print(f"Active Rules Count: {len(rules)}")
    for r in rules:
        print(f"   Rule ID {r.id}: field={r.field_name}, op={r.operator}, val={r.value}, group={r.group_id}, logic={r.logical_operator}, active={r.is_active}")
    print(f"Required Documents: {s.required_documents}")
    print(f"Application Process: {s.application_process}")

db.close()
