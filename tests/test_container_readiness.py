import subprocess
from pathlib import Path
from unittest.mock import patch
import pytest
from starlette.testclient import TestClient

from app.database.connection import engine
from main import app

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_backend_health_liveness_returns_ok(client):
    """GET /health liveness probe returns HTTP 200 without touching database."""
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_backend_health_readiness_with_database_available(client):
    """GET /health/ready readiness probe returns HTTP 200 when database is reachable."""
    res = client.get("/health/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"


def test_backend_health_readiness_with_database_unavailable(client):
    """GET /health/ready returns HTTP 503 when database connectivity fails."""
    with patch.object(engine, "connect", side_effect=Exception("Database connection timeout")):
        res = client.get("/health/ready")
        assert res.status_code == 503
        data = res.json()
        assert data["status"] == "not_ready"
        assert data["database"] == "disconnected"
        assert "Database connectivity check failed" in data["error"]


def test_backend_dockerfile_structure():
    """Verify backend Dockerfile exists and enforces non-root, pinned image, and readiness probe."""
    dockerfile_path = REPO_ROOT / "backend" / "Dockerfile"
    assert dockerfile_path.exists(), "backend/Dockerfile must exist"
    content = dockerfile_path.read_text(encoding="utf-8")

    assert "python:3.11-slim" in content, "Must use pinned Python 3.11-slim base image"
    assert "useradd" in content and "appuser" in content, "Must create a dedicated non-root user"
    assert "USER appuser" in content, "Must switch to non-root execution"
    assert "WORKDIR /app" in content
    assert "EXPOSE 8000" in content
    assert "/health/ready" in content, "Healthcheck directive must probe /health/ready"


def test_frontend_dockerfile_structure():
    """Verify frontend Dockerfile implements multi-stage build and Nginx Alpine serving."""
    dockerfile_path = REPO_ROOT / "frontend" / "Dockerfile"
    nginx_conf_path = REPO_ROOT / "frontend" / "nginx.conf"
    assert dockerfile_path.exists(), "frontend/Dockerfile must exist"
    assert nginx_conf_path.exists(), "frontend/nginx.conf must exist"

    content = dockerfile_path.read_text(encoding="utf-8")
    assert "FROM node:" in content and "AS builder" in content, "Must include Node builder stage"
    assert "FROM nginx:" in content and "AS production" in content, "Must include Nginx production stage"
    assert "EXPOSE 80" in content
    assert "COPY nginx.conf" in content

    nginx_content = nginx_conf_path.read_text(encoding="utf-8")
    assert "proxy_pass http://backend:8000/api/;" in nginx_content, "Nginx must reverse-proxy /api/ to backend"
    assert "try_files $uri $uri/ /index.html;" in nginx_content, "Nginx must support SPA client-side routing"


def test_dockerignore_files_content():
    """Verify .dockerignore files exclude local virtual environments, caches, and secrets."""
    backend_dockerignore = REPO_ROOT / "backend" / ".dockerignore"
    frontend_dockerignore = REPO_ROOT / "frontend" / ".dockerignore"
    root_gitignore = REPO_ROOT / ".gitignore"

    assert backend_dockerignore.exists()
    assert frontend_dockerignore.exists()

    b_content = backend_dockerignore.read_text(encoding="utf-8")
    assert ".venv" in b_content
    assert "__pycache__" in b_content
    assert ".env" in b_content
    assert "*.db" in b_content

    f_content = frontend_dockerignore.read_text(encoding="utf-8")
    assert "node_modules" in f_content
    assert "dist" in f_content

    g_content = root_gitignore.read_text(encoding="utf-8")
    assert "node_modules" in g_content
    assert ".venv" in g_content
    assert "*.db" in g_content


def test_docker_compose_cli_validation():
    """Verify docker-compose.prod.yml parses cleanly with docker compose config CLI."""
    compose_path = REPO_ROOT / "docker-compose.prod.yml"
    env_example_path = REPO_ROOT / ".env.prod.example"
    assert compose_path.exists()
    assert env_example_path.exists()

    # 1. Default startup verification: migration service must NOT run automatically
    cmd_default = ["docker", "compose", "-f", str(compose_path), "--env-file", str(env_example_path), "config"]
    res_default = subprocess.run(cmd_default, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=str(REPO_ROOT))
    assert res_default.returncode == 0, f"docker compose config failed: {res_default.stderr}"
    assert "lifenavigator-backend" in res_default.stdout
    assert "lifenavigator-db" in res_default.stdout
    assert "lifenavigator-frontend" in res_default.stdout
    # Safety invariant: lifenavigator-migration must be excluded from default startup
    assert "lifenavigator-migration" not in res_default.stdout, "Safety violation: migration service must not run on default startup"

    # 2. Manual migration profile verification: migration service parses cleanly when explicitly targeted
    cmd_manual = ["docker", "compose", "-f", str(compose_path), "--env-file", str(env_example_path), "--profile", "manual-migration", "config"]
    res_manual = subprocess.run(cmd_manual, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=str(REPO_ROOT))
    assert res_manual.returncode == 0, f"docker compose manual-migration config failed: {res_manual.stderr}"
    assert "lifenavigator-migration" in res_manual.stdout
