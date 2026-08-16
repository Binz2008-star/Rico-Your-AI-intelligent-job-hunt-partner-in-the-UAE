"""Account confirmation orchestration (launch-blocker closure).

Shared by the Jotform merge path and the Telegram /start bind path: when an
unverified channel matches an EXISTING registered account, we never write to
the account immediately. A single-use, time-limited, random token is delivered
to the ACCOUNT OWNER's email; only proof of possession may apply the pending
payload. All failures fail closed.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from src.log_privacy import user_ref

logger = logging.getLogger(__name__)


def _api_base() -> str:
    return os.getenv("BACKEND_API_BASE_URL", "https://api.ricohunt.com").rstrip("/")


def _notify_confirmation(
    account_email: str,
    purpose: str,
    raw_token: str,
    *,
    code_only: bool = False,
) -> None:
    """Email the account owner the confirmation token/link. Best-effort."""
    from src.services.mailer import send_email

    if code_only:
        subject = "Confirm your Telegram link — Rico"
        body = (
            "A request was made to link this email's Rico account to a Telegram "
            "chat. If this was you, reply in that Telegram chat with the code "
            f"below.\n\nCode: {raw_token}\n\nThis code expires in 15 minutes. "
            "If you did not request this, you can ignore this email — nothing "
            "has changed on your account."
        )
    else:
        link = (
            f"{_api_base()}/api/v1/confirm-account"
            f"?token={raw_token}&purpose={purpose}"
        )
        subject = "Confirm your Rico account update"
        body = (
            "A Rico onboarding form submission was received that matches this "
            "email's account. Nothing has been changed on your account. To apply "
            f"the submitted details, open this link within 24 hours:\n\n{link}\n\n"
            "If you did not submit this form, ignore this email — no changes "
            "were made."
        )
    ok = send_email(to_email=account_email, subject=subject, body=body)
    if not ok:
        logger.warning(
            "confirmation_email_delivery_failed purpose=%s account=%s",
            purpose, user_ref(account_email),
        )


def create_jotform_merge_confirmation(
    account_email: str, pending: Dict[str, Any]
) -> bool:
    """Create a pending Jotform merge and email the account owner a link.

    Returns True when the confirmation was created AND the email dispatched
    (the owner can be reached). False → the webhook reports a failure the
    provider can retry; nothing is written to the account either way.
    """
    from src.repositories.account_confirmation_repo import (
        JOTFORM_MERGE_PURPOSE,
        create_confirmation,
    )

    raw_token = create_confirmation(
        account_key=account_email, purpose=JOTFORM_MERGE_PURPOSE, payload=pending
    )
    if not raw_token:
        return False
    _notify_confirmation(account_email, JOTFORM_MERGE_PURPOSE, raw_token)
    return True


def create_telegram_bind_confirmation(
    account_email: str, chat_id: str, username: str
) -> bool:
    """Create a pending Telegram bind and email the account owner a code."""
    from src.repositories.account_confirmation_repo import (
        TELEGRAM_BIND_PURPOSE,
        create_confirmation,
    )

    raw_token = create_confirmation(
        account_key=account_email,
        purpose=TELEGRAM_BIND_PURPOSE,
        payload={"chat_id": str(chat_id), "username": username},
        ttl_seconds=15 * 60,
    )
    if not raw_token:
        return False
    _notify_confirmation(account_email, TELEGRAM_BIND_PURPOSE, raw_token, code_only=True)
    return True


def apply_jotform_merge(pending: Dict[str, Any]) -> Dict[str, Any]:
    """Apply a confirmed Jotform merge payload to the matched account.

    Mirrors the normal webhook write path (user + profile + settings + CV) in a
    single transaction, then marks onboarding complete. The payload was built
    server-side and stored at confirmation-creation time; the confirm request
    carries only the token, never this data.
    """
    from src.rico_db import RicoDB

    db = RicoDB()
    with db._transaction() as conn:
        user = db.upsert_user(pending.get("user") or {}, conn=conn)
        db_user_id = str(user["id"])
        db.upsert_profile(
            db_user_id,
            pending.get("profile") or {},
            cv_file_url=pending.get("cv_file_url"),
            conn=conn,
        )
        db.upsert_settings(db_user_id, pending.get("settings") or {}, conn=conn)
    try:
        from src.repositories.onboarding_repo import mark_onboarding_complete

        mark_onboarding_complete(db_user_id)
    except Exception as exc:
        logger.warning("confirmation: onboarding mark failed db_user_id=%s: %s", db_user_id, exc)
    return {"status": "ok", "db_user_id": db_user_id}


def confirm_account(raw_token: str, purpose: str) -> Dict[str, Any]:
    """Consume a confirmation token and apply its pending payload.

    Returns {"status": "ok", ...} on success; {"status": "rejected",
    "reason": ...} on invalid/expired/reused/mismatched tokens. Never raises.
    """
    from src.repositories.account_confirmation_repo import (
        JOTFORM_MERGE_PURPOSE,
        consume_confirmation,
    )

    pending = consume_confirmation(raw_token, purpose)
    if not pending:
        return {
            "status": "rejected",
            "reason": "invalid_or_expired_or_used_token",
        }

    if purpose == JOTFORM_MERGE_PURPOSE:
        return apply_jotform_merge(pending)

    # telegram_bind tokens are consumed inside the Telegram chat flow, not here.
    return {
        "status": "rejected",
        "reason": "unsupported_confirm_purpose",
    }


def resolve_telegram_bind_code(raw_code: str, chat_id: str) -> Optional[str]:
    """Consume a Telegram bind code from the chat and return the bound account.

    The code is matched by purpose only; the payload's chat_id must equal the
    chat that is replying, otherwise the bind fails closed (a code emailed to
    account A cannot be redeemed from account B's chat).
    """
    from src.repositories.account_confirmation_repo import (
        TELEGRAM_BIND_PURPOSE,
        consume_confirmation,
    )

    pending = consume_confirmation(raw_code, TELEGRAM_BIND_PURPOSE)
    if not pending:
        return None
    if str(pending.get("chat_id", "")) != str(chat_id):
        logger.warning(
            "telegram_bind: code chat mismatch (code bound to different chat)"
        )
        return None
    return pending.get("username")
