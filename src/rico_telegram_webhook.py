"""src/rico_telegram_webhook.py — Telegram webhook controller for Rico AI."""
from __future__ import annotations

import logging
from typing import Any, Dict

from src.repositories.webhook_events_repo import is_processed, mark_processed
from src.rico_chat_api import RicoChatAPI
from src.rico_telegram_ui import handle_callback_only
from src.telegram_actions import answer_callback_query

_TELEGRAM_SOURCE = "telegram"

logger = logging.getLogger(__name__)

chat_api = RicoChatAPI()


def process_telegram_update(update: Dict[str, Any]) -> Dict[str, Any]:
    update_id = str(update.get("update_id", ""))
    if update_id and is_processed(_TELEGRAM_SOURCE, update_id):
        logger.info("telegram_webhook: duplicate update_id=%s — skipping", update_id)
        return {"ok": True, "duplicate": True}

    if update.get("callback_query"):
        result = handle_callback_only(update)
        # Acknowledge to Telegram (stops button spinner, must be within 10 s)
        callback_id = result.get("callback_id", "")
        if callback_id:
            ack_text = result.get("reply", "")[:200]
            answer_callback_query(callback_id, text=ack_text)
        if update_id:
            mark_processed(_TELEGRAM_SOURCE, update_id)
        return result

    message = update.get("message", {})
    chat = message.get("chat", {})
    user = message.get("from", {})

    text = message.get("text", "")
    user_id = str(chat.get("id") or user.get("id") or "telegram-user")

    try:
        response = chat_api.process_message(user_id=user_id, message=text)
    except Exception as exc:
        logger.warning("rico_chat_api_error: %s", exc)
        response = {"message": "Rico is unavailable right now."}

    if update_id:
        mark_processed(_TELEGRAM_SOURCE, update_id)

    return {
        "chat_id": user_id,
        "reply": response,
    }
