# LifeNavigator-AI

LifeNavigator-AI is an end-to-end AI agent and benefits navigation platform designed to help citizens discover government welfare schemes, evaluate verified eligibility criteria, and obtain grounded answers with source citations from official documents.

The system features:
- **Hybrid RAG Pipeline**: Combines 384-dimensional vector embeddings with lexical keyword matching, returning grounded answers with source citations and strict prompt-injection defenses.
- **In-Database Vector Store Adapter**: L2-normalized vector storage integrated with PostgreSQL without requiring external vector database services.
- **Authorized Source Registry & Connectors**: Automated synchronization adapters for official `.gov.in` and `.nic.in` government domains, with anti-SSRF protection.
- **Automated Daily Synchronization & Background Scheduler**: Thread-safe background worker with atomic locking, configurable daily polling intervals, and manual "Sync now" capabilities.
- **Scheme Versioning & Review Workflow**: Full provenance tracking, version snapshots, change detection, and administrator approval workflows.
- **Deterministic Eligibility Engine**: Strict separation between rule-based eligibility evaluation and language-model generated explanations.
- **Citizen Experience & Administration Dashboard**: Complete vanilla JS SPA preserving the custom design system (DM Sans, Manrope, `#285b46` green, `#f7f8f4` neutral background).

---

## Architecture & Data Flow

```
+-------------------------------------------------------------------------------+
|                             CITIZEN & ADMIN UI                                |
|          (Vanilla JS + CSS SPA bundled via Vite - Preserved Design)           |
+-------------------------------------------------------------------------------+
                                      | HTTP API
                                      v
+-------------------------------------------------------------------------------+
|                              FASTAPI BACKEND                                  |
|                                                                               |
|   +-----------------------+   +-------------------+   +-------------------+   |
|   |   Auth & User Roles   |   | Eligibility Rules |   |  AI Agent Router  |   |
|   +-----------------------+   +-------------------+   +-------------------+   |
|                                                                               |
|   +-----------------------------------------------------------------------+   |
|   |                         HYBRID RAG PIPELINE                           |   |
|   |   * DeterministicSemanticEmbeddingProvider (384-dim, unit-norm)       |   |
|   |   * Vector Cosine Similarity Search (JSON vector store adapter)       |   |
|   |   * Lexical Token Overlap Scoring                                     |   |
|   |   * GroundedTemplateProvider & LLM Provider with Injection Defense    |   |
|   +-----------------------------------------------------------------------+   |
|                                                                               |
|   +-----------------------------------------------------------------------+   |
|   |                   SOURCE REGISTRY & SCHEDULER                         |   |
|   |   * Daily Scheduled Worker (Atomic Lock, Thread-Safe)                 |   |
|   |   * Anti-SSRF URL Validation (Official Government Domains)            |   |
|   |   * Scheme Sync & Version Snapshotting                                |   |
|   +-----------------------------------------------------------------------+   |
+-------------------------------------------------------------------------------+
                                      | SQLAlchemy 2.0
                                      v
+-------------------------------------------------------------------------------+
|                            POSTGRESQL DATABASE                                |
|   * schemes & scheme_versions                                                 |
|   * scheme_sources & scheme_import_history                                     |
|   * scheme_documents & scheme_document_chunks (embedding vector store)        |
|   * users & user_profiles & eligibility_rules                                 |
+-------------------------------------------------------------------------------+
```

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env`.

| Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+psycopg://username:password@localhost:5432/lifenavigator` |
| `JWT_SECRET_KEY` | Secret key for HS256 tokens (min 32 chars) | `your-secure-random-32-char-key` |
| `JWT_ALGORITHM` | JWT signing algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Lifetime of access tokens | `60` |
| `ADMIN_EMAILS` | Comma-separated admin emails | `admin@example.com` |
| `EMBEDDING_PROVIDER` | Embedding provider (`deterministic` or `openai`) | `deterministic` |
| `LLM_PROVIDER` | Explanation provider (`template`, `openai`, `gemini`) | `template` |
| `OPENAI_API_KEY` | Optional OpenAI key | (optional) |
| `GEMINI_API_KEY` | Optional Google Gemini key | (optional) |
| `SYNC_INTERVAL_HOURS` | Interval for background source sync | `24` |
| `SCHEDULER_ENABLED` | Enable the background source sync worker | `true` |
| `RAG_SIMILARITY_THRESHOLD` | Minimum similarity threshold | `0.1` |
| `HYBRID_ALPHA` | Semantic vs lexical weight balance (0.0 to 1.0) | `0.6` |

---

## Database Migrations

Database schema migrations are managed via Alembic:

```powershell
# From the repository root:
.\backend\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
```

---

## Running the Application

### 1. Backend Server (FastAPI)

```powershell
# In PowerShell:
cd C:\GitHub\LifeNavigator-AI\backend
.\.venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 8000
```
- API Docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`
- The background scheduler automatically starts during FastAPI lifespan startup.

### 2. Frontend Development Server (Vite)

```powershell
# In PowerShell:
cd C:\GitHub\LifeNavigator-AI\frontend
npm run dev
```
- Web Application: `http://localhost:5173`

---

## Administration & Operations

### Registering an Administrator
1. Ensure the desired email (e.g. `admin@example.com`) is present in `ADMIN_EMAILS` in `backend/.env`.
2. Open the web application and register an account with that email.
3. Upon login, the "Admin" navigation item appears in the sidebar.

### Scheduled Synchronization & Manual Sync
- The background scheduler executes daily (or at the interval specified by `SYNC_INTERVAL_HOURS`).
- An administrator can click **"Sync now"** in the **Sources & sync** admin tab or call:
  ```http
  POST /api/admin/scheme-data/sync-now
  ```
- Scheduler status and health can be queried at:
  ```http
  GET /api/admin/scheme-data/sync-status
  ```

### Official Document Ingestion & Reindexing
- To ingest an official government circular or document:
  Use the **Documents** tab in the admin dashboard, select the scheme, enter the official HTTPS source URL, and paste the official text.
- Each document is automatically split into semantic chunks, hashed, and indexed with embeddings.
- Existing documents can be reindexed with new embeddings via **Reindex** or removed via **Remove**.

### RAG Diagnostics
- Real-time observability into indexed documents, chunk counts, embedded counts, and vector store dimensions is available under the **RAG diagnostics** admin tab.
- An interactive **Test hybrid retrieval** query tool is provided to test semantic vector similarity and keyword overlap scores.

---

## Running Tests

### Backend Unit & Integration Tests (pytest)
```powershell
.\backend\.venv\Scripts\python.exe -m pytest tests
```

### Frontend Tests, Lint, and Build
```powershell
cd frontend
npm test
npm run lint
npm run build
```
