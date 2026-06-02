"""Email delivery for password reset flow."""
from __future__ import annotations

import logging
import os

from src.services.mailer import send_email

logger = logging.getLogger(__name__)


def _reset_base_url() -> str:
    return os.getenv("RESET_BASE_URL", "http://localhost:3000").rstrip("/")


def send_password_reset_email(user_email: str, token: str) -> bool:
    """
    Send password reset email to user.
    Returns True if email was sent successfully, False otherwise.
    Never raises - failures are logged and swallowed for security.
    """
    reset_url = f"{_reset_base_url()}/reset-password?token={token}"

    subject = "Reset your RicoHunt password"
    body = "\n".join([
        "Hello,",
        "",
        "You requested a password reset for your RicoHunt account.",
        "",
        "Click the link below to reset your password:",
        "",
        reset_url,
        "",
        "This link expires in 24 hours and can only be used once.",
        "",
        "If you did not request this reset, you can ignore this email.",
        "",
        "Thanks,",
        "The RicoHunt Team",
    ])

    try:
        ok = send_email(to_email=user_email, subject=subject, body=body)
        if not ok:
            logger.warning("password_reset_email_delivery_failed")
        else:
            logger.info("password_reset_email_sent")
        return ok
    except Exception:
        logger.exception("password_reset_email_exception")
        return False
