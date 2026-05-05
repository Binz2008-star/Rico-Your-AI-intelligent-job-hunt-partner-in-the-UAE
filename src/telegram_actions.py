"""Telegram inline action buttons for job decisions."""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


def _token() -> str:
    return os.getenv("TELEGRAM_BOT_TOKEN", "").strip()


def _chat_id() -> str:
    return os.getenv("TELEGRAM_CHAT_ID", "").strip()


def build_job_keyboard(job: Dict[str, Any]) -> Dict[str, Any]:
    link = job.get("link", "")
    job_id = str(job.get("id") or job.get("link") or f"{job.get('company','')}_{job.get('title','')}")[:64]
    buttons: List[List[Dict[str, str]]] = []
    if link:
        buttons.append([{"text": "Open / Apply", "url": link}])
    buttons.append([
        {"text": "Mark Applied", "callback_data": f"applied|{job_id}"},
        {"text": "Watch", "callback_data": f"watch|{job_id}"},
        {"text": "Skip", "callback_data": f"skip|{job_id}"},
    ])
    return {"inline_keyboard": buttons}


def send_job_action(job: Dict[str, Any], decision: Optional[str] = None, reasoning: Optional[str] = None) -> bool:
    token = _token()
    chat_id = _chat_id()
    if not token or not chat_id:
        return False
    title = job.get("title", "N/A")
    company = job.get("company", "N/A")
    score = job.get("score", job.get("final_score", "N/A"))
    text = f"<b>{title}</b>\n🏢 {company}\n⭐ Score: {score}"
    if decision:
        text += f"\n🤖 Decision: <b>{decision}</b>"
    if reasoning:
        text += f"\nReason: {reasoning[:500]}"
    resp = requests.post(
        TELEGRAM_API.format(token=token, method="sendMessage"),
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "reply_markup": build_job_keyboard(job)},
        timeout=15,
    )
    return resp.ok
