"""Tool registry for Rico OpenAI agent.

Maps Rico's tool-calling layer to the existing job automation modules.
All functions are defensive and additive.
"""

from __future__ import annotations

from typing import Any, Dict

from src.rico_memory import RicoMemoryStore
from src.rico_repo_adapter import RicoSystem, run_rico_for_default_profile


def search_jobs(query: str, city: str | None = None, limit: int = 10, **_: Any) -> Dict[str, Any]:
    """Run Rico's existing recommendation workflow.

    Current default uses the repo's existing profile until multi-user profile
    routing is fully wired into the OpenAI agent.
    """
    result = run_rico_for_default_profile()
    matches = result.get("matches", [])[:limit]
    if city:
        city_lower = city.lower()
        matches = [m for m in matches if city_lower in str(m.get("location", "")).lower()]
    return {
        "query": query,
        "city": city,
        "count": len(matches),
        "matches": matches,
    }


def update_preferences(user_id: str = "default", preferences: Dict[str, Any] | None = None, **_: Any) -> Dict[str, Any]:
    memory = RicoMemoryStore()
    profile = memory.upsert_profile_from_dict(user_id, preferences or {})
    return {
        "status": "updated",
        "user_id": user_id,
        "profile": profile.user_id,
    }


def write_cover_letter(job_id: str, tone: str = "professional", **_: Any) -> Dict[str, Any]:
    return {
        "status": "draft_ready_placeholder",
        "job_id": job_id,
        "tone": tone,
        "message": "Cover letter generation is routed through Rico's OpenAI layer and should be finalized after job lookup is connected.",
    }


def prepare_interview(job_id: str, **_: Any) -> Dict[str, Any]:
    return {
        "status": "prep_ready_placeholder",
        "job_id": job_id,
        "topics": [
            "role fit",
            "company motivation",
            "experience examples",
            "salary and notice period",
            "questions to ask recruiter",
        ],
    }


def track_application(job_id: str, status: str, user_id: str = "default", **_: Any) -> Dict[str, Any]:
    memory = RicoMemoryStore()
    memory.record_learning_signal(user_id, job_id, f"application_{status}")
    return {
        "status": "tracked",
        "user_id": user_id,
        "job_id": job_id,
        "application_status": status,
    }


def get_rico_tools() -> Dict[str, Any]:
    return {
        "search_jobs": search_jobs,
        "update_preferences": update_preferences,
        "write_cover_letter": write_cover_letter,
        "prepare_interview": prepare_interview,
        "track_application": track_application,
    }
