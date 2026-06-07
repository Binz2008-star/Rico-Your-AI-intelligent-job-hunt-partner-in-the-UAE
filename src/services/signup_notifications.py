"""Admin notifications for successful user signups."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from src.services.mailer import send_email

logger = logging.getLogger(__name__)

DEFAULT_SIGNUP_NOTIFICATION_EMAIL = "info@ricohunt.com"


def _notifications_enabled() -> bool:
    return os.getenv("ENABLE_SIGNUP_EMAIL_NOTIFICATIONS", "true").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _admin_recipient() -> str:
    return (
        os.getenv("ADMIN_SIGNUP_NOTIFICATION_EMAIL", DEFAULT_SIGNUP_NOTIFICATION_EMAIL).strip()
        or DEFAULT_SIGNUP_NOTIFICATION_EMAIL
    )


def _format_created_at(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if value:
        return str(value)
    return datetime.now(timezone.utc).isoformat()


def _calculate_profile_completeness(profile: dict[str, Any] | None) -> tuple[int, str]:
    """Calculate profile completeness percentage and recommended action based on critical field priority."""
    if not profile:
        return 0, "Ask user to complete profile"

    key_fields = [
        "target_roles",
        "preferred_cities",
        "years_experience",
        "current_role",
        "skills",
        "cv_filename",
    ]

    filled = sum(1 for field in key_fields if profile.get(field))
    percentage = int((filled / len(key_fields)) * 100)

    # Priority-based recommended action
    if not profile.get("cv_filename"):
        action = "Ask user to upload CV"
    elif not profile.get("target_roles") or (isinstance(profile.get("target_roles"), list) and not profile.get("target_roles")):
        action = "Ask user to add target roles"
    elif not profile.get("preferred_cities") or (isinstance(profile.get("preferred_cities"), list) and not profile.get("preferred_cities")):
        action = "Ask user to add preferred UAE cities"
    elif percentage < 80:
        action = "Ask user to complete remaining profile details"
    else:
        action = "Ready for job matching"

    return percentage, action


def build_signup_notification_body(
    *,
    name: str | None,
    email: str,
    user_id: int | str,
    created_at: Any,
    plan: str | None = None,
    profile: dict[str, Any] | None = None,
) -> str:
    display_name = name.strip() if isinstance(name, str) and name.strip() else "Not provided"
    display_plan = plan.strip() if isinstance(plan, str) and plan.strip() else "free"

    # Extract profile fields with "Not provided" fallback
    country = profile.get("country") or "Not provided" if profile else "Not provided"
    city = profile.get("preferred_cities") if profile else None
    if city and isinstance(city, list) and city:
        city = ", ".join(city[:3])  # Show up to 3 cities
    else:
        city = "Not provided"

    target_roles = profile.get("target_roles") if profile else None
    if target_roles and isinstance(target_roles, list) and target_roles:
        target_roles = ", ".join(target_roles[:3])  # Show up to 3 roles
    else:
        target_roles = "Not provided"

    industry = profile.get("industries") if profile else None
    if industry and isinstance(industry, list) and industry:
        industry = ", ".join(industry[:2])
    else:
        industry = "Not provided"

    years_experience = profile.get("years_experience") if profile else None
    years_display = f"{years_experience} years" if years_experience else "Not provided"

    cv_uploaded = "Yes" if profile and profile.get("cv_filename") else "No"

    profile_completeness, recommended_action = _calculate_profile_completeness(profile)

    return "\n".join(
        [
            "New user registered on RicoHunt.",
            "",
            "Account:",
            f"- Name: {display_name}",
            f"- Email: {email}",
            f"- User ID: {user_id}",
            f"- Plan: {display_plan}",
            f"- Signup source: website",
            f"- Signup time: {_format_created_at(created_at)}",
            "",
            "Location & Language:",
            f"- Country: {country}",
            f"- City: {city}",
            f"- Preferred language: Not provided",
            "",
            "Career Profile:",
            f"- Target roles: {target_roles}",
            f"- Industry: {industry}",
            f"- Years of experience: {years_display}",
            f"- CV uploaded: {cv_uploaded}",
            f"- Profile completeness: {profile_completeness}%",
            "",
            "Recommended next action:",
            f"- {recommended_action}",
        ]
    )


def send_admin_signup_notification(*, user: Any, name: str | None = None, plan: str | None = None, profile: dict[str, Any] | None = None) -> None:
    """Best-effort notification. Never raises to the registration flow."""
    if not _notifications_enabled():
        return

    recipient = _admin_recipient()
    user_id = getattr(user, "id", "unknown")
    try:
        body = build_signup_notification_body(
            name=name,
            email=getattr(user, "email"),
            user_id=user_id,
            created_at=getattr(user, "created_at", None),
            plan=plan,
            profile=profile,
        )
        display_name = name.strip() if isinstance(name, str) and name.strip() else getattr(user, "email", "unknown")
        ok = send_email(
            to_email=recipient,
            subject=f"New RicoHunt signup — {display_name}",
            body=body,
        )
        if not ok:
            logger.warning(
                "signup_notification_email_not_sent user_id=%s recipient=%s",
                user_id,
                recipient,
            )
    except Exception:
        logger.exception(
            "signup_notification_email_failed user_id=%s recipient=%s",
            user_id,
            recipient,
        )
