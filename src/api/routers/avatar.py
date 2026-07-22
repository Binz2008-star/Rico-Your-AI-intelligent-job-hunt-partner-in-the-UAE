"""
src/api/routers/avatar.py
Profile avatar endpoints (owner request 2026-07-21; migration 050).

Routes:
  GET    /api/v1/user/avatar   current avatar as a data URL   (JWT required)
  POST   /api/v1/user/avatar   upload/replace avatar          (JWT required)
  DELETE /api/v1/user/avatar   remove avatar                  (JWT required)

Storage design: the stack has no blob store, so the avatar is persisted as a
compact data URL in the dedicated user_avatars table (never in the profile
JSONB — the base64 payload must not leak into profile fetches or the LLM chat
context). The frontend downscales client-side before upload; the server still
enforces magic-byte image validation and a hard 500 KB cap.
"""
from __future__ import annotations

import base64
import logging
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from src.api.deps import get_current_user
from src.api.rate_limit import LIMIT_UPLOAD, limiter
from src.api.upload_limits import read_upload_bounded
from src.repositories import avatar_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/user/avatar", tags=["avatar"])

_MAX_AVATAR_BYTES = 500 * 1024  # hard server cap; client sends ~100 KB

# Magic-byte signatures for the accepted raster formats.
_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
]


def _sniff_image(data: bytes) -> str | None:
    """Return the content type from magic bytes, or None if not an accepted image."""
    for magic, ctype in _SIGNATURES:
        if data.startswith(magic):
            return ctype
    # WebP: RIFF....WEBP
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


@router.get("")
def get_avatar(request: Request) -> dict[str, Any]:
    user = get_current_user(request)
    row = avatar_repo.get_avatar(user["email"])
    if not row:
        return {"avatar": None}
    return {"avatar": row["data_url"], "content_type": row["content_type"]}


@router.post("", status_code=201)
@limiter.limit(LIMIT_UPLOAD)
async def upload_avatar(request: Request, file: UploadFile = File(...)) -> dict[str, Any]:
    user = get_current_user(request)
    data = await read_upload_bounded(
        file,
        _MAX_AVATAR_BYTES,
        detail="Avatar images are capped at 500 KB — the app resizes before upload, so this usually means a raw file was sent directly.",
    )
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    ctype = _sniff_image(data)
    if not ctype:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, or WebP images are accepted")
    data_url = f"data:{ctype};base64,{base64.b64encode(data).decode('ascii')}"
    try:
        avatar_repo.set_avatar(user["email"], data_url, ctype, len(data))
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Avatar storage is temporarily unavailable")
    return {"ok": True, "avatar": data_url, "content_type": ctype}


@router.delete("")
def delete_avatar(request: Request) -> dict[str, Any]:
    user = get_current_user(request)
    try:
        deleted = avatar_repo.delete_avatar(user["email"])
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Avatar storage is temporarily unavailable")
    return {"ok": True, "deleted": deleted}
