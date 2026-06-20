"""
src/services/audit_writer.py
Append-only writer for agent_audit_events.

Rules:
  - Only INSERT. Never UPDATE or DELETE.
  - All lifecycle steps for one user action share the same correlation_id.
  - When DB is unavailable, events are emitted as structured log lines.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.db import get_db_connection, is_db_available

logger = logging.getLogger(__name__)

_UTC = timezone.utc

# Valid event_type values (open-ended in DB but validated on write)
VALID_EVENT_TYPES = frozenset({
    "action_created",
    "policy_evaluated",
    "approval_requested",
    "approval_granted",
    "approval_denied",
    "approval_expired",
    "execution_started",
    "execution_completed",
    "execution_failed",
    "undo_requested",
    "undo_completed",
})

VALID_RISK_CLASSES = frozenset({"low", "medium", "high", "critical"})
VALID_PERMISSION_LEVELS = frozenset({"read", "write", "external", "irreversible"})
VALID_POLICY_DECISIONS = frozenset({"allowed", "denied", "pending", "expired", ""})


@dataclass
class AuditEvent:
    """Typed representation of a single audit event row."""
    correlation_id:   str
    idempotency_key:  str
    user_id:          str
    event_type:       str
    action_type:      str                        = ""
    card_id:          str                        = ""
    agent_name:       str                        = "rico"
    agent_version:    str                        = "1"
    risk_class:       str                        = ""
    permission_level: str                        = ""
    policy_decision:  str                        = ""
    reason:           str                        = ""
    before_state:     Optional[Dict[str, Any]]   = None
    after_state:      Optional[Dict[str, Any]]   = None
    target_resource:  Optional[Dict[str, Any]]   = None
    expected_effect:  str                        = ""
    actual_effect:    Optional[Dict[str, Any]]   = None
    provider:         str                        = ""
    external_systems: List[str]                  = field(default_factory=list)
    reversible:       bool                       = True
    undo_window_sec:  int                        = 0
    latency_ms:       int                        = 0
    error_code:       Optional[str]              = None
    error_message:    Optional[str]              = None
    created_at:       datetime                   = field(default_factory=lambda: datetime.now(_UTC))


class AuditWriteError(Exception):
    """Raised when an audit INSERT fails and the caller must know."""


def new_correlation_id() -> str:
    return str(uuid.uuid4())


def write_event(event: AuditEvent) -> None:
    """
    INSERT one event row into agent_audit_events.
    Never updates an existing row — append-only by design.
    Falls back to structured logging when DB is unavailable.
    """
    if event.event_type not in VALID_EVENT_TYPES:
        raise ValueError(f"Unknown event_type: {event.event_type!r}")

    if is_db_available():
        _db_insert(event)
    else:
        _log_event(event)


def _db_insert(event: AuditEvent) -> None:
    t0 = time.monotonic()
    conn = get_db_connection()
    if not conn:
        _log_event(event)
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO agent_audit_events (
                    correlation_id, card_id, idempotency_key, user_id,
                    agent_name, agent_version,
                    event_type, action_type,
                    risk_class, permission_level, policy_decision, reason,
                    before_state, after_state, target_resource,
                    expected_effect, actual_effect,
                    provider, external_systems,
                    reversible, undo_window_sec, latency_ms,
                    error_code, error_message, created_at
                ) VALUES (
                    %s,%s,%s,%s,
                    %s,%s,
                    %s,%s,
                    %s,%s,%s,%s,
                    %s,%s,%s,
                    %s,%s,
                    %s,%s,
                    %s,%s,%s,
                    %s,%s,%s
                )
                """,
                (
                    event.correlation_id,
                    event.card_id,
                    event.idempotency_key,
                    event.user_id,
                    event.agent_name,
                    event.agent_version,
                    event.event_type,
                    event.action_type,
                    event.risk_class,
                    event.permission_level,
                    event.policy_decision,
                    event.reason,
                    json.dumps(event.before_state) if event.before_state is not None else None,
                    json.dumps(event.after_state)  if event.after_state  is not None else None,
                    json.dumps(event.target_resource) if event.target_resource is not None else None,
                    event.expected_effect,
                    json.dumps(event.actual_effect) if event.actual_effect is not None else None,
                    event.provider,
                    event.external_systems,
                    event.reversible,
                    event.undo_window_sec,
                    event.latency_ms,
                    event.error_code,
                    event.error_message,
                    event.created_at.isoformat(),
                ),
            )
        conn.commit()
        elapsed = int((time.monotonic() - t0) * 1000)
        logger.info(
            "audit_event_written event_type=%s correlation_id=%s idempotency_key=%s user_id=%s latency_ms=%d",
            event.event_type, event.correlation_id, event.idempotency_key, event.user_id, elapsed,
        )
    except Exception:
        logger.exception(
            "audit_event_write_failed event_type=%s correlation_id=%s",
            event.event_type, event.correlation_id,
        )
        try:
            conn.rollback()
        except Exception:
            pass
        raise AuditWriteError(f"Failed to write audit event {event.event_type!r}") from None
    finally:
        conn.close()


def _log_event(event: AuditEvent) -> None:
    logger.info(
        "audit_event event_type=%s correlation_id=%s idempotency_key=%s "
        "user_id=%s action_type=%s policy_decision=%s risk_class=%s reason=%r",
        event.event_type,
        event.correlation_id,
        event.idempotency_key,
        event.user_id,
        event.action_type,
        event.policy_decision,
        event.risk_class,
        event.reason,
    )
