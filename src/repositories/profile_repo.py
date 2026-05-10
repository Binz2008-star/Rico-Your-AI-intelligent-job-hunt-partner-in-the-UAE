"""src/repositories/profile_repo.py
DB-backed user profile, preferences, and saved-search repository.

Read path: DB first (RicoDB.get_user_bundle), falls back to RicoMemoryStore
            when DB is unavailable or user has no DB record yet.
Write path: DB primary; mirrors to JSON store so existing JSON-dependent code
            continues to work during the transition.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.rico_agent import RicoAgentSettings, RicoProfile

logger = logging.getLogger(__name__)


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _db() -> Any:
    from src.rico_db import RicoDB
    db = RicoDB()
    return db if db.available else None


def _memory():
    from src.rico_memory import RicoMemoryStore
    return RicoMemoryStore()


def _bundle_to_profile(bundle: Dict[str, Any]) -> RicoProfile:
    """Convert a RicoDB.get_user_bundle() row into a RicoProfile."""
    pdata: Dict[str, Any] = bundle.get("profile") or {}
    sdata: Dict[str, Any] = bundle.get("settings") or {}

    settings = RicoAgentSettings(
        autonomy_level=sdata.get("autonomy_level", "recommend_only"),
        communication_style=sdata.get("communication_style", "professional"),
        match_strictness=sdata.get("match_strictness", "balanced"),
        can_reject_unsuitable_jobs=sdata.get("can_reject_unsuitable_jobs", True),
        can_learn_from_actions=sdata.get("can_learn_from_actions", True),
        can_personalize_recommendations=sdata.get("can_personalize_recommendations", True),
        can_generate_cover_letters=sdata.get("can_generate_cover_letters", True),
        can_generate_recruiter_messages=sdata.get("can_generate_recruiter_messages", True),
        can_prepare_interview_notes=sdata.get("can_prepare_interview_notes", True),
        can_send_follow_up_reminders=sdata.get("can_send_follow_up_reminders", True),
        can_create_weekly_report=sdata.get("can_create_weekly_report", True),
    )

    return RicoProfile(
        user_id=bundle.get("external_user_id") or str(bundle.get("id", "")),
        name=bundle.get("name"),
        email=bundle.get("email"),
        phone=bundle.get("phone"),
        telegram_username=bundle.get("telegram_username"),
        target_roles=pdata.get("target_roles") or [],
        preferred_cities=pdata.get("preferred_cities") or [],
        salary_expectation_aed=pdata.get("salary_expectation_aed"),
        minimum_salary_aed=pdata.get("minimum_salary_aed"),
        skills=pdata.get("skills") or [],
        industries=pdata.get("industries") or [],
        visa_status=pdata.get("visa_status"),
        notice_period=pdata.get("notice_period"),
        years_experience=pdata.get("years_experience"),
        current_role=pdata.get("current_role"),
        current_company=pdata.get("current_company"),
        linkedin_url=pdata.get("linkedin_url"),
        portfolio_url=pdata.get("portfolio_url"),
        deal_breakers=pdata.get("deal_breakers") or [],
        green_flags=pdata.get("green_flags") or [],
        red_flags=pdata.get("red_flags") or [],
        settings=settings,
    )


# ── Profile ────────────────────────────────────────────────────────────────────

def get_profile(user_id: str) -> Optional[RicoProfile]:
    """Load profile: DB first, JSON fallback."""
    db = _db()
    if db:
        try:
            bundle = db.get_user_bundle(user_id)
            if bundle:
                return _bundle_to_profile(bundle)
        except Exception:
            logger.exception("profile_repo: get_profile DB failed user_id=%s", user_id)

    return _memory().load_profile(user_id)


def upsert_profile(user_id: str, updates: Dict[str, Any]) -> RicoProfile:
    """Write profile to DB (primary) and JSON (fallback mirror).

    `updates` uses the same snake_case keys as RicoProfile fields.
    """
    # ── JSON mirror (always) — keeps existing code working ────────────────────
    mem = _memory()
    profile = mem.upsert_profile_from_dict(user_id=user_id, updates=dict(updates))

    # ── DB primary ─────────────────────────────────────────────────────────────
    db = _db()
    if not db:
        return profile

    try:
        user_payload: Dict[str, Any] = {
            "external_user_id": user_id,
            "name": updates.get("name"),
            "email": updates.get("email"),
            "phone": updates.get("phone"),
            "telegram_username": updates.get("telegram_username"),
        }
        user_row = db.upsert_user(user_payload)
        db_user_id = str(user_row["id"])

        # Fields that belong in rico_profiles JSONB
        profile_keys = {
            "target_roles", "preferred_cities", "salary_expectation_aed",
            "minimum_salary_aed", "skills", "industries", "visa_status",
            "notice_period", "years_experience", "current_role", "current_company",
            "linkedin_url", "portfolio_url", "deal_breakers", "green_flags",
            "red_flags", "cv_filename", "cv_status", "profile_creation_mode",
            "manual_profile_wizard_disabled",
        }
        profile_data = {k: v for k, v in updates.items() if k in profile_keys and v is not None}
        if profile_data:
            db.upsert_profile(db_user_id, profile_data)

        # Settings fields
        settings_keys = {
            "autonomy_level", "match_strictness", "communication_style",
            "can_reject_unsuitable_jobs", "can_learn_from_actions",
            "can_personalize_recommendations", "can_generate_cover_letters",
            "can_generate_recruiter_messages", "can_prepare_interview_notes",
            "can_send_follow_up_reminders", "can_create_weekly_report",
        }
        settings_data = updates.get("settings") or {}
        settings_data.update({k: v for k, v in updates.items() if k in settings_keys and v is not None})
        if settings_data:
            db.upsert_settings(db_user_id, settings_data)

    except Exception:
        logger.exception("profile_repo: upsert_profile DB failed user_id=%s", user_id)

    return profile


# ── Preferences ────────────────────────────────────────────────────────────────

def get_preferences(user_id: str) -> Dict[str, Any]:
    """Return agent/scoring/notification preferences from DB, or defaults."""
    db = _db()
    if db:
        try:
            bundle = db.get_user_bundle(user_id)
            if bundle and bundle.get("settings"):
                return dict(bundle["settings"])
        except Exception:
            logger.exception("profile_repo: get_preferences DB failed user_id=%s", user_id)

    profile = _memory().load_profile(user_id)
    if profile:
        from dataclasses import asdict
        return asdict(profile.settings)
    return {}


def save_preferences(user_id: str, prefs: Dict[str, Any]) -> None:
    """Persist preferences to DB; silently skips when DB unavailable."""
    db = _db()
    if not db:
        return
    try:
        user_row = db.upsert_user({"external_user_id": user_id})
        db.upsert_settings(str(user_row["id"]), prefs)
    except Exception:
        logger.exception("profile_repo: save_preferences DB failed user_id=%s", user_id)


# ── Saved searches ─────────────────────────────────────────────────────────────

def save_search(user_id: str, query: str, filters: Optional[Dict[str, Any]] = None) -> None:
    """Persist a saved search for a user. Silently skips when DB unavailable."""
    db = _db()
    if not db:
        logger.debug("profile_repo: save_search skipped — DB unavailable user_id=%s", user_id)
        return
    try:
        from psycopg2.extras import Json
        user_row = db.upsert_user({"external_user_id": user_id})
        db_user_id = str(user_row["id"])
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO rico_saved_searches (user_id, query, filters) VALUES (%s, %s, %s)",
                    (db_user_id, query.strip(), Json(filters or {})),
                )
            conn.commit()
        logger.info("profile_repo: saved_search persisted user_id=%s query=%r", user_id, query)
    except Exception:
        logger.exception("profile_repo: save_search DB failed user_id=%s", user_id)


def list_saved_searches(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Return saved searches for a user, newest first. Returns [] when DB unavailable."""
    db = _db()
    if not db:
        return []
    try:
        bundle = db.get_user_bundle(user_id)
        if not bundle:
            return []
        db_user_id = str(bundle["id"])
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, query, filters, created_at
                    FROM rico_saved_searches
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (db_user_id, limit),
                )
                rows = cur.fetchall()
        return [dict(r) for r in rows]
    except Exception:
        logger.exception("profile_repo: list_saved_searches DB failed user_id=%s", user_id)
        return []
