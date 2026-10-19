import pytest
from starlette.testclient import TestClient
from app.core.config import Settings
from main import app


@pytest.fixture
def client():
    # Use TestClient with lifespan disabled to avoid running background scheduler in unit tests
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def test_psycopg_driver_import_and_dialect():
    """Verify that psycopg v3 binary driver is installed and loadable by SQLAlchemy."""
    import psycopg
    assert psycopg.__version__ is not None
    from sqlalchemy.dialects import registry
    dialect_cls = registry.load("postgresql.psycopg")
    assert dialect_cls is not None


def test_cors_permitted_origin_simple_request(client):
    """Permitted origin receives matching Access-Control-Allow-Origin and credentials."""
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:5173"}
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_permitted_origin_127_0_0_1(client):
    """Alternative permitted local origin receives CORS headers."""
    response = client.get(
        "/health",
        headers={"Origin": "http://127.0.0.1:5173"}
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_preflight_request_options(client):
    """Preflight OPTIONS request from permitted origin receives HTTP 200 and allowed methods/headers."""
    response = client.options(
        "/api/schemes/search",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization, content-type",
        }
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "GET" in response.headers.get("access-control-allow-methods", "")
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_rejected_origin_no_allow_header(client):
    """Disallowed origin does NOT receive Access-Control-Allow-Origin header."""
    response = client.get(
        "/health",
        headers={"Origin": "https://unauthorized-external-site.com"}
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_cors_rejected_origin_preflight(client):
    """Disallowed origin preflight does NOT receive Access-Control-Allow-Origin header."""
    response = client.options(
        "/api/schemes/search",
        headers={
            "Origin": "https://malicious-attacker.org",
            "Access-Control-Request-Method": "POST",
        }
    )
    assert "access-control-allow-origin" not in response.headers


def test_cors_settings_rejects_wildcard_with_credentials():
    """Security rule: Wildcard '*' cannot be configured with credentials."""
    with pytest.raises(ValueError, match="Wildcard '\\*' origin is not permitted"):
        Settings(
            DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/db",
            JWT_SECRET_KEY="a" * 32,
            CORS_ALLOWED_ORIGINS="*"
        )


def test_cors_settings_rejects_invalid_scheme():
    """Security rule: Origins must specify protocol (http:// or https://)."""
    with pytest.raises(ValueError, match="Invalid CORS origin"):
        Settings(
            DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/db",
            JWT_SECRET_KEY="a" * 32,
            CORS_ALLOWED_ORIGINS="localhost:5173"
        )


def test_cors_settings_strips_trailing_slashes():
    """Browser origin comparison is sensitive to trailing slashes; configuration normalizes them."""
    s = Settings(
        DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/db",
        JWT_SECRET_KEY="a" * 32,
        CORS_ALLOWED_ORIGINS="https://app.lifenavigator.gov.in/, https://admin.lifenavigator.gov.in"
    )
    assert s.cors_origins == [
        "https://app.lifenavigator.gov.in",
        "https://admin.lifenavigator.gov.in"
    ]
