"""
src/api/routers/journey.py
Career journey snapshot + daily plan for the authenticated user.

Read-only: derives the journey stage and today's prioritized actions from the
user's canonical application data (applications_repo.get_stats). No writes, no
fake data — DB unavailability surfaces as 503 (the repo raises), never as an
empty-but-plausible snapshot.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from src.agent.context.journey_state import derive_state, generate_daily_plan
from src.api.deps import get_current_user_id
from src.repositories.applications_repo import get_stats

router = APIRouter(prefix="/api/v1/journey", tags=["journey"])


@router.get("/today")
def journey_today(user_id: str = Depends(get_current_user_id)) -> Dict[str, Any]:
    """Return the user's derived journey snapshot and today's action plan."""
    stats = get_stats(user_id=user_id)
    by_status = stats.get("by_status", {}) or {}

    def _count(key: str) -> int:
        value = by_status.get(key, 0)
        return value if isinstance(value, int) and value >= 0 else 0

    try:
        state = derive_state(
            user_id=user_id,
            saved_count=_count("saved"),
            prepared_count=_count("prepared"),
            applied_count=_count("applied"),
            follow_up_due_count=_count("follow_up_due"),
            interviewing_count=_count("interview"),
            offer_count=_count("offer"),
        )
        plan = generate_daily_plan(state)
    except ValueError as exc:
        # Canonical counts failed the module's fail-fast validation — surface
        # a retryable server error rather than a fabricated snapshot.
        raise HTTPException(status_code=500, detail=f"journey derivation failed: {exc}")

    return {"journey": state.to_dict(), "plan": plan.to_dict()}
