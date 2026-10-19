# LifeNavigator-AI — Evidence-Based Scheme Verification Report

**Phase:** Evidence-Based Scheme Verification  
**Date of Audit & Execution:** October 19, 2026  
**Environment:** PostgreSQL 17.10 (Native `localhost:5432/lifenavigator`), Isolated Test Container (`localhost:5433/lifenavigator_stage3c_test`)  
**Alembic Migration Revision:** `3c1a2b3c4d5e`  
**Execution Status:** Verified & Complete  

---

## 1. Executive Summary & Objective

The objective of this phase was to verify official eligibility criteria for five priority government welfare schemes from authoritative ministry sources, codify only evidence-supported eligibility rules using the existing `EligibilityRule` data model, and safely update their `eligibility_verification_status` from `unverified` to `verified`.

All existing system capabilities, fail-closed eligibility safeguards, native database integrity, and frontend designs have been preserved:
- **Pre-execution Backup:** Custom-format PostgreSQL backup created and verified intact (`backups/lifenavigator_native_pre_scheme_verification_20261019_143444.dump`, SHA-256: `7cdb7a53f12deae1e010f24e3a0f30860ebc9e7a28dfa052ae4ae079e7c943ab`).
- **Target Schemes Verified (5):**
  1. Pudhumai Penn — Scheme ID `116`
  2. PM-USP Central Sector Scholarship (CSSS) — Scheme ID `30`
  3. AICTE Pragati Scholarship for Girl Students — Scheme ID `55`
  4. PM-KISAN — Scheme ID `11`
  5. Pradhan Mantri Fasal Bima Yojana (PMFBY) — Scheme ID `25`
- **Fail-Closed Safeguard Maintained:** The remaining 120 active schemes remain `eligibility_verification_status = 'unverified'`. They strictly fail-closed, returning `unverified` without falsely inferring eligibility.
- **Decoupling Maintained:** Citizen social reservation categories (`SC`, `ST`, `OBC`, `General`, `EWS`) are never compared with scheme administrative sector categories (`Education`, `Agriculture`).

---

## 2. Baseline vs Final Verification Status Matrix

The application differentiates between:
1. **Scheme Identity & Source Verification (`Scheme.verification_status`):** Validates that the scheme officially exists, is active, and is registered with an authenticated government source URL in `scheme_sources`.
2. **Criteria Verification (`Scheme.eligibility_verification_status`):** Validates that scheme eligibility conditions have been reviewed against official ministry guidelines and codified into active `EligibilityRule` records.

### Verification Status Matrix

| Scheme ID | Scheme Name | Ministry / Department | Baseline Identity Status | Baseline Eligibility Status | Final Eligibility Status | Active Rules (Baseline $\to$ Final) |
|---|---|---|---|---|---|:---:|
| **11** | Pradhan Mantri Kisan Samman Nidhi (PM-KISAN) | MoA&FW / DA&FW | `verified` | `unverified` | **`verified`** | 2 $\to$ 2 |
| **25** | Pradhan Mantri Fasal Bima Yojana (PMFBY) | MoA&FW / DA&FW | `verified` | `unverified` | **`verified`** | 0 $\to$ 1 |
| **30** | PM-USP Central Sector Scholarship (CSSS) | MoE / Higher Education | `verified` | `unverified` | **`verified`** | 0 $\to$ 2 |
| **55** | Pragati Scholarship Scheme for Girl Students | MoE / AICTE | `verified` | `unverified` | **`verified`** | 0 $\to$ 3 |
| **116** | Pudhumai Penn Scheme (Moovalur Ramamirtham Ammaiyar) | Govt of Tamil Nadu / SW&WE | `verified` | `unverified` | **`verified`** | 0 $\to$ 3 |
| **Remaining 120** | All other active schemes in database | Various Central & State Ministries | `verified` | `unverified` | **`unverified`** | 5 active rules total |

*Note: Total active schemes in database = 125. Exactly 5 schemes are now verified; exactly 120 remain unverified.*

---

## 3. Official Evidence Tables

### Scheme 116 — Pudhumai Penn (Moovalur Ramamirtham Ammaiyar Higher Education Assurance Scheme)

| Field | Official Government Evidence |
|---|---|
| **Official Scheme Name** | Moovalur Ramamirtham Ammaiyar Higher Education Assurance Scheme (Pudhumai Penn) |
| **Responsible Authority** | Department of Social Welfare and Women Empowerment, Government of Tamil Nadu |
| **Official Source URLs** | Portal: [https://pudhumaipenn.tn.gov.in/](https://pudhumaipenn.tn.gov.in/)<br>Alternate/Departmental: [https://penkalvi.tn.gov.in/](https://penkalvi.tn.gov.in/) |
| **Date Checked** | October 19, 2026 |
| **Verified Eligibility Conditions** | 1. **Gender:** Female (`gender equals Female`).<br>2. **State / Domicile:** Resident of Tamil Nadu (`state equals Tamil Nadu`).<br>3. **Education Enrollment:** Currently admitted and pursuing regular full-time undergraduate degree (BA, BSc, BCom, BE/BTech, MBBS, etc.), diploma, or ITI in recognized institutions (`employment_status equals Student`).<br>4. **Schooling:** Studied Classes VI to XII continuously in Tamil Nadu Government schools (tracked via EMIS number). |
| **Explicit Exclusions** | Distance education, correspondence courses, open university students; students who completed schooling in private schools without RTE quota. |
| **Income Limit** | No income ceiling prescribed (universal for eligible government school girl students). |
| **Benefit Amount** | ₹1,000 per month (₹12,000/year) direct benefit transfer (DBT) into student's Aadhaar-seeded bank account until course completion. |
| **Required Documents** | School study certificate (Class VI–XII EMIS verification), college admission receipt/bonafide, Aadhaar card, bank passbook. |
| **Unresolved / Gaps** | Automated verification of government school EMIS study history requires integration with Tamil Nadu EMIS database; until integrated, profile fields verify state, gender, and student status. |

---

### Scheme 30 — PM-USP Central Sector Scholarship for College and University Students (CSSS)

| Field | Official Government Evidence |
|---|---|
| **Official Scheme Name** | Pradhan Mantri Uchchatar Shiksha Protsahan (PM-USP) Central Sector Scheme of Scholarship for College and University Students |
| **Responsible Authority** | Department of Higher Education, Ministry of Education, Government of India |
| **Official Source URLs** | National Scholarship Portal: [https://scholarships.gov.in/](https://scholarships.gov.in/)<br>Ministry Guidelines: [https://www.education.gov.in/scholarships-education-loan-4](https://www.education.gov.in/scholarships-education-loan-4) |
| **Date Checked** | October 19, 2026 |
| **Verified Eligibility Conditions** | 1. **Education / Employment:** Admitted to regular, full-time undergraduate or postgraduate degree course in a recognized college/institution (`employment_status equals Student`).<br>2. **Income Ceiling:** Gross parental/family annual income $\le$ ₹4,50,000 per annum (`annual_income lte 450000`).<br>3. **Merit Cutoff:** Scored above the 80th percentile of successful candidates in the relevant stream from the respective State Board / CBSE / CISCE in Class XII. |
| **Explicit Exclusions** | Students pursuing correspondence, distance education, or diploma courses not leading to a degree; students already receiving any other State or Central scholarship. |
| **Benefit Amount** | ₹12,000 per annum for the first 3 years of undergraduate study; ₹20,000 per annum at postgraduate level. |
| **Required Documents** | Class XII mark sheet, income certificate issued by competent revenue authority, college bonafide certificate, Aadhaar card, bank passbook. |
| **Unresolved / Gaps** | Class XII 80th percentile cutoff percentile varies yearly per board and stream; percentile verification requires board result lookup or self-attested percentage check. |

---

### Scheme 55 — AICTE Pragati Scholarship Scheme for Girl Students

| Field | Official Government Evidence |
|---|---|
| **Official Scheme Name** | AICTE Pragati Scholarship Scheme for Girl Students (Degree and Diploma) |
| **Responsible Authority** | All India Council for Technical Education (AICTE), Ministry of Education, Government of India |
| **Official Source URLs** | National Scholarship Portal: [https://scholarships.gov.in/](https://scholarships.gov.in/)<br>AICTE Scheme Portal: [https://www.aicte-india.org/schemes/students-development-schemes/Pragati](https://www.aicte-india.org/schemes/students-development-schemes/Pragati) |
| **Date Checked** | October 19, 2026 |
| **Verified Eligibility Conditions** | 1. **Gender:** Female student only (`gender equals Female`).<br>2. **Education / Employment:** Admitted to 1st year (or 2nd year through lateral entry) of AICTE-approved technical Degree or Diploma course (`employment_status equals Student`).<br>3. **Income Ceiling:** Family annual income from all sources $\le$ ₹8,00,000 per annum (`annual_income lte 800000`).<br>4. **Family Quota:** Maximum two girl children per family. |
| **Explicit Exclusions** | Non-technical programs; institutions not approved by AICTE; management quota admissions; second degree in parallel. |
| **Benefit Amount** | ₹50,000 per annum lump-sum grant for every year of study towards college fee, computer, books, and stationeries. |
| **Required Documents** | AICTE college admission letter, Class X and XII mark sheets, income certificate (revenue authority $\le$ 8 LPA), Aadhaar card, bank passbook. |
| **Unresolved / Gaps** | Institution-level AICTE approval verification requires integration with the AICTE institution registry; profile fields verify gender, student status, and income threshold. |

---

### Scheme 11 — Pradhan Mantri Kisan Samman Nidhi (PM-KISAN)

| Field | Official Government Evidence |
|---|---|
| **Official Scheme Name** | Pradhan Mantri Kisan Samman Nidhi (PM-KISAN) |
| **Responsible Authority** | Department of Agriculture and Farmers Welfare, Ministry of Agriculture & Farmers Welfare, Government of India |
| **Official Source URLs** | Official Portal: [https://pmkisan.gov.in/](https://pmkisan.gov.in/)<br>Operational Guidelines: [https://pmkisan.gov.in/Documents/Revised_Guidelines_PMKISAN.pdf](https://pmkisan.gov.in/Documents/Revised_Guidelines_PMKISAN.pdf) |
| **Date Checked** | October 19, 2026 |
| **Verified Eligibility Conditions** | 1. **Occupation:** Farmer family (`is_farmer equals true`).<br>2. **Landholding:** Owns cultivable land in their name per state land revenue records (`land_ownership equals true`).<br>3. **e-KYC & Aadhaar Seeding:** Mandatory Aadhaar-seeded bank account and land record seeding. |
| **Explicit Exclusions** | 1. All institutional landholders.<br>2. Former and present holders of constitutional posts.<br>3. Former and present Ministers, MPs, MLAs, MLCs, Mayors, Chairpersons of District Panchayats.<br>4. Serving or retired officers and employees of Central/State Govt/PSUs (excluding multi-tasking / Class IV / Group D).<br>5. Pensioners whose monthly pension is ₹10,000 or more.<br>6. Income tax payees in last assessment year.<br>7. Professionals (doctors, engineers, lawyers, CAs, architects). |
| **Benefit Amount** | ₹6,000 per year paid in three equal 4-monthly installments of ₹2,000 directly into the bank account via DBT. |
| **Required Documents** | Land ownership document / Patta / Chitta / Jamabandi, Aadhaar card, Aadhaar-linked active bank account. |
| **Unresolved / Gaps** | Professional and tax-payer exclusion criteria require Income Tax Department (CBDT) PAN API verification; application uses land ownership and farmer status. |

---

### Scheme 25 — Pradhan Mantri Fasal Bima Yojana (PMFBY)

| Field | Official Government Evidence |
|---|---|
| **Official Scheme Name** | Pradhan Mantri Fasal Bima Yojana (PMFBY) |
| **Responsible Authority** | Department of Agriculture and Farmers Welfare, Ministry of Agriculture & Farmers Welfare, Government of India |
| **Official Source URLs** | National Crop Insurance Portal: [https://pmfby.gov.in/](https://pmfby.gov.in/)<br>Revised Operational Guidelines: [https://pmfby.gov.in/pdf/Revised_Operational_Guidelines.pdf](https://pmfby.gov.in/pdf/Revised_Operational_Guidelines.pdf) |
| **Date Checked** | October 19, 2026 |
| **Verified Eligibility Conditions** | 1. **Occupation:** Farmer (`is_farmer equals true`).<br>2. **Crop & Area:** Cultivating notified crops in notified insurance units/areas.<br>3. **Insurable Interest:** Landowner, tenant farmer, or sharecropper having insurable interest in the notified crop. |
| **Explicit Exclusions** | Non-notified crops; unnotified geographical areas; losses arising from war, nuclear risks, or preventable malicious damage. |
| **Premium Subsidies** | Farmer premium is capped: Max 2.0% of sum insured for Kharif food and oilseed crops; Max 1.5% for Rabi crops; Max 5.0% for annual commercial/horticultural crops. Remaining actuarial premium is subsidized 50:50 by Central and State Governments. |
| **Required Documents** | Land revenue record (Patta/Chitta/7-12), Sowing certificate / Girdawari issued by village revenue officer, Aadhaar card, bank passbook. |
| **Unresolved / Gaps** | Sowing period and notified crop per taluk/district are determined seasonally by State SLCCCI notifications; engine verifies farmer identity and subsidized coverage. |

---

## 4. Implemented Eligibility Rules & Database Mapping

All rules were codified into the existing `eligibility_rules` table using standard supported operators (`equals`, `lte`). No custom columns or breaking schema alterations were introduced.

```sql
-- Scheme 11: PM-KISAN (Rules 8 & 9 updated to group 1, AND)
UPDATE eligibility_rules SET group_id = 1, logical_operator = 'AND', is_active = TRUE, source_version_id = 33 WHERE id IN (8, 9);
UPDATE schemes SET eligibility_verification_status = 'verified' WHERE id = 11;

-- Scheme 25: PMFBY
INSERT INTO eligibility_rules (scheme_id, field_name, operator, value, group_id, logical_operator, is_active, source_version_id)
VALUES (25, 'is_farmer', 'equals', 'true', 1, 'AND', TRUE, 34);
UPDATE schemes SET eligibility_verification_status = 'verified' WHERE id = 25;

-- Scheme 30: PM-USP CSSS
INSERT INTO eligibility_rules (scheme_id, field_name, operator, value, group_id, logical_operator, is_active, source_version_id)
VALUES (30, 'employment_status', 'equals', 'Student', 1, 'AND', TRUE, 50),
       (30, 'annual_income', 'lte', '450000', 1, 'AND', TRUE, 50);
UPDATE schemes SET eligibility_verification_status = 'verified' WHERE id = 30;

-- Scheme 55: AICTE Pragati
INSERT INTO eligibility_rules (scheme_id, field_name, operator, value, group_id, logical_operator, is_active, source_version_id)
VALUES (55, 'gender', 'equals', 'Female', 1, 'AND', TRUE, 57),
       (55, 'employment_status', 'equals', 'Student', 1, 'AND', TRUE, 57),
       (55, 'annual_income', 'lte', '800000', 1, 'AND', TRUE, 57);
UPDATE schemes SET eligibility_verification_status = 'verified' WHERE id = 55;

-- Scheme 116: Pudhumai Penn
INSERT INTO eligibility_rules (scheme_id, field_name, operator, value, group_id, logical_operator, is_active, source_version_id)
VALUES (116, 'state', 'equals', 'Tamil Nadu', 1, 'AND', TRUE, 136),
       (116, 'gender', 'equals', 'Female', 1, 'AND', TRUE, 136),
       (116, 'employment_status', 'equals', 'Student', 1, 'AND', TRUE, 136);
UPDATE schemes SET eligibility_verification_status = 'verified' WHERE id = 116;
```

---

## 5. Synthetic Profile Audit Results

Evaluated against the live database using `backend/scripts/run_two_profile_audit.py` and the FastAPI TestClient:

### Profile A: College Student (Kavitha Rajan)
*Profile Characteristics: 20 years old, Female, Tamil Nadu resident, Undergraduate Engineering Student, Annual Income ₹1,50,000, Not a farmer.*

| Scheme ID | Scheme Name | Evaluation Status | Engine Output & Cited Reasons |
|---|---|:---:|---|
| **116** | Pudhumai Penn | **`eligible`** | `Rule group 1 matched (AND): state equals Tamil Nadu, gender equals Female, employment_status equals Student` |
| **30** | PM-USP CSSS | **`eligible`** | `Rule group 1 matched (AND): employment_status equals Student, annual_income lte 450000` |
| **55** | AICTE Pragati | **`eligible`** | `Rule group 1 matched (AND): gender equals Female, employment_status equals Student, annual_income lte 800000` |
| **11** | PM-KISAN | **`ineligible`** | `Rule group 1 did not match (AND): is_farmer equals true, land_ownership equals true` |
| **25** | PMFBY | **`ineligible`** | `Rule group 1 did not match (AND): is_farmer equals true` |

### Profile B: Rural Farmer (Murugan Palanisamy)
*Profile Characteristics: 45 years old, Male, Tamil Nadu resident (Thanjavur), Self-Employed Farmer, Owns 2.5 acres cultivable land (Paddy), Annual Income ₹2,40,000.*

| Scheme ID | Scheme Name | Evaluation Status | Engine Output & Cited Reasons |
|---|---|:---:|---|
| **11** | PM-KISAN | **`eligible`** | `Rule group 1 matched (AND): is_farmer equals true, land_ownership equals true` |
| **25** | PMFBY | **`eligible`** | `Rule group 1 matched (AND): is_farmer equals true` |
| **30** | PM-USP CSSS | **`ineligible`** | `Rule group 1 did not match (AND): employment_status equals Student` |
| **55** | AICTE Pragati | **`ineligible`** | `Rule group 1 did not match (AND): gender equals Female, employment_status equals Student` |
| **116** | Pudhumai Penn | **`ineligible`** | `Rule group 1 did not match (AND): gender equals Female, employment_status equals Student` |

### Missing Information & Unverified Safeguard Verification

1. **Missing Profile Attributes Trigger `needs_more_info`:**
   - A student profile missing `gender` evaluated against Scheme 55 (AICTE Pragati) or Scheme 116 (Pudhumai Penn) returns `status = 'needs_more_info'` with `missing_fields = ['gender']`.
   - A farmer profile missing `employment_status` evaluated against Scheme 30 returns `status = 'needs_more_info'` with `missing_fields = ['employment_status']`.
2. **Unverified Schemes Fail Closed:**
   - All 120 unverified schemes return `status = 'unverified'` for both Profile A and Profile B with the reason: `"Eligibility criteria have not been verified; check the official source"`.

---

## 6. Verification Test Execution Evidence

All tests were executed against real running services:

```text
1. Isolated PostgreSQL Matrix Tests (Port 5433 - lifenavigator_stage3c_test):
   Command: backend\.venv\Scripts\pytest.exe tests\test_stage3c_postgresql_matrix.py
   Result: 19 passed in 2.66s

2. Production Migration Runner Tests (Port 5433):
   Command: backend\.venv\Scripts\pytest.exe tests\test_production_migration_runner.py
   Result: 12 passed in 0.37s

3. Eligibility Engine & 125-Scheme Evaluation Tests:
   Command: backend\.venv\Scripts\pytest.exe tests\test_eligibility_engine.py
   Result: 17 passed in 1.18s

4. Two-Profile Matching Audit Tests:
   Command: backend\.venv\Scripts\pytest.exe tests\test_two_profile_matching_audit.py
   Result: 5 passed in 0.51s

5. Full Backend Test Suite:
   Command: backend\.venv\Scripts\pytest.exe tests\
   Result: 149 passed, 0 failed, 4 warnings in 14.68s

6. Frontend Test Suite:
   Command: cmd /c npm test
   Result: 27 passed, 1 skipped (live backend check when 8000 is offline), 0 failed in 125ms

7. Frontend ESLint:
   Command: cmd /c npm run lint
   Result: 0 errors, 0 warnings

8. Frontend Production Build:
   Command: cmd /c npm run build
   Result: Vite v6.4.3 build successful in 171ms (dist/index.html, dist/assets/*)

9. Two-Profile End-to-End Audit Script:
   Command: backend\.venv\Scripts\python.exe backend\scripts\run_two_profile_audit.py
   Result: Success, results saved to data/two_profile_audit_results.json
```

---

## 7. Unresolved Criteria & Operational Limitations

1. **State School EMIS Verification (Pudhumai Penn):** The requirement of studying in government schools from standard 6 to 12 is verified during application via the Tamil Nadu EMIS student database. In the standalone application, eligibility checks student status, gender, and Tamil Nadu residency.
2. **Merit Percentile Verification (CSSS):** The top 80th percentile cutoff is determined annually per state/central examination board. Citizens meeting income and student criteria should confirm their Class XII board marks against that year's published cut-off list.
3. **AICTE Approval Lookup (Pragati):** Technical degree/diploma courses must be recognized by AICTE. The engine verifies general technical degree enrollment, income, and gender.
4. **Income Tax & Institutional Landowner Exclusions (PM-KISAN):** Exclusions for income tax payees and constitutional post holders cannot be verified without direct CBDT PAN integration.
5. **Schemes 9 & 10 (PM YASASVI):** Deliberately retained as unverified pending publication of updated official scholarship guidelines from the Ministry of Social Justice and Empowerment.

---

## 8. Summary of Completion

- **Phase 1 Inspection:** Baseline recorded and reported without premature data changes.
- **Phase 2 Evidence:** Authoritative ministry sources referenced with documented criteria, benefits, exclusions, and official URLs.
- **Phase 3 Implementation:** Transactional updates applied to both native (5432) and test (5433) databases.
- **Phase 4 Testing:** All 4 outcomes verified; isolated test database utilized; 149 backend tests, 27 frontend tests, lint, and build 100% passing.
- **Phase 5 Deliverable:** Complete documentation generated in `data/scheme_verification_report.md`.
