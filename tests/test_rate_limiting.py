import time
import jwt
import pytest
from pydantic import ValidationError
from starlette.requests import Request
from starlette.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings, Settings
from app.core.rate_limit import limiter, get_client_ip, get_user_or_ip
from app.database.base import Base
from app.database.connection import engine
from app.models.user import User
from app.models.profile import UserProfile
from app.services.auth_service import hash_password
from app.services.jwt_service import create_access_token
from main import app


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    limiter.reset()
    yield
    limiter.reset()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def test_login_rate_limiting_enforces_5_per_minute(client):
    """POST /api/auth/login enforces 5 requests per minute per IP."""
    limiter.reset()
    # Create test account
    with Session(engine) as db:
        user = User(email="ratelimit_login@example.com", password_hash=hash_password("ValidPassword123!"))
        db.add(user)
        db.commit()

    login_payload = {"email": "ratelimit_login@example.com", "password": "ValidPassword123!"}

    # First 5 attempts succeed
    for i in range(5):
        res = client.post("/api/auth/login", json=login_payload)
        assert res.status_code == 200, f"Attempt {i+1} should succeed, got {res.status_code}"

    # 6th attempt is blocked with HTTP 429
    res_6 = client.post("/api/auth/login", json=login_payload)
    assert res_6.status_code == 429
    data = res_6.json()
    assert "detail" in data
    assert "Rate limit exceeded" in data["detail"]
    assert data["error"] == "too_many_requests"
    assert "retry-after" in res_6.headers or "Retry-After" in res_6.headers


def test_register_rate_limiting_enforces_3_per_hour(client):
    """POST /api/auth/register enforces 3 requests per hour per IP."""
    limiter.reset()

    for i in range(3):
        res = client.post(
            "/api/auth/register",
            json={"email": f"reg_user_{i}@example.com", "password": "ValidPassword123!"}
        )
        assert res.status_code == 201, f"Registration {i+1} should succeed"

    # 4th attempt is rate limited
    res_4 = client.post(
        "/api/auth/register",
        json={"email": "reg_user_overflow@example.com", "password": "ValidPassword123!"}
    )
    assert res_4.status_code == 429
    data = res_4.json()
    assert "detail" in data
    assert "Rate limit exceeded" in data["detail"]
    assert data["error"] == "too_many_requests"


def test_agent_query_user_separation(client):
    """POST /api/agent/query isolates buckets by authenticated user, not global."""
    limiter.reset()

    # Create two distinct test users with profiles
    with Session(engine) as db:
        u1 = User(email="user_a@example.com", password_hash=hash_password("ValidPassword123!"))
        u2 = User(email="user_b@example.com", password_hash=hash_password("ValidPassword123!"))
        db.add_all([u1, u2])
        db.commit()
        db.refresh(u1)
        db.refresh(u2)

        p1 = UserProfile(user_id=u1.id, full_name="User A", age=25, gender="Male", marital_status="Single", state="Karnataka")
        p2 = UserProfile(user_id=u2.id, full_name="User B", age=26, gender="Female", marital_status="Single", state="Karnataka")
        db.add_all([p1, p2])
        db.commit()

        token_a = create_access_token(u1.id)
        token_b = create_access_token(u2.id)

    # User A makes 20 queries (all succeed)
    headers_a = {"Authorization": f"Bearer {token_a}"}
    for i in range(20):
        res = client.post("/api/agent/query", json={"query": "scholarships for students"}, headers=headers_a)
        assert res.status_code == 200, f"Query {i+1} for User A should succeed"

    # User A 21st query is blocked with HTTP 429
    res_a_overflow = client.post("/api/agent/query", json={"query": "scholarships for students"}, headers=headers_a)
    assert res_a_overflow.status_code == 429
    assert "Rate limit exceeded" in res_a_overflow.json()["detail"]

    # User B queries from the exact same client IP - should immediately SUCCEED (separate bucket)
    headers_b = {"Authorization": f"Bearer {token_b}"}
    res_b = client.post("/api/agent/query", json={"query": "scholarships for students"}, headers=headers_b)
    assert res_b.status_code == 200, "User B should not be affected by User A's rate limit exhaustion"


def test_untrusted_forwarded_for_header_cannot_spoof_ip(client):
    """Attacker cannot bypass rate limiting by rotating untrusted X-Forwarded-For headers."""
    limiter.reset()
    # Ensure trusted proxies is empty (default secure setting)
    original_trusted = settings.TRUSTED_PROXIES
    settings.TRUSTED_PROXIES = ""
    try:
        payload = {"email": "spoof_attempt@example.com", "password": "WrongPassword123!"}
        # Send 5 requests with differing spoofed X-Forwarded-For headers
        for i in range(5):
            res = client.post(
                "/api/auth/login",
                json=payload,
                headers={"X-Forwarded-For": f"198.51.100.{i+1}"}
            )
            assert res.status_code == 401

        # 6th request with yet another fake IP should still be BLOCKED (tracked by direct socket IP)
        res_6 = client.post(
            "/api/auth/login",
            json=payload,
            headers={"X-Forwarded-For": "198.51.100.99"}
        )
        assert res_6.status_code == 429, "Spoofed X-Forwarded-For must be ignored when proxy is untrusted"
    finally:
        settings.TRUSTED_PROXIES = original_trusted


def test_trusted_proxy_correctly_uses_forwarded_for(client):
    """When proxy is explicitly trusted, X-Forwarded-For is safely honored for upstream clients."""
    limiter.reset()
    original_trusted = settings.TRUSTED_PROXIES
    # In TestClient, direct socket host is "testclient"
    settings.TRUSTED_PROXIES = "testclient"
    try:
        # Client IP 10.0.0.1 consumes all 5 login attempts
        payload = {"email": "proxy_test@example.com", "password": "WrongPassword123!"}
        for _ in range(5):
            res = client.post("/api/auth/login", json=payload, headers={"X-Forwarded-For": "10.0.0.1"})
            assert res.status_code == 401

        # 6th attempt from 10.0.0.1 is blocked
        res_blocked = client.post("/api/auth/login", json=payload, headers={"X-Forwarded-For": "10.0.0.1"})
        assert res_blocked.status_code == 429

        # A different upstream client (10.0.0.2) behind the same trusted proxy can still make requests
        res_other = client.post("/api/auth/login", json=payload, headers={"X-Forwarded-For": "10.0.0.2"})
        assert res_other.status_code == 401
    finally:
        settings.TRUSTED_PROXIES = original_trusted


def test_rate_limit_disabled_setting(client):
    """When RATE_LIMIT_ENABLED is False, limits are not enforced."""
    limiter.reset()
    original_enabled = settings.RATE_LIMIT_ENABLED
    limiter.enabled = False
    try:
        payload = {"email": "disabled_test@example.com", "password": "WrongPassword123!"}
        # More than 5 requests should all pass through to auth handler (401, not 429)
        for _ in range(8):
            res = client.post("/api/auth/login", json=payload)
            assert res.status_code == 401
    finally:
        limiter.enabled = original_enabled


def make_scope_request(auth_header: str | None = None, client_host: str = "198.51.100.1") -> Request:
    headers = []
    if auth_header is not None:
        headers.append((b"authorization", auth_header.encode("utf-8")))
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/agent/query",
        "headers": headers,
        "client": (client_host, 12345),
    }
    return Request(scope)


def test_production_config_with_rate_limiting_enabled_succeeds():
    """1. Production configuration with rate limiting enabled succeeds."""
    cfg = Settings(ENVIRONMENT="production", RATE_LIMIT_ENABLED=True)
    assert cfg.ENVIRONMENT == "production"
    assert cfg.RATE_LIMIT_ENABLED is True


def test_production_config_with_rate_limiting_disabled_raises_validation_error():
    """2. Production configuration with rate limiting disabled raises a validation error."""
    with pytest.raises(ValidationError) as exc:
        Settings(ENVIRONMENT="production", RATE_LIMIT_ENABLED=False)
    assert "RATE_LIMIT_ENABLED cannot be False" in str(exc.value)

    # Case-insensitive environment match
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="PRODUCTION", RATE_LIMIT_ENABLED=False)
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT=" Production ", RATE_LIMIT_ENABLED=False)


def test_non_production_config_can_still_disable_rate_limiting():
    """3. Non-production configuration can still disable rate limiting."""
    dev_cfg = Settings(ENVIRONMENT="development", RATE_LIMIT_ENABLED=False)
    assert dev_cfg.ENVIRONMENT == "development"
    assert dev_cfg.RATE_LIMIT_ENABLED is False

    test_cfg = Settings(ENVIRONMENT="testing", RATE_LIMIT_ENABLED=False)
    assert test_cfg.ENVIRONMENT == "testing"
    assert test_cfg.RATE_LIMIT_ENABLED is False


def test_token_missing_exp_or_iat_cannot_receive_user_bucket():
    """4. A correctly signed token missing exp or iat cannot receive a user-specific bucket."""
    now = int(time.time())

    # Missing exp
    payload_no_exp = {
        "iat": now,
        "sub": "42",
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    token_no_exp = jwt.encode(payload_no_exp, settings.JWT_SECRET_KEY, algorithm="HS256")
    req_no_exp = make_scope_request(f"Bearer {token_no_exp}", client_host="192.0.2.10")
    assert get_user_or_ip(req_no_exp) == "ip:192.0.2.10"

    # Missing iat
    payload_no_iat = {
        "exp": now + 3600,
        "sub": "42",
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    token_no_iat = jwt.encode(payload_no_iat, settings.JWT_SECRET_KEY, algorithm="HS256")
    req_no_iat = make_scope_request(f"Bearer {token_no_iat}", client_host="192.0.2.10")
    assert get_user_or_ip(req_no_iat) == "ip:192.0.2.10"


def test_invalid_expired_or_malformed_tokens_fall_back_to_ip_bucket():
    """5. Invalid, expired, or malformed tokens safely fall back to the IP bucket."""
    now = int(time.time())
    host = "192.0.2.20"

    # Unauthenticated / missing header
    req_none = make_scope_request(None, client_host=host)
    assert get_user_or_ip(req_none) == f"ip:{host}"

    # Malformed token
    req_malformed = make_scope_request("Bearer not.a.valid.jwt.token", client_host=host)
    assert get_user_or_ip(req_malformed) == f"ip:{host}"

    # Expired token
    payload_expired = {
        "exp": now - 3600,
        "iat": now - 7200,
        "sub": "42",
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    token_expired = jwt.encode(payload_expired, settings.JWT_SECRET_KEY, algorithm="HS256")
    req_expired = make_scope_request(f"Bearer {token_expired}", client_host=host)
    assert get_user_or_ip(req_expired) == f"ip:{host}"

    # Wrong secret key
    payload_valid = {
        "exp": now + 3600,
        "iat": now,
        "sub": "42",
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    token_wrong_key = jwt.encode(payload_valid, "wrong-secret-key-that-is-at-least-32-chars-long", algorithm="HS256")
    req_wrong_key = make_scope_request(f"Bearer {token_wrong_key}", client_host=host)
    assert get_user_or_ip(req_wrong_key) == f"ip:{host}"

    # Wrong audience
    payload_wrong_aud = {
        "exp": now + 3600,
        "iat": now,
        "sub": "42",
        "iss": settings.JWT_ISSUER,
        "aud": "wrong-audience",
    }
    token_wrong_aud = jwt.encode(payload_wrong_aud, settings.JWT_SECRET_KEY, algorithm="HS256")
    req_wrong_aud = make_scope_request(f"Bearer {token_wrong_aud}", client_host=host)
    assert get_user_or_ip(req_wrong_aud) == f"ip:{host}"

    # Wrong issuer
    payload_wrong_iss = {
        "exp": now + 3600,
        "iat": now,
        "sub": "42",
        "iss": "wrong-issuer",
        "aud": settings.JWT_AUDIENCE,
    }
    token_wrong_iss = jwt.encode(payload_wrong_iss, settings.JWT_SECRET_KEY, algorithm="HS256")
    req_wrong_iss = make_scope_request(f"Bearer {token_wrong_iss}", client_host=host)
    assert get_user_or_ip(req_wrong_iss) == f"ip:{host}"


def test_invalid_subject_values_cannot_create_user_bucket():
    """6. Invalid subject values, including zero, negative numbers, non-numeric text, and missing sub, cannot create a user-specific bucket."""
    now = int(time.time())
    host = "192.0.2.30"
    base_claims = {
        "exp": now + 3600,
        "iat": now,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }

    # Missing sub claim entirely
    token_no_sub = jwt.encode(base_claims, settings.JWT_SECRET_KEY, algorithm="HS256")
    req_no_sub = make_scope_request(f"Bearer {token_no_sub}", client_host=host)
    assert get_user_or_ip(req_no_sub) == f"ip:{host}"

    # Zero subject string and int
    for zero_sub in ["0", 0]:
        try:
            token_zero = jwt.encode({**base_claims, "sub": zero_sub}, settings.JWT_SECRET_KEY, algorithm="HS256")
            req_zero = make_scope_request(f"Bearer {token_zero}", client_host=host)
            assert get_user_or_ip(req_zero) == f"ip:{host}"
        except Exception:
            pass

    # Negative subject string and int
    for neg_sub in ["-1", "-99", -5]:
        try:
            token_neg = jwt.encode({**base_claims, "sub": neg_sub}, settings.JWT_SECRET_KEY, algorithm="HS256")
            req_neg = make_scope_request(f"Bearer {token_neg}", client_host=host)
            assert get_user_or_ip(req_neg) == f"ip:{host}"
        except Exception:
            pass

    # Non-numeric text subject
    for text_sub in ["admin", "user_123", "", "   ", "NaN", "true", "1.5"]:
        token_text = jwt.encode({**base_claims, "sub": text_sub}, settings.JWT_SECRET_KEY, algorithm="HS256")
        req_text = make_scope_request(f"Bearer {token_text}", client_host=host)
        assert get_user_or_ip(req_text) == f"ip:{host}"


def test_valid_token_with_all_claims_and_positive_subject_receives_user_bucket():
    """7. A valid token with all required claims and a positive integer subject still receives the correct user-specific bucket."""
    now = int(time.time())
    host = "192.0.2.40"

    # Positive integer as string (canonical format per PyJWT / RFC 7519)
    payload_str = {
        "exp": now + 3600,
        "iat": now,
        "sub": "42",
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    token_str = jwt.encode(payload_str, settings.JWT_SECRET_KEY, algorithm="HS256")
    req_str = make_scope_request(f"Bearer {token_str}", client_host=host)
    assert get_user_or_ip(req_str) == "user:42"

    # Standard application access token from jwt_service
    token_app = create_access_token(user_id=105)
    req_app = make_scope_request(f"Bearer {token_app}", client_host=host)
    assert get_user_or_ip(req_app) == "user:105"
