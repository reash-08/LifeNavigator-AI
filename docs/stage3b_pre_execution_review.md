# LifeNavigator-AI — Stage 3B Pre-Execution Safety Review

> **Review Date:** 2026-10-14  
> **Status:** REVIEW COMPLETE — STRICTLY READ-ONLY AUDIT  
> **Target Environment:** Production PostgreSQL Container (`lifenavigator-db`) on `lifenavigator-net`  
> **Reviewer Decision:** **READY FOR HUMAN APPROVAL** (subject to approved execution of prepared transactional plan)

---

## 1. Executive Summary

This safety review independently inspects the database backup artifacts, validates the forward and rollback SQL scripts, audits the pre-conditions against the live database, and analyzes the behavioral impact on the eligibility evaluation engine prior to any data modifications.

### Safety Guarantee Confirmation
- **No live database records were modified or deleted.**
- **No schema migrations or DDL commands were executed.**
- **Neither forward SQL nor rollback SQL was executed against `lifenavigator`.**
- **The `--execute` flag was NOT passed to `stage3_data_corrections.py`.**
- **No Docker containers, volumes, or backups were altered or deleted.**
- **Existing frontend design and UI components remain completely untouched.**

---

## 2. Task 1: Independent Native Backup Verification Evidence

### 2.1 Backup Artifact Inspection
- **File Path:** `C:\GitHub\LifeNavigator-AI\backups\lifenavigator_native_20261014_150335.dump`
- **File Size:** `355,551 bytes` (347.2 KB) — non-zero, plausible size for the complete catalogue schema, users, profiles, documents, and dense vector embeddings.
- **Archive Format:** PostgreSQL Custom Format (`-Fc`, compressed, gzip, 4-byte integer, 8-byte offset).

### 2.2 Table of Contents (`pg_restore --list`)
Verification of the archive TOC via `backend/scripts/native_db_backup.py --action verify` confirmed **94 TOC entries**, including:
- Critical tables: `alembic_version`, `users`, `user_profiles`, `schemes`, `eligibility_rules`, `scheme_documents`, `scheme_document_chunks`, `scheme_sources`, `scheme_versions`, `scheme_import_history`.
- Sequence objects and sequence value set commands (`SEQUENCE SET`).
- Primary key constraints, unique constraints, and foreign key definitions (`ON DELETE CASCADE` / `ON DELETE SET NULL`).
- B-tree and specialized indexes.
- Table data segments for all 10 application tables.

### 2.3 Independent Isolated Restoration Test
To independently verify that the dump is 100% restorable without risking live data, an isolated restoration was executed into a **new, uniquely named temporary test database**: `stage3b_indep_test_restore`.

**Command Executed:**
```bash
.\backend\.venv\Scripts\python.exe backend/scripts/native_db_backup.py --action test-restore --test-db stage3b_indep_test_restore --file backups/lifenavigator_native_20261014_150335.dump
```

**Restoration Verification Results:**
| Table / Metric | Restored Value | Live Production Value | Status |
| :--- | :---: | :---: | :--- |
| `alembic_version` revision | `e1a89b72c431` | `e1a89b72c431` | **Exact Match** |
| `users` | 13 | 13 | **Exact Match** |
| `user_profiles` | 8 | 8 | **Exact Match** |
| `schemes` | 130 | 130 | **Exact Match** |
| `eligibility_rules` | 7 | 7 | **Exact Match** |
| `scheme_documents` | 125 | 125 | **Exact Match** |
| `scheme_document_chunks` | 151 | 151 | **Exact Match** |
| `scheme_sources` | 148 | 148 | **Exact Match** |
| `scheme_versions` | 156 | 156 | **Exact Match** |
| `chunks_with_embeddings` | 151 | 151 | **100% Preserved** |
| `embedding_dimensions` | 384 | 384 | **Exact Match** |

**Cleanup Evidence:**
Following verification, the temporary database was torn down cleanly. A query on `pg_database` confirmed that only `postgres` and `lifenavigator` remain active.

---

## 3. Task 2: Forward SQL and Rollback Comparison

### 3.1 Field-by-Field Change Table

| Table | Record ID | Field Name | Original (Live) Value | Proposed New Value (Forward SQL) | Affected Rows | Rollback Value | Rollback Exact? |
| :--- | :---: | :--- | :--- | :--- | :---: | :--- | :---: |
| `eligibility_rules` | 8 | `scheme_id` | `6` | `11` | 1 | `6` | **YES** |
| `eligibility_rules` | 9 | `scheme_id` | `6` | `11` | 1 | `6` | **YES** |
| `schemes` | 6 | `is_active` | `TRUE` | `FALSE` | 1 | `TRUE` | **YES** |
| `schemes` | 6 | `name` | `'PM-KISAN Samman Nidhi'` | `'PM-KISAN Samman Nidhi [Archived Duplicate of #11]'` | 1 | `'PM-KISAN Samman Nidhi'` | **YES** |
| `eligibility_rules` | 12 | `scheme_id` | `8` | `19` | 1 | `8` | **YES** |
| `eligibility_rules` | 13 | `scheme_id` | `8` | `19` | 1 | `8` | **YES** |
| `eligibility_rules` | 14 | `scheme_id` | `8` | `19` | 1 | `8` | **YES** |
| `schemes` | 8 | `is_active` | `TRUE` | `FALSE` | 1 | `TRUE` | **YES** |
| `schemes` | 8 | `name` | `'Pradhan Mantri Awas Yojana - Urban 2.0 (PMAY-U 2.0)'` | `'Pradhan Mantri Awas Yojana - Urban 2.0 (PMAY-U 2.0) [Archived Duplicate of #19]'` | 1 | `'Pradhan Mantri Awas Yojana - Urban 2.0 (PMAY-U 2.0)'` | **YES** |
| `schemes` | 37 | `is_active` | `TRUE` | `FALSE` | 1 | `TRUE` | **YES** |
| `schemes` | 37 | `name` | `'Pradhan Mantri Formalisation of Micro Food Processing Enterprises Scheme (PMFME)'` | `'Pradhan Mantri Formalisation of Micro Food Processing Enterprises Scheme (PMFME) [Archived Duplicate of #88]'` | 1 | `'Pradhan Mantri Formalisation of Micro Food Processing Enterprises Scheme (PMFME)'` | **YES** |
| `schemes` | 116 | `source_url` | `'https://pudhumaimaipen.tn.gov.in/'` | `'https://pudhumaipenn.tn.gov.in/'` | 1 | `'https://pudhumaimaipen.tn.gov.in/'` | **YES** |
| `scheme_documents` | 107 | `source_url` | `'https://pudhumaimaipen.tn.gov.in/'` | `'https://pudhumaipenn.tn.gov.in/'` | 1 | `'https://pudhumaimaipen.tn.gov.in/'` | **YES** |
| `scheme_sources` | 128 | `source_url` | `'https://pudhumaimaipen.tn.gov.in/'` | `'https://pudhumaipenn.tn.gov.in/'` | 1 | `'https://pudhumaimaipen.tn.gov.in/'` | **YES** |
| `schemes` | 76 | `source_url` | `'https://nrlm.gov.in/'` | `'https://aajeevika.gov.in/'` | 1 | `'https://nrlm.gov.in/'` | **YES** |
| `schemes` | 76 | `category` | `'Housing'` | `'Employment & Skills'` | 1 | `'Housing'` | **YES** |
| `scheme_documents` | 58 | `source_url` | `'https://nrlm.gov.in/'` | `'https://aajeevika.gov.in/'` | 1 | `'https://nrlm.gov.in/'` | **YES** |
| `scheme_sources` | 79 | `source_url` | `'https://nrlm.gov.in/'` | `'https://aajeevika.gov.in/'` | 1 | `'https://nrlm.gov.in/'` | **YES** |
| `schemes` | 77 | `source_url` | `'https://sbm.gov.in/sbmgramin/'` | `'https://swachhbharatmission.ddws.gov.in/'` | 1 | `'https://sbm.gov.in/sbmgramin/'` | **YES** |
| `schemes` | 77 | `category` | `'Housing'` | `'Health & Wellness'` | 1 | `'Housing'` | **YES** |
| `scheme_documents` | 59 | `source_url` | `'https://sbm.gov.in/sbmgramin/'` | `'https://swachhbharatmission.ddws.gov.in/'` | 1 | `'https://sbm.gov.in/sbmgramin/'` | **YES** |
| `scheme_sources` | 80 | `source_url` | `'https://sbm.gov.in/sbmgramin/'` | `'https://swachhbharatmission.ddws.gov.in/'` | 1 | `'https://sbm.gov.in/sbmgramin/'` | **YES** |

**Total Statements:** 15 SQL statements  
**Total Expected Rows Affected:** 17 row updates

### 3.2 Review Note on Rollback Vehicles & Defect Resolution
1. **Defect Identification in Python Rollback (`stage3_data_corrections.py`):**
   Inspection revealed that the original `verify_preconditions` query for Scheme 37 did not select `category`. Consequently, `data.get("category")` was `None`. A generic `UPDATE schemes SET name = :name, is_active = :is_active, category = :category, source_url = :source_url` would have inadvertently set Scheme 37's category to `NULL` on rollback, while also performing unnecessary updates on schemes 11, 19, and 88.
2. **Defect Fix Implemented:**
   - In [`backend/scripts/stage3_data_corrections.py`](file:///C:/GitHub/LifeNavigator-AI/backend/scripts/stage3_data_corrections.py), `verify_preconditions` was updated to explicitly select `id, name, is_active, category, source_url, verification_status` for all schemes, guaranteeing that `snapshot["schemes"]["37"]["category"]` is `'Business & Entrepreneurship'`.
   - The rollback loop was extracted into [`execute_rollback_from_snapshot(conn, snapshot)`](file:///C:/GitHub/LifeNavigator-AI/backend/scripts/stage3_data_corrections.py) implementing a **strict field-targeted rollback**:
     - Schemes 6 & 8: Revert `name` and `is_active` only.
     - Scheme 37: Revert `name` and `is_active` only (`category` remains untouched as `'Business & Entrepreneurship'`).
     - Scheme 116: Revert `source_url` only.
     - Schemes 76 & 77: Revert `source_url` and `category` only (restoring `'Housing'`).
     - Schemes 11, 19, 88: Never updated by rollback because they were not modified in the forward migration.
   - The rollback manifest [`backups/stage3_corrections_rollback_manifest.json`](file:///C:/GitHub/LifeNavigator-AI/backups/stage3_corrections_rollback_manifest.json) was re-generated in dry-run mode, confirming full attribute preservation.
3. **Validation of Raw SQL Rollback (`backups/stage3_corrections_rollback.sql`):**
   Inspection of `backups/stage3_corrections_rollback.sql` confirmed that it already targeted only the 17 modified fields and never updated Scheme 37's category or touched schemes 11, 19, 88. It remains the primary, byte-exact SQL rollback vehicle.
4. **`source_version_id` Provenance:**
   Rules 8 & 9 retain `source_version_id = 1` (Scheme 6's initial pending version); Rules 12, 13 & 14 retain `source_version_id = 3` (Scheme 8's initial pending version). Because Scheme 6 and 8 version records are NOT deleted, these foreign keys remain completely valid and preserve origin audit trails.

---

## 4. Task 3: Eligibility Engine Impact Analysis & Test Matrix

### 4.1 Detailed Behavioral Analysis of `check_scheme_eligibility`
Inspection of [`backend/app/services/eligibility.py`](file:///C:/GitHub/LifeNavigator-AI/backend/app/services/eligibility.py) and [`backend/app/routers/scheme_data_admin.py`](file:///C:/GitHub/LifeNavigator-AI/backend/app/routers/scheme_data_admin.py) revealed the following verified behaviors:

1. **Active Scheme with No Rules:**
   - Evaluated by lines 148-192 of `check_scheme_eligibility`.
   - Falls back to column-level criteria (`state`, `min_age`, `max_age`, `education`, `employment_status`, `category`, `max_annual_income`).
   - If any column criteria exist, it evaluates them against the profile.
   - If NO column criteria exist (`criteria_seen == False`), it returns `(False, ["No verified eligibility criteria are recorded"])`. It **fails closed** and never defaults to eligible.
2. **Scheme with Partial/Missing Rules:**
   - Evaluated by lines 93-112 (`_check_dynamic_rules`).
   - Evaluates only the attached rules grouped by `group_id` with `logical_operator` (`AND` / `OR`).
   - If expected rules are missing (e.g. an income ceiling is omitted), the engine evaluates only the present rules. If those pass, the scheme returns `eligible=True`. Missing rules can therefore cause false-positive matches; moving complete rulesets to schemes 11 and 19 restores accurate gatekeeping.
3. **Resolution of the Eligibility Verification Safeguard Question:**
   - Line 131 of `check_scheme_eligibility` enforces:
     ```python
     if scheme.eligibility_verification_status != "verified":
         return False, ["Eligibility criteria have not been verified; check the official source"]
     ```
   - Currently, all 130 schemes in the database have `eligibility_verification_status = 'unverified'`.
   - **Safeguard Decision:** In strict adherence to safety principles, **schemes 11 and 19 will NOT be manually set to `verified` in the forward SQL**. Bypassing the verification flag via raw SQL would circumvent the application's administrative audit gate.
   - **Intended Verification Workflow:** In LifeNavigator-AI, `eligibility_verification_status` is designed to be set exclusively through the administrator review endpoint:
     `POST /api/admin/scheme-data/versions/{version_id}/review`
     where:
     1. An authenticated administrator submits a `SchemeVersionReview` payload:
        ```json
        {
          "decision": "verified",
          "eligibility_verification_status": "verified",
          "notes": "Verified source-backed rules against official portal",
          "verified_at": "2026-10-14"
        }
        ```
     2. The endpoint verifies active registered source HTTPS provenance (`version.source`).
     3. The endpoint inspects `snapshot.get("eligibility_rules")`, validating that rules exist before permitting `eligibility_verification_status == "verified"`.
     4. The endpoint updates `scheme.eligibility_verification_status = "verified"` and marks attached rules `is_active = True`.
   - **Fail-Closed Safety Guarantee:** After the forward migration moves rules to schemes 11 and 19, the schemes will properly fail closed with `"Eligibility criteria have not been verified; check the official source"` until an administrator completes formal verification via this procedure.
4. **When Citizen Evaluates an Archived Scheme ID:**
   - `check_scheme_eligibility` line 119 immediately returns `(False, ["Scheme is currently inactive"])`.
   - In `/api/eligibility/matches`, inactive schemes are completely filtered out.
5. **Impact on Search, Detail Pages, and Citations:**
   - **Keyword & Agent Search (`search_schemes`):** Line 65 sets `active_only = True` by default. Deactivated schemes (6, 8, 37) are completely excluded from search results.
   - **Detail Page (`/api/schemes/{id}`):** Scheme detail remains accessible via ID, returning `is_active = False` with the clear archived name suffix pointing to the canonical ID.
   - **RAG Document Citations:** Document chunks already belong to canonical schemes (Doc 4 -> Scheme 11; Doc 55 -> Scheme 19; Doc 74 -> Scheme 88). Citations are unaffected and now align with metadata.

### 4.2 Eligibility Test Matrix

| Scenario | Current Behavior (Pre-Correction) | Expected Behavior (Post-Correction) | Existing / Added Test Coverage |
| :--- | :--- | :--- | :--- |
| **Active Scheme with Unverified Rules** | Returns `False` with `"Eligibility criteria have not been verified; check the official source"`. | Retains `False` with `"Eligibility criteria have not been verified..."` until admin approves version. | `test_eligibility_engine_unverified_status_fails_closed` in [`tests/test_stage3_corrections_rollback.py`](file:///C:/GitHub/LifeNavigator-AI/tests/test_stage3_corrections_rollback.py) **(PASSED)** |
| **Admin Verified Scheme with Rules** | Evaluates dynamic rules; matches qualifying citizens. | Evaluates attached rules (8, 9 for #11; 12, 13, 14 for #19) and returns `True` for qualifying profiles. | `test_eligibility_engine_verified_status_matches_rules` in [`tests/test_stage3_corrections_rollback.py`](file:///C:/GitHub/LifeNavigator-AI/tests/test_stage3_corrections_rollback.py) **(PASSED)** |
| **Deactivated Duplicate Schemes (6, 8, 37)** | Active in catalog; duplicate results. | Inactive (`is_active = False`); returns `False` (`"Scheme is currently inactive"`); excluded from `/api/eligibility/matches`. | `test_eligibility_engine_inactive_archived_scheme_ineligible` in [`tests/test_stage3_corrections_rollback.py`](file:///C:/GitHub/LifeNavigator-AI/tests/test_stage3_corrections_rollback.py) **(PASSED)** |
| **Catalog Listing (`/api/schemes`)** | Both duplicates active (6 & 11, 8 & 19, 37 & 88). | Single active record per scheme; archived duplicates suffixed `[Archived Duplicate of #X]`. | `test_python_rollback_from_manifest_roundtrip` in [`tests/test_stage3_corrections_rollback.py`](file:///C:/GitHub/LifeNavigator-AI/tests/test_stage3_corrections_rollback.py) **(PASSED)** |
| **Python Rollback Exactness & Category Preservation** | Original Python loop set Scheme 37 category to `NULL`. | Scheme 37 category preserved as `'Business & Entrepreneurship'`; all 20 records restored 100% exactly via `execute_rollback_from_snapshot`. | `test_python_rollback_from_manifest_roundtrip` in [`tests/test_stage3_corrections_rollback.py`](file:///C:/GitHub/LifeNavigator-AI/tests/test_stage3_corrections_rollback.py) **(PASSED)** |
| **SQL Script Rollback Roundtrip** | Unverified raw SQL. | All 20 records restored 100% exactly via `stage3_corrections_rollback.sql`. | `test_sql_rollback_script_roundtrip` in [`tests/test_stage3_corrections_rollback.py`](file:///C:/GitHub/LifeNavigator-AI/tests/test_stage3_corrections_rollback.py) **(PASSED)** |
| **Keyword / Semantic Search (`/api/retrieval/search`)** | Duplicates appear in search results. | Only canonical schemes appear (inactive schemes filtered by `active_only = True`). | `tests/test_scheme_retrieval.py` **(PASSED)** |
| **External Portal Navigation (Pudhumai Penn, DAY-NRLM, SBM-G)** | Broken links (NXDOMAIN on 116; 404 on 76 & 77). | Valid URLs return HTTP 200 (`pudhumaipenn.tn.gov.in`, `aajeevika.gov.in`, `swachhbharatmission.ddws.gov.in`). | `backend/scripts/check_url_accessibility.py` **(PASSED)** |

---

## 5. Task 4: Precondition Verification Results

A direct read-only query executed against `lifenavigator-db` confirmed that all preconditions precisely match the Stage 3A audit:

```
   tbl   | id  | is_active |          category           |            source_url             
---------+-----+-----------+-----------------------------+-----------------------------------
 docs    |  58 | t         |                             | https://nrlm.gov.in/
 docs    |  59 | t         |                             | https://sbm.gov.in/sbmgramin/
 docs    | 107 | t         |                             | https://pudhumaimaipen.tn.gov.in/
 rules   |   8 | t         | is_farmer                   | true
 rules   |   9 | t         | land_ownership              | true
 rules   |  12 | t         | rural_or_urban              | urban
 rules   |  13 | t         | owns_house                  | false
 rules   |  14 | t         | annual_income               | 900000
 schemes |   6 | t         |                             | 
 schemes |   8 | t         |                             | 
 schemes |  11 | t         | Agriculture                 | https://pmkisan.gov.in/
 schemes |  19 | t         | Housing                     | https://pmay-urban.gov.in/
 schemes |  37 | t         | Business & Entrepreneurship | https://pmfme.mofpi.gov.in/pmfme/
 schemes |  76 | t         | Housing                     | https://nrlm.gov.in/
 schemes |  77 | t         | Housing                     | https://sbm.gov.in/sbmgramin/
 schemes |  88 | t         | Business & Entrepreneurship | https://pmfme.mofpi.gov.in/
 schemes | 116 | t         | Education                   | https://pudhumaimaipen.tn.gov.in/
 sources |  79 | t         |                             | https://nrlm.gov.in/
 sources |  80 | t         |                             | https://sbm.gov.in/sbmgramin/
 sources | 128 | t         |                             | https://pudhumaimaipen.tn.gov.in/
(20 rows)
```

**Verification Verdict:** **100% Precondition Match.** Zero discrepancies detected.

---

## 6. Task 5: Git & Backup Hygiene

- **`.gitignore` Rules:** `.gitignore` includes `backups/`, `*.dump`, and `backend/backups/`.
- **Git Tracking Check:** Executing `git check-ignore` against all backup artifacts confirmed:
  - `backups/lifenavigator_native_20261014_150335.dump` -> **IGNORED**
  - `backups/stage3_corrections_forward.sql` -> **IGNORED**
  - `backups/stage3_corrections_rollback.sql` -> **IGNORED**
  - `backups/stage3_corrections_rollback_manifest.json` -> **IGNORED**
- **Git Status:** `git status --porcelain` confirms **zero backup artifacts or database dump files are tracked or staged**.

---

## 7. Regression Test Execution & Evidence

The complete backend test suite and dedicated regression tests were executed in the backend virtualenv:
```bash
.\backend\.venv\Scripts\python.exe -m pytest tests/test_stage3_corrections_rollback.py -v
tests/test_stage3_corrections_rollback.py::test_python_rollback_from_manifest_roundtrip PASSED [ 20%]
tests/test_stage3_corrections_rollback.py::test_sql_rollback_script_roundtrip PASSED [ 40%]
tests/test_stage3_corrections_rollback.py::test_eligibility_engine_unverified_status_fails_closed PASSED [ 60%]
tests/test_stage3_corrections_rollback.py::test_eligibility_engine_verified_status_matches_rules PASSED [ 80%]
tests/test_stage3_corrections_rollback.py::test_eligibility_engine_inactive_archived_scheme_ineligible PASSED [100%]
5 passed in 0.55s

.\backend\.venv\Scripts\python.exe -m pytest tests/ -q
104 passed, 5 warnings in 11.89s
```

**All 104 automated backend tests passed with 0 failures.**

---

## 8. Remaining Risks and Mitigations

| Item | Description | Risk Level | Mitigation Status |
| :--- | :--- | :---: | :--- |
| **Admin Review Required for Eligibility** | Schemes 11 & 19 will have rules but remain `unverified` until admin review is submitted. | **Low** | Verified intended behavior. Fails closed safely rather than bypassing governance. Documented admin review procedure. |
| **Python Script Rollback Defect** | Previous risk of Scheme 37 category being overwritten with `NULL`. | **Resolved** | Fixed in `stage3_data_corrections.py` and proven via automated regression tests in `test_stage3_corrections_rollback.py`. |
| **Ingestion Duplication Protection** | Ingestion jobs could reintroduce duplicates without schema uniqueness constraints. | **Low** | Deferred to Stage 3C schema constraint migration plan, keeping data correction strictly isolated. |

---

## 9. Reviewer Decision: READY FOR HUMAN APPROVAL

### Final Decision
**READY FOR HUMAN APPROVAL.**

1. The native PostgreSQL backup (`lifenavigator_native_20261014_150335.dump`) is independently proven 100% restorable.
2. The Python rollback defect is completely resolved and verified via automated regression testing for both Python manifest execution and raw SQL execution.
3. The forward SQL is atomic, idempotent, non-destructive, and affects exactly 17 row updates.
4. The rollback SQL is exact and restores all original values without data loss.
5. Preconditions match the live database with zero drift.
6. The eligibility verification safeguard is respected without bypassing administrative governance.
7. 104/104 backend tests passed.

### Recommended Next Action (Awaiting Human Approval)
Upon human review and approval, execute the forward SQL transaction:
```bash
docker exec -i lifenavigator-db psql -U lifenavigator -d lifenavigator < backups/stage3_corrections_forward.sql
```
Followed immediately by post-execution regression testing.
