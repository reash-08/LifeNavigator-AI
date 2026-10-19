import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.services.embedding import get_embedding_provider
from app.database.connection import SessionLocal
from app.models.scheme_document import SchemeDocumentChunk, SchemeDocument
from app.services.document_ingestion import retrieve_document_chunks
from sqlalchemy import func

print("=================================================================")
print("=== RAG PIPELINE & EMBEDDINGS VERIFICATION ===")
print("=================================================================")

# 1. Configured Embedding Provider and Dimensionality
provider = get_embedding_provider()
EMBEDDING_DIMENSION = provider.dimension
print(f"1. Embedding Provider configured: '{settings.EMBEDDING_PROVIDER}'")
print(f"   Provider instance: {provider.__class__.__name__}")
print(f"   Expected dimension constant: {EMBEDDING_DIMENSION}")

test_vec = provider.embed_text("test query for farmer welfare")
print(f"   Test vector generated: length={len(test_vec)}, dtype={type(test_vec[0])}")
assert len(test_vec) == EMBEDDING_DIMENSION, f"Expected {EMBEDDING_DIMENSION}, got {len(test_vec)}"

# 2. Stored Vectors in PostgreSQL
with SessionLocal() as db:
    total_chunks = db.query(func.count(SchemeDocumentChunk.id)).scalar()
    chunks_with_embeddings = db.query(SchemeDocumentChunk).filter(SchemeDocumentChunk.embedding != None).all()
    print(f"\n2. Stored Document Chunks in DB: {total_chunks}")
    print(f"   Chunks with embeddings: {len(chunks_with_embeddings)}")
    assert len(chunks_with_embeddings) == total_chunks, "Some chunks are missing embeddings!"
    
    # Check dimensions of all chunks
    mismatched_dims = []
    for chunk in chunks_with_embeddings:
        dim = len(chunk.embedding)
        if dim != EMBEDDING_DIMENSION:
            mismatched_dims.append((chunk.id, dim))
    
    print(f"   Chunks with mismatched dimensions: {len(mismatched_dims)}")
    assert len(mismatched_dims) == 0, f"Found mismatched dimensions: {mismatched_dims}"
    print(f"   All {total_chunks} chunks verified to have exact {EMBEDDING_DIMENSION}-dimensional embeddings.")

    # 3. Document Ingestion & Chunk Retrieval
    query = "solar pump grant for farmers"
    retrieved = retrieve_document_chunks(db, query, limit=5)
    print(f"\n3. Chunk Retrieval for query '{query}':")
    print(f"   Retrieved {len(retrieved)} chunks")
    for chunk, doc, sim_score in retrieved:
        print(f"   - Chunk ID {chunk.id} (Doc: {doc.title or doc.source_name}): similarity score = {sim_score:.4f}")
        print(f"     Excerpt: {chunk.text[:80]}...")
        assert sim_score >= 0.0
        assert doc.source_url.startswith("http")

print("\n=================================================================")
print(">>> RAG PIPELINE & EMBEDDING CHECKS PASSED CLEANLY! <<<")
print("=================================================================")
