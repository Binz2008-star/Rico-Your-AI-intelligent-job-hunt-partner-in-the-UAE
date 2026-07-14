"""
Career Memory Engine — MemoryWriter (ADR-001 M1, shadow writes only).

The single write path into career_memory_events. M1 contract (owner-accepted):

  - Flag-gated: RICO_MEMORY_ENGINE_ENABLED (default OFF) is both the feature
    flag and the kill switch; read at call time so flipping the env var takes
    effect without a restart of callers holding module references.
  - Shadow-only: no reader exists; a write failure must NEVER propagate to the
    calling action path. Every public function returns bool and never raises.
  - Identity (ADR-001 §3): storage key is the immutable rico_users.id UUID,
    namespaced 'acct:<uuid>'. Public sessions stay separately keyed as
    'session:<public:web-...>'. Email is only a lookup attribute here.
  - Idempotent: UNIQUE (account_key, idempotency_key); replays dedupe silently.
  - Data minimization (ADR-001 §8): payloads pass an exclusion filter that
    drops secret-looking keys and truncates oversized strings; full provider
    payloads must never be passed in.
  - Metrics: in-process counters (get_write_stats) + one structured log line
    per failure, so shadow-write failure/drift is observable from day one.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Payload exclusion filter (ADR-001 §8): drop keys that look like secrets or
# credentials, whatever their nesting depth.
_SECRET_KEY_RE = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|authorization|credential|cookie|session[_-]?id)",
    re.IGNORECASE,
)
_MAX_STRING_LEN = 2000  # bulk text belongs to bulk_text records, not payloads
_PUBLIC_PREFIX = "public:"

_VALID_SOURCES = {"user_stated", "verified_event", "cv_extracted", "inferred"}
_VALID_RETENTION = {"core_fact", "episode", "bulk_text", "derived", "referenced"}

_stats_lock = threading.Lock()
_stats: Dict[str, int] = {
    "written": 0,
    "deduped": 0,
    "failed": 0,
    "skipped_disabled": 0,
    "unresolved_identity": 0,
    "excluded_keys_dropped": 0,
}


def is_memory_engine_enabled() -> bool:
    """Feature flag AND kill switch — default OFF (M1 shadow mode)."""
    return os.getenv("RICO_MEMORY_ENGINE_ENABLED", "").strip().lower() == "true"


def get_write_stats() -> Dict[str, int]:
    """Snapshot of in-process shadow-write counters (drift/failure metrics)."""
    with _stats_lock:
        return dict(_stats)


def _reset_stats() -> None:
    """Test hook only."""
    with _stats_lock:
        for k in _stats:
            _stats[k] = 0


def _bump(key: str, n: int = 1) -> None:
    with _stats_lock:
        _stats[key] = _stats.get(key, 0) + n


def sanitize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Apply the ADR-001 §8 exclusion filter: strip secret-looking keys at any
    depth and truncate oversized strings. Never raises."""

    def clean(value: Any) -> Any:
        if isinstance(value, dict):
            out = {}
            for k, v in value.items():
                if _SECRET_KEY_RE.search(str(k)):
                    _bump("excluded_keys_dropped")
                    continue
                out[str(k)] = clean(v)
            return out
        if isinstance(value, list):
            return [clean(v) for v in value]
        if isinstance(value, str) and len(value) > _MAX_STRING_LEN:
            return value[:_MAX_STRING_LEN] + "…[truncated]"
        return value

    try:
        return clean(dict(payload or {}))
    except Exception:
        logger.warning("memory_writer: payload sanitize failed; storing empty payload")
        return {}


def resolve_account_key(user_id: str) -> Optional[str]:
    """Map a caller-facing user id to the durable memory key (ADR-001 §3).

    - public sessions ('public:web-…') → 'session:<id>' (no DB lookup; they
      never merge into account memory implicitly)
    - anything else → look up the immutable rico_users.id by email or by
      external_user_id; returns 'acct:<uuid>' or None when unresolvable.
    """
    uid = (user_id or "").strip()
    if not uid:
        return None
    if uid.startswith(_PUBLIC_PREFIX):
        return f"session:{uid}"

    try:
        from src.db import get_db_connection

        conn = get_db_connection()
        if conn is None:
            return None
        try:
            with conn.cursor() as cur:
                if "@" in uid:
                    cur.execute("SELECT id FROM rico_users WHERE email = %s LIMIT 1", (uid,))
                else:
                    cur.execute(
                        "SELECT id FROM rico_users WHERE external_user_id = %s LIMIT 1", (uid,)
                    )
                row = cur.fetchone()
            return f"acct:{row[0]}" if row else None
        finally:
            conn.close()
    except Exception:
        logger.warning("memory_writer: identity resolution failed", exc_info=True)
        return None


def record_event(
    user_id: str,
    event_type: str,
    *,
    idempotency_key: str,
    actor: str,
    source: str,
    confidence: float = 1.0,
    retention_class: str = "episode",
    occurred_at: Optional[datetime] = None,
    source_record_id: Optional[str] = None,
    source_uri: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> bool:
    """Shadow-write one memory event. Returns True when the event is durably
    recorded (or already was — dedup counts as success). NEVER raises."""
    try:
        if not is_memory_engine_enabled():
            _bump("skipped_disabled")
            return False

        if source not in _VALID_SOURCES or retention_class not in _VALID_RETENTION:
            _bump("failed")
            logger.warning(
                "memory_write_failed reason=invalid_envelope source=%s retention=%s",
                source, retention_class,
            )
            return False

        account_key = resolve_account_key(user_id)
        if not account_key:
            _bump("unresolved_identity")
            logger.warning("memory_write_skipped reason=unresolved_identity")
            return False

        from src.db import get_db_connection

        conn = get_db_connection()
        if conn is None:
            _bump("failed")
            logger.warning("memory_write_failed reason=no_db_connection")
            return False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO career_memory_events
                        (account_key, event_type, version, retention_class,
                         occurred_at, actor, source, source_record_id,
                         source_uri, confidence, idempotency_key, payload)
                    VALUES (%s, %s, 1, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT ON CONSTRAINT career_memory_events_account_idem_key
                    DO NOTHING
                    """,
                    (
                        account_key,
                        event_type,
                        retention_class,
                        occurred_at or datetime.now(timezone.utc),
                        actor,
                        source,
                        source_record_id,
                        source_uri,
                        confidence,
                        idempotency_key,
                        json.dumps(sanitize_payload(payload or {})),
                    ),
                )
                inserted = cur.rowcount == 1
            conn.commit()
            _bump("written" if inserted else "deduped")
            return True
        finally:
            conn.close()
    except Exception:
        _bump("failed")
        logger.warning("memory_write_failed reason=exception", exc_info=True)
        return False


def record_action_episode(
    user_id: str,
    action: str,
    job: Dict[str, Any],
    job_key: str,
    ok: bool,
    source: str,
    action_id: str,
    error: Optional[str] = None,
) -> bool:
    """Shadow-record one agent-runtime action outcome as an episode.

    Reuses the runtime's own idempotency identity (action_id = md5 of
    user:action:job_key) so the memory event dedupes exactly like the action.
    Payload is minimal by design (data minimization): title/company/status,
    never the full job dict or provider payload.
    """
    return record_event(
        user_id,
        "action",
        idempotency_key=f"action:{action_id}",
        actor=f"agent:{source}",
        source="verified_event",
        confidence=1.0,
        retention_class="episode",
        source_record_id=action_id,
        payload={
            "action": action,
            "job_key": job_key,
            "title": (job or {}).get("title", ""),
            "company": (job or {}).get("company", ""),
            "ok": ok,
            "error": error or "",
        },
    )
