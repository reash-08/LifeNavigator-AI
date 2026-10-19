"""Local, repeat-safe ingestion and hybrid retrieval for official scheme documents."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.scheme import Scheme
from app.models.scheme_document import SchemeDocument, SchemeDocumentChunk
from app.services.embedding import get_embedding_provider
from app.services.vector_store import search_similar_chunks

_WORD = re.compile(r"[\w]+", re.UNICODE)


@dataclass(frozen=True)
class Chunk:
    ordinal: int
    text: str
    start_char: int
    end_char: int


def chunk_text(text: str, *, chunk_size: int = 1200, overlap: int = 200) -> list[Chunk]:
    if chunk_size < 1 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("chunk_size must be positive and overlap must be in [0, chunk_size)")
    text = re.sub(r"\s+", " ", text).strip()
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start + chunk_size // 2, end)
            if boundary > start:
                end = boundary
        content_start = start
        while content_start < end and text[content_start].isspace():
            content_start += 1
        content_end = end
        while content_end > content_start and text[content_end - 1].isspace():
            content_end -= 1
        content = text[content_start:content_end]
        if content:
            chunks.append(Chunk(len(chunks), content, content_start, content_end))
        if end >= len(text):
            break
        next_start = max(start + 1, end - overlap)
        boundary = text.find(" ", next_start, end)
        start = boundary + 1 if boundary >= 0 else next_start
    return chunks


def extract_text(path: Path) -> str:
    """Extract UTF-8 text or PDF pages. PDF support uses the lightweight local pypdf package."""
    if path.suffix.casefold() == ".pdf":
        from pypdf import PdfReader
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    if path.suffix.casefold() not in {".txt", ".md"}:
        raise ValueError("Only .txt, .md, and text-based .pdf sources are supported")
    return path.read_text(encoding="utf-8")


def ingest_document(
    db: Session,
    *,
    scheme_id: int,
    source_name: str,
    source_url: str,
    text: str,
    title: str | None = None,
    document_type: str = "official_document",
    metadata: dict | None = None,
    chunk_size: int = 1200,
    overlap: int = 200,
) -> tuple[SchemeDocument, bool]:
    if not source_name.strip() or not source_url.strip():
        raise ValueError("source_name and source_url are required for provenance")
    if not re.match(r"^https://", source_url.strip(), re.IGNORECASE):
        raise ValueError("source_url must use HTTPS")
    if not text.strip():
        raise ValueError("document contains no extractable text")
    if db.get(Scheme, scheme_id) is None:
        raise ValueError(f"scheme {scheme_id} does not exist")

    normalized = re.sub(r"\s+", " ", text).strip()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    existing = db.query(SchemeDocument).filter_by(scheme_id=scheme_id, content_sha256=digest).one_or_none()
    if existing:
        # Check if chunks are missing embeddings, backfill if necessary
        missing_embeddings = [c for c in existing.chunks if c.embedding is None]
        if missing_embeddings:
            provider = get_embedding_provider()
            vectors = provider.embed_batch([c.text for c in missing_embeddings])
            for c, vec in zip(missing_embeddings, vectors):
                c.embedding = vec
            db.commit()
        return existing, False

    chunks = chunk_text(normalized, chunk_size=chunk_size, overlap=overlap)
    provider = get_embedding_provider()
    embeddings = provider.embed_batch([item.text for item in chunks])

    doc_metadata = {
        **(metadata or {}),
        "chunk_count": len(chunks),
        "embedding_provider": provider.__class__.__name__,
        "embedding_dim": provider.dimension,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    document = SchemeDocument(
        scheme_id=scheme_id,
        source_name=source_name.strip(),
        source_url=source_url.strip(),
        title=title,
        content_sha256=digest,
        extracted_text=normalized,
        document_type=document_type,
        ingestion_status="completed",
        metadata_json=doc_metadata,
        version=1,
    )
    document.chunks = [
        SchemeDocumentChunk(
            ordinal=item.ordinal,
            text=item.text,
            start_char=item.start_char,
            end_char=item.end_char,
            embedding=embeddings[idx] if idx < len(embeddings) else None,
        )
        for idx, item in enumerate(chunks)
    ]
    db.add(document)
    db.commit()
    db.refresh(document)
    return document, True


def reindex_document(db: Session, document_id: int) -> SchemeDocument:
    """Regenerate chunks and embeddings for an existing document."""
    document = db.get(SchemeDocument, document_id)
    if not document:
        raise ValueError(f"Document {document_id} not found")

    chunks = chunk_text(document.extracted_text)
    provider = get_embedding_provider()
    embeddings = provider.embed_batch([item.text for item in chunks])

    # Delete old chunks explicitly from DB and flush to prevent UNIQUE constraint conflict
    for old_chunk in list(document.chunks):
        db.delete(old_chunk)
    db.flush()

    new_chunks = [
        SchemeDocumentChunk(
            document_id=document.id,
            ordinal=item.ordinal,
            text=item.text,
            start_char=item.start_char,
            end_char=item.end_char,
            embedding=embeddings[idx] if idx < len(embeddings) else None,
        )
        for idx, item in enumerate(chunks)
    ]
    db.add_all(new_chunks)
    document.version += 1
    document.ingestion_status = "completed"
    document.error_message = None
    if document.metadata_json is None:
        document.metadata_json = {}
    document.metadata_json["reindexed_at"] = datetime.now(timezone.utc).isoformat()
    db.commit()
    db.refresh(document)
    return document


def retrieve_document_chunks(
    db: Session,
    query: str,
    *,
    scheme_id: int | None = None,
    limit: int = 5,
    use_vector: bool = True,
) -> list[tuple[SchemeDocumentChunk, SchemeDocument, float]]:
    """Hybrid retrieval: combines semantic vector search and keyword token matching."""
    terms = {token.casefold() for token in _WORD.findall(query) if len(token) > 1}
    if not terms and not query.strip():
        return []

    # 1. Lexical retrieval
    rows = db.query(SchemeDocumentChunk, SchemeDocument).join(SchemeDocument).filter(SchemeDocumentChunk.text != "")
    if scheme_id is not None:
        rows = rows.filter(SchemeDocument.scheme_id == scheme_id)

    lexical_scores: dict[int, tuple[SchemeDocumentChunk, SchemeDocument, float]] = {}
    for chunk, document in rows.all():
        words = {token.casefold() for token in _WORD.findall(chunk.text) if len(token) > 1}
        overlap = terms & words
        if overlap:
            score = len(overlap) / len(terms) if terms else 0.0
            lexical_scores[chunk.id] = (chunk, document, score)

    # 2. Semantic vector retrieval (when use_vector is enabled)
    vector_scores: dict[int, tuple[SchemeDocumentChunk, SchemeDocument, float]] = {}
    if use_vector and query.strip():
        provider = get_embedding_provider()
        query_vector = provider.embed_text(query)
        similar = search_similar_chunks(db, query_vector, limit=limit * 2, scheme_id=scheme_id)
        for chunk, document, v_score in similar:
            vector_scores[chunk.id] = (chunk, document, v_score)

    # 3. Hybrid fusion: combine lexical and vector scores
    all_chunk_ids = set(lexical_scores.keys()) | set(vector_scores.keys())
    combined: list[tuple[SchemeDocumentChunk, SchemeDocument, float]] = []

    for cid in all_chunk_ids:
        chunk = None
        document = None
        l_score = 0.0
        v_score = 0.0

        if cid in lexical_scores:
            chunk, document, l_score = lexical_scores[cid]
        if cid in vector_scores:
            chunk, document, v_score = vector_scores[cid]

        # Hybrid weight: 0.6 vector + 0.4 lexical (or pure single score if only one present)
        if v_score > 0 and l_score > 0:
            final_score = round(0.6 * v_score + 0.4 * l_score, 4)
        elif v_score > 0:
            final_score = round(v_score, 4)
        else:
            final_score = round(l_score, 4)

        if chunk and document:
            combined.append((chunk, document, final_score))

    combined.sort(key=lambda item: (-item[2], item[1].id, item[0].ordinal))
    return combined[:limit]
