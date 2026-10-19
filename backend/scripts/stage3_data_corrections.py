"""Stage 3 Data Corrections Script for LifeNavigator-AI.

This script safely plans and prepares database corrections for audited issues:
1. PM-KISAN: Transfers eligibility rules 8 & 9 from legacy scheme 6 to canonical verified scheme 11; archives scheme 6.
2. PMAY-U: Transfers eligibility rules 12, 13 & 14 from legacy scheme 8 to canonical verified scheme 19; archives scheme 8.
3. PMFME: Archives redundant pending duplicate scheme 37 while retaining canonical verified scheme 88.
4. Pudhumai Penn: Updates broken official typo URL across scheme 116, document 107, and source 128.
5. DAY-NRLM: Updates 404 URL across scheme 76, document 58, and source 79; updates category from 'Housing' to 'Employment & Skills'.
6. Swachh Bharat Grameen: Updates 404 URL across scheme 77, document 59, and source 80; updates category from 'Housing' to 'Health & Wellness'.

SAFETY GUARDS:
- Runs in DRY-RUN mode by default.
- Strict pre-condition assertions: verifies all IDs, names, current URLs, categories, and rule linkages before any modification.
- Aborts immediately if any pre-condition fails.
- Generates an explicit rollback manifest and matching rollback SQL.
- Wrapped in an atomic transaction.
- NO destructive deletes are used.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# Correction Specifications & Target Values
CORRECTIONS_SPEC = {
    "pm_kisan": {
        "legacy_scheme_id": 6,
        "canonical_scheme_id": 11,
        "expected_rule_ids": [8, 9],
        "archive_name_suffix": " [Archived Duplicate of #11]"
    },
    "pmay_u": {
        "legacy_scheme_id": 8,
        "canonical_scheme_id": 19,
        "expected_rule_ids": [12, 13, 14],
        "archive_name_suffix": " [Archived Duplicate of #19]"
    },
    "pmfme": {
        "duplicate_scheme_id": 37,
        "canonical_scheme_id": 88,
        "archive_name_suffix": " [Archived Duplicate of #88]"
    },
    "urls_and_categories": {
        "pudhumai_penn": {
            "scheme_id": 116,
            "document_id": 107,
            "source_id": 128,
            "expected_old_url": "https://pudhumaimaipen.tn.gov.in/",
            "new_url": "https://pudhumaipenn.tn.gov.in/"
        },
        "day_nrlm": {
            "scheme_id": 76,
            "document_id": 58,
            "source_id": 79,
            "expected_old_url": "https://nrlm.gov.in/",
            "new_url": "https://aajeevika.gov.in/",
            "expected_old_category": "Housing",
            "new_category": "Employment & Skills"
        },
        "sbm_g": {
            "scheme_id": 77,
            "document_id": 59,
            "source_id": 80,
            "expected_old_url": "https://sbm.gov.in/sbmgramin/",
            "new_url": "https://swachhbharatmission.ddws.gov.in/",
            "expected_old_category": "Housing",
            "new_category": "Health & Wellness"
        }
    }
}


class PreconditionFailure(Exception):
    """Raised when any database pre-condition check fails."""
    pass


def get_db_connection():
    """Import engine safely from app.database.connection."""
    from app.database.connection import engine
    return engine


def verify_preconditions(conn) -> Dict[str, Any]:
    """Verify that live database records precisely match audited expectations."""
    print("[*] Verifying pre-conditions against live database...")
    rollback_snapshot: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "schemes": {},
        "eligibility_rules": {},
        "scheme_documents": {},
        "scheme_sources": {}
    }

    # 1. PM-KISAN checks
    s6 = conn.execute(text("SELECT id, name, is_active, category, source_url, verification_status FROM schemes WHERE id = 6")).mappings().fetchone()
    if not s6 or not s6["is_active"] or "PM-KISAN" not in s6["name"]:
        raise PreconditionFailure(f"Scheme 6 pre-check failed: {s6}")
    rollback_snapshot["schemes"][6] = dict(s6)

    s11 = conn.execute(text("SELECT id, name, is_active, category, source_url, verification_status FROM schemes WHERE id = 11")).mappings().fetchone()
    if not s11 or not s11["is_active"] or "PM-KISAN" not in s11["name"]:
        raise PreconditionFailure(f"Scheme 11 pre-check failed: {s11}")
    rollback_snapshot["schemes"][11] = dict(s11)

    r_kisan = conn.execute(text("SELECT id, scheme_id, field_name FROM eligibility_rules WHERE id IN (8, 9)")).mappings().fetchall()
    rule_map_kisan = {r["id"]: r["scheme_id"] for r in r_kisan}
    if rule_map_kisan != {8: 6, 9: 6}:
        raise PreconditionFailure(f"Rules 8 and 9 must belong to scheme 6. Found: {rule_map_kisan}")
    for r in r_kisan:
        rollback_snapshot["eligibility_rules"][r["id"]] = dict(r)

    # 2. PMAY-U checks
    s8 = conn.execute(text("SELECT id, name, is_active, category, source_url, verification_status FROM schemes WHERE id = 8")).mappings().fetchone()
    if not s8 or not s8["is_active"] or "PMAY-U" not in s8["name"]:
        raise PreconditionFailure(f"Scheme 8 pre-check failed: {s8}")
    rollback_snapshot["schemes"][8] = dict(s8)

    s19 = conn.execute(text("SELECT id, name, is_active, category, source_url, verification_status FROM schemes WHERE id = 19")).mappings().fetchone()
    if not s19 or not s19["is_active"] or "PMAY-U" not in s19["name"]:
        raise PreconditionFailure(f"Scheme 19 pre-check failed: {s19}")
    rollback_snapshot["schemes"][19] = dict(s19)

    r_pmayu = conn.execute(text("SELECT id, scheme_id, field_name FROM eligibility_rules WHERE id IN (12, 13, 14)")).mappings().fetchall()
    rule_map_pmayu = {r["id"]: r["scheme_id"] for r in r_pmayu}
    if rule_map_pmayu != {12: 8, 13: 8, 14: 8}:
        raise PreconditionFailure(f"Rules 12, 13, 14 must belong to scheme 8. Found: {rule_map_pmayu}")
    for r in r_pmayu:
        rollback_snapshot["eligibility_rules"][r["id"]] = dict(r)

    # 3. PMFME checks (capture full attributes including category to guarantee exact preservation)
    s37 = conn.execute(text("SELECT id, name, is_active, category, source_url, verification_status FROM schemes WHERE id = 37")).mappings().fetchone()
    if not s37 or not s37["is_active"] or "PMFME" not in s37["name"] or s37["category"] != "Business & Entrepreneurship":
        raise PreconditionFailure(f"Scheme 37 pre-check failed: {s37}")
    rollback_snapshot["schemes"][37] = dict(s37)

    s88 = conn.execute(text("SELECT id, name, is_active, category, source_url, verification_status FROM schemes WHERE id = 88")).mappings().fetchone()
    if not s88 or not s88["is_active"] or "PMFME" not in s88["name"] or s88["verification_status"] != "verified":
        raise PreconditionFailure(f"Scheme 88 pre-check failed: {s88}")
    rollback_snapshot["schemes"][88] = dict(s88)

    # 4. Pudhumai Penn checks
    s116 = conn.execute(text("SELECT id, name, is_active, category, source_url, verification_status FROM schemes WHERE id = 116")).mappings().fetchone()
    if not s116 or s116["source_url"] != "https://pudhumaimaipen.tn.gov.in/":
        raise PreconditionFailure(f"Scheme 116 URL pre-check failed: {s116}")
    rollback_snapshot["schemes"][116] = dict(s116)

    d107 = conn.execute(text("SELECT id, scheme_id, source_url FROM scheme_documents WHERE id = 107")).mappings().fetchone()
    if not d107 or d107["scheme_id"] != 116 or d107["source_url"] != "https://pudhumaimaipen.tn.gov.in/":
        raise PreconditionFailure(f"Document 107 URL pre-check failed: {d107}")
    rollback_snapshot["scheme_documents"][107] = dict(d107)

    src128 = conn.execute(text("SELECT id, source_name, source_url FROM scheme_sources WHERE id = 128")).mappings().fetchone()
    if not src128 or src128["source_url"] != "https://pudhumaimaipen.tn.gov.in/":
        raise PreconditionFailure(f"Source 128 URL pre-check failed: {src128}")
    rollback_snapshot["scheme_sources"][128] = dict(src128)

    # 5. DAY-NRLM checks
    s76 = conn.execute(text("SELECT id, name, is_active, category, source_url, verification_status FROM schemes WHERE id = 76")).mappings().fetchone()
    if not s76 or s76["source_url"] != "https://nrlm.gov.in/" or s76["category"] != "Housing":
        raise PreconditionFailure(f"Scheme 76 pre-check failed: {s76}")
    rollback_snapshot["schemes"][76] = dict(s76)

    d58 = conn.execute(text("SELECT id, scheme_id, source_url FROM scheme_documents WHERE id = 58")).mappings().fetchone()
    if not d58 or d58["scheme_id"] != 76 or d58["source_url"] != "https://nrlm.gov.in/":
        raise PreconditionFailure(f"Document 58 pre-check failed: {d58}")
    rollback_snapshot["scheme_documents"][58] = dict(d58)

    src79 = conn.execute(text("SELECT id, source_name, source_url FROM scheme_sources WHERE id = 79")).mappings().fetchone()
    if not src79 or src79["source_url"] != "https://nrlm.gov.in/":
        raise PreconditionFailure(f"Source 79 pre-check failed: {src79}")
    rollback_snapshot["scheme_sources"][79] = dict(src79)

    # 6. SBM-G checks
    s77 = conn.execute(text("SELECT id, name, is_active, category, source_url, verification_status FROM schemes WHERE id = 77")).mappings().fetchone()
    if not s77 or s77["source_url"] != "https://sbm.gov.in/sbmgramin/" or s77["category"] != "Housing":
        raise PreconditionFailure(f"Scheme 77 pre-check failed: {s77}")
    rollback_snapshot["schemes"][77] = dict(s77)

    d59 = conn.execute(text("SELECT id, scheme_id, source_url FROM scheme_documents WHERE id = 59")).mappings().fetchone()
    if not d59 or d59["scheme_id"] != 77 or d59["source_url"] != "https://sbm.gov.in/sbmgramin/":
        raise PreconditionFailure(f"Document 59 pre-check failed: {d59}")
    rollback_snapshot["scheme_documents"][59] = dict(d59)

    src80 = conn.execute(text("SELECT id, source_name, source_url FROM scheme_sources WHERE id = 80")).mappings().fetchone()
    if not src80 or src80["source_url"] != "https://sbm.gov.in/sbmgramin/":
        raise PreconditionFailure(f"Source 80 pre-check failed: {src80}")
    rollback_snapshot["scheme_sources"][80] = dict(src80)

    print("[+] All pre-conditions verified successfully. Live data matches audit specifications exactly.")
    return rollback_snapshot


def execute_rollback_from_snapshot(conn, snapshot: Dict[str, Any]) -> None:
    """Execute rollback targeting strictly the modified records and fields from snapshot."""
    # 1. Rollback eligibility rules (only rules 8, 9, 12, 13, 14)
    for rid_str, rdata in snapshot.get("eligibility_rules", {}).items():
        conn.execute(
            text("UPDATE eligibility_rules SET scheme_id = :scheme_id WHERE id = :id"),
            {"id": int(rid_str), "scheme_id": rdata["scheme_id"]}
        )

    # 2. Rollback schemes - strictly revert only modified schemes and their modified fields
    # Schemes 11, 19, 88 were NOT modified by forward migration and are never updated.
    scheme_field_targets = {
        6: ["name", "is_active"],
        8: ["name", "is_active"],
        37: ["name", "is_active"],
        116: ["source_url"],
        76: ["source_url", "category"],
        77: ["source_url", "category"]
    }

    for sid, fields_to_revert in scheme_field_targets.items():
        orig_scheme = snapshot.get("schemes", {}).get(str(sid))
        if not orig_scheme:
            raise PreconditionFailure(f"Rollback manifest missing snapshot for scheme {sid}")
        set_clauses = [f"{f} = :{f}" for f in fields_to_revert]
        params = {"id": sid}
        for f in fields_to_revert:
            params[f] = orig_scheme.get(f)
        conn.execute(
            text(f"UPDATE schemes SET {', '.join(set_clauses)} WHERE id = :id"),
            params
        )

    # 3. Rollback documents (107, 58, 59)
    for doc_id_str, ddata in snapshot.get("scheme_documents", {}).items():
        conn.execute(
            text("UPDATE scheme_documents SET source_url = :url WHERE id = :id"),
            {"id": int(doc_id_str), "url": ddata["source_url"]}
        )

    # 4. Rollback sources (128, 79, 80)
    for src_id_str, sdata in snapshot.get("scheme_sources", {}).items():
        conn.execute(
            text("UPDATE scheme_sources SET source_url = :url WHERE id = :id"),
            {"id": int(src_id_str), "url": sdata["source_url"]}
        )


def plan_or_execute_corrections(execute: bool = False, rollback: bool = False) -> None:
    """Plan or execute corrections with strict transaction boundaries."""
    engine = get_db_connection()
    repo_root = Path(__file__).resolve().parents[2]
    backup_dir = repo_root / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = backup_dir / "stage3_corrections_rollback_manifest.json"
    sql_path = backup_dir / "stage3_corrections_forward.sql"
    rollback_sql_path = backup_dir / "stage3_corrections_rollback.sql"

    with engine.connect() as conn:
        if rollback:
            if not manifest_path.exists():
                print(f"[!] Cannot rollback: manifest file not found at {manifest_path}", file=sys.stderr)
                sys.exit(1)
            with open(manifest_path, "r", encoding="utf-8") as f:
                snapshot = json.load(f)
            print("[*] Executing ROLLBACK using saved manifest...")
            with conn.begin():
                execute_rollback_from_snapshot(conn, snapshot)
            print("[+] Rollback successfully completed.")
            return

        # Normal forward path: verify pre-conditions
        snapshot = verify_preconditions(conn)

        # Save snapshot manifest
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)
        print(f"[+] Saved rollback snapshot manifest: {manifest_path.name}")

        # Write forward and rollback SQL scripts for reference
        forward_sql = """-- Stage 3 Data Corrections Forward Migration
BEGIN;
-- 1. PM-KISAN: Transfer rules 8 & 9 to scheme 11; archive scheme 6
UPDATE eligibility_rules SET scheme_id = 11 WHERE id IN (8, 9);
UPDATE schemes SET is_active = FALSE, name = 'PM-KISAN Samman Nidhi [Archived Duplicate of #11]' WHERE id = 6;

-- 2. PMAY-U: Transfer rules 12, 13 & 14 to scheme 19; archive scheme 8
UPDATE eligibility_rules SET scheme_id = 19 WHERE id IN (12, 13, 14);
UPDATE schemes SET is_active = FALSE, name = 'Pradhan Mantri Awas Yojana - Urban 2.0 (PMAY-U 2.0) [Archived Duplicate of #19]' WHERE id = 8;

-- 3. PMFME: Archive scheme 37 in favor of canonical verified scheme 88
UPDATE schemes SET is_active = FALSE, name = 'Pradhan Mantri Formalisation of Micro Food Processing Enterprises Scheme (PMFME) [Archived Duplicate of #88]' WHERE id = 37;

-- 4. Pudhumai Penn URL Correction
UPDATE schemes SET source_url = 'https://pudhumaipenn.tn.gov.in/' WHERE id = 116;
UPDATE scheme_documents SET source_url = 'https://pudhumaipenn.tn.gov.in/' WHERE id = 107;
UPDATE scheme_sources SET source_url = 'https://pudhumaipenn.tn.gov.in/' WHERE id = 128;

-- 5. DAY-NRLM URL and Category Correction
UPDATE schemes SET source_url = 'https://aajeevika.gov.in/', category = 'Employment & Skills' WHERE id = 76;
UPDATE scheme_documents SET source_url = 'https://aajeevika.gov.in/' WHERE id = 58;
UPDATE scheme_sources SET source_url = 'https://aajeevika.gov.in/' WHERE id = 79;

-- 6. Swachh Bharat Grameen URL and Category Correction
UPDATE schemes SET source_url = 'https://swachhbharatmission.ddws.gov.in/', category = 'Health & Wellness' WHERE id = 77;
UPDATE scheme_documents SET source_url = 'https://swachhbharatmission.ddws.gov.in/' WHERE id = 59;
UPDATE scheme_sources SET source_url = 'https://swachhbharatmission.ddws.gov.in/' WHERE id = 80;
COMMIT;
"""
        with open(sql_path, "w", encoding="utf-8") as f:
            f.write(forward_sql)
        print(f"[+] Prepared forward SQL migration: {sql_path.name}")

        rollback_sql = """-- Stage 3 Data Corrections Rollback Migration
BEGIN;
UPDATE eligibility_rules SET scheme_id = 6 WHERE id IN (8, 9);
UPDATE schemes SET is_active = TRUE, name = 'PM-KISAN Samman Nidhi' WHERE id = 6;

UPDATE eligibility_rules SET scheme_id = 8 WHERE id IN (12, 13, 14);
UPDATE schemes SET is_active = TRUE, name = 'Pradhan Mantri Awas Yojana - Urban 2.0 (PMAY-U 2.0)' WHERE id = 8;

UPDATE schemes SET is_active = TRUE, name = 'Pradhan Mantri Formalisation of Micro Food Processing Enterprises Scheme (PMFME)' WHERE id = 37;

UPDATE schemes SET source_url = 'https://pudhumaimaipen.tn.gov.in/' WHERE id = 116;
UPDATE scheme_documents SET source_url = 'https://pudhumaimaipen.tn.gov.in/' WHERE id = 107;
UPDATE scheme_sources SET source_url = 'https://pudhumaimaipen.tn.gov.in/' WHERE id = 128;

UPDATE schemes SET source_url = 'https://nrlm.gov.in/', category = 'Housing' WHERE id = 76;
UPDATE scheme_documents SET source_url = 'https://nrlm.gov.in/' WHERE id = 58;
UPDATE scheme_sources SET source_url = 'https://nrlm.gov.in/' WHERE id = 79;

UPDATE schemes SET source_url = 'https://sbm.gov.in/sbmgramin/', category = 'Housing' WHERE id = 77;
UPDATE scheme_documents SET source_url = 'https://sbm.gov.in/sbmgramin/' WHERE id = 59;
UPDATE scheme_sources SET source_url = 'https://sbm.gov.in/sbmgramin/' WHERE id = 80;
COMMIT;
"""
        with open(rollback_sql_path, "w", encoding="utf-8") as f:
            f.write(rollback_sql)
        print(f"[+] Prepared rollback SQL migration: {rollback_sql_path.name}")

        if not execute:
            print("\n" + "="*70)
            print("DRY-RUN MODE ACTIVE: NO DATABASE RECORDS WERE MODIFIED.")
            print("To execute these corrections, you must pass the --execute flag explicitly.")
            print("="*70 + "\n")
            return

        # If --execute flag is explicitly given:
        print("[*] Executing corrections within transaction...")
        with conn.begin():
            conn.execute(text("UPDATE eligibility_rules SET scheme_id = 11 WHERE id IN (8, 9)"))
            conn.execute(text("UPDATE schemes SET is_active = FALSE, name = 'PM-KISAN Samman Nidhi [Archived Duplicate of #11]' WHERE id = 6"))

            conn.execute(text("UPDATE eligibility_rules SET scheme_id = 19 WHERE id IN (12, 13, 14)"))
            conn.execute(text("UPDATE schemes SET is_active = FALSE, name = 'Pradhan Mantri Awas Yojana - Urban 2.0 (PMAY-U 2.0) [Archived Duplicate of #19]' WHERE id = 8"))

            conn.execute(text("UPDATE schemes SET is_active = FALSE, name = 'Pradhan Mantri Formalisation of Micro Food Processing Enterprises Scheme (PMFME) [Archived Duplicate of #88]' WHERE id = 37"))

            conn.execute(text("UPDATE schemes SET source_url = 'https://pudhumaipenn.tn.gov.in/' WHERE id = 116"))
            conn.execute(text("UPDATE scheme_documents SET source_url = 'https://pudhumaipenn.tn.gov.in/' WHERE id = 107"))
            conn.execute(text("UPDATE scheme_sources SET source_url = 'https://pudhumaipenn.tn.gov.in/' WHERE id = 128"))

            conn.execute(text("UPDATE schemes SET source_url = 'https://aajeevika.gov.in/', category = 'Employment & Skills' WHERE id = 76"))
            conn.execute(text("UPDATE scheme_documents SET source_url = 'https://aajeevika.gov.in/' WHERE id = 58"))
            conn.execute(text("UPDATE scheme_sources SET source_url = 'https://aajeevika.gov.in/' WHERE id = 79"))

            conn.execute(text("UPDATE schemes SET source_url = 'https://swachhbharatmission.ddws.gov.in/', category = 'Health & Wellness' WHERE id = 77"))
            conn.execute(text("UPDATE scheme_documents SET source_url = 'https://swachhbharatmission.ddws.gov.in/' WHERE id = 59"))
            conn.execute(text("UPDATE scheme_sources SET source_url = 'https://swachhbharatmission.ddws.gov.in/' WHERE id = 80"))

        print("[+] All database corrections committed successfully!")


def main():
    parser = argparse.ArgumentParser(description="LifeNavigator-AI Stage 3 Data Corrections Script")
    parser.add_argument("--execute", action="store_true", default=False,
                        help="Explicitly execute corrections (otherwise runs in dry-run mode).")
    parser.add_argument("--rollback", action="store_true", default=False,
                        help="Rollback previously executed corrections using saved manifest.")
    args = parser.parse_args()

    try:
        plan_or_execute_corrections(execute=args.execute, rollback=args.rollback)
    except PreconditionFailure as e:
        print(f"\n[!] PRECONDITION FAILURE: {e}", file=sys.stderr)
        print("[!] Execution aborted safely. Database was NOT modified.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
