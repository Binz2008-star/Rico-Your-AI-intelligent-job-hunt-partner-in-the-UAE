"""Validation helpers for public Rico sessions.

Public chat and CV upload flows accept either an authenticated JWT identity or
an anonymous `public:{session_id}` identity. Keep these helpers small and free
of framework dependencies so routers, services, and tests can share one source
of truth.
"""
from __future__ import annotations

import re

_SAFE_SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_PUBLIC_USER_ID_RE = re.compile(r"^public:[A-Za-z0-9_-]{8,64}$")
_EMAIL_RE = re.compile(
    r"^(?=.{3,254}$)[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)


def normalize_public_email(value: str | None) -> str | None:
    """Normalize and validate an email used by unauthenticated public chat.

    The previous minimal check only required an `@`, which accepted malformed
    identifiers such as `x@y`, `a@`, or values with whitespace. This validator is
    intentionally conservative while still avoiding an external dependency.
    """
    if value is None:
        return None

    email = value.strip().lower()
    if not email:
        return None
    if not _EMAIL_RE.fullmatch(email):
        raise ValueError("Email must be a valid address")
    return email


def is_safe_public_session_id(value: str | None) -> bool:
    """Return True when a public session ID is safe for user_id composition."""
    return bool(value and _SAFE_SESSION_RE.fullmatch(value))


def make_public_user_id(session_id: str) -> str:
    """Create a canonical public user ID from a validated session ID."""
    if not is_safe_public_session_id(session_id):
        raise ValueError("Session ID must be 8-64 chars: letters, numbers, hyphen, underscore")
    return f"public:{session_id}"


def is_valid_public_user_id(value: str | None) -> bool:
    """Validate canonical public user IDs used by CV upload/profile preview."""
    return bool(value and _PUBLIC_USER_ID_RE.fullmatch(value))
