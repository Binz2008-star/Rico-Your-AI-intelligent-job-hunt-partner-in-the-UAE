"""
src/services/pipeline_service.py
Business logic for triggering and tracking pipeline runs.
All DB I/O goes through repositories.pipeline_repo.
All Playwright / browser code stays in src.run_daily — never imported here.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.db import is_db_available
from src.repositories import pipeline_repo

logger = logging.getLogger(__name__)

_UTC = timezone.utc

# In-memory fallback state when DB is unavailable
_mem: Dict[str, Any] = {
    "status": "idle",
    "started_at": None,
    "finished_at": None,
    "jobs_found": 0,
    "error": None,
}
_mem_lock = threading.Lock()
# Serialises the status-check + run-insert sequence to prevent concurrent triggers
_trigger_lock = threading.Lock()

# A pipeline_runs row stuck in 'running' for longer than this is treated as
# abandoned (process crash, hung run without a timeout, daemon thread lost).
# Generous relative to a normal run so a legitimately long run is never falsely
# recovered; the run_pipeline distributed lock still prevents real overlap.
# Mirrors the chat_operations lease philosophy: liveness is proven, never assumed.
_STALE_RUNNING_SECONDS = 5400


def _run_is_stale(run: Dict[str, Any]) -> bool:
    """True when a 'running' row started longer ago than _STALE_RUNNING_SECONDS.

    A 'running' row with no usable started_at cannot be proven fresh, so it is
    treated as stale — a corrupt row must never brick the trigger endpoint.
    """
    started_raw = run.get("started_at")
    if not started_raw:
        return True
    try:
        started = datetime.fromisoformat(str(started_raw))
        if started.tzinfo is None:
            started = started.replace(tzinfo=_UTC)
        return (datetime.now(_UTC) - started).total_seconds() > _STALE_RUNNING_SECONDS
    except (ValueError, TypeError):
        # Unparseable timestamp — cannot prove freshness. Treat as stale rather
        # than bricking the trigger indefinitely on a corrupt row.
        return True


def get_status() -> Dict[str, Any]:
    """Return the latest pipeline run state (DB preferred, memory fallback)."""
    if is_db_available():
        run = pipeline_repo.get_latest()
        if run:
            return run
    with _mem_lock:
        return dict(_mem)


def trigger() -> None:
    """
    Start the pipeline in a background thread.
    Raises RuntimeError if a run is already in progress.
    """
    with _trigger_lock:
        if is_db_available():
            run = pipeline_repo.get_latest()
            if run and run.get("status") == "running":
                if _run_is_stale(run):
                    # The previous run can never finish (no timeout, daemon thread,
                    # no lease). Recover it so the trigger endpoint is never
                    # permanently blocked by an unprocessable row (the head-of-line
                    # failure mode from the scheduler audit). Marking it 'failed'
                    # with an explicit reason keeps the audit trail honest.
                    logger.warning(
                        "pipeline_stale_running_recovered run_id=%s",
                        run.get("run_id"),
                    )
                    pipeline_repo.update_run(
                        run["run_id"], "failed", "abandoned_stale_running"
                    )
                else:
                    raise RuntimeError("A pipeline run is already in progress")
            run_id = pipeline_repo.insert_run()
        else:
            with _mem_lock:
                if _mem["status"] == "running":
                    raise RuntimeError("A pipeline run is already in progress")
                _mem.update(
                    {
                        "status": "running",
                        "started_at": datetime.now(_UTC).isoformat(),
                        "finished_at": None,
                        "error": None,
                    }
                )
            run_id = None

    thread = threading.Thread(
        target=_run_bg,
        args=(run_id,),
        daemon=True,
        name="pipeline-trigger",
    )
    thread.start()


def _run_bg(run_id: Optional[int]) -> None:
    """Execute run_pipeline() and record the outcome.

    run_pipeline() returns 0 on success and non-zero on critical failure (e.g.
    fetch/score abort, or the distributed lock being unavailable). Its return
    code must drive the recorded status — recording 'done' for a run that
    returned a failure would make the pipeline_status control-plane lie.
    """
    try:
        from src.run_daily import run_pipeline
        rc = run_pipeline()

        if run_id is not None:
            if rc == 0:
                pipeline_repo.update_run(run_id, "done")
            else:
                pipeline_repo.update_run(run_id, "failed", f"run_pipeline_returned_{rc}")
        else:
            with _mem_lock:
                _mem.update(
                    {
                        "status": "done" if rc == 0 else "failed",
                        "finished_at": datetime.now(_UTC).isoformat(),
                        "error": None if rc == 0 else f"run_pipeline_returned_{rc}",
                    }
                )

    except Exception as exc:
        error_msg = str(exc)
        logger.exception("pipeline_bg_run_failed")
        if run_id is not None:
            pipeline_repo.update_run(run_id, "failed", error_msg)
        else:
            with _mem_lock:
                _mem.update(
                    {
                        "status": "failed",
                        "finished_at": datetime.now(_UTC).isoformat(),
                        "error": error_msg,
                    }
                )
