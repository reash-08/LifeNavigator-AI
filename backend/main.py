from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.core.config import settings
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.services.scheduler import start_scheduler, stop_scheduler
from app.routers.profile import router as profile_router
from app.routers.auth import router as auth_router
from app.routers.users import router as users_router
from app.routers.schemes import router as schemes_router
from app.routers.eligibility import router as eligibility_router
from app.routers.eligibility_rules import router as eligibility_rules_router
from app.routers.retrieval import router as retrieval_router
from app.routers.agent import router as agent_router
from app.routers.scheme_data_admin import router as scheme_data_admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="LifeNavigator AI",
    description="AI-powered government benefits discovery and eligibility platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(retrieval_router)
app.include_router(agent_router)
app.include_router(schemes_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(profile_router)
app.include_router(eligibility_router)
app.include_router(eligibility_rules_router)
app.include_router(scheme_data_admin_router)

@app.get("/")
def root():
    return {
        "message": "LifeNavigator AI API is running"
    }


@app.get("/health", tags=["Health"])
def health_check():
    """Liveness probe: verifies process is running."""
    return {"status": "ok"}


@app.get("/health/ready", tags=["Health"])
def readiness_check():
    """Readiness probe: verifies database connectivity."""
    try:
        from sqlalchemy import text
        from app.database.connection import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "status": "ready",
            "database": "connected",
        }
    except Exception:
        from fastapi import status
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "database": "disconnected",
                "error": "Database connectivity check failed",
            },
        )
