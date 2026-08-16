"""Content-free usage ledger for public/guest AI turns (final hardening review).

Closes the confirmed anti-dodge gap: a registered email used on the public chat
endpoints is checked against the account allowance, but public turns were never
recorded — so the cap never enforced. This ledger records usage per account
identity + usage window WITHOUT writing message content into chat history.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.db import get_db_connection

logger = logging.getLogger(__name__)
_UTC = timezone.utc


def _normalise_key(identity_key: str) -> str:
    return identity_key.strip().lower()


def record_public_ai_usage(identity_key: str, window_start: datetime | None = None) -> bool:
    """Increment the usage counter for *identity_key*.

    *window_start* defaults to the start of the current UTC day — the counter's
    COUNT query sums rows whose window_start >= the allowance window start, so a
    daily-granular ledger row is counted for both the Free daily and paid
    billing-period windows.

    Best-effort: a failed write must not break the chat turn itself, but a
    failure is logged loudly — silent under-counting is the exact bug this
    ledger exists to prevent.
    """
    key = _normalise_key(identity_key)
    if not key:
        return False
    if window_start is None:
        window_start = datetime.now(_UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    if window_start.tzinfo is None:
        window_start = window_start.replace(tzinfo=_UTC)
    conn = get_db_connection()
    if conn is None:
        logger.warning("ai_usage: ledger write skipped (db unavailable) key=%s", key[:8])
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rico_public_ai_usage (identity_key, window_start, ai_count)
                VALUES (%s, %s, 1)
                ON CONFLICT (identity_key, window_start)
                DO UPDATE SET ai_count = rico_public_ai_usage.ai_count + 1,
                              updated_at = NOW()
                """,
                (key, window_start),
            )
        conn.commit()
        return True
    except Exception:
        logger.warning("ai_usage: ledger write failed key=%s", key[:8], exc_info=True)
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def count_public_ai_usage(identity_key: str, since: datetime) -> int:
    """Return total public-turn usage for *identity_key* at/after *since*.

    Read-path: returns 0 on DB unavailability (the caller's authenticated
    allowance is the primary gate)."""
    try:
        return _count_usage(identity_key, since)
    except Exception:
        # Table not migrated yet or DB issue: degrade to 0 (read-only path).
        logger.debug("ai_usage: ledger read failed key=%s", identity_key[:8], exc_info=True)
        return 0


def count_public_ai_usage_strict(identity_key: str, since: datetime) -> int:
    """Strict variant for unbound identities whose ONLY gate is this ledger.

    Raises when the ledger cannot be consulted, so callers can FAIL CLOSED
    (deny) instead of granting unlimited usage during a DB outage.
    """
    return _count_usage(identity_key, since)


def _count_usage(identity_key: str, since: datetime) -> int:
    key = _normalise_key(identity_key)
    if not key:
        return 0
    if since.tzinfo is None:
        since = since.replace(tzinfo=_UTC)
    conn = get_db_connection()
    if conn is None:
        raise RuntimeError("ai_usage ledger unavailable (db down)")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(SUM(ai_count), 0) AS total
                FROM rico_public_ai_usage
                WHERE identity_key = %s AND window_start >= %s
                """,
                (key, since),
            )
            row = cur.fetchone()
            return int(row["total"] if isinstance(row, dict) else row[0])
    finally:
        conn.close()
