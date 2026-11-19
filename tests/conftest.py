import os
import sys
from pathlib import Path
import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
TEST_DATABASE = Path(__file__).resolve().parent / "test_life_navigator.db"
sys.path.insert(0, str(BACKEND_DIR))

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DATABASE.as_posix()}"
os.environ["JWT_SECRET_KEY"] = "test-secret-that-is-longer-than-thirty-two-characters"
os.environ["ADMIN_EMAILS"] = "admin@example.com"
os.environ["SCHEDULER_ENABLED"] = "false"


@pytest.fixture(autouse=True)
def isolate_rate_limiter():
    """Reset rate limiter storage before and after each test for clean isolation."""
    try:
        from app.core.rate_limit import limiter
        limiter.reset()
    except Exception:
        pass
    yield
    try:
        from app.core.rate_limit import limiter
        limiter.reset()
    except Exception:
        pass
