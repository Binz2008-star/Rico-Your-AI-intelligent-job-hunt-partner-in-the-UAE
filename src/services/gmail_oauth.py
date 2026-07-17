"""
src/services/gmail_oauth.py
Google server-side WEB OAuth flow for the Gmail read-only connector (M0).

Design (docs/integrations/gmail-readonly-connector.md §3):
  * Requests ONLY ``gmail.readonly``. There is no code path in this module (or
    anywhere in the connector) that can request compose/send/modify scopes —
    read-only is structural, not just configured.
  * Rico identity comes exclusively from the JWT-authenticated user; the OAuth
    ``state`` is a signed, short-lived value carrying that identity so the
    Google callback cannot be forged or attached to the wrong user.
  * Refresh tokens are persisted Fernet-encrypted (src/services/token_crypto).
    Access tokens are minted from the refresh token on demand — never stored.
  * Disconnect revokes at Google (best-effort) and tombstones the local row.
  * No token material, auth codes, or state payloads are ever logged.

Env vars (all optional until the feature is enabled):
  GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET / GOOGLE_OAUTH_REDIRECT_URI
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from typing import Any, Dict, Optional, Tuple

from src.repositories import gmail_repo
from src.services.token_crypto import KEY_VERSION, TokenCryptoError, encrypt_token

logger = logging.getLogger(__name__)

# The ONLY scope this connector may request. Read-only by construction.
GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
SCOPES = [GMAIL_READONLY_SCOPE]

GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_REVOKE_URI = "https://oauth2.googleapis.com/revoke"

STATE_TTL_SECONDS = 600  # 10 minutes — the flow is interactive


class GmailOAuthError(RuntimeError):
    """Raised when the OAuth flow cannot proceed (config, state, exchange)."""


# ── Config ────────────────────────────────────────────────────────────────────


def _client_id() -> str:
    return (os.getenv("GOOGLE_OAUTH_CLIENT_ID") or "").strip()


def _client_secret() -> str:
    return (os.getenv("GOOGLE_OAUTH_CLIENT_SECRET") or "").strip()


def _redirect_uri() -> str:
    return (os.getenv("GOOGLE_OAUTH_REDIRECT_URI") or "").strip()


def oauth_configured() -> bool:
    """True when client id/secret/redirect URI are all present."""
    return bool(_client_id() and _client_secret() and _redirect_uri())


def _client_config() -> Dict[str, Any]:
    return {
        "web": {
            "client_id": _client_id(),
            "client_secret": _client_secret(),
            "auth_uri": GOOGLE_AUTH_URI,
            "token_uri": GOOGLE_TOKEN_URI,
            "redirect_uris": [_redirect_uri()],
        }
    }


# ── Signed short-lived state ──────────────────────────────────────────────────
#
# state = base64url(json{"sub": <user_id>, "exp": <unix>, "n": <nonce>}) + "." + hmac
# HMAC-SHA256 keyed with JWT_SECRET. Stateless (no server-side store), expires
# after STATE_TTL_SECONDS, and any byte tampering breaks the signature.


def _state_secret() -> bytes:
    secret = (os.getenv("JWT_SECRET") or "").strip()
    if not secret:
        raise GmailOAuthError("JWT_SECRET is not set — cannot sign OAuth state")
    return secret.encode("utf-8")


def _sign(payload_b64: str) -> str:
    digest = hmac.new(_state_secret(), payload_b64.encode("ascii"), hashlib.sha256)
    return base64.urlsafe_b64encode(digest.digest()).decode("ascii").rstrip("=")


def make_state(user_id: str, ttl_seconds: int = STATE_TTL_SECONDS) -> str:
    """Build a signed, short-lived OAuth state carrying the Rico user identity."""
    if not user_id or not str(user_id).strip():
        raise GmailOAuthError("Cannot sign OAuth state without a user identity")
    payload = {
        "sub": str(user_id).strip(),
        "exp": int(time.time()) + int(ttl_seconds),
        "n": secrets.token_urlsafe(8),
    }
    payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        .decode("ascii")
        .rstrip("=")
    )
    return f"{payload_b64}.{_sign(payload_b64)}"


def verify_state(state: str) -> Optional[str]:
    """Return the user_id carried by a valid, unexpired state; else None.

    Constant-time signature comparison; expired or tampered states are rejected.
    Never logs the state contents.
    """
    if not state or "." not in state:
        return None
    payload_b64, _, signature = state.rpartition(".")
    if not payload_b64 or not signature:
        return None
    try:
        expected = _sign(payload_b64)
    except GmailOAuthError:
        return None
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    if int(payload.get("exp") or 0) < int(time.time()):
        return None
    sub = str(payload.get("sub") or "").strip()
    return sub or None


# ── Authorization URL ─────────────────────────────────────────────────────────


def build_auth_url(user_id: str) -> str:
    """Return the Google authorization URL for the current JWT user.

    ``access_type=offline`` + ``prompt=consent`` so Google issues a refresh
    token; ``include_granted_scopes`` stays false so previously granted broader
    scopes can never silently attach to this credential.
    """
    if not oauth_configured():
        raise GmailOAuthError("Google OAuth is not configured")
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        _client_config(), scopes=SCOPES, redirect_uri=_redirect_uri()
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="false",
        state=make_state(user_id),
    )
    return auth_url


# ── Code exchange + persistence ───────────────────────────────────────────────


def _fetch_provider_email(credentials: Any) -> Optional[str]:
    """Best-effort connected-account email via gmail.users.getProfile.

    Stays within gmail.readonly (profile metadata only). Failure is tolerated —
    the UI simply shows "Connected" without the address.
    """
    try:
        from googleapiclient.discovery import build

        service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        profile = service.users().getProfile(userId="me").execute()
        return (profile or {}).get("emailAddress") or None
    except Exception:
        logger.warning("gmail_oauth_provider_email_lookup_failed", exc_info=True)
        return None


def exchange_code(user_id: str, code: str) -> Dict[str, Any]:
    """Exchange the authorization code and persist the encrypted refresh token.

    Returns the stored connection dict. Raises GmailOAuthError on any failure.
    Never logs or returns raw token material to the caller's response path.
    """
    if not oauth_configured():
        raise GmailOAuthError("Google OAuth is not configured")
    if not code or not str(code).strip():
        raise GmailOAuthError("Missing authorization code")

    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        _client_config(), scopes=SCOPES, redirect_uri=_redirect_uri()
    )
    try:
        flow.fetch_token(code=code)
    except Exception as exc:
        logger.warning("gmail_oauth_token_exchange_failed user_id=%s", user_id)
        gmail_repo.insert_audit_event(
            user_id, "oauth_callback", "error", metadata={"reason": "token_exchange_failed"}
        )
        raise GmailOAuthError(f"Token exchange failed: {type(exc).__name__}") from None

    credentials = flow.credentials
    refresh_token = getattr(credentials, "refresh_token", None)
    if not refresh_token:
        gmail_repo.insert_audit_event(
            user_id, "oauth_callback", "error", metadata={"reason": "no_refresh_token"}
        )
        raise GmailOAuthError(
            "Google did not return a refresh token — re-run consent with prompt=consent"
        )

    granted_scopes = list(getattr(credentials, "scopes", None) or SCOPES)

    try:
        encrypted = encrypt_token(refresh_token)
    except TokenCryptoError as exc:
        gmail_repo.insert_audit_event(
            user_id, "oauth_callback", "error", metadata={"reason": "encryption_unavailable"}
        )
        raise GmailOAuthError(str(exc)) from None

    provider_email = _fetch_provider_email(credentials)

    stored = gmail_repo.upsert_connection(
        user_id=user_id,
        encrypted_refresh_token=encrypted,
        provider_account_email=provider_email,
        scopes=granted_scopes,
        key_version=KEY_VERSION,
    )
    if not stored:
        gmail_repo.insert_audit_event(
            user_id, "oauth_callback", "error", metadata={"reason": "persistence_failed"}
        )
        raise GmailOAuthError("Could not persist the Gmail connection")

    gmail_repo.insert_audit_event(
        user_id,
        "oauth_callback",
        "ok",
        connection_id=stored.get("id"),
        metadata={"scopes": granted_scopes},
    )
    # The caller only ever sees repository fields — strip the ciphertext too.
    return {k: v for k, v in stored.items() if k != "encrypted_refresh_token"}


# ── Credentials for sync ──────────────────────────────────────────────────────


def credentials_from_refresh_token(refresh_token: str) -> Any:
    """Build google Credentials that mint short-lived access tokens on demand."""
    from google.oauth2.credentials import Credentials

    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=GOOGLE_TOKEN_URI,
        client_id=_client_id(),
        client_secret=_client_secret(),
        scopes=SCOPES,
    )


# ── Disconnect / revoke ───────────────────────────────────────────────────────


def revoke_at_google(refresh_token: str) -> bool:
    """Best-effort token revocation at Google. Never raises."""
    try:
        import requests

        resp = requests.post(
            GOOGLE_REVOKE_URI,
            params={"token": refresh_token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception:
        logger.warning("gmail_oauth_revoke_request_failed", exc_info=True)
        return False


def disconnect(user_id: str) -> Tuple[bool, bool]:
    """Disconnect the user's Gmail: revoke at Google, tombstone locally.

    Returns (disconnected, revoked_at_google). Imported application history is
    left intact by design.
    """
    connection = gmail_repo.get_connection(user_id)
    revoked = False
    if connection and connection.get("encrypted_refresh_token"):
        try:
            from src.services.token_crypto import decrypt_token

            refresh_token = decrypt_token(connection["encrypted_refresh_token"])
            revoked = revoke_at_google(refresh_token)
        except TokenCryptoError:
            logger.warning(
                "gmail_oauth_disconnect_decrypt_failed user_id=%s — tombstoning anyway",
                user_id,
            )
        gmail_repo.insert_audit_event(
            user_id,
            "token_revoke",
            "ok" if revoked else "error",
            connection_id=connection.get("id"),
        )

    disconnected = gmail_repo.tombstone_connection(user_id)
    gmail_repo.insert_audit_event(
        user_id,
        "user_disconnected",
        "ok" if disconnected else "noop",
        connection_id=(connection or {}).get("id"),
    )
    return disconnected, revoked
