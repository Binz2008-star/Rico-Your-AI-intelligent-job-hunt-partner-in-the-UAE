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


def build_signup_notification_body(
    *,
    name: str | None,
    email: str,
    user_id: int | str,
    created_at: Any,
    plan: str | None = None,
) -> str:
    display_name = name.strip() if isinstance(name, str) and name.strip() else "Not provided"
    display_plan = plan.strip() if isinstance(plan, str) and plan.strip() else "free"

    return "\n".join(
        [
            "New user registered on RicoHunt.",
            "",
            f"Name: {display_name}",
            f"Email: {email}",
            f"User ID: {user_id}",
            f"Signup time: {_format_created_at(created_at)}",
            f"Plan: {display_plan}",
            "Source: website",
        ]
    )


def send_admin_signup_notification(*, user: Any, name: str | None = None, plan: str | None = None) -> None:
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
        )
        ok = send_email(
            to_email=recipient,
            subject="New RicoHunt signup",
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
