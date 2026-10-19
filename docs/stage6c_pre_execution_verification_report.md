# LifeNavigator-AI — Stage 6C Pre-Execution Verification Report

**Date:** 2026-10-18  
**Environment:** Windows (Native PostgreSQL 17.10)  
**Database:** `localhost:5432/lifenavigator`  
**Current Alembic Revision:** `3c1a2b3c4d5e` (Head)  
**Safety Gate Status:** All 9 Phase 1 safety checks PASSED. Awaiting explicit human authorization.  
**Database Mutation Status:** STRICTLY ZERO MUTATIONS PERSISTED. (Database remains 100% read-only).

---

## 1. Safety Check & Backup Verification Results

| Check Item | Parameter / Target | Actual Database / File State | Status |
| :--- | :--- | :--- | :---: |
| **Database Engine** | PostgreSQL native service | `PostgreSQL 17.10 on x86_64-windows` | **PASS** |
| **Alembic Revision** | `3c1a2b3c4d5e` | `3c1a2b3c4d5e` | **PASS** |
| **Backup File Exists** | `backups/lifenavigator_native_stage6c_pre_mutation_20261018_122120.dump` | File size: `391,354` bytes (~382.2 KB) | **PASS** |
| **Backup SHA-256** | `b64a24510ddfa7ef547f9dc0515b3298f38518ba58e2f9a7f349ec928086d32f` | `b64a24510ddfa7ef547f9dc0515b3298f38518ba58e2f9a7f349ec928086d32f` | **PASS** |
| **Backup Readability** | `pg_restore --list` | Valid custom-format TOC; 115 entries; all 10 key tables verified | **PASS** |
| **Schemes 9 & 10 State** | Unverified, unlinked fixture records | `source_id = NULL`, `source_url = NULL`, `status = unverified` | **PASS** |
| **Scheme 116 Application URL** | Fix domain typo (`pudhumaimaipen` -> `pudhumaipenn`) | Current: `https://pudhumaimaipen.tn.gov.in/` | **PASS** |
| **SchemeVersion 136 URL** | Scheme 116 Version 1 row | Row ID 136: current `source_url = 'https://pudhumaimaipen.tn.gov.in/'` | **PASS** |
| **19 Scheme Target Sources** | Active, exact matching URLs, 0 current links | All 19 `SchemeSource` records exist, active, URL match 100% | **PASS** |
| **Dry-Run Transaction** | Rollback dry-run with assertions | 21 rows affected inside transaction, all assertions passed, rolled back | **PASS** |

---

## 2. Baseline Row Counts

| Table Name | Baseline Row Count | Pre-Mutation Active State |
| :--- | :---: | :--- |
| `schemes` | **130** | 125 active, 5 inactive (duplicates / sunset) |
| `scheme_sources` | **151** | 151 active, 0 inactive |
| `scheme_documents` | **125** | 125 active extractions |
| `scheme_document_chunks` | **151** | 384-dim unit-norm vector embeddings |
| `scheme_versions` | **156** | 156 version history snapshots |
| `users` | **17** | Registered user records |
| `user_profiles` | **10** | Detailed citizen persona profiles |
| `eligibility_rules` | **7** | Dynamic eligibility DSL rules |
| `alembic_version` | **1** | Revision: `3c1a2b3c4d5e` |

---

## 3. The 19 Scheme Source Mappings Audit

All 19 schemes have corresponding `SchemeVersion v2` snapshots created during the Stage 3 catalogue expansion that already reference these exact target `SchemeSource` IDs. The proposed changes update the foreign key pointer `schemes.source_id` on the main `schemes` table so that it aligns with `Scheme.source_url` and `SchemeVersion v2`.

| Sch ID | Scheme Name | Current `source_id` & Name | Proposed `source_id` | Authoritative Target Source Name & URL | Semantic Category & Hierarchy |
| :---: | :--- | :--- | :---: | :--- | :--- |
| **7** | Indira Gandhi National Old Age Pension Scheme (IGNOAPS) | `NULL` | **120** | `NSAP Portal — IGNOAPS`<br>`https://nsap.nic.in/` | Apex national pension portal under MoRD |
| **13** | PM POSHAN | `3` (`.../aboutus.html`) | **41** | `PM POSHAN Official Portal`<br>`https://pmposhan.education.gov.in/` | Dedicated national nutrition scheme portal under MoE |
| **15** | Mission Shakti | `5` (`.../mission-shakti-guidelines...`) | **66** | `Ministry of Women and Child Development — Mission Shakti`<br>`https://wcd.gov.in/` | Administering ministry umbrella portal |
| **16** | Shakti Sadan | `6` (`.../women/shakti-sadan`) | **67** | `Ministry of Women and Child Development — Shakti Sadan`<br>`https://wcd.gov.in/` | Administering ministry dedicated component source |
| **17** | Assistance to Persons with Disabilities (ADIP) | `7` (`.../en/adip-scheme/`) | **103** | `Department of Empowerment of Persons with Disabilities — ADIP Scheme`<br>`https://depwd.gov.in/` | Administering department portal under MoSJE |
| **18** | Ayushman Bharat — PM-JAY | `8` (`myScheme` Hindi redirect) | **57** | `National Health Authority — PM-JAY`<br>`https://pmjay.gov.in/` | Dedicated apex national health assurance portal |
| **20** | PMKVY 4.0 | `10` (`.../PMKVY%204.0%20Guidelines.pdf`) | **85** | `PMKVY Official Portal`<br>`https://www.pmkvyofficial.org/` | Dedicated national skill development portal |
| **21** | PMEGP | `11` (`.../pmegphome/index.jsp`) | **93** | `Khadi and Village Industries Commission — PMEGP e-Portal`<br>`https://www.kviconline.gov.in/` | Authoritative statutory implementation agency under MSME |
| **23** | PM-AJAY | `12` (`.../schemes/104`) | **109** | `Department of Social Justice and Empowerment — PM-AJAY`<br>`https://socialjustice.gov.in/` | Administering department portal under MoSJE |
| **24** | IGNOAPS (Sikkim) | `13` (`myScheme` redirect) | **146** | `Government of Sikkim — Pension Scheme`<br>`https://pensionscheme.sikkim.gov.in/` | Authoritative state pension portal |
| **26** | PM-KUSUM | `16` (`.../Publicity.html`) | **29** | `Ministry of New and Renewable Energy — PM-KUSUM Portal`<br>`https://pmkusum.mnre.gov.in/` | Dedicated national solar scheme portal |
| **27** | PM Ujjwala Yojana (PMUY) | `17` (`.../about.html`) | **69** | `Pradhan Mantri Ujjwala Yojana Official Portal`<br>`https://www.pmuy.gov.in/` | Dedicated national clean energy LPG portal |
| **28** | PM-SYM | `18` (`.../FAQ-0`) | **86** | `Ministry of Labour and Employment — PM-SYM`<br>`https://labour.gov.in/` | Administering ministry portal |
| **29** | NMMSS | `19` (`.../Students`) | **42** | `National Scholarship Portal — NMMSS`<br>`https://scholarships.gov.in/` | Centralized national scholarship portal |
| **30** | CSSS | `19` (`.../Students`) | **43** | `National Scholarship Portal — CSSS`<br>`https://scholarships.gov.in/` | Centralized national scholarship portal |
| **31** | PMMVY | `20` (`.../pradhan-mantri-matru-vandana-yojana`) | **68** | `Ministry of Women and Child Development — PMMVY Portal`<br>`https://pmmvy.wcd.gov.in/` | Dedicated citizen DBT portal |
| **32** | Janani Suraksha Yojana (JSY) | `21` (`.../index1.php?...`) | **58** | `National Health Mission — Janani Suraksha Yojana`<br>`https://nhm.gov.in/` | Administering apex health mission portal |
| **33** | JSSK | `22` (`.../index4.php?...`) | **59** | `National Health Mission — JSSK`<br>`https://nhm.gov.in/` | Administering apex health mission portal |
| **36** | PM Vishwakarma | `25` (`.../Scheme%20booklet%20Eng...pdf`) | **94** | `Ministry of MSME — PM Vishwakarma Portal`<br>`https://pmvishwakarma.gov.in/` | Dedicated national artisan scheme portal |

---

## 4. Scheme 116 URL Typo Correction

- **Scheme ID:** 116 (`Moovalur Ramamirtham Ammaiyar Higher Education Assurance Scheme (Pudhumai Penn)`)
- **Current `schemes.application_url`:** `https://pudhumaimaipen.tn.gov.in/` (Defect: extra `"mai"` in subdomain)
- **Target `schemes.application_url`:** `https://pudhumaipenn.tn.gov.in/`
- **Associated `scheme_versions` Row:** Row ID 136 (`scheme_id = 116`, `version_number = 1`)
- **Current `scheme_versions.source_url`:** `https://pudhumaimaipen.tn.gov.in/`
- **Target `scheme_versions.source_url`:** `https://pudhumaipenn.tn.gov.in/`
- **Linked Source in Database:** `SchemeSource #128` (`Government of Tamil Nadu – Pudhumai Penn Portal`, `https://pudhumaipenn.tn.gov.in/`) is already active and linked to Scheme 116.

---

## 5. Untouched and Preserved Entities

- **Schemes 9 and 10 (PM YASASVI):** Kept strictly unchanged (`source_id = NULL`, `source_url = NULL`, `verification_status = NULL`, `eligibility_verification_status = 'unverified'`).
- **Old `SchemeSource` Records:** Sources 3, 5, 6, 7, 8, 10, 11, 12, 13, 16, 17, 18, 19, 20, 21, 22, 25 are preserved without deletion or modification. Total `scheme_sources` remains exactly 151.
- **Alembic Migration State:** Remains `3c1a2b3c4d5e`.
- **Other Tables:** Zero modifications to `eligibility_rules`, `user_profiles`, `users`, `scheme_documents`, `scheme_document_chunks`.

---

## 6. Execution Script Ready

The idempotent, transactional script `scripts/execute_stage6c_corrections.py` has been verified via full dry-run with rollback. When executed with `--execute`, it will execute the exact updates inside a single PostgreSQL transaction with strict assertion guards and roll back on any mismatch.
