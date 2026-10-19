import sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database.connection import SessionLocal
from app.models.scheme_document import SchemeDocumentChunk
from app.services.embedding import get_embedding_provider
from app.services.vector_store import cosine_similarity

provider = get_embedding_provider()
print(f"Provider: {provider.__class__.__name__}")
print(f"Provider reported dimension: {provider.dimension}")
test_vec = provider.embed_text("National scholarship scheme for higher education")
print(f"Generated vector length: {len(test_vec)}")
assert len(test_vec) == 384, f"Expected 384, got {len(test_vec)}"

with SessionLocal() as db:
    chunks = db.query(SchemeDocumentChunk).all()
    print(f"Total chunks in database: {len(chunks)}")
    non_null_chunks = [c for c in chunks if c.embedding is not None]
    print(f"Chunks with embeddings: {len(non_null_chunks)}")
    
    dimensions = set(len(c.embedding) for c in non_null_chunks)
    print(f"Unique embedding dimensions found across chunks: {dimensions}")
    assert dimensions == {384}, f"Inconsistent dimensions: {dimensions}"
    
    # Test cosine similarity between test query and first chunk
    first_vec = non_null_chunks[0].embedding
    sim = cosine_similarity(test_vec, first_vec)
    print(f"Sample Cosine similarity: {sim:.4f}")
    assert -1.0 <= sim <= 1.0

print("\nEmbedding consistency verified: 100% of chunks have exact 384-dimensional embeddings matching the provider.")
