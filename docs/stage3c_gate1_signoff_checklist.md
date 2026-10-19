# LifeNavigator-AI — Stage 3C Gate 1 Scheduling Approval Checklist

> **DOCUMENT STATUS:** **PENDING HUMAN SIGN-OFF**  
> **Operational Scope:** GATE 1 MAINTENANCE WINDOW SCHEDULING ONLY — **NO PRODUCTION EXECUTION**  
> **Governing Specifications:**  
> - Authorisation & Handover Record: [`docs/stage3c_human_authorization_handover.md`](file:///c:/GitHub/LifeNavigator-AI/docs/stage3c_human_authorization_handover.md)  
> - Production Readiness Checklist: [`docs/stage3c_production_readiness_checklist.md`](file:///c:/GitHub/LifeNavigator-AI/docs/stage3c_production_readiness_checklist.md)  
> - Migration Runbook: [`docs/stage3c_production_migration_plan.md`](file:///c:/GitHub/LifeNavigator-AI/docs/stage3c_production_migration_plan.md)  

---

## 1. Critical Boundary & Authority Clarification

### What Gate 1 Authorizes:
- **Reserving the Scheduled Maintenance Window:** Approves reserving a designated 30-minute off-peak operational window.
- **Publishing Stakeholder Communications:** Authorizes issuing T-24h user and support notices regarding planned read-only maintenance.
- **Rostering Operational Personnel:** Formally assigns the Primary Migration Operator, Approving Authority, and Independent Recovery Operator.
- **Assigning Risk Ownership:** Assigns named owners and due dates for documented operational limitations.

### What Gate 1 STRICTLY DOES NOT Authorize:
- **DOES NOT Authorize Migration Execution:** No Alembic DDL commands (`alembic upgrade`, `run_production_migration.py upgrade`) may be run.
- **DOES NOT Authorize Production Traffic Pause:** Application traffic may not be stopped until the approved window commences.
- **DOES NOT Authorize Entering Confirmation Tokens:** The token `YES-MIGRATE-PRODUCTION` must never be entered under Gate 1.
- **DOES NOT Modify Live Database:** Zero live connections, backups, restores, or SQL writes are permitted under Gate 1.

> **CRITICAL OPERATIONAL RULE:** Execution of migration DDL requires a separate, explicit **Gate 2 Sign-Off** inside the scheduled maintenance window after Phase 1 (host health), Phase 2 (traffic paused, 0 active transactions), Phase 3 (native backup dump created and test-restored), and Phase 4 (`--preflight-only` runner check) have all successfully passed.

---

## 2. Gate 1 Human Input Requirements & Pre-Populated System Invariants

### 2.1 System Invariants (Pre-Populated & Verified from Repository Evidence)
- **Target Application:** LifeNavigator-AI Production Backend
- **Target Container:** `lifenavigator-db` (`pgvector/pgvector:pg16` on Docker network `lifenavigator-net`)
- **Target Database Name:** `lifenavigator`
- **Target Database User:** `lifenavigator`
- **Target Internal Port:** `5432`
- **Target Alembic Revision:** `3c1a2b3c4d5e` (`add scheme slug, aliases, canonical redirect and uniqueness constraints`)
- **Verified Parent Revision:** `e1a89b72c431` (`add embedding to chunks and sync metadata to documents and sources`)
- **Revision Lineage:** Linear 14-revision graph from root `427befa634e8` to `3c1a2b3c4d5e` (0 branches, 0 merge heads)
- **Isolated Test Evidence:**
  - Production Runner Suite: 12 tests passed in 0.32s ([`tests/test_production_migration_runner.py`](file:///c:/GitHub/LifeNavigator-AI/tests/test_production_migration_runner.py))
  - PostgreSQL Matrix Suite: 18 tests passed in 2.67s ([`tests/test_stage3c_postgresql_matrix.py`](file:///c:/GitHub/LifeNavigator-AI/tests/test_stage3c_postgresql_matrix.py))
  - Preflight Isolation: `--preflight-only` confirmed to exit immediately without reaching Alembic execution paths
- **Governance Gate Preservation:** Schemes 11 (PM-KISAN) and 19 (PMAY-U 2.0) preserved as `eligibility_verification_status = 'unverified'` with fail-closed citizen advisory
- **Frontend Code Preservation:** Zero modifications to `frontend/`; stale assertion in `frontend/test/e2e_sequence.test.js:60` (`128`) deferred to separate maintenance PR

---

### 2.2 Missing Information Checklist (Requires Authorized Human Input)

The following fields must be supplied by the designated human authorities. No values may be assumed or invented.

| Category | Field Identifier | Required Human Input | Status |
| :--- | :--- | :--- | :---: |
| **Change Control** | `CHG-REF` | Formal Change Ticket Reference (e.g., `OPS-CHG-20261017-01`) | `[Pending Human Input]` |
| **Infrastructure** | `HOST-ID` | Production Docker Host Identifier / IP Address | `[Pending Human Input]` |
| **Schedule** | `MAINT-DATE` | Scheduled Maintenance Window Date (`YYYY-MM-DD`) | `[Pending Human Input]` |
| **Schedule** | `MAINT-TIME` | Scheduled Maintenance Window Start Time (`HH:MM`) | `[Pending Human Input]` |
| **Schedule** | `MAINT-TZ` | Maintenance Window Timezone (e.g., `UTC` / `IST`) | `[Pending Human Input]` |
| **Personnel** | `OP-PRIMARY` | Primary Migration Operator (Full Name, Title, Contact) | `[Pending Human Input]` |
| **Personnel** | `OP-LEAD` | Approving Authority / Lead DBA (Full Name, Title, Contact) | `[Pending Human Input]` |
| **Personnel** | `OP-RECOVERY` | Independent Recovery Operator (Full Name, Title, Contact) | `[Pending Human Input]` |
| **Communications**| `COMMS-CHAN` | Incident Bridge / War Room Channel Link | `[Pending Human Input]` |
| **Risk Owner** | `OWNER-TLS` | Accountable Owner & Target Due Date: Edge TLS Termination | `[Pending Human Input]` |
| **Risk Owner** | `OWNER-PORT` | Accountable Owner & Target Due Date: Host Port 8000 Firewalling | `[Pending Human Input]` |
| **Risk Owner** | `OWNER-RL` | Accountable Owner & Target Due Date: In-Memory Rate Limiting Redis Migration | `[Pending Human Input]` |
| **Risk Owner** | `OWNER-LOCK` | Accountable Owner & Target Due Date: Scheduler Worker Audit | `[Pending Human Input]` |
| **Risk Owner** | `OWNER-FE` | Accountable Owner & Target Due Date: Frontend Test Assertion PR (`#60`) | `[Pending Human Input]` |

---

## 3. Pre-Requisite Verification Checklist for Gate 1

Before signing Gate 1, the Approving Authority must confirm that the following operational pre-requisites are met:

- [ ] **Technical Readiness Verified:** The Stage 3C Production Readiness Checklist ([`docs/stage3c_production_readiness_checklist.md`](file:///c:/GitHub/LifeNavigator-AI/docs/stage3c_production_readiness_checklist.md)) has been reviewed and all 21 technical gates are verified **PASS**.
- [ ] **Off-Peak Window Selected:** The proposed window occurs during low-traffic hours (recommended: Sunday 02:00–02:30 UTC) with an established 30-minute duration.
- [ ] **Hard Rollback Deadline Understood:** The T+15 minute hard stop rule is accepted: if migration execution and initial post-checks exceed 15 minutes from initiation, the rollout aborts and triggers rollback.
- [ ] **Dual-Operator Redundancy Confirmed:** The Primary Migration Operator and Independent Recovery Operator are two separate individuals, both having verified console/host access.
- [ ] **Zero-RPO Protocol Confirmed:** The procedure to stop the backend container (`docker compose stop backend`) and verify zero active transactions in `pg_stat_activity` prior to dump creation is confirmed.
- [ ] **Backup Verification Protocol Confirmed:** The mandate to run `native_db_backup.py --verify-restore` (creating dump, checking TOC, and test-restoring into temporary DB `lifenavigator_test_restore`) before migration is confirmed.
- [ ] **Disaster Recovery Rule Understood:** The mandate to restore to `lifenavigator_recovery_verify` first and execute an atomic rename swap (preserving `lifenavigator_corrupted`), rather than dropping the live database, is confirmed.
- [ ] **Non-Destructive Failure Rule Understood:** The rule strictly prohibiting database downgrade upon backend container startup failures (inspecting container logs instead) is acknowledged.
- [ ] **Governance & Frontend Separation Confirmed:** Schemes 11 and 19 remain unverified; the frontend test assertion update remains decoupled in a separate frontend PR.
- [ ] **Accountable Risk Ownership Assigned:** Named owners and due dates are populated in Section 4 below.

---

## 4. Operational Risk Register & Assigned Ownership

The following operational items must have an accountable owner and target due date assigned prior to completing Gate 1 sign-off:

| Risk Item | Nature of Limitation | Current Operational Mitigation | Accountable Owner | Target Due Date |
| :--- | :--- | :--- | :--- | :--- |
| **TLS Termination** | Nginx listens on HTTP ports 80/3000 without SSL. | Edge termination at Cloudflare / AWS Application Load Balancer. | `[Pending Human Input]` | `[Pending Human Input]` |
| **Backend Port Exposure** | Port 8000 mapped to `0.0.0.0:8000` in Compose. | Host firewall restricts port 8000 to internal traffic; access via Nginx. | `[Pending Human Input]` | `[Pending Human Input]` |
| **In-Memory Rate Limiting** | `slowapi` tracks rate limits in process memory. | Single-worker Uvicorn deployment in production container. | `[Pending Human Input]` | `[Pending Human Input]` |
| **Scheduler Multi-Worker Locking** | In-memory `threading.Lock()` does not span containers. | Stage 3C resolves this via database `pg_try_advisory_xact_lock(458712398571234)`. | `[Pending Human Input]` | `[Pending Human Input]` |
| **Stale Frontend Test Assertion** | `frontend/test/e2e_sequence.test.js:60` asserts 128 instead of 125. | Tracked as a separate frontend maintenance PR; frontend untouched in 3C. | `[Pending Human Input]` | `[Pending Human Input]` |

---

## 5. Stakeholder Communication & Notification Plan

| Milestone | Target Timing | Communication Channel | Audience | Message / Action Summary |
| :---: | :---: | :--- | :--- | :--- |
| **T-24h** | 24 hours prior to window | Email / Slack Broadcast | Internal Users & Support | Announce scheduled 30-minute maintenance window; state expected read-only window. |
| **T-1h** | 1 hour prior to window | Operational War Room | Operational Migration Team | Primary Operator, Lead DBA, and Recovery Operator assemble on bridge; check host disk. |
| **T-0** | Window start | User Banner / Web Proxy | External Citizens & Users | Enable frontend maintenance banner; pause backend traffic. |
| **T+15m** | Rollback cutoff | Operational War Room | Operational Migration Team | Stop/Go decision point: if post-checks unverified, initiate Rollback Option A or B. |
| **T+25m** | Service resumption | User Banner / Status Page | External Citizens & Users | Remove maintenance banner; confirm API health; announce resumption of normal operations. |
| **T+60m** | Post-monitoring close | Email / Ticket Update | Stakeholders & Support | Confirm 60-minute monitoring window completed with zero 500 error spikes; close ticket. |

---

## 6. Formal Gate 1 Sign-Off Record

*This section must be completed and signed by the designated Approving Authority to authorize window scheduling.*

```text
================================================================================
                    STAGE 3C GATE 1 SCHEDULING APPROVAL RECORD
================================================================================

Change Management Ticket Ref : [Pending Human Input]
Production Docker Host       : [Pending Human Input]
Scheduled Maintenance Date   : [Pending Human Input]
Scheduled Window Start Time  : [Pending Human Input]
Timezone                     : [Pending Human Input]
Planned Duration             : 30 minutes (Hard rollback cutoff: T+15 minutes)

Primary Migration Operator   : [Pending Human Input]
Approving Authority (Lead)   : [Pending Human Input]
Independent Recovery Operator: [Pending Human Input]
Emergency Incident Bridge    : [Pending Human Input]

AFFIRMATIONS:
[ ] I confirm that all pre-requisites in Section 3 are verified.
[ ] I confirm that the operational risk owners in Section 4 are assigned.
[ ] I confirm that this approval authorizes scheduling the maintenance window ONLY.
[ ] I explicitly understand that executing migration DDL requires a separate,
    explicit Gate 2 sign-off inside the window after writer pause, backup,
    isolated restore verification, and preflight assertions succeed.

GATE 1 DECISION:
[  ] APPROVED FOR SCHEDULING
[  ] REJECTED
[  ] PENDING FURTHER REVIEW

Approving Authority Name     : [Pending Human Input]
Title / Organizational Role  : [Pending Human Input]
Approval Date & Time         : [Pending Human Input]
Signature / Cryptographic Sig: [Pending Human Input]

================================================================================
```

---

## 7. Next Actions Following Gate 1 Approval

Once Gate 1 is signed by the Approving Authority:
1. File the completed record in the change management tracking system under the reference ticket.
2. Issue the T-24h stakeholder maintenance notice.
3. Convene the operational bridge 1 hour prior to the scheduled window start.
4. When the maintenance window commences, proceed to **Phase 1 through Phase 4** of [`docs/stage3c_human_authorization_handover.md`](file:///c:/GitHub/LifeNavigator-AI/docs/stage3c_human_authorization_handover.md).
5. Review Phase 1–4 evidence with the Approving Authority to seek **Gate 2: Approval to Execute Migration**.
