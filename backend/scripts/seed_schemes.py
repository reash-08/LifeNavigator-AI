"""Validate and safely seed the curated scheme dataset.

Run from the repository root with ``python backend/scripts/seed_schemes.py``
to validate and preview. Add ``--apply`` to write missing schemes.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.database.connection import SessionLocal  # noqa: E402
from app.models.eligibility_rule import EligibilityRule  # noqa: E402
from app.models.scheme import Scheme  # noqa: E402
from app.schemas.eligibility_rule import EligibilityRuleCreate  # noqa: E402
from app.schemas.scheme import SchemeCreate  # noqa: E402
from app.models.scheme_source import SchemeImportHistory, SchemeSource  # noqa: E402
from app.services.scheme_sync import is_official_source_url, sync_records  # noqa: E402

DATASET_PATH = REPOSITORY_DIR / "data" / "schemes" / "starter.json"


class DatasetScheme(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=255)
    description: str = Field(min_length=1)
    benefit: str = Field(min_length=1)
    state: str | None = Field(default=None, max_length=100)
    category: str = Field(min_length=1, max_length=100)
    subcategory: str | None = Field(default=None, max_length=100)
    government_level: str
    ministry: str | None = Field(default=None, max_length=200)
    department: str | None = Field(default=None, max_length=200)
    beneficiary_groups: list[str] = Field(min_length=1)
    min_age: int | None = Field(default=None, ge=0, le=120)
    max_age: int | None = Field(default=None, ge=0, le=120)
    education: str | None = Field(default=None, max_length=100)
    employment_status: str | None = Field(default=None, max_length=100)
    max_annual_income: int | None = Field(default=None, ge=0)
    required_documents: str | None = None
    application_process: str | None = None
    application_deadline: date | None = None
    source_name: str = Field(min_length=1, max_length=200)
    source_url: str = Field(min_length=1, max_length=500)
    api_url: str | None = Field(default=None, max_length=1000)
    source_type: str = "official_portal"
    aliases: list[str] = Field(default_factory=list)
    verification_status: str = "pending"
    eligibility_verification_status: str = "unverified"
    verified_at: date | None = None
    effective_from: date | None = None
    effective_until: date | None = None
    application_url: str | None = Field(default=None, max_length=500)
    is_active: bool = True
    eligibility_rules: list[dict] = Field(default_factory=list)

    def validated_models(self) -> tuple[SchemeCreate, list[EligibilityRuleCreate]]:
        scheme_fields = set(SchemeCreate.model_fields)
        scheme_data = self.model_dump(exclude={"eligibility_rules"})
        scheme = SchemeCreate.model_validate({k: v for k, v in scheme_data.items() if k in scheme_fields})
        rule_fields = set(EligibilityRuleCreate.model_fields)
        for item in self.eligibility_rules:
            unknown = set(item) - rule_fields
            if unknown:
                raise ValueError(f"unsupported eligibility rule fields: {sorted(unknown)}")
        rules = [EligibilityRuleCreate.model_validate(item) for item in self.eligibility_rules]
        if not is_official_source_url(self.source_url):
            raise ValueError("source_url must be an HTTPS official government or approved source host")
        if self.verification_status not in {"pending", "verified", "rejected", "expired"}:
            raise ValueError("unsupported verification_status")
        if self.source_type not in {"official_portal", "official_api", "open_data", "manual_curated"}:
            raise ValueError("unsupported source_type")
        if self.eligibility_verification_status not in {"unverified", "verified", "not_confirmed"}:
            raise ValueError("unsupported eligibility_verification_status")
        if self.verification_status == "verified" and self.verified_at is None:
            raise ValueError("verified schemes require verified_at")
        if self.eligibility_verification_status == "verified":
            if self.verification_status != "verified" or not self.eligibility_rules:
                raise ValueError("verified eligibility requires a verified scheme and explicit rules")
        if self.effective_from and self.effective_until and self.effective_until < self.effective_from:
            raise ValueError("effective_until cannot precede effective_from")
        if self.application_url:
            application = urlparse(self.application_url)
            if application.scheme != "https" or not application.netloc:
                raise ValueError("application_url must be an absolute HTTPS URL")
        return scheme, rules


class SchemeDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = Field(ge=1)
    dataset_id: str = Field(min_length=1)
    updated_at: date
    schemes: list[DatasetScheme] = Field(min_length=1)


def normalized_name(name: str) -> str:
    return " ".join(name.casefold().split())


def load_dataset(path: Path = DATASET_PATH) -> SchemeDataset:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read valid JSON dataset at {path}: {exc}") from exc
    dataset = SchemeDataset.model_validate(payload)
    for record in dataset.schemes:
        record.validated_models()
    return dataset


def import_records(db: Session, records: Iterable[DatasetScheme], *, verify_curated: bool = False) -> tuple[int, int]:
    """Compatibility wrapper for callers that need an insert/skip pair."""
    summary = sync_records(db, records, apply=True, verify_curated=verify_curated)
    return summary.added, summary.skipped + summary.unchanged + summary.updated


def _write_validation_failure(message: str, dataset_path: Path) -> None:
    """Best-effort audit row for invalid input, without masking validation errors."""
    try:
        with SessionLocal() as db:
            now = datetime.now(timezone.utc)
            db.add(SchemeImportHistory(
                source_name="Local curated dataset",
                source_url=dataset_path.as_uri() if dataset_path.is_absolute() else str(dataset_path),
                started_at=now,
                completed_at=now,
                status="failed",
                discovered=0,
                failed=1,
                details={"error": message},
            ))
            db.commit()
    except Exception:
        pass


def ingest_scheme_docs(db: Session, schemes: Iterable[DatasetScheme]) -> int:
    """Ingest official summary documents and compute embeddings for verified schemes."""
    from app.services.document_ingestion import ingest_document

    ingested_count = 0
    all_db_schemes = {s.name: s for s in db.query(Scheme).all()}
    for record in schemes:
        db_scheme = all_db_schemes.get(record.name)
        if not db_scheme:
            continue
        text_parts = [
            f"# {record.name}",
            f"Ministry / Department: {record.ministry or ''} - {record.department or ''}",
            f"Government Level: {record.government_level} | State: {record.state or 'All India'}",
            f"Category: {record.category}" + (f" ({record.subcategory})" if record.subcategory else ""),
            f"\n## Overview\n{record.description}",
            f"\n## Benefits\n{record.benefit}",
            "\n## Eligibility Criteria",
            f"- Beneficiary Groups: {', '.join(record.beneficiary_groups)}",
        ]
        if record.min_age is not None or record.max_age is not None:
            text_parts.append(f"- Age: {record.min_age or 'Any'} to {record.max_age or 'Any'} years")
        if record.max_annual_income is not None:
            text_parts.append(f"- Maximum Annual Family Income: Rs {record.max_annual_income:,}")
        if record.education:
            text_parts.append(f"- Education Requirement: {record.education}")
        if record.employment_status:
            text_parts.append(f"- Employment Status: {record.employment_status}")
        if record.required_documents:
            text_parts.append(f"\n## Required Documents\n{record.required_documents}")
        if record.application_process:
            text_parts.append(f"\n## How to Apply\n{record.application_process}")
        if record.application_url:
            text_parts.append(f"\nApplication URL: {record.application_url}")
        text_parts.append(f"Official Source Portal: {record.source_url} ({record.source_name})")

        full_text = "\n".join(text_parts)
        try:
            doc, created = ingest_document(
                db,
                scheme_id=db_scheme.id,
                source_name=record.source_name,
                source_url=record.source_url,
                title=f"{record.name} - Official Summary & Guidelines",
                text=full_text,
            )
            if created:
                ingested_count += 1
        except Exception as exc:
            print(f"Warning: could not ingest document for {record.name}: {exc}", file=sys.stderr)
    return ingested_count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--apply", action="store_true", help="write new schemes, versions and import history")
    parser.add_argument("--verify-curated", action="store_true", help="import curated records with their verified status instead of defaulting to pending")
    parser.add_argument("--ingest-docs", action="store_true", help="ingest official scheme documents and compute embeddings for RAG")
    args = parser.parse_args()
    try:
        dataset = load_dataset(args.dataset)
    except (ValidationError, ValueError) as exc:
        if args.apply:
            _write_validation_failure(str(exc), args.dataset)
        print(f"Dataset validation failed: {exc}", file=sys.stderr)
        return 2
    try:
        with SessionLocal() as db:
            summary = sync_records(db, dataset.schemes, apply=args.apply, verify_curated=args.verify_curated)
            doc_count = 0
            if args.apply and args.ingest_docs:
                doc_count = ingest_scheme_docs(db, dataset.schemes)
            if args.apply:
                db.commit()
            else:
                db.rollback()
    except Exception as exc:
        if args.apply:
            _write_validation_failure(f"Import failed: {exc}", args.dataset)
        print(f"Import failed; transaction rolled back: {exc}", file=sys.stderr)
        return 1
    mode = "Applied" if args.apply else "Preview"
    print(
        f"{mode} {dataset.dataset_id}: discovered={summary.discovered}, added={summary.added}, "
        f"pending_changes={summary.updated}, unchanged={summary.unchanged}, "
        f"duplicates_skipped={summary.skipped}, failed={summary.failed}."
    )
    if args.ingest_docs and args.apply:
        print(f"RAG Document Ingestion: newly ingested {doc_count} scheme documents with vector embeddings.")
    for detail in summary.details:
        print(f"  {detail.get('result')}: {detail.get('scheme')}")
    if not args.apply:
        print("Preview only; database was not changed. New schemes will be pending review if applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
