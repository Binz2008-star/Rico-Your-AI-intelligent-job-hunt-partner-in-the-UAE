"""
src/api/policy_gate.py
Agentic UX approval policy gate — backend foundation.

This module validates approval tokens and writes audit events.
It does NOT execute real external actions (email, apply, etc.) yet.

Flow:
  1. action_created  — intent received
  2. policy_evaluated — risk class + permission tier checked
  3. approval_granted | approval_denied | approval_expired — decision recorded
  4. execution_started / execution_completed — stubbed for future use

Token validation enforces:
  - valid HMAC-SHA256 signature
  - not expired
  - not already used
  - not invalidated
  - user_id match
  - card_id match
  - idempotency_key match
  - risk_class allowed by permission tier
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from src.db import get_db_connection, is_db_available
from src.services.audit_writer import AuditEvent, new_correlation_id, write_event

logger = logging.getLogger(__name__)

_UTC = timezone.utc

# ── Permission tier hierarchy ─────────────────────────────────────────────────
# Maps permission_level → allowed risk classes (inclusive up to that level).
_TIER_ALLOWED_RISKS: Dict[str, frozenset] = {
    "read":         frozenset({"low"}),
    "write":        frozenset({"low", "medium"}),
    "external":     frozenset({"low", "medium", "high"}),
    "irreversible": frozenset({"low", "medium", "high", "critical"}),
}

_DEFAULT_UNDO_WINDOW_SEC = 30  # 30 s undo window for reversible actions


# ── Structured errors ─────────────────────────────────────────────────────────

class PolicyDeniedError(Exception):
    """Raised when the policy gate rejects an action."""
    def __init__(self, reason: str, error_code: str = "POLICY_DENIED") -> None:
        super().__init__(reason)
        self.reason = reason
        self.error_code = error_code


class TokenValidationError(PolicyDeniedError):
    """Raised when the approval token fails validation."""


class IdempotencyConflictError(PolicyDeniedError):
    """Raised when the idempotency key has already been executed."""


# ── Approval request / response types ─────────────────────────────────────────

@dataclass
class ApprovalRequest:
    user_id:          str
    card_id:          str
    idempotency_key:  str
    action_type:      str
    risk_class:       str       # low | medium | high | critical
    permission_level: str       # read | write | external | irreversible
    approval_token_id: str      # UUID stored on the approval card
    hmac_signature:   str       # HMAC-SHA256 provided by the client
    expected_effect:  str       = ""
    target_resource:  Optional[Dict[str, Any]] = None
    before_state:     Optional[Dict[str, Any]] = None
    agent_name:       str       = "rico"
    agent_version:    str       = "1"
    provider:         str       = ""


@dataclass
class PolicyResult:
    allowed:          bool
    policy_decision:  str       # allowed | denied | expired
    reason:           str
    correlation_id:   str
    idempotency_key:  str
    error_code:       Optional[str] = None


# ── HMAC helpers ──────────────────────────────────────────────────────────────

def _hmac_secret() -> bytes:
    secret = os.environ.get("RICO_APPROVAL_HMAC_SECRET", "")
    if not secret:
        raise RuntimeError("RICO_APPROVAL_HMAC_SECRET env var is not set")
    return secret.encode()


def _build_token_payload(req: ApprovalRequest) -> str:
    """Deterministic string that the signature must cover."""
    return json.dumps(
        {
            "approval_token_id": req.approval_token_id,
            "user_id":           req.user_id,
            "card_id":           req.card_id,
            "idempotency_key":   req.idempotency_key,
            "risk_class":        req.risk_class,
            "permission_level":  req.permission_level,
        },
        sort_keys=True,
    )


def compute_hmac(req: ApprovalRequest) -> str:
    """Return the expected HMAC-SHA256 hex digest for an approval request."""
    payload = _build_token_payload(req).encode()
    return hmac.new(_hmac_secret(), payload, hashlib.sha256).hexdigest()


def issue_approval_token(
    user_id: str,
    card_id: str,
    idempotency_key: str,
    risk_class: str,
    permission_level: str,
    ttl_seconds: int = 300,
) -> Dict[str, str]:
    """
    Create and persist a new approval token.
    Returns dict with approval_token_id and hmac_signature for the caller.
    """
    approval_token_id = str(uuid.uuid4())
    expires_at = datetime.now(_UTC) + timedelta(seconds=ttl_seconds)

    dummy_req = ApprovalRequest(
        user_id=user_id,
        card_id=card_id,
        idempotency_key=idempotency_key,
        action_type="",
        risk_class=risk_class,
        permission_level=permission_level,
        approval_token_id=approval_token_id,
        hmac_signature="",
    )
    sig = compute_hmac(dummy_req)

    if is_db_available():
        _db_insert_approval_token(
            approval_token_id=approval_token_id,
            hmac_signature=sig,
            user_id=user_id,
            card_id=card_id,
            idempotency_key=idempotency_key,
            risk_class=risk_class,
            permission_level=permission_level,
            expires_at=expires_at,
        )
    else:
        logger.info(
            "approval_token_issued (no-db) approval_token_id=%s user_id=%s",
            approval_token_id, user_id,
        )

    return {"approval_token_id": approval_token_id, "hmac_signature": sig}


def _db_insert_approval_token(
    *,
    approval_token_id: str,
    hmac_signature: str,
    user_id: str,
    card_id: str,
    idempotency_key: str,
    risk_class: str,
    permission_level: str,
    expires_at: datetime,
) -> None:
    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO agent_approval_tokens
                (approval_token_id, hmac_signature, card_id, user_id,
                 idempotency_key, risk_class, permission_level, expires_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (approval_token_id) DO NOTHING
                """,
                (
                    approval_token_id, hmac_signature, card_id, user_id,
                    idempotency_key, risk_class, permission_level,
                    expires_at.isoformat(),
                ),
            )
        conn.commit()
    except Exception:
        logger.exception("approval_token_insert_failed token_id=%s", approval_token_id)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


# ── Token validation ──────────────────────────────────────────────────────────

def _validate_token(req: ApprovalRequest) -> None:
    """
    Raise TokenValidationError on any validation failure.
    When DB is available, loads the stored token to check expiry/used/invalidated.
    Without DB the caller must provide a valid HMAC (signature check only).
    """
    # 1. HMAC signature
    expected_sig = compute_hmac(req)
    if not hmac.compare_digest(expected_sig, req.hmac_signature):
        raise TokenValidationError("Invalid HMAC signature", "INVALID_SIGNATURE")

    # 2. risk_class allowed by permission_level
    allowed_risks = _TIER_ALLOWED_RISKS.get(req.permission_level, frozenset())
    if req.risk_class not in allowed_risks:
        raise PolicyDeniedError(
            f"risk_class={req.risk_class!r} exceeds permission_level={req.permission_level!r}",
            "RISK_EXCEEDS_TIER",
        )

    # 3. DB checks (expiry, used_at, invalidated, field match)
    if is_db_available():
        _db_validate_token(req)


def _db_validate_token(req: ApprovalRequest) -> None:
    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, card_id, idempotency_key, risk_class,
                       permission_level, expires_at, used_at, invalidated
                FROM agent_approval_tokens
                WHERE approval_token_id = %s
                """,
                (req.approval_token_id,),
            )
            row = cur.fetchone()

        if row is None:
            raise TokenValidationError("Approval token not found", "TOKEN_NOT_FOUND")

        (db_user, db_card, db_idem, db_risk, db_perm,
         expires_at, used_at, invalidated) = row

        if invalidated:
            raise TokenValidationError("Approval token has been invalidated", "TOKEN_INVALIDATED")

        now = datetime.now(_UTC)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=_UTC)
        if now > expires_at:
            raise TokenValidationError("Approval token has expired", "TOKEN_EXPIRED")

        if used_at is not None:
            raise TokenValidationError("Approval token has already been used", "TOKEN_ALREADY_USED")

        if db_user != req.user_id:
            raise TokenValidationError("user_id mismatch", "USER_MISMATCH")

        if db_card != req.card_id:
            raise TokenValidationError("card_id mismatch", "CARD_MISMATCH")

        if db_idem != req.idempotency_key:
            raise TokenValidationError("idempotency_key mismatch", "IDEMPOTENCY_MISMATCH")

    except (TokenValidationError, PolicyDeniedError):
        raise
    except Exception:
        logger.exception("db_validate_token_failed token_id=%s", req.approval_token_id)
    finally:
        conn.close()


def _db_mark_token_used(approval_token_id: str) -> None:
    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE agent_approval_tokens SET used_at = NOW() WHERE approval_token_id = %s",
                (approval_token_id,),
            )
        conn.commit()
    except Exception:
        logger.exception("mark_token_used_failed token_id=%s", approval_token_id)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


# ── Idempotency check ─────────────────────────────────────────────────────────

def _check_idempotency(req: ApprovalRequest) -> Optional[str]:
    """
    Return the existing policy_decision if this idempotency_key was already
    processed for this user+card+action, else None.
    """
    if not is_db_available():
        return None
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT policy_decision FROM agent_audit_events
                WHERE idempotency_key = %s
                  AND user_id = %s
                  AND card_id = %s
                  AND event_type IN ('approval_granted', 'approval_denied', 'approval_expired')
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (req.idempotency_key, req.user_id, req.card_id),
            )
            row = cur.fetchone()
        return row[0] if row else None
    except Exception:
        logger.exception("idempotency_check_failed idempotency_key=%s", req.idempotency_key)
        return None
    finally:
        conn.close()


# ── Policy gate entry point ───────────────────────────────────────────────────

def evaluate(req: ApprovalRequest) -> PolicyResult:
    """
    Validate an approval request, apply policy, and write audit events.

    Does NOT execute real external actions. Callers implement execution
    after receiving PolicyResult(allowed=True).

    Returns PolicyResult — never raises for policy denial (denial is a result,
    not an exception). Raises only for programming errors.
    """
    t0 = time.monotonic()
    correlation_id = new_correlation_id()

    # ── 1. action_created ──────────────────────────────────────────────────────
    write_event(AuditEvent(
        correlation_id=correlation_id,
        card_id=req.card_id,
        idempotency_key=req.idempotency_key,
        user_id=req.user_id,
        agent_name=req.agent_name,
        agent_version=req.agent_version,
        event_type="action_created",
        action_type=req.action_type,
        risk_class=req.risk_class,
        permission_level=req.permission_level,
        target_resource=req.target_resource,
        before_state=req.before_state,
        expected_effect=req.expected_effect,
        provider=req.provider,
    ))

    # ── 2. Idempotency guard ───────────────────────────────────────────────────
    existing_decision = _check_idempotency(req)
    if existing_decision is not None:
        logger.info(
            "policy_gate_idempotent idempotency_key=%s existing_decision=%s",
            req.idempotency_key, existing_decision,
        )
        return PolicyResult(
            allowed=existing_decision == "allowed",
            policy_decision=existing_decision,
            reason="Duplicate idempotency_key — returning cached decision",
            correlation_id=correlation_id,
            idempotency_key=req.idempotency_key,
            error_code="IDEMPOTENCY_REPLAY" if existing_decision != "allowed" else None,
        )

    # ── 3. policy_evaluated ────────────────────────────────────────────────────
    write_event(AuditEvent(
        correlation_id=correlation_id,
        card_id=req.card_id,
        idempotency_key=req.idempotency_key,
        user_id=req.user_id,
        agent_name=req.agent_name,
        agent_version=req.agent_version,
        event_type="policy_evaluated",
        action_type=req.action_type,
        risk_class=req.risk_class,
        permission_level=req.permission_level,
        policy_decision="pending",
        provider=req.provider,
    ))

    # ── 4. Token validation + policy decision ──────────────────────────────────
    latency_ms = int((time.monotonic() - t0) * 1000)
    try:
        _validate_token(req)
    except TokenValidationError as exc:
        _write_decision_event(
            correlation_id=correlation_id,
            req=req,
            event_type="approval_denied",
            policy_decision="denied",
            reason=exc.reason,
            error_code=exc.error_code,
            latency_ms=latency_ms,
        )
        return PolicyResult(
            allowed=False,
            policy_decision="denied",
            reason=exc.reason,
            correlation_id=correlation_id,
            idempotency_key=req.idempotency_key,
            error_code=exc.error_code,
        )
    except PolicyDeniedError as exc:
        _write_decision_event(
            correlation_id=correlation_id,
            req=req,
            event_type="approval_denied",
            policy_decision="denied",
            reason=exc.reason,
            error_code=exc.error_code,
            latency_ms=latency_ms,
        )
        return PolicyResult(
            allowed=False,
            policy_decision="denied",
            reason=exc.reason,
            correlation_id=correlation_id,
            idempotency_key=req.idempotency_key,
            error_code=exc.error_code,
        )

    # ── 5. Approval granted ────────────────────────────────────────────────────
    _db_mark_token_used(req.approval_token_id)

    _write_decision_event(
        correlation_id=correlation_id,
        req=req,
        event_type="approval_granted",
        policy_decision="allowed",
        reason="Token valid; risk class within permitted tier",
        error_code=None,
        latency_ms=latency_ms,
        reversible=True,
        undo_window_sec=_DEFAULT_UNDO_WINDOW_SEC,
    )

    logger.info(
        "policy_gate_allowed correlation_id=%s idempotency_key=%s user_id=%s "
        "action_type=%s risk_class=%s",
        correlation_id, req.idempotency_key, req.user_id,
        req.action_type, req.risk_class,
    )

    return PolicyResult(
        allowed=True,
        policy_decision="allowed",
        reason="Token valid; risk class within permitted tier",
        correlation_id=correlation_id,
        idempotency_key=req.idempotency_key,
    )


def _write_decision_event(
    *,
    correlation_id: str,
    req: ApprovalRequest,
    event_type: str,
    policy_decision: str,
    reason: str,
    error_code: Optional[str],
    latency_ms: int,
    reversible: bool = True,
    undo_window_sec: int = 0,
) -> None:
    write_event(AuditEvent(
        correlation_id=correlation_id,
        card_id=req.card_id,
        idempotency_key=req.idempotency_key,
        user_id=req.user_id,
        agent_name=req.agent_name,
        agent_version=req.agent_version,
        event_type=event_type,
        action_type=req.action_type,
        risk_class=req.risk_class,
        permission_level=req.permission_level,
        policy_decision=policy_decision,
        reason=reason,
        target_resource=req.target_resource,
        before_state=req.before_state,
        expected_effect=req.expected_effect,
        provider=req.provider,
        reversible=reversible,
        undo_window_sec=undo_window_sec,
        latency_ms=latency_ms,
        error_code=error_code,
    ))
