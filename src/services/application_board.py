"""application_board.py — Canonical persistence for user-visible chat job actions.

Ownership rule (single source of truth for the /applications board)
-------------------------------------------------------------------
* ``applications_repo``  — the CANONICAL, user-scoped, board-visible record. The
  ``/applications`` page (and ``/flow`` → ``/applications``) reads exclusively
  from it via ``get_page()``. This module is the one writer chat uses for the
  ``saved`` and ``prepared`` states.
* ``user_job_context``   — secondary lifecycle/learning metadata. Stamped by the
  chat handlers, NOT here. A failure there never invalidates a verified canonical
  save (this module doesn't touch it, so the property holds by construction).
* legacy JSON store      — guest/pipeline compatibility only; never the record of
  truth for an authenticated chat Save/Prepare.

Why this exists
---------------
A card-originated chat Save routed through ``agent_runtime.handle_action`` →
``job_tools.save_job`` → ``mark_applied`` writes the legacy JSON file WITHOUT a
``user_id``, so the saved job never reached ``applications_repo`` and never
appeared on the board — while the handler still claimed "Saved". ``_save_job_by_
ordinal`` and the Prepare flow already wrote canonically; this module factors
that proven pattern into one place so save/prepare cannot diverge, and gates
success on an explicit read-back so "Saved"/"Prepared" is only ever reported
when the board actually reflects it.
"""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

logger = logging.getLogger(__name__)

# The only two user-visible chat states this module owns.
_ALLOWED_STATUSES: tuple[str, ...] = ("saved", "prepared")

# Canonical no-downgrade ordering — mirrors RicoChatAPI._get_status_rank so the
# board never regresses (e.g. a later "save" must not knock a "prepared"/"applied"
# row back down to "saved").
_STATUS_RANK: dict[str, int] = {
    "found": 0,
    "saved": 10,
    "opened": 20,
    "opened_external": 20,
    "prepared": 30,
    "applied": 40,
    "follow_up_due": 50,
    "interview": 60,
    "offer": 70,
    "rejected": 70,
    "decision_made": 80,
    "archived": 90,
}


def _rank(status: str) -> int:
    return _STATUS_RANK.get((status or "").strip().lower(), 0)


@dataclass
class BoardResult:
    """Outcome of a canonical board persistence attempt.

    ``ok`` is True ONLY when a read-back confirmed the board holds at least the
    requested status for this user and job. ``error`` carries a machine code on
    failure; ``quota_message`` carries the user-safe upgrade copy on a quota hit.
    """
    ok: bool
    status: str = ""          # verified status on the board after the call
    created: bool = False      # a NEW record was created (quota-consuming)
    error: str = ""            # "" | bad_status | no_user | bad_job | quota_exceeded | persist_failed | readback_failed
    quota_message: str = ""


def persist_job_action(user_id: str, job: dict[str, Any], status: str, *, save_key: str) -> BoardResult:
    """Persist a chat Save/Prepare to ``applications_repo`` and verify by read-back.

    Args:
        user_id:  Authenticated user id (email/uuid). Required — the write is
                  user-scoped and never falls back to the legacy JSON store.
        job:      Job dict; ``title``/``company``/``location`` and the best URL
                  (``apply_url`` → ``source_url`` → ``link``) are preserved.
        status:   ``"saved"`` or ``"prepared"`` only.
        save_key: Canonical job identity (the same key save/prepare/skip derive
                  via ``RicoChatAPI._derive_lifecycle_job_key``) so repeated Save,
                  and a Save→Prepare transition, address ONE record.

    Returns:
        ``BoardResult``. Never raises — every failure is reported honestly so the
        caller can avoid claiming a save/prepare that did not land.
    """
    from fastapi import HTTPException

    from src.repositories import applications_repo

    status = (status or "").strip().lower()
    if status not in _ALLOWED_STATUSES:
        return BoardResult(ok=False, error="bad_status")
    if not user_id:
        return BoardResult(ok=False, error="no_user")
    if not isinstance(job, dict) or not (save_key or "").strip():
        return BoardResult(ok=False, error="bad_job")

    title = str(job.get("title") or "").strip()
    company = str(job.get("company") or "").strip()
    location = str(job.get("location") or "").strip()
    url = str(job.get("apply_url") or job.get("source_url") or job.get("link") or "").strip()

    # 1. Existing canonical record (user-scoped by construction — a lookup for
    #    user A can never see user B's row).
    try:
        existing = applications_repo.find_by_job_id(save_key, user_id=user_id)
    except Exception:
        logger.warning("application_board: existing lookup failed user=%s", user_id, exc_info=True)
        existing = None
    existing_status = str((existing or {}).get("status") or "") if existing else ""

    # 2. Write, honoring the no-downgrade transition policy.
    created = False
    if existing and _rank(existing_status) >= _rank(status):
        # Board already reflects this stage or beyond (idempotent Save, or a
        # would-be downgrade like prepared→save). No write, no new quota.
        pass
    else:
        try:
            if existing:
                # Forward transition (e.g. saved→prepared). update_status enforces
                # the saved quota only on →saved; not a new row, so no duplicate
                # quota is consumed.
                applications_repo.update_status(
                    {
                        "job_id": save_key,
                        "title": title,
                        "company": company,
                        "location": location,
                        "link": url,
                    },
                    status,
                    user_id=user_id,
                )
            else:
                # New record — create() enforces the saved-job quota for →saved.
                created = bool(
                    applications_repo.create(
                        job_id=save_key,
                        title=title,
                        company=company,
                        location=location,
                        url=url,
                        status=status,
                        source="chat",
                        user_id=user_id,
                    )
                )
        except HTTPException as exc:
            # applications_repo raises 402 when the saved-job quota is exhausted.
            if getattr(exc, "status_code", None) == 402:
                detail = getattr(exc, "detail", None)
                qmsg = detail.get("message") if isinstance(detail, dict) else ""
                return BoardResult(ok=False, error="quota_exceeded", quota_message=str(qmsg or ""))
            logger.warning("application_board: persist HTTPException user=%s", user_id, exc_info=True)
            return BoardResult(ok=False, error="persist_failed")
        except Exception:
            logger.warning("application_board: persist failed user=%s", user_id, exc_info=True)
            return BoardResult(ok=False, error="persist_failed")

    # 3. Canonical read-back — the ONLY thing that authorizes a success claim.
    try:
        row = applications_repo.find_by_job_id(save_key, user_id=user_id)
    except Exception:
        logger.warning("application_board: read-back failed user=%s", user_id, exc_info=True)
        row = None
    if not row:
        return BoardResult(ok=False, created=created, error="readback_failed")
    verified = str(row.get("status") or "")
    if _rank(verified) < _rank(status):
        # The board did not reach at least the requested tier.
        return BoardResult(ok=False, status=verified, created=created, error="readback_failed")

    return BoardResult(ok=True, status=verified, created=created)
