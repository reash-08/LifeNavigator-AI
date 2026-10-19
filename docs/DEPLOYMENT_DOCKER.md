# LifeNavigator-AI — Production Docker Deployment Guide

This guide details the complete procedure for building, deploying, operating, and rolling back LifeNavigator-AI in a production or staging containerized environment.

---

## 1. Architecture Overview

The containerized stack consists of four decoupled services defined in `docker-compose.prod.yml`:

```
┌────────────────────────────────────────────────────────┐
│                        Internet                        │
└───────────────────────────┬────────────────────────────┘
                            │ Port 3000 (or 80)
                            ▼
               ┌────────────────────────┐
               │       frontend         │
               │  (Nginx 1.27-Alpine)   │
               │   Static Assets & SPA  │
               └────────────┬───────────┘
                            │ Internal Reverse Proxy: /api, /health
                            ▼
               ┌────────────────────────┐
               │        backend         │
               │   (Python 3.11-Slim)   │
               │   FastAPI / Uvicorn    │
               └───────┬────────┬───────┘
                       │        │
      Depends on exit 0│        │ SQL / pgvector
                       ▼        ▼
       ┌───────────────────┐  ┌───────────────────┐
       │     migration     │  │        db         │
       │ (Alembic One-Off) │  │ (PostgreSQL 16    │
       │  alembic upgrade  │  │  + pgvector)      │
       └───────────────────┘  └───────────────────┘
```

- **`frontend`**: Multi-stage build (Node.js 20 build -> Nginx Alpine runtime). Serves pre-compiled Vite static assets and reverse-proxies `/api` and `/health` requests directly to `backend:8000`.
- **`backend`**: Minimal Python 3.11 container executing as non-root user `appuser`. Provides the FastAPI API, RAG vector retrieval, and eligibility engines.
- **`migration`**: One-off Alembic runner container (`restart: "no"`). Runs `alembic upgrade head` after `db` becomes healthy and before `backend` starts, eliminating migration race conditions across backend worker processes.
- **`db`**: PostgreSQL 16 with `pgvector` extension and persistent named volume `lifenavigator_postgres_data`.

---

## 2. Environment Setup

1. Copy the production environment template:
   ```bash
   cp .env.prod.example .env.prod
   ```
2. Generate a secure 48-byte URL-safe secret key for JWT signing:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```
3. Set `POSTGRES_PASSWORD` and update `DATABASE_URL` with that password in `.env.prod`.
4. Ensure `ENVIRONMENT=production` and `RATE_LIMIT_ENABLED=true`.

> **Note on Externally Managed Databases**:
> If deploying against a managed PostgreSQL instance (e.g., AWS RDS, GCP Cloud SQL, Supabase, Azure):
> 1. Set `DATABASE_URL` to your external connection string.
> 2. Remove or comment out the `db` service block in `docker-compose.prod.yml`, and remove the `db` condition from `migration` and `backend` dependencies.

---

## 3. Building and Starting the Stack

### Step 1: Build Images
Build the production images using Docker Compose:
```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod build
```

### Step 2: Launch Stack
Start all services in detached mode:
```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```
Docker Compose will automatically:
1. Start `db` and wait for PostgreSQL `pg_isready` to return 0.
2. Launch `migration` to execute `alembic upgrade head` against `db`.
3. Launch `backend` once `migration` exits with 0 and `db` is healthy.
4. Launch `frontend` once `backend` reports healthy.

---

## 4. Health Verification & Probing

### Automatic Container Health Probes
- **Backend Readiness**: Probes `GET http://127.0.0.1:8000/health/ready`, testing active database connectivity (`SELECT 1`).
  - Returns `200 OK` (`{"status": "ready", "database": "connected"}`) when healthy.
  - Returns `503 Service Unavailable` (`{"status": "not_ready", "database": "disconnected"}`) if database connectivity drops.
- **Frontend Liveness**: Probes HTTP port 80 via `wget -q --spider http://127.0.0.1/`.

### Manual Health Checks from Host
Verify stack health using curl:
```bash
# Check frontend serving
curl -I http://localhost:3000/

# Check backend through frontend proxy
curl http://localhost:3000/health
# Returns: {"status":"ok"}

# Check backend database readiness directly
curl http://localhost:8000/health/ready
# Returns: {"status":"ready","database":"connected"}
```

---

## 5. Log Inspection & Troubleshooting

Inspect logs across all containers or per service:
```bash
# Stream all logs
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f

# Inspect migration logs specifically
docker compose -f docker-compose.prod.yml --env-file .env.prod logs migration

# Inspect backend logs
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f backend

# Inspect database logs
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f db
```

---

## 6. Maintenance & Manual Migrations

If manual migration inspection is required:
```bash
# Check current migration revision
docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm backend alembic current

# Run migrations manually
docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm backend alembic upgrade head
```

---

## 7. Graceful Shutdown & Teardown

To stop the running application without deleting persistent database volumes:
```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod down
```

> **Warning**: Do NOT use `docker compose down -v` in production, as the `-v` flag deletes named persistent volumes (`postgres_data`).

---

## 8. Rollback Strategy

If a deployment must be rolled back:

1. **Revert Application Containers**:
   ```bash
   # Checkout previous stable release git tag or image commit
   git checkout <previous_stable_tag>
   docker compose -f docker-compose.prod.yml --env-file .env.prod build
   ```

2. **Roll Back Database Schema (if migrations were executed)**:
   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm backend alembic downgrade <previous_revision_id>
   ```

3. **Restart the Stack**:
   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
   ```
4. Verify readiness with `curl http://localhost:8000/health/ready`.
