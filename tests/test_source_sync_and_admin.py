import pytest
from starlette.testclient import TestClient

from app.database.connection import SessionLocal, engine
from app.database.base import Base
from main import app
from app.models.scheme import Scheme
from app.models.scheme_source import SchemeSource
from app.models.scheme_document import SchemeDocument
from app.services.source_adapters import validate_safe_url, LocalCuratedSourceAdapter
from app.services.scheme_sync import sync_all_sources
from app.services.scheduler import get_scheduler_status, trigger_sync_now


@pytest.fixture(autouse=True)
def isolated_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _admin_headers(client: TestClient) -> dict[str, str]:
    client.post("/api/auth/register", json={"email": "admin@example.com", "password": "correct-horse-battery-staple"})
    resp = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "correct-horse-battery-staple"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_anti_ssrf_url_validation():
    # Valid government URLs
    valid, err = validate_safe_url("https://india.gov.in/schemes")
    assert valid and err is None

    valid, err = validate_safe_url("https://pmkisan.nic.in/portal")
    assert valid and err is None

    # Invalid non-HTTPS
    valid, err = validate_safe_url("http://india.gov.in")
    assert not valid and "HTTPS" in err

    # Invalid non-government domain
    valid, err = validate_safe_url("https://attacker-site.com/steal")
    assert not valid and "official government domain" in err

    # Invalid internal / private IP
    valid, err = validate_safe_url("https://127.0.0.1:8000/api")
    assert not valid

    valid, err = validate_safe_url("https://169.254.169.254/latest/meta-data")
    assert not valid


def test_local_curated_source_adapter():
    adapter = LocalCuratedSourceAdapter()
    records = adapter.fetch_schemes()
    assert len(records) > 0
    first = records[0]
    assert first["name"]
    assert first["source_name"]
    assert first["source_url"].startswith("https://")


def test_sync_all_sources_creates_schemes_and_versions():
    with SessionLocal() as db:
        source = SchemeSource(
            source_name="Local Starter Dataset",
            source_url="https://india.gov.in/my-government/schemes",
            source_type="local_curated",
            is_active=True,
        )
        db.add(source)
        db.commit()

        report = sync_all_sources(db, apply=True)
        assert report.added > 0 or report.discovered > 0
        assert report.failed == 0

        schemes = db.query(Scheme).all()
        assert len(schemes) > 0


def test_scheduler_status_and_sync_now():
    status = get_scheduler_status()
    assert "is_running" in status
    assert "sync_interval_hours" in status

    # Trigger sync now
    result = trigger_sync_now()
    assert "status" in result
    assert result["status"] == "completed"
    assert "report" in result


def test_admin_source_endpoints():
    client = TestClient(app)
    headers = _admin_headers(client)

    # 1. Register a new source
    create_resp = client.post(
        "/api/admin/scheme-data/sources",
        headers=headers,
        json={
            "source_name": "Ministry of Jal Shakti Portal",
            "source_url": "https://jaljeevanmission.gov.in",
            "source_type": "official_portal",
            "sync_interval_hours": 12,
            "notes": "Jal Jeevan Mission drinking water supply records",
        },
    )
    assert create_resp.status_code == 201
    source_id = create_resp.json()["id"]

    # 2. List sources
    list_resp = client.get("/api/admin/scheme-data/sources", headers=headers)
    assert list_resp.status_code == 200
    sources = list_resp.json()
    assert any(s["id"] == source_id for s in sources)

    # 3. Update source (disable)
    update_resp = client.put(
        f"/api/admin/scheme-data/sources/{source_id}",
        headers=headers,
        json={"is_active": False},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["is_active"] is False


def test_admin_diagnostics_and_retrieval_endpoints():
    client = TestClient(app)
    headers = _admin_headers(client)

    # Seed a scheme with a document
    with SessionLocal() as db:
        scheme = Scheme(
            name="National Health Mission",
            description="Healthcare coverage",
            benefit="Free medicines and maternal care",
            is_active=True,
            source_name="Ministry of Health",
            source_url="https://nhm.gov.in",
            verification_status="verified",
        )
        db.add(scheme)
        db.commit()

        from app.services.document_ingestion import ingest_document
        doc, _ = ingest_document(
            db,
            scheme_id=scheme.id,
            source_name="Ministry of Health",
            source_url="https://nhm.gov.in/guidelines",
            title="NHM Guidelines",
            text="Primary health centres provide essential drugs and maternal healthcare to rural residents.",
        )
        doc_id = doc.id

    # 1. GET /diagnostics
    diag_resp = client.get("/api/admin/scheme-data/diagnostics", headers=headers)
    assert diag_resp.status_code == 200
    diag = diag_resp.json()
    assert diag["total_schemes"] >= 1
    assert diag["total_documents"] >= 1
    assert diag["total_chunks"] >= 1
    assert diag["embedded_chunks"] >= 1

    # 2. POST /test-retrieval
    test_retrieval_resp = client.post(
        "/api/admin/scheme-data/test-retrieval",
        headers=headers,
        json={"query": "maternal healthcare drugs", "limit": 3},
    )
    assert test_retrieval_resp.status_code == 200
    ret_data = test_retrieval_resp.json()
    assert ret_data["match_count"] >= 1
    assert "rural residents" in ret_data["results"][0]["excerpt"]

    # 3. POST /documents/{id}/reindex
    reindex_resp = client.post(
        f"/api/admin/scheme-data/documents/{doc_id}/reindex",
        headers=headers,
    )
    assert reindex_resp.status_code == 200
    assert reindex_resp.json()["status"] == "completed"

    # 4. DELETE /documents/{id}
    del_resp = client.delete(
        f"/api/admin/scheme-data/documents/{doc_id}",
        headers=headers,
    )
    assert del_resp.status_code == 204
