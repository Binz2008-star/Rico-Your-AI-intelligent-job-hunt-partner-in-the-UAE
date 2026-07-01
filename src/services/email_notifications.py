"""src/services/email_notifications.py

Per-user email job-alert opt-in / opt-out and unsubscribe-token management.

Mirrors src/services/telegram_notifications.py so the two channels behave the
same way:
- Alerts are sent ONLY after the user explicitly opts in.
- Opt-in state and cadence live in rico_agent_settings.settings (JSONB):
  ``can_receive_email_alerts`` (bool) and ``email_alert_frequency`` ("daily"|"weekly").
- Opt-in mints a login-free unsubscribe token so every alert email can carry a
  one-click unsubscribe link. Opt-out flips the flag but keeps the token so a
  later re-subscribe reuses it.

This module is PR-1 plumbing: it does NOT send any email. Sending lands in a
later PR (email_alert_service). All DB access is best-effort and never raises —
the flag write via upsert_profile always happens even if the token table is
missing, so opt-in degrades gracefully.
"""
from __future__ import annotations

import logging
import secrets
from typing import Optional

from src.repositories.profile_repo import get_profile, upsert_profile

logger = logging.getLogger(__name__)

_VALID_FREQUENCIES = frozenset({"daily", "weekly"})


# ---------------------------------------------------------------------------
# Opt-in / opt-out / status
# ---------------------------------------------------------------------------

def is_opted_in(user_id: str) -> bool:
    """Return True if the user has opted in to email job alerts."""
    try:
        profile = get_profile(user_id)
        if not profile:
            return False
        settings = getattr(profile, "settings", None)
        return bool(getattr(settings, "can_receive_email_alerts", False)) if settings else False
    except Exception:
        logger.debug("email_notifications.is_opted_in failed user=%s", user_id, exc_info=True)
        return False


def get_frequency(user_id: str) -> str:
    """Return the user's email alert cadence ("daily" or "weekly"). Defaults to daily."""
    try:
        profile = get_profile(user_id)
        settings = getattr(profile, "settings", None) if profile else None
        freq = getattr(settings, "email_alert_frequency", "daily") if settings else "daily"
        return freq if freq in _VALID_FREQUENCIES else "daily"
    except Exception:
        return "daily"


def opt_in(user_id: str, frequency: str | None = None) -> bool:
    """Opt a user in to email job alerts.

    Sets ``can_receive_email_alerts=True`` (and optionally the cadence) and mints
    an unsubscribe token if one does not already exist. Returns True on success.
    """
    try:
        updates: dict = {"can_receive_email_alerts": True}
        if frequency is not None:
            freq = frequency.strip().lower()
            if freq not in _VALID_FREQUENCIES:
                freq = "daily"
            updates["email_alert_frequency"] = freq
        upsert_profile(user_id=user_id, updates=updates)
        # Best-effort token mint — an opt-in must still succeed if the token
        # table is missing (e.g. migration 033 not yet applied).
        ensure_unsubscribe_token(user_id)
        logger.info("email_notifications.opt_in user=%s frequency=%s", user_id, frequency)
        return True
    except Exception:
        logger.exception("email_notifications.opt_in failed user=%s", user_id)
        return False


def opt_out(user_id: str) -> bool:
    """Opt a user out of email job alerts.

    Flips ``can_receive_email_alerts=False``. The unsubscribe token is kept so a
    later re-subscribe reuses the same link. Returns True on success.
    """
    try:
        upsert_profile(user_id=user_id, updates={"can_receive_email_alerts": False})
        logger.info("email_notifications.opt_out user=%s", user_id)
        return True
    except Exception:
        logger.exception("email_notifications.opt_out failed user=%s", user_id)
        return False


# ---------------------------------------------------------------------------
# Unsubscribe tokens (login-free one-click unsubscribe)
# ---------------------------------------------------------------------------

def ensure_unsubscribe_token(user_id: str) -> Optional[str]:
    """Return the user's unsubscribe token, minting one if absent.

    Idempotent: ON CONFLICT keeps the existing token so the link is stable.
    Returns None when the DB (or table) is unavailable. Never raises.
    """
    if not user_id:
        return None
    from src.db import get_db_connection

    conn = get_db_connection()
    if not conn:
        return None
    try:
        token = secrets.token_urlsafe(32)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO email_unsubscribe_tokens (user_id, token)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO NOTHING
                RETURNING token
                """,
                (user_id, token),
            )
            row = cur.fetchone()
            if row:
                minted = row[0]
            else:
                # Row already existed — read the stored token back.
                cur.execute(
                    "SELECT token FROM email_unsubscribe_tokens WHERE user_id = %s",
                    (user_id,),
                )
                existing = cur.fetchone()
                minted = existing[0] if existing else None
        conn.commit()
        return minted
    except Exception:
        logger.debug("email_notifications.ensure_unsubscribe_token failed user=%s", user_id, exc_info=True)
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    finally:
        conn.close()


def resolve_user_by_token(token: str) -> Optional[str]:
    """Return the user_id for an unsubscribe token, or None if unknown. Never raises."""
    tok = (token or "").strip()
    if not tok:
        return None
    from src.db import get_db_connection

    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id FROM email_unsubscribe_tokens WHERE token = %s",
                (tok,),
            )
            row = cur.fetchone()
        return row[0] if row else None
    except Exception:
        logger.debug("email_notifications.resolve_user_by_token failed", exc_info=True)
        return None
    finally:
        conn.close()


def unsubscribe_by_token(token: str) -> bool:
    """Opt a user out via their unsubscribe token (no login required).

    Returns True when a matching user was found and opted out. Returns False for
    an unknown/invalid token. Never raises.
    """
    user_id = resolve_user_by_token(token)
    if not user_id:
        return False
    return opt_out(user_id)
