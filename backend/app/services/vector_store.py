"""Vector store adapter for LifeNavigator-AI document chunks.

Stores embeddings as JSON vector arrays in the relational database (PostgreSQL / SQLite)
and provides cosine similarity search, chunk indexing, and similarity scoring.
"""
from __future__ import annotations

import math
from sqlalchemy.orm import Session

from app.models.scheme_document import SchemeDocument, SchemeDocumentChunk


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = 0.0
    norm1 = 0.0
    norm2 = 0.0
    for a, b in zip(v1, v2):
        dot += a * b
        norm1 += a * a
        norm2 += b * b
    if norm1 <= 0.0 or norm2 <= 0.0:
        return 0.0
    val = dot / (math.sqrt(norm1) * math.sqrt(norm2))
    # Bound to [-1.0, 1.0] to handle float precision
    return max(-1.0, min(1.0, val))


def search_similar_chunks(
    db: Session,
    query_vector: list[float],
    *,
    limit: int = 5,
    scheme_id: int | None = None,
    min_score: float = 0.0,
) -> list[tuple[SchemeDocumentChunk, SchemeDocument, float]]:
    """Retrieve document chunks ordered by vector cosine similarity to query_vector."""
    if not query_vector:
        return []

    query = db.query(SchemeDocumentChunk, SchemeDocument).join(SchemeDocument)
    if scheme_id is not None:
        query = query.filter(SchemeDocument.scheme_id == scheme_id)

    # Filter out empty or un-embedded chunks
    rows = query.filter(SchemeDocumentChunk.embedding.isnot(None)).all()
    if not rows:
        return []

    scored: list[tuple[SchemeDocumentChunk, SchemeDocument, float]] = []
    for chunk, document in rows:
        embedding = chunk.embedding
        if not embedding or not isinstance(embedding, list):
            continue
        sim = cosine_similarity(query_vector, embedding)
        # Normalize similarity from [-1, 1] to [0, 1] for unified scoring
        normalized_score = round(max(0.0, (sim + 1.0) / 2.0 if sim < 0.0 else sim), 4)
        if normalized_score >= min_score:
            scored.append((chunk, document, normalized_score))

    scored.sort(key=lambda item: (-item[2], item[1].id, item[0].ordinal))
    return scored[:limit]


def index_chunk_embeddings(
    db: Session,
    chunks: list[SchemeDocumentChunk],
    embeddings: list[list[float]],
) -> int:
    """Attach generated embeddings to chunk records and persist."""
    count = 0
    for chunk, vector in zip(chunks, embeddings):
        chunk.embedding = vector
        count += 1
    db.flush()
    return count
