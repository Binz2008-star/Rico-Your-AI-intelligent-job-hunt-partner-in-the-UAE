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
    # Support both legacy and new SMTP config
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    smtp_user = os.getenv("SMTP_USER", os.getenv("EMAIL_USER", "")).strip()
    smtp_password = os.getenv("SMTP_PASSWORD", os.getenv("EMAIL_PASS", "")).replace(" ", "").strip()

    if not smtp_user or not smtp_password:
        logger.warning("email_delivery_not_configured recipient=%s", to_email)
        return False

    # Use configured sender or fallback to support email
    email_from = os.getenv("EMAIL_FROM", os.getenv("SUPPORT_EMAIL", "info@ricohunt.com"))
    email_from_name = os.getenv("EMAIL_FROM_NAME", "Rico Hunt")

    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = f"{email_from_name} <{email_from}>"
    msg["To"] = to_email

    try:
        context = ssl.create_default_context()
        # Use SSL for port 465, STARTTLS for port 587
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=10) as server:
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.starttls(context=context)
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        return True
    except Exception:
        logger.exception("email_delivery_failed recipient=%s subject=%s", to_email, subject)
        return False
