"""src/rico_telegram_webhook.py — Telegram webhook controller for Rico AI."""
from __future__ import annotations

import logging
from typing import Any, Dict

from src.rico_chat_api import RicoChatAPI
from src.rico_telegram_ui import handle_callback_only
from src.telegram_actions import answer_callback_query

logger = logging.getLogger(__name__)

chat_api = RicoChatAPI()


def _persist_telegram_identity(user_id: str, tg_user: Dict[str, Any]) -> None:
    """Save the Telegram numeric chat_id (and @handle if present) to the profile.

    Called on every inbound message so the daily pipeline can find this user
    when sending proactive job alerts. Failures are logged but never raised —
    the chat response must always proceed regardless of DB availability.
    """
    try:
        from src.repositories.profile_repo import upsert_profile
        updates: Dict[str, Any] = {"telegram_chat_id": user_id}
        username = tg_user.get("username")
        if username:
            updates["telegram_username"] = f"@{username}"
        upsert_profile(user_id=user_id, updates=updates)
    except Exception as exc:
        logger.warning("telegram_identity_persist_failed user_id=%s error=%s", user_id, exc)


def process_telegram_update(update: Dict[str, Any]) -> Dict[str, Any]:
    if update.get("callback_query"):
        result = handle_callback_only(update)
        # Acknowledge to Telegram (stops button spinner, must be within 10 s)
        callback_id = result.get("callback_id", "")
        if callback_id:
            ack_text = result.get("reply", "")[:200]
            answer_callback_query(callback_id, text=ack_text)
        return result

    message = update.get("message", {})
    chat = message.get("chat", {})
    tg_user = message.get("from", {})

    text = message.get("text", "")
    chat_id_raw = chat.get("id") or tg_user.get("id")
    user_id = str(chat_id_raw or "telegram-user")

    # Persist chat_id so the daily pipeline can send proactive job alerts
    if chat_id_raw:
        _persist_telegram_identity(user_id, tg_user)

    try:
        response = chat_api.process_message(user_id=user_id, message=text)
    except Exception as exc:
        logger.warning("rico_chat_api_error: %s", exc)
        response = {"message": "Rico is unavailable right now."}

    return {
        "chat_id": user_id,
        "reply": response,
    }
