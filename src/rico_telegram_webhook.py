"""src/rico_telegram_webhook.py — Telegram webhook controller for Rico AI."""
from __future__ import annotations

import logging
import os
import time
from collections import deque
from threading import Lock
from typing import Any, Deque, Dict, Optional, Set, Tuple

from src.rico_chat_api import RicoChatAPI
from src.rico_telegram_ui import handle_callback_only
from src.telegram_actions import answer_callback_query
from src.telegram_bot import send_telegram_to_user
from src.repositories.profile_repo import find_profiles_by_telegram_username, upsert_profile
from src.models.principal import IdentityOwnershipAmbiguous
from src.log_privacy import user_ref

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


def _is_seen_update(update_id: int) -> bool:
    """Return True if this update_id was already processed (no side effect).

    Thread-safe, read-only: marking happens ONLY after processing succeeds
    (see _mark_seen_update), so a failed delivery is never silently swallowed
    as a duplicate — Telegram retries it and the action is not lost.
    """
    now = time.monotonic()
    with _SEEN_LOCK:
        while _SEEN_IDS and _SEEN_IDS[0][1] < now:
            _SEEN_SET.discard(_SEEN_IDS.popleft()[0])
        return update_id in _SEEN_SET


def _mark_seen_update(update_id: int) -> None:
    """Record an update_id as processed. Thread-safe; capacity-bounded."""
    now = time.monotonic()
    with _SEEN_LOCK:
        while _SEEN_IDS and _SEEN_IDS[0][1] < now:
            _SEEN_SET.discard(_SEEN_IDS.popleft()[0])
        if len(_SEEN_SET) >= _SEEN_MAX:
            oldest_id, _ = _SEEN_IDS.popleft()
            _SEEN_SET.discard(oldest_id)
        expiry = now + _SEEN_TTL
        _SEEN_IDS.append((update_id, expiry))
        _SEEN_SET.add(update_id)


# ---------------------------------------------------------------------------
# /start and /stop handlers
# ---------------------------------------------------------------------------

def _handle_start(message: Dict[str, Any]) -> Dict[str, Any]:
    """Bind this Telegram chat_id to the user's Rico profile and enable notifications.

    Lookup priority:
    1. Match message.from.username against rico_users.telegram_username (WebApp users
       who have already shared their handle via chat).
    2. If no match, treat the chat_id itself as the Rico user_id (pure Telegram users).

    Launch-blocker closure: a Telegram username match is NOT sufficient durable
    ownership proof — a freed/abandoned handle could be re-bound to a victim's
    account. When a username matches an EXISTING account, an out-of-band
    one-time code is emailed to that account's address and the chat is bound
    only after the owner replies with the code. Native (unmatched) chats bind by
    chat identity as before.
    """
    chat_id = str(message.get("chat", {}).get("id") or message.get("from", {}).get("id") or "")
    username = (message.get("from", {}).get("username") or "").strip().lstrip("@").lower()

    bound_user_id: str | None = None

    if username:
        try:
            matches = find_profiles_by_telegram_username(username)
            if matches:
                matched = matches[0].user_id
                from src.services.account_confirmation_service import (
                    create_telegram_bind_confirmation,
                )

                if create_telegram_bind_confirmation(matched, chat_id, username):
                    reply = (
                        "This Telegram username is already linked to a Rico account. "
                        "I emailed a one-time confirmation code to that account's email. "
                        "Reply with the code here to link this chat."
                    )
                else:
                    reply = (
                        "I couldn't verify this account right now. "
                        "Please try /start again in a moment."
                    )
                if chat_id:
                    send_telegram_to_user(chat_id, reply)
                return {"chat_id": chat_id, "reply": reply}
        except Exception as exc:
            logger.warning("telegram_start: confirmation path failed username=%s: %s", username, exc)

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

def _resolve_registered_user(chat_id: str) -> str | None:
    """Return the registered web account bound to this Telegram chat, if any.

    Only a Telegram chat that was linked to a web account (/start with a matching
    username) has an entitlement relationship; a bound account must be held to the
    same subscription gates as the web surface. Never raises.
    """
    if not chat_id:
        return None
    try:
        from src.repositories.profile_repo import find_registered_user_by_telegram_chat_id

        return find_registered_user_by_telegram_chat_id(chat_id)
    except Exception:
        logger.warning("telegram: registered-user resolution failed chat_id=%s", chat_id)
        return None


def _gate_telegram_ai(user_id: str) -> str | None:
    """Return a gate reply when this user has no AI-message allowance left.

    Mirrors the web surface's entitlement gate (check_ai_message_allowed_for_user)
    so a Telegram chat bound to a registered account cannot bypass the paid
    AI-message cap. Returns None when allowed or when usage cannot be verified.
    """
    try:
        from src.services.subscription_gating import (
            QuotaUnavailableError,
            check_ai_message_allowed_for_user,
        )

        gate = check_ai_message_allowed_for_user(user_id)
    except QuotaUnavailableError:
        # Usage cannot be verified (DB down) — fail closed rather than granting
        # untracked AI usage on the Telegram surface.
        return "I can't verify your usage right now because the service is temporarily unavailable. Please try again in a few minutes."
    except IdentityOwnershipAmbiguous:
        # Ambiguous/undecidable account ownership must NOT fail open on Telegram:
        # the web surface refuses (account_conflict) rather than granting usage.
        logger.warning("telegram: ai gate ambiguous account identity user=%s", user_ref(user_id))
        return (
            "This account could not be resolved unambiguously, so it cannot "
            "be used right now. Please contact support."
        )
    except Exception:
        return None
    if gate and not gate.allowed:
        return gate.message
    return None


def process_telegram_update(update: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch a Telegram update, deduplicating retries WITHOUT losing work.

    Telegram retries the same update_id when our server returns a non-2xx
    response or times out. The seen-mark is applied ONLY after processing
    succeeds, so a failed delivery is retried (at-least-once) instead of being
    silently skipped as a duplicate — an action (save/apply/stop) is never lost
    to a transient 500.
    """
    update_id = update.get("update_id")
    if update_id is not None and _is_seen_update(int(update_id)):
        logger.debug("telegram_duplicate_update skipped update_id=%s", update_id)
        return {"ok": True, "skipped": True}

    result = _process_update(update)

    if update_id is not None:
        _mark_seen_update(int(update_id))
    return result


def _looks_like_bind_code(text: str) -> bool:
    """True when *text* has the shape of a confirmation code (urlsafe 43 chars).

    Keeps the code-reply check off every ordinary message.
    """
    if len(text) != 43:
        return False
    return all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-" for c in text)


def _handle_bind_code_reply(text: str, chat_id: str) -> Optional[Dict[str, Any]]:
    """Bind this chat to the account whose emailed code was just redeemed.

    Returns a reply dict when the code was valid AND bound; None otherwise
    (fall through to normal message handling). Single-use code, chat-scoped.
    """
    if not _looks_like_bind_code(text) or not chat_id:
        return None
    from src.services.account_confirmation_service import resolve_telegram_bind_code

    bound_email = resolve_telegram_bind_code(text, chat_id)
    if not bound_email:
        return None
    try:
        upsert_profile(
            bound_email,
            {
                "telegram_chat_id": chat_id,
                "telegram_notifications_enabled": True,
            },
            require_db=True,
        )
        reply = "Telegram is now linked to your Rico account."
    except Exception as exc:
        logger.warning("telegram_bind: profile write failed chat_id=%s: %s", chat_id, exc)
        reply = "I couldn't link your account right now. Please try /start again."
    if chat_id:
        send_telegram_to_user(chat_id, reply)
    return {"chat_id": chat_id, "reply": {"message": reply}}


def _gate_native_telegram(chat_id: str) -> str | None:
    """Bounded daily AI allowance for unbound (native) Telegram chats.

    Launch-blocker closure: an unbound chat must not be an unlimited LLM proxy.
    The allowance is a fixed daily cap keyed by the chat identity in the
    content-free usage ledger. DB failures FAIL CLOSED (deny) — never unlimited.
    """
    if not chat_id:
        return None
    limit = int(os.environ.get("RICO_TELEGRAM_GUEST_DAILY_LIMIT", "10") or "10")
    from datetime import datetime, timezone

    from src.repositories.ai_usage_repo import (
        count_public_ai_usage_strict,
        record_public_ai_usage,
    )

    now = datetime.now(timezone.utc)
    window_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        usage = count_public_ai_usage_strict(chat_id, window_start)
    except Exception:
        logger.warning("telegram: native gate verification failed chat_id=%s", chat_id)
        return (
            "I can't verify your usage right now because the service is "
            "temporarily unavailable. Please try again in a few minutes."
        )
    if usage >= limit:
        return (
            f"You've reached today's free message limit ({limit}). "
            "Link your Rico account with /start to continue."
        )
    record_public_ai_usage(chat_id)
    return None


def _process_update(update: Dict[str, Any]) -> Dict[str, Any]:
    """Process one Telegram update. Raises on failure so the caller can retry.

    The deduplication seen-mark is applied by process_telegram_update only after
    this returns without raising.
    """
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

    # Telegram bind confirmation: a code emailed to the account owner, replied
    # in this chat, binds the chat to the account (single-use, chat-scoped).
    bind_result = _handle_bind_code_reply(text, chat_id)
    if bind_result is not None:
        return bind_result

    # Entitlement gate: a Telegram chat bound to a registered web account is held
    # to the same AI-message cap as the web chat (billing bypass fix). Native
    # Telegram-only chats (no web account, no subscription relationship) are not
    # gated here — that remains an explicit product decision.
    bound_user = _resolve_registered_user(chat_id)
    if bound_user:
        gate_reply = _gate_telegram_ai(bound_user)
        if gate_reply:
            if chat_id:
                send_telegram_to_user(chat_id, gate_reply)
            return {"chat_id": chat.get("id"), "reply": {"message": gate_reply}}
        # The bound account runs under ITS identity (email), not the raw
        # chat_id: the turn is recorded in rico_chat_history under the account
        # so the AI-message allowance is actually consumed by Telegram usage
        # (final-hardening billing fix). The gate above already verified the
        # allowance.
        user_id = bound_user
    else:
        # Unbound (native) Telegram chat: bounded daily AI allowance, fail
        # closed on DB outage — never an unlimited LLM proxy.
        native_gate = _gate_native_telegram(chat_id)
        if native_gate:
            if chat_id:
                send_telegram_to_user(chat_id, native_gate)
            return {"chat_id": chat.get("id"), "reply": {"message": native_gate}}

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
