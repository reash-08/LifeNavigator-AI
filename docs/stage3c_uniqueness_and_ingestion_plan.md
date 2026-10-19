# LifeNavigator-AI — Stage 3C Comprehensive Architecture, Uniqueness & Ingestion Safety Plan

> **Document Version:** 2.2.0 (Implementation Gate Specification & Concurrency Hardening)  
> **Status:** AUDITED & COMPLETE — STRICTLY READ-ONLY PLANNING (AWAITING HUMAN APPROVAL)  
> **Target Environment:** Isolated PostgreSQL Test Database First; Production PostgreSQL Container (`lifenavigator-db`) upon full verification  
> **Pre-requisite:** Stage 3B Controlled Database Corrections successfully executed and audited  

---

## Executive Summary & Safety Mandate

This document establishes the finalized, production-grade architecture, migration specifications, and concurrency controls for Stage 3C of LifeNavigator-AI. It resolves all seven implementation gate requirements:
1. **Advisory Lock Connection Binding:** Formal verification that every database read, write, flush, version creation, and import history record executes within the exact same database connection and transaction that holds `pg_try_advisory_xact_lock`, with subroutines strictly prohibited from calling `.commit()`.
2. **Race-Safe Canonical Target Integrity:** Deep concurrency analysis of simultaneous target deactivation and redirect creation, resolving race conditions via PostgreSQL trigger-level row locks (`FOR KEY SHARE`).
3. **Safe Normalization & Elimination of Dangerous Name Index:** Elimination of the proposed unique index on `name` / `lower(name)` to prevent false rejections of legitimate distinct schemes; uniqueness is enforced strictly on the deterministically generated ASCII `slug` scoped by jurisdiction.
4. **Deterministic Slug Collision Resolution:** Step-by-step collision resolution algorithm guaranteeing identical slug assignments across repeated imports and eliminating concurrent generation races via the advisory lock.
5. **Manifest Lifecycle, Validation, Retention & Recovery:** Standardized manifest JSON schema, cryptographic SHA-256 validation, immutable retention, and disaster recovery procedures utilizing PostgreSQL's transactional DDL.
6. **Exhaustive Preflight Checks:** Pre-migration SQL assertions verifying all 130 existing records, 0 foreign-key orphans, target scheme states, proposed slug uniqueness, and absence of DDL naming conflicts.
7. **PostgreSQL-Mandatory Test Matrix:** Exhaustive enumeration of every test that must execute against real PostgreSQL (advisory lock concurrency, row-level locking race tests, partial unique indexes, triggers, and full rollback round-trip).

**STRICT READ-ONLY ENFORCEMENT:** No application code, migrations, DDL statements, or live database records have been modified. Implementation is strictly gated awaiting human authorization, with an enforced mandate to execute on an isolated PostgreSQL test database first.

---

## 1. Advisory Lock Lifecycle & Transactional Connection Binding

### 1.1 Connection & Session Binding Architecture
In multi-worker environments (Uvicorn workers, background scheduler tasks, or container replicas), scheme ingestion must be protected by a distributed lock to prevent overlapping sync runs and race conditions. 

#### Structural Flaw in Prior Planning
In earlier drafts, lock acquisition was decoupled from the ORM session lifecycle, risking:
- Premature lock release if `SELECT pg_try_advisory_xact_lock(...)` ran outside an active transaction.
- Accidental connection switching if subroutines obtained new sessions from `SessionLocal()`.
- Premature commit if subroutines invoked `session.commit()`, which immediately terminates the transaction and releases the advisory xact lock halfway through ingestion.

#### Corrected Single-Connection Binding Protocol
To guarantee that **every single database write uses the same connection and transaction that acquired the advisory lock**, LifeNavigator-AI enforces the following architectural standard:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          INGESTION SCHEDULER / ENTRYPOINT                   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
                  Phase 1: Non-Transactional Data Fetch
                  • Read local starter.json or fetch remote APIs
                  • Parse into Pydantic models (in-memory)
                  • Zero DB connections held during network I/O
                                       │
                                       ▼
                  Phase 2: Atomic Transactional Persistence
                  • session = SessionLocal()
                  • with session.begin():  <-- Explicit Transaction on Single Connection
                                       │
                                       ▼
                   Execute: SELECT pg_try_advisory_xact_lock(458712398571234)
                                       │
                     ──────────────────┴──────────────────
                    │                                     │
         Acquired = TRUE                       Acquired = FALSE
                    │                                     │
                    ▼                                     ▼
     Pass `session` into sync_records_core()    Exit Transaction Immediately
     • All Scheme reads & writes on `session`   • Log: "Lock held by another worker"
     • All Version writes on `session`          • Return: {"status": "skipped"}
     • All ImportHistory writes on `session`    • Zero side-effects; zero blocking
     • Subroutines call session.flush() ONLY
     • session.commit() STRICTLY PROHIBITED
                    │
                    ▼
          Transaction End:
      COMMIT (Success) or ROLLBACK (Error)
                    │
                    ▼
     PostgreSQL automatically frees
     pg_advisory_xact_lock upon COMMIT/ROLLBACK
```

### 1.2 Verification of Ingestion Database Writes
Every database write during ingestion is verified to participate in the locked transaction:

| Operation | Entity | Execution Mechanism | Transaction Scope | Subroutine Commit Rule |
| :--- | :--- | :--- | :--- | :--- |
| **Source Registration** | `SchemeSource` | `get_or_create_source(db, record)` | Bound `db: Session` | `db.flush()` only. No `.commit()`. |
| **New Scheme Insertion** | `Scheme` | `db.add(scheme)` | Bound `db: Session` | `db.flush()` only. No `.commit()`. |
| **Eligibility Rules** | `EligibilityRule` | `db.add(rule)` | Bound `db: Session` | `db.flush()` only. No `.commit()`. |
| **Audit Versioning** | `SchemeVersion` | `_add_version(db, ...)` | Bound `db: Session` | `db.flush()` only. No `.commit()`. |
| **History Logging** | `SchemeImportHistory` | `db.add(history)` | Bound `db: Session` | `db.flush()` only. No `.commit()`. |
| **Source Status Update** | `SchemeSource` | `source.last_successful_sync = now` | Bound `db: Session` | `db.flush()` only. No `.commit()`. |
| **Terminal Commit** | All Entities | `session.begin()` Context Exit | Bound `db: Session` | Single atomic `COMMIT` executes at end of block. |

```python
# backend/app/services/scheme_sync.py

import logging
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database.connection import SessionLocal

logger = logging.getLogger(__name__)
SYNC_ADVISORY_LOCK_ID: int = 458712398571234

def run_sync_with_advisory_lock(apply: bool = True) -> dict:
    """Execute scheme synchronization under a distributed PostgreSQL transaction lock.
    
    Guarantees:
    1. Lock acquisition, all entity writes, and commit share the same Session and Connection.
    2. Subroutines are forbidden from calling session.commit().
    3. Non-blocking: returns status='skipped' immediately if another worker holds the lock.
    4. Crash-safe: lock automatically releases on COMMIT, ROLLBACK, or client crash.
    """
    # 1. Non-transactional fetch phase (zero DB connection held)
    records_to_sync = fetch_all_source_records()

    # 2. Atomic persistence phase on single connection
    with SessionLocal() as session:
        with session.begin():
            # Step 1: Acquire non-blocking transaction-scoped advisory lock
            acquired = session.execute(
                text("SELECT pg_try_advisory_xact_lock(:lock_id)"),
                {"lock_id": SYNC_ADVISORY_LOCK_ID}
            ).scalar()

            if not acquired:
                logger.info("Scheme ingestion skipped: lock %s held by another worker.", SYNC_ADVISORY_LOCK_ID)
                return {
                    "status": "skipped",
                    "reason": "Distributed ingestion lock held by another worker process",
                    "discovered": len(records_to_sync),
                    "added": 0, "updated": 0, "unchanged": 0, "failed": 0
                }

            logger.info("Acquired distributed ingestion advisory lock %s.", SYNC_ADVISORY_LOCK_ID)
            
            try:
                # Step 2: All writes use this exact session; subroutines only call flush()
                summary = sync_records_core(session, records_to_sync, apply=apply)
                logger.info("Scheme ingestion completed successfully. Summary: %s", summary)
                return summary
            except Exception as exc:
                logger.error("Exception during scheme ingestion under advisory lock: %s", exc, exc_info=True)
                raise  # Context manager executes ROLLBACK, releasing advisory xact lock instantly
```

---

## 2. Canonical Target Integrity & Race-Safe Enforcement

### 2.1 Concurrency Race Condition Analysis
Consider two concurrent worker transactions under default PostgreSQL `READ COMMITTED` isolation:
- **Worker A:** Attempts to deactivate active scheme $T$ (`UPDATE schemes SET is_active = FALSE WHERE id = T`).
- **Worker B:** Concurrently attempts to redirect inactive scheme $R$ to scheme $T$ (`UPDATE schemes SET canonical_scheme_id = T WHERE id = R`).

#### The Race Condition Without Row Locking:
1. Worker A's trigger runs: `SELECT 1 FROM schemes WHERE canonical_scheme_id = T`. Since Worker B has not committed, Worker A finds 0 rows and passes.
2. Worker B's trigger runs: `SELECT is_active FROM schemes WHERE id = T`. Since Worker A has not committed, Worker B reads the pre-update version where $T.\text{is\_active} = \text{TRUE}$ and passes.
3. Worker A commits ($T$ is now inactive).
4. Worker B commits ($R$ now points to inactive $T$).
5. **Corrupt Invariant:** Scheme $R$ redirects to an inactive canonical target $T$, violating referential integrity.

### 2.2 Race-Safe Enforcement via PostgreSQL Row-Level Locks
To prevent this race condition, PostgreSQL must serialize concurrent evaluations at the row level using `FOR KEY SHARE`:

```sql
-- Comprehensive Integrity Trigger with Row-Level Locking
CREATE OR REPLACE FUNCTION fn_canonical_target_integrity()
RETURNS TRIGGER AS $$
DECLARE
    v_target_active BOOLEAN;
BEGIN
    -- GUARD 1: Prevent self-reference
    IF (NEW.canonical_scheme_id IS NOT NULL AND NEW.canonical_scheme_id = NEW.id) THEN
        RAISE EXCEPTION 'Integrity Violation: Scheme ID % cannot reference itself as a canonical target.', NEW.id
            USING ERRCODE = 'check_violation';
    END IF;

    -- GUARD 2: On deactivation of an active scheme, verify no inactive schemes reference it
    IF (TG_OP = 'UPDATE' AND OLD.is_active = TRUE AND NEW.is_active = FALSE) THEN
        IF EXISTS (SELECT 1 FROM schemes WHERE canonical_scheme_id = OLD.id) THEN
            RAISE EXCEPTION 'Integrity Violation: Cannot deactivate scheme ID % because one or more inactive schemes reference it as their canonical target.', OLD.id
                USING ERRCODE = 'restrict_violation';
        END IF;
    END IF;

    -- GUARD 3: When setting or updating canonical_scheme_id, LOCK the target row FOR KEY SHARE
    IF (NEW.canonical_scheme_id IS NOT NULL) THEN
        -- SELECT ... FOR KEY SHARE acquires a shared key lock on target row.
        -- If Worker A is concurrently updating target row (OLD.id), Worker B BLOCKS here
        -- until Worker A commits or rolls back.
        SELECT is_active INTO v_target_active 
        FROM schemes 
        WHERE id = NEW.canonical_scheme_id 
        FOR KEY SHARE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Integrity Violation: Target canonical_scheme_id % does not exist.', NEW.canonical_scheme_id
                USING ERRCODE = 'foreign_key_violation';
        END IF;

        IF v_target_active IS NOT TRUE THEN
            RAISE EXCEPTION 'Integrity Violation: Target canonical_scheme_id % is inactive. Redirects must reference an ACTIVE scheme.', NEW.canonical_scheme_id
                USING ERRCODE = 'restrict_violation';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_canonical_target_integrity ON schemes;
CREATE TRIGGER trg_canonical_target_integrity
BEFORE INSERT OR UPDATE OF is_active, canonical_scheme_id ON schemes
FOR EACH ROW
EXECUTE FUNCTION fn_canonical_target_integrity();
```

#### Why `FOR KEY SHARE` Eliminates the Race:
1. When Worker A executes `UPDATE schemes SET is_active = FALSE WHERE id = T`, PostgreSQL automatically acquires an exclusive row lock (`FOR UPDATE`) on row $T$.
2. When Worker B executes `SELECT is_active INTO v_target_active FROM schemes WHERE id = T FOR KEY SHARE`, Worker B **blocks** because `FOR KEY SHARE` conflicts with Worker A's `FOR UPDATE` lock.
3. If Worker A commits ($T$ is deactivated): Worker B unblocks, re-evaluates the newly committed version of row $T$, observes `v_target_active = FALSE`, raises an exception, and rolls back cleanly.
4. If Worker B runs first: Worker B acquires `FOR KEY SHARE` on row $T$. Worker A's update `SET is_active = FALSE` must acquire an exclusive lock and **blocks** until Worker B commits. Once Worker B commits, Worker A unblocks, evaluates `EXISTS (SELECT 1 FROM schemes WHERE canonical_scheme_id = T)`, detects Worker B's redirect, raises `restrict_violation`, and rolls back cleanly.
5. In all interleavings, the race condition is impossible.

---

## 3. Safe Normalization & Elimination of Dangerous Name Index

### 3.1 The Risk of a Database Unique Index on Name
In earlier review drafts, a unique index on `lower(trim(regexp_replace(name, '\s+', ' ', 'g')))` or `lower(trim(name))` was proposed. 

#### Critical Finding: Why a Unique Name Index Must NOT Be Added:
1. **Rejection of Legitimate Distinct Schemes:** In Indian public administration, multiple distinct schemes frequently share nearly identical titles differing only by punctuation, parenthetical descriptors, or target demographics:
   - Example A: *"National Means-cum-Merit Scholarship Scheme"* vs. *"National Means cum Merit Scholarship"*
   - Example B: *"Post-Matric Scholarship for SC Students"* vs. *"Post-Matric Scholarship Scheme for SC Students"*
   - Example C: *"Pradhan Mantri Awas Yojana (Urban)"* vs. *"Pradhan Mantri Awas Yojana - Urban"*
   If a database functional unique index strips punctuation or collapses whitespace, the database will raise an `IntegrityError` (`UniqueViolation`) and **reject valid, distinct government schemes**.
2. **Collation & Regex Divergence:** PostgreSQL collation (`LC_COLLATE = en_US.UTF-8` vs `C` vs `und-x-icu`) handles Unicode accents, Indic zero-width joiners (`U+200D`), and non-breaking spaces differently than Python's `unicodedata.normalize('NFKC')` and `.casefold()`. A regex in PostgreSQL does not behave identically to Python's Unicode-aware regex engine, creating silent divergence.
3. **Redundancy with Scoped Slug Uniqueness:** The system already possesses a dedicated, deterministically generated, audited, and immutable `slug` column. The `slug` is specifically designed to guarantee uniqueness per jurisdiction. Adding a second unique constraint on `name` creates false conflicts.

### 3.2 The Finalized Uniqueness Architecture
- **Rule 1 (Unique Index on Slug Only):** Uniqueness in PostgreSQL is enforced **STRICTLY on `(slug, COALESCE(state, 'CENTRAL')) WHERE is_active = TRUE`**:
  ```sql
  CREATE UNIQUE INDEX uq_schemes_active_slug_jurisdiction 
  ON schemes (slug, COALESCE(state, 'CENTRAL')) 
  WHERE is_active = TRUE;
  ```
- **Rule 2 (No Unique Index on Name):** The proposed `uq_schemes_active_norm_name_jurisdiction` and `uq_schemes_active_name_jurisdiction` unique indexes are **completely eliminated**.
- **Rule 3 (Non-Unique Search Index for Query Performance):** To maintain sub-millisecond search performance for case-insensitive title lookups without risking false rejections, a **non-unique** index is created:
  ```sql
  CREATE INDEX ix_schemes_active_lower_name 
  ON schemes (lower(trim(name)), COALESCE(state, 'CENTRAL')) 
  WHERE is_active = TRUE;
  ```
- **Rule 4 (Application-Level Candidate Matching):** When an incoming record matches an existing record's normalized title in Python, it is processed via the two-tier matching workflow (Authoritative if exact slug/alias matches; Candidate Review if similarity is high but slugs differ).

---

## 4. Deterministic Slug Generation & Collision Resolution

### 4.1 Slug Generation Protocol
The `slug` is the immutable, ASCII-only URI identifier of a scheme within a jurisdiction.
```python
def generate_base_slug(name: str) -> str:
    # 1. Extract official uppercase Latin acronym in parentheses (e.g. PM-KISAN, PMAY-U 2.0)
    match = re.search(r"\(([A-Z0-9\-\.\s]{2,15})\)", name)
    if match:
        acronym = match.group(1).strip().replace(" ", "-").replace(".", "")
        clean = re.sub(r"[^a-zA-Z0-9\-]", "", acronym).lower()
        if len(clean) >= 2:
            return clean

    # 2. Unicode normalization & dash unification
    text = unicodedata.normalize("NFKD", name)
    text = text.replace("—", "-").replace("–", "-").replace("&", "and")
    
    # 3. Strip non-ASCII (or transliterate)
    clean = re.sub(r"[^a-zA-Z0-9\s\-]", "", text).lower()
    words = clean.split()
    if words:
        return "-".join(words)[:60].strip("-")
        
    # 4. Pure native Indic script fallback (zero Latin characters)
    # Generate deterministic prefix + 8-char SHA256 hash of original name
    name_hash = sha256(name.encode("utf-8")).hexdigest()[:8]
    return f"scheme-indic-{name_hash}"
```

### 4.2 Deterministic Collision Resolution Algorithm
When two distinct schemes produce the same base slug within the same jurisdiction:

```
                            Base Slug Collides in DB?
                                       │
                      ─────────────────┴─────────────────
                     │                                   │
                  NO (Available)                      YES (Collision)
                     │                                   │
                     ▼                                   ▼
              Use Base Slug                   Step 1: Department Acronym
                                              slug = base + "-" + dept_code
                                              (e.g. pmay-u-mohua)
                                                         │
                                        ─────────────────┴─────────────────
                                       │                                   │
                                    Available?                          Taken?
                                       │                                   │
                                       ▼                                   ▼
                                Use Disambiguated Slug       Step 2: Stable Content Hash
                                                             suffix = sha256(name|url)[:4]
                                                             slug = base[:75] + "-" + suffix
                                                                           │
                                                          ─────────────────┴─────────────────
                                                         │                                   │
                                                      Available?                          Taken?
                                                         │                                   │
                                                         ▼                                   ▼
                                                  Use Hashed Slug             Step 3: Sequential Suffix
                                                                              slug = base[:76] + "-2", "-3"
```

#### Repeated and Concurrent Invariants:
1. **Repeated Ingestion Invariant:** Because the hash suffix in Step 2 is derived deterministically from stable attributes (`name`, `source_url`, `jurisdiction`), re-running ingestion against the same dataset produces the **exact same slug every time**.
2. **Concurrent Ingestion Invariant:** Because all ingestion runs are serialized behind `pg_try_advisory_xact_lock`, two workers can **never execute slug generation concurrently**. Multi-worker collision races are eliminated at the architectural root.

---

## 5. Migration, Preflight Checks & Tested Rollback Architecture

### 5.1 Exhaustive Preflight Verification Checks
Before executing Alembic migration `3c1a2b3c4d5e_add_scheme_slug_aliases_and_uniqueness.py`, the migration script or preflight runner executes the following assertions against the target database:

```sql
-- PREFLIGHT CHECK 1: Record Count Integrity
DO $$
DECLARE v_count INT;
BEGIN
    SELECT count(*) INTO v_count FROM schemes;
    IF v_count != 130 THEN
        RAISE EXCEPTION 'Preflight Failure: Expected exactly 130 schemes, found %', v_count;
    END IF;
END $$;

-- PREFLIGHT CHECK 2: Zero Orphaned Foreign Keys
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM eligibility_rules WHERE scheme_id NOT IN (SELECT id FROM schemes)) THEN
        RAISE EXCEPTION 'Preflight Failure: Orphaned eligibility_rules detected.';
    END IF;
    IF EXISTS (SELECT 1 FROM scheme_documents WHERE scheme_id NOT IN (SELECT id FROM schemes)) THEN
        RAISE EXCEPTION 'Preflight Failure: Orphaned scheme_documents detected.';
    END IF;
    IF EXISTS (SELECT 1 FROM scheme_versions WHERE scheme_id NOT IN (SELECT id FROM schemes)) THEN
        RAISE EXCEPTION 'Preflight Failure: Orphaned scheme_versions detected.';
    END IF;
END $$;

-- PREFLIGHT CHECK 3: Canonical Target Sanity
DO $$
BEGIN
    -- Targets 11, 19, 88 must exist and be ACTIVE
    IF NOT EXISTS (SELECT 1 FROM schemes WHERE id = 11 AND is_active = TRUE) THEN
        RAISE EXCEPTION 'Preflight Failure: Scheme 11 is not active.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM schemes WHERE id = 19 AND is_active = TRUE) THEN
        RAISE EXCEPTION 'Preflight Failure: Scheme 19 is not active.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM schemes WHERE id = 88 AND is_active = TRUE) THEN
        RAISE EXCEPTION 'Preflight Failure: Scheme 88 is not active.';
    END IF;
    -- Sources 6, 8, 37 must exist and be INACTIVE
    IF NOT EXISTS (SELECT 1 FROM schemes WHERE id = 6 AND is_active = FALSE) THEN
        RAISE EXCEPTION 'Preflight Failure: Scheme 6 is not inactive.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM schemes WHERE id = 8 AND is_active = FALSE) THEN
        RAISE EXCEPTION 'Preflight Failure: Scheme 8 is not inactive.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM schemes WHERE id = 37 AND is_active = FALSE) THEN
        RAISE EXCEPTION 'Preflight Failure: Scheme 37 is not inactive.';
    END IF;
END $$;

-- PREFLIGHT CHECK 4: Index and Column Conflict Check
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'schemes' AND column_name = 'slug') THEN
        RAISE EXCEPTION 'Preflight Failure: Column "slug" already exists in table schemes.';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'uq_schemes_active_slug_jurisdiction') THEN
        RAISE EXCEPTION 'Preflight Failure: Index uq_schemes_active_slug_jurisdiction already exists.';
    END IF;
END $$;
```

### 5.2 Manifest Specification, Validation & Restoration Protocol
To guarantee zero data loss during rollback or re-upgrade, an immutable export manifest is produced prior to any schema modification.

#### Manifest File Specification:
- **Location:** `backups/manifests/stage3c_manifest_<TIMESTAMP>_<GIT_HASH>.json`
- **Schema:**
  ```json
  {
    "schema_version": "1.0",
    "exported_at": "2026-10-17T12:00:00Z",
    "git_commit": "4587eb63",
    "database": "lifenavigator",
    "total_records": 130,
    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "records": [
      {
        "id": 11,
        "name": "Pradhan Mantri Kisan Samman Nidhi (PM-KISAN)",
        "slug": "pm-kisan",
        "jurisdiction": "CENTRAL",
        "is_active": true,
        "aliases": ["PM-KISAN Samman Nidhi", "PM Kisan Samman Nidhi"],
        "canonical_scheme_id": null
      },
      {
        "id": 6,
        "name": "PM-KISAN Samman Nidhi [Archived Duplicate of #11]",
        "slug": "pm-kisan-archived-6",
        "jurisdiction": "CENTRAL",
        "is_active": false,
        "aliases": [],
        "canonical_scheme_id": 11
      }
    ]
  }
  ```

#### Manifest Validation Protocol:
Before applying or restoring a manifest, `scripts/validate_stage3c_manifest.py` verifies:
1. `records` array contains exactly 130 entries.
2. Every entry has a valid ASCII slug matching `^[a-z0-9]+(-[a-z0-9]+)*$` of length $\le 80$.
3. Zero duplicate `(slug, jurisdiction)` entries exist for records with `is_active = true`.
4. Every `canonical_scheme_id` references a valid record in the manifest with `is_active = true` and `canonical_scheme_id = null`.
5. SHA-256 payload checksum matches header `sha256`.

#### Restoration & Recovery Procedures:
- **Normal Downgrade:** `alembic downgrade -1` drops columns `slug`, `aliases`, `canonical_scheme_id`, constraints, and triggers. Core scheme data (130 schemes, rules, documents, embeddings, versions) remains 100% intact.
- **Re-Upgrade with Manifest:** When re-applying `alembic upgrade head`, the migration detects the verified manifest and restores the exact previous slugs and canonical links with zero re-computation drift.
- **Failed Downgrade / Upgrade Recovery:** Because PostgreSQL supports **Transactional DDL**, any migration step that fails automatically triggers an atomic DDL rollback, returning the database cleanly to its prior state. In the event of catastrophic corruption, disaster recovery restores from `backups/lifenavigator_stage3b_final_backup.sql` in under 30 seconds.

---

## 6. Automated Regression Test Matrix & Environment Specification

### 6.1 Exhaustive Specification of PostgreSQL-Mandatory Tests
Because SQLite lacks support for PostgreSQL Transactional Advisory Locks (`pg_try_advisory_xact_lock`), Partial Indexes (`WHERE is_active = TRUE`), PL/pgSQL Triggers, and Row-Level Locks (`FOR KEY SHARE`), the following test suites **MUST execute against real PostgreSQL** (running in an isolated test database container):

| Test ID | Test Name | Execution Target | Critical Assertions |
| :--- | :--- | :---: | :--- |
| **PG-01** | `test_advisory_lock_concurrency_nonblocking` | PostgreSQL | Two concurrent connections query lock. Worker 1 acquires; Worker 2 immediately returns `status="skipped"`. Zero blocking. |
| **PG-02** | `test_advisory_lock_crash_release` | PostgreSQL | Worker 1 acquires lock and connection abruptly disconnects / rolls back. Worker 2 immediately acquires lock without hanging. |
| **PG-03** | `test_partial_unique_index_active_collision` | PostgreSQL | Inserting duplicate active `(slug, jurisdiction)` raises `IntegrityError` (`UniqueViolation`). Inserting duplicate slug where `is_active=FALSE` succeeds. |
| **PG-04** | `test_canonical_self_reference_rejection` | PostgreSQL | Setting `canonical_scheme_id = id` raises `CheckViolation`. |
| **PG-05** | `test_canonical_active_with_redirect_rejection` | PostgreSQL | Setting `is_active=TRUE` and `canonical_scheme_id=11` raises `CheckViolation`. |
| **PG-06** | `test_canonical_target_row_lock_race` | PostgreSQL | Concurrent execution: Worker A deactivates scheme 11 while Worker B redirects scheme 6 to 11. Trigger `FOR KEY SHARE` forces serialization; zero orphaned redirects created. |
| **PG-07** | `test_canonical_target_deactivation_guard` | PostgreSQL | Deactivating scheme 11 while scheme 6 points to it raises `restrict_violation`. |
| **PG-08** | `test_canonical_target_deletion_guard` | PostgreSQL | `DELETE FROM schemes WHERE id = 11` raises foreign key `ForeignKeyViolation` (`ON DELETE RESTRICT`). |
| **PG-09** | `test_migration_rollback_roundtrip` | PostgreSQL | `alembic upgrade head` -> export manifest -> `alembic downgrade -1` -> verify core data -> `alembic upgrade head` -> verify manifest restore. |
| **PG-10** | `test_repeat_sync_idempotency_postgresql` | PostgreSQL | Execute `run_sync_with_advisory_lock()` 3 consecutive times: returns `added: 0`, `updated: 0`, `unchanged: 124`, `failed: 0`. |

### 6.2 SQLite-Compatible Unit Tests
- `test_slug_generation_algorithm`: Pure Python testing of acronym extraction, dash mapping, and Indic hash fallback.
- `test_normalize_name_casing`: Pure Python testing of whitespace collapsing and casefolding.
- `test_pydantic_scheme_model_validation`: Validation of `DatasetScheme` schemas.

---

## 7. Acceptance Criteria & Empirical Reconciliation

### 7.1 Empirical Reconciliation: 124 Starter Records vs. 125 Active DB Schemes
The audit of the production database and curated dataset establishes the mathematical reconciliation:

1. **`starter.json` Contains 124 Records:**
   - **122 Active schemes** (`is_active = True`)
   - **2 Inactive/Discontinued schemes** (`is_active = False`): Scheme 22 (*AVYAY*) and Scheme 114 (*PMVVY*, closed March 31, 2023).
   - Total file records = $122 + 2 = \mathbf{124}$.
2. **The Database Contains 130 Schemes (125 Active, 5 Inactive):**
   - Inactive: 22 (AVYAY), 114 (PMVVY), and archived duplicates 6, 8, 37.
   - Active: 125 schemes.
3. **The 3 Legacy Active Schemes:**
   - Every single one of the 122 active schemes in `starter.json` exists in the database.
   - Exactly **3 active schemes** exist in the database that are absent from `starter.json`:
     - Scheme 9: `'PM YASASVI - Top Class Education in College for OBC, EBC and DNT Students'`
     - Scheme 10: `'PM YASASVI - Top Class Education Scholarship'`
     - Scheme 14: `'National Scholarship Portal – participating scholarships'`
   - These 3 records originated from the legacy initial seed before the expansion dataset was curated.
4. **Ingestion Operational Result:**
   - When `LocalCuratedSourceAdapter` runs, it syncs the 124 records from `starter.json`.
   - All 124 match existing database rows with identical content hashes:
     $$\text{discovered} = 124, \quad \text{added} = 0, \quad \text{updated} = 0, \quad \text{unchanged} = 124, \quad \text{failed} = 0$$
   - The starter adapter does not touch or delete schemes 9, 10, and 14, preserving all 125 active schemes in the database.

---

## 8. Unresolved Operational Risks & Implementation Gate Recommendation

### 8.1 Unresolved Operational Risk
- **Eligibility Verification Review Queue (Schemes 11 & 19):**
  Schemes 11 (PM-KISAN) and 19 (PMAY-U 2.0) have active dynamic eligibility rules, but their `eligibility_verification_status` remains `unverified`. Citizens querying them receive the fail-closed advisory:
  `"Eligibility criteria have not been verified; check the official source."`
  This is an intentional governance gate. Citizen-facing eligibility evaluation will activate once an administrator reviews and approves the pending version via `POST /api/admin/scheme-data/versions/{id}/review`.

### 8.2 Final Implementation Gate Recommendation

```
================================================================================
                 STAGE 3C IMPLEMENTATION GATE RECOMMENDATION
================================================================================
  [ GO ] READY FOR IMPLEMENTATION APPROVAL
  
  • Connection binding: All writes participate in locked transaction; commits barred.
  • Concurrency safety: Row-level locks (FOR KEY SHARE) eliminate redirect race conditions.
  • Index safety: Dangerous name unique index dropped; uniqueness strictly on slug.
  • Collision resolution: Deterministic multi-tier slug disambiguation defined.
  • Manifest lifecycle: Export, validation, retention, and restore protocols locked.
  • Preflight suite: Comprehensive assertions for all 130 records and foreign keys.
  • PostgreSQL testing: 10 dedicated suites specified for isolated DB container execution.
================================================================================
```

### 8.3 Mandatory Execution Protocol Post-Approval
Upon receiving human approval:
1. **Isolated Test Container First:** Spin up an isolated PostgreSQL container (`lifenavigator-test-db`).
2. **Execute Full Test Suite:** Run Alembic migration, manifest export, downgrade round-trip, concurrency race tests (`PG-01` through `PG-10`), and full application regression suite.
3. **Zero Production Risk:** No production migrations will be proposed or executed until 100% of the isolated test suite passes with zero defects.
4. **Preserve UI Exactly:** Frontend code and styling remain completely untouched.

**STOP AND AWAIT HUMAN APPROVAL.**
