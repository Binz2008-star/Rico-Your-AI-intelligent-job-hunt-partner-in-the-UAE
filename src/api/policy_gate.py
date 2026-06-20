"""policy_gate.py

HMAC-SHA256 token validation + risk-class policy gate.

Contract:
- evaluate_token() is the single entry point.
- Returns PolicyResult(allowed=True) or PolicyResult(allowed=False, reason=...).
- All denial reasons are explicit, machine-readable strings.
- Audit event is written for EVERY decision (allowed or denied).
- No side effects beyond audit write; execution is the caller's responsibility.

Token payload (JSON):
  {
    "user_id":         str,
    "card_id":         str,
    "idempotency_key": str,
    "risk_class":      str,   # e.g. 'safe-read', 'draft-write', 'reversible-write', 'external-commit', 'destructive'
    "requested_scopes": [str],
    "intent_summary":  str,
    "undo_capable":    bool,
    "issued_at":       int,   # unix timestamp
    "expires_at":      int,   # unix timestamp
    "agent_id":        str
  }

HMAC:
  Base64url-encoded HMAC-SHA256(secret_key, base64url(header) + '.' + base64url(payload))
  Token format: base64url(header).base64url(payload).base64url(signature)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

from src.services.audit_writer import write_audit_event

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config (env-only, no hardcoded values)
# ---------------------------------------------------------------------------

def _get_secret() -> bytes:
    secret = os.environ.get("AGENT_TOKEN_SECRET")
    if not secret:
        raise RuntimeError("AGENT_TOKEN_SECRET env var is not set")
    return secret.encode()


# Risk class allowed per permission tier.
# Extend this map as tiers evolve; never relax tiers without a migration + PR.
_TIER_ALLOWED_CLASSES: dict[str, set[str]] = {
    "preview": {"safe-read"},
    "assisted": {"safe-read", "draft-write"},
    "bounded": {"safe-read", "draft-write", "reversible-write"},
    "autonomous": {"safe-read", "draft-write", "reversible-write", "external-commit"},
    # 'destructive' is NEVER allowed by policy tier; requires explicit human action.
}


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class PolicyResult:
    allowed: bool
    reason: str | None = None          # None when allowed
    idempotent_skip: bool = False      # True when duplicate ALLOWED was skipped


@dataclass(frozen=True, slots=True)
class ApprovalToken:
    user_id: str
    card_id: str
    idempotency_key: str
    risk_class: str
    requested_scopes: list[str]
    intent_summary: str
    undo_capable: bool
    issued_at: int
    expires_at: int
    agent_id: str
    raw: str = field(repr=False)       # original token string for audit hash


# ---------------------------------------------------------------------------
# Token parsing + HMAC verification
# ---------------------------------------------------------------------------

def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * (padding % 4))


def _verify_and_parse(raw_token: str, secret: bytes) -> ApprovalToken:
    """Parse and HMAC-verify the token. Raises ValueError on any failure."""
    parts = raw_token.split(".")
    if len(parts) != 3:
        raise ValueError("INVALID_TOKEN_FORMAT")

    header_b64, payload_b64, sig_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode()

    expected_sig = hmac.new(secret, signing_input, hashlib.sha256).digest()
    provided_sig = _b64url_decode(sig_b64)

    if not hmac.compare_digest(expected_sig, provided_sig):
        raise ValueError("SIGNATURE_INVALID")

    try:
        payload: dict[str, Any] = json.loads(_b64url_decode(payload_b64))
    except Exception as exc:
        raise ValueError("PAYLOAD_DECODE_ERROR") from exc

    required = {
        "user_id", "card_id", "idempotency_key", "risk_class",
        "requested_scopes", "intent_summary", "undo_capable",
        "issued_at", "expires_at", "agent_id",
    }
    missing = required - payload.keys()
    if missing:
        raise ValueError(f"PAYLOAD_MISSING_FIELDS:{','.join(sorted(missing))}")

    return ApprovalToken(
        user_id=str(payload["user_id"]),
        card_id=str(payload["card_id"]),
        idempotency_key=str(payload["idempotency_key"]),
        risk_class=str(payload["risk_class"]),
        requested_scopes=list(payload["requested_scopes"]),
        intent_summary=str(payload["intent_summary"]),
        undo_capable=bool(payload["undo_capable"]),
        issued_at=int(payload["issued_at"]),
        expires_at=int(payload["expires_at"]),
        agent_id=str(payload["agent_id"]),
        raw=raw_token,
    )


# ---------------------------------------------------------------------------
# Core gate
# ---------------------------------------------------------------------------

async def evaluate_token(
    *,
    raw_token: str,
    expected_user_id: str,
    expected_card_id: str,
    permission_tier: str,
    seen_idempotency_keys: set[str],   # caller-managed in-process cache; DB is source of truth
    _now: int | None = None,           # injectable for tests
    _audit_conn: Any = None,           # injectable for tests
) -> PolicyResult:
    """Evaluate one approval token against all gate rules.

    Args:
        raw_token:              The full token string from the approval card.
        expected_user_id:       User ID from the authenticated session (not from token).
        expected_card_id:       Card ID from the request context.
        permission_tier:        User's current tier ('preview', 'assisted', 'bounded', 'autonomous').
        seen_idempotency_keys:  In-process set of already-processed keys (best-effort; DB is source of truth).
        _now:                   Unix timestamp override for tests.
        _audit_conn:            asyncpg.Connection override for tests.

    Returns:
        PolicyResult with allowed=True or allowed=False + reason.
    """
    now = _now if _now is not None else int(time.time())
    secret = _get_secret()

    # --- 1. Parse + HMAC verify ---
    try:
        token = _verify_and_parse(raw_token, secret)
    except ValueError as exc:
        reason = str(exc)
        await _audit_denied(
            raw_token=raw_token,
            reason=reason,
            actor_user_id=expected_user_id,
            card_id=expected_card_id,
            idempotency_key="unknown",
            risk_class="unknown",
            agent_id="unknown",
            intent_summary="unknown",
            undo_capable=False,
            issued_at=now,
            expires_at=now,
            requested_scopes=[],
            conn=_audit_conn,
        )
        return PolicyResult(allowed=False, reason=reason)

    # --- 2. TTL check ---
    if now > token.expires_at:
        return await _deny(
            token=token,
            reason="TOKEN_EXPIRED",
            conn=_audit_conn,
        )

    # --- 3. user_id match ---
    if token.user_id != expected_user_id:
        return await _deny(token=token, reason="USER_ID_MISMATCH", conn=_audit_conn)

    # --- 4. card_id match ---
    if token.card_id != expected_card_id:
        return await _deny(token=token, reason="CARD_ID_MISMATCH", conn=_audit_conn)

    # --- 5. risk_class allowed by tier ---
    allowed_classes = _TIER_ALLOWED_CLASSES.get(permission_tier, set())
    if token.risk_class not in allowed_classes:
        return await _deny(
            token=token,
            reason=f"RISK_CLASS_NOT_ALLOWED_FOR_TIER:{permission_tier}",
            conn=_audit_conn,
        )

    # --- 6. idempotency_key duplicate protection (in-process) ---
    if token.idempotency_key in seen_idempotency_keys:
        # Idempotent: return allowed=True without executing again.
        # The DB layer (ON CONFLICT DO NOTHING) is the authoritative guard.
        logger.info(
            "policy_gate_idempotent",
            extra={"idempotency_key": token.idempotency_key, "card_id": token.card_id},
        )
        return PolicyResult(allowed=True, idempotent_skip=True)

    # --- 7. Write ALLOWED audit event ---
    import datetime  # local import to keep top-level imports minimal
    await write_audit_event(
        actor_user_id=token.user_id,
        agent_id=token.agent_id,
        card_id=token.card_id,
        idempotency_key=token.idempotency_key,
        intent_summary=token.intent_summary,
        risk_class=token.risk_class,
        requested_scopes=token.requested_scopes,
        policy_decision="ALLOWED",
        denial_reason=None,
        approval_state="approved",
        token_issued_at=datetime.datetime.fromtimestamp(token.issued_at, tz=datetime.timezone.utc),
        token_expires_at=datetime.datetime.fromtimestamp(token.expires_at, tz=datetime.timezone.utc),
        effect_summary=None,
        undo_capable=token.undo_capable,
        raw_token=token.raw,
        _conn=_audit_conn,
    )

    seen_idempotency_keys.add(token.idempotency_key)

    logger.info(
        "policy_gate_allowed",
        extra={
            "actor_user_id": token.user_id,
            "card_id": token.card_id,
            "risk_class": token.risk_class,
            "idempotency_key": token.idempotency_key,
        },
    )
    return PolicyResult(allowed=True)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _deny(
    *,
    token: ApprovalToken,
    reason: str,
    conn: Any,
) -> PolicyResult:
    import datetime
    await write_audit_event(
        actor_user_id=token.user_id,
        agent_id=token.agent_id,
        card_id=token.card_id,
        idempotency_key=token.idempotency_key,
        intent_summary=token.intent_summary,
        risk_class=token.risk_class,
        requested_scopes=token.requested_scopes,
        policy_decision="DENIED",
        denial_reason=reason,
        approval_state="rejected",
        token_issued_at=datetime.datetime.fromtimestamp(token.issued_at, tz=datetime.timezone.utc),
        token_expires_at=datetime.datetime.fromtimestamp(token.expires_at, tz=datetime.timezone.utc),
        effect_summary=None,
        undo_capable=token.undo_capable,
        raw_token=token.raw,
        _conn=conn,
    )
    logger.warning(
        "policy_gate_denied",
        extra={"card_id": token.card_id, "reason": reason},
    )
    return PolicyResult(allowed=False, reason=reason)


async def _audit_denied(
    *,
    raw_token: str,
    reason: str,
    actor_user_id: str,
    card_id: str,
    idempotency_key: str,
    risk_class: str,
    agent_id: str,
    intent_summary: str,
    undo_capable: bool,
    issued_at: int,
    expires_at: int,
    requested_scopes: list[str],
    conn: Any,
) -> None:
    import datetime
    await write_audit_event(
        actor_user_id=actor_user_id,
        agent_id=agent_id,
        card_id=card_id,
        idempotency_key=idempotency_key,
        intent_summary=intent_summary,
        risk_class=risk_class,
        requested_scopes=requested_scopes,
        policy_decision="DENIED",
        denial_reason=reason,
        approval_state="rejected",
        token_issued_at=datetime.datetime.fromtimestamp(issued_at, tz=datetime.timezone.utc),
        token_expires_at=datetime.datetime.fromtimestamp(expires_at, tz=datetime.timezone.utc),
        effect_summary=None,
        undo_capable=undo_capable,
        raw_token=raw_token,
        _conn=conn,
    )
    logger.warning(
        "policy_gate_denied",
        extra={"card_id": card_id, "reason": reason},
    )
