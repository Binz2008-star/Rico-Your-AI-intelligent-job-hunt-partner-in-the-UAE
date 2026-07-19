"""src/repositories/reasoning_repo.py

Persistent Reasoning Graph (migration 047).

Stores each agent decision as a structured ReasoningTrace node
(src/agent/reasoning/trace.py) so Rico keeps an auditable record of why every
decision was made and whether it proved correct. Reads are always scoped by
user_id — a user can only inspect their own reasoning.

Write path contract (mirrors job_observations_repo):
  * ``save_trace`` NEVER raises — failures (DB down, migration 047 not yet
    applied) degrade to a no-op so a trace write can never affect the action
    it describes.
  * When the table is absent (pgcode 42P01) recording disables itself for the
    rest of the process. Applying migration 047 + the next deploy/restart
    enables it.
  * ``RICO_REASONING_TRACES=false`` is the kill switch: persistence (and the
    read API) turns off without touching the in-process trace building.

Privacy: trace payloads carry operational facts only (gate states, action
names, job title/company — the same identity class as action_audit_log).
Never raw chat/document text, contact identifiers, or tokens (#1076). Trace
content is stored, not logged.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from psycopg2.extras import Json

from src.db import get_db_connection, is_db_available

logger = logging.getLogger(__name__)

_MAX_LIST_LIMIT = 50

# Process-local: set when the table does not exist yet (migration 047 not
# applied). Keeps the action hot path free of repeated doomed writes.
_table_missing = False

_UPSERT_SQL = """
    INSERT INTO reasoning_traces (
        trace_id, user_id, goal, status, decision, confidence, source, trace
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (trace_id) DO UPDATE SET
        status     = EXCLUDED.status,
        decision   = EXCLUDED.decision,
        confidence = EXCLUDED.confidence,
        trace      = EXCLUDED.trace,
        updated_at = NOW()
"""

_LIST_SQL = """
    SELECT trace_id, goal, status, decision, confidence, source,
           created_at, updated_at
    FROM reasoning_traces
    WHERE user_id = %s
    ORDER BY created_at DESC
    LIMIT %s
"""

_GET_SQL = """
    SELECT trace_id, goal, status, decision, confidence, source,
           trace, created_at, updated_at
    FROM reasoning_traces
    WHERE trace_id = %s AND user_id = %s
"""


def _enabled() -> bool:
    return os.getenv("RICO_REASONING_TRACES", "true").strip().lower() != "false"


def _mark_if_table_missing(exc: Exception) -> None:
    global _table_missing
    if getattr(exc, "pgcode", None) == "42P01":  # undefined_table
        _table_missing = True
        logger.info(
            "reasoning_traces: table absent (migration 047 not applied) — "
            "recording disabled for this process"
        )


def save_trace(trace: Any) -> bool:
    """Best-effort upsert of one ReasoningTrace. Never raises.

    Accepts a ReasoningTrace (anything with ``to_dict()``) or a plain dict in
    the same shape. Returns True only when a row was written.
    """
    if _table_missing or not _enabled() or not is_db_available():
        return False

    try:
        data: Dict[str, Any] = trace.to_dict() if hasattr(trace, "to_dict") else dict(trace)
        trace_id = str(data.get("trace_id") or "").strip()
        if not trace_id:
            return False
        decision = data.get("decision") or {}
        row = (
            trace_id[:32],
            str(data.get("user_id") or "")[:255],
            str(data.get("goal") or "")[:512],
            str(data.get("status") or "decided")[:16],
            str(decision.get("action") or "")[:128] if isinstance(decision, dict) else "",
            float(data.get("confidence") or 0.0),
            str(data.get("source") or "")[:32],
            Json(data),
        )
    except Exception:
        logger.debug("reasoning_traces: could not serialize trace", exc_info=True)
        return False

    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            return False
        with conn.cursor() as cur:
            cur.execute(_UPSERT_SQL, row)
        conn.commit()
        return True
    except Exception as exc:
        _mark_if_table_missing(exc)
        logger.debug("reasoning_traces: write skipped err=%s", type(exc).__name__)
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def list_recent(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Summaries of the user's most recent reasoning traces, newest first.
    Never raises; returns [] on any failure."""
    if _table_missing or not _enabled() or not is_db_available() or not user_id:
        return []

    limit = max(1, min(int(limit or 1), _MAX_LIST_LIMIT))
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            return []
        with conn.cursor() as cur:
            cur.execute(_LIST_SQL, (user_id, limit))
            rows = cur.fetchall()
        return [
            {
                "trace_id": str(r[0]).strip(),
                "goal": r[1],
                "status": r[2],
                "decision": r[3],
                "confidence": r[4],
                "source": r[5],
                "created_at": r[6].isoformat() if r[6] else None,
                "updated_at": r[7].isoformat() if r[7] else None,
            }
            for r in rows
        ]
    except Exception as exc:
        _mark_if_table_missing(exc)
        logger.debug("reasoning_traces: list skipped err=%s", type(exc).__name__)
        return []
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def get_trace(trace_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """Full trace payload for one trace, scoped to its owner.
    Never raises; returns None when absent or on any failure."""
    if _table_missing or not _enabled() or not is_db_available():
        return None
    if not trace_id or not user_id:
        return None

    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            return None
        with conn.cursor() as cur:
            cur.execute(_GET_SQL, (str(trace_id)[:32], user_id))
            r = cur.fetchone()
        if not r:
            return None
        return {
            "trace_id": str(r[0]).strip(),
            "goal": r[1],
            "status": r[2],
            "decision": r[3],
            "confidence": r[4],
            "source": r[5],
            "trace": r[6] if isinstance(r[6], dict) else {},
            "created_at": r[7].isoformat() if r[7] else None,
            "updated_at": r[8].isoformat() if r[8] else None,
        }
    except Exception as exc:
        _mark_if_table_missing(exc)
        logger.debug("reasoning_traces: get skipped err=%s", type(exc).__name__)
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _reset_state_for_tests() -> None:
    global _table_missing
    _table_missing = False
