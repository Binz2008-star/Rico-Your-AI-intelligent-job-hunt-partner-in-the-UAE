"""Telegram UI helpers for Rico AI.

Provides inline keyboard structures, callback parsing, and lightweight
callback action helpers without changing the existing Telegram notification
pipeline.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from filelock import FileLock, Timeout as FileLockTimeout

from src.applications import get_job_id, mark_applied, update_application_status
from src.message_generator import generate_message


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
TELEGRAM_ACTIONS_FILE = DATA_DIR / "telegram_actions.json"
TELEGRAM_ACTIONS_LOCK = str(TELEGRAM_ACTIONS_FILE) + ".lock"
LOCK_TIMEOUT_SECONDS = 10


RICO_ACTIONS = [
    ("Apply", "apply"),
    ("Save", "save"),
    ("Skip", "skip"),
    ("Why this?", "why"),
    ("Draft", "draft"),
    ("Remind me", "remind"),
    ("Not relevant", "not_relevant"),
]

SUPPORTED_ACTIONS = {action for _, action in RICO_ACTIONS}


def recommendation_keyboard(job_key: str) -> Dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": "Apply", "callback_data": f"rico:apply:{job_key}"},
                {"text": "Save", "callback_data": f"rico:save:{job_key}"},
                {"text": "Skip", "callback_data": f"rico:skip:{job_key}"},
            ],
            [
                {"text": "Why this?", "callback_data": f"rico:why:{job_key}"},
                {"text": "Draft", "callback_data": f"rico:draft:{job_key}"},
            ],
            [
                {"text": "Remind me", "callback_data": f"rico:remind:{job_key}"},
                {"text": "Not relevant", "callback_data": f"rico:not_relevant:{job_key}"},
            ],
        ]
    }


def recommendation_keyboard_for_job(job: Dict[str, Any]) -> Dict[str, Any]:
    return recommendation_keyboard(get_job_id(job))


def recommendation_message(match: Dict[str, Any]) -> str:
    title = match.get("title") or "Role"
    company = match.get("company") or "Company"
    location = match.get("location") or "UAE"
    score = match.get("rico_score") or match.get("score") or "-"
    explanation = match.get("rico_explanation") or match.get("why") or "Strong potential fit based on your profile."

    return (
        f"🔥 {title}\n"
        f"🏢 {company}\n"
        f"📍 {location}\n"
        f"🎯 Match: {score}%\n\n"
        f"Why Rico picked this:\n{explanation}"
    )


def parse_callback(callback_data: str) -> Dict[str, str]:
    parts = (callback_data or "").split(":", 2)
    if len(parts) != 3:
        return {"namespace": "unknown", "action": "unknown", "job_key": ""}
    namespace, action, job_key = parts
    return {
        "namespace": namespace,
        "action": action,
        "job_key": job_key,
    }


def _load_action_log() -> List[Dict[str, Any]]:
    try:
        with TELEGRAM_ACTIONS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def _save_action_log(entries: List[Dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = TELEGRAM_ACTIONS_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    os.replace(tmp, TELEGRAM_ACTIONS_FILE)


def record_callback_action(
    action: str,
    job_key: str,
    user_id: str = "",
    metadata: Dict[str, Any] | None = None,
) -> bool:
    if action not in SUPPORTED_ACTIONS:
        return False

    entry = {
        "action": action,
        "job_key": job_key,
        "user_id": user_id,
        "metadata": metadata or {},
        "created_at": datetime.now().isoformat(),
    }

    try:
        with FileLock(TELEGRAM_ACTIONS_LOCK, timeout=LOCK_TIMEOUT_SECONDS):
            entries = _load_action_log()
            entries.append(entry)
            _save_action_log(entries)
        return True
    except FileLockTimeout:
        return False


def handle_callback_only(update: Dict[str, Any]) -> Dict[str, Any]:
    callback = update.get("callback_query", {}) if isinstance(update, dict) else {}
    data = parse_callback(callback.get("data", ""))
    user = callback.get("from", {}) or {}
    user_id = str(user.get("id") or "")

    if data["namespace"] != "rico" or data["action"] not in SUPPORTED_ACTIONS:
        return {
            "ok": False,
            "chat_id": user_id,
            "reply": "Unsupported Telegram action.",
            **data,
        }

    record_callback_action(
        action=data["action"],
        job_key=data["job_key"],
        user_id=user_id,
        metadata={"callback_id": callback.get("id", "")},
    )

    return {
        "ok": True,
        "chat_id": user_id,
        "reply": callback_ack_message(data["action"]),
        **data,
    }


def callback_ack_message(action: str) -> str:
    return {
        "apply": "Rico received your apply action. I will track this job once the job card is linked to your tracker.",
        "save": "Saved. Rico will keep this job in mind.",
        "skip": "Skipped. Rico will use this as feedback.",
        "why": "Rico picked this because it matched your current role, location, and preference signals.",
        "draft": "Rico can draft a short application message when the job details are available.",
        "remind": "Reminder noted.",
        "not_relevant": "Marked not relevant. Rico will reduce similar matches.",
    }.get(action, "Action received.")


def handle_job_action(action: str, job: Dict[str, Any], user_id: str = "") -> Dict[str, Any]:
    job_key = get_job_id(job)
    record_callback_action(action, job_key, user_id=user_id, metadata={"job": job})

    if action == "apply":
        mark_applied(job, status="applied", notes="Marked from Telegram callback")
        return {"ok": True, "reply": "Marked as applied. Rico will track this job."}

    if action == "save":
        mark_applied(job, status="saved", notes="Saved from Telegram callback")
        return {"ok": True, "reply": "Saved. Rico will keep this job in your tracker."}

    if action == "skip":
        return {"ok": True, "reply": "Skipped. Rico will use this as feedback."}

    if action == "not_relevant":
        return {"ok": True, "reply": "Marked not relevant. Rico will reduce similar matches."}

    if action == "why":
        reason = job.get("profile_explanation") or job.get("match_reason") or "It matched your current profile and search preferences."
        return {"ok": True, "reply": str(reason)}

    if action == "draft":
        return {"ok": True, "reply": generate_message(job)}

    if action == "remind":
        reminder_date = (datetime.now() + timedelta(days=2)).date().isoformat()
        update_application_status(job, "saved", notes=f"Telegram reminder requested for {reminder_date}")
        return {"ok": True, "reply": f"Reminder noted for {reminder_date}."}

    return {"ok": False, "reply": "Unsupported action."}
