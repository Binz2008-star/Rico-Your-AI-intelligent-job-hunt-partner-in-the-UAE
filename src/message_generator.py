from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def generate_message(job: Dict[str, Any], profile: Optional[Any] = None) -> str:
    """Generate a tailored cover letter for a job using verified profile identity.

    Falls back to a structured prompt if identity fields are incomplete,
    rather than returning the old one-line stub.
    """
    try:
        from src.cover_letter_writer import (
            CoverLetterIdentity,
            CoverLetterIdentityError,
            generate_cover_letter_with_identity,
        )

        # Build identity from profile if available
        name = _profile_str(profile, "name")
        location = _profile_city(profile)
        years_exp = _profile_num(profile, "years_experience")
        skills = _profile_list(profile, "skills")
        current_role = _profile_str(profile, "current_role")
        target_roles = _profile_list(profile, "target_roles")
        title_for_identity = current_role or (target_roles[0] if target_roles else None)

        # Require at minimum name and location to generate a real letter
        if name and location:
            identity = CoverLetterIdentity(
                name=name,
                location=location,
                title=title_for_identity,
                years_experience=years_exp,
                verified_strengths=skills[:6] if skills else [],
            )
            return generate_cover_letter_with_identity(job, identity)

        arabic = str(job.get("language") or "").strip().lower() in ("ar", "arabic")

        # Partial identity — return a structured prompt asking for missing fields
        title = job.get("title") or ("الوظيفة المعلن عنها" if arabic else "the advertised role")
        company = job.get("company") or ("الشركة" if arabic else "the company")

        if arabic:
            missing = []
            if not name:
                missing.append("اسمك الكامل")
            if not location:
                missing.append("مدينتك (مثل دبي أو أبوظبي)")
            missing_str = " و".join(missing)
            return (
                f"يمكنني كتابة خطاب تقديم مخصص لوظيفة **{title}** لدى **{company}**، "
                f"لكنني أحتاج إلى {missing_str} أولاً.\n\n"
                "زوّدني بهذه التفاصيل وسأكتبه فوراً."
            )

        missing = []
        if not name:
            missing.append("your full name")
        if not location:
            missing.append("your city (e.g. Dubai, Abu Dhabi)")
        missing_str = " and ".join(missing)
        return (
            f"I can write a tailored cover letter for **{title}** at **{company}**, "
            f"but I need {missing_str} first.\n\n"
            "Reply with those details and I'll generate it right away."
        )

    except Exception as exc:
        logger.warning("generate_message_failed job=%r err=%s", job.get("title"), exc)
        title = job.get("title") or "the role"
        company = job.get("company") or "the company"
        return (
            f"I can write a cover letter for **{title}** at **{company}**. "
            "Please share your name and location and I'll generate it now."
        )


# ── helpers ──────────────────────────────────────────────────────────────────

def _profile_str(profile: Any, key: str) -> str:
    if profile is None:
        return ""
    val = getattr(profile, key, None) or (profile.get(key) if isinstance(profile, dict) else None)
    return str(val).strip() if val else ""


def _profile_num(profile: Any, key: str):
    if profile is None:
        return None
    val = getattr(profile, key, None) or (profile.get(key) if isinstance(profile, dict) else None)
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _profile_list(profile: Any, key: str) -> list:
    if profile is None:
        return []
    val = getattr(profile, key, None) or (profile.get(key) if isinstance(profile, dict) else None)
    if isinstance(val, list):
        return [str(v) for v in val if v]
    if isinstance(val, str) and val.strip():
        return [s.strip() for s in val.split(",") if s.strip()]
    return []


def _profile_city(profile: Any) -> str:
    """Return the best available city string from profile."""
    cities = _profile_list(profile, "preferred_cities")
    if cities:
        return cities[0]
    loc = _profile_str(profile, "location") or _profile_str(profile, "city")
    return loc
