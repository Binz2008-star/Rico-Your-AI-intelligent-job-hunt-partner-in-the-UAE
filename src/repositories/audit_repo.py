"""
src/repositories/audit_repo.py
Action audit log persistence and idempotency checking.

Two storage paths:
  1. DB preferred: writes to action_audit_log table.
  2. In-memory fallback: TTL-based dict when DB is unavailable.

Idempotency scope: IDEMPOTENT_ACTION_TYPES (apply/skip/save/block/not_relevant).
  Same action_id submitted twice within _DEDUP_TTL_S → second call is rejected.
  action_id is deterministic (MD5 of user_id:action:job_key, computed by
  agent_runtime.handle_action), so repeating the same action on the same job
  always produces the same id.
"""
from __future__ import annotations

import logging
import time
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.db import get_db_connection, is_db_available
from src.models.action_log import ActionLog

logger = logging.getLogger(__name__)

_UTC = timezone.utc

# ── In-process idempotency cache (TTL-based) ──────────────────────────────────
# action_id -> (unix_timestamp_of_execution, result_status)
_DEDUP_CACHE: Dict[str, Tuple[float, str]] = {}
_DEDUP_TTL_S = 3600   # 1 hour
_DEDUP_LOCK  = threading.Lock()

# Only these action types are subject to idempotency enforcement
IDEMPOTENT_ACTION_TYPES = frozenset({"apply", "skip", "save", "block", "not_relevant"})


# ── Idempotency check ─────────────────────────────────────────────────────────

def is_duplicate(action_id: str) -> bool:
    """
    Return True if this action_id was already executed within the TTL window.
    Checks DB first, then in-memory cache.
    """
    if is_db_available():
        return _db_check_duplicate(action_id)
    return _mem_check_duplicate(action_id)


def _db_check_duplicate(action_id: str) -> bool:
    conn = get_db_connection()
    if not conn:
        return _mem_check_duplicate(action_id)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM action_audit_log
                WHERE action_id = %s
                  AND result_status IN ('success', 'duplicate')
                  AND timestamp > NOW() - INTERVAL '1 hour'
                LIMIT 1
                """,
                (action_id,),
            )
            return cur.fetchone() is not None
    except Exception:
        logger.exception("audit_repo_dedup_check_failed action_id=%s", action_id)
        return _mem_check_duplicate(action_id)
    finally:
        conn.close()


def _mem_check_duplicate(action_id: str) -> bool:
    now = time.monotonic()
    with _DEDUP_LOCK:
        entry = _DEDUP_CACHE.get(action_id)
        if entry is None:
            return False
        ts, status = entry
        if now - ts > _DEDUP_TTL_S:
            del _DEDUP_CACHE[action_id]
            return False
        return status in ("success", "duplicate")


# ── Audit log write ───────────────────────────────────────────────────────────

def log_action(log: ActionLog) -> None:
    """
    Persist one action execution record.
    Also seeds the in-memory dedup cache for processes without DB access.
    """
    _mem_seed(log)

    if is_db_available():
        _db_write(log)
    else:
        logger.info(
            "action_audit action_id=%s type=%s user=%s status=%s duration_ms=%d failure=%r",
            log.get("action_id", ""),
            log.get("action_type", ""),
            log.get("user_email", ""),
            log.get("result_status", ""),
            log.get("duration_ms", 0),
            log.get("failure_reason"),
        )


def _db_write(log: ActionLog) -> None:
    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO action_audit_log (
                    action_id, action_type, user_email,
                    job_id, job_title, job_company,
                    timestamp, result_status, result_message,
                    duration_ms, failure_reason
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    log.get("action_id", ""),
                    log.get("action_type", ""),
                    log.get("user_email", ""),
                    log.get("job_id"),
                    log.get("job_title"),
                    log.get("job_company"),
                    log.get("timestamp", datetime.now(_UTC).isoformat()),
                    log.get("result_status", ""),
                    log.get("result_message", ""),
                    log.get("duration_ms", 0),
                    log.get("failure_reason"),
                ),
            )
        conn.commit()
        logger.info(
            "action_audit action_id=%s type=%s user=%s status=%s duration_ms=%d",
            log.get("action_id", ""),
            log.get("action_type", ""),
            log.get("user_email", ""),
            log.get("result_status", ""),
            log.get("duration_ms", 0),
        )
    except Exception:
        logger.exception("audit_repo_write_failed action_id=%s", log.get("action_id"))
    finally:
        conn.close()


def _mem_seed(log: ActionLog) -> None:
    action_id = log.get("action_id", "")
    if not action_id:
        return
    with _DEDUP_LOCK:
        _DEDUP_CACHE[action_id] = (time.monotonic(), log.get("result_status", ""))


# ── General audit log write (for profile questions, etc.) ───────────────────

def write_audit_log(
    user_id: str,
    event_type: str,
    data: Dict[str, Any],
    timestamp: Optional[datetime] = None,
) -> None:
    """
    Write a general audit log entry (e.g., profile questions).

    This is a compatibility wrapper for logging events that don't fit
    the action_log schema (like profile_question events). Migration 030 owns
    the event_type/data columns; request handling never mutates the schema.
    """
    if timestamp is None:
        timestamp = datetime.now(_UTC)

    if is_db_available():
        conn = get_db_connection()
        if not conn:
            return
        try:
            with conn.cursor() as cur:
                import json
                cur.execute(
                    """
                    INSERT INTO action_audit_log (
                        action_id, action_type, user_email,
                        timestamp, event_type, data, result_status, duration_ms
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid.uuid4()),  # action_id (unique per audit event)
                        "audit",  # action_type
                        user_id,  # user_email
                        timestamp.isoformat(),
                        event_type,
                        json.dumps(data),
                        "success",
                        0,
                    ),
                )
                conn.commit()
                logger.info(
                    "audit_log_written user=%s event_type=%s",
                    user_id, event_type,
                )
        except Exception:
            logger.exception("audit_log_write_failed user=%s event_type=%s", user_id, event_type)
        finally:
            conn.close()
    else:
        logger.info(
            "audit_log user=%s event_type=%s data=%s",
            user_id, event_type, data,
        )


# ── Recent log query (for inspection / tests) ─────────────────────────────────

def get_recent(limit: int = 20, user_id: str | None = None) -> list:
    """Return recent audit log entries from DB, or [] when DB is unavailable.

    When *user_id* is provided only rows for that user are returned, which is
    far more efficient than fetching global rows and filtering in Python.
    """
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            if user_id:
                cur.execute(
                    """
                    SELECT action_id, action_type, user_email, job_title,
                           timestamp, result_status, duration_ms, failure_reason,
                           event_type, data
                    FROM action_audit_log
                    WHERE user_email = %s
                    ORDER BY timestamp DESC
                    LIMIT %s
                    """,
                    (user_id, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT action_id, action_type, user_email, job_title,
                           timestamp, result_status, duration_ms, failure_reason,
                           event_type, data
                    FROM action_audit_log
                    ORDER BY timestamp DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
            rows = cur.fetchall()
        return [
            {
                "action_id": r[0],
                "action_type": r[1],
                "user_email": r[2],
                "job_title": r[3],
                "timestamp": r[4].isoformat() if r[4] else None,
                "result_status": r[5],
                "duration_ms": r[6],
                "failure_reason": r[7],
                "event_type": r[8],
                "data": r[9] or {},
            }
            for r in rows
        ]
    except Exception:
        logger.exception("audit_repo_get_recent_failed")
        return []
    finally:
        conn.close()


# ── Learning signal logging ─────────────────────────────────────────────────────

def log_learning_signal(
    canonical_user_id: str,
    signal_type: str,
    signal_value: str,
    signal_weight: float,
    source: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log a learning signal event.

    Learning signals are behavioral cues extracted from user actions.
    """
    if is_db_available():
        _db_write_learning_signal(canonical_user_id, signal_type, signal_value, signal_weight, source, metadata)
    else:
        logger.info(
            "learning_signal user=%s type=%s value=%s weight=%.2f source=%s",
            canonical_user_id, signal_type, signal_value, signal_weight, source,
        )


def _db_write_learning_signal(
    canonical_user_id: str,
    signal_type: str,
    signal_value: str,
    signal_weight: float,
    source: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Write learning signal to database."""
    conn = get_db_connection()
    if not conn:
        return

    try:
        with conn.cursor() as cur:
            # Insert signal (table created by migration 031_audit_helper_tables)
            import json
            cur.execute(
                """
                INSERT INTO learning_signals_audit
                (canonical_user_id, signal_type, signal_value, signal_weight, source, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    canonical_user_id,
                    signal_type,
                    signal_value,
                    signal_weight,
                    source,
                    json.dumps(metadata) if metadata else None,
                ),
            )
            conn.commit()

        logger.info(
            "learning_signal_logged user=%s type=%s value=%s weight=%.2f",
            canonical_user_id, signal_type, signal_value, signal_weight,
        )
    except Exception:
        logger.exception("learning_signal_db_write_failed user=%s type=%s", canonical_user_id, signal_type)
    finally:
        conn.close()


# ── Profile hydration logging ───────────────────────────────────────────────────

def log_profile_hydration(
    canonical_user_id: str,
    hydration_sources: List[str],
    completeness_before: float,
    completeness_after: float,
) -> None:
    """
    Log a profile hydration event.

    Tracks when and how user profiles are enriched from various sources.
    """
    if is_db_available():
        _db_write_profile_hydration(canonical_user_id, hydration_sources, completeness_before, completeness_after)
    else:
        logger.info(
            "profile_hydration user=%s sources=%s completeness_before=%.2f completeness_after=%.2f",
            canonical_user_id, hydration_sources, completeness_before, completeness_after,
        )


def _db_write_profile_hydration(
    canonical_user_id: str,
    hydration_sources: List[str],
    completeness_before: float,
    completeness_after: float,
) -> None:
    """Write profile hydration event to database."""
    conn = get_db_connection()
    if not conn:
        return

    try:
        with conn.cursor() as cur:
            # Insert hydration event (table created by migration 031_audit_helper_tables)
            cur.execute(
                """
                INSERT INTO profile_hydration_audit
                (canonical_user_id, hydration_sources, completeness_before, completeness_after)
                VALUES (%s, %s, %s, %s)
                """,
                (canonical_user_id, hydration_sources, completeness_before, completeness_after),
            )
            conn.commit()

        logger.info(
            "profile_hydration_logged user=%s sources=%s completeness_before=%.2f completeness_after=%.2f",
            canonical_user_id, hydration_sources, completeness_before, completeness_after,
        )
    except Exception:
        logger.exception("profile_hydration_db_write_failed user=%s", canonical_user_id)
    finally:
        conn.close()


# ── Permission check logging ────────────────────────────────────────────────────

def log_permission_check(
    canonical_user_id: str,
    intent: str,
    permission_level: str,
    allowed: bool,
    requires_confirmation: bool = False,
) -> None:
    """
    Log a permission check event.

    Tracks when high-impact actions are checked for permissions.
    """
    if is_db_available():
        _db_write_permission_check(canonical_user_id, intent, permission_level, allowed, requires_confirmation)
    else:
        logger.info(
            "permission_check user=%s intent=%s level=%s allowed=%s requires_confirmation=%s",
            canonical_user_id, intent, permission_level, allowed, requires_confirmation,
        )


def _db_write_permission_check(
    canonical_user_id: str,
    intent: str,
    permission_level: str,
    allowed: bool,
    requires_confirmation: bool,
) -> None:
    """Write permission check to database."""
    conn = get_db_connection()
    if not conn:
        return

    try:
        with conn.cursor() as cur:
            # Insert permission check (table created by migration 031_audit_helper_tables)
            cur.execute(
                """
                INSERT INTO permission_check_audit
                (canonical_user_id, intent, permission_level, allowed, requires_confirmation)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (canonical_user_id, intent, permission_level, allowed, requires_confirmation),
            )
            conn.commit()

        logger.info(
            "permission_check_logged user=%s intent=%s level=%s allowed=%s",
            canonical_user_id, intent, permission_level, allowed,
        )
    except Exception:
        logger.exception("permission_check_db_write_failed user=%s intent=%s", canonical_user_id, intent)
    finally:
        conn.close()


# ── Identity audit stubs ────────────────────────────────────────────────────────
# These are referenced by src/agent/identity/resolver.py.
# No DB table yet — events are logged only.

def log_identity_resolution(
    canonical_user_id: str,
    identity_source: str,
    confidence: float,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Log an identity resolution event."""
    logger.info(
        "identity_resolved canonical=%s source=%s confidence=%.2f",
        canonical_user_id, identity_source, confidence,
    )


def log_identity_merge(
    from_user_id: str,
    to_user_id: str,
    merge_reason: str = "",
) -> None:
    """Log an identity merge event."""
    logger.info(
        "identity_merged from=%s to=%s reason=%s",
        from_user_id, to_user_id, merge_reason,
    )


def log_identity_link(
    canonical_user_id: str,
    link_type: str,
    link_value: str,
) -> None:
    """Log an identity link event."""
    logger.info(
        "identity_linked canonical=%s link_type=%s",
        canonical_user_id, link_type,
    )
