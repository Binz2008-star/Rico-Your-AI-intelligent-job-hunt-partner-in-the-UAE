"""
src/api/rate_limit.py
Central rate-limiter configuration for the Rico API.

Uses Redis when REDIS_URL is set; falls back to in-process MemoryStorage
so the server starts cleanly even without Redis.

Import `limiter` everywhere you need a @limiter.limit() decorator.
Import `rate_limit_exceeded_handler` and register it on the FastAPI app.
"""
from __future__ import annotations

import logging
import os

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# ── Storage ───────────────────────────────────────────────────────────────────

def _storage_uri() -> str:
    redis_url = os.getenv("REDIS_URL", "").strip()
    if redis_url:
        logger.info("rate_limiter: using Redis storage")
        return redis_url
    logger.info("rate_limiter: no REDIS_URL — using in-memory storage (single-process only)")
    return "memory://"


# ── Client identity ───────────────────────────────────────────────────────────

def client_ip_key(request: Request) -> str:
    """Resolve the real client IP for rate-limiting.

    Behind Render's proxy the TCP peer is the load balancer, so ``request.client.host`` is
    identical for every user — using it would collapse all clients into a single bucket
    (so one noisy client could 429 everyone, or the limit could be effectively bypassed).
    Render forwards the originating client in ``X-Forwarded-For``; use its first entry when
    present, falling back to the direct peer (correct for local/dev with no proxy).
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return get_remote_address(request)


# ── Limiter singleton ─────────────────────────────────────────────────────────

limiter = Limiter(
    key_func=client_ip_key,
    storage_uri=_storage_uri(),
    default_limits=[],          # no global default — each route sets its own
)

# ── Limits (named constants so tests can reference them) ──────────────────────

LIMIT_LOGIN    = "5/minute"     # brute-force protection on auth
LIMIT_REGISTER = "3/minute"     # self-signup — strict to prevent abuse
LIMIT_CHAT     = "30/minute"    # Rico chat — generous for interactive use
LIMIT_UPLOAD   = "10/minute"    # CV upload — heavy parsing, keep low
LIMIT_WEBHOOK  = "60/minute"    # Jotform / Telegram — servers may burst
LIMIT_PASSWORD_RESET = "3/minute"  # forgot/reset — anti-enumeration & token brute-force
LIMIT_VERIFY_EMAIL   = "5/minute"  # verify + resend — prevent token-brute-force & spam
LIMIT_PROFILE  = "20/minute"    # profile reads/writes — prevent storage DoS
LIMIT_ADMIN    = "10/minute"    # admin endpoints — low ceiling, sensitive operations

# ── 429 response handler ──────────────────────────────────────────────────────

async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    logger.warning(
        "rate_limit_exceeded path=%s limit=%s client=%s",
        request.url.path,
        exc.limit,
        get_remote_address(request),
    )
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too many requests. Please slow down.",
            "limit": str(exc.limit),
            "retry_after": "60s",
        },
        headers={"Retry-After": "60"},
    )
