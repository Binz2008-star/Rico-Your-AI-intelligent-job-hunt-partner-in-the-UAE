"""
src/api/deps.py
FastAPI dependency injection for authentication and authorization.
"""
from __future__ import annotations

import hmac
import logging
import os
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request

from src.api.auth import decode_access_token

logger = logging.getLogger(__name__)


def _env_auth_fallback_allowed() -> bool:
    return os.getenv("ALLOW_ENV_AUTH_FALLBACK", "").lower() in ("1", "true", "yes")


def _token_auth_version(payload: Dict[str, Any]) -> int:
    """Token's auth-version claim; legacy tokens (no claim) count as version 1."""
    try:
        return int(payload.get("av") or 1)
    except (TypeError, ValueError):
        return 1


def get_current_user(request: Request) -> Dict[str, Any]:
    """
    Validate the JWT cookie AND the live account state (#1072).

    Beyond signature/expiry, tokens are checked against the users table:
    the account must still exist and be active, the token's auth-version
    claim ("av") must match the account's current auth_version (password
    reset / logout-all bump it, revoking older tokens), and the ROLE comes
    from the DB — never from a stale token claim.

    Fail-closed: if the user store is configured but unreachable, requests
    are rejected with a retryable 503 rather than authorized from stale
    claims. When no user store is configured at all (dev/test without
    DATABASE_URL), there are no DB accounts to revoke and the token's own
    claims are used, as before.

    Env-fallback admin tokens (claim auth="env") cannot participate in DB
    revocation; in production they are rejected unless
    ALLOW_ENV_AUTH_FALLBACK is explicitly set.

    Raises HTTP 401 if missing/invalid/revoked, 503 if the store is down.
    Usage: route(user: dict = Depends(get_current_user))
    """
    # Per-request cache — set ONLY by this function after full verification.
    # request.state.current_user is NOT trusted here: the app's
    # hydrate_request_auth_context middleware fills it from token CLAIMS ONLY
    # on every request, so treating it as authoritative would bypass the
    # auth_version / is_active / DB-role enforcement entirely (#1072).
    verified = getattr(request.state, "verified_user", None)
    if isinstance(verified, dict) and verified.get("email"):
        return verified

    token = request.cookies.get("access_token")
    request.state.access_token_present = bool(token)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated. POST /api/v1/auth/login first.",
        )
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    email = payload["sub"]
    token_role = payload.get("role", "user")   # legacy tokens have no role → default "user"

    if payload.get("auth") == "env":
        from src.api.auth import _is_production
        if _is_production() and not _env_auth_fallback_allowed():
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        user = {"email": email, "role": token_role}
    else:
        from src.db import is_db_available
        if not is_db_available():
            # No user store configured (dev/test) — nothing to revoke against.
            user = {"email": email, "role": token_role}
        else:
            from src.repositories.users_repo import AuthStoreUnavailable, get_auth_snapshot
            try:
                status, snapshot = get_auth_snapshot(email)
            except AuthStoreUnavailable:
                raise HTTPException(
                    status_code=503,
                    detail="Authentication temporarily unavailable — please retry",
                )
            if status != "found" or snapshot is None:
                raise HTTPException(status_code=401, detail="Invalid or expired token")
            if not snapshot["is_active"]:
                raise HTTPException(status_code=401, detail="Account is deactivated")
            if _token_auth_version(payload) != snapshot["auth_version"]:
                raise HTTPException(
                    status_code=401,
                    detail="Session expired. Please sign in again.",
                )
            user = {"email": email, "role": snapshot["role"] or "user"}

    request.state.verified_user = user
    # Overwrite the middleware's claims-only hydration so downstream readers
    # of request.state see the DB-verified identity on protected routes.
    request.state.current_user = user
    request.state.user_id = user["email"]
    return user


def get_current_user_id(request: Request) -> str:
    """
    Return the JWT ``sub`` claim as a bare string (the canonical user_id).

    This is the single enforcement point for JWT-derived user isolation.
    All SaaS-path routes that perform per-user data access MUST declare this
    as a dependency instead of extracting user_id ad-hoc.

    Raises HTTP 401 if the token is missing, invalid, or has an empty sub.
    Usage: route(user_id: str = Depends(get_current_user_id))
    """
    # request.state.user_id is claims-only middleware hydration — never
    # sufficient on its own (#1072). Only the verified cache short-circuits.
    verified = getattr(request.state, "verified_user", None)
    if isinstance(verified, dict) and str(verified.get("email", "")).strip():
        return str(verified["email"]).strip()

    user = get_current_user(request)
    user_id = user.get("email", "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing user identity (sub)")
    request.state.user_id = user_id
    return user_id


def require_admin(request: Request) -> Dict[str, Any]:
    """
    Validate the JWT cookie AND require role=admin. Raises 401/403 otherwise.
    Usage: route(user: dict = Depends(require_admin))
         or inline: require_admin(request)
    """
    user = get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def _owner_user_id() -> str:
    """The configured owner's immutable canonical user id (``users.id``).

    Read from ``RICO_OWNER_USER_ID`` (server-side only — NEVER returned to the
    browser). Empty when unset; callers must fail closed in that case so an
    unconfigured environment grants owner access to nobody.
    """
    return (os.getenv("RICO_OWNER_USER_ID") or "").strip()


def _resolve_canonical_user_id(user: Dict[str, Any]) -> Optional[str]:
    """Resolve the authenticated user's immutable numeric ``users.id``.

    Authorization for the owner surface is keyed on this id, not on email:
    email is only the JWT subject/lookup key, while ``users.id`` is the stable
    canonical identity that cannot be reassigned. Returns None when the id
    cannot be established (env-auth token with no DB account, DB unavailable,
    or account not found) so callers fail closed.
    """
    email = (user or {}).get("email")
    if not email:
        return None
    from src.db import is_db_available
    if not is_db_available():
        return None
    try:
        from src.repositories.users_repo import get_user_by_email
        row = get_user_by_email(email)
    except Exception:
        logger.warning("owner_id_resolve_failed", exc_info=True)
        return None
    return str(row.id) if row else None


def is_owner(user: Dict[str, Any]) -> bool:
    """Whether ``user`` is Rico's owner account.

    True only when ``RICO_OWNER_USER_ID`` is configured AND the authenticated
    account's immutable ``users.id`` matches it. Fails closed (returns False)
    when the owner id is unset or the canonical id cannot be resolved. The
    owner id itself is never returned to callers — only this boolean.
    """
    owner_id = _owner_user_id()
    if not owner_id:
        return False
    canonical_id = _resolve_canonical_user_id(user)
    return canonical_id is not None and hmac.compare_digest(canonical_id, owner_id)


def require_owner(request: Request) -> Dict[str, Any]:
    """Validate the JWT cookie AND require the authenticated account to be the owner.

    Authorization is server-side only and keyed on the immutable canonical
    ``users.id`` (compared against ``RICO_OWNER_USER_ID``), never on email
    alone. Raises 401 when unauthenticated and 403 for any authenticated
    non-owner (including when the owner id is unconfigured — fail closed).

    Usage: route(owner: dict = Depends(require_owner))
    """
    user = get_current_user(request)  # raises 401 when unauthenticated
    if not is_owner(user):
        raise HTTPException(status_code=403, detail="Owner access required")
    return user


def require_cron_secret(request: Request) -> None:
    """
    Authorize a server-to-server cron call via a shared secret.

    Render Cron jobs cannot carry a JWT cookie, so cron-only endpoints (e.g. the
    follow-up reminders sweep) are guarded by an ``X-Cron-Secret`` header compared
    against the ``RICO_CRON_SECRET`` env var using a constant-time comparison.

    Fails closed: if ``RICO_CRON_SECRET`` is unset the endpoint is treated as
    not-configured (503) and never falls open. Returns None on success.
    Usage: route(_cron: None = Depends(require_cron_secret))
    """
    expected = (os.getenv("RICO_CRON_SECRET") or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Cron endpoint not configured")
    provided = (request.headers.get("X-Cron-Secret") or "").strip()
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail="Invalid cron secret")
