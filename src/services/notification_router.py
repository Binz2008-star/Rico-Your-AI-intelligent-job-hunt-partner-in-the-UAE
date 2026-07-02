"""src/services/notification_router.py

Audience-aware Telegram notification routing for Rico.

Why this exists
---------------
Rico's Telegram bot serves two very different audiences:

* End users — people hunting for jobs. They must only ever see job/career
  notifications (matched jobs, saved jobs, apply-link status, follow-up and
  interview reminders, CV/profile nudges, subscription/account messages).

* Operators / developers — the people running the platform. They need the
  technical signals (CI failures, deploy status, backend/database health,
  AI-provider quota alerts, errors and logs).

Historically every broadcast went to a single ``TELEGRAM_CHAT_ID``, so
operational alerts (e.g. "Workflow Failed", "session missing on runner")
leaked into the user-facing chat. This module classifies every notification
by audience and routes admin/dev notifications to a dedicated admin channel.

Notification types
------------------
* ``user_job``      — matched/saved jobs, apply-link status, follow-up &
                      interview reminders, CV/profile completion nudges.
* ``user_account``  — subscription/account messages, user-requested updates.
* ``admin_ci``      — GitHub commits, PR status, CI/test results.
* ``admin_deploy``  — Vercel / Render / deploy status.
* ``admin_error``   — errors, exceptions, technical logs, runner/session issues.
* ``admin_provider``— AI-provider quota / health alerts (OpenAI, DeepSeek, HF).

Hard rules
----------
1. ``admin_*`` notifications must NEVER be delivered to a user chat.
2. If no admin/dev channel is configured, an ``admin_*`` notification is
   logged and dropped — it is never "helpfully" redirected to the user chat.
3. ``user_*`` notifications keep their existing behaviour (default shared
   user chat ``TELEGRAM_CHAT_ID`` or an explicit per-user ``chat_id``).
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_TELEGRAM_MAX_CHARS = 4096

# ── Notification type taxonomy ────────────────────────────────────────────────
USER_JOB = "user_job"
USER_ACCOUNT = "user_account"
ADMIN_CI = "admin_ci"
ADMIN_DEPLOY = "admin_deploy"
ADMIN_ERROR = "admin_error"
ADMIN_PROVIDER = "admin_provider"

USER_NOTIFICATION_TYPES = frozenset({USER_JOB, USER_ACCOUNT})
ADMIN_NOTIFICATION_TYPES = frozenset(
    {ADMIN_CI, ADMIN_DEPLOY, ADMIN_ERROR, ADMIN_PROVIDER}
)
ALL_NOTIFICATION_TYPES = USER_NOTIFICATION_TYPES | ADMIN_NOTIFICATION_TYPES


# ── Classification ────────────────────────────────────────────────────────────

def is_admin_type(notification_type: str) -> bool:
    """Return True when *notification_type* targets the admin/dev audience.

    Classification is fail-safe: anything that is not an explicit ``user_*``
    type is treated as admin, so an unclassified alert is contained in the
    operator channel rather than leaking into a user chat.
    """
    nt = (notification_type or "").strip().lower()
    if nt in ADMIN_NOTIFICATION_TYPES or nt.startswith("admin_"):
        return True
    if nt in USER_NOTIFICATION_TYPES or nt.startswith("user_"):
        return False
    # Unrecognised / empty → fail safe to admin (never leak to users).
    return True


def is_user_type(notification_type: str) -> bool:
    """Return True when *notification_type* targets the user audience."""
    return not is_admin_type(notification_type)


# ── Channel resolution ────────────────────────────────────────────────────────

def _first_env(*names: str) -> str:
    """Return the first non-empty environment value among *names* (stripped)."""
    for name in names:
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return ""


def admin_chat_id() -> str:
    """Resolve the admin/dev Telegram chat id, or '' if none is configured.

    Supports both naming conventions for robustness. The user chat
    (``TELEGRAM_CHAT_ID``) is intentionally NOT consulted — admin alerts must
    never fall back to a user chat.
    """
    return _first_env(
        "TELEGRAM_ADMIN_CHAT_ID",
        "ADMIN_TELEGRAM_CHAT_ID",
        "TELEGRAM_DEV_CHAT_ID",
        "DEV_TELEGRAM_CHAT_ID",
    )


def admin_bot_token() -> str:
    """Resolve the bot token for admin notifications.

    Prefers a dedicated admin bot (``TELEGRAM_ADMIN_BOT_TOKEN``) and falls back
    to the shared ``TELEGRAM_BOT_TOKEN`` when no separate admin bot is set.
    """
    return _first_env("TELEGRAM_ADMIN_BOT_TOKEN", "TELEGRAM_BOT_TOKEN")


# ── Low-level send ────────────────────────────────────────────────────────────

def _post_telegram(token: str, chat_id: str, message: str) -> bool:
    """POST a message to Telegram. Returns True on success, never raises."""
    if len(message) > _TELEGRAM_MAX_CHARS:
        message = message[: _TELEGRAM_MAX_CHARS - 30] + "\n... (truncated)"
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=15,
        )
        if not resp.ok:
            logger.warning(
                "notification_router: admin send failed status=%s body=%s",
                resp.status_code, (resp.text or "")[:200],
            )
        return resp.ok
    except Exception as exc:  # noqa: BLE001 — never crash the caller
        logger.warning("notification_router: admin send exception: %s", exc)
        return False


# ── Public API ────────────────────────────────────────────────────────────────

def send_admin_notification(
    message: str,
    notification_type: str = ADMIN_ERROR,
) -> bool:
    """Send an admin/dev notification to the admin channel ONLY.

    Returns True if the message was delivered. If no admin/dev chat is
    configured the message is logged and dropped — it is never sent to a user
    chat (rule 2). Never raises.
    """
    chat_id = admin_chat_id()
    if not chat_id:
        logger.warning(
            "notification_router: admin channel not configured; dropping '%s' "
            "notification instead of leaking to users "
            "(set TELEGRAM_ADMIN_CHAT_ID or TELEGRAM_DEV_CHAT_ID). preview=%s",
            notification_type, (message or "")[:160],
        )
        return False

    token = admin_bot_token()
    if not token:
        logger.warning(
            "notification_router: no bot token available for admin notification "
            "type=%s", notification_type,
        )
        return False

    ok = _post_telegram(token, chat_id, message)
    if ok:
        logger.info("notification_router: admin notification sent type=%s", notification_type)
    else:
        logger.warning("notification_router: admin notification send failed type=%s", notification_type)
    return ok


def send_notification(
    message: str,
    notification_type: str,
    *,
    chat_id: Optional[str] = None,
) -> bool:
    """Route *message* to the correct audience based on *notification_type*.

    * ``admin_*`` → admin/dev channel only. A supplied user ``chat_id`` is
      ignored (and refused) so admin content can never reach a user chat. If no
      admin channel is configured the message is dropped and logged.
    * ``user_*``  → the supplied per-user ``chat_id`` when given, otherwise the
      shared user chat (``TELEGRAM_CHAT_ID``). Delegates to the existing
      user-facing senders so the public-alerts kill switch, HTML escaping and
      length clamping still apply.

    Returns True if the message was delivered. Never raises.
    """
    if is_admin_type(notification_type):
        if chat_id:
            # An admin notification was handed a user chat_id — refuse it and
            # route to the admin channel instead (rule 1).
            logger.error(
                "notification_router: refusing to send admin notification "
                "type=%s to a user chat_id; routing to admin channel instead",
                notification_type,
            )
        return send_admin_notification(message, notification_type)

    # user audience
    try:
        if chat_id:
            from src.telegram_bot import send_telegram_to_user

            return bool(send_telegram_to_user(str(chat_id), message))
        from src.telegram_bot import send_telegram_message

        return bool(send_telegram_message(message))
    except Exception:  # noqa: BLE001 — never crash the caller
        logger.exception(
            "notification_router: user notification send error type=%s",
            notification_type,
        )
        return False
