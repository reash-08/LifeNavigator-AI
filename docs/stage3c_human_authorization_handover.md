# LifeNavigator-AI — Stage 3C Production Migration Human Authorization & Operator Handover Record

> **DOCUMENT STATUS:** **PENDING HUMAN SIGN-OFF**  
> **Operational Mode:** FINAL APPROVAL PREPARATION ONLY — **ZERO PRODUCTION EXECUTION**  
> **Governing Specifications:**  
> - Readiness Checklist: [`docs/stage3c_production_readiness_checklist.md`](file:///c:/GitHub/LifeNavigator-AI/docs/stage3c_production_readiness_checklist.md)  
> - Migration Runbook: [`docs/stage3c_production_migration_plan.md`](file:///c:/GitHub/LifeNavigator-AI/docs/stage3c_production_migration_plan.md)  
> - Compose Configuration: [`docker-compose.prod.yml`](file:///c:/GitHub/LifeNavigator-AI/docker-compose.prod.yml)  
> - Production Runner: [`backend/scripts/run_production_migration.py`](file:///c:/GitHub/LifeNavigator-AI/backend/scripts/run_production_migration.py)  
> - Native Backup Script: [`backend/scripts/native_db_backup.py`](file:///c:/GitHub/LifeNavigator-AI/backend/scripts/native_db_backup.py)  

---

## 1. Safety Mandate & Authority Notice

This document establishes the formal operational handover and human authorization framework for deploying Stage 3C database schema enhancements to the production LifeNavigator-AI environment.

1. **No Implied Execution Authority:** The creation or presence of this document **DOES NOT** authorize execution. No command may be run against the production database without completed, signed human authorization records.
2. **Strict Production Isolation:** Production database (`lifenavigator-db` / database `lifenavigator`) remains strictly untouched.
3. **Linear Revision Target:** Targets single-revision migration `3c1a2b3c4d5e` from verified parent `e1a89b72c431`.
4. **Governance Invariant:** Schemes 11 (PM-KISAN) and 19 (PMAY-U 2.0) must remain in `eligibility_verification_status = 'unverified'` with active fail-closed advisories until post-deployment administrative sign-off.
5. **Frontend Isolation:** Frontend files remain strictly untouched; the test assertion discrepancy in `frontend/test/e2e_sequence.test.js:60` (`128` vs `125`) is handled via a separate frontend maintenance PR.

---

## 2. Formal Production Authorization Record

*All bracketed fields (`[Pending Input]`, `[_________________]`) must be formally completed and signed by authorized personnel prior to initiating maintenance.*

```
================================================================================
           STAGE 3C PRODUCTION DATABASE MIGRATION AUTHORIZATION RECORD
================================================================================

1. GENERAL METADATA & CHANGE MANAGEMENT
   - Change Request / Ticket Ref : [Pending Input - e.g., OPS-CHG-20261017-01]
   - Target Application          : LifeNavigator-AI Production Backend
   - Migration Objective         : Stage 3C Schema Enhancements (Deterministic Slugs,
                                   Aliases, Canonical Redirects, Concurrency Trigger)
   - Governing Runbook           : docs/stage3c_production_migration_plan.md (Rev 1.0)
   - Operational Readiness Gate  : docs/stage3c_production_readiness_checklist.md (PASS)

2. TARGET SYSTEM & SERVER IDENTITY
   - Production Docker Host      : [Pending Input - Hostname / IP]
   - Target DB Container Name    : lifenavigator-db
   - Target Database Name        : lifenavigator
   - Target Database User        : lifenavigator
   - Internal PostgreSQL Port    : 5432
   - Target Server Version       : PostgreSQL 16.2 / pgvector (pg16)
   - Current Database Revision   : e1a89b72c431
   - Target Database Revision    : 3c1a2b3c4d5e

3. MAINTENANCE WINDOW & TIMING
   - Scheduled Maintenance Date  : [Pending Input - YYYY-MM-DD]
   - Scheduled Window Start Time : [Pending Input - HH:MM]
   - Timezone                    : [Pending Input - UTC / IST / Other]
   - Planned Window Duration     : 30 minutes
   - Hard Stop / Rollback Cutoff : T+15 minutes from migration initiation

4. DESIGNATED HUMAN OPERATIONAL ROLES
   - Primary Migration Operator  : [Pending Input - Full Name, Role, Email]
   - Approving Authority (Lead)  : [Pending Input - Full Name, Title, Email]
   - Independent Recovery Op     : [Pending Input - Full Name, Title, Email]

5. PRE-MIGRATION BACKUP & VERIFICATION DESTINATION
   - Primary Backup Directory    : backups/
   - Expected Dump Filename      : backups/lifenavigator_native_<TIMESTAMP>.dump
   - Backup Format               : PostgreSQL Custom Format (-Fc)
   - Backup Integrity Tool       : backend/scripts/native_db_backup.py
   - Isolated Restore Verify DB  : lifenavigator_test_restore (Dropped post-verification)
   - Baseline Pre-Manifest File  : backups/manifests/stage3c_pre_prod_manifest.json (130 records)

6. PREFLIGHT VERIFICATION SUMMARY (ISOLATED TEST EVIDENCE)
   - Total Core Schemes          : 130 (125 Active, 5 Inactive) [VERIFIED IN ISOLATION]
   - Foreign Key Orphan Rows     : 0 across rules, documents, versions [VERIFIED]
   - Canonical Targets (11,19,88): Verified ACTIVE [VERIFIED]
   - Archived Duplicates (6,8,37): Verified INACTIVE [VERIFIED]
   - Conflicting Columns/Indexes : 0 slug columns, 0 partial unique indexes [VERIFIED]
   - Vector Embeddings Baseline  : 151 chunks (384-dimensional pgvector) [VERIFIED]
   - Production Runner Tests     : 12 passed in 0.32s (tests/test_production_migration_runner.py)
   - PostgreSQL Matrix Tests     : 18 passed in 2.67s (tests/test_stage3c_postgresql_matrix.py)

================================================================================
```

---

## 3. Explicit Three-Tier Human Decision Gates

To ensure strict operational control, the migration is governed by **three distinct, sequential human sign-off gates**. No step in a subsequent gate may be initiated until the preceding gate is signed and timestamped.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       THREE-TIER APPROVAL WORKFLOW                          │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
                     Gate 1: Approval to Schedule Maintenance Window
                                       │
                                       ▼
                     Gate 2: Approval to Execute Migration
                                       │
                                       ▼
                     Gate 3: Approval to Resume Application Traffic
```

---

### Gate 1: Approval to Schedule Maintenance Window
*Mandatory pre-condition: All pre-execution readiness checklist items in `docs/stage3c_production_readiness_checklist.md` verified PASS.*

- **Scope of Approval:** Authorizes the reservation of the maintenance window, publication of user/stakeholder advisories, and assignment of operational personnel. **Does NOT authorize running any commands.**
- **Decision:** `[  ] APPROVED    [  ] REJECTED    [  ] PENDING`
- **Approving Authority:** `[________________________________________]`
- **Title / Role:** `[________________________________________]`
- **Timestamp:** `[________________________________________]`
- **Signature:** `[________________________________________]`

---

### Gate 2: Approval to Execute Migration
*Mandatory pre-condition: Window commenced, Phase 1 (resource audit) passed, Phase 2 (traffic paused, zero active transactions) verified, Phase 3 (native backup dump created and test-restored into `lifenavigator_test_restore`) verified, and Phase 4 (`--preflight-only` runner check) passed.*

- **Scope of Approval:** Authorizes the Primary Operator to run `run_production_migration.py upgrade 3c1a2b3c4d5e` and enter the interactive confirmation token `YES-MIGRATE-PRODUCTION`.
- **Decision:** `[  ] APPROVED    [  ] REJECTED    [  ] PENDING`
- **Approving Authority:** `[________________________________________]`
- **Title / Role:** `[________________________________________]`
- **Timestamp:** `[________________________________________]`
- **Signature:** `[________________________________________]`

---

### Gate 3: Approval to Resume Application Traffic
*Mandatory pre-condition: Phase 5 (DDL execution) completed, Phase 6 (post-migration schema assertions and manifest verification) passed, Phase 7 (application backend container restarted, `/health/ready` verified, search API smoke test with `limit=200` returning 125 active schemes, and canonical redirect test passed).*

- **Scope of Approval:** Authorizes removing the maintenance banner, enabling inbound traffic on the Nginx reverse proxy, and resuming normal citizen access.
- **Decision:** `[  ] APPROVED    [  ] REJECTED    [  ] PENDING`
- **Approving Authority:** `[________________________________________]`
- **Title / Role:** `[________________________________________]`
- **Timestamp:** `[________________________________________]`
- **Signature:** `[________________________________________]`

---

## 4. Concise Operator Handover Checklist (8 Phases)

> **OPERATOR INSTRUCTION:** Execute only the commands documented below during the approved maintenance window. Every command is labeled **[NOT EXECUTED - PLANNING ONLY]**. Capture and attach all specified evidence to the change record.

| Phase # | Phase Name | Responsible Person | Stop Condition / Abort Trigger | Evidence to Capture | Gate Status |
| :---: | :--- | :--- | :--- | :--- | :---: |
| **Phase 1** | **Host & Resource Audit** | Primary Migration Operator | Available disk space $< 5.0$ GB; container state not `healthy`. | `df -h` output; `docker inspect` health status JSON. | `[  ] PASS` |
| **Phase 2** | **Traffic Pause & Writer Drain** | Primary Migration Operator | Active writing transactions persist after stopping backend. | `pg_stat_activity` query returning 0 writing transactions. | `[  ] PASS` |
| **Phase 3** | **Native Backup & Test Restore** | Lead Database Administrator | Dump $< 10$ KB; TOC missing tables; test restore fails. | Backup file path/size; `pg_restore --list` log; test restore log. | `[  ] PASS` |
| **Phase 4** | **Read-Only Preflight Verification** | Primary Migration Operator | Runner preflight fails; manifest checksum mismatch. | Terminal output of `--preflight-only`; pre-manifest SHA-256. | `[  ] PASS` |
| **Phase 5** | **Production Migration Execution** | Primary Migration Operator | DDL error; Alembic failure; abort by operator. | Terminal output showing `YES-MIGRATE-PRODUCTION` and revision. | `[  ] PASS` |
| **Phase 6** | **Post-Migration Schema Checks** | Lead Database Administrator | Schema assertion fails; post-manifest count $\ne 130$. | SQL anonymous block output; post-manifest validation log. | `[  ] PASS` |
| **Phase 7** | **App Resumption & Smoke Tests** | QA Engineer / Primary Operator | `/health/ready` fails; search smoke test fails. | Curl HTTP 200 responses; JSON assertion logs. | `[  ] PASS` |
| **Phase 8** | **Monitoring & Final Handover** | Production Gatekeeper | 500 error spike; connection pool exhaustion. | Container logs; `pg_stat_activity` metrics; Gate 3 sign-off. | `[  ] PASS` |

---

### Phase 1: Host Resource & Container Health Audit
- **Responsible Person:** Primary Migration Operator
- **Commands [NOT EXECUTED]:**
  ```bash
  # 1. Verify host disk space (Minimum required: 5.0 GB)
  df -h /var/lib/docker  # Linux, or PowerShell: Get-PSDrive C

  # 2. Verify production database container health
  docker inspect lifenavigator-db --format '{{json .State.Health.Status}}'
  # Expected: "healthy"

  # 3. Verify pg_isready on production database
  docker exec lifenavigator-db pg_isready -U lifenavigator -d lifenavigator
  # Expected: accepting connections
  ```
- **Stop Condition:** Abort maintenance if disk space $< 5.0$ GB or container health is not `healthy`.
- **Evidence Captured:** Terminal log showing disk space and container status `healthy`.

---

### Phase 2: Traffic Pause & Writer Drain (Zero-RPO Boundary)
- **Responsible Person:** Primary Migration Operator
- **Commands [NOT EXECUTED]:**
  ```bash
  # 1. Stop backend application container
  docker compose -f docker-compose.prod.yml stop backend

  # 2. Verify zero active writing client sessions
  docker exec lifenavigator-db psql -U lifenavigator -d lifenavigator -c "
  SELECT pid, usename, client_addr, state, query 
  FROM pg_stat_activity 
  WHERE datname = 'lifenavigator' AND pid != pg_backend_pid();
  "
  ```
- **Stop Condition:** If un-terminable client write queries remain, abort maintenance.
- **Evidence Captured:** Terminal output of `pg_stat_activity` showing zero non-idle sessions.

---

### Phase 3: Native PostgreSQL Backup & Isolated Test Restoration
- **Responsible Person:** Lead Database Administrator / Primary Operator
- **Commands [NOT EXECUTED]:**
  ```bash
  # 1. Execute native custom-format backup (pg_dump -Fc)
  python backend/scripts/native_db_backup.py --container lifenavigator-db --db lifenavigator --user lifenavigator

  # 2. Run isolated test-restore into temporary DB lifenavigator_test_restore
  python backend/scripts/native_db_backup.py --verify-restore --container lifenavigator-db --db lifenavigator --user lifenavigator
  ```
- **Stop Condition:** **HARD STOP.** If backup creation fails, archive size $< 10$ KB, TOC integrity check fails, or isolated restoration fails, **ABORT IMMEDIATELY**. Do not proceed to migration.
- **Evidence Captured:** Backup dump path, file size in bytes, `pg_restore --list` table verification, and temporary database verification output (130 schemes, 151 embedded chunks).

---

### Phase 4: Read-Only Preflight Verification
- **Responsible Person:** Primary Migration Operator
- **Commands [NOT EXECUTED]:**
  ```bash
  # 1. Run fail-closed preflight check via production runner
  python backend/scripts/run_production_migration.py upgrade 3c1a2b3c4d5e \
    --environment production \
    --db-url "$DATABASE_URL" \
    --expected-db lifenavigator \
    --expected-user lifenavigator \
    --expected-port 5432 \
    --preflight-only

  # 2. Export pre-migration identity baseline manifest
  python backend/scripts/export_stage3c_manifest.py --db-url "$DATABASE_URL" --output backups/manifests/stage3c_pre_prod_manifest.json
  python backend/scripts/validate_stage3c_manifest.py backups/manifests/stage3c_pre_prod_manifest.json --expected-count 130
  ```
- **Stop Condition:** If any preflight assertion fails (`TargetIdentityError`, `PreflightValidationError`, or manifest count $\ne 130$), abort immediately.
- **Evidence Captured:** Preflight console log with `ALL PREFLIGHT ASSERTIONS PASSED SUCCESSFULLY`; manifest checksum record.

---

### Phase 5: Production Migration Execution
- **Responsible Person:** Primary Migration Operator (Requires Gate 2 Authorization)
- **Commands [NOT EXECUTED]:**
  ```bash
  # Execute migration with interactive confirmation
  python backend/scripts/run_production_migration.py upgrade 3c1a2b3c4d5e \
    --environment production \
    --db-url "$DATABASE_URL" \
    --expected-db lifenavigator \
    --expected-user lifenavigator \
    --expected-port 5432
  # When prompted, operator types: YES-MIGRATE-PRODUCTION
  ```
- **Stop Condition:** If any SQL or Alembic error occurs, PostgreSQL transactional DDL rolls back automatically to `e1a89b72c431`. Proceed immediately to failure triage (Section 5).
- **Evidence Captured:** Full console transcript showing target verification, operator confirmation token entry, Alembic upgrade output, and exit status code 0.

---

### Phase 6: Post-Migration Schema & Data Invariant Assertions
- **Responsible Person:** Lead Database Administrator / Primary Operator
- **Commands [NOT EXECUTED]:**
  ```sql
  -- Run direct database schema assertions inside lifenavigator-db
  DO $$
  DECLARE
      v_null_slugs INT;
      v_dup_slugs INT;
  BEGIN
      IF NOT EXISTS (SELECT 1 FROM alembic_version WHERE version_num = '3c1a2b3c4d5e') THEN
          RAISE EXCEPTION 'POST-CHECK FAILED: alembic_version != 3c1a2b3c4d5e';
      END IF;

      SELECT count(*) INTO v_null_slugs FROM schemes WHERE slug IS NULL;
      IF v_null_slugs > 0 THEN
          RAISE EXCEPTION 'POST-CHECK FAILED: % schemes have NULL slugs', v_null_slugs;
      END IF;

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
  ```bash
  # Export and validate post-migration manifest
  python backend/scripts/export_stage3c_manifest.py --db-url "$DATABASE_URL" --output backups/manifests/stage3c_post_prod_manifest.json
  python backend/scripts/validate_stage3c_manifest.py backups/manifests/stage3c_post_prod_manifest.json --expected-count 130
  ```
- **Stop Condition:** If any post-check assertion fails, evaluate Rollback Option A (Clean Alembic Downgrade).
- **Evidence Captured:** SQL `POST-CHECK PASSED` notice; post-manifest validation output (130 schemes).

---

### Phase 7: Application Container Resumption & Smoke Verification
- **Responsible Person:** QA Engineer / Primary Operator
- **Commands [NOT EXECUTED]:**
  ```bash
  # 1. Start application backend container (migration excluded via manual-migration profile)
  docker compose -f docker-compose.prod.yml up -d backend
  sleep 15

  # 2. Health readiness check
  curl -f -s http://localhost:8000/health/ready
  # Expected: {"status": "ready", "database": "connected"}

  # 3. Search API active schemes smoke check (limit=200)
  curl -s --fail "http://localhost:8000/api/schemes/search?active_only=true&limit=200" | python -c "
  import sys, json
  data = json.load(sys.stdin)
  assert 'query' in data and 'results' in data, 'Invalid schema'
  results = data['results']
  print(f'Total active schemes returned: {len(results)}')
  assert len(results) == 125, f'Expected 125 active schemes, got {len(results)}'
  print('Active schemes search smoke check: PASS')
  "

  # 4. Search query keyword match & evidence check
  curl -s --fail "http://localhost:8000/api/schemes/search?q=farmer&active_only=true" | python -c "
  import sys, json
  data = json.load(sys.stdin)
  results = data.get('results', [])
  assert len(results) > 0, 'No matching schemes'
  top = results[0]
  assert 'name' in top and 'score' in top and 'evidence' in top
  print(f'Search query check PASS: top match={top[\"name\"]}')
  "

  # 5. Canonical redirect resolution check
  curl -s --fail "http://localhost:8000/api/schemes/6" | python -c "
  import sys, json
  data = json.load(sys.stdin)
  assert data.get('is_active') is False
  assert data.get('canonical_scheme_id') == 11
  print('Canonical redirect check PASS: Scheme 6 -> 11')
  "
  ```
- **CRITICAL OPERATIONAL RULE:** If the backend container fails to start post-migration, **DO NOT DOWNGRADE THE DATABASE**. The database schema is valid. Inspect `docker compose logs backend` to resolve container packaging or environment variables.
- **Stop Condition:** If smoke tests fail due to application defects, hold Gate 3 sign-off and triage with backend lead.
- **Evidence Captured:** Terminal logs of all 5 smoke checks passing with exit code 0.

---

### Phase 8: Monitoring & Final Handover
- **Responsible Person:** Production Gatekeeper / Primary Migration Operator
- **Commands [NOT EXECUTED]:**
  ```bash
  # 1. Tail application container logs
  docker compose -f docker-compose.prod.yml logs -f --tail=50 backend

  # 2. Inspect active database connections and pool status
  docker exec lifenavigator-db psql -U lifenavigator -d lifenavigator -c "
  SELECT count(*), state FROM pg_stat_activity WHERE datname = 'lifenavigator' GROUP BY state;
  "
  ```
- **Monitoring Window:** 60 minutes of active monitoring post-resumption.
- **Success Criteria:** Zero 500 error spikes on `/api/schemes/search` or `/api/schemes/{id}`; background ingestion locks cleanly (`status: unchanged, discovered: 124`).
- **Gate 3 Sign-Off:** Approving authority signs Gate 3 to formally complete handover.
- **Evidence Captured:** Error rate telemetry graph, database session table, signed Gate 3 form.

---

## 5. Rollback & Emergency Recovery Protocols

```
                                 INCIDENT DETECTED
                                        │
                       ─────────────────┴─────────────────
                      │                                   │
           App Container Startup Fails            Database / DDL Check Fails
                      │                                   │
                      ▼                                   ▼
         DO NOT DOWNGRADE DATABASE                  Evaluate Data Loss
         Keep database at 3c1a2b3c4d5e                    │
         Inspect `docker compose logs`         ───────────┴───────────
         Fix env/port/network config          │                       │
         Restart backend container     Schema Only (No Loss)   Data Corrupted / Truncated
                                              │                       │
                                              ▼                       ▼
                                      Rollback Option A       Rollback Option B
                                      Alembic Downgrade       Disaster Recovery
                                      (Keeps 130 records)     Restore to Temp DB First
                                                              Controlled Cutover
```

### 5.1 Rollback Option A: Clean Alembic Downgrade
- **When to Use:** Post-migration schema checks fail, but core data (130 records) is uncorrupted.
- **Preserved:** All 130 schemes, eligibility rules, documents, chunks, versions, sources, and vector embeddings.
- **Removed:** `slug`, `aliases`, `canonical_scheme_id` columns, uniqueness partial index, search indexes, check constraints, and integrity trigger.
- **Execution Command [NOT EXECUTED]:**
  ```bash
  # Requires typing: YES-DOWNGRADE-PRODUCTION
  python backend/scripts/run_production_migration.py downgrade -1 \
    --environment production \
    --db-url "$DATABASE_URL" \
    --expected-db lifenavigator \
    --expected-user lifenavigator \
    --expected-port 5432
  ```

---

### 5.2 Rollback Option B: Disaster Recovery from Native Backup
- **When to Use:** Severe data corruption, foreign key violation, or unrecoverable state divergence.
- **CRITICAL INVARIANT:** **Never drop or overwrite the live database automatically.**
- **Restore-to-Separate-Database-First Procedure [NOT EXECUTED]:**
  ```bash
  # 1. Stop backend container completely
  docker compose -f docker-compose.prod.yml stop backend

  # 2. Create separate recovery database
  docker exec lifenavigator-db psql -U lifenavigator -d postgres -c "
  CREATE DATABASE lifenavigator_recovery_verify OWNER lifenavigator;
  "

  # 3. Restore backup into recovery database
  docker cp backups/lifenavigator_native_<TIMESTAMP>.dump lifenavigator-db:/tmp/restore.dump
  docker exec lifenavigator-db pg_restore -U lifenavigator -d lifenavigator_recovery_verify --no-owner --no-privileges /tmp/restore.dump
  docker exec lifenavigator-db rm -f /tmp/restore.dump

  # 4. Verify schema, counts, foreign keys, and vector embeddings in recovery database
  docker exec lifenavigator-db psql -U lifenavigator -d lifenavigator_recovery_verify -c "
  SELECT version_num FROM alembic_version;
  SELECT count(*) AS total_schemes FROM schemes;
  SELECT count(*) AS active_schemes FROM schemes WHERE is_active = TRUE;
  SELECT count(*) AS total_chunks FROM scheme_document_chunks;
  SELECT count(*) AS embedded_chunks FROM scheme_document_chunks WHERE embedding IS NOT NULL;
  "
  # Expected: version_num = e1a89b72c431, total_schemes = 130, active_schemes = 125, total_chunks = 151, embedded_chunks = 151

  # 5. Terminate connections and perform atomic rename swap (Preserves damaged DB for forensics)
  docker exec lifenavigator-db psql -U lifenavigator -d postgres -c "
  SELECT pg_terminate_backend(pid) FROM pg_stat_activity 
  WHERE datname IN ('lifenavigator', 'lifenavigator_recovery_verify') AND pid != pg_backend_pid();
  "

  docker exec lifenavigator-db psql -U lifenavigator -d postgres -c "
  ALTER DATABASE lifenavigator RENAME TO lifenavigator_corrupted;
  ALTER DATABASE lifenavigator_recovery_verify RENAME TO lifenavigator;
  "

  # 6. Verify restored primary database
  docker exec lifenavigator-db psql -U lifenavigator -d lifenavigator -c "
  SELECT version_num FROM alembic_version;
  SELECT count(*) FROM schemes;
  "
  # Expected: e1a89b72c431 and 130
  ```

---

## 6. Operational Risk Register & Accountable Owners

The four documented operational limitations are tracked below. None block the Stage 3C schema deployment because current single-instance operational mitigations protect runtime stability. However, each requires an explicit accountable owner and remediation due date for production hardening:

| Risk Item | Limitation Detail | Current Operational Mitigation | Deployment Blocker? | Accountable Owner | Due Date |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **TLS Termination** | Nginx listens on HTTP ports 80/3000 without SSL. | Terminate TLS at Cloudflare edge or AWS Application Load Balancer. | **NO** | `[Pending Input - Owner Name]` | `[Pending Input - Date]` |
| **Backend Port Exposure** | Backend port 8000 mapped to `0.0.0.0:8000` in Compose. | Host-level firewall restricts port 8000 to internal subnet; Nginx reverse proxy used. | **NO** | `[Pending Input - Owner Name]` | `[Pending Input - Date]` |
| **In-Memory Rate Limiting** | `slowapi` tracks rate limits in process memory. | Single-worker Uvicorn deployment in production container. | **NO** | `[Pending Input - Owner Name]` | `[Pending Input - Date]` |
| **Scheduler Multi-Worker Locking** | In-memory `threading.Lock()` does not span containers. | Stage 3C resolves this via database `pg_try_advisory_xact_lock(458712398571234)`. | **NO** | `[Pending Input - Owner Name]` | `[Pending Input - Date]` |
| **Frontend Stale Assertion** | `frontend/test/e2e_sequence.test.js:60` asserts 128 instead of 125. | Handled via separate, dedicated frontend maintenance PR; frontend untouched in 3C. | **NO** | `[Pending Input - Owner Name]` | `[Pending Input - Date]` |

---

## 7. Handover Completion & Next Steps

1. **Missing Information to be Completed by Authorized Personnel:**
   - Change management ticket reference (`OPS-CHG-...`).
   - Production Docker host identifier / IP address.
   - Confirmed maintenance window date, start time, and timezone.
   - Named individuals for Primary Migration Operator, Approving Authority, and Independent Recovery Operator.
   - Accountable owners and target due dates in the Risk Register (Section 6).
2. **Execution Gate:**
   - This document is in status **PENDING HUMAN SIGN-OFF**.
   - **No migration execution is permitted until Gate 1 and Gate 2 are formally signed.**
   - Once signed, the Primary Migration Operator proceeds in accordance with the 8 phases of Section 4.
