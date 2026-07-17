"""src/rico_telegram_webhook.py — Telegram webhook controller for Rico AI."""
from __future__ import annotations

import logging
import time
from collections import deque
from threading import Lock
from typing import Any, Deque, Dict, Set, Tuple

from src.rico_chat_api import RicoChatAPI
from src.rico_telegram_ui import handle_callback_only
from src.telegram_actions import answer_callback_query
from src.telegram_bot import send_telegram_to_user
from src.repositories.profile_repo import find_profiles_by_telegram_username, upsert_profile

logger = logging.getLogger(__name__)

chat_api = RicoChatAPI()

# ---------------------------------------------------------------------------
# Duplicate-update guard: prevent Telegram webhook retries from double-processing
# ---------------------------------------------------------------------------
# Stores (update_id, expiry_ts) pairs. Capacity-bounded — keeps at most
# _SEEN_MAX entries so memory stays O(1) regardless of traffic.
_SEEN_LOCK: Lock = Lock()
_SEEN_IDS: Deque[Tuple[int, float]] = deque()
_SEEN_SET: Set[int] = set()
_SEEN_MAX = 2000
_SEEN_TTL = 3600  # 1 hour — Telegram retries expire well within this window


def _is_duplicate_update(update_id: int) -> bool:
    """Return True if this update_id was already processed. Thread-safe."""
    now = time.monotonic()
    with _SEEN_LOCK:
        # Purge expired entries from the front of the deque
        while _SEEN_IDS and _SEEN_IDS[0][1] < now:
            _SEEN_SET.discard(_SEEN_IDS.popleft()[0])

        if update_id in _SEEN_SET:
            return True

        # Evict oldest if at capacity
        if len(_SEEN_SET) >= _SEEN_MAX:
            oldest_id, _ = _SEEN_IDS.popleft()
            _SEEN_SET.discard(oldest_id)

        expiry = now + _SEEN_TTL
        _SEEN_IDS.append((update_id, expiry))
        _SEEN_SET.add(update_id)
        return False


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

    linked = False
    if chat_id:
        try:
            # Consent state is durable state (#1082): the link/enable write must
            # commit to the canonical DB. require_db raises on DB unavailability
            # or write failure instead of confirming from the process-local
            # mirror, so the "now linked" reply below is never a false claim.
            upsert_profile(
                bound_user_id,
                {
                    "telegram_chat_id": chat_id,
                    "telegram_notifications_enabled": True,
                    **({"telegram_username": username} if username else {}),
                },
                require_db=True,
            )
            linked = True
        except Exception as exc:
            logger.warning("telegram_start: upsert failed user=%s: %s", bound_user_id, exc)

    display = f"@{username}" if username else f"chat {chat_id}"
    if linked:
        reply = (
            f"Welcome to Rico! Your Telegram ({display}) is now linked. "
            "I'll send you job alerts and follow-up reminders here. "
            "Send /stop at any time to pause notifications."
        )
    else:
        # Don't tell the user linking succeeded when the profile write actually
        # failed — they'd believe notifications are on when nothing was persisted.
        reply = (
            "I couldn't link your Telegram right now due to a temporary issue. "
            "Please send /start again in a moment."
        )
    logger.info("telegram_start: bound chat_id=%s to user=%s linked=%s", chat_id, bound_user_id, linked)
    if chat_id:
        send_telegram_to_user(chat_id, reply)
    return {"chat_id": chat_id, "reply": reply}


def _handle_stop(message: Dict[str, Any]) -> Dict[str, Any]:
    """Durably disable notifications for every account bound to this Telegram chat."""
    from src.repositories.profile_repo import disable_telegram_alerts_for_chat

    chat_id = str(message.get("chat", {}).get("id") or message.get("from", {}).get("id") or "")

    stopped = False
    if chat_id:
        try:
            # Opt-out is durable consent (#1082): disable EVERY rico_users row
            # bound to this chat_id (native Telegram row and/or web-linked
            # account) in one committed DB write, so the next roster excludes
            # the chat entirely. Raises on DB failure — no committed row means
            # no "Notifications paused" claim.
            disabled = disable_telegram_alerts_for_chat(chat_id)
            if disabled == 0:
                # Chat never linked a row by chat_id (e.g. /stop before /start):
                # persist an explicit opt-out row durably so consent survives.
                upsert_profile(
                    chat_id,
                    {"telegram_chat_id": chat_id, "telegram_notifications_enabled": False},
                    require_db=True,
                )
            stopped = True
        except Exception as exc:
            logger.warning("telegram_stop: durable opt-out failed chat_id=%s: %s", chat_id, exc)

    if stopped:
        reply = "Notifications paused. Send /start to re-enable them whenever you're ready."
    else:
        reply = "I couldn't update your notification settings right now. Please try /stop again shortly."
    logger.info("telegram_stop: disabled notifications for chat_id=%s ok=%s", chat_id, stopped)
    if chat_id:
        send_telegram_to_user(chat_id, reply)
    return {"chat_id": chat_id, "reply": reply}


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

def process_telegram_update(update: Dict[str, Any]) -> Dict[str, Any]:
    # Deduplicate: Telegram retries the same update_id if our server returns
    # a non-2xx response or times out. Silently ack duplicates without re-processing.
    update_id = update.get("update_id")
    if update_id is not None and _is_duplicate_update(int(update_id)):
        logger.debug("telegram_duplicate_update skipped update_id=%s", update_id)
        return {"ok": True, "skipped": True}

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
    chat_id = str(chat.get("id") or tg_user.get("id") or "")
    user_id = chat_id or "telegram-user"

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

    reply_text = response.get("message", "") if isinstance(response, dict) else str(response)
    if chat_id and reply_text:
        ok = send_telegram_to_user(chat_id, reply_text)
        if not ok:
            logger.warning("telegram_send_failed chat_id=%s", chat_id)

    return {
        "chat_id": chat.get("id"),
        "reply": response,
    }
