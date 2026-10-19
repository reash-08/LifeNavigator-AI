from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.database.connection import engine
from main import app


def test_app_metadata_and_routes_are_registered():
    assert app.title == "LifeNavigator AI"
    assert app.version == "1.0.0"

    paths = set(app.openapi()["paths"])
    assert "/" in paths
    assert "/health" in paths
    assert "/health/ready" in paths
    assert "/api/schemes/search" in paths


def test_application_lifespan_starts_and_stops_scheduler(monkeypatch):
    start = MagicMock()
    stop = MagicMock()
    monkeypatch.setattr("main.start_scheduler", start)
    monkeypatch.setattr("main.stop_scheduler", stop)

    with TestClient(app):
        start.assert_called_once_with()
        stop.assert_not_called()

    stop.assert_called_once_with()


def test_root_and_liveness_endpoints_do_not_require_database():
    with TestClient(app) as client:
        root = client.get("/")
        health = client.get("/health")

    assert root.status_code == 200
    assert root.json() == {"message": "LifeNavigator AI API is running"}
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}


def test_readiness_probe_uses_a_simple_connection_check_without_database_io(monkeypatch):
    connection = MagicMock()
    context = MagicMock()
    context.__enter__.return_value = connection
    context.__exit__.return_value = False
    connect = MagicMock(return_value=context)
    monkeypatch.setattr(engine, "connect", connect)

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "connected"}
    connect.assert_called_once_with()
    connection.execute.assert_called_once()
    assert str(connection.execute.call_args.args[0]) == "SELECT 1"


def test_scheme_search_rejects_invalid_limit_before_database_access(monkeypatch):
    connect = MagicMock(side_effect=AssertionError("database access is not expected"))
    monkeypatch.setattr(engine, "connect", connect)

    with TestClient(app) as client:
        response = client.get("/api/schemes/search", params={"limit": 0})

    assert response.status_code == 422
    assert connect.call_count == 0
