"""audit_writer.py

Append-only writer for agent_audit_log.
Every policy decision MUST call write_audit_event — allowed or denied.

Rules:
- Never UPDATE or DELETE rows.
- Never swallow exceptions silently; re-raise after logging.
- No PII in intent_summary beyond what is minimally necessary.
- approval_token_hash stores SHA-256 of the raw token, never the token.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Optional

import asyncpg  # type: ignore[import]

logger = logging.getLogger(__name__)

RiskClass = Literal[
    "safe-read",
    "draft-write",
    "reversible-write",
    "external-commit",
    "destructive",
]

PolicyDecision = Literal["allowed", "denied"]


@dataclass(slots=True)
class AuditEventPayload:
    event_type: str
    action_id: uuid.UUID
    card_id: str
    user_id: uuid.UUID
    agent_id: str
    risk_class: RiskClass
    intent_summary: str
    policy_decision: PolicyDecision
    idempotency_key: str
    denial_reason: Optional[str] = None
    approval_token_raw: Optional[str] = None  # will be hashed before storage
    tool_name: Optional[str] = None
    target_resource: Optional[str] = None
    expected_effect: Optional[str] = None
    actual_effect: Optional[str] = None
    undo_capability: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


def _hash_token(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    return hashlib.sha256(raw.encode()).hexdigest()


async def write_audit_event(
    pool: asyncpg.Pool,
    payload: AuditEventPayload,
) -> None:
    """Append one audit event row. Never raises silently."""
    token_hash = _hash_token(payload.approval_token_raw)
    intent = payload.intent_summary[:512]  # enforce field cap

    sql = """
        INSERT INTO agent_audit_log (
            event_type, action_id, card_id, user_id, agent_id,
            risk_class, intent_summary, policy_decision, denial_reason,
            idempotency_key, approval_token_hash, tool_name,
            target_resource, expected_effect, actual_effect,
            undo_capability, metadata, created_at
        ) VALUES (
            $1, $2, $3, $4, $5,
            $6, $7, $8, $9,
            $10, $11, $12,
            $13, $14, $15,
            $16, $17, $18
        )
    """

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                sql,
                payload.event_type,
                payload.action_id,
                payload.card_id,
                payload.user_id,
                payload.agent_id,
                payload.risk_class,
                intent,
                payload.policy_decision,
                payload.denial_reason,
                payload.idempotency_key,
                token_hash,
                payload.tool_name,
                payload.target_resource,
                payload.expected_effect,
                payload.actual_effect,
                payload.undo_capability,
                payload.metadata,
                datetime.now(timezone.utc),
            )
    except Exception:
        logger.exception(
            "audit_writer: failed to write audit event",
            extra={
                "action_id": str(payload.action_id),
                "card_id": payload.card_id,
                "user_id": str(payload.user_id),
                "policy_decision": payload.policy_decision,
            },
        )
        raise

    logger.info(
        "audit_writer: event written",
        extra={
            "event_type": payload.event_type,
            "action_id": str(payload.action_id),
            "policy_decision": payload.policy_decision,
            "risk_class": payload.risk_class,
        },
    )
