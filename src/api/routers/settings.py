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
from src.services.matching_guardrails import build_matching_guardrail_warnings
from src.services.settings_service import get_settings, update_settings

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


def _load_profile_for_guardrails(user_id: Optional[str]) -> Any | None:
    try:
        from src.repositories.profile_repo import get_profile

        return get_profile(user_id) if user_id else None
    except Exception:
        return None


def _with_guardrail_warnings(settings: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
    profile = _load_profile_for_guardrails(user_id)
    return {
        **settings,
        "warnings": build_matching_guardrail_warnings(
            settings=settings,
            profile=profile,
        ),
    }


@router.get("", response_model=SettingsResponse)
def read_settings(user_id: str = Depends(get_current_user_id)) -> Dict[str, Any]:
    settings = get_settings(user_id=user_id)
    return _with_guardrail_warnings(settings, user_id)


@router.put("", response_model=SettingsResponse)
def write_settings(
    body: SettingsUpdateRequest,
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    # Durable-truth contract (#764): if the canonical DB write fails, return a
    # retryable 503 instead of a 200 that echoes stale/default state.
    try:
        settings = update_settings(data, user_id=user_id)
    except RuntimeError:
        raise HTTPException(
            status_code=503,
            detail="Settings could not be saved. Please try again.",
        )
    return _with_guardrail_warnings(settings, user_id)


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


# ── Email job-alert preferences ──────────────────────────────────────────────

class EmailOptInRequest(BaseModel):
    frequency: Optional[str] = None  # "daily" | "weekly"; defaults to daily


class EmailStatusResponse(BaseModel):
    opted_in: bool
    frequency: str


@router.post("/email/opt-in", response_model=EmailStatusResponse)
def email_opt_in(
    body: EmailOptInRequest,
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    """Enable email job-alert notifications for the authenticated user."""
    from src.services.email_notifications import opt_in, is_opted_in, get_frequency

    ok = opt_in(user_id=user_id, frequency=body.frequency)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to enable email alerts.")
    return {"opted_in": is_opted_in(user_id), "frequency": get_frequency(user_id)}


@router.post("/email/opt-out", response_model=EmailStatusResponse)
def email_opt_out(user_id: str = Depends(get_current_user_id)) -> Dict[str, Any]:
    """Disable email job-alert notifications for the authenticated user."""
    from src.services.email_notifications import opt_out, is_opted_in, get_frequency

    ok = opt_out(user_id=user_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to disable email alerts.")
    return {"opted_in": is_opted_in(user_id), "frequency": get_frequency(user_id)}


@router.get("/email/status", response_model=EmailStatusResponse)
def email_status(user_id: str = Depends(get_current_user_id)) -> Dict[str, Any]:
    """Return the current email job-alert opt-in status and cadence."""
    from src.services.email_notifications import is_opted_in, get_frequency

    return {"opted_in": is_opted_in(user_id), "frequency": get_frequency(user_id)}
