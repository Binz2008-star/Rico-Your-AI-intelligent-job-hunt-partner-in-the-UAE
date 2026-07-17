"""
src/repositories/settings_repo.py
DB I/O for the settings table. Callers receive plain dicts — no SQL here above this layer.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from src.db import get_db_connection

logger = logging.getLogger(__name__)

def read(user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Load settings row from Postgres.
    When ``user_id`` is provided, returns that user's row; otherwise falls back
    to the legacy "default" row for the single-user pipeline.
    Returns None if the row doesn't exist or DB is unavailable.
    """
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT include_keywords, exclude_keywords, min_score,
                          max_daily_applies, telegram_chat_id,
                          score_threshold_apply, score_threshold_watch,
                          COALESCE(blocked_companies, '{}') AS blocked_companies
                   FROM settings WHERE user_id = %s""",
                (user_id or "default",),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {
            "include_keywords": list(row[0] or []),
            "exclude_keywords": list(row[1] or []),
            "min_score": row[2],
            "max_daily_applies": row[3],
            "telegram_chat_id": row[4] or "",
            "score_threshold_apply": row[5] if row[5] is not None else 75,
            "score_threshold_watch": row[6] if row[6] is not None else 50,
            "blocked_companies": list(row[7] or []),
        }
    except Exception:
        logger.exception("settings_repo_read_failed")
        return None
    finally:
        conn.close()


def upsert(data: Dict[str, Any], user_id: Optional[str] = None, *, require_db: bool = False) -> None:
    """Insert or update the settings row for the given user.

    Only columns present in *data* are written; absent keys are left as-is.
    Array columns use explicit TEXT[] casts to avoid psycopg2 empty-list
    type-inference failures.

    ``require_db`` (default ``False`` — preserves existing callers' best-effort
    behavior) makes the write MANDATORY: DB unavailability or a write failure
    raises RuntimeError instead of being swallowed, so user-directed settings
    mutations can return a retryable non-2xx instead of a false success (#764).
    """
    conn = get_db_connection()
    if not conn:
        if require_db:
            raise RuntimeError(f"settings DB unavailable (require_db) user_id={user_id}")
        return

    # Map Python key → (SQL column, SQL cast expression)
    _ARRAY_COLS = {"include_keywords", "exclude_keywords", "blocked_companies"}
    _INT_COLS   = {"min_score", "max_daily_applies", "score_threshold_apply", "score_threshold_watch"}
    _TEXT_COLS  = {"telegram_chat_id"}
    _ALL_COLS   = _ARRAY_COLS | _INT_COLS | _TEXT_COLS

    # Build lists of (column, sql_fragment, value) for fields present in data
    fields: list = []
    for key in _ALL_COLS:
        if key not in data:
            continue
        val = data[key]
        if key in _ARRAY_COLS:
            # Convert Python list → PostgreSQL text[] literal so psycopg2
            # never has to infer the element type of an empty list.
            if val is None:
                pg_val = None
                cast = "%s::TEXT[]"
            else:
                pg_val = "{" + ",".join(
                    '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'
                    for v in val
                ) + "}"
                cast = "%s::TEXT[]"
        else:
            pg_val = val
            cast = "%s"
        fields.append((key, cast, pg_val))

    if not fields:
        return

    col_names = ", ".join(f[0] for f in fields)
    col_casts = ", ".join(f[1] for f in fields)
    col_vals  = [f[2] for f in fields]

    update_set = ", ".join(
        f"{f[0]} = EXCLUDED.{f[0]}" for f in fields
    )

    sql = f"""
        INSERT INTO settings (user_id, {col_names}, updated_at)
        VALUES (%s, {col_casts}, NOW())
        ON CONFLICT (user_id) DO UPDATE SET
            {update_set},
            updated_at = NOW()
    """

    try:
        with conn.cursor() as cur:
            cur.execute(sql, [user_id or "default"] + col_vals)
        conn.commit()
    except Exception as exc:
        logger.exception("settings_repo_upsert_failed user_id=%s data_keys=%s", user_id, list(data.keys()))
        rollback = getattr(conn, "rollback", None)
        if callable(rollback):
            try:
                rollback()
            except Exception:
                logger.exception("settings_repo_rollback_failed")
        if require_db:
            raise RuntimeError(f"settings write failed (require_db) user_id={user_id}") from exc
    finally:
        conn.close()
