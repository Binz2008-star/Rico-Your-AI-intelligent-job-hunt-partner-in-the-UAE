"""src/rico_telegram_webhook.py — Telegram webhook controller for Rico AI."""
from __future__ import annotations

import logging
from typing import Any, Dict

from src.rico_chat_api import RicoChatAPI
from src.rico_telegram_ui import handle_callback_only
from src.telegram_actions import answer_callback_query
from src.repositories.profile_repo import find_profiles_by_telegram_username, upsert_profile

logger = logging.getLogger(__name__)

chat_api = RicoChatAPI()


# ---------------------------------------------------------------------------
# /start and /stop handlers
# ---------------------------------------------------------------------------

def _handle_start(message: Dict[str, Any]) -> Dict[str, Any]:
    """Bind this Telegram chat_id to the user's Rico profile and enable notifications.

    Lookup priority:
    1. Match message.from.username against rico_users.telegram_username (WebApp users
       who have already shared their handle via chat).
    2. If no match, treat the chat_id itself as the Rico user_id (pure Telegram users).
    """
    chat_id = str(message.get("chat", {}).get("id") or message.get("from", {}).get("id") or "")
    username = (message.get("from", {}).get("username") or "").strip().lstrip("@").lower()

    bound_user_id: str | None = None

    if username:
        try:
            matches = find_profiles_by_telegram_username(username)
            if matches:
                bound_user_id = matches[0].user_id
        except Exception as exc:
            logger.warning("telegram_start: lookup failed username=%s: %s", username, exc)

    # Fall back to chat_id as the Rico user identity (native Telegram users)
    if not bound_user_id:
        bound_user_id = chat_id

    if chat_id:
        try:
            upsert_profile(
                bound_user_id,
                {
                    "telegram_chat_id": chat_id,
                    "telegram_notifications_enabled": True,
                    **({"telegram_username": username} if username else {}),
                },
            )
        except Exception as exc:
            logger.warning("telegram_start: upsert failed user=%s: %s", bound_user_id, exc)

    display = f"@{username}" if username else f"chat {chat_id}"
    reply = (
        f"Welcome to Rico! Your Telegram ({display}) is now linked. "
        "I'll send you job alerts and follow-up reminders here. "
        "Send /stop at any time to pause notifications."
    )
    logger.info("telegram_start: bound chat_id=%s to user=%s", chat_id, bound_user_id)
    return {"chat_id": chat_id, "reply": reply}


def _handle_stop(message: Dict[str, Any]) -> Dict[str, Any]:
    """Disable notifications for this Telegram user."""
    chat_id = str(message.get("chat", {}).get("id") or message.get("from", {}).get("id") or "")
    user_id = chat_id  # for Telegram users, chat_id == Rico user_id

    if chat_id:
        try:
            upsert_profile(user_id, {"telegram_notifications_enabled": False})
        except Exception as exc:
            logger.warning("telegram_stop: upsert failed user=%s: %s", user_id, exc)

    reply = (
        "Notifications paused. Send /start to re-enable them whenever you're ready."
    )
    logger.info("telegram_stop: disabled notifications for chat_id=%s", chat_id)
    return {"chat_id": chat_id, "reply": reply}


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

def process_telegram_update(update: Dict[str, Any]) -> Dict[str, Any]:
    if update.get("callback_query"):
        result = handle_callback_only(update)
        callback_id = result.get("callback_id", "")
        if callback_id:
            ack_text = result.get("reply", "")[:200]
            answer_callback_query(callback_id, text=ack_text)
        return result

    message = update.get("message", {})
    chat = message.get("chat", {})
    tg_user = message.get("from", {})

    text = (message.get("text") or "").strip()
    user_id = str(chat.get("id") or tg_user.get("id") or "telegram-user")

    # Bot command routing — must run before generic chat handler
    command = text.split()[0].lower() if text.startswith("/") else ""
    if command in ("/start", "/start@ricobot"):
        return _handle_start(message)
    if command in ("/stop", "/stop@ricobot"):
        return _handle_stop(message)

    try:
        response = chat_api.process_message(user_id=user_id, message=text)
    except Exception as exc:
        logger.warning("rico_chat_api_error: %s", exc)
        response = {"message": "Rico is unavailable right now."}

    return {
        "chat_id": chat_id,
        "reply": response,
    }
