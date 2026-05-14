"""
src/telegram_bot.py
Telegram notification helper.
  - All user-supplied fields are HTML-escaped (including link).
  - Messages are clamped to Telegram's 4 096-char hard limit.
"""

from __future__ import annotations

import html
import os
from typing import Any, Dict
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

load_dotenv()

_TELEGRAM_MAX_CHARS = 4096
_MAX_JOBS_PER_MESSAGE = 5  # demo-safe limit
_DEMO_MODE = os.getenv("RICO_DEMO_MODE", "").lower() in ("true", "1", "yes")
_PUBLIC_ALERTS_ENABLED = os.getenv("RICO_TELEGRAM_PUBLIC_ALERTS", "true").lower() in ("true", "1", "yes")


def _safe_html(value: object) -> str:
    """Convert any value to an HTML-escaped string."""
    return html.escape(str(value) if value is not None else "")


def _safe_link(value: object) -> str:
    """
    Sanitise a URL for use inside an HTML href attribute.
    Accepts only http/https schemes; anything else becomes '#'.
    """
    raw = str(value or "").strip()
    try:
        parsed = urlparse(raw)
        if parsed.scheme not in ("http", "https"):
            return "#"
    except Exception:
        return "#"
    # Escape for HTML attribute context (handles quotes, angle brackets)
    return html.escape(raw, quote=True)


def send_telegram_message(message: str) -> bool:
    """Send a Telegram message. Returns True on success.

    Respects RICO_TELEGRAM_PUBLIC_ALERTS=false kill switch.
    """
    if not _PUBLIC_ALERTS_ENABLED:
        print("Telegram public alerts disabled (RICO_TELEGRAM_PUBLIC_ALERTS=false)")
        return False

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not all([bot_token, chat_id]):
        print("Error: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env file")
        return False

    # Hard-clamp to Telegram limit before every send
    if len(message) > _TELEGRAM_MAX_CHARS:
        truncation_note = "\n\n<b>... (message truncated)</b>"
        message = message[: _TELEGRAM_MAX_CHARS - len(truncation_note)] + truncation_note

    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
        }
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print("Telegram message sent successfully")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error sending Telegram message: {e}")
        return False


def send_job_card_with_buttons(job: Dict[str, Any], chat_id: str | None = None) -> bool:
    """
    Send a single job card with Rico inline action buttons.
    Also caches the job so Telegram callbacks can look up the full details.
    Returns True on success.
    """
    from src.telegram_actions import build_job_keyboard
    from src.rico_telegram_ui import cache_job, recommendation_message

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    target = chat_id or os.getenv("TELEGRAM_CHAT_ID")
    if not token or not target:
        return False

    cache_job(job)
    message = recommendation_message(job)
    keyboard = build_job_keyboard(job)

    if len(message) > _TELEGRAM_MAX_CHARS:
        message = message[: _TELEGRAM_MAX_CHARS - 20] + "\n... (truncated)"

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(
            url,
            json={
                "chat_id": target,
                "text": message,
                "parse_mode": "HTML",
                "reply_markup": keyboard,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:
        print(f"Error sending job card: {exc}")
        return False


def _normalize_job_key(job: Dict[str, Any]) -> str:
    """Create normalized key for deduplication: title|company|location|link."""
    title = (job.get("title") or "").strip().lower()
    company = (job.get("company") or "").strip().lower()
    location = (job.get("location") or "").strip().lower()
    link = (job.get("link") or "").strip().lower()
    return f"{title}|{company}|{location}|{link}"


def _format_score(score: int) -> str:
    """Format score for demo-safe display."""
    if _DEMO_MODE:
        if score >= 90:
            return "Match: Excellent"
        elif score >= 75:
            return "Match: Strong"
        elif score >= 60:
            return "Match: Good"
        else:
            return "Match: Fair"
    return str(score)


def format_telegram_jobs(jobs_with_scores) -> str:
    """
    Format jobs for Telegram with HTML.
    All fields are escaped; links are scheme-validated.
    Message is clamped to 4 096 chars.

    Demo mode: dedupes jobs, caps score display, limits to 5 jobs.
    """
    if not jobs_with_scores:
        if _DEMO_MODE:
            # Suppress "No new jobs found today" in demo mode
            return ""
        return "<b>No new jobs found today.</b>"

    # Deduplicate jobs by normalized key
    seen_keys = set()
    deduped = []
    for job, score in jobs_with_scores:
        key = _normalize_job_key(job)
        if key not in seen_keys:
            seen_keys.add(key)
            deduped.append((job, score))

    if not deduped:
        return ""

    # Limit to max jobs
    jobs_to_show = deduped[:_MAX_JOBS_PER_MESSAGE]

    lines = [
        "<b>🔔 Job Hunting Daily Report</b>",
        f"Found {len(deduped)} high-quality job matches",
        "",
    ]

    for job, score in jobs_to_show:
        title = _safe_html(job.get("title", "N/A"))
        company = _safe_html(job.get("company", "N/A"))
        location = _safe_html(job.get("location", "N/A"))
        link = _safe_link(job.get("link", ""))
        display_score = _format_score(score)

        lines.extend([
            f"<b>📌 {title}</b>",
            f"🏢 {company}",
            f"📍 {location}",
            f"⭐ {display_score}",
            f'🔗 <a href="{link}">Apply</a>',
            "",
        ])

    message = "\n".join(lines)

    # Final hard clamp (defensive — send_telegram_message also clamps)
    if len(message) > _TELEGRAM_MAX_CHARS:
        truncation_note = "\n\n<b>... (truncated)</b>"
        message = message[: _TELEGRAM_MAX_CHARS - len(truncation_note)] + truncation_note

    return message
