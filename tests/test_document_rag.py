from pathlib import Path

import pytest

from app.database.connection import SessionLocal
from app.database.connection import engine
from app.database.base import Base
from app.models.scheme import Scheme
from app.models.scheme_document import SchemeDocument, SchemeDocumentChunk
from app.services.document_ingestion import chunk_text, extract_text, ingest_document, retrieve_document_chunks
from app.services.explanation import GroundedTemplateProvider, answer_from_documents
from app.services.eligibility import check_scheme_eligibility
from app.models.profile import UserProfile


@pytest.fixture(autouse=True)
def isolated_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _scheme_id() -> int:
    with SessionLocal() as db:
        scheme = Scheme(name="Farm solar pump grant", description="Solar pump support.",
                        benefit="Grant assistance under recorded rules.", category="Agriculture", is_active=True,
                        source_name="Ministry fixture", source_url="https://ministry.example/scheme",
                        verification_status="verified")
        db.add(scheme)
        db.commit()
        return scheme.id


def test_chunking_obeys_size_overlap_and_invalid_configuration():
    source = " ".join(f"word{i}" for i in range(100))
    chunks = chunk_text(source, chunk_size=100, overlap=20)
    assert len(chunks) > 1
    assert all(len(chunk.text) <= 100 for chunk in chunks)
    normalized = " ".join(source.split())
    assert all(normalized[chunk.start_char:chunk.end_char] == chunk.text for chunk in chunks)
    assert chunks[0].text[-10:] in chunks[1].text
    assert chunks[0].ordinal == 0 and chunks[-1].end_char <= len(source)
    with pytest.raises(ValueError):
        chunk_text(source, chunk_size=10, overlap=10)


def test_text_ingestion_is_provenanced_and_idempotent():
    scheme_id = _scheme_id()
    content = "Applicants in Karnataka may apply for solar irrigation pumps. The grant covers pump installation."
    with SessionLocal() as db:
        doc, created = ingest_document(db, scheme_id=scheme_id, source_name="Agriculture Ministry",
            source_url="https://agri.example/guideline", title="Pump guidance", text=content, chunk_size=50, overlap=10)
        doc_id = doc.id
        same, created_again = ingest_document(db, scheme_id=scheme_id, source_name="Agriculture Ministry",
            source_url="https://agri.example/guideline", title="Pump guidance", text=f"  {content}  ", chunk_size=50, overlap=10)
        assert created and not created_again and same.id == doc_id
        assert same.chunks and [c.ordinal for c in same.chunks] == list(range(len(same.chunks)))
        assert same.source_url == "https://agri.example/guideline"


@pytest.mark.parametrize("source_url,content", [("http://bad.example", "text"), ("https://ok.example", " ")])
def test_ingestion_rejects_missing_or_unsafe_provenance(source_url, content):
    with SessionLocal() as db:
        scheme = Scheme(name="Test", description="Test", benefit="Test")
        db.add(scheme)
        db.commit()
        with pytest.raises(ValueError):
            ingest_document(db, scheme_id=scheme.id, source_name="Source", source_url=source_url, text=content)


def test_retrieval_ranks_chunks_and_can_scope_by_scheme():
    first_id, second_id = _scheme_id(), _scheme_id()
    with SessionLocal() as db:
        one, _ = ingest_document(db, scheme_id=first_id, source_name="Official A", source_url="https://a.example", text="Karnataka solar pump grant installation subsidy eligibility")
        ingest_document(db, scheme_id=second_id, source_name="Official B", source_url="https://b.example", text="Karnataka solar pump support")
        results = retrieve_document_chunks(db, "solar pump grant", limit=5)
        assert results[0][1].id == one.id
        assert results[0][2] > results[1][2]
        assert all(document.scheme_id == first_id for _, document, _ in retrieve_document_chunks(db, "solar", scheme_id=first_id))


def test_scheme_search_includes_cited_document_evidence():
    scheme_id = _scheme_id()
    with SessionLocal() as db:
        ingest_document(db, scheme_id=scheme_id, source_name="Official Agriculture Ministry",
            source_url="https://agri.example/pumps", text="Karnataka farmers may claim solar pump subsidy.")
    from app.services.retrieval import search_schemes
    with SessionLocal() as db:
        match = next(item for item in search_schemes(db, "solar pump subsidy") if item.id == scheme_id)
        evidence = next(item for item in match.evidence if item.kind == "document_chunk")
        assert evidence.source_name == "Official Agriculture Ministry"
        assert evidence.source_url == "https://agri.example/pumps"
        assert evidence.document_id and evidence.chunk_id


def test_provider_receives_only_retrieved_cited_excerpts_and_engine_remains_authoritative():
    scheme_id = _scheme_id()
    profile = UserProfile(user_id=123, full_name="Fixture", age=20, gender="Other", state="Karnataka")
    with SessionLocal() as db:
        scheme = db.get(Scheme, scheme_id)
        before = check_scheme_eligibility(profile, scheme)
        ingest_document(db, scheme_id=scheme_id, source_name="Official guide", source_url="https://guide.example",
                        text="Farmers may apply for a solar pump grant.")
        class CaptureProvider:
            def explain(self, *, question, evidence, eligibility=None):
                assert evidence and evidence[0]["source_url"] == "https://guide.example"
                return "provider output"
        answer = answer_from_documents(db, question="solar pump grant", scheme_id=scheme_id,
                                       eligibility={"eligible": False, "reasons": ["age rule"]}, provider=CaptureProvider())
        assert answer.answer == "provider output"
        assert answer.evidence[0]["source_name"] == "Official guide"
        assert check_scheme_eligibility(profile, scheme) == before


def test_template_provider_fails_closed_without_evidence_and_does_not_override_decision():
    provider = GroundedTemplateProvider()
    assert "could not find" in provider.explain(question="unknown", evidence=[])
    answer = provider.explain(question="anything", evidence=[{"text": "Recorded excerpt", "source_name": "Official"}],
                              eligibility={"eligible": False, "reasons": ["not recorded"]})
    assert "not confirmed eligible" in answer and "Recorded excerpt" not in answer


def test_local_text_extraction_supports_text_markdown_and_rejects_unknown(tmp_path: Path):
    source = tmp_path / "guidance.txt"
    source.write_text("Official source text", encoding="utf-8")
    assert extract_text(source) == "Official source text"
    source = tmp_path / "binary.docx"
    source.write_bytes(b"ignored")
    with pytest.raises(ValueError):
        extract_text(source)
