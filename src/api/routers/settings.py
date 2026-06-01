"""
src/api/routers/settings.py
Thin HTTP layer for user settings.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.deps import get_current_user_id
from src.schemas.settings import SettingsResponse, SettingsUpdateRequest
from src.services.settings_service import get_settings, update_settings

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
def read_settings(user_id: str = Depends(get_current_user_id)) -> Dict[str, Any]:
    return get_settings(user_id=user_id)


@router.put("", response_model=SettingsResponse)
def write_settings(
    body: SettingsUpdateRequest,
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    return update_settings(data, user_id=user_id)


# ── Telegram notification preferences ────────────────────────────────────────

class TelegramOptInRequest(BaseModel):
    telegram_chat_id: Optional[str] = None  # optional — already set via /start bot command


class TelegramStatusResponse(BaseModel):
    opted_in: bool
    telegram_username: Optional[str] = None


@router.post("/telegram/opt-in", response_model=TelegramStatusResponse)
def telegram_opt_in(
    body: TelegramOptInRequest,
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    """Enable Telegram job-alert notifications for the authenticated user."""
    from src.services.telegram_notifications import opt_in, is_opted_in
    from src.repositories.profile_repo import get_profile

    ok = opt_in(user_id=user_id, telegram_chat_id=body.telegram_chat_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to enable Telegram notifications.")

    profile = get_profile(user_id)
    tg_username = getattr(profile, "telegram_username", None) if profile else None
    return {"opted_in": is_opted_in(user_id), "telegram_username": tg_username}


@router.post("/telegram/opt-out", response_model=TelegramStatusResponse)
def telegram_opt_out(user_id: str = Depends(get_current_user_id)) -> Dict[str, Any]:
    """Disable Telegram job-alert notifications for the authenticated user."""
    from src.services.telegram_notifications import opt_out, is_opted_in
    from src.repositories.profile_repo import get_profile

    ok = opt_out(user_id=user_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to disable Telegram notifications.")

    profile = get_profile(user_id)
    tg_username = getattr(profile, "telegram_username", None) if profile else None
    return {"opted_in": is_opted_in(user_id), "telegram_username": tg_username}


@router.get("/telegram/status", response_model=TelegramStatusResponse)
def telegram_status(user_id: str = Depends(get_current_user_id)) -> Dict[str, Any]:
    """Return the current Telegram notification opt-in status."""
    from src.services.telegram_notifications import is_opted_in
    from src.repositories.profile_repo import get_profile

    profile = get_profile(user_id)
    tg_username = getattr(profile, "telegram_username", None) if profile else None
    return {"opted_in": is_opted_in(user_id), "telegram_username": tg_username}
