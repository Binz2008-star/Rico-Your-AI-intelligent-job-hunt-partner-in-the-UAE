"""
src/api/routers/settings.py
Thin HTTP layer for user settings.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.deps import get_current_user_id
from src.schemas.settings import SettingsResponse, SettingsUpdateRequest
from src.services.settings_service import get_settings, update_settings

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


def _exclude_keyword_role_conflicts(
    user_id: Optional[str], exclude_keywords: List[str]
) -> List[str]:
    """Warn when an excluded keyword overlaps one of the user's saved target roles.

    e.g. excluding "manager" while targeting "Environmental Manager" would otherwise
    silently filter out the user's own target role. The search layer suppresses the
    exclusion for genuine role matches, but the user should still be told so they can
    fix the conflicting setting. Returns an empty list when there is no conflict.
    """
    if not exclude_keywords:
        return []
    try:
        from src.repositories.profile_repo import get_profile

        profile = get_profile(user_id) if user_id else None
    except Exception:
        return []
    if not profile:
        return []
    target_roles = getattr(profile, "target_roles", None) or []

    warnings: List[str] = []
    seen: set[str] = set()
    for raw_role in target_roles:
        role = str(raw_role or "").strip()
        role_l = role.lower()
        if not role_l:
            continue
        role_tokens = {t for t in re.split(r"[^a-z0-9+#]+", role_l) if t}
        for kw in exclude_keywords:
            k = str(kw or "").strip().lower()
            if not k:
                continue
            if (k in role_tokens or (" " in k and k in role_l)) and k not in seen:
                seen.add(k)
                warnings.append(
                    f'Excluded keyword "{k}" overlaps your target role "{role}". '
                    f'Rico still surfaces "{role}" matches but filters other "{k}" results.'
                )
    return warnings


@router.get("", response_model=SettingsResponse)
def read_settings(user_id: str = Depends(get_current_user_id)) -> Dict[str, Any]:
    settings = get_settings(user_id=user_id)
    warnings = _exclude_keyword_role_conflicts(
        user_id, settings.get("exclude_keywords") or []
    )
    if warnings:
        return {**settings, "warnings": warnings}
    return settings


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
