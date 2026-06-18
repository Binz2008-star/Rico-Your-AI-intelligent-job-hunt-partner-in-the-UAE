"""Follow-up reminder sweep (Issue #355, Phase 1).

Dashboard-first: transitions ``applied`` jobs that have aged past the interval to
``follow_up_due`` so they surface on the /flow board for the user to act on.

No auto-send. No Telegram in Phase 1 (deferred). Idempotent: re-running the sweep
only ever touches rows still at status='applied'.

Invoked by the cron-guarded ``POST /api/v1/pipeline/reminders`` endpoint.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

DEFAULT_FOLLOWUP_INTERVAL_DAYS = 7


def _coerce_interval(interval_days: Any) -> int:
    try:
        days = int(interval_days)
    except (TypeError, ValueError):
        return DEFAULT_FOLLOWUP_INTERVAL_DAYS
    return days if days >= 1 else DEFAULT_FOLLOWUP_INTERVAL_DAYS


def run_due_scan(interval_days: Any = DEFAULT_FOLLOWUP_INTERVAL_DAYS) -> Dict[str, Any]:
    """Mark applied jobs older than ``interval_days`` as ``follow_up_due``.

    Returns a summary dict: ``{"status", "interval_days", "marked_due"}``.
    Never raises — DB unavailability or a pre-migration schema returns a safe
    summary so the cron call gets a 200 with a clear status instead of a 500.
    """
    days = _coerce_interval(interval_days)

    from src.rico_db import RicoDB

    db = RicoDB()
    if not getattr(db, "available", False):
        logger.warning("followup_scan: DB unavailable — skipping")
        return {"status": "unavailable", "interval_days": days, "marked_due": 0}

    try:
        marked = db.mark_followups_due(days)
    except Exception as exc:
        # e.g. columns not present until migration 027 is applied to Neon.
        logger.warning("followup_scan: failed (apply migration 027?): %s", exc)
        return {"status": "error", "interval_days": days, "marked_due": 0}

    logger.info("followup_scan: marked %s job(s) follow_up_due (interval=%sd)", marked, days)
    return {"status": "ok", "interval_days": days, "marked_due": int(marked)}
