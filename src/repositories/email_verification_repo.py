"""
src/repositories/email_verification_repo.py
Token storage for the email-verification flow.

Only the SHA-256 hash of the raw token is persisted — plaintext never touches the DB.
Pattern mirrors password_reset_repo.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.log_privacy import user_ref

logger = logging.getLogger(__name__)
_UTC = timezone.utc
_TOKEN_TTL_HOURS = 24


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_verification_token(email: str) -> str:
    """
    Generate a secure verification token, store its hash, return the plaintext token.
    Raises RuntimeError if the DB is unavailable.
    """
    from src.db import get_db_connection
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    expires_at = datetime.now(_UTC) + timedelta(hours=_TOKEN_TTL_HOURS)

    conn = get_db_connection()
    if not conn:
        raise RuntimeError("DB unavailable — cannot create email verification token")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO email_verification_tokens (user_email, token_hash, expires_at)
                VALUES (%s, %s, %s)
                """,
                (email.strip().lower(), token_hash, expires_at),
            )
        conn.commit()
    except Exception:
        logger.error("email_verification_repo_create_failed user=%s", user_ref(email))
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()

    return token


def consume_verification_token(token: str) -> Optional[str]:
    """
    Atomically validate and mark the token used.
    Returns the associated email on success, None if invalid / expired / already used.
    """
    from src.db import get_db_connection
    token_hash = _hash_token(token)
    now = datetime.now(_UTC)

    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE email_verification_tokens
                   SET used_at = %s
                 WHERE token_hash = %s
                   AND used_at IS NULL
                   AND expires_at > %s
                RETURNING user_email
                """,
                (now, token_hash, now),
            )
            row = cur.fetchone()
        conn.commit()
        return row[0] if row else None
    except Exception:
        logger.exception("email_verification_repo_consume_failed")
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    finally:
        conn.close()


def check_verification_token(token: str) -> Optional[str]:
    """
    Validate a token WITHOUT consuming it.

    Returns the associated email if the token is valid and unused, None
    otherwise.  This is scanner-safe: email link prefetchers that issue
    GET requests will not burn the token.  The actual consumption must
    happen via ``consume_verification_token`` in a POST handler.
    """
    from src.db import get_db_connection
    token_hash = _hash_token(token)
    now = datetime.now(_UTC)

    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_email
                  FROM email_verification_tokens
                 WHERE token_hash = %s
                   AND used_at IS NULL
                   AND expires_at > %s
                """,
                (token_hash, now),
            )
            row = cur.fetchone()
        return row[0] if row else None
    except Exception:
        logger.exception("email_verification_repo_check_failed")
        return None
    finally:
        conn.close()
