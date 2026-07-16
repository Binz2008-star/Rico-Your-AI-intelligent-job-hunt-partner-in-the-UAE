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
        # Consent is durable state: require DB persistence so a swallowed DB
        # failure returns False rather than a false success (#1082).
        upsert_profile(user_id=user_id, updates=updates, require_db=True)
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
        # Opt-out MUST persist durably; a mirror-only write would leave the
        # persisted roster opted-in and still deliver later (#1082).
        upsert_profile(user_id=user_id, updates={"can_receive_email_alerts": False}, require_db=True)
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


# ---------------------------------------------------------------------------
# Email alert log — per-(user, job) dedup + per-period send cap
# ---------------------------------------------------------------------------
# Backed by email_alert_log (migration 033). Mirrors the telegram_alert_log
# helpers on RicoDB. All best-effort: on DB/table absence they fail open in the
# safe direction (dedup: "not sent"; cap: "0 sent") so a missing migration
# never blocks or duplicates alerts silently.

_EMAIL_ALERT_TYPE = "job_match"


def was_email_alert_sent(user_id: str, job_key: str, alert_type: str = _EMAIL_ALERT_TYPE) -> bool:
    """Return True if this (user, job, type) was already emailed. Never raises."""
    if not user_id or not job_key:
        return False
    from src.db import get_db_connection

    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM email_alert_log WHERE user_id=%s AND job_key=%s AND alert_type=%s",
                (user_id, job_key, alert_type),
            )
            return cur.fetchone() is not None
    except Exception:
        logger.debug("email_notifications.was_email_alert_sent failed user=%s", user_id, exc_info=True)
        return False
    finally:
        conn.close()


def get_sent_job_keys(user_id: str, alert_type: str = _EMAIL_ALERT_TYPE) -> set[str]:
    """Return the set of job_keys already emailed to *user_id* for *alert_type*.

    One query for the whole per-user dedup check, replacing a per-candidate
    ``was_email_alert_sent`` round trip (each of which opened its own connection).
    Fails open to an empty set on DB error so a transient failure never blocks a
    send. Never raises.
    """
    if not user_id:
        return set()
    from src.db import get_db_connection

    conn = get_db_connection()
    if not conn:
        return set()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT job_key FROM email_alert_log WHERE user_id=%s AND alert_type=%s",
                (user_id, alert_type),
            )
            return {row[0] for row in cur.fetchall()}
    except Exception:
        logger.debug("email_notifications.get_sent_job_keys failed user=%s", user_id, exc_info=True)
        return set()
    finally:
        conn.close()


def log_email_alert(user_id: str, job_key: str, alert_type: str = _EMAIL_ALERT_TYPE) -> bool:
    """Record that a job was emailed. Returns True if newly inserted (not a dup)."""
    if not user_id or not job_key:
        return False
    from src.db import get_db_connection

    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO email_alert_log (user_id, job_key, alert_type)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, job_key, alert_type) DO NOTHING
                """,
                (user_id, job_key, alert_type),
            )
            inserted = cur.rowcount > 0
        conn.commit()
        return inserted
    except Exception:
        logger.debug("email_notifications.log_email_alert failed user=%s", user_id, exc_info=True)
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def emailed_within_hours(user_id: str, hours: int, alert_type: str = _EMAIL_ALERT_TYPE) -> bool:
    """Return True if any alert email was logged for the user within *hours*.

    Backs the frequency cap. The window is expressed in hours (not days) and set
    shorter than the nominal cadence so a ~24h daily / ~7d weekly cron with normal
    jitter is not skipped when the previous send lands just inside a same-length
    window. Fails open to False (allow sending) on DB error so a transient failure
    never permanently mutes a user.
    """
    if not user_id or hours <= 0:
        return False
    from src.db import get_db_connection

    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM email_alert_log
                 WHERE user_id = %s
                   AND alert_type = %s
                   AND sent_at >= NOW() - (%s * INTERVAL '1 hour')
                 LIMIT 1
                """,
                (user_id, alert_type, hours),
            )
            return cur.fetchone() is not None
    except Exception:
        logger.debug("email_notifications.emailed_within_hours failed user=%s", user_id, exc_info=True)
        return False
    finally:
        conn.close()
