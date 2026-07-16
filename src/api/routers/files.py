"""
src/api/routers/files.py
User file / document management endpoints.

Routes:
  GET    /api/v1/user/files                   list uploaded files   (JWT required)
  POST   /api/v1/user/files                   upload document       (JWT required)
  DELETE /api/v1/user/files/{id}              delete a file         (JWT required)
  PATCH  /api/v1/user/files/{id}              rename / retype file  (JWT required)
  POST   /api/v1/user/files/{id}/set-primary  set primary CV        (JWT required)
  GET    /api/v1/user/files/quota             quota usage summary   (JWT required)
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from src.api.deps import get_current_user
from src.api.rate_limit import LIMIT_UPLOAD, limiter
from src.repositories import profile_repo
from src.repositories.profile_repo import upsert_profile
from src.rico_db import DocumentConflictError, RicoDB
from src.services.subscription_gating import (
    check_document_quota,
    enforce_document_quota,
)
from src.subscription_plans import resolve_effective_user_plan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/user/files", tags=["files"])

_db = RicoDB()

_UNSAFE_CHARS_RE = re.compile(r"[<>\"';\x00-\x1f\x7f]")
_PDF_MAGIC = b"%PDF"
_MAX_BYTES = 25 * 1024 * 1024  # 25 MB — documents (PDF) carry fonts + page images
_ALLOWED_DOC_TYPES = {"cv", "cover_letter", "other"}


def _safe_filename(raw: str | None) -> str:
    if not raw:
        return "document.pdf"
    name = _UNSAFE_CHARS_RE.sub("", raw).strip()
    return name[:200] or "document.pdf"


class FileUpdateRequest(BaseModel):
    label: Optional[str] = None
    doc_type: Optional[str] = None


# ── Quota summary ──────────────────────────────────────────────────────────────

@router.get("/quota")
def get_quota(request: Request) -> dict[str, Any]:
    """Return document storage quota usage for the authenticated user."""
    user = get_current_user(request)
    user_id = user["email"]

    resolved = resolve_effective_user_plan(user_id)
    entitlements = resolved.subscription.entitlements
    plan = resolved.subscription.plan.value

    cv_limit = entitlements.cv_storage_limit
    other_limit = entitlements.other_document_limit

    if _db.available:
        cv_used = _db.count_user_documents(user_id, "cv")
        other_used = _db.count_user_documents(user_id, "other") + _db.count_user_documents(user_id, "cover_letter")
    else:
        cv_used = 0
        other_used = 0

    return {
        "plan": plan,
        "cv": {
            "used": cv_used,
            "limit": cv_limit,
            "unlimited": cv_limit is None,
        },
        "other_documents": {
            "used": other_used,
            "limit": other_limit,
            "unlimited": other_limit is None,
        },
    }


# ── List files ─────────────────────────────────────────────────────────────────

def has_active_cv_document(docs: list[dict[str, Any]]) -> bool:
    """True when the user has a real, primary CV document on record."""
    return any(d.get("doc_type") == "cv" and d.get("is_primary") for d in docs)


def build_profile_cv_record(user_id: str) -> Optional[dict[str, Any]]:
    """Synthesise a legacy 'profile-cv' record from the profile JSONB.

    Users who uploaded a CV before multi-document storage existed (or whose
    CV document write failed) only have cv_filename on the profile. Returns
    None when no parsed profile CV exists or the lookup fails.
    """
    try:
        profile = profile_repo.get_profile(user_id)
        cv_filename = profile and getattr(profile, "cv_filename", None)
        if not cv_filename:
            return None
        cv_extracted_at = getattr(profile, "cv_extracted_at", None)
        return {
            "id": "profile-cv",
            "user_id": user_id,
            "filename": cv_filename,
            "original_filename": cv_filename,
            "doc_type": "cv",
            "file_size": 0,
            "label": None,
            "is_primary": True,
            "is_legacy": True,
            "skills_count": len(getattr(profile, "skills", []) or []),
            "years_experience": getattr(profile, "years_experience", None),
            "current_role": getattr(profile, "current_role", None),
            "created_at": cv_extracted_at,
            "updated_at": cv_extracted_at,
        }
    except Exception:
        logger.debug("profile_cv_fallback_failed user=%s", user_id)
        return None


@router.get("")
def list_files(request: Request) -> dict[str, Any]:
    """Return all documents for the authenticated user."""
    user = get_current_user(request)
    user_id = user["email"]

    docs = _db.list_user_documents(user_id) if _db.available else []

    # When no real document is the active CV, surface the parsed profile CV
    # alongside the real documents (not only when the list is empty) so the
    # active CV is never hidden by unrelated uploads.
    if not has_active_cv_document(docs):
        profile_cv = build_profile_cv_record(user_id)
        if profile_cv:
            docs = [profile_cv] + docs

    # Attach quota info to the response. The synthetic legacy record is not a
    # stored document and must not count against quota — enforcement counts
    # user_documents rows, and the UI display has to agree with it.
    resolved = resolve_effective_user_plan(user_id)
    entitlements = resolved.subscription.entitlements
    stored = [d for d in docs if not d.get("is_legacy")]

    return {
        "files": docs,
        "total": len(docs),
        "quota": {
            "plan": resolved.subscription.plan.value,
            "cv_used": sum(1 for d in stored if d.get("doc_type") == "cv"),
            "cv_limit": entitlements.cv_storage_limit,
            "other_used": sum(1 for d in stored if d.get("doc_type") != "cv"),
            "other_limit": entitlements.other_document_limit,
        },
    }


# ── Upload document ────────────────────────────────────────────────────────────

@router.post("", status_code=201)
@limiter.limit(LIMIT_UPLOAD)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    doc_type: str = "cover_letter",
) -> dict[str, Any]:
    """Upload a document (CV, cover letter, or other). Quota-gated."""
    user = get_current_user(request)
    user_id = user["email"]

    if doc_type not in _ALLOWED_DOC_TYPES:
        raise HTTPException(status_code=422, detail=f"doc_type must be one of {sorted(_ALLOWED_DOC_TYPES)}")

    declared_size = getattr(file, "size", None)
    if isinstance(declared_size, int) and declared_size > _MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                "This file is too large. You can upload documents up to 25MB. "
                "If your file is larger, please compress it or upload a lighter PDF version."
            ),
        )

    data = await file.read()
    if len(data) > _MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                "This file is too large. You can upload documents up to 25MB. "
                "If your file is larger, please compress it or upload a lighter PDF version."
            ),
        )
    if not data:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")
    if not data.startswith(_PDF_MAGIC):
        raise HTTPException(status_code=422, detail="Only PDF files are accepted")

    if not _db.available:
        raise HTTPException(status_code=503, detail="Database unavailable")

    # Exact-duplicate protection (#960): SHA-256 of the original bytes. An exact
    # re-upload returns the existing document and must NOT consume quota — so the
    # dedupe check runs BEFORE quota enforcement (a re-upload of the only CV must
    # not be blocked by the storage limit). This is a cheap pre-check, not the
    # source of truth: the atomic get_or_create below is what actually decides
    # `duplicate`, because a concurrent identical upload can still land between
    # this check and the insert.
    content_hash = hashlib.sha256(data).hexdigest()
    existing = _db.find_user_document_by_hash(user_id, doc_type, content_hash)
    if existing:
        logger.info(
            "file_upload_duplicate user=%s doc_type=%s id=%s", user_id, doc_type, existing["id"]
        )
        return {
            "ok": True,
            "id": existing["id"],
            "filename": existing["filename"],
            "doc_type": doc_type,
            "duplicate": True,
        }

    # New (distinct) document — quota applies exactly as before. A quota check
    # here that's immediately followed by a duplicate-after-all race (below) is
    # harmless: enforce_document_quota only counts existing rows, and a raced
    # duplicate creates no new row, so the count is unaffected either way.
    enforce_document_quota(user_id, doc_type)

    safe_name = _safe_filename(file.filename)
    result = _db.get_or_create_user_document(
        user_id=user_id,
        filename=safe_name,
        original_filename=file.filename or safe_name,
        doc_type=doc_type,
        file_size=len(data),
        is_primary=False,
        content_hash=content_hash,
    )
    is_duplicate = not result["inserted"]

    logger.info(
        "file_uploaded user=%s filename=%s doc_type=%s id=%s duplicate=%s",
        user_id, result["filename"], doc_type, result["id"], is_duplicate,
    )
    # `filename` is always the canonical stored filename — the just-uploaded
    # name on a real insert, or the EXISTING row's name when this request lost
    # a concurrent duplicate-insert race (never the incoming filename in that
    # case, since nothing of this upload was actually persisted).
    return {
        "ok": True,
        "id": result["id"],
        "filename": result["filename"],
        "doc_type": result["doc_type"],
        "duplicate": is_duplicate,
    }


# ── Delete file ────────────────────────────────────────────────────────────────

@router.delete("/{file_id}")
def delete_file(file_id: str, request: Request) -> dict[str, Any]:
    user = get_current_user(request)
    user_id = user["email"]

    if not _db.available:
        raise HTTPException(status_code=503, detail="Database unavailable")

    # The synthetic 'profile-cv' card is the parsed CV grounding, not a stored
    # row. Deleting it means "remove my CV data": purge the grounding so it no
    # longer feeds matching/chat and cannot resurrect as an undeletable card.
    # This previously returned 400, leaving users unable to delete their CV
    # data at all — a privacy defect (#1083).
    if file_id == "profile-cv":
        _db.clear_cv_grounding(user_id)
        logger.info("file_deleted_profile_cv user=%s cleared_cv_grounding=True", user_id)
        return {"ok": True, "cleared_cv_grounding": True}

    # Capture the document's type/primary flag before deletion so we can also
    # purge the derived CV grounding when the *active* CV itself is removed —
    # otherwise the deleted CV's extracted text keeps grounding chat/matching and
    # list_files resurrects it as a synthetic card (#1083).
    docs = _db.list_user_documents(user_id)
    target = next((d for d in docs if str(d.get("id")) == str(file_id)), None)

    deleted = _db.delete_user_document(user_id, file_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="File not found")

    cleared = False
    if target and target.get("doc_type") == "cv" and target.get("is_primary"):
        cleared = _db.clear_cv_grounding(user_id)

    logger.info("file_deleted user=%s id=%s cleared_cv_grounding=%s", user_id, file_id, cleared)
    return {"ok": True, "cleared_cv_grounding": cleared}


# ── Update label / type ───────────────────────────────────────────────────────

@router.patch("/{file_id}")
def update_file(file_id: str, body: FileUpdateRequest, request: Request) -> dict[str, Any]:
    user = get_current_user(request)
    user_id = user["email"]

    if file_id == "profile-cv":
        raise HTTPException(status_code=400, detail="Legacy profile CV cannot be renamed here.")

    if body.doc_type and body.doc_type not in _ALLOWED_DOC_TYPES:
        raise HTTPException(status_code=422, detail=f"doc_type must be one of {sorted(_ALLOWED_DOC_TYPES)}")

    if not _db.available:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        updated = _db.update_user_document(user_id, file_id, label=body.label, doc_type=body.doc_type)
    except DocumentConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not updated:
        raise HTTPException(status_code=404, detail="File not found")

    return {"ok": True}


# ── Set primary CV ─────────────────────────────────────────────────────────────

@router.post("/{file_id}/set-primary")
def set_primary(file_id: str, request: Request) -> dict[str, Any]:
    user = get_current_user(request)
    user_id = user["email"]

    if file_id == "profile-cv":
        return {"ok": True, "note": "Already the active CV from your profile."}

    if not _db.available:
        raise HTTPException(status_code=503, detail="Database unavailable")

    updated = _db.set_primary_document(user_id, file_id)
    if not updated:
        raise HTTPException(status_code=404, detail="File not found or not a CV")

    logger.info("file_set_primary user=%s id=%s", user_id, file_id)

    # Re-sync profile fields from the newly activated CV document.
    # Without this, switching active CVs leaves years_experience / skills / current_role
    # pointing at the previously confirmed CV's data.
    try:
        doc = _db.get_primary_document(user_id, doc_type="cv")
        if doc:
            resync: dict[str, Any] = {}
            if doc.get("years_experience") is not None:
                resync["years_experience"] = float(doc["years_experience"])
            if doc.get("current_role"):
                resync["current_role"] = doc["current_role"]
            skills = doc.get("skills_json") or []
            if skills:
                resync["skills"] = list(skills)
            if resync:
                upsert_profile(user_id, resync)
                logger.info("file_set_primary_profile_resynced user=%s fields=%s", user_id, list(resync.keys()))
    except Exception as _exc:
        logger.warning("file_set_primary_resync_failed user=%s error=%s", user_id, str(_exc))

    return {"ok": True}
