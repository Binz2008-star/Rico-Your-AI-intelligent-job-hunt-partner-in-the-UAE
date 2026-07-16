"""src/services/telegram_notifications.py

Per-user Telegram notification service for Rico.

Contract:
- Notifications are sent ONLY after the user explicitly opts in.
- opt_in() must be called (or confirmed via /start bot command) before any send.
- Rate guard: max 10 job-alert notifications per user per 24 h; max 1 of any
  alert_type per user per 1 h.  Checked against the rico_alerts table.
- Failed sends are logged but never surfaced as errors to the caller.
- No secrets are hardcoded — bot token read from TELEGRAM_BOT_TOKEN env var.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from src.repositories.profile_repo import get_profile, upsert_profile
from src.telegram_bot import send_job_card_with_buttons, _TELEGRAM_MAX_CHARS

logger = logging.getLogger(__name__)

_UTC = timezone.utc
_RATE_WINDOW_HOURS = 1
_DAILY_JOB_ALERT_LIMIT = 10


# ---------------------------------------------------------------------------
# Internal DB helpers
# ---------------------------------------------------------------------------

def _db():
    from src.rico_db import RicoDB
    db = RicoDB()
    return db if db.available else None


def _get_user_row(db, user_id: str) -> dict[str, Any] | None:
    """Return the rico_users row for *user_id*, or None on miss/error."""
    try:
        bundle = db.get_user_bundle(user_id)
        return bundle.get("user") if bundle else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Opt-in / opt-out
# ---------------------------------------------------------------------------

def is_opted_in(user_id: str) -> bool:
    """Return True if the user has opted in to Telegram notifications."""
    try:
        profile = get_profile(user_id)
        if not profile:
            return False
        # telegram_chat_id must be present (we know which chat to send to)
        # and can_receive_telegram_notifications must be True in settings
        chat_id = getattr(profile, "telegram_chat_id", None)
        settings = getattr(profile, "settings", None)
        enabled = getattr(settings, "can_receive_telegram_notifications", False) if settings else False
        return bool(chat_id and enabled)
    except Exception:
        logger.debug("telegram_notifications.is_opted_in failed user=%s", user_id, exc_info=True)
        return False


def opt_in(user_id: str, telegram_chat_id: str | None = None) -> bool:
    """Opt a user in to Telegram notifications.

    Sets can_receive_telegram_notifications=True in settings.
    Optionally also stores *telegram_chat_id* in the user record.
    Returns True on success.
    """
    try:
        updates: dict[str, Any] = {"can_receive_telegram_notifications": True}
        if telegram_chat_id:
            updates["telegram_chat_id"] = str(telegram_chat_id)
        # Consent is durable state: require DB persistence so a swallowed DB
        # failure surfaces as False here instead of a false success (#1082).
        upsert_profile(user_id=user_id, updates=updates, require_db=True)
        logger.info("telegram_notifications.opt_in user=%s chat_id=%s", user_id, telegram_chat_id)
        return True
    except Exception:
        logger.exception("telegram_notifications.opt_in failed user=%s", user_id)
        return False


def opt_out(user_id: str) -> bool:
    """Opt a user out of Telegram notifications.

    Sets can_receive_telegram_notifications=False.  Does NOT delete their
    telegram_username or telegram_chat_id so they can re-enable later.
    Returns True on success.
    """
    try:
        # Opt-out MUST persist durably; a JSON-mirror-only write would leave the
        # user opted-in in Neon and still reachable by a later worker (#1082).
        upsert_profile(user_id=user_id, updates={"can_receive_telegram_notifications": False}, require_db=True)
        logger.info("telegram_notifications.opt_out user=%s", user_id)
        return True
    except Exception:
        logger.exception("telegram_notifications.opt_out failed user=%s", user_id)
        return False


# ---------------------------------------------------------------------------
# Rate guard
# ---------------------------------------------------------------------------

def _check_rate_limit(db, db_user_id: str, alert_type: str) -> bool:
    """Return True if within rate limits (send is allowed).

    - Any alert_type: at most 1 per user per RATE_WINDOW_HOURS
    - job_alert: at most DAILY_JOB_ALERT_LIMIT per user per 24 h
    """
    try:
        if not db.available:
            return True
        with db._get_conn() as conn:
            with conn.cursor() as cur:
                window_start = datetime.now(_UTC) - timedelta(hours=_RATE_WINDOW_HOURS)
                cur.execute(
                    """
                    SELECT COUNT(*) FROM rico_alerts
                    WHERE user_id::text = %s
                      AND channel = 'telegram'
                      AND alert_type = %s
                      AND status = 'sent'
                      AND sent_at >= %s
                    """,
                    (db_user_id, alert_type, window_start),
                )
                row = cur.fetchone()
                if row and row[0] >= 1:
                    logger.debug(
                        "telegram_rate_limit hit user=%s type=%s window=%sh",
                        db_user_id, alert_type, _RATE_WINDOW_HOURS,
                    )
                    return False

                if alert_type == "job_alert":
                    day_start = datetime.now(_UTC) - timedelta(hours=24)
                    cur.execute(
                        """
                        SELECT COUNT(*) FROM rico_alerts
                        WHERE user_id::text = %s
                          AND channel = 'telegram'
                          AND alert_type = 'job_alert'
                          AND status = 'sent'
                          AND sent_at >= %s
                        """,
                        (db_user_id, day_start),
                    )
                    row = cur.fetchone()
                    if row and row[0] >= _DAILY_JOB_ALERT_LIMIT:
                        logger.debug(
                            "telegram_daily_limit hit user=%s count=%d",
                            db_user_id, row[0],
                        )
                        return False

        return True
    except Exception:
        logger.debug("telegram_notifications._check_rate_limit error", exc_info=True)
        return True  # allow on DB error — fail open


def _log_alert(db, db_user_id: str, alert_type: str, message: str, status: str) -> None:
    """Insert a row into rico_alerts. Best-effort — never raises."""
    try:
        if not db.available:
            return
        now = datetime.now(_UTC)
        with db._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO rico_alerts
                        (user_id, channel, alert_type, message, status, sent_at, created_at)
                    VALUES (%s::uuid, 'telegram', %s, %s, %s, %s, %s)
                    """,
                    (db_user_id, alert_type, message[:2000], status, now if status == "sent" else None, now),
                )
            conn.commit()
    except Exception:
        logger.debug("telegram_notifications._log_alert failed", exc_info=True)


# ---------------------------------------------------------------------------
# Core send
# ---------------------------------------------------------------------------

def _resolve_chat_id(user_id: str) -> str | None:
    """Return the telegram_chat_id for *user_id*, or None if unknown."""
    try:
        db = _db()
        if not db:
            return None
        user_row = _get_user_row(db, user_id)
        return str(user_row["telegram_chat_id"]) if user_row and user_row.get("telegram_chat_id") else None
    except Exception:
        return None


def _resolve_db_user_id(user_id: str) -> str | None:
    """Return the UUID primary key for *user_id* from rico_users."""
    try:
        db = _db()
        if not db:
            return None
        user_row = _get_user_row(db, user_id)
        return str(user_row["id"]) if user_row and user_row.get("id") else None
    except Exception:
        return None


def send_user_notification(
    user_id: str,
    message: str,
    alert_type: str = "job_alert",
    job: dict[str, Any] | None = None,
) -> bool:
    """Send a Telegram message to a specific opted-in user.

    - Returns True if the message was sent successfully.
    - Checks opt-in status, telegram_chat_id presence, and rate limits.
    - If *job* is provided, sends an interactive job card with action buttons
      (via send_job_card_with_buttons); otherwise sends plain text.
    - Never raises — all errors are logged and False is returned.
    """
    try:
        if not is_opted_in(user_id):
            logger.debug("telegram_notifications: user=%s not opted in, skipping", user_id)
            return False

        chat_id = _resolve_chat_id(user_id)
        if not chat_id:
            logger.debug("telegram_notifications: no telegram_chat_id for user=%s", user_id)
            return False

        db_user_id = _resolve_db_user_id(user_id)

        db = _db()
        if db_user_id and db:
            if not _check_rate_limit(db, db_user_id, alert_type):
                logger.info(
                    "telegram_notifications: rate limited user=%s type=%s",
                    user_id, alert_type,
                )
                return False

        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            logger.warning("telegram_notifications: TELEGRAM_BOT_TOKEN not set")
            return False

        if job:
            ok = send_job_card_with_buttons(job, chat_id=chat_id)
        else:
            import requests
            msg = message
            if len(msg) > _TELEGRAM_MAX_CHARS:
                msg = msg[: _TELEGRAM_MAX_CHARS - 30] + "\n... (truncated)"
            resp = requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"},
                timeout=15,
            )
            ok = resp.ok

        status = "sent" if ok else "failed"
        if db_user_id and db:
            _log_alert(db, db_user_id, alert_type, message, status)

        if ok:
            logger.info(
                "telegram_notifications: sent user=%s type=%s job=%s",
                user_id, alert_type, bool(job),
            )
        else:
            logger.warning(
                "telegram_notifications: send failed user=%s type=%s",
                user_id, alert_type,
            )
        return ok

    except Exception:
        logger.exception("telegram_notifications.send_user_notification error user=%s", user_id)
        return False
