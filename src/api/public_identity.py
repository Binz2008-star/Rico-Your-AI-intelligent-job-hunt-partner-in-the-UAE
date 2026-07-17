"""Validation and capability helpers for public Rico sessions.

Public chat and CV upload flows accept either an authenticated JWT identity or
an anonymous `public:{session_id}` identity. Keep these helpers small and
mostly free of framework dependencies so routers, services, and tests can
share one source of truth.

Guest capability (#1070): a `public:*` session ID is a client-minted string,
so possession of the string alone must NOT grant access to the guest's
temporary profile / OCR / chat context, and must not entitle a login/signup to
merge that guest's data. Ownership is proven by a signed, HttpOnly,
browser-bound capability cookie:

  * The FIRST request that establishes guest state is endorsed — the server
    sets ``rico_guest_proof`` = HMAC(secret, session_id) for that browser.
  * Every later request claiming the same session must present a proof that
    verifies for that exact session ID; a formatted-but-unproved ID against a
    session that already has state is rejected (fail closed).
  * The public→auth merge additionally requires the same proof and consumes a
    one-time claim (see src/services/identity_merge_service.py).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re

logger = logging.getLogger(__name__)

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
        raise ValueError("Email must be a valid address")
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


# ─────────────────────────────────────────────────────────────────────────────
# Guest capability proof (#1070)
# ─────────────────────────────────────────────────────────────────────────────

GUEST_PROOF_COOKIE = "rico_guest_proof"
GUEST_PROOF_MAX_AGE = 7 * 24 * 3600  # short-lived: 7 days, refreshed on use

# Capability check outcomes.
GUEST_VERIFIED = "verified"   # proof cookie matches the claimed session
GUEST_NEW = "new"             # no guest state yet — caller endorses this browser
GUEST_REJECTED = "rejected"   # state exists but ownership is unproved


def _proof_secret() -> bytes:
    """Derive the proof-signing key from JWT_SECRET (domain-separated)."""
    secret = os.getenv("JWT_SECRET", "").strip()
    if not secret:
        # Dev fallback mirrors the auth module's permissiveness outside prod;
        # signing with a fixed dev key keeps the flow testable. Production
        # deployments always set JWT_SECRET.
        secret = "dev-only-insecure-secret"
    return hashlib.sha256(b"rico-guest-proof:" + secret.encode("utf-8")).digest()


def make_guest_proof(session_id: str) -> str:
    """Return the capability proof for a session ID (hex HMAC-SHA256)."""
    if not is_safe_public_session_id(session_id):
        raise ValueError("Session ID must be 8-64 chars: letters, numbers, hyphen, underscore")
    return hmac.new(_proof_secret(), session_id.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_guest_proof(session_id: str | None, proof: str | None) -> bool:
    """Constant-time check that *proof* is the capability for *session_id*."""
    if not session_id or not proof or not is_safe_public_session_id(session_id):
        return False
    try:
        expected = make_guest_proof(session_id)
    except ValueError:
        return False
    return hmac.compare_digest(expected, proof)


def guest_state_exists(public_user_id: str) -> bool:
    """True when ANY guest state already exists for this public identity.

    Checks the canonical DB row and the process-local mirror. Fail-closed: a
    DB error reports True ("state may exist"), so an unproved caller is
    rejected rather than silently endorsed over data we could not verify.
    """
    try:
        from src.rico_memory import RicoMemoryStore

        if RicoMemoryStore().load_profile(public_user_id) is not None:
            return True
    except Exception:
        logger.warning("guest_state_exists: mirror check failed", exc_info=True)
        return True

    try:
        from src.rico_db import RicoDB

        db = RicoDB()
        if not db.available:
            return False
        conn = db.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM rico_users WHERE external_user_id = %s LIMIT 1",
                    (public_user_id,),
                )
                return cur.fetchone() is not None
        finally:
            conn.close()
    except Exception:
        logger.warning("guest_state_exists: db check failed", exc_info=True)
        return True


def check_guest_capability(request, session_id: str) -> str:
    """Classify a public request's claim over *session_id*.

    Returns GUEST_VERIFIED when the browser presents a valid proof cookie for
    this exact session; GUEST_NEW when the session has no state yet (the
    caller should endorse the browser via ``endorse_guest_session``); and
    GUEST_REJECTED when state exists but the claim is unproved — the caller
    must refuse context access (403), never serve another guest's data.
    """
    proof = request.cookies.get(GUEST_PROOF_COOKIE)
    if verify_guest_proof(session_id, proof):
        return GUEST_VERIFIED
    if guest_state_exists(f"public:{session_id}"):
        logger.warning(
            "guest_capability_rejected: unproved claim over existing session (sid_len=%d)",
            len(session_id or ""),
        )
        return GUEST_REJECTED
    return GUEST_NEW


def endorse_guest_session(response, session_id: str) -> None:
    """Bind this browser to *session_id*: set the signed HttpOnly proof cookie."""
    from src.api.auth import _cookie_domain, _cookie_samesite, _cookie_secure

    response.set_cookie(
        key=GUEST_PROOF_COOKIE,
        value=make_guest_proof(session_id),
        max_age=GUEST_PROOF_MAX_AGE,
        httponly=True,
        secure=_cookie_secure(),
        samesite=_cookie_samesite(),
        domain=_cookie_domain(),
        path="/",
    )


def clear_guest_capability(response) -> None:
    """Rotate/clear the guest capability (after a successful public→auth merge)."""
    from src.api.auth import _cookie_domain, _cookie_samesite, _cookie_secure

    response.delete_cookie(
        key=GUEST_PROOF_COOKIE,
        httponly=True,
        secure=_cookie_secure(),
        samesite=_cookie_samesite(),
        domain=_cookie_domain(),
        path="/",
    )
