"""Centralized API rate limiting and client identity resolution.

Provides client IP extraction that does not blindly trust forwarding headers,
authenticated user identification for dedicated per-user buckets,
and consistent JSON HTTP 429 responses.

NOTE ON DISTRIBUTED DEPLOYMENTS:
The default in-memory storage used by SlowAPI stores bucket state in local process
memory and is not synchronized across multiple separate worker processes or containers.
For multi-worker or multi-container production environments requiring cluster-wide limits,
configure a Redis-backed storage URI:
    limiter = Limiter(..., storage_uri=settings.REDIS_URL or "redis://localhost:6379/0")
"""
from __future__ import annotations

import logging
from typing import Any
from fastapi import Request, status
from fastapi.responses import JSONResponse
import jwt
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from app.core.config import settings

logger = logging.getLogger("lifenavigator.rate_limit")


def get_client_ip(request: Request) -> str:
    """Resolve client IP safely without blindly trusting forwarding headers.

    If TRUSTED_PROXIES is configured and the direct socket address is in the
    trusted set, the leftmost client IP from X-Forwarded-For (or X-Real-IP) is used.
    Otherwise, the direct socket client address is returned, preventing spoofing.
    """
    direct_ip = "127.0.0.1"
    if request.client and request.client.host:
        direct_ip = request.client.host

    trusted = settings.trusted_proxies_list
    if trusted and direct_ip in trusted:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # X-Forwarded-For format: client, proxy1, proxy2
            ips = [item.strip() for item in forwarded_for.split(",") if item.strip()]
            if ips:
                return ips[0]
        real_ip = request.headers.get("x-real-ip")
        if real_ip and real_ip.strip():
            return real_ip.strip()

    return direct_ip


def get_user_or_ip(request: Request) -> str:
    """Resolve client identifier for user-specific rate limit buckets.

    Extracts verified 'sub' claim from Bearer JWT. Validates the signature,
    algorithm, issuer, and audience, and strictly requires the same claims
    as the security layer ('exp', 'iat', 'sub', 'iss', 'aud').

    A user-specific bucket ('user:<sub_id>') is only assigned if 'sub' is
    a valid positive integer identifier. If unauthenticated, expired,
    malformed, or having an invalid subject, safely falls back to the client IP.
    """
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                audience=settings.JWT_AUDIENCE,
                issuer=settings.JWT_ISSUER,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
            sub = payload.get("sub")
            if sub is not None and not isinstance(sub, bool):
                if isinstance(sub, int) and sub > 0:
                    return f"user:{sub}"
                elif isinstance(sub, str) and sub.strip().isdigit() and int(sub.strip()) > 0:
                    return f"user:{int(sub.strip())}"
        except Exception:
            pass

    return f"ip:{get_client_ip(request)}"


limiter = Limiter(
    key_func=get_client_ip,
    enabled=settings.RATE_LIMIT_ENABLED,
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return a consistent JSON HTTP 429 response when a rate limit is exceeded."""
    limit_detail = str(exc.detail) if exc.detail else "Rate limit exceeded"
    # Format clean error message
    detail_message = f"Rate limit exceeded: {limit_detail}. Please try again later."
    
    headers: dict[str, str] = {}
    retry_after = getattr(exc, "retry_after", None)
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    else:
        headers["Retry-After"] = "60"

    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "detail": detail_message,
            "error": "too_many_requests",
            "limit": limit_detail,
        },
        headers=headers,
    )
