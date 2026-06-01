"""src/rico_telegram_webhook.py — Telegram webhook controller for Rico AI."""
from __future__ import annotations

import logging
from typing import Any, Dict

from src.rico_chat_api import RicoChatAPI
from src.rico_telegram_ui import handle_callback_only
from src.telegram_actions import answer_callback_query
from src.repositories.profile_repo import find_profiles_by_telegram_username, upsert_profile
from src.services.telegram_notifications import opt_in

logger = logging.getLogger(__name__)

chat_api = RicoChatAPI()

_WELCOME_TEXT = (
    "👋 Hi! I'm Rico, your UAE job search partner.\n\n"
    "I've linked this Telegram to your account. You'll now receive:\n"
    "• Strong new job matches\n"
    "• Application follow-up reminders\n"
    "• Important account notices\n\n"
    "You can disable alerts any time by saying 'stop Telegram alerts' in the app."
)


def _handle_start(chat_id: str, tg_username: str | None) -> str:
    """Handle /start command: link telegram_chat_id to the profile and opt in.

    If the user's Telegram @username is known, we look up their Rico profile
    and enable notifications.  Returns a reply string.
    """
    try:
        if tg_username:
            profiles = find_profiles_by_telegram_username(tg_username.lstrip("@"))
            if profiles:
                user_id = getattr(profiles[0], "user_id", None)
                if user_id:
                    opt_in(user_id, telegram_chat_id=chat_id)
                    logger.info(
                        "telegram_start: linked chat_id=%s username=%s user_id=%s",
                        chat_id, tg_username, user_id,
                    )
                    return _WELCOME_TEXT

        # Username not found in Rico DB — send a generic greeting; the user can
        # link their account from the web app Settings page.
        return (
            "👋 Hi! I'm Rico, your UAE job search partner.\n\n"
            "To activate Telegram alerts, log in to ricohunt.com and add your "
            "Telegram username (@" + (tg_username or "your_handle") + ") in Settings.\n\n"
            "Once linked, you'll receive job matches and reminders directly here."
        )
    except Exception:
        logger.exception("telegram_start handler failed chat_id=%s", chat_id)
        return "Hi! I'm Rico. Please link your account from the ricohunt.com settings page to enable alerts."


def _persist_telegram_identity(user_id: str, tg_user: Dict[str, Any]) -> None:
    """Save the Telegram numeric chat_id (and @handle if present) to the profile.

    Called on every inbound message so the daily pipeline can find this user
    when sending proactive job alerts. Failures are logged but never raised —
    the chat response must always proceed regardless of DB availability.
    """
    try:
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

    text = (message.get("text") or "").strip()
    chat_id_raw = chat.get("id") or tg_user.get("id")
    chat_id = str(chat_id_raw or "telegram-user")
    tg_username = tg_user.get("username")  # Telegram @username, may be None

    # /start command — link account and enable notifications
    if text == "/start" or text.startswith("/start "):
        reply_text = _handle_start(chat_id, tg_username)
        return {"chat_id": chat_id, "reply": {"type": "clarification", "message": reply_text}}

    # Persist chat_id so the daily pipeline can send proactive job alerts
    user_id = chat_id
    if chat_id_raw:
        _persist_telegram_identity(user_id, tg_user)

    try:
        response = chat_api.process_message(user_id=user_id, message=text)
    except Exception as exc:
        logger.warning("rico_chat_api_error: %s", exc)
        response = {"message": "Rico is unavailable right now."}

    return {
        "chat_id": chat_id,
        "reply": response,
    }
