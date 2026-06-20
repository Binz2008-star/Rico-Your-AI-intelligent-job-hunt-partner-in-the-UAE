"""policy_gate.py

HTTP policy gate for semi-autonomous agent actions.
Every agent execution MUST pass through this gate before any side effect.

Enforces:
  1. HMAC-SHA256 signature on approval token
  2. TTL expiry (TOKEN_TTL_SECONDS, default 300)
  3. user_id binding — token must match session user
  4. card_id binding — token must match requested card
  5. idempotency_key deduplication via Redis SETNX
  6. risk_class allowed by user's permission tier

Returns:
  200  { allowed: true, action_id, idempotency_key }
  403  { allowed: false, reason }
  422  { error: 'validation_error', detail }

No execution logic lives here — this gate only decides allow/deny
and writes the audit record. Execution happens downstream.
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
from typing import Any, Optional

import asyncpg  # type: ignore[import]
import redis.asyncio as aioredis  # type: ignore[import]
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from src.services.audit_writer import AuditEventPayload, RiskClass, write_audit_event

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config (env-only, no hardcoded values)
# ---------------------------------------------------------------------------

TOKEN_SECRET: bytes = os.environ["AGENT_APPROVAL_TOKEN_SECRET"].encode()
TOKEN_TTL_SECONDS: int = int(os.environ.get("AGENT_APPROVAL_TOKEN_TTL", "300"))
REDIS_URL: str = os.environ["REDIS_URL"]
IDEMPOTENCY_KEY_TTL: int = int(os.environ.get("IDEMPOTENCY_KEY_TTL", "86400"))  # 24h
AGENT_ID: str = os.environ.get("AGENT_SERVICE_ID", "rico-agent-v1")

# ---------------------------------------------------------------------------
# Permission tier → allowed risk classes
# Spec: docs/agentic-ux-contract.md, Permission Levels section
# ---------------------------------------------------------------------------

PERMISSION_TIER_RISK_CLASSES: dict[str, list[RiskClass]] = {
    "P0": ["safe-read"],
    "P1": ["safe-read", "draft-write"],
    "P2": ["safe-read", "draft-write", "reversible-write"],
    "P3": ["safe-read", "draft-write", "reversible-write", "external-commit"],
    "P4": [],  # P4 = locked, no autonomous execution
}

# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ApprovalToken:
    user_id: str
    card_id: str
    idempotency_key: str
    risk_class: RiskClass
    issued_at: float  # unix timestamp


def _compute_hmac(payload_bytes: bytes) -> str:
    return hmac.new(TOKEN_SECRET, payload_bytes, hashlib.sha256).hexdigest()


def parse_and_validate_token(
    raw_token: str,
    expected_user_id: str,
    expected_card_id: str,
) -> ApprovalToken:
    """Decode, verify HMAC, TTL, user_id, card_id. Raise ValueError on any failure."""
    try:
        header_b64, payload_b64, sig = raw_token.split(".", 2)
    except ValueError:
        raise ValueError("malformed_token")

    import base64
    try:
        payload_json = base64.urlsafe_b64decode(payload_b64 + "==").decode()
        claims: dict[str, Any] = json.loads(payload_json)
    except Exception:
        raise ValueError("malformed_token")

    # 1. HMAC signature check
    signing_input = f"{header_b64}.{payload_b64}".encode()
    expected_sig = _compute_hmac(signing_input)
    if not hmac.compare_digest(expected_sig, sig):
        raise ValueError("invalid_signature")

    # 2. TTL
    issued_at = float(claims.get("iat", 0))
    if time.time() - issued_at > TOKEN_TTL_SECONDS:
        raise ValueError("token_expired")

    # 3. user_id binding
    if claims.get("user_id") != expected_user_id:
        raise ValueError("user_id_mismatch")

    # 4. card_id binding
    if claims.get("card_id") != expected_card_id:
        raise ValueError("card_id_mismatch")

    return ApprovalToken(
        user_id=claims["user_id"],
        card_id=claims["card_id"],
        idempotency_key=claims["idempotency_key"],
        risk_class=claims["risk_class"],
        issued_at=issued_at,
    )


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

async def check_and_lock_idempotency(
    redis: aioredis.Redis,
    idempotency_key: str,
) -> bool:
    """Returns True if key is new (proceed). False if duplicate (already seen)."""
    redis_key = f"agent:idempotency:{idempotency_key}"
    result = await redis.set(redis_key, "1", nx=True, ex=IDEMPOTENCY_KEY_TTL)
    return result is not None  # None = key already existed


# ---------------------------------------------------------------------------
# FastAPI app (mounted as sub-app or standalone)
# ---------------------------------------------------------------------------

app = FastAPI(title="Policy Gate", docs_url=None, redoc_url=None)


class PolicyRequest(BaseModel):
    approval_token: str = Field(..., min_length=10)
    card_id: str = Field(..., min_length=1, max_length=128)
    risk_class: RiskClass
    intent_summary: str = Field(..., min_length=1, max_length=512)
    expected_effect: Optional[str] = Field(None, max_length=512)
    tool_name: Optional[str] = Field(None, max_length=128)
    target_resource: Optional[str] = Field(None, max_length=256)
    undo_capability: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("risk_class")
    @classmethod
    def validate_risk_class(cls, v: str) -> str:
        allowed = {"safe-read", "draft-write", "reversible-write", "external-commit", "destructive"}
        if v not in allowed:
            raise ValueError(f"unknown risk_class: {v}")
        return v


async def _get_user_permission_tier(user_id: str, pool: asyncpg.Pool) -> str:
    """Fetch user's current permission tier from DB. Defaults to P1 if unset."""
    row = await pool.fetchrow(
        "SELECT permission_tier FROM users WHERE id = $1",
        uuid.UUID(user_id),
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_found")
    return row["permission_tier"] or "P1"


@app.post("/api/agent/policy-gate")
async def policy_gate(request: Request, body: PolicyRequest) -> JSONResponse:
    """
    Policy gate for semi-autonomous agent actions.
    Must be called before any agent execution with side effects.
    """
    pool: asyncpg.Pool = request.app.state.db_pool
    redis: aioredis.Redis = request.app.state.redis

    # --- resolve session user ---
    session_user_id: Optional[str] = getattr(request.state, "user_id", None)
    if not session_user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthenticated")

    action_id = uuid.uuid4()
    denial_reason: Optional[str] = None
    decision: str = "denied"
    token: Optional[ApprovalToken] = None

    try:
        # --- 1. Parse & validate token ---
        try:
            token = parse_and_validate_token(
                body.approval_token,
                expected_user_id=session_user_id,
                expected_card_id=body.card_id,
            )
        except ValueError as exc:
            denial_reason = str(exc)
            await _write_policy_audit(
                pool=pool,
                action_id=action_id,
                body=body,
                session_user_id=session_user_id,
                policy_decision="denied",
                denial_reason=denial_reason,
                approval_token_raw=body.approval_token,
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"allowed": False, "reason": denial_reason},
            )

        # --- 2. Idempotency lock ---
        is_new = await check_and_lock_idempotency(redis, token.idempotency_key)
        if not is_new:
            # idempotent — return the same 200 without re-executing
            logger.info(
                "policy_gate: duplicate idempotency_key, returning idempotent response",
                extra={"idempotency_key": token.idempotency_key, "user_id": session_user_id},
            )
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "allowed": True,
                    "idempotent": True,
                    "action_id": str(action_id),
                    "idempotency_key": token.idempotency_key,
                },
            )

        # --- 3. Permission tier check ---
        tier = await _get_user_permission_tier(session_user_id, pool)
        allowed_classes = PERMISSION_TIER_RISK_CLASSES.get(tier, [])
        if body.risk_class not in allowed_classes:
            denial_reason = f"risk_class_not_allowed_for_tier:{tier}"
            await _write_policy_audit(
                pool=pool,
                action_id=action_id,
                body=body,
                session_user_id=session_user_id,
                policy_decision="denied",
                denial_reason=denial_reason,
                approval_token_raw=body.approval_token,
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"allowed": False, "reason": denial_reason},
            )

        # --- All checks passed ---
        decision = "allowed"
        await _write_policy_audit(
            pool=pool,
            action_id=action_id,
            body=body,
            session_user_id=session_user_id,
            policy_decision="allowed",
            denial_reason=None,
            approval_token_raw=body.approval_token,
        )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "allowed": True,
                "idempotent": False,
                "action_id": str(action_id),
                "idempotency_key": token.idempotency_key,
            },
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "policy_gate: unexpected error",
            extra={"action_id": str(action_id), "user_id": session_user_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="policy_gate_error",
        )


async def _write_policy_audit(
    *,
    pool: asyncpg.Pool,
    action_id: uuid.UUID,
    body: PolicyRequest,
    session_user_id: str,
    policy_decision: str,
    denial_reason: Optional[str],
    approval_token_raw: str,
) -> None:
    payload = AuditEventPayload(
        event_type="policy_evaluated",
        action_id=action_id,
        card_id=body.card_id,
        user_id=uuid.UUID(session_user_id),
        agent_id=AGENT_ID,
        risk_class=body.risk_class,  # type: ignore[arg-type]
        intent_summary=body.intent_summary,
        policy_decision=policy_decision,  # type: ignore[arg-type]
        denial_reason=denial_reason,
        idempotency_key=body.idempotency_key if hasattr(body, 'idempotency_key') else "",
        approval_token_raw=approval_token_raw,
        tool_name=body.tool_name,
        target_resource=body.target_resource,
        expected_effect=body.expected_effect,
        undo_capability=body.undo_capability,
        metadata=body.metadata,
    )
    await write_audit_event(pool, payload)
