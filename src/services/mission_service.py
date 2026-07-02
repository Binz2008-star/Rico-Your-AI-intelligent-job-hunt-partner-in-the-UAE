"""src/services/mission_service.py
Mission Engine — computes MissionState from existing profile and pipeline data.

No new DB tables.  Reads only from:
  - profile_repo.get_profile()          → target_roles, preferred_cities, cv_filename
  - applications_repo.get_stats()       → jobs saved + applications sent

Progress score: 4 binary factors, 25 pts each.
  1. cv_uploaded       — cv_filename is present in the profile
  2. roles_set         — at least one target_role on the profile
  3. locations_set     — at least one preferred_city on the profile
  4. pipeline_active   — at least one job saved or application sent

Next recommendation: determined by the first missing factor in priority order.
Never raises; degrades gracefully when data sources are unavailable.
"""
from __future__ import annotations

import logging
from typing import Any

from src.schemas.mission import MissionState

logger = logging.getLogger(__name__)

# Points awarded per completed factor (must sum to 100)
_FACTOR_POINTS = 25


def _safe_get_profile(user_id: str) -> Any:
    try:
        from src.repositories import profile_repo
        return profile_repo.get_profile(user_id)
    except Exception:
        logger.exception("mission_service: profile load failed user_id=%s", user_id)
        return None


def _safe_get_stats(user_id: str) -> dict[str, int]:
    try:
        from src.repositories import applications_repo
        stats = applications_repo.get_stats(user_id=user_id)
        return {
            "total": int(stats.get("total", 0)),
            "applied": int(stats.get("applied", 0)),
            "saved": int(stats.get("saved", 0)),
        }
    except Exception:
        logger.warning("mission_service: stats unavailable user_id=%s", user_id)
        return {"total": 0, "applied": 0, "saved": 0}


def _build_goal(target_roles: list[str], target_locations: list[str]) -> str:
    role_part = target_roles[0] if target_roles else None
    location_part = target_locations[0] if target_locations else None
    if role_part and location_part:
        return f"Find {role_part} role in {location_part}"
    if role_part:
        return f"Find {role_part} role in UAE"
    if location_part:
        return f"Find a job in {location_part}"
    return "Define your job search mission"


def _next_recommendation(missing: list[str]) -> tuple[str, str | None]:
    """Return (next_recommendation, blocking_reason) from the first missing factor."""
    if not missing:
        return (
            "You're on track — keep applying and Rico will surface the best opportunities.",
            None,
        )
    first = missing[0]
    if first == "cv_uploaded":
        return (
            "Upload your CV so Rico can match you to the right jobs.",
            "CV is missing — Rico can't score job matches without it.",
        )
    if first == "roles_set":
        return (
            "Tell Rico which roles you're targeting (e.g. 'Project Manager', 'Operations Director').",
            "No target role set — Rico doesn't know what to search for.",
        )
    if first == "locations_set":
        return (
            "Set your preferred UAE cities (e.g. Dubai, Abu Dhabi) to narrow your search.",
            None,
        )
    if first == "pipeline_active":
        return (
            "Ask Rico to search for jobs — save the ones that interest you to build your pipeline.",
            None,
        )
    return ("Talk to Rico to continue your job search.", None)


def compute_mission(user_id: str) -> MissionState:
    """Compute the current MissionState for a user.

    Never raises. Returns a degraded MissionState on any data failure.
    """
    profile = _safe_get_profile(user_id)
    stats = _safe_get_stats(user_id)

    # Extract profile fields safely
    target_roles: list[str] = []
    target_locations: list[str] = []
    cv_filename: str | None = None

    if profile is not None:
        target_roles = list(getattr(profile, "target_roles", None) or [])
        target_locations = list(getattr(profile, "preferred_cities", None) or [])
        cv_filename = getattr(profile, "cv_filename", None)

    jobs_total: int = stats["total"]
    applications_sent: int = stats["applied"]
    jobs_saved: int = stats["saved"]

    # 4 binary factors → progress_score
    factors: list[tuple[str, bool]] = [
        ("cv_uploaded", bool(cv_filename)),
        ("roles_set", len(target_roles) > 0),
        ("locations_set", len(target_locations) > 0),
        ("pipeline_active", jobs_total > 0),
    ]
    missing = [name for name, present in factors if not present]
    progress_score = (len(factors) - len(missing)) * _FACTOR_POINTS

    cv_status = "uploaded" if cv_filename else "missing"
    goal = _build_goal(target_roles, target_locations)
    next_rec, blocking = _next_recommendation(missing)

    return MissionState(
        goal=goal,
        target_roles=target_roles,
        target_locations=target_locations,
        cv_status=cv_status,
        jobs_saved=jobs_saved,
        applications_sent=applications_sent,
        progress_score=progress_score,
        missing_factors=missing,
        next_recommendation=next_rec,
        blocking_reason=blocking,
    )
