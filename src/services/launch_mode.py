"""Authoritative pre-launch access policy.

The feature is intentionally opt-in: an absent or invalid RICO_LAUNCH_MODE
keeps the existing live product behavior. Production activation is a separate
operator action after preview, CI, migration, and owner smoke checks pass.
"""
from __future__ import annotations

import os
from typing import Any

LIVE_MODE = "live"
WAITLIST_MODE = "waitlist"


def get_launch_mode() -> str:
    raw = os.getenv("RICO_LAUNCH_MODE", LIVE_MODE).strip().lower()
    return WAITLIST_MODE if raw == WAITLIST_MODE else LIVE_MODE


def is_waitlist_mode() -> bool:
    return get_launch_mode() == WAITLIST_MODE


def _normalise_email(value: str | None) -> str:
    return (value or "").strip().lower()


def internal_allowlist() -> frozenset[str]:
    configured = {
        _normalise_email(item)
        for item in os.getenv("INTERNAL_ALLOWLIST_EMAILS", "").split(",")
        if _normalise_email(item)
    }
    admin_email = _normalise_email(os.getenv("ADMIN_EMAIL"))
    if admin_email:
        configured.add(admin_email)
    return frozenset(configured)


def is_internal_email(email: str | None) -> bool:
    normalised = _normalise_email(email)
    return bool(normalised) and normalised in internal_allowlist()


def request_user_email(request: Any) -> str | None:
    current_user = getattr(getattr(request, "state", None), "current_user", None)
    if not isinstance(current_user, dict):
        return None
    email = current_user.get("email")
    return str(email) if email else None


# Public API routes that remain available while the product is in waitlist mode.
# All other /api/v1 routes fail closed unless the authenticated email is allowed.
_WAITLIST_PUBLIC_EXACT = frozenset(
    {
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        "/api/v1/auth/me",
        "/api/v1/auth/forgot-password",
        "/api/v1/auth/reset-password",
        "/api/v1/auth/verify-email",
        "/api/v1/auth/resend-verification",
        "/api/v1/prelaunch/access",
        "/api/v1/waitlist/register",
        "/api/v1/version",
        "/health",
        "/version",
        "/",
    }
)


def is_public_during_waitlist(path: str, method: str = "GET") -> bool:
    if method.upper() == "OPTIONS":
        return True
    return path in _WAITLIST_PUBLIC_EXACT


def is_request_allowed(request: Any) -> bool:
    """Return the backend-authoritative access decision for this request."""
    if not is_waitlist_mode():
        return True

    path = str(getattr(getattr(request, "url", None), "path", ""))
    method = str(getattr(request, "method", "GET"))
    if is_public_during_waitlist(path, method):
        return True

    # Only product API routes are gated here. Health/root/version remain covered
    # above and non-API infrastructure routes keep their existing behavior.
    if not path.startswith("/api/v1/"):
        return True

    return is_internal_email(request_user_email(request))
