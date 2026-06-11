"""
src/api/routers/onboarding.py

POST /api/v1/onboarding/submit — persist structured onboarding answers directly
to the user profile via upsert_profile(). Bypasses NLP round-trip; the frontend
collects answers in structured form so there is no need to parse natural language.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.api.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])


class OnboardingSubmitRequest(BaseModel):
    target_roles: Optional[List[str]] = Field(default=None)
    preferred_cities: Optional[List[str]] = Field(default=None)
    salary_expectation_aed: Optional[float] = Field(default=None, ge=0)
    years_experience: Optional[float] = Field(default=None, ge=0)
    current_role: Optional[str] = Field(default=None, max_length=200)
    skills: Optional[List[str]] = Field(default=None)


@router.post("/submit")
def onboarding_submit(request: Request, body: OnboardingSubmitRequest) -> Dict[str, Any]:
    user = get_current_user(request)
    user_id: str = user["email"]

    updates: Dict[str, Any] = {}
    if body.target_roles is not None:
        from src.role_normalization import validate_and_normalize_target_roles
        updates["target_roles"] = validate_and_normalize_target_roles(body.target_roles)
    if body.preferred_cities is not None:
        updates["preferred_cities"] = [c.strip() for c in body.preferred_cities if c.strip()]
    if body.salary_expectation_aed is not None:
        updates["salary_expectation_aed"] = body.salary_expectation_aed
    if body.years_experience is not None:
        updates["years_experience"] = body.years_experience
    if body.current_role is not None:
        updates["current_role"] = body.current_role.strip()
    if body.skills is not None:
        from src.role_normalization import validate_and_normalize_skills
        updates["skills"] = validate_and_normalize_skills(body.skills)

    if not updates:
        logger.info("onboarding_submit: empty submission rejected user_id=%s", user_id)
        raise HTTPException(
            status_code=422,
            detail="At least one onboarding field is required.",
        )

    from src.repositories.profile_repo import get_profile, upsert_profile
    upsert_profile(user_id, updates)
    logger.info("onboarding_submit: profile updated user_id=%s fields=%s", user_id, list(updates.keys()))

    # Re-read the merged profile and gate onboarding status on the shared
    # minimum-career-profile rule — never on mere profile existence.
    from src.models.onboarding import ONBOARDING_IN_PROGRESS
    from src.repositories.onboarding_repo import mark_onboarding_complete, set_onboarding_status
    from src.services.profile_context_resolver import (
        evaluate_minimum_profile,
        has_career_profile_data,
        resolve_profile_context,
    )

    ctx = resolve_profile_context(user_id, get_profile(user_id))
    min_complete, missing_fields = evaluate_minimum_profile(ctx)
    if min_complete:
        mark_onboarding_complete(user_id)
        status = "completed"
    else:
        set_onboarding_status(user_id, ONBOARDING_IN_PROGRESS)
        status = "in_progress"
    logger.info(
        "onboarding_submit: user_id=%s status=%s missing_fields=%s", user_id, status, missing_fields
    )

    return {
        "status": status,
        "updated_fields": list(updates.keys()),
        "missing_fields": missing_fields,
        "profile_exists": has_career_profile_data(ctx),
        "profile_completeness": ctx.completion_score,
    }
