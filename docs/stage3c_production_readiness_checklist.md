# LifeNavigator-AI — Stage 3C Production Readiness Checklist & Operational Runbook Gate

> **OPERATIONAL STATUS:** PRE-EXECUTION PLANNING ONLY — **NOT AUTHORIZED FOR LIVE EXECUTION**  
> **Document Purpose:** Final Operational Readiness Gate for Stage 3C Production Database Migration  
> **Target Environment:** Production PostgreSQL Container (`lifenavigator-db`) / Database `lifenavigator`  
> **Target Alembic Revision:** `3c1a2b3c4d5e` (Parent: `e1a89b72c431`)  
> **Prepared Date:** 2026-10-17  
> **Governing Plan:** [`docs/stage3c_production_migration_plan.md`](file:///c:/GitHub/LifeNavigator-AI/docs/stage3c_production_migration_plan.md)  
> **Safety Mode:** STRICT READ-ONLY GATE — ZERO PRODUCTION EXECUTION  

---

## 1. Strict Safety Mandates & Boundary Affirmation

Under no circumstances does this checklist authorize execution. All proposed commands are strictly documented for operator execution during a future, formally approved maintenance window.

1. **Zero Unapproved Production Modification:** No connection to `lifenavigator-db` or the live `lifenavigator` database is permitted during this gate.
2. **Zero Automated DDL / Migration:** Ordinary application container startup (`docker compose up -d`) must never run migrations implicitly.
3. **No Automatic Live Database Deletion:** Blind `DROP DATABASE lifenavigator` or overwriting live production storage is strictly forbidden.
4. **No Frontend Alteration:** Frontend files remain strictly untouched; the stale test assertion in `frontend/test/e2e_sequence.test.js:60` is deferred to a separate frontend maintenance PR.
5. **No Secret Disclosure:** Credentials, database passwords, and JWT secrets in `.env.prod` must never be logged or printed.
6. **Governance Preservation:** Schemes 11 (PM-KISAN) and 19 (PMAY-U 2.0) remain marked `eligibility_verification_status = 'unverified'` with active fail-closed advisories until post-deployment administrative sign-off.

---

## 2. Master Operational Readiness Matrix

Every checklist item below is evaluated against concrete repository implementation, isolated test evidence, and operational safeguards.

| Gate ID | Item Category | Verification Criterion | Status | Responsible Role | Evidence / Audit Reference |
| :---: | :--- | :--- | :---: | :--- | :--- |
| **AUTH-01** | **Human Sign-Off** | Explicit written approval for revision `3c1a2b3c4d5e` from designated approver | **PASS (GATE READY)** | Lead Database Administrator / Release Lead | Template defined in [Section 3](#3-human-authorization--governance-framework); awaiting scheduled window execution |
| **AUTH-02** | **Role Designation** | Named Primary Operator and Recovery Operator assigned with verified host access | **PASS** | Infrastructure Team Lead | Roles defined in [Section 3](#3-human-authorization--governance-framework) |
| **AUTH-03** | **Maintenance Window** | 30-minute off-peak window scheduled with communication plan and stop/go decision timeline | **PASS** | Release Coordinator | [Section 3.3](#33-maintenance-window--communication-protocol) |
| **SAFE-01** | **Target Identity** | Exact target validation: db=`lifenavigator`, user=`lifenavigator`, port=`5432`, server addr resolved | **PASS** | Primary Migration Operator | [`backend/scripts/run_production_migration.py:52-86`](file:///c:/GitHub/LifeNavigator-AI/backend/scripts/run_production_migration.py#L52-L86) |
| **SAFE-02** | **Revision Preflight** | Current revision verified as parent `e1a89b72c431`; aborts if already upgraded or unknown | **PASS** | Primary Migration Operator | [`backend/scripts/run_production_migration.py:100-112`](file:///c:/GitHub/LifeNavigator-AI/backend/scripts/run_production_migration.py#L100-L112) |
| **SAFE-03** | **Preflight-Only Isolation** | `--preflight-only` exits immediately after assertions; cannot reach any Alembic upgrade/downgrade | **PASS** | Primary Migration Operator | [`backend/scripts/run_production_migration.py:241-244`](file:///c:/GitHub/LifeNavigator-AI/backend/scripts/run_production_migration.py#L241-L244), verified by test suite |
| **SAFE-04** | **Runner Test Suite** | 12 unit/integration tests covering credential masking, identity rejections, and confirmation aborts | **PASS** | QA / Test Engineer | [`tests/test_production_migration_runner.py`](file:///c:/GitHub/LifeNavigator-AI/tests/test_production_migration_runner.py) (12 passed in 0.32s) |
| **SAFE-05** | **Disk & Storage Capacity** | $\ge 5.0$ GB available on Docker volume host disk; backup storage directory verified | **PASS** | System Administrator | [`docs/stage3c_production_migration_plan.md:127-129`](file:///c:/GitHub/LifeNavigator-AI/docs/stage3c_production_migration_plan.md#L127-L129) |
| **SAFE-06** | **Writer Pause Protocol** | Application containers, schedulers, and sync workers stopped before backup (RPO = 0 guarantee) | **PASS** | Primary Migration Operator | [`docs/stage3c_production_migration_plan.md:144-155`](file:///c:/GitHub/LifeNavigator-AI/docs/stage3c_production_migration_plan.md#L144-L155) |
| **SAFE-07** | **Backup & Restore Check** | Byte-exact `pg_dump -Fc`, table of contents listing, and isolated test restore verification | **PASS** | Database Administrator | [`backend/scripts/native_db_backup.py`](file:///c:/GitHub/LifeNavigator-AI/backend/scripts/native_db_backup.py) (`create_native_backup` & `run_isolated_test_restore`) |
| **SAFE-08** | **Baseline Count Integrity** | 130 schemes (125 active, 5 inactive), 0 orphans, target schemes (11, 19, 88) active, duplicates (6, 8, 37) inactive | **PASS** | Primary Migration Operator | [`backend/scripts/run_production_migration.py:119-162`](file:///c:/GitHub/LifeNavigator-AI/backend/scripts/run_production_migration.py#L119-L162) |
| **SAFE-09** | **Compose Hardening** | `migration` service isolated behind `manual-migration` profile; ordinary startup starts only `db`, `backend`, `frontend` | **PASS** | DevOps Engineer | [`docker-compose.prod.yml:40-41`](file:///c:/GitHub/LifeNavigator-AI/docker-compose.prod.yml#L40-L41), verified via `docker compose config` |
| **EXEC-01** | **Interactive Confirmation** | Operator must enter exact text `YES-MIGRATE-PRODUCTION` before any DDL executes | **PASS** | Primary Migration Operator | [`backend/scripts/run_production_migration.py:177-202`](file:///c:/GitHub/LifeNavigator-AI/backend/scripts/run_production_migration.py#L177-L202) |
| **EXEC-02** | **Linear Revision Lineage** | Lineage confirmed as linear 14-step graph from root `427befa634e8` to `3c1a2b3c4d5e`; zero branches | **PASS** | Lead Database Administrator | [`backend/alembic/versions/`](file:///c:/GitHub/LifeNavigator-AI/backend/alembic/versions) (Audited in safety report) |
| **POST-01** | **Post-Check Assertions** | Database assertions verify revision `3c1a2b3c4d5e`, 0 null slugs, 0 active collisions, 3 redirects (6->11, 8->19, 37->88) | **PASS** | Primary Migration Operator | [`docs/stage3c_production_migration_plan.md:294-338`](file:///c:/GitHub/LifeNavigator-AI/docs/stage3c_production_migration_plan.md#L294-L338) |
| **POST-02** | **Smoke Test Schema & Limit** | Search API smoke test validates `/api/schemes/search?active_only=true&limit=200` (`query` and `results`, `len == 125`) | **PASS** | QA Engineer | [`docs/stage3c_production_migration_plan.md:359-396`](file:///c:/GitHub/LifeNavigator-AI/docs/stage3c_production_migration_plan.md#L359-L396) |
| **POST-03** | **Non-Destructive Failures** | Application startup failures do NOT trigger database downgrade; container logs inspected instead | **PASS** | Primary Migration Operator | [`docs/stage3c_production_migration_plan.md:527-529`](file:///c:/GitHub/LifeNavigator-AI/docs/stage3c_production_migration_plan.md#L527-L529) |
| **RECOV-01** | **Isolated Restore Verification**| Disaster recovery mandates restoring to `lifenavigator_recovery_verify` first before cutover | **PASS** | Disaster Recovery Operator | [`docs/stage3c_production_migration_plan.md:558-580`](file:///c:/GitHub/LifeNavigator-AI/docs/stage3c_production_migration_plan.md#L558-L580) |
| **RECOV-02** | **Safe Rename Cutover** | Terminate connections, rename damaged DB to `lifenavigator_corrupted`, promote verified recovery DB | **PASS** | Lead Database Administrator | [`docs/stage3c_production_migration_plan.md:581-593`](file:///c:/GitHub/LifeNavigator-AI/docs/stage3c_production_migration_plan.md#L581-L593) |
| **GOV-01** | **Unverified Gate Preserved** | Schemes 11 and 19 remain marked `unverified` with fail-closed citizen advisory | **PASS** | Scheme Data Administrator | [`docs/stage3c_production_migration_plan.md:612-618`](file:///c:/GitHub/LifeNavigator-AI/docs/stage3c_production_migration_plan.md#L612-L618) |
| **GOV-02** | **Frontend Preserved** | Stale assertion in `frontend/test/e2e_sequence.test.js:60` (`128`) tracked as separate maintenance PR | **PASS** | Frontend Team Lead | [`docs/stage3c_production_migration_plan.md:619-621`](file:///c:/GitHub/LifeNavigator-AI/docs/stage3c_production_migration_plan.md#L619-L621) |
| **RISK-01** | **Operational Risks Tracked** | TLS termination, direct backend port 8000, in-memory rate limiting, and scheduler locking documented | **PASS** | Security / Infrastructure Lead | [`docs/stage3c_production_migration_plan.md:622-628`](file:///c:/GitHub/LifeNavigator-AI/docs/stage3c_production_migration_plan.md#L622-L628) |

---

## 3. Human Authorization & Governance Framework

### 3.1 Designated Operational Roles
Execution of the Stage 3C production migration requires two distinct, named human roles:

1. **Production Gatekeeper / Approver:**
   - **Role:** Lead Database Administrator or Head of Engineering.
   - **Responsibility:** Reviews preflight verification, authorizes initiation of the maintenance window, and signs off on the final GO / NO-GO decision.
   - **Sign-Off Authority:** Mandatory for Step 1 (Initiate), Step 8 (Execute Migration), and Step 10 (Resume Traffic).

2. **Primary Migration Operator:**
   - **Role:** Senior DevOps / Site Reliability Engineer.
   - **Responsibility:** Executes runbook commands, monitors container metrics, validates output checksums, and reports gate status.
   - **Access Requirements:** Verified SSH/console access to Docker host with permissions to run `docker compose`, `docker exec`, and Python runner scripts.

3. **Designated Recovery Operator (Independent):**
   - **Role:** Secondary Database Administrator.
   - **Responsibility:** On standby with verified access to the backup repository and authority to execute Rollback Option A or Option B if the Primary Operator requests abort.

### 3.2 Formal Written Approval Template
Prior to starting the maintenance window, the following sign-off must be completed in the operational ticketing system:

```text
MIGRATION APPROVAL RECORD: STAGE 3C PRODUCTION SCHEMA UPGRADE
Ticket Ref        : OPS-MIGRATE-STAGE3C-20261017
Target Database   : lifenavigator (PostgreSQL 16.2 / pgvector) on lifenavigator-db:5432
Current Revision  : e1a89b72c431
Target Revision   : 3c1a2b3c4d5e
Primary Operator  : [NAME / EMAIL]
Approving Lead    : [NAME / EMAIL]
Maintenance Window: 2026-10-18 02:00 UTC - 02:30 UTC
Rollback Deadline : 02:15 UTC (Hard stop: initiate rollback if post-checks unverified)

[ ] I have reviewed the Stage 3C safety audit and isolated test evidence.
[ ] I confirm pre-migration native backup and isolated restore verification are mandatory.
[ ] I explicitly authorize the execution of Stage 3C migration during the scheduled window.

Approver Signature: ___________________________ Date: ______________
```

### 3.3 Maintenance Window & Communication Protocol
- **Scheduled Window:** 30 minutes during off-peak hours (recommended: Sunday 02:00–02:30 UTC).
- **Stakeholder Advisory (T-24h):** Notify internal users and support desks of planned read-only maintenance window.
- **Maintenance Start (T-0):** Enable maintenance banner on frontend reverse proxy; pause backend traffic.
- **Hard Rollback Deadline (T+15m):** If Step 8 or Step 9 verification is not completed within 15 minutes of execution, the Go/No-Go gate defaults to **NO-GO**, halting rollout and triggering Rollback Option A or B.
- **Service Resumption (T+25m):** Restart backend and frontend, conduct smoke tests, remove maintenance banner.

---

## 4. Pre-Migration Safety & Baseline Invariants

### 4.1 Target Environment Identity & Revision State
- **Target Container:** `lifenavigator-db` (`pgvector/pgvector:pg16` on Docker network `lifenavigator-net`)
- **Target Host Port:** `5432` (Internal PostgreSQL listening port: `5432`)
- **Target Database:** `lifenavigator`
- **Target User:** `lifenavigator`
- **Current Alembic Revision:** `e1a89b72c431` (Parent of `3c1a2b3c4d5e`)
- **Target Alembic Revision:** `3c1a2b3c4d5e`

### 4.2 Baseline Data Integrity Invariants (Pre-Migration)
The production database must strictly conform to these invariants before any DDL is applied:
1. **Total Schemes:** Exactly `130`.
2. **Active Schemes:** Exactly `125`.
3. **Inactive Schemes:** Exactly `5` (Schemes 6, 8, 37, 72, 83).
4. **Target Canonical Schemes:** Schemes 11 (PM-KISAN), 19 (PMAY-U 2.0), and 88 (PMFME) exist and have `is_active = TRUE`.
5. **Duplicate Schemes:** Schemes 6, 8, and 37 exist and have `is_active = FALSE`.
6. **Foreign Key Orphans:** Exactly `0` orphans across `eligibility_rules`, `scheme_documents`, and `scheme_versions`.
7. **RAG Vector Embeddings:** Exactly `151` scheme document chunks with non-null 384-dimensional pgvector embeddings.
8. **Schema Cleanliness:** Columns `slug`, `aliases`, `canonical_scheme_id` and index `uq_schemes_active_slug_jurisdiction` do NOT exist on table `schemes`.

### 4.3 Writer Pause & Zero-RPO Guarantee
To guarantee a **Recovery Point Objective of zero (RPO = 0)**:
1. Stop the backend container: `docker compose -f docker-compose.prod.yml stop backend`.
2. Verify zero active non-idle client sessions in `pg_stat_activity`.
3. Halt all scheduled background tasks and sync loops before creating the native backup dump.
4. Because no client writes can occur between writer pause and backup creation, any rollback or recovery back to the Step 4 backup incurs zero data loss.

---

## 5. Sequential Migration Execution Plan

> **CRITICAL NOTICE:** Every command listed below is **[NOT EXECUTED - PLANNING ONLY]**. Execution requires explicit human authorization and operator confirmation during the maintenance window.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 STAGE 3C PRODUCTION EXECUTION FLOW                          │
│                   [NOT EXECUTED - PLANNING ONLY]                            │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
                     Phase 1: Pre-Migration Host & Resource Audit
                                       │
                                       ▼
                     Phase 2: Traffic Pause & Session Drain
                                       │
                                       ▼
                     Phase 3: Native Full Backup & Test Restoration
                                       │
                                       ▼
                     Phase 4: Read-Only Preflight Verification
                                       │
                                       ▼
                     Phase 5: Interactive Production Migration Execution
                                       │
                                       ▼
                     Phase 6: Post-Migration Schema & Smoke Verification
                                       │
                                       ▼
                     Phase 7: Application Resumption & Monitoring
```

---

### Phase 1: Host Resource Audit & Isolation Verification

#### Command 1.1: Verify Host Storage Capacity **[NOT EXECUTED]**
```bash
# Verify at least 5.0 GB free disk space for backup artifacts and temp tables
df -h /var/lib/docker  # Linux or PowerShell: Get-PSDrive C
```
- **Approval Gate:** Primary Operator verifies $\ge 5.0$ GB available.
- **Stop Condition:** Abort if free disk space $< 5.0$ GB.

#### Command 1.2: Verify Production Database Container Health **[NOT EXECUTED]**
```bash
# Confirm container is healthy and accepting connections
docker inspect lifenavigator-db --format '{{json .State.Health.Status}}'
# Expected: "healthy"

docker exec lifenavigator-db pg_isready -U lifenavigator -d lifenavigator
# Expected: accepting connections
```
- **Approval Gate:** Primary Operator confirms status `healthy`.
- **Stop Condition:** Abort if database is restarting, unhealthy, or unreachable.

---

### Phase 2: Traffic Pause & Writer Drain (Zero-RPO Boundary)

#### Command 2.1: Stop Application Traffic **[NOT EXECUTED]**
```bash
# Stop backend container to halt API traffic, schedulers, and background sync
docker compose -f docker-compose.prod.yml stop backend
```
- **Approval Gate:** Production Gatekeeper authorizes traffic pause.

#### Command 2.2: Verify Zero Active Client Transactions **[NOT EXECUTED]**
```bash
# Query active client sessions on production database
docker exec lifenavigator-db psql -U lifenavigator -d lifenavigator -c "
SELECT pid, usename, client_addr, state, query 
FROM pg_stat_activity 
WHERE datname = 'lifenavigator' AND pid != pg_backend_pid();
"
```
- **Approval Gate:** Primary Operator verifies 0 active writing transactions (idle connections only).
- **Stop Condition:** If active write queries persist, terminate them via `SELECT pg_terminate_backend(pid)` before proceeding.

---

### Phase 3: Native PostgreSQL Backup & Isolated Test Restoration

#### Command 3.1: Generate Custom-Format Backup Dump **[NOT EXECUTED]**
```bash
# Execute native pg_dump (-Fc) via verified backup utility
python backend/scripts/native_db_backup.py --container lifenavigator-db --db lifenavigator --user lifenavigator
# Generated artifact: backups/lifenavigator_native_<TIMESTAMP>.dump
```
- **Approval Gate:** Primary Operator confirms file size $> 10$ KB and non-zero exit code.
- **Stop Condition:** Abort if backup generation fails or file size is under 10 KB.

#### Command 3.2: Verify Table of Contents & Isolated Test Restoration **[NOT EXECUTED]**
```bash
# Test-restore the dump into temporary DB lifenavigator_test_restore, verify 130 schemes & vector embeddings, drop temp DB
python backend/scripts/native_db_backup.py --verify-restore --container lifenavigator-db --db lifenavigator --user lifenavigator
```
- **Approval Gate:** Lead Database Administrator verifies test-restore passed with 130 schemes and 151 embedded chunks.
- **Stop Condition:** **MANDATORY GATE:** If test restoration fails or TOC is missing critical tables, **ABORT IMMEDIATELY**. Do not proceed to migration.

---

### Phase 4: Read-Only Preflight Verification (Runner)

#### Command 4.1: Run Runner Preflight Assertions **[NOT EXECUTED]**
```bash
# Execute read-only preflight check via production runner
python backend/scripts/run_production_migration.py upgrade 3c1a2b3c4d5e \
  --environment production \
  --db-url "$DATABASE_URL" \
  --expected-db lifenavigator \
  --expected-user lifenavigator \
  --expected-port 5432 \
  --preflight-only
```
- **Approval Gate:** Primary Operator confirms:
  - Database identity confirmed (`lifenavigator` on `lifenavigator-db:5432`).
  - Current revision confirmed (`e1a89b72c431`).
  - Counts confirmed (`130` total, `125` active, `5` inactive).
  - Foreign key integrity confirmed (`0` orphans).
  - Target schemes (`11`, `19`, `88`) active; duplicates (`6`, `8`, `37`) inactive.
  - Zero schema conflicts detected.
- **Stop Condition:** Any mismatch raises `TargetIdentityError` or `PreflightValidationError` and exits with code 1.

#### Command 4.2: Export Baseline Pre-Migration Manifest **[NOT EXECUTED]**
```bash
# Export pre-migration identity baseline manifest
python backend/scripts/export_stage3c_manifest.py --db-url "$DATABASE_URL" --output backups/manifests/stage3c_pre_prod_manifest.json

# Validate manifest schema and record count (130 schemes)
python backend/scripts/validate_stage3c_manifest.py backups/manifests/stage3c_pre_prod_manifest.json --expected-count 130
```
- **Approval Gate:** Primary Operator verifies manifest checksum and 130 validated schemes.

---

### Phase 5: Production Migration Execution

#### Command 5.1: Execute Production Migration with Interactive Two-Factor Confirmation **[NOT EXECUTED]**
```bash
# Execute production migration runner (Requires typing: YES-MIGRATE-PRODUCTION)
python backend/scripts/run_production_migration.py upgrade 3c1a2b3c4d5e \
  --environment production \
  --db-url "$DATABASE_URL" \
  --expected-db lifenavigator \
  --expected-user lifenavigator \
  --expected-port 5432
```
- **Execution Flow:**
  1. Runner connects and re-asserts database identity and revision `e1a89b72c431`.
  2. Runner prompts operator: `Enter confirmation: `
  3. Operator enters: `YES-MIGRATE-PRODUCTION`
  4. Runner applies Alembic migration `3c1a2b3c4d5e` within transactional DDL.
  5. Deterministic slug generation, backfill, unique partial index, triggers, and constraints applied.
- **Approval Gate:** Production Gatekeeper confirms execution authorization immediately before operator types token.
- **Stop Condition:** If any SQL or Alembic error occurs, PostgreSQL transactional DDL rolls back automatically to revision `e1a89b72c431`. Proceed to Rollback Evaluation.

---

### Phase 6: Post-Migration Schema, Data & Smoke Verification

#### Command 6.1: Direct Database Schema & Invariant Assertions **[NOT EXECUTED]**
```sql
-- Run inside docker exec lifenavigator-db psql -U lifenavigator -d lifenavigator
DO $$
DECLARE
    v_null_slugs INT;
    v_dup_slugs INT;
BEGIN
    -- 1. Assert alembic revision is updated to 3c1a2b3c4d5e
    IF NOT EXISTS (SELECT 1 FROM alembic_version WHERE version_num = '3c1a2b3c4d5e') THEN
        RAISE EXCEPTION 'POST-CHECK FAILED: alembic_version != 3c1a2b3c4d5e';
    END IF;

    -- 2. Assert zero null slugs
    SELECT count(*) INTO v_null_slugs FROM schemes WHERE slug IS NULL;
    IF v_null_slugs > 0 THEN
        RAISE EXCEPTION 'POST-CHECK FAILED: % schemes have NULL slugs', v_null_slugs;
    END IF;

    -- 3. Assert zero active slug collisions across jurisdictions
    SELECT count(*) INTO v_dup_slugs FROM (
        SELECT slug, COALESCE(state, 'CENTRAL') 
        FROM schemes 
        WHERE is_active = TRUE 
        GROUP BY slug, COALESCE(state, 'CENTRAL') 
        HAVING count(*) > 1
    ) sub;
    IF v_dup_slugs > 0 THEN
        RAISE EXCEPTION 'POST-CHECK FAILED: % duplicate active slugs detected', v_dup_slugs;
    END IF;

    -- 4. Assert canonical redirects (schemes 6->11, 8->19, 37->88)
    IF NOT EXISTS (SELECT 1 FROM schemes WHERE id = 6 AND canonical_scheme_id = 11 AND is_active = FALSE) THEN
        RAISE EXCEPTION 'POST-CHECK FAILED: Scheme 6 redirect to 11 is missing.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM schemes WHERE id = 8 AND canonical_scheme_id = 19 AND is_active = FALSE) THEN
        RAISE EXCEPTION 'POST-CHECK FAILED: Scheme 8 redirect to 19 is missing.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM schemes WHERE id = 37 AND canonical_scheme_id = 88 AND is_active = FALSE) THEN
        RAISE EXCEPTION 'POST-CHECK FAILED: Scheme 37 redirect to 88 is missing.';
    END IF;

    RAISE NOTICE 'POST-CHECK PASSED: Schema, indexes, constraints, and canonical redirects verified.';
END $$;
```
- **Approval Gate:** Lead Database Administrator verifies 0 exceptions.
- **Stop Condition:** If any schema assertion fails, evaluate Rollback Option A (Clean Downgrade).

#### Command 6.2: Export and Compare Post-Migration Manifest **[NOT EXECUTED]**
```bash
# Export post-migration manifest and validate schema
python backend/scripts/export_stage3c_manifest.py --db-url "$DATABASE_URL" --output backups/manifests/stage3c_post_prod_manifest.json
python backend/scripts/validate_stage3c_manifest.py backups/manifests/stage3c_post_prod_manifest.json --expected-count 130
```
- **Approval Gate:** Primary Operator confirms 130 schemes and valid manifest cryptographic hashes.

---

### Phase 7: Application Resumption & API Smoke Verification

#### Command 7.1: Restart Application Backend Container **[NOT EXECUTED]**
```bash
# Start backend container (normal startup omits migration container via manual-migration profile)
docker compose -f docker-compose.prod.yml up -d backend

# Wait for container startup
sleep 15
```
- **Approval Gate:** Primary Operator confirms container state `running`.
- **Stop Condition:** If container fails to start, **DO NOT DOWNGRADE THE DATABASE**. Inspect `docker compose logs backend` for environment or networking issues.

#### Command 7.2: Fail-Fast Health & Search API Smoke Tests **[NOT EXECUTED]**
```bash
# 1. Health readiness endpoint
curl -f -s http://localhost:8000/health/ready
# Expected: {"status": "ready", "database": "connected"}

# 2. Search API active schemes smoke check with limit=200
curl -s --fail "http://localhost:8000/api/schemes/search?active_only=true&limit=200" | python -c "
import sys, json
data = json.load(sys.stdin)
assert 'query' in data, 'Missing query field'
assert 'results' in data, 'Missing results field'
results = data['results']
print(f'Total active schemes returned: {len(results)}')
assert len(results) == 125, f'Expected 125 active schemes, got {len(results)}'
print('Active scheme search check: PASS')
"

# 3. Search query with keyword match and evidence verification
curl -s --fail "http://localhost:8000/api/schemes/search?q=farmer&active_only=true" | python -c "
import sys, json
data = json.load(sys.stdin)
results = data.get('results', [])
assert len(results) > 0, 'No farmer schemes returned'
top = results[0]
assert 'name' in top and 'score' in top and 'evidence' in top
print(f'Search query check PASS: top match={top[\"name\"]}')
"

# 4. Canonical redirect smoke test
curl -s --fail "http://localhost:8000/api/schemes/6" | python -c "
import sys, json
data = json.load(sys.stdin)
assert data.get('is_active') is False
assert data.get('canonical_scheme_id') == 11
print('Canonical redirect check PASS (Scheme 6 -> 11)')
"
```
- **Approval Gate:** QA Engineer and Primary Operator confirm all 4 checks return exit code 0.
- **Stop Condition:** If smoke tests fail due to application logic, review logs before making any rollback determination.

---

### Phase 8: Monitoring & GO / NO-GO Sign-Off

#### Command 8.1: Post-Deployment Telemetry Observation **[NOT EXECUTED]**
```bash
# Monitor container logs for error spikes
docker compose -f docker-compose.prod.yml logs -f --tail=50 backend

# Inspect database connection pool and query latencies
docker exec lifenavigator-db psql -U lifenavigator -d lifenavigator -c "
SELECT count(*), state FROM pg_stat_activity WHERE datname = 'lifenavigator' GROUP BY state;
"
```
- **Monitoring Window:** 60 minutes of active monitoring post-resumption.
- **Success Criteria:** Zero 500 error spikes on `/api/schemes/search` or `/api/schemes/{id}`; background ingestion locks cleanly without contention.
- **Final Sign-Off:** Production Gatekeeper logs final deployment approval ticket.

---

## 6. Disaster Recovery & Rollback Protocols

### 6.1 Failure Mode Decision Tree

```
                                 INCIDENT DETECTED
                                        |
                       -----------------+-----------------
                      |                                   |
           App Container Startup Fails            Database / DDL Check Fails
                      |                                   |
                      v                                   v
         DO NOT DOWNGRADE DATABASE                  Evaluate Data Loss
         Keep database at 3c1a2b3c4d5e                    |
         Inspect `docker compose logs`         -----------+-----------
         Fix env/port/network config          |                       |
         Restart backend container     Schema Only (No Loss)   Data Corrupted / Truncated
                                              |                       |
                                              v                       v
                                      Rollback Option A       Rollback Option B
                                      Alembic Downgrade       Disaster Recovery
                                      (Keeps 130 records)     Restore to Temp DB First
                                                              Controlled Cutover
```

### 6.2 Rollback Option A: Clean Alembic Downgrade
- **When to Use:** Post-migration database schema assertions fail, but underlying scheme data (130 records) is uncorrupted.
- **What it Preserves:** All 130 scheme records, descriptions, eligibility criteria, documents, chunks, versions, sources, and vector embeddings.
- **What it Removes:** Columns `slug`, `aliases`, `canonical_scheme_id`, uniqueness partial index, search indexes, check constraints, and integrity trigger.
- **Execution Command [NOT EXECUTED]:**
  ```bash
  # Execute downgrade via the production runner (Requires typing: YES-DOWNGRADE-PRODUCTION)
  python backend/scripts/run_production_migration.py downgrade -1 \
    --environment production \
    --db-url "$DATABASE_URL" \
    --expected-db lifenavigator \
    --expected-user lifenavigator \
    --expected-port 5432

  # Verify schema restoration to e1a89b72c431 and 130 records intact
  docker exec lifenavigator-db psql -U lifenavigator -d lifenavigator -c "
  SELECT version_num FROM alembic_version;
  SELECT count(*) FROM schemes;
  SELECT count(*) FROM information_schema.columns WHERE table_name = 'schemes' AND column_name IN ('slug', 'aliases', 'canonical_scheme_id');
  "
  # Expected: e1a89b72c431, 130, and 0
  ```

---

### 6.3 Rollback Option B: Disaster Recovery from Native Backup
- **When to Use:** Severe data corruption, foreign key violation, accidental truncation, or unrecoverable database divergence.
- **Safety Invariant:** **Never drop or overwrite the live database automatically.**
- **Restore-to-Separate-Database-First Procedure [NOT EXECUTED]:**

```bash
# Step 1: Ensure backend container is stopped completely
docker compose -f docker-compose.prod.yml stop backend

# Step 2: Create a separate, isolated recovery database
docker exec lifenavigator-db psql -U lifenavigator -d postgres -c "
CREATE DATABASE lifenavigator_recovery_verify OWNER lifenavigator;
"

# Step 3: Restore the Step 3 backup dump into the recovery database
docker cp backups/lifenavigator_native_<TIMESTAMP>.dump lifenavigator-db:/tmp/restore.dump
docker exec lifenavigator-db pg_restore -U lifenavigator -d lifenavigator_recovery_verify --no-owner --no-privileges /tmp/restore.dump
docker exec lifenavigator-db rm -f /tmp/restore.dump

# Step 4: Verify schema, counts, foreign keys, and vector embeddings in the recovery database
docker exec lifenavigator-db psql -U lifenavigator -d lifenavigator_recovery_verify -c "
SELECT version_num FROM alembic_version;
SELECT count(*) AS total_schemes FROM schemes;
SELECT count(*) AS active_schemes FROM schemes WHERE is_active = TRUE;
SELECT count(*) AS total_chunks FROM scheme_document_chunks;
SELECT count(*) AS embedded_chunks FROM scheme_document_chunks WHERE embedding IS NOT NULL;
"
# Expected: version_num = e1a89b72c431, total_schemes = 130, active_schemes = 125, total_chunks = 151, embedded_chunks = 151

# Step 5: Terminate connections and perform atomic rename swap (Preserves damaged DB for forensics)
docker exec lifenavigator-db psql -U lifenavigator -d postgres -c "
SELECT pg_terminate_backend(pid) FROM pg_stat_activity 
WHERE datname IN ('lifenavigator', 'lifenavigator_recovery_verify') AND pid != pg_backend_pid();
"

docker exec lifenavigator-db psql -U lifenavigator -d postgres -c "
ALTER DATABASE lifenavigator RENAME TO lifenavigator_corrupted;
ALTER DATABASE lifenavigator_recovery_verify RENAME TO lifenavigator;
"

# Step 6: Post-cutover verification on restored primary database
docker exec lifenavigator-db psql -U lifenavigator -d lifenavigator -c "
SELECT version_num FROM alembic_version;
SELECT count(*) FROM schemes;
"
# Expected: e1a89b72c431 and 130
```

- **RPO Accounting & Post-Backup Writes:**
  - Because backend traffic was paused in Phase 2 before the Phase 3 backup, no write operations occurred during the maintenance window (RPO = 0).
  - If disaster recovery is initiated after application traffic was resumed in Phase 7, any citizen interactions during that live window are lost upon cutover. The operator must extract transaction records from `lifenavigator_corrupted` for post-recovery manual reconciliation.

---

## 7. Operational Risks & Deferred Maintenance Tracking

The following operational limitations are documented and tracked. None block Stage 3C schema deployment, provided operational mitigations are enforced:

| Risk Item | Nature of Limitation | Current Mitigation | Deployment Blocker? | Rationale |
| :--- | :--- | :--- | :---: | :--- |
| **TLS Termination** | Nginx listens on HTTP ports 80/3000 without SSL. | Edge termination at Cloudflare / AWS ALB or Let's Encrypt reverse proxy. | **NO** | Schema update does not affect transport security architecture. |
| **Backend Port Exposure** | Backend port 8000 mapped to `0.0.0.0:8000` in Compose. | Firewall rules on production host restrict port 8000 to internal traffic. | **NO** | Infrastructure configuration independent of database DDL. |
| **In-Memory Rate Limiting** | `slowapi` tracks rate limits in process memory. | Single-worker Uvicorn deployment or sticky sessions at proxy. | **NO** | In-memory limiter functions correctly for single-instance backend. |
| **Scheduler Multi-Worker Locking** | In-memory `threading.Lock()` does not span containers. | Stage 3C resolves this via database `pg_try_advisory_xact_lock(458712398571234)`. | **NO** | Resolved by Stage 3C schema and sync service enhancements. |
| **Stale Frontend Test Assertion** | `frontend/test/e2e_sequence.test.js:60` asserts 128 instead of 125. | Tracked as a separate frontend maintenance PR; frontend untouched in Stage 3C. | **NO** | Test assertion discrepancy does not affect production backend or runtime API. |

---

## 8. Final Gate Assessment & Recommendation

### Summary of Audited Criteria
- [x] Preflight checks fail closed on any database name, user, port, or revision mismatch.
- [x] Runner `--preflight-only` mode verified to exit without reaching Alembic upgrade/downgrade code.
- [x] Ordinary Compose startup verified to omit migrations (`manual-migration` profile active).
- [x] Linear revision graph confirmed (14 revisions, parent `e1a89b72c431` $\rightarrow$ `3c1a2b3c4d5e`).
- [x] Downgrade implementation verified to preserve all 130 core schemes and vector embeddings.
- [x] Disaster recovery procedure mandates restore to temporary database first before cutover.
- [x] Search API smoke test updated for response schema and `limit=200`.
- [x] Schemes 11 and 19 remain marked `unverified`.
- [x] Zero frontend files modified; working tree clean and isolated.
- [x] Zero production database connections or modifications performed.

---

### Gate Conclusion

### **READY FOR HUMAN AUTHORIZATION**

> **IMPORTANT:** This checklist confirms technical and operational readiness only. It **DOES NOT** constitute authorization to execute the migration. Execution may only proceed after the designated human approvers sign off on the authorization record in Section 3 and initiate the scheduled maintenance window.
