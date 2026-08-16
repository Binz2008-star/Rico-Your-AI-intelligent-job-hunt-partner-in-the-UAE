"""Out-of-band account ownership confirmation (launch-blocker closure).

A public Jotform submission or a Telegram /start username match must NOT write
into an existing registered account on unverified input. This module provides
the shared primitive: a cryptographically-random, single-use, time-limited,
hash-at-rest confirmation token delivered to the ACCOUNT OWNER. Only a valid,
unexpired, unused, purpose- and account-matched token may apply the server-built
pending payload. Every failure fails closed.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from src.db import get_db_connection

logger = logging.getLogger(__name__)
_UTC = timezone.utc

JOTFORM_MERGE_PURPOSE = "jotform_merge"
TELEGRAM_BIND_PURPOSE = "telegram_bind"

_DEFAULT_TTL_SECONDS = {
    JOTFORM_MERGE_PURPOSE: 24 * 3600,
    TELEGRAM_BIND_PURPOSE: 15 * 60,
}


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_confirmation(
    account_key: str,
    purpose: str,
    payload: Optional[Dict[str, Any]] = None,
    ttl_seconds: Optional[int] = None,
) -> Optional[str]:
    """Create a pending confirmation and return the RAW token (deliver to the
    account owner). Returns None on failure. The token is never stored raw —
    only its SHA-256 hash is persisted.
    """
    account_key = (account_key or "").strip().lower()
    if not account_key or not purpose:
        return None
    if ttl_seconds is None:
        ttl_seconds = _DEFAULT_TTL_SECONDS.get(purpose, 24 * 3600)

    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(_UTC) + timedelta(seconds=ttl_seconds)

    conn = get_db_connection()
    if conn is None:
        logger.warning("confirmation: create skipped (db unavailable) account=%s", account_key[:8])
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO account_confirmations
                    (account_key, purpose, token_hash, payload, expires_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (account_key, purpose, token_hash, __import__("json").dumps(payload) if payload else None, expires_at),
            )
        conn.commit()
        return raw_token
    except Exception:
        logger.warning("confirmation: create failed account=%s", account_key[:8], exc_info=True)
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    finally:
        conn.close()


def consume_confirmation(
    raw_token: str,
    purpose: str,
    expected_account_key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Atomically consume a confirmation token.

    Returns the payload (dict) iff the token is valid, unexpired, unused,
    purpose-matched and (when given) account-matched. Single-use is enforced in
    one UPDATE ... RETURNING so concurrent replays cannot both win. Any mismatch
    returns None and the token is left unconsumed (rejected, not marked used).
    """
    token = (raw_token or "").strip()
    if not token or not purpose:
        return None
    token_hash = _hash_token(token)

    conn = get_db_connection()
    if conn is None:
        logger.warning("confirmation: consume skipped (db unavailable)")
        return None
    try:
        with conn.cursor() as cur:
            if expected_account_key is not None:
                cur.execute(
                    """
                    UPDATE account_confirmations
                       SET used_at = NOW()
                     WHERE token_hash = %s
                       AND purpose = %s
                       AND account_key = %s
                       AND used_at IS NULL
                       AND expires_at > NOW()
                     RETURNING payload, account_key
                    """,
                    (token_hash, purpose, expected_account_key.strip().lower()),
                )
            else:
                cur.execute(
                    """
                    UPDATE account_confirmations
                       SET used_at = NOW()
                     WHERE token_hash = %s
                       AND purpose = %s
                       AND used_at IS NULL
                       AND expires_at > NOW()
                     RETURNING payload, account_key
                    """,
                    (token_hash, purpose),
                )
            row = cur.fetchone()
        conn.commit()
        if not row:
            return None
        import json

        payload = row["payload"] if isinstance(row, dict) else row[0]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = None
        return dict(payload) if isinstance(payload, dict) else {}
    except Exception:
        logger.warning("confirmation: consume failed", exc_info=True)
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    finally:
        conn.close()
