# LifeNavigator-AI — Stage 6C: Source and URL Corrections Manifest & Execution Report

**Date:** 2026-10-18
**Repository:** `C:\GitHub\LifeNavigator-AI`
**Database:** PostgreSQL 16.15 (`pgvector`) on `localhost:5432/lifenavigator`
**Current Alembic Revision:** `3c1a2b3c4d5e` (Head)
**Safety Status:** Authorized Execution Complete; Single-Transaction Mutation Committed; Post-Execution Verification Passed (100%).

---

## 1. Executive Summary

Following the **Stage 6A Two-Profile Audit** and **Stage 6B Eligibility Remediation Plan**, Stage 6C focuses strictly on **source-registration integrity and official URL corrections**.

### Verified Database Baseline (Pre-Mutation):
- **Total Schemes:** 130 (125 active, 5 inactive: duplicate canonical references #6, #8, #37; sunset schemes #22, #114)
- **Total Scheme Sources:** 151 (all 151 active)
- **Scheme Documents:** 125
- **Scheme Document Chunks:** 151 (384-dimensional unit-norm vector embeddings)
- **Scheme Versions:** 156
- **Users:** 17
- **User Profiles:** 10
- **Eligibility Rules:** 7
- **Alembic Revision:** `3c1a2b3c4d5e`

---

## 2. Phase 1 — Read-Only Inspection Findings

### 2.1 The 21 Source-Registration Mismatches
In Stage 6A, 21 active schemes failed the source registration check in `backend/app/services/eligibility.py`:
```python
registered_source = getattr(scheme, "source", None)
if (
    registered_source is None
    or not registered_source.is_active
    or registered_source.source_url != scheme.source_url
):
    return False, ["Eligibility source is not registered or active"]
```

#### Empirical Analysis of the 21 Schemes:
1. **19 Schemes with Existing Dedicated Sources:** During the Stage 3 catalogue expansion, schemes had their `Scheme.source_url` updated to official apex portals (e.g. `https://pmvishwakarma.gov.in/`, `https://pmmvy.wcd.gov.in/`). Matching, dedicated `SchemeSource` records **were already created** in PostgreSQL with active status (`is_active=True`), identical `source_url`, and 0 linked schemes. However, the foreign key column `Scheme.source_id` on the pre-existing scheme records remained pointed to older fixture sources (such as deep PDF links or obsolete subpaths).
2. **1 Scheme Completely Unlinked:** Scheme 7 (IGNOAPS) has `Scheme.source_id = None`, despite `SchemeSource #120` (`NSAP Portal — IGNOAPS`, `https://nsap.nic.in/`) existing in the database with 0 linked schemes.
3. **2 Schemes with Missing Sources:** Schemes 9 and 10 (PM YASASVI) have `source_url = None` and `source_id = None`. They represent unverified fixture records from early testing.
4. **Zero Shared-Source Collisions:** Modifying `Scheme.source_id` on these 19 schemes updates ONLY the foreign key pointer on the `schemes` table to point to the dedicated, active `SchemeSource`. It **does not alter, overwrite, or delete** any existing `SchemeSource` records.

### 2.2 Scheme 116 (Pudhumai Penn) URL Typo
- **Current Database Value:** `application_url = "https://pudhumaimaipen.tn.gov.in/"`
- **Defect:** Typo in domain containing an extraneous `"mai"`, causing `NXDOMAIN` lookup failure.
- **Authoritative Source:** Registered Government of Tamil Nadu portal under TNeGA / NIC is `https://pudhumaipenn.tn.gov.in/` (unified portal: `https://penkalvi.tn.gov.in/`).
- **Linked Source in DB:** `SchemeSource #128` (`Government of Tamil Nadu – Pudhumai Penn Portal`, `https://pudhumaipenn.tn.gov.in/`) is already active and linked to Scheme 116 (`source_id = 128`).
- **Correction:** Update `Scheme.application_url` and `SchemeVersion.source_url` (v1) to `https://pudhumaipenn.tn.gov.in/`.

### 2.3 Schemes 76 and 77 — Verified Correct (No Mutation Required)
- **Scheme 76 (DAY-NRLM):** Category is already `Employment & Skills`, `source_url = "https://aajeevika.gov.in/"`, `source_id = 79` (`National Rural Livelihoods Mission Portal`, `https://aajeevika.gov.in/`). Matches 100%.
- **Scheme 77 (SBM-G IHHL):** Category is already `Health & Wellness`, `source_url = "https://swachhbharatmission.ddws.gov.in/"`, `source_id = 80` (`Swachh Bharat Mission – Grameen Portal`, `https://swachhbharatmission.ddws.gov.in/`). Matches 100%.

### 2.4 Schemes 9 and 10 (PM YASASVI) — Ambiguity Analysis
- **Current DB Values:** `source_url = None`, `source_id = None`, `verification_status = None`, `eligibility_verification_status = 'unverified'`.
- **Investigation:** Administered by the Department of Social Justice and Empowerment (DoSJE), Ministry of Social Justice and Empowerment (MoSJE), Government of India (`https://socialjustice.gov.in/`), applied via National Scholarship Portal (`https://scholarships.gov.in/`).
- **Database Status:** There is currently NO dedicated `SchemeSource` record in the database for PM YASASVI. In the preliminary Stage 6B draft, linking to Source #43 (`National Scholarship Portal — CSSS`) was proposed, but Source #43 is dedicated to CSSS under the Ministry of Education. Linking to #43 would create false provenance.
- **Recommendation:** In accordance with Mandatory Rule #8 ("Do not mark a scheme as verified merely because a URL has been added or corrected") and Rule #10 ("If a source mapping is ambiguous or an official URL cannot be verified, leave it unchanged and report it for human review"), Schemes 9 and 10 remain unmutated in this stage.

---

## 3. Phase 2 — Complete Proposed Correction Manifest

| Sch ID | Scheme Name | Current `app_url` | Current `source_id` | Current Linked Source URL | Proposed `source_id` | Target `SchemeSource` Name & URL | Evidence & Rationale | URL Type | Related Rows to Update | Expected Rows | Confidence |
| :---: | :--- | :--- | :---: | :--- | :---: | :--- | :--- | :--- | :--- | :---: | :---: |
| **7** | Indira Gandhi National Old Age Pension Scheme (IGNOAPS) | `https://nsap.nic.in/` | `None` | `None` | **120** | `NSAP Portal — IGNOAPS`<br>`https://nsap.nic.in/` | Source #120 exists with exact URL and scheme name; 0 currently linked schemes. | General portal / scheme overview | None (Doc #7 matches) | 1 (`schemes`) | High (100%) |
| **13** | PM POSHAN | `https://pmposhan.education.gov.in/` | `3` | `https://pmposhan.education.gov.in/aboutus.html` | **41** | `PM POSHAN Official Portal`<br>`https://pmposhan.education.gov.in/` | Source #41 exists with exact root URL; 0 currently linked schemes. | Dedicated scheme portal | None | 1 (`schemes`) | High (100%) |
| **15** | Mission Shakti | `https://wcd.gov.in/` | `5` | `https://wcd.gov.in/offerings/...` | **66** | `Ministry of Women and Child Development — Mission Shakti`<br>`https://wcd.gov.in/` | Source #66 exists with exact root URL and scheme name; 0 currently linked schemes. | Apex ministry portal | None | 1 (`schemes`) | High (100%) |
| **16** | Shakti Sadan | `https://wcd.gov.in/` | `6` | `https://wcd.gov.in/women/shakti-sadan` | **67** | `Ministry of Women and Child Development — Shakti Sadan`<br>`https://wcd.gov.in/` | Source #67 exists with exact root URL and dedicated scheme name; 0 currently linked schemes. | Apex ministry portal | None | 1 (`schemes`) | High (100%) |
| **17** | Assistance to Persons with Disabilities (ADIP) | `https://depwd.gov.in/` | `7` | `https://depwd.gov.in/en/adip-scheme/` | **103** | `Department of Empowerment of Persons with Disabilities — ADIP Scheme`<br>`https://depwd.gov.in/` | Source #103 exists with exact root URL and scheme name; 0 currently linked schemes. | Department portal / scheme page | None | 1 (`schemes`) | High (100%) |
| **18** | Ayushman Bharat — PM-JAY | `https://pmjay.gov.in/` | `8` | `https://www.myscheme.gov.in/hi/schemes/ab-pmjay` | **57** | `National Health Authority — PM-JAY`<br>`https://pmjay.gov.in/` | Source #57 exists with exact root URL; replaces myScheme Hindi redirect; 0 currently linked schemes. | Dedicated scheme portal / gateway | None | 1 (`schemes`) | High (100%) |
| **20** | PMKVY 4.0 | `https://www.pmkvyofficial.org/` | `10` | `https://www.pmkvyofficial.org/photos/...pdf` | **85** | `PMKVY Official Portal`<br>`https://www.pmkvyofficial.org/` | Source #85 exists with exact root URL; replaces direct PDF link; 0 currently linked schemes. | Dedicated scheme portal | None | 1 (`schemes`) | High (100%) |
| **21** | PMEGP | `https://www.kviconline.gov.in/` | `11` | `https://www.kviconline.gov.in/pmegpeportal/...jsp` | **93** | `Khadi and Village Industries Commission — PMEGP e-Portal`<br>`https://www.kviconline.gov.in/` | Source #93 exists with exact root URL; replaces internal JSP path; 0 currently linked schemes. | Dedicated e-Portal / application engine | None | 1 (`schemes`) | High (100%) |
| **23** | PM-AJAY | `https://socialjustice.gov.in/` | `12` | `https://socialjustice.gov.in/schemes/104` | **109** | `Department of Social Justice and Empowerment — PM-AJAY`<br>`https://socialjustice.gov.in/` | Source #109 exists with exact root URL and dedicated PM-AJAY name; 0 currently linked schemes. | Department portal / scheme page | None | 1 (`schemes`) | High (100%) |
| **24** | IGNOAPS (Sikkim) | `https://pensionscheme.sikkim.gov.in/` | `13` | `https://www.myscheme.gov.in/schemes/ignoaps-sikkim` | **146** | `Government of Sikkim — Pension Scheme`<br>`https://pensionscheme.sikkim.gov.in/` | Source #146 exists with exact official state URL; replaces myScheme redirect; 0 currently linked schemes. | State pension portal | None | 1 (`schemes`) | High (100%) |
| **26** | PM-KUSUM | `https://pmkusum.mnre.gov.in/` | `16` | `https://pmkusum.mnre.gov.in/Publicity.html` | **29** | `Ministry of New and Renewable Energy — PM-KUSUM Portal`<br>`https://pmkusum.mnre.gov.in/` | Source #29 exists with exact root URL; replaces `/Publicity.html`; 0 currently linked schemes. | Dedicated scheme portal | None | 1 (`schemes`) | High (100%) |
| **27** | PM Ujjwala Yojana (PMUY) | `https://www.pmuy.gov.in/` | `17` | `https://www.pmuy.gov.in/about.html` | **69** | `Pradhan Mantri Ujjwala Yojana Official Portal`<br>`https://www.pmuy.gov.in/` | Source #69 exists with exact root URL; replaces `/about.html`; 0 currently linked schemes. | Dedicated scheme portal | None | 1 (`schemes`) | High (100%) |
| **28** | PM-SYM | `https://labour.gov.in/` | `18` | `https://labour.gov.in/FAQ-0` | **86** | `Ministry of Labour and Employment — PM-SYM`<br>`https://labour.gov.in/` | Source #86 exists with exact root URL; replaces FAQ subpath; 0 currently linked schemes. | Apex ministry portal | None | 1 (`schemes`) | High (100%) |
| **29** | NMMSS | `https://scholarships.gov.in/` | `19` | `https://scholarships.gov.in/Students` | **42** | `National Scholarship Portal — NMMSS`<br>`https://scholarships.gov.in/` | Source #42 exists with exact URL and dedicated NMMSS name; 0 currently linked schemes. | National Scholarship Portal root | None | 1 (`schemes`) | High (100%) |
| **30** | CSSS | `https://scholarships.gov.in/` | `19` | `https://scholarships.gov.in/Students` | **43** | `National Scholarship Portal — CSSS`<br>`https://scholarships.gov.in/` | Source #43 exists with exact URL and dedicated CSSS name; 0 currently linked schemes. | National Scholarship Portal root | None | 1 (`schemes`) | High (100%) |
| **31** | PMMVY | `https://pmmvy.wcd.gov.in/` | `20` | `https://wcd.gov.in/offerings/...` | **68** | `Ministry of Women and Child Development — PMMVY Portal`<br>`https://pmmvy.wcd.gov.in/` | Source #68 exists with exact dedicated citizen portal URL; 0 currently linked schemes. | Dedicated citizen DBT portal | None | 1 (`schemes`) | High (100%) |
| **32** | Janani Suraksha Yojana (JSY) | `https://nhm.gov.in/` | `21` | `https://www.nhm.gov.in/nhm/...` | **58** | `National Health Mission — Janani Suraksha Yojana`<br>`https://nhm.gov.in/` | Source #58 exists with exact root URL and matching name; 0 currently linked schemes. | National Health Mission portal | None | 1 (`schemes`) | High (100%) |
| **33** | JSSK | `https://nhm.gov.in/` | `22` | `https://www.nhm.gov.in/nhm/...` | **59** | `National Health Mission — JSSK`<br>`https://nhm.gov.in/` | Source #59 exists with exact root URL and dedicated JSSK name; 0 currently linked schemes. | National Health Mission portal | None | 1 (`schemes`) | High (100%) |
| **36** | PM Vishwakarma | `https://pmvishwakarma.gov.in/` | `25` | `https://msme.gov.in/...pdf` | **94** | `Ministry of MSME — PM Vishwakarma Portal`<br>`https://pmvishwakarma.gov.in/` | Source #94 exists with exact root portal URL; replaces PDF link; 0 currently linked schemes. | Dedicated national scheme portal | None | 1 (`schemes`) | High (100%) |
| **116** | Pudhumai Penn | `https://pudhumaimaipen.tn.gov.in/` (Typo) | `128` | `https://pudhumaipenn.tn.gov.in/` | **128** (Unchanged) | `Government of Tamil Nadu – Pudhumai Penn Portal`<br>`https://pudhumaipenn.tn.gov.in/` | Update `application_url` to `https://pudhumaipenn.tn.gov.in/` to resolve domain typo. | State Higher Education Assurance portal | `SchemeVersion` #136 (`source_url`) | 1 (`schemes`), 1 (`scheme_versions`) | High (100%) |
| **9** | PM YASASVI (College) | `https://scholarships.gov.in/` | `None` | `None` | `None` (Hold) | Awaiting dedicated source registration | Ministry of Social Justice / NSP. Unverified fixture record. | General scholarship portal | None | 0 (Unmutated) | Ambiguous / Human Review |
| **10** | PM YASASVI (Scholarship) | `https://scholarships.gov.in/` | `None` | `None` | `None` (Hold) | Awaiting dedicated source registration | Ministry of Social Justice / NSP. Near-duplicate fixture record. | General scholarship portal | None | 0 (Unmutated) | Ambiguous / Human Review |

---

## 4. Phase 3 — Native Backup Verification

- **Backup Path:** `C:\GitHub\LifeNavigator-AI\backups\lifenavigator_native_stage6c_pre_mutation_20261018_122120.dump`
- **Backup Format:** PostgreSQL custom format (`-Fc`) via PostgreSQL 17.10 native client tools
- **File Size:** `391,354` bytes (~382.2 KB)
- **SHA-256 Hash:** `b64a24510ddfa7ef547f9dc0515b3298f38518ba58e2f9a7f349ec928086d32f`
- **Table of Contents (TOC) Listing:** 115 entries verified via `pg_restore --list`.
- **TOC Data Verification:** `TABLE DATA public.schemes`, `TABLE DATA public.scheme_sources`, `TABLE DATA public.scheme_documents`, `TABLE DATA public.scheme_document_chunks`, `TABLE DATA public.scheme_versions`, `TABLE DATA public.users`, `TABLE DATA public.user_profiles`, `TABLE DATA public.eligibility_rules`, `TABLE DATA public.alembic_version` all verified present.
- **Current Alembic Revision:** `3c1a2b3c4d5e`
- **Database Status:** Strictly read-only; zero mutations executed.

---

## 5. Phase 4 — Execution Plan (Awaiting Human Authorization)

```sql
BEGIN;

-- 1. Correct Pudhumai Penn application URL domain typo
UPDATE schemes
SET application_url = 'https://pudhumaipenn.tn.gov.in/'
WHERE id = 116;

-- Correct SchemeVersion 136 source_url typo
UPDATE scheme_versions
SET source_url = 'https://pudhumaipenn.tn.gov.in/'
WHERE scheme_id = 116 AND version_number = 1;

-- 2. Re-link 19 schemes to existing dedicated matching SchemeSource records
UPDATE schemes SET source_id = 120 WHERE id = 7;
UPDATE schemes SET source_id = 41 WHERE id = 13;
UPDATE schemes SET source_id = 66 WHERE id = 15;
UPDATE schemes SET source_id = 67 WHERE id = 16;
UPDATE schemes SET source_id = 103 WHERE id = 17;
UPDATE schemes SET source_id = 57 WHERE id = 18;
UPDATE schemes SET source_id = 85 WHERE id = 20;
UPDATE schemes SET source_id = 93 WHERE id = 21;
UPDATE schemes SET source_id = 109 WHERE id = 23;
UPDATE schemes SET source_id = 146 WHERE id = 24;
UPDATE schemes SET source_id = 29 WHERE id = 26;
UPDATE schemes SET source_id = 69 WHERE id = 27;
UPDATE schemes SET source_id = 86 WHERE id = 28;
UPDATE schemes SET source_id = 42 WHERE id = 29;
UPDATE schemes SET source_id = 43 WHERE id = 30;
UPDATE schemes SET source_id = 68 WHERE id = 31;
UPDATE schemes SET source_id = 58 WHERE id = 32;
UPDATE schemes SET source_id = 59 WHERE id = 33;
UPDATE schemes SET source_id = 94 WHERE id = 36;

-- Verification check: assert remaining mismatches among active schemes is exactly 2 (Schemes 9 and 10)
SELECT count(*) FROM schemes s
JOIN scheme_sources src ON s.source_id = src.id
WHERE s.is_active = TRUE AND s.source_url != src.source_url;
-- Expected: 0

COMMIT;
```

### Dry-Run Rollback Script:
```sql
BEGIN;

UPDATE schemes SET application_url = 'https://pudhumaimaipen.tn.gov.in/' WHERE id = 116;
UPDATE scheme_versions SET source_url = 'https://pudhumaimaipen.tn.gov.in/' WHERE scheme_id = 116 AND version_number = 1;

UPDATE schemes SET source_id = NULL WHERE id = 7;
UPDATE schemes SET source_id = 3 WHERE id = 13;
UPDATE schemes SET source_id = 5 WHERE id = 15;
UPDATE schemes SET source_id = 6 WHERE id = 16;
UPDATE schemes SET source_id = 7 WHERE id = 17;
UPDATE schemes SET source_id = 8 WHERE id = 18;
UPDATE schemes SET source_id = 10 WHERE id = 20;
UPDATE schemes SET source_id = 11 WHERE id = 21;
UPDATE schemes SET source_id = 12 WHERE id = 23;
UPDATE schemes SET source_id = 13 WHERE id = 24;
UPDATE schemes SET source_id = 16 WHERE id = 26;
UPDATE schemes SET source_id = 17 WHERE id = 27;
UPDATE schemes SET source_id = 18 WHERE id = 28;
UPDATE schemes SET source_id = 19 WHERE id IN (29, 30);
UPDATE schemes SET source_id = 20 WHERE id = 31;
UPDATE schemes SET source_id = 21 WHERE id = 32;
UPDATE schemes SET source_id = 22 WHERE id = 33;
UPDATE schemes SET source_id = 25 WHERE id = 36;

COMMIT;
```

---

## 6. Phase 5 — Execution Verification & Post-Mutation Audit Sign-Off

### 6.1 Execution Execution Timestamp: 2026-10-18 15:25:52 UTC+05:30
- **Execution Script:** `scripts/execute_stage6c_corrections.py --execute`
- **Transaction Mode:** Single atomic PostgreSQL transaction (`BEGIN ... COMMIT`)
- **Execution Result:** Success (Exit Code 0). All assertions passed; committed.

### 6.2 Pre-Execution Backups Preserved
1. `backups/lifenavigator_native_stage6c_pre_mutation_20261018_122120.dump`
   - Size: `391,354` bytes
   - SHA-256: `b64a24510ddfa7ef547f9dc0515b3298f38518ba58e2f9a7f349ec928086d32f`
2. `backups/lifenavigator_native_stage6c_pre_execution_fresh_20261018_152512.dump`
   - Size: `391,354` bytes
   - SHA-256: `6c3bf9240082a02f3ffafbe8f4a3427f173bef04e19169ac86924a92bf914932`

### 6.3 Post-Mutation Database Verification
- **Alembic Revision:** `3c1a2b3c4d5e` (strictly unchanged)
- **Table Counts Invariance:**
  - `schemes`: 130 (125 active, 5 inactive)
  - `scheme_sources`: 151 (all 151 active)
  - `scheme_documents`: 125
  - `scheme_document_chunks`: 151
  - `scheme_versions`: 156
  - `users`: 17
  - `user_profiles`: 10
  - `eligibility_rules`: 7
- **Row Updates Applied:**
  - Scheme 116 (`schemes.application_url`): updated to `https://pudhumaipenn.tn.gov.in/` (1 row)
  - SchemeVersion 136 (`scheme_versions.source_url`): updated to `https://pudhumaipenn.tn.gov.in/` (1 row)
  - 19 Schemes (`schemes.source_id`): re-linked to dedicated sources (19 rows)
  - Total rows updated: exactly 21 rows across database
- **Schemes 9 & 10 (PM YASASVI):** Strictly unchanged (`source_id = NULL`, `source_url = NULL`, `eligibility_verification_status = 'unverified'`).
- **Remaining Active Source Mismatches:** Exactly 2 (Schemes 9 and 10). Down from 21 to 2.
- **Regression Test Matrix:** 37 of 37 passed (`pytest` test suite: source-sync, retrieval, dataset, two-profile audit, eligibility engine, catalogue expansion).
