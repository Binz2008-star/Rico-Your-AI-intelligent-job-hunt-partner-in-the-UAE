"""audit_writer.py

Async, append-only writer for agent_audit_log.

Contracts:
- Never raises on DB errors; logs the error instead (non-blocking audit).
- Always writes a row for every policy decision, ALLOWED or DENIED.
- Caller is responsible for providing all validated fields.
- No side effects beyond the INSERT.
"""
from __future__ import annotations

import hashlib
import logging
import os
from typing import Any

import asyncpg  # type: ignore[import]

logger = logging.getLogger(__name__)

_DATABASE_URL: str = os.environ["DATABASE_URL"]


async def _get_conn() -> asyncpg.Connection:  # pragma: no cover
    """Return a single-use connection. Caller must close it."""
    return await asyncpg.connect(_DATABASE_URL)


def _hash_token(raw_token: str) -> str:
    """SHA-256 of the raw token. Stored for traceability; never the token itself."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


async def write_audit_event(
    *,
    actor_user_id: str,
    agent_id: str,
    card_id: str,
    idempotency_key: str,
    intent_summary: str,
    risk_class: str,
    requested_scopes: list[str],
    policy_decision: str,             # 'ALLOWED' | 'DENIED'
    denial_reason: str | None,
    approval_state: str,              # 'pending' | 'approved' | 'rejected'
    token_issued_at: Any,             # datetime (UTC)
    token_expires_at: Any,            # datetime (UTC)
    effect_summary: dict[str, Any] | None,
    undo_capable: bool,
    raw_token: str,
    _conn: asyncpg.Connection | None = None,  # injectable for tests
) -> None:
    """Insert one row into agent_audit_log.

    On constraint violation (duplicate idempotency_key for ALLOWED),
    the row is silently skipped — idempotent by design.

    On any other DB error, logs at ERROR level and returns without raising,
    so a failing audit write never blocks the gate response.
    """
    token_hash = _hash_token(raw_token)
    close_after = _conn is None
    conn = _conn or await _get_conn()

    try:
        await conn.execute(
            """
            INSERT INTO agent_audit_log (
                actor_user_id, agent_id, card_id, idempotency_key,
                intent_summary, risk_class, requested_scopes,
                policy_decision, denial_reason, approval_state,
                token_issued_at, token_expires_at,
                effect_summary, undo_capable, raw_token_hash
            ) VALUES (
                $1, $2, $3, $4,
                $5, $6, $7::jsonb,
                $8, $9, $10,
                $11, $12,
                $13::jsonb, $14, $15
            )
            ON CONFLICT (actor_user_id, card_id, idempotency_key)
            WHERE policy_decision = 'ALLOWED'
            DO NOTHING
            """,
            actor_user_id,
            agent_id,
            card_id,
            idempotency_key,
            intent_summary,
            risk_class,
            requested_scopes,
            policy_decision,
            denial_reason,
            approval_state,
            token_issued_at,
            token_expires_at,
            effect_summary,
            undo_capable,
            token_hash,
        )
        logger.info(
            "audit_event_written",
            extra={
                "actor_user_id": actor_user_id,
                "card_id": card_id,
                "policy_decision": policy_decision,
                "idempotency_key": idempotency_key,
                "denial_reason": denial_reason,
            },
        )
    except asyncpg.UniqueViolationError:
        logger.info(
            "audit_idempotent_skip",
            extra={"card_id": card_id, "idempotency_key": idempotency_key},
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "audit_write_failed",
            extra={"error": str(exc), "card_id": card_id},
            exc_info=True,
        )
    finally:
        if close_after:
            await conn.close()
