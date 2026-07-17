"""
src/repositories/users_repo.py
DB-backed user lookup and creation.
Falls back gracefully when the DB is unavailable — callers handle None.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from src.log_privacy import user_ref

logger = logging.getLogger(__name__)


@dataclass
class User:
    id: int
    email: str
    password_hash: str
    role: str           # "admin" | "user"
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime]
    email_verified: bool = True


def get_user_by_email(email: str) -> Optional[User]:
    """Return the User row for this email, or None if not found / DB unavailable."""
    from src.db import get_db_connection, is_db_available
    if not is_db_available():
        return None
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, email, password_hash, role, is_active, created_at, last_login_at,
                       COALESCE(email_verified, TRUE)
                FROM users
                WHERE email = %s AND is_active = TRUE
                LIMIT 1
                """,
                (email.strip().lower(),),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return User(
                id=row[0],
                email=row[1],
                password_hash=row[2],
                role=row[3],
                is_active=row[4],
                created_at=row[5],
                last_login_at=row[6],
                email_verified=row[7],
            )
    except Exception:
        logger.error("users_repo_get_failed user=%s", user_ref(email))
        return None
    finally:
        conn.close()


def create_user(email: str, password_hash: str, role: str = "user") -> Optional[User]:
    """Insert a new user row. Returns the created User or None on failure."""
    from src.db import get_db_connection, is_db_available
    if not is_db_available():
        return None
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (email, password_hash, role, email_verified)
                VALUES (%s, %s, %s, FALSE)
                RETURNING id, email, password_hash, role, is_active, created_at, last_login_at,
                          email_verified
                """,
                (email.strip().lower(), password_hash, role),
            )
            row = cur.fetchone()
            conn.commit()
            return User(
                id=row[0],
                email=row[1],
                password_hash=row[2],
                role=row[3],
                is_active=row[4],
                created_at=row[5],
                last_login_at=row[6],
                email_verified=row[7],
            )
    except Exception:
        logger.error("users_repo_create_failed user=%s", user_ref(email))
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    finally:
        conn.close()


def set_signup_attribution(user_id: int, source: str, attribution: dict) -> bool:
    """Persist signup attribution for a user (requires migration 036).

    Best-effort: returns False when the DB or the columns are unavailable so
    registration proceeds regardless of migration state. Never raises.
    Logs user_id only — no email/PII.
    """
    from src.db import get_db_connection, is_db_available
    if not is_db_available():
        return False
    conn = get_db_connection()
    if not conn:
        return False
    try:
        from psycopg2.extras import Json
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET signup_source = %s,
                    signup_attribution = %s
                WHERE id = %s
                """,
                (source, Json(attribution) if attribution else None, user_id),
            )
        conn.commit()
        return True
    except Exception:
        logger.warning("users_repo_set_signup_attribution_failed user_id=%s", user_id)
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def get_signup_sources(user_ids: List[int]) -> dict[int, str]:
    """Map user id → signup_source for admin surfaces (requires migration 036).

    Best-effort: returns {} when the DB or the column is unavailable so callers
    degrade to showing no source. Never raises.
    """
    if not user_ids:
        return {}
    from src.db import get_db_connection, is_db_available
    if not is_db_available():
        return {}
    conn = get_db_connection()
    if not conn:
        return {}
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, signup_source
                FROM users
                WHERE id = ANY(%s) AND signup_source IS NOT NULL
                """,
                (list(user_ids),),
            )
            rows = cur.fetchall()
        return {row[0]: row[1] for row in rows}
    except Exception:
        logger.warning("users_repo_get_signup_sources_failed count=%s", len(user_ids))
        return {}
    finally:
        conn.close()


def update_password(email: str, new_hash: str) -> bool:
    """Update password_hash for the given email. Returns True on success."""
    from src.db import get_db_connection, is_db_available
    if not is_db_available():
        return False
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE email = %s AND is_active = TRUE",
                (new_hash, email.strip().lower()),
            )
            updated = cur.rowcount
        conn.commit()
        return updated > 0
    except Exception:
        logger.error("users_repo_update_password_failed user=%s", user_ref(email))
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def update_last_login(user_id: int) -> None:
    """Update last_login_at for the given user (best-effort, non-blocking)."""
    from src.db import get_db_connection, is_db_available
    if not is_db_available():
        return
    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET last_login_at = %s WHERE id = %s",
                (datetime.now(timezone.utc), user_id),
            )
        conn.commit()
    except Exception:
        logger.exception("users_repo_update_last_login_failed user_id=%s", user_id)
    finally:
        conn.close()


def mark_email_verified(email: str) -> bool:
    """Mark the user's email as verified. Returns True on success."""
    from src.db import get_db_connection, is_db_available
    if not is_db_available():
        return False
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET email_verified = TRUE WHERE email = %s AND is_active = TRUE",
                (email.strip().lower(),),
            )
            updated = cur.rowcount
        conn.commit()
        return updated > 0
    except Exception:
        logger.error("users_repo_mark_verified_failed user=%s", user_ref(email))
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def list_active_users() -> List[User]:
    """Return all active users.  Falls back to [] when DB is unavailable.

    This is the source-of-truth for the multi-user daily scheduler.
    Phase-1 scheduler support: returns [] when DB is unavailable.
    """
    from src.db import get_db_connection, is_db_available
    if not is_db_available():
        return []
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, email, password_hash, role, is_active, created_at, last_login_at,
                       COALESCE(email_verified, TRUE)
                FROM users
                WHERE is_active = TRUE
                ORDER BY id
                """,
            )
            rows = cur.fetchall()
        return [
            User(
                id=row[0],
                email=row[1],
                password_hash=row[2],
                role=row[3],
                is_active=row[4],
                created_at=row[5],
                last_login_at=row[6],
                email_verified=row[7],
            )
            for row in rows
        ]
    except Exception:
        logger.exception("users_repo_list_active_failed")
        return []
    finally:
        conn.close()
