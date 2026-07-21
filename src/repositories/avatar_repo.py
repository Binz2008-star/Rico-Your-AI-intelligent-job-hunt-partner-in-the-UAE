"""
src/repositories/avatar_repo.py
Profile avatar storage (migration 050_user_avatars.sql).

The avatar lives in a DEDICATED table as a compact data URL so the base64
payload never rides along in profile fetches or the LLM chat context.
Fail-open contract: if the DB (or the table, pre-migration) is unavailable,
reads return None and writes raise RuntimeError — callers turn that into an
HTTP 503, never a crash.
"""
from __future__ import annotations

import logging
from typing import Optional

from src.log_privacy import user_ref

logger = logging.getLogger(__name__)


def get_avatar(user_id: str) -> Optional[dict]:
    """Return {data_url, content_type, updated_at} or None."""
    from src.db import get_db_connection

    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT data_url, content_type, updated_at FROM user_avatars WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {"data_url": row[0], "content_type": row[1], "updated_at": row[2]}
    except Exception as exc:  # pre-migration table absence stays non-fatal
        logger.warning("avatar_repo.get_avatar failed for %s: %s", user_ref(user_id), exc)
        return None
    finally:
        conn.close()


def set_avatar(user_id: str, data_url: str, content_type: str, byte_size: int) -> None:
    """Upsert the user's avatar. Raises RuntimeError when storage is unavailable."""
    from src.db import get_db_connection

    conn = get_db_connection()
    if not conn:
        raise RuntimeError("DB unavailable — cannot store avatar")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_avatars (user_id, data_url, content_type, byte_size, updated_at)
                VALUES (%s, %s, %s, %s, now())
                ON CONFLICT (user_id) DO UPDATE SET
                    data_url = EXCLUDED.data_url,
                    content_type = EXCLUDED.content_type,
                    byte_size = EXCLUDED.byte_size,
                    updated_at = now()
                """,
                (user_id, data_url, content_type, byte_size),
            )
        conn.commit()
    except Exception as exc:
        logger.warning("avatar_repo.set_avatar failed for %s: %s", user_ref(user_id), exc)
        raise RuntimeError("avatar storage unavailable") from exc
    finally:
        conn.close()


def delete_avatar(user_id: str) -> bool:
    """Remove the user's avatar; True when a row was deleted."""
    from src.db import get_db_connection

    conn = get_db_connection()
    if not conn:
        raise RuntimeError("DB unavailable — cannot delete avatar")
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM user_avatars WHERE user_id = %s", (user_id,))
            deleted = cur.rowcount > 0
        conn.commit()
        return deleted
    except Exception as exc:
        logger.warning("avatar_repo.delete_avatar failed for %s: %s", user_ref(user_id), exc)
        raise RuntimeError("avatar storage unavailable") from exc
    finally:
        conn.close()
