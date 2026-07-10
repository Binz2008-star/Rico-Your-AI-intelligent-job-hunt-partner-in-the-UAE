"""Autonomous notification composer for Rico.

Builds rich Telegram notifications for autonomous actions:
  - Daily digest of new matches
  - High-match immediate alert
  - Follow-up reminder with draft preview
  - Daily action plan

All notifications are formatted as HTML for Telegram's parse_mode=HTML.
"""
from __future__ import annotations

import html
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _esc(text: str) -> str:
    return html.escape(str(text))


def format_daily_digest(
    user_name: str,
    saved_jobs: List[Dict[str, Any]],
    new_matches_count: int = 0,
    drafts_ready_count: int = 0,
    followups_due_count: int = 0,
) -> str:
    """Format a daily digest notification for Telegram.

    Args:
        user_name: The user's display name.
        saved_jobs: List of auto-saved job dicts (each with title, company, score).
        new_matches_count: Total new matches found (may be more than saved).
        drafts_ready_count: Number of cover letter drafts prepared.
        followups_due_count: Number of follow-up reminders due.

    Returns:
        HTML-formatted message string.
    """
    lines: List[str] = []
    lines.append(f"🌅 <b>Good morning {_esc(user_name)}!</b> Rico's daily digest:\n")

    if saved_jobs:
        lines.append(f"📌 <b>Auto-saved {len(saved_jobs)} high-match jobs:</b>")
        for job in saved_jobs[:5]:
            title = job.get("title", job.get("job", {}).get("title", "Role"))
            company = job.get("company", job.get("job", {}).get("company", "Company"))
            score = job.get("score", "?")
            lines.append(f"  • {_esc(title)} — {_esc(company)} (Score: {score})")
        if len(saved_jobs) > 5:
            lines.append(f"  ... and {len(saved_jobs) - 5} more")
        lines.append("")

    if new_matches_count > 0:
        lines.append(f"🔍 Found <b>{new_matches_count}</b> new matching jobs today.")
    if drafts_ready_count > 0:
        lines.append(f"📝 <b>{drafts_ready_count}</b> cover letter drafts ready for your review.")
    if followups_due_count > 0:
        lines.append(f"⏰ <b>{followups_due_count}</b> follow-up reminders due.")

    if not saved_jobs and new_matches_count == 0 and drafts_ready_count == 0 and followups_due_count == 0:
        lines.append("No new matches today. Rico will keep scanning for you. 🔄")

    lines.append("\n💬 Reply to chat with Rico for details or to take action.")
    return "\n".join(lines)


def format_high_match_alert(job: Dict[str, Any]) -> str:
    """Format an immediate high-match alert (score >= 90) for Telegram."""
    title = job.get("title", "Role")
    company = job.get("company", "Company")
    score = job.get("score", "?")
    location = job.get("location", job.get("city", ""))
    link = job.get("link", job.get("url", ""))

    lines = [
        f"🔥 <b>Strong match found!</b> (Score: {score})",
        f"📋 {_esc(title)} at {_esc(company)}",
    ]
    if location:
        lines.append(f"📍 {_esc(location)}")
    if link:
        lines.append(f"🔗 {_esc(link)}")
    lines.append("\n💬 Tell Rico \"save this\" or \"apply\" to take action.")
    return "\n".join(lines)


def format_followup_reminder(
    job_title: str,
    company: str,
    days_since: int,
    draft_preview: Optional[str] = None,
) -> str:
    """Format a follow-up reminder for Telegram."""
    lines = [
        f"⏰ <b>Follow-up reminder</b>",
        f"📋 {_esc(job_title)} at {_esc(company)}",
        f"📅 Applied {days_since} days ago — time to follow up.",
    ]
    if draft_preview:
        preview = draft_preview[:200]
        if len(draft_preview) > 200:
            preview += "..."
        lines.append(f"\n📝 <b>Draft ready:</b>\n{_esc(preview)}")
        lines.append("\n💬 Say \"send follow-up\" to approve, or edit it in chat.")
    else:
        lines.append("\n💬 Ask Rico to draft a follow-up message for you.")
    return "\n".join(lines)


def format_daily_plan(
    user_name: str,
    state: str,
    actions: List[Dict[str, str]],
) -> str:
    """Format a daily action plan for Telegram."""
    lines = [
        f"📋 <b>Rico's plan for {_esc(user_name)} today</b>",
        f"Phase: <b>{_esc(state)}</b>\n",
    ]
    for i, action in enumerate(actions, 1):
        priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(action.get("priority", "low"), "🟢")
        lines.append(f"{priority_icon} {i}. {_esc(action.get('message', ''))}")
    lines.append("\n💬 Chat with Rico to get started on any action.")
    return "\n".join(lines)
