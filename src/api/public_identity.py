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
# Guest capability (#1070) — server-minted identity, versioned signed token
# ─────────────────────────────────────────────────────────────────────────────

GUEST_PROOF_COOKIE = "rico_guest_proof"
GUEST_CAPABILITY_VERSION = 1
GUEST_CAPABILITY_PURPOSE = "guest-session"
GUEST_CAPABILITY_TTL_SECONDS = 7 * 24 * 3600  # enforced from the SIGNED payload

# Error codes surfaced by the HTTP layer. Each failure mode is distinct and
# observable (#1070 correction 5):
#   guest_capability_invalid     — tampered/expired/wrong-version/wrong-purpose
#                                  token (403; the bad cookie is cleared)
#   guest_capability_unavailable — GUEST_CAPABILITY_SECRET missing in
#                                  production (503; fail closed, nothing minted)
GUEST_CAPABILITY_INVALID = "guest_capability_invalid"
GUEST_CAPABILITY_UNAVAILABLE = "guest_capability_unavailable"


class InvalidGuestCapability(ValueError):
    """The presented capability token failed validation (fail closed).

    Carries a FIXED ``reason_code`` for logging/observability. Neither the
    code nor the message ever contains token material, SIDs, nonces, or
    signatures — log ``reason_code``, never the free-form exception.
    """

    def __init__(self, reason_code: str):
        self.reason_code = reason_code
        super().__init__(reason_code)


class GuestCapabilityUnavailable(RuntimeError):
    """Guest capabilities cannot be minted/validated (missing prod secret)."""


def _capability_secret() -> bytes:
    """Return the dedicated guest-capability signing key.

    GUEST_CAPABILITY_SECRET is its own secret — deliberately NOT derived from
    JWT_SECRET (#1070 correction 3), so rotating one never silently weakens or
    invalidates the other.

    Rotation/deployment: set GUEST_CAPABILITY_SECRET on Render before deploy.
    Rotating the value invalidates every outstanding guest capability — active
    guests transparently restart as fresh anonymous sessions on their next
    request (one 403 + cookie clear, then a new mint). Rotate by replacing the
    value and redeploying; no schema or data change is involved.

    Missing in production → GuestCapabilityUnavailable (fail closed: no mint,
    no validation, guest surfaces return 503). Outside production a fixed dev
    key keeps local/CI flows testable.
    """
    secret = os.getenv("GUEST_CAPABILITY_SECRET", "").strip()
    if secret:
        return hashlib.sha256(b"rico-guest-capability:" + secret.encode("utf-8")).digest()
    from src.api.auth import _is_production

    if _is_production():
        raise GuestCapabilityUnavailable(
            "GUEST_CAPABILITY_SECRET is not set — guest capabilities are disabled"
        )
    return hashlib.sha256(b"rico-guest-capability:dev-only-insecure-secret").digest()


def _b64url_encode(data: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    import base64

    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(payload_b64: str) -> str:
    return _b64url_encode(
        hmac.new(_capability_secret(), payload_b64.encode("ascii"), hashlib.sha256).digest()
    )


def mint_guest_capability() -> tuple[str, str]:
    """Mint a NEW server-authoritative guest identity and its capability token.

    The backend mints the SID (#1070 correction 1) — a client-suggested value
    never becomes the ownership identity. Returns ``(sid, token)`` where token
    is ``base64url(json_payload) . base64url(hmac_sha256(payload))`` and the
    signed payload carries version, purpose, sid, issued_at, expires_at, and a
    cryptographic nonce (correction 2).
    """
    import json as _json
    import secrets as _secrets
    import time as _time

    sid = "g-" + _secrets.token_urlsafe(24).replace("=", "")[:40]
    now = int(_time.time())
    payload = {
        "v": GUEST_CAPABILITY_VERSION,
        "purpose": GUEST_CAPABILITY_PURPOSE,
        "sid": sid,
        "iat": now,
        "exp": now + GUEST_CAPABILITY_TTL_SECONDS,
        "nonce": _secrets.token_urlsafe(12),
    }
    payload_b64 = _b64url_encode(_json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return sid, f"{payload_b64}.{_sign(payload_b64)}"


def make_guest_capability_for_sid(sid: str) -> str:
    """Mint a capability token for a KNOWN sid — test/fixture helper only.

    Production code paths must use mint_guest_capability(); this exists so
    suites exercising upload/chat mechanics can pin a deterministic identity.
    """
    import json as _json
    import secrets as _secrets
    import time as _time

    if not is_safe_public_session_id(sid):
        raise ValueError("Session ID must be 8-64 chars: letters, numbers, hyphen, underscore")
    now = int(_time.time())
    payload = {
        "v": GUEST_CAPABILITY_VERSION,
        "purpose": GUEST_CAPABILITY_PURPOSE,
        "sid": sid,
        "iat": now,
        "exp": now + GUEST_CAPABILITY_TTL_SECONDS,
        "nonce": _secrets.token_urlsafe(12),
    }
    payload_b64 = _b64url_encode(_json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{payload_b64}.{_sign(payload_b64)}"


def parse_guest_capability(token: str | None) -> str:
    """Validate a capability token and return its server-minted sid.

    EVERY field is enforced from the signed payload (#1070 correction 2):
    signature (constant-time), version, purpose, sid shape, issued_at sanity,
    expiry (independent of the cookie's Max-Age), and nonce presence.
    Raises InvalidGuestCapability on any failure — never a partial trust.
    """
    import json as _json
    import time as _time

    if not token or "." not in token:
        raise InvalidGuestCapability("malformed")
    payload_b64, _, sig = token.partition(".")
    try:
        expected_sig = _sign(payload_b64)
    except GuestCapabilityUnavailable:
        raise
    if not hmac.compare_digest(expected_sig, sig):
        raise InvalidGuestCapability("signature")
    try:
        payload = _json.loads(_b64url_decode(payload_b64))
    except Exception as exc:
        raise InvalidGuestCapability("payload_undecodable") from exc
    if not isinstance(payload, dict):
        raise InvalidGuestCapability("payload_malformed")
    if payload.get("v") != GUEST_CAPABILITY_VERSION:
        raise InvalidGuestCapability("version")
    if payload.get("purpose") != GUEST_CAPABILITY_PURPOSE:
        raise InvalidGuestCapability("purpose")
    if not payload.get("nonce"):
        raise InvalidGuestCapability("nonce")
    sid = payload.get("sid")
    if not isinstance(sid, str) or not is_safe_public_session_id(sid):
        raise InvalidGuestCapability("sid")
    now = int(_time.time())
    iat = payload.get("iat")
    exp = payload.get("exp")
    if not isinstance(iat, int) or not isinstance(exp, int) or iat > now + 60:
        raise InvalidGuestCapability("timestamps")
    if exp <= now:
        raise InvalidGuestCapability("expired")
    return sid


def resolve_guest_identity(request, response) -> str:
    """Resolve the server-authoritative guest sid for an unauthenticated request.

    * Valid capability cookie → that token's sid IS the identity.
    * No cookie → mint a fresh server identity and endorse this browser
      (Set-Cookie on *response*). This is also the one-time legacy migration
      path for pre-capability guests: their client-minted localStorage id
      carries zero authorization meaning and is never adopted (correction 1);
      the migration is logged, not signalled, so session-id probing gains no
      state oracle.
    * Present-but-invalid cookie → InvalidGuestCapability. The caller returns
      403 guest_capability_invalid and clears the bad cookie — observable,
      fail closed, self-healing on the next request (correction 5).
    * Missing production secret → GuestCapabilityUnavailable (caller → 503).
    """
    token = request.cookies.get(GUEST_PROOF_COOKIE)
    if token:
        sid = parse_guest_capability(token)  # raises on any validation failure
        return sid
    sid, new_token = mint_guest_capability()
    _set_capability_cookie(response, new_token)
    logger.info("guest_capability_minted sid_prefix=%s", sid[:6])
    return sid


def _set_capability_cookie(response, token: str) -> None:
    from src.api.auth import _cookie_domain, _cookie_samesite, _cookie_secure

    response.set_cookie(
        key=GUEST_PROOF_COOKIE,
        value=token,
        max_age=GUEST_CAPABILITY_TTL_SECONDS,
        httponly=True,
        secure=_cookie_secure(),
        samesite=_cookie_samesite(),
        domain=_cookie_domain(),
        path="/",
    )


def clear_guest_capability(response) -> None:
    """Clear the guest capability cookie (invalid token, or consumed by merge)."""
    from src.api.auth import _cookie_domain, _cookie_samesite, _cookie_secure

    response.delete_cookie(
        key=GUEST_PROOF_COOKIE,
        httponly=True,
        secure=_cookie_secure(),
        samesite=_cookie_samesite(),
        domain=_cookie_domain(),
        path="/",
    )
