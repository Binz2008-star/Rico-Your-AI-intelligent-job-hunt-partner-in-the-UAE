"""
src/api/routers/apply_queue.py
Apply-queue endpoints: prepare → queue → approve/reject → follow-ups.

POST /api/v1/apply/prepare          — AI-tailor CV + cover letter for a job
GET  /api/v1/apply/queue            — list pending drafts
POST /api/v1/apply/approve/{id}     — approve draft (wires lifecycle tracking)
DELETE /api/v1/apply/reject/{id}    — reject draft
GET  /api/v1/apply/follow-ups       — list approved drafts with follow-up due
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.api.deps import get_current_user
from src.api.rate_limit import limiter
from src.rico_db import RicoDB

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/apply", tags=["apply-queue"])

LIMIT_PREPARE = "5/minute"


class PrepareRequest(BaseModel):
    job_key: str
    title: str
    company: str
    description: Optional[str] = None
    apply_url: Optional[str] = None
    location: Optional[str] = None
    why: Optional[str] = None


class DraftResponse(BaseModel):
    id: str
    job_key: str
    job_title: str
    company: str
    apply_url: Optional[str] = None
    tailored_cv: str
    cover_letter: str
    status: str
    follow_up_at: Optional[str] = None
    created_at: str


def _user_id(user: dict) -> str:
    return str(user.get("email") or user.get("sub") or user.get("id") or "")


def _db() -> RicoDB:
    return RicoDB()


@router.post("/prepare", response_model=DraftResponse)
@limiter.limit(LIMIT_PREPARE)
def prepare_application(
    request: Request,
    req: PrepareRequest,
    user: dict = Depends(get_current_user),
) -> DraftResponse:
    """AI-tailor the user's CV and generate a cover letter for this job, then queue for approval."""
    user_id = _user_id(user)
    db = _db()

    bundle = db.get_user_bundle(user_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Profile not found. Upload your CV first.")
    cv_text = bundle.get("cv_text") or ""
    if not cv_text.strip():
        raise HTTPException(status_code=422, detail="No CV found in your profile. Upload your CV first.")

    profile_raw = bundle.get("profile") or {}
    profile: Dict[str, Any] = profile_raw if isinstance(profile_raw, dict) else {}

    job = {
        "title": req.title,
        "company": req.company,
        "description": req.description or req.why or "",
        "apply_url": req.apply_url or "",
        "location": req.location or "UAE",
        "why": req.why or "",
    }

    from src.rico_apply_ai import tailor_application
    result = tailor_application(cv_text=cv_text, profile=profile, job=job)

    draft = db.create_application_draft(
        user_id=user_id,
        job_key=req.job_key,
        job_title=req.title,
        company=req.company,
        job_description=job["description"],
        apply_url=req.apply_url or "",
        tailored_cv=result["tailored_cv"],
        cover_letter=result["cover_letter"],
    )

    return DraftResponse(
        id=str(draft["id"]),
        job_key=draft["job_key"],
        job_title=draft["job_title"],
        company=draft["company"],
        apply_url=draft.get("apply_url"),
        tailored_cv=draft["tailored_cv"],
        cover_letter=draft["cover_letter"],
        status=draft["status"],
        follow_up_at=str(draft["follow_up_at"]) if draft.get("follow_up_at") else None,
        created_at=str(draft["created_at"]),
    )


@router.get("/queue", response_model=List[DraftResponse])
def get_queue(
    user: dict = Depends(get_current_user),
) -> List[DraftResponse]:
    """Return pending application drafts for the authenticated user."""
    user_id = _user_id(user)
    db = _db()
    drafts = db.get_application_drafts(user_id, status="pending")
    return [
        DraftResponse(
            id=str(d["id"]),
            job_key=d["job_key"],
            job_title=d["job_title"],
            company=d["company"],
            apply_url=d.get("apply_url"),
            tailored_cv=d["tailored_cv"],
            cover_letter=d["cover_letter"],
            status=d["status"],
            follow_up_at=str(d["follow_up_at"]) if d.get("follow_up_at") else None,
            created_at=str(d["created_at"]),
        )
        for d in drafts
    ]


@router.post("/approve/{draft_id}", response_model=dict)
def approve_draft(
    draft_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    """Approve a prepared application draft and wire lifecycle tracking."""
    user_id = _user_id(user)
    db = _db()

    # Atomic transition: pending → approved in a single UPDATE...RETURNING.
    # This eliminates the TOCTOU race where the draft was fetched separately
    # before the status update, which could allow double-approve or acting on
    # a draft that was already rejected by a concurrent request.
    draft = db.update_draft_status_returning(draft_id, user_id, "approved")
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found or already actioned.")

    # Wire into lifecycle pipeline — never raises, best-effort
    try:
        from src.repositories.user_job_context_repo import (
            record_interaction,
            set_lifecycle_status,
        )
        job_title = draft.get("job_title") or ""
        company = draft.get("company") or ""
        apply_url = draft.get("apply_url") or ""
        record_interaction(user_id=user_id, title=job_title, company=company, action="apply")
        set_lifecycle_status(
            user_id=user_id,
            title=job_title,
            company=company,
            status="applied",
            apply_url=apply_url,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("lifecycle wire failed for draft %s: %s", draft_id, exc)

    return {"ok": True, "status": "approved"}


@router.delete("/reject/{draft_id}", response_model=dict)
def reject_draft(
    draft_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    """Reject a prepared application draft."""
    user_id = _user_id(user)
    db = _db()
    updated = db.update_draft_status(draft_id, user_id, "rejected")
    if not updated:
        raise HTTPException(status_code=404, detail="Draft not found or already actioned.")
    return {"ok": True, "status": "rejected"}


@router.get("/follow-ups", response_model=List[DraftResponse])
def get_follow_ups(
    user: dict = Depends(get_current_user),
) -> List[DraftResponse]:
    """Return approved drafts where a follow-up reminder is due (7 days after approval)."""
    user_id = _user_id(user)
    db = _db()
    drafts = db.get_follow_up_drafts(user_id)
    return [
        DraftResponse(
            id=str(d["id"]),
            job_key=d["job_key"],
            job_title=d["job_title"],
            company=d["company"],
            apply_url=d.get("apply_url"),
            tailored_cv=d["tailored_cv"],
            cover_letter=d["cover_letter"],
            status=d["status"],
            follow_up_at=str(d["follow_up_at"]) if d.get("follow_up_at") else None,
            created_at=str(d["created_at"]),
        )
        for d in drafts
    ]
