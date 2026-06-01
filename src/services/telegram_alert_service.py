"""src/services/telegram_alert_service.py
Proactive Telegram notifications for Rico AI.

Responsibilities:
- Send new job matches to subscribed users.
- Send follow-up reminders for saved/applied jobs.
- Duplicate guard: never send the same (user, job) pair twice.
- Daily rate limit: max MAX_ALERTS_PER_DAY job-match alerts per user.
- Safe failure: Telegram API errors are logged and swallowed — they must never
  crash the caller (pipeline, chat handler, or scheduler).
"""
from __future__ import annotations

import logging
import os
from typing import Any

import requests

from src.rico_db import RicoDB

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
MAX_ALERTS_PER_DAY = 5


def _token() -> str:
    return os.getenv("TELEGRAM_BOT_TOKEN", "").strip()


def _send_message(chat_id: str, text: str, reply_markup: dict | None = None) -> bool:
    """Low-level Telegram sendMessage. Returns True on success."""
    token = _token()
    if not token or not chat_id:
        return False
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        resp = requests.post(
            _TELEGRAM_API.format(token=token, method="sendMessage"),
            json=payload,
            timeout=15,
        )
        if not resp.ok:
            logger.warning(
                "telegram_alert: sendMessage failed chat_id=%s status=%s body=%s",
                chat_id, resp.status_code, resp.text[:200],
            )
        return resp.ok
    except Exception as exc:
        logger.warning("telegram_alert: sendMessage exception chat_id=%s: %s", chat_id, exc)
        return False


def _format_job_card(job: dict[str, Any], index: int = 1) -> str:
    title = job.get("title") or "Untitled"
    company = job.get("company") or "Unknown company"
    location = job.get("location") or ""
    salary = job.get("salary") or ""
    score = job.get("score") or job.get("final_score") or ""
    apply_url = job.get("apply_url") or job.get("source_url") or job.get("link") or ""

    lines = [f"<b>{index}. {title}</b>"]
    lines.append(f"🏢 {company}")
    if location:
        lines.append(f"📍 {location}")
    if salary:
        lines.append(f"💰 {salary}")
    if score:
        lines.append(f"⭐ Match: {score}%")
    if apply_url:
        lines.append(f'<a href="{apply_url}">Apply / View →</a>')
    return "\n".join(lines)


def _job_key(job: dict[str, Any]) -> str:
    from src.applications import get_job_id  # lazy import — keeps service light
    try:
        return get_job_id(job)
    except Exception:
        title = (job.get("title") or "").lower().replace(" ", "_")[:40]
        company = (job.get("company") or "").lower().replace(" ", "_")[:20]
        return f"{title}__{company}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def send_job_alerts(
    user_id: str,
    chat_id: str,
    jobs: list[dict[str, Any]],
    *,
    dry_run: bool = False,
) -> int:
    """Send new job matches to a user's Telegram.

    Skips jobs that were already sent (duplicate guard) and respects the daily
    rate limit. Returns the number of alerts actually sent.

    Args:
        user_id:  Rico internal user_id (for DB tracking).
        chat_id:  Telegram numeric chat_id to send to.
        jobs:     List of job dicts (same shape as job search results).
        dry_run:  If True, evaluate guards but don't send or record.
    """
    if not jobs or not chat_id:
        return 0

    db = RicoDB()
    sent = 0

    for job in jobs:
        # Per-user daily cap
        if db.available and db.count_alerts_today(user_id) >= MAX_ALERTS_PER_DAY:
            logger.info(
                "telegram_alert: daily cap reached user=%s cap=%d", user_id, MAX_ALERTS_PER_DAY
            )
            break

        key = _job_key(job)

        # Duplicate guard
        if db.available and db.was_alert_sent(user_id, key):
            logger.debug("telegram_alert: skipping duplicate user=%s job_key=%s", user_id, key)
            continue

        card = _format_job_card(job, sent + 1)

        if not dry_run:
            ok = _send_message(chat_id, card)
            if ok and db.available:
                db.log_telegram_alert(user_id, key)
            if ok:
                sent += 1
        else:
            sent += 1  # dry_run counts eligibles

    if sent:
        logger.info("telegram_alert: sent=%d user=%s dry_run=%s", sent, user_id, dry_run)
    return sent


def send_followup_reminder(
    chat_id: str,
    job_title: str,
    company: str,
    *,
    days_ago: int = 3,
) -> bool:
    """Send a follow-up reminder for a job the user applied to.

    Args:
        chat_id:    Telegram chat_id to send to.
        job_title:  Job title string.
        company:    Company name.
        days_ago:   How many days ago the user applied (for the message copy).
    """
    text = (
        f"👋 Quick check-in!\n\n"
        f"You applied to <b>{job_title}</b> at <b>{company}</b> "
        f"{days_ago} day{'s' if days_ago != 1 else ''} ago.\n\n"
        "Have you heard back? Reply here or update your status in Rico."
    )
    ok = _send_message(chat_id, text)
    if ok:
        logger.info(
            "telegram_alert: followup_sent chat_id=%s job=%s company=%s",
            chat_id, job_title, company,
        )
    return ok


def broadcast_job_alerts_to_subscribed_users(
    jobs: list[dict[str, Any]],
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    """Dispatch job alerts to all users with active Telegram notifications.

    This is the entry point for the daily pipeline. It fetches all subscribed
    users and calls send_job_alerts for each. Returns a summary dict.
    """
    db = RicoDB()
    if not db.available:
        logger.warning("telegram_alert: DB unavailable, skipping broadcast")
        return {"users": 0, "total_sent": 0}

    users = db.get_users_with_active_telegram_notifications()
    total_sent = 0

    for u in users:
        user_id = u.get("external_user_id") or u.get("id") or ""
        chat_id = u.get("telegram_chat_id") or ""
        if not user_id or not chat_id:
            continue
        sent = send_job_alerts(user_id, chat_id, jobs, dry_run=dry_run)
        total_sent += sent

    logger.info(
        "telegram_alert: broadcast done users=%d total_sent=%d dry_run=%s",
        len(users), total_sent, dry_run,
    )
    return {"users": len(users), "total_sent": total_sent}
