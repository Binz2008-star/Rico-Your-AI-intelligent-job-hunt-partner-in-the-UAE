"""src/services/analytics_emitters.py

Server-side analytics emitters — v1, deliberately minimal (owner gate,
2026-07-19): exactly TWO events are wired, from exactly two call sites.

  * job_action        — src/agent/runtime.py, after a successful handled
                        action (the mandated path for all job actions).
  * search_performed  — src/rico_chat_api.py _finalize(), once per finalized
                        job_matches response.

Contract (inherits the analytics_events_repo foundation, PR #1176):
  * NEVER raises and never alters product flow — every emitter swallows
    everything, and call sites are additionally wrapped.
  * NO free text: emitters accept only enum tokens and counts by signature —
    there is no parameter through which message text, CV text, or a search
    query could even be passed.
  * Authenticated users only in v1: ``public:`` guest sessions are skipped
    entirely. The guest identity contract (audience="guest" +
    guest_session_id) exists in the foundation; wiring guest emission is a
    later, separately-approved change.
  * Identity is hashed by the foundation (keyed HMAC under
    RICO_ANALYTICS_HMAC_KEY, fail-closed when absent) — raw ids never reach
    rows or logs.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _eligible_user(user_id: Any) -> Optional[str]:
    """v1 scope: real authenticated identities only; guests skipped."""
    uid = str(user_id or "").strip()
    if not uid or uid.startswith("public:"):
        return None
    return uid


def emit_job_action(user_id: Any, action: Any) -> None:
    """Record one job_action event. Fire-and-forget; never raises."""
    try:
        uid = _eligible_user(user_id)
        if uid is None:
            return
        from src.repositories.analytics_events_repo import record_event
        record_event(
            "job_action",
            user_id=uid,
            surface="command",
            properties={"action": str(action)},
        )
    except Exception:
        logger.debug("analytics: emit_job_action skipped", exc_info=True)


def emit_search_performed(user_id: Any, results_count: Any, surface: str = "command") -> None:
    """Record one search_performed event (counts only — never query text)."""
    try:
        uid = _eligible_user(user_id)
        if uid is None:
            return
        from src.repositories.analytics_events_repo import record_event
        record_event(
            "search_performed",
            user_id=uid,
            surface=surface,
            properties={"surface": surface, "results_count": int(results_count)},
        )
    except Exception:
        logger.debug("analytics: emit_search_performed skipped", exc_info=True)
