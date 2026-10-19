"""Safe, deterministic scheme imports with version history, advisory locking, and uniqueness enforcement."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
import logging
from collections import Counter
from collections.abc import Iterable
from urllib.parse import urlparse

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from app.database.connection import SessionLocal
from app.models.eligibility_rule import EligibilityRule
from app.models.scheme import Scheme
from app.models.scheme_source import SchemeImportHistory, SchemeSource, SchemeVersion
from app.services.slug_generator import generate_base_slug, resolve_slug_collision

logger = logging.getLogger(__name__)

# Deterministic 64-bit integer derived from LifeNavigator ingestion namespace
SYNC_ADVISORY_LOCK_ID: int = 458712398571234


def normalize_name(value: str) -> str:
    return " ".join(value.casefold().split())


def is_official_source_url(value: str) -> bool:
    parsed = urlparse(value)
    host = (parsed.hostname or "").casefold()
    return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username and not parsed.password and (
        host == "gov.in" or host.endswith(".gov.in") or host == "nic.in" or host.endswith(".nic.in")
        or host in {"pmkvyofficial.org", "www.pmkvyofficial.org"}
    )


def _canonical_json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def snapshot_hash(value: dict) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def record_snapshot(record) -> dict:
    scheme_data = record.model_dump(
        mode="json",
        exclude={"eligibility_rules", "aliases", "api_url", "source_type", "effective_from", "effective_until", "slug", "canonical_scheme_id"},
    )
    rules = [item.model_dump(mode="json") for item in record.validated_models()[1]]
    rules.sort(key=lambda item: (item["field_name"], item["operator"], item["value"], item.get("group_id") or 0))
    return {**scheme_data, "eligibility_rules": rules}


def scheme_snapshot(scheme: Scheme) -> dict:
    values = {
        column.name: getattr(scheme, column.name)
        for column in Scheme.__table__.columns
        if column.name not in {"id", "source_id", "slug", "aliases", "canonical_scheme_id"}
    }
    values["eligibility_rules"] = [
        {
            "field_name": rule.field_name,
            "operator": rule.operator,
            "value": rule.value,
            "group_id": rule.group_id,
            "logical_operator": rule.logical_operator,
        }
        for rule in sorted(
            scheme.eligibility_rules,
            key=lambda item: (item.field_name, item.operator, item.value, item.group_id or 0),
        )
    ]
    return json.loads(json.dumps(values, ensure_ascii=False, default=lambda value: value.isoformat() if hasattr(value, "isoformat") else str(value)))


@dataclass
class SyncSummary:
    discovered: int = 0
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    failed: int = 0
    details: list[dict] = field(default_factory=list)


def get_or_create_source(db: Session, record) -> SchemeSource:
    source = db.scalar(
        select(SchemeSource).where(
            SchemeSource.source_name == record.source_name,
            SchemeSource.source_url == record.source_url,
        )
    )
    if source:
        return source
    source = SchemeSource(
        source_name=record.source_name,
        source_url=record.source_url,
        api_url=record.api_url,
        provider=record.ministry,
        source_type=record.source_type,
        is_active=True,
        notes="Registered from the curated local scheme dataset; automated fetching is not enabled.",
    )
    db.add(source)
    db.flush()
    return source


def _add_version(
    db: Session,
    scheme: Scheme,
    record,
    snapshot: dict,
    source: SchemeSource,
    summary: str,
    *,
    verification_status: str = "pending",
) -> SchemeVersion:
    next_version = (db.scalar(
        select(func.max(SchemeVersion.version_number)).where(SchemeVersion.scheme_id == scheme.id)
    ) or 0) + 1
    version = SchemeVersion(
        scheme_id=scheme.id,
        source_id=source.id,
        version_number=next_version,
        snapshot=snapshot,
        source_url=record.source_url,
        verification_status=verification_status,
        eligibility_verification_status=record.eligibility_verification_status,
        verified_at=record.verified_at,
        effective_from=record.effective_from,
        effective_until=record.effective_until,
        change_summary=summary,
        content_hash=snapshot_hash(snapshot),
    )
    db.add(version)
    db.flush()
    return version


def sync_records(db: Session, records: Iterable, *, apply: bool, verify_curated: bool = False) -> SyncSummary:
    """Preview or apply records with Stage 3C uniqueness, slug resolution, and candidate review.
    
    Subroutines call db.flush() only. Commits are managed by the outer transaction block.
    """
    items = list(records)
    summary = SyncSummary(discovered=len(items))
    existing = list(db.scalars(select(Scheme).options(selectinload(Scheme.eligibility_rules))))

    # Index existing schemes by (slug, jurisdiction) and (normalized_name, jurisdiction)
    by_slug_juris: dict[tuple[str, str], Scheme] = {}
    by_name_juris: dict[tuple[str, str], Scheme] = {}
    used_slugs_by_juris: dict[str, set[str]] = {}

    alias_counts: Counter[tuple[str, str]] = Counter()
    scheme_by_alias: dict[tuple[str, str], Scheme] = {}

    for s in existing:
        juris = (s.state or "CENTRAL").upper()
        if s.slug:
            by_slug_juris[(s.slug, juris)] = s
            if s.is_active:
                used_slugs_by_juris.setdefault(juris, set()).add(s.slug)
        by_name_juris[(normalize_name(s.name), juris)] = s

        # Tally aliases for ambiguity detection
        raw_aliases = s.aliases if isinstance(s.aliases, list) else []
        for a in raw_aliases:
            norm_a = normalize_name(a)
            alias_key = (norm_a, juris)
            alias_counts[alias_key] += 1
            scheme_by_alias[alias_key] = s

    # Filter out ambiguous aliases (aliases claiming > 1 scheme within jurisdiction)
    unambiguous_alias_map: dict[tuple[str, str], Scheme] = {
        k: scheme_by_alias[k] for k, count in alias_counts.items() if count == 1
    }

    seen_in_batch: set[tuple[str, str]] = set()
    per_source: dict[tuple[str, str], dict] = {}

    for record in items:
        jurisdiction = (record.state or "CENTRAL").upper()
        name_key = normalize_name(record.name)
        candidate_slug = generate_base_slug(record.name)

        source_key = (record.source_name, record.source_url)
        bucket = per_source.setdefault(
            source_key,
            {"discovered": 0, "added": 0, "updated": 0, "unchanged": 0, "skipped": 0, "failed": 0, "details": []}
        )
        bucket["discovered"] += 1

        # Check for duplicates within the incoming batch
        batch_id_key = (name_key, jurisdiction)
        if batch_id_key in seen_in_batch:
            summary.skipped += 1
            bucket["skipped"] += 1
            bucket["details"].append({"scheme": record.name, "result": "duplicate_in_dataset"})
            continue
        seen_in_batch.add(batch_id_key)

        # 1. Authoritative Tier Matching
        exact = by_slug_juris.get((candidate_slug, jurisdiction))
        if exact is None:
            exact = by_name_juris.get((name_key, jurisdiction))

        # Check unambiguous persistent aliases in DB if still no match
        if exact is None:
            for alias in getattr(record, "aliases", []):
                norm_a = normalize_name(alias)
                matched_via_alias = unambiguous_alias_map.get((norm_a, jurisdiction))
                if matched_via_alias is not None:
                    exact = matched_via_alias
                    break

        snapshot = record_snapshot(record)
        desired_hash = snapshot_hash(snapshot)

        if exact is not None:
            current_hash = snapshot_hash(scheme_snapshot(exact))
            if current_hash == desired_hash:
                if verify_curated and (
                    exact.verification_status != record.verification_status
                    or exact.is_active != record.is_active
                    or exact.verified_at != record.verified_at
                ):
                    summary.updated += 1
                    bucket["updated"] += 1
                    bucket["details"].append({"scheme": record.name, "result": "verified_curated_updated", "scheme_id": exact.id})
                    if apply:
                        exact.verification_status = record.verification_status
                        exact.verified_at = record.verified_at
                        exact.is_active = record.is_active
                        exact.eligibility_verification_status = record.eligibility_verification_status
                    continue
                summary.unchanged += 1
                bucket["unchanged"] += 1
                bucket["details"].append({"scheme": record.name, "result": "unchanged", "scheme_id": exact.id})
                continue

            already_pending = db.scalar(select(SchemeVersion.id).where(
                SchemeVersion.scheme_id == exact.id,
                SchemeVersion.content_hash == desired_hash,
            ))
            if already_pending:
                if verify_curated:
                    if apply:
                        exact.verification_status = record.verification_status
                        exact.verified_at = record.verified_at
                        exact.is_active = record.is_active
                        exact.eligibility_verification_status = record.eligibility_verification_status
                        scheme_data, rules = record.validated_models()
                        for k, val in scheme_data.model_dump().items():
                            setattr(exact, k, val)
                        existing_version = db.get(SchemeVersion, already_pending)
                        if existing_version and existing_version.verification_status != record.verification_status:
                            existing_version.verification_status = record.verification_status
                            existing_version.verified_at = record.verified_at
                    summary.updated += 1
                    bucket["updated"] += 1
                    bucket["details"].append({"scheme": record.name, "result": "verified_curated_updated", "scheme_id": exact.id})
                    continue
                summary.unchanged += 1
                bucket["unchanged"] += 1
                bucket["details"].append({"scheme": record.name, "result": "pending_version_already_exists", "scheme_id": exact.id})
                continue

            summary.updated += 1
            bucket["updated"] += 1
            bucket["details"].append({"scheme": record.name, "result": "version_pending", "scheme_id": exact.id})
            if apply:
                source = get_or_create_source(db, record)
                v_status = record.verification_status if verify_curated else "pending"
                _add_version(
                    db,
                    exact,
                    record,
                    snapshot,
                    source,
                    "Curated verified update." if verify_curated else "Source data changed; existing scheme was left unchanged pending review.",
                    verification_status=v_status,
                )
            continue

        # New Scheme Insertion
        summary.added += 1
        bucket["added"] += 1
        bucket["details"].append({"scheme": record.name, "result": "verified_new_scheme" if verify_curated else "pending_new_scheme"})
        if apply:
            source = get_or_create_source(db, record)
            scheme_data, rules = record.validated_models()
            fields = scheme_data.model_dump(exclude_unset=False)

            # Resolve deterministic slug collision
            existing_slugs = used_slugs_by_juris.setdefault(jurisdiction, set())
            assigned_slug = resolve_slug_collision(
                candidate_slug,
                existing_slugs,
                name=record.name,
                source_url=record.source_url,
                jurisdiction=jurisdiction,
                ministry=record.ministry,
            )
            existing_slugs.add(assigned_slug)

            fields["slug"] = assigned_slug
            fields["aliases"] = list(getattr(record, "aliases", []))
            fields["canonical_scheme_id"] = None

            if verify_curated:
                fields["verification_status"] = record.verification_status
                fields["verified_at"] = record.verified_at
                fields["is_active"] = record.is_active
                fields["eligibility_verification_status"] = record.eligibility_verification_status
            else:
                fields["verification_status"] = "pending"
                fields["verified_at"] = None
                fields["eligibility_verification_status"] = "unverified"

            scheme = Scheme(**fields)
            scheme.source_id = source.id
            db.add(scheme)
            db.flush()

            created_rules = []
            for rule in rules:
                rule_is_active = (record.verification_status == "verified") if verify_curated else False
                db_rule = EligibilityRule(scheme_id=scheme.id, is_active=rule_is_active, **rule.model_dump())
                db.add(db_rule)
                created_rules.append(db_rule)
            db.flush()

            version_status = record.verification_status if verify_curated else "pending"
            version_summary = ("Imported from verified curated dataset." if verify_curated else "New source-backed scheme awaiting verification review.")
            version = _add_version(db, scheme, record, snapshot, source, version_summary, verification_status=version_status)
            for db_rule in created_rules:
                db_rule.source_version_id = version.id

            by_slug_juris[(assigned_slug, jurisdiction)] = scheme
            by_name_juris[(name_key, jurisdiction)] = scheme

    for counts in per_source.values():
        summary.details.extend(counts["details"])

    if apply:
        # Persist source-level run records only after classification is complete.
        for (source_name, source_url), counts in per_source.items():
            record = next(item for item in items if item.source_name == source_name and item.source_url == source_url)
            source = get_or_create_source(db, record)
            db.add(SchemeImportHistory(
                source_id=source.id,
                source_name=source_name,
                source_url=source_url,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                status="success" if counts["failed"] == 0 else "partial",
                discovered=counts["discovered"],
                added=counts["added"],
                updated=counts["updated"],
                unchanged=counts["unchanged"],
                skipped=counts["skipped"],
                failed=counts["failed"],
                details={"records": counts["details"]},
            ))
        db.flush()
    return summary


def sync_all_sources(db: Session, *, apply: bool = True, commit: bool = True, verify_curated: bool = False) -> SyncSummary:
    """Fetch and synchronize records across all active sources.
    
    Uses registered source adapters or the official curated starter dataset.
    """
    from app.services.source_adapters import LocalCuratedSourceAdapter, get_adapter_for_source

    active_sources = list(db.scalars(select(SchemeSource).where(SchemeSource.is_active.is_(True))))
    records_to_sync = []

    # 1. Official curated starter dataset
    local_adapter = LocalCuratedSourceAdapter()
    for item in local_adapter.fetch_records():
        try:
            from scripts.seed_schemes import DatasetScheme
            records_to_sync.append(DatasetScheme.model_validate(item))
        except Exception:
            pass

    # 2. Configured official API sources
    for source in active_sources:
        if source.api_url and source.source_type == "official_api":
            try:
                adapter = get_adapter_for_source(source)
                for item in adapter.fetch_records():
                    try:
                        from scripts.seed_schemes import DatasetScheme
                        records_to_sync.append(DatasetScheme.model_validate(item))
                    except Exception:
                        pass
                source.last_checked = datetime.now(timezone.utc)
                source.status = "healthy"
            except Exception as exc:
                source.last_checked = datetime.now(timezone.utc)
                source.status = "error"
                source.error_details = str(exc)

    result = sync_records(db, records_to_sync, apply=apply, verify_curated=verify_curated)
    if apply:
        now = datetime.now(timezone.utc)
        for source in active_sources:
            source.last_checked = now
            if source.status != "error":
                source.last_successful_sync = now
        db.flush()
        if commit:
            db.commit()
    return result


def run_sync_with_advisory_lock(
    session: Session | None = None,
    *,
    apply: bool = True,
    verify_curated: bool = False,
) -> SyncSummary:
    """Execute scheme synchronization under a distributed PostgreSQL transaction lock.
    
    Guarantees:
    1. Lock acquisition, all entity writes, and commit share the same Session and Connection.
    2. Subroutines are forbidden from calling session.commit().
    3. Non-blocking: returns status='skipped' immediately if another worker holds the lock.
    4. Crash-safe: lock automatically releases on COMMIT, ROLLBACK, or client crash.
    """
    if session is not None:
        # Caller provided session: acquire advisory xact lock within active connection if on PostgreSQL
        dialect_name = session.bind.dialect.name if session.bind else ""
        if dialect_name == "postgresql":
            acquired = session.execute(
                text("SELECT pg_try_advisory_xact_lock(:lock_id)"),
                {"lock_id": SYNC_ADVISORY_LOCK_ID}
            ).scalar()
            if not acquired:
                logger.info("Scheme ingestion skipped: advisory lock %s held by another worker.", SYNC_ADVISORY_LOCK_ID)
                return SyncSummary(
                    skipped=1,
                    details=[{"status": "skipped", "reason": "Distributed ingestion lock held by another worker process"}]
                )
        return sync_all_sources(session, apply=apply, commit=False, verify_curated=verify_curated)

    # Standalone invocation: manage full session and transaction lifecycle
    with SessionLocal() as db:
        dialect_name = db.bind.dialect.name if db.bind else ""
        with db.begin():
            if dialect_name == "postgresql":
                acquired = db.execute(
                    text("SELECT pg_try_advisory_xact_lock(:lock_id)"),
                    {"lock_id": SYNC_ADVISORY_LOCK_ID}
                ).scalar()

                if not acquired:
                    logger.info("Scheme ingestion skipped: advisory lock %s held by another worker.", SYNC_ADVISORY_LOCK_ID)
                    return SyncSummary(
                        skipped=1,
                        details=[{"status": "skipped", "reason": "Distributed ingestion lock held by another worker process"}]
                    )

                logger.info("Acquired distributed ingestion advisory lock %s.", SYNC_ADVISORY_LOCK_ID)
            summary = sync_all_sources(db, apply=apply, commit=False, verify_curated=verify_curated)
            return summary
