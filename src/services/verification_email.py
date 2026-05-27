"""Email delivery for the email-verification flow."""
from __future__ import annotations

import logging
import os

from src.services.mailer import send_email

logger = logging.getLogger(__name__)


def _verify_base_url() -> str:
    return os.getenv("RESET_BASE_URL", "http://localhost:3000").rstrip("/")


def send_verification_email(user_email: str, token: str) -> None:
    """Best-effort verification email. Never raises to the registration flow."""
    verify_url = f"{_verify_base_url()}/verify-email?token={token}"

    subject = "Verify your RicoHunt email address"
    body = "\n".join([
        "Welcome to RicoHunt!",
        "",
        "Please verify your email address by clicking the link below:",
        "",
        verify_url,
        "",
        "This link expires in 24 hours and can only be used once.",
        "",
        "If you did not create a RicoHunt account, you can ignore this email.",
    ])

    ok = send_email(to_email=user_email, subject=subject, body=body)
    if not ok:
        logger.warning(
            "verification_email_not_sent recipient=%s (email delivery not configured or failed)",
            user_email,
        )
