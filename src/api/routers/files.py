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

import logging
import re
from typing import Any, Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from src.api.deps import get_current_user
from src.api.rate_limit import LIMIT_UPLOAD, limiter
from src.repositories import profile_repo
from src.rico_db import RicoDB
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
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
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

@router.get("")
def list_files(request: Request) -> dict[str, Any]:
    """Return all documents for the authenticated user."""
    user = get_current_user(request)
    user_id = user["email"]

    docs = _db.list_user_documents(user_id) if _db.available else []

    # For users who uploaded a CV before this feature existed, synthesise a
    # record from the profile JSONB so the UI is never empty.
    if not docs:
        try:
            profile = profile_repo.get_profile(user_id)
            cv_filename = profile and getattr(profile, "cv_filename", None)
            cv_extracted_at = profile and getattr(profile, "cv_extracted_at", None)
            if cv_filename:
                docs = [
                    {
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
                ]
        except Exception:
            logger.debug("list_files profile_fallback_failed user=%s", user_id)

    # Attach quota info to the response
    resolved = resolve_effective_user_plan(user_id)
    entitlements = resolved.subscription.entitlements

    return {
        "files": docs,
        "total": len(docs),
        "quota": {
            "plan": resolved.subscription.plan.value,
            "cv_used": sum(1 for d in docs if d.get("doc_type") == "cv"),
            "cv_limit": entitlements.cv_storage_limit,
            "other_used": sum(1 for d in docs if d.get("doc_type") != "cv"),
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

    # Enforce document storage quota before reading the file body
    enforce_document_quota(user_id, doc_type)

    data = await file.read()
    if len(data) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")
    if not data:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")
    if not data.startswith(_PDF_MAGIC):
        raise HTTPException(status_code=422, detail="Only PDF files are accepted")

    if not _db.available:
        raise HTTPException(status_code=503, detail="Database unavailable")

    safe_name = _safe_filename(file.filename)
    doc_id = _db.save_user_document(
        user_id=user_id,
        filename=safe_name,
        original_filename=file.filename or safe_name,
        doc_type=doc_type,
        file_size=len(data),
        is_primary=False,
    )

    logger.info("file_uploaded user=%s filename=%s doc_type=%s id=%s", user_id, safe_name, doc_type, doc_id)
    return {"ok": True, "id": doc_id, "filename": safe_name, "doc_type": doc_type}


# ── Delete file ────────────────────────────────────────────────────────────────

@router.delete("/{file_id}")
def delete_file(file_id: str, request: Request) -> dict[str, Any]:
    user = get_current_user(request)
    user_id = user["email"]

    if file_id == "profile-cv":
        raise HTTPException(status_code=400, detail="Upload a new CV to replace it.")

    if not _db.available:
        raise HTTPException(status_code=503, detail="Database unavailable")

    deleted = _db.delete_user_document(user_id, file_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="File not found")

    logger.info("file_deleted user=%s id=%s", user_id, file_id)
    return {"ok": True}


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

    updated = _db.update_user_document(user_id, file_id, label=body.label, doc_type=body.doc_type)
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
    return {"ok": True}
