"""Small email delivery abstraction for backend notifications.

The SMTP implementation uses the existing EMAIL_USER / EMAIL_PASS settings.
Callers pass an explicit recipient so individual notification flows can choose
their own configured destination.
"""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage

logger = logging.getLogger(__name__)


def send_email(*, to_email: str, subject: str, body: str) -> bool:
    """Send a plain-text email. Returns False when delivery is not configured or fails."""
    email_user = os.getenv("EMAIL_USER", "").strip()
    email_pass = os.getenv("EMAIL_PASS", "").replace(" ", "").strip()

    if not email_user or not email_pass:
        logger.warning("email_delivery_not_configured recipient=%s", to_email)
        return False

    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = email_user
    msg["To"] = to_email

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(email_user, email_pass)
            server.send_message(msg)
        return True
    except Exception:
        logger.exception("email_delivery_failed recipient=%s subject=%s", to_email, subject)
        return False
