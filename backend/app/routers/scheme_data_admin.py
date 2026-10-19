from datetime import date, datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.security import get_current_admin
from app.database.connection import get_db
from app.models.eligibility_rule import EligibilityRule
from app.models.scheme import Scheme
from app.models.scheme_source import SchemeImportHistory, SchemeSource, SchemeVersion
from app.models.scheme_document import SchemeDocument, SchemeDocumentChunk
from app.models.user import User
from app.schemas.eligibility_rule import EligibilityRuleCreate
from app.schemas.scheme import SchemeCreate
from app.schemas.scheme_version import SchemeVersionReview
from app.services.embedding import get_embedding_provider
from app.services.scheduler import get_scheduler_status, trigger_sync_now
from app.services.scheme_sync import is_official_source_url


router = APIRouter(prefix="/api/admin/scheme-data", tags=["Scheme Data Administration"])


class DocumentIngestRequest(BaseModel):
    scheme_id: int = Field(gt=0)
    source_name: str = Field(min_length=1, max_length=200)
    source_url: str = Field(min_length=1, max_length=1000)
    title: str | None = Field(default=None, max_length=500)
    content: str = Field(min_length=1, max_length=2_000_000)


class SourceCreateRequest(BaseModel):
    source_name: str = Field(min_length=1, max_length=200)
    source_url: str = Field(min_length=1, max_length=1000)
    api_url: str | None = Field(default=None, max_length=1000)
    provider: str | None = Field(default=None, max_length=300)
    source_type: str = Field(default="official_portal", max_length=40)
    sync_interval_hours: int = Field(default=24, ge=1, le=168)
    notes: str | None = None


class SourceUpdateRequest(BaseModel):
    is_active: bool | None = None
    sync_interval_hours: int | None = Field(default=None, ge=1, le=168)
    notes: str | None = None


class TestRetrievalRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    scheme_id: int | None = None
    limit: int = Field(default=5, ge=1, le=20)


def _version_payload(row: SchemeVersion):
    return {
        "id": row.id, "scheme_id": row.scheme_id, "scheme_name": row.scheme.name,
        "version_number": row.version_number, "snapshot": row.snapshot,
        "source_id": row.source_id, "source_name": row.source.source_name if row.source else None,
        "source_url": row.source_url, "verification_status": row.verification_status,
        "eligibility_verification_status": row.eligibility_verification_status,
        "verified_at": row.verified_at, "effective_from": row.effective_from,
        "effective_until": row.effective_until, "imported_at": row.imported_at,
        "change_summary": row.change_summary,
    }


# ==================== DOCUMENTS & RAG ====================

@router.get("/documents")
def list_documents(
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(SchemeDocument).options(selectinload(SchemeDocument.chunks))
        .order_by(SchemeDocument.ingested_at.desc(), SchemeDocument.id.desc())
    ).all()
    return [
        {
            "id": row.id,
            "scheme_id": row.scheme_id,
            "title": row.title,
            "source_name": row.source_name,
            "source_url": row.source_url,
            "content_sha256": row.content_sha256,
            "ingested_at": row.ingested_at,
            "chunk_count": len(row.chunks),
            "embedded_count": sum(1 for c in row.chunks if c.embedding is not None),
            "ingestion_status": row.ingestion_status,
            "document_type": row.document_type,
            "version": row.version,
            "error_message": row.error_message,
        }
        for row in rows
    ]


@router.post("/documents", status_code=status.HTTP_201_CREATED)
def add_document(
    payload: DocumentIngestRequest,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    from app.services.document_ingestion import ingest_document

    try:
        scheme = db.get(Scheme, payload.scheme_id)
        source = db.get(SchemeSource, scheme.source_id) if scheme and scheme.source_id else None
        if (
            source is None
            or not source.is_active
            or source.source_name != payload.source_name.strip()
            or source.source_url != payload.source_url.strip()
            or scheme.source_name != source.source_name
            or scheme.source_url != source.source_url
        ):
            raise ValueError("Use the scheme's matching active registered source")
        document, created = ingest_document(
            db, scheme_id=payload.scheme_id, source_name=payload.source_name,
            source_url=payload.source_url, title=payload.title, text=payload.content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "id": document.id,
        "scheme_id": document.scheme_id,
        "title": document.title,
        "source_name": document.source_name,
        "source_url": document.source_url,
        "chunk_count": len(document.chunks),
        "embedded_count": sum(1 for c in document.chunks if c.embedding is not None),
        "created": created,
    }


@router.post("/documents/{document_id}/reindex")
def reindex_document_endpoint(
    document_id: int,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    from app.services.document_ingestion import reindex_document

    try:
        doc = reindex_document(db, document_id)
        return {
            "id": doc.id,
            "version": doc.version,
            "chunk_count": len(doc.chunks),
            "status": doc.ingestion_status,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    doc = db.get(SchemeDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(doc)
    db.commit()
    return None


# ==================== SOURCE REGISTRY & SYNCHRONIZATION ====================

@router.get("/sources")
def list_sources(
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    sources = db.scalars(select(SchemeSource).order_by(SchemeSource.source_name)).all()
    return [
        {
            "id": s.id,
            "source_name": s.source_name,
            "source_url": s.source_url,
            "api_url": s.api_url,
            "provider": s.provider,
            "source_type": s.source_type,
            "is_active": s.is_active,
            "sync_interval_hours": s.sync_interval_hours,
            "status": s.status,
            "last_checked": s.last_checked,
            "last_successful_sync": s.last_successful_sync,
            "notes": s.notes,
            "created_at": s.created_at,
        }
        for s in sources
    ]


@router.post("/sources", status_code=status.HTTP_201_CREATED)
def register_source(
    payload: SourceCreateRequest,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if not is_official_source_url(payload.source_url):
        raise HTTPException(status_code=422, detail="Source URL must be an official government HTTPS domain")
    if payload.api_url and not is_official_source_url(payload.api_url):
        raise HTTPException(status_code=422, detail="API URL must be an official government HTTPS domain")

    existing = db.scalar(
        select(SchemeSource).where(
            SchemeSource.source_name == payload.source_name.strip(),
            SchemeSource.source_url == payload.source_url.strip(),
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="A source with this name and URL already exists")

    source = SchemeSource(
        source_name=payload.source_name.strip(),
        source_url=payload.source_url.strip(),
        api_url=payload.api_url.strip() if payload.api_url else None,
        provider=payload.provider.strip() if payload.provider else None,
        source_type=payload.source_type,
        sync_interval_hours=payload.sync_interval_hours,
        status="healthy",
        notes=payload.notes,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return {
        "id": source.id,
        "source_name": source.source_name,
        "source_url": source.source_url,
        "is_active": source.is_active,
    }


@router.put("/sources/{source_id}")
def update_source(
    source_id: int,
    payload: SourceUpdateRequest,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    source = db.get(SchemeSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    if payload.is_active is not None:
        source.is_active = payload.is_active
    if payload.sync_interval_hours is not None:
        source.sync_interval_hours = payload.sync_interval_hours
    if payload.notes is not None:
        source.notes = payload.notes

    db.commit()
    db.refresh(source)
    return {
        "id": source.id,
        "source_name": source.source_name,
        "is_active": source.is_active,
        "sync_interval_hours": source.sync_interval_hours,
    }


@router.post("/sync-now")
def sync_now(
    _: User = Depends(get_current_admin),
):
    """Trigger manual on-demand synchronization using the central worker pipeline."""
    result = trigger_sync_now()
    return result


@router.get("/sync-status")
def sync_status(
    _: User = Depends(get_current_admin),
):
    """Return operational scheduler and synchronization health."""
    return get_scheduler_status()


# ==================== RAG OBSERVABILITY & DIAGNOSTICS ====================

@router.get("/diagnostics")
def rag_diagnostics(
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    total_schemes = db.scalar(select(func.count(Scheme.id))) or 0
    total_docs = db.scalar(select(func.count(SchemeDocument.id))) or 0
    total_chunks = db.scalar(select(func.count(SchemeDocumentChunk.id))) or 0
    embedded_chunks = db.scalar(
        select(func.count(SchemeDocumentChunk.id)).where(SchemeDocumentChunk.embedding.isnot(None))
    ) or 0
    total_sources = db.scalar(select(func.count(SchemeSource.id))) or 0
    healthy_sources = db.scalar(
        select(func.count(SchemeSource.id)).where(SchemeSource.status == "healthy")
    ) or 0

    latest_doc = db.scalar(select(SchemeDocument.ingested_at).order_by(SchemeDocument.ingested_at.desc()).limit(1))
    provider = get_embedding_provider()

    return {
        "total_schemes": total_schemes,
        "total_documents": total_docs,
        "total_chunks": total_chunks,
        "embedded_chunks": embedded_chunks,
        "total_sources": total_sources,
        "healthy_sources": healthy_sources,
        "embedding_provider": provider.__class__.__name__,
        "embedding_dimensions": provider.dimension,
        "last_document_ingested_at": latest_doc.isoformat() if latest_doc else None,
        "scheduler": get_scheduler_status(),
    }


@router.post("/test-retrieval")
def test_retrieval(
    payload: TestRetrievalRequest,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Admin diagnostic test tool: evaluates hybrid retrieval and displays chunk evidence."""
    from app.services.document_ingestion import retrieve_document_chunks

    chunks = retrieve_document_chunks(
        db, payload.query, scheme_id=payload.scheme_id, limit=payload.limit
    )
    return {
        "query": payload.query,
        "match_count": len(chunks),
        "results": [
            {
                "chunk_id": chunk.id,
                "document_id": document.id,
                "scheme_id": document.scheme_id,
                "document_title": document.title or document.source_name,
                "source_name": document.source_name,
                "source_url": document.source_url,
                "score": score,
                "excerpt": chunk.text[:300] + ("…" if len(chunk.text) > 300 else ""),
            }
            for chunk, document, score in chunks
        ],
    }


# ==================== IMPORTS & REVIEWS ====================

@router.get("/imports")
def list_import_history(
    limit: int = 50,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if not 1 <= limit <= 200:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 200")
    rows = db.scalars(select(SchemeImportHistory).order_by(SchemeImportHistory.started_at.desc()).limit(limit)).all()
    return [
        {
            "id": row.id,
            "source_id": row.source_id,
            "source_name": row.source_name,
            "source_url": row.source_url,
            "started_at": row.started_at,
            "completed_at": row.completed_at,
            "status": row.status,
            "discovered": row.discovered,
            "added": row.added,
            "updated": row.updated,
            "unchanged": row.unchanged,
            "skipped": row.skipped,
            "failed": row.failed,
            "details": row.details,
        }
        for row in rows
    ]


@router.get("/versions/pending")
def list_pending_versions(
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(SchemeVersion)
        .options(selectinload(SchemeVersion.scheme), selectinload(SchemeVersion.source))
        .where(SchemeVersion.verification_status == "pending")
        .order_by(SchemeVersion.imported_at, SchemeVersion.id)
    ).all()
    return [_version_payload(row) for row in rows]


@router.get("/versions")
def list_scheme_versions(
    verification_status: str = "verified",
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if verification_status not in {"pending", "verified", "rejected", "expired"}:
        raise HTTPException(status_code=422, detail="Unsupported version status")
    rows = db.scalars(
        select(SchemeVersion)
        .options(selectinload(SchemeVersion.scheme), selectinload(SchemeVersion.source))
        .where(SchemeVersion.verification_status == verification_status)
        .order_by(SchemeVersion.imported_at.desc(), SchemeVersion.id.desc())
    ).all()
    return [_version_payload(row) for row in rows]


@router.post("/versions/{version_id}/review")
def review_scheme_version(
    version_id: int,
    review: SchemeVersionReview,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    version = db.scalar(
        select(SchemeVersion)
        .options(
            selectinload(SchemeVersion.scheme).selectinload(Scheme.eligibility_rules),
            selectinload(SchemeVersion.scheme).selectinload(Scheme.versions),
            selectinload(SchemeVersion.source),
        )
        .where(SchemeVersion.id == version_id)
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Scheme version not found")
    if version.verification_status != "pending" and not (
        review.decision == "expired" and version.verification_status == "verified"
    ):
        raise HTTPException(status_code=409, detail="Only pending scheme versions can be reviewed")

    if review.decision in {"rejected", "expired"}:
        version.verification_status = review.decision
        version.reviewed_at = datetime.now(timezone.utc)
        version.reviewed_by_user_id = admin.id
        version.review_notes = review.notes
        scheme = version.scheme
        if version.version_number == 1 and scheme.verification_status == "pending":
            scheme.verification_status = review.decision
        elif review.decision == "expired" and scheme.verification_status == "verified":
            latest_verified = max(
                (item.version_number for item in scheme.versions if item.verification_status == "verified"),
                default=0,
            )
            if version.version_number == latest_verified:
                scheme.verification_status = "expired"
                scheme.is_active = False
        if review.decision == "rejected" and version.version_number == 1:
            scheme.is_active = False
        db.commit()
        return {"id": version.id, "verification_status": version.verification_status}

    source = version.source
    parsed = urlparse(version.source_url or "")
    if source is None or not source.is_active or source.source_url != version.source_url:
        raise HTTPException(status_code=422, detail="A matching active registered source is required before approval")
    if parsed.scheme != "https" or not parsed.netloc:
        raise HTTPException(status_code=422, detail="The version must have an HTTPS source URL")

    snapshot = dict(version.snapshot or {})
    rules_data = snapshot.pop("eligibility_rules", [])
    scheme_fields = set(Scheme.__table__.columns.keys()) - {"id"}
    scheme_data = {key: value for key, value in snapshot.items() if key in scheme_fields}
    scheme_data["verification_status"] = "verified"
    scheme_data["verified_at"] = review.verified_at or date.today()
    scheme_data["eligibility_verification_status"] = review.eligibility_verification_status
    try:
        validated = SchemeCreate.model_validate(scheme_data)
        validated_rules = [EligibilityRuleCreate.model_validate(item) for item in rules_data]
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Version snapshot failed validation: {exc}") from exc
    if review.eligibility_verification_status == "verified" and not validated_rules:
        raise HTTPException(status_code=422, detail="Verified eligibility requires explicit source-backed rules")

    scheme = version.scheme
    scheme.source_id = source.id
    for key, value in validated.model_dump().items():
        setattr(scheme, key, value)
    for current_rule in scheme.eligibility_rules:
        current_rule.is_active = False
    for rule in validated_rules:
        db.add(EligibilityRule(
            scheme_id=scheme.id,
            source_version_id=version.id,
            is_active=review.eligibility_verification_status == "verified",
            **rule.model_dump(),
        ))

    version.verification_status = "verified"
    version.eligibility_verification_status = review.eligibility_verification_status
    version.verified_at = review.verified_at or date.today()
    version.effective_from = review.effective_from or version.effective_from
    version.effective_until = review.effective_until or version.effective_until
    version.reviewed_at = datetime.now(timezone.utc)
    version.reviewed_by_user_id = admin.id
    version.review_notes = review.notes
    db.commit()
    return {
        "id": version.id,
        "scheme_id": scheme.id,
        "verification_status": version.verification_status,
        "eligibility_verification_status": version.eligibility_verification_status,
    }
