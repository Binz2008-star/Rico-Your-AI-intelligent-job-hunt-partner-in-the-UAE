"""Small email delivery abstraction for backend notifications.

Supports a typed provider model controlled by ``EMAIL_PROVIDER``:

- ``resend``   — use Resend HTTPS API only; missing ``RESEND_API_KEY``
                 returns False immediately; never falls back to SMTP.
- ``smtp``     — use the existing SMTP implementation explicitly;
                 intended for local/non-Railway compatibility only.
- ``disabled`` — return False immediately with a sanitized warning.

Provider selection is fail-closed:

- Invalid ``EMAIL_PROVIDER`` value → immediate False, no SMTP, no HTTP.
- Unset ``EMAIL_PROVIDER`` in production (Railway) → immediate False, no SMTP.
- Unset ``EMAIL_PROVIDER`` outside production → defaults to ``smtp``
  for backward compatibility with local-dev and non-Railway environments.

Callers pass an explicit recipient so individual notification flows can
choose their own configured destination. The public caller contract
``send_email(*, to_email, subject, body, html=None) -> bool`` is preserved
across all providers.
"""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
import uuid
from email.message import EmailMessage
from typing import Literal

import httpx

from src.log_privacy import safe_exc, user_ref

logger = logging.getLogger(__name__)

EmailProvider = Literal["resend", "smtp", "disabled"]

_RESEND_URL = "https://api.resend.com/emails"
# Strict timeout budget: connect 3s, read 5s, write 5s, pool 2s.
_RESEND_TIMEOUT = httpx.Timeout(connect=3.0, read=5.0, write=5.0, pool=2.0)
# Maximum attempts: initial + one retry.
_MAX_ATTEMPTS = 2
# Backoff between attempts (seconds).
_RETRY_BACKOFF = 0.5


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------

def _is_production() -> bool:
    """True when running on a known production platform (Railway)."""
    return bool(os.getenv("RAILWAY_REPLICA_ID", "").strip())


def _resolve_provider() -> EmailProvider | None:
    """Read and validate ``EMAIL_PROVIDER`` from the environment.

    Returns one of ``resend``, ``smtp``, ``disabled``, or ``None`` when
    the configuration is unsafe (invalid value, or unset in production).

    - Invalid value → ``None`` (fail-closed, no SMTP fallback)
    - Unset in production → ``None`` (fail-closed, no SMTP fallback)
    - Unset outside production → ``smtp`` (backward compatibility)
    """
    raw = os.getenv("EMAIL_PROVIDER", "").strip().lower()
    if not raw:
        if _is_production():
            return None
        return "smtp"
    if raw in ("resend", "smtp", "disabled"):
        return raw  # type: ignore[return-value]
    return None


# ---------------------------------------------------------------------------
# Sender resolution (shared)
# ---------------------------------------------------------------------------

def _resolve_sender() -> tuple[str, str]:
    """Return ``(from_address, from_name)`` from env, with safe defaults."""
    email_from = os.getenv("EMAIL_FROM", os.getenv("SUPPORT_EMAIL", "info@ricohunt.com"))
    email_from_name = os.getenv("EMAIL_FROM_NAME", "Rico Hunt")
    return email_from, email_from_name


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def send_email(
    *,
    to_email: str,
    subject: str,
    body: str,
    html: str | None = None,
) -> bool:
    """Send an email. Returns False when delivery is not configured or fails.

    ``body`` is always the plain-text part. When ``html`` is provided the
    message is sent as multipart/alternative (plain-text + HTML) so clients
    that block or can't render HTML still show the text fallback. Existing
    callers that pass no ``html`` keep sending plain text unchanged.

    The provider is selected by ``EMAIL_PROVIDER`` (resend|smtp|disabled).
    Never raises — failures are logged and returned as ``False``.
    """
    provider = _resolve_provider()
    if provider is None:
        logger.warning(
            "email_delivery_not_configured recipient=%s reason=invalid_or_unset_provider",
            user_ref(to_email),
        )
        return False
    if provider == "disabled":
        logger.warning(
            "email_delivery_disabled recipient=%s",
            user_ref(to_email),
        )
        return False
    if provider == "resend":
        return _send_via_resend(to_email=to_email, subject=subject, body=body, html=html)
    return _send_via_smtp(to_email=to_email, subject=subject, body=body, html=html)


# ---------------------------------------------------------------------------
# Resend HTTPS adapter
# ---------------------------------------------------------------------------

def _send_via_resend(
    *,
    to_email: str,
    subject: str,
    body: str,
    html: str | None,
) -> bool:
    """Send via Resend HTTPS API. Never falls back to SMTP."""
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    if not api_key:
        logger.warning(
            "email_delivery_not_configured provider=resend recipient=%s reason=missing_api_key",
            user_ref(to_email),
        )
        return False

    email_from, email_from_name = _resolve_sender()
    from_header = f"{email_from_name} <{email_from}>"

    payload: dict[str, object] = {
        "from": from_header,
        "to": [to_email],
        "subject": subject,
        "text": body,
    }
    if html:
        payload["html"] = html

    idempotency_key = str(uuid.uuid4())
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Idempotency-Key": idempotency_key,
    }

    last_status: int | None = None

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            resp = httpx.post(
                _RESEND_URL,
                json=payload,
                headers=headers,
                timeout=_RESEND_TIMEOUT,
            )
            last_status = resp.status_code

            if 200 <= resp.status_code < 300:
                logger.info(
                    "email_delivery_sent provider=resend recipient=%s status=%d attempt=%d",
                    user_ref(to_email),
                    resp.status_code,
                    attempt,
                )
                return True

            # Determine whether to retry
            should_retry = _should_retry_status(resp.status_code)
            if should_retry and attempt < _MAX_ATTEMPTS:
                logger.warning(
                    "email_delivery_retry provider=resend recipient=%s status=%d attempt=%d",
                    user_ref(to_email),
                    resp.status_code,
                    attempt,
                )
                import time

                time.sleep(_RETRY_BACKOFF)
                continue

            # Permanent failure — log sanitized error, do not retry
            logger.error(
                "email_delivery_failed provider=resend recipient=%s status=%d attempt=%d permanent=true",
                user_ref(to_email),
                resp.status_code,
                attempt,
            )
            return False

        except (httpx.TimeoutException, httpx.TransportError) as exc:
            if attempt < _MAX_ATTEMPTS:
                logger.warning(
                    "email_delivery_retry provider=resend recipient=%s error=%s attempt=%d",
                    user_ref(to_email),
                    type(exc).__name__,
                    attempt,
                )
                import time

                time.sleep(_RETRY_BACKOFF)
                continue
            logger.error(
                "email_delivery_failed provider=resend recipient=%s error=%s attempt=%d permanent=false_exhausted",
                user_ref(to_email),
                type(exc).__name__,
                attempt,
            )
            return False

        except Exception as exc:
            # Unexpected exception — never log str(exc) which may carry secrets
            logger.error(
                "email_delivery_failed provider=resend recipient=%s error=%s attempt=%d",
                user_ref(to_email),
                safe_exc(exc),
                attempt,
            )
            return False

    # Should not reach here, but guard defensively
    logger.error(
        "email_delivery_failed provider=resend recipient=%s status=%s attempts_exhausted",
        user_ref(to_email),
        last_status,
    )
    return False


def _should_retry_status(status: int) -> bool:
    """Retry only on 429 and 5xx. Never retry on permanent 4xx."""
    if status == 429:
        return True
    if 500 <= status < 600:
        return True
    return False


# ---------------------------------------------------------------------------
# SMTP provider (legacy preservation — local/non-Railway only)
# ---------------------------------------------------------------------------

def _send_via_smtp(
    *,
    to_email: str,
    subject: str,
    body: str,
    html: str | None,
) -> bool:
    """Send via SMTP. Preserves the original implementation for local/dev use."""
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    smtp_user = os.getenv("SMTP_USER", os.getenv("EMAIL_USER", "")).strip()
    smtp_password = os.getenv("SMTP_PASSWORD", os.getenv("EMAIL_PASS", "")).replace(" ", "").strip()

    if not smtp_user or not smtp_password:
        logger.warning(
            "email_delivery_not_configured provider=smtp recipient=%s",
            user_ref(to_email),
        )
        return False

    email_from, email_from_name = _resolve_sender()

    msg = EmailMessage()
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")
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
        logger.info(
            "email_delivery_sent provider=smtp recipient=%s",
            user_ref(to_email),
        )
        return True
    except Exception as exc:
        logger.error(
            "email_delivery_failed provider=smtp recipient=%s error=%s",
            user_ref(to_email),
            safe_exc(exc),
        )
        return False
