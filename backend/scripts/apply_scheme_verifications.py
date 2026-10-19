"""Apply Evidence-Supported Eligibility Rules and Verification Statuses.

Targets 5 priority schemes:
- Scheme 11: PM-KISAN
- Scheme 25: PMFBY
- Scheme 30: PM-USP CSSS
- Scheme 55: AICTE Pragati Scholarship
- Scheme 116: Pudhumai Penn

Ensures strict fail-closed criteria, transactional execution, and reversibility.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure backend modules can be imported from root or backend directory
current_file = Path(__file__).resolve()
for parent in [current_file.parents[1], current_file.parents[1] / "backend", current_file.parents[0]]:
    if parent.exists() and str(parent) not in sys.path:
        sys.path.insert(0, str(parent))

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.scheme import Scheme
from app.models.eligibility_rule import EligibilityRule
from app.models.scheme_source import SchemeVersion

TARGET_SCHEME_IDS = [11, 25, 30, 55, 116]

VERIFIED_RULES_SPEC = {
    11: [
        # PM-KISAN: Rules 8 & 9 exist, ensure active, group_id=1, AND
        {"field_name": "is_farmer", "operator": "equals", "value": "true", "group_id": 1, "logical_operator": "AND", "version_id": 33},
        {"field_name": "land_ownership", "operator": "equals", "value": "true", "group_id": 1, "logical_operator": "AND", "version_id": 33},
    ],
    25: [
        # PMFBY: Farmer cultivating notified crop
        {"field_name": "is_farmer", "operator": "equals", "value": "true", "group_id": 1, "logical_operator": "AND", "version_id": 34},
    ],
    30: [
        # PM-USP CSSS: Student with family income <= 4.5 lakh
        {"field_name": "employment_status", "operator": "equals", "value": "Student", "group_id": 1, "logical_operator": "AND", "version_id": 50},
        {"field_name": "annual_income", "operator": "lte", "value": "450000", "group_id": 1, "logical_operator": "AND", "version_id": 50},
    ],
    55: [
        # AICTE Pragati: Female student with family income <= 8 lakh
        {"field_name": "gender", "operator": "equals", "value": "Female", "group_id": 1, "logical_operator": "AND", "version_id": 57},
        {"field_name": "employment_status", "operator": "equals", "value": "Student", "group_id": 1, "logical_operator": "AND", "version_id": 57},
        {"field_name": "annual_income", "operator": "lte", "value": "800000", "group_id": 1, "logical_operator": "AND", "version_id": 57},
    ],
    116: [
        # Pudhumai Penn: Female student residing in Tamil Nadu
        {"field_name": "state", "operator": "equals", "value": "Tamil Nadu", "group_id": 1, "logical_operator": "AND", "version_id": 136},
        {"field_name": "gender", "operator": "equals", "value": "Female", "group_id": 1, "logical_operator": "AND", "version_id": 136},
        {"field_name": "employment_status", "operator": "equals", "value": "Student", "group_id": 1, "logical_operator": "AND", "version_id": 136},
    ],
}


def apply_verification(db_url: str, apply: bool = False):
    engine = create_engine(db_url)
    mode = "APPLY (COMMIT)" if apply else "DRY-RUN (ROLLBACK)"
    print(f"\n=======================================================")
    print(f"Executing Scheme Verification in mode: {mode}")
    print(f"Target DB: {db_url.split('@')[-1]}")
    print(f"=======================================================")

    with Session(engine) as session:
        # Check current statuses
        schemes = session.query(Scheme).filter(Scheme.id.in_(TARGET_SCHEME_IDS)).order_by(Scheme.id).all()
        print(f"\n--- Current Scheme Statuses ({len(schemes)} found) ---")
        for s in schemes:
            print(f"Scheme {s.id:3d}: {s.name[:50]} | Eligibility Status: {s.eligibility_verification_status}")

        existing_rules = session.query(EligibilityRule).filter(EligibilityRule.scheme_id.in_(TARGET_SCHEME_IDS)).order_by(EligibilityRule.scheme_id, EligibilityRule.id).all()
        print(f"\n--- Existing Rules for Target Schemes ({len(existing_rules)} found) ---")
        for r in existing_rules:
            print(f"Rule {r.id:2d}: Scheme {r.scheme_id:3d} | {r.field_name} {r.operator} {r.value} | Group: {r.group_id} ({r.logical_operator})")

        # Atomic modification
        # 1. Update schemes eligibility_verification_status
        for s in schemes:
            s.eligibility_verification_status = "verified"
            session.add(s)

        # 2. Update existing rules for Scheme 11
        for r in existing_rules:
            if r.scheme_id == 11:
                r.group_id = 1
                r.logical_operator = "AND"
                r.is_active = True
                r.source_version_id = 33
                session.add(r)

        # 3. Add new rules for Schemes 25, 30, 55, 116
        for scheme_id in [25, 30, 55, 116]:
            current_rule_fields = {r.field_name for r in existing_rules if r.scheme_id == scheme_id}
            specs = VERIFIED_RULES_SPEC[scheme_id]
            for spec in specs:
                if spec["field_name"] not in current_rule_fields:
                    new_rule = EligibilityRule(
                        scheme_id=scheme_id,
                        field_name=spec["field_name"],
                        operator=spec["operator"],
                        value=spec["value"],
                        group_id=spec["group_id"],
                        logical_operator=spec["logical_operator"],
                        is_active=True,
                        source_version_id=spec["version_id"],
                    )
                    session.add(new_rule)
                    print(f"  [+] Adding rule for Scheme {scheme_id}: {spec['field_name']} {spec['operator']} {spec['value']}")

        if not apply:
            print("\n[!] Dry run complete. Rolling back transaction.")
            session.rollback()
            return

        print("\n[+] Applying changes and committing transaction...")
        session.commit()

    # Post-check if applied
    if apply:
        with Session(engine) as session:
            verified_count = session.query(Scheme).filter(Scheme.eligibility_verification_status == "verified").count()
            unverified_count = session.query(Scheme).filter(Scheme.eligibility_verification_status == "unverified").count()
            total_active = session.query(Scheme).filter(Scheme.is_active == True).count()
            total_rules = session.query(EligibilityRule).count()
            target_rules = session.query(EligibilityRule).filter(EligibilityRule.scheme_id.in_(TARGET_SCHEME_IDS)).count()

            print(f"\n=== Verification State After Apply ===")
            print(f"Total Active Schemes: {total_active}")
            print(f"Verified Schemes: {verified_count} (Expected: 5)")
            print(f"Unverified Schemes: {unverified_count} (Expected: {total_active - 5})")
            print(f"Total Rules in DB: {total_rules}")
            print(f"Rules for Target Schemes: {target_rules} (Expected: 11)")

            for sid in TARGET_SCHEME_IDS:
                sch = session.get(Scheme, sid)
                active_rules = [r for r in sch.eligibility_rules if r.is_active]
                print(f"\nScheme {sid} ({sch.name[:45]}):")
                print(f"  Eligibility Verification Status: {sch.eligibility_verification_status}")
                print(f"  Active Rules: {len(active_rules)}")
                for r in active_rules:
                    print(f"    - {r.field_name} {r.operator} '{r.value}' (group {r.group_id}, {r.logical_operator})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply scheme eligibility verifications")
    parser.add_argument("--apply", action="store_true", help="Commit changes to database")
    parser.add_argument("--db", type=str, default="native", choices=["native", "test", "both", "current"], help="Target database: native (5432), test (5433), both, or current (settings.DATABASE_URL)")
    args = parser.parse_args()

    native_url = settings.DATABASE_URL
    test_url = "postgresql+psycopg://test_runner:test_isolation_pw_2026@localhost:5433/lifenavigator_stage3c_test"

    targets = []
    if args.db == "current":
        targets.append(("Current (settings.DATABASE_URL)", settings.DATABASE_URL))
    else:
        if args.db in ["native", "both"]:
            targets.append(("Native (5432)", native_url))
        if args.db in ["test", "both"]:
            targets.append(("Test (5433)", test_url))

    for label, url in targets:
        apply_verification(url, apply=args.apply)
