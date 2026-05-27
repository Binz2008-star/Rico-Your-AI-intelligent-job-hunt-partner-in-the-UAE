"""
src/repositories/user_job_context_repo.py
Neon-backed persistence for Rico job-search matches.

Stores the top matches from each JSearch run so apply/source links survive
across chat turns, Render restarts, and RICO_MEMORY_BACKEND=postgres mode.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)
_UTC = timezone.utc
_MATCH_TTL_DAYS = 7


def upsert_matches(user_id: str, matches: list[dict]) -> None:
    """
    Write formatted job-search matches to user_job_context.

    Uses INSERT … ON CONFLICT DO UPDATE so re-running the same search
    refreshes searched_at without creating duplicate rows.

    Never raises — failures are logged and swallowed so the chat response
    is not affected by a transient DB error.
    """
    if not matches:
        return
    from src.db import get_db_connection

    conn = get_db_connection()
    if not conn:
        logger.debug("user_job_context_repo: DB unavailable, skipping upsert user=%s", user_id)
        return
    try:
        with conn.cursor() as cur:
            for m in matches:
                cur.execute(
                    """
                    INSERT INTO user_job_context
                        (user_id, title, company, location, apply_url, source_url,
                         verification_status, searched_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (user_id, lower(title), lower(company))
                    DO UPDATE SET
                        apply_url           = EXCLUDED.apply_url,
                        source_url          = EXCLUDED.source_url,
                        verification_status = EXCLUDED.verification_status,
                        searched_at         = NOW()
                    """,
                    (
                        user_id,
                        (m.get("title") or "").strip(),
                        (m.get("company") or "").strip(),
                        (m.get("location") or "").strip() or None,
                        (m.get("apply_url") or "").strip(),
                        (m.get("source_url") or "").strip(),
                        m.get("verification_status") or "lead_needs_verification",
                    ),
                )
        conn.commit()
        logger.debug("user_job_context_repo: upserted %d matches user=%s", len(matches), user_id)
    except Exception:
        logger.exception("user_job_context_repo_upsert_failed user=%s", user_id)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def find_by_title_company(
    user_id: str,
    title: str,
    company: str,
    max_age_days: int = _MATCH_TTL_DAYS,
) -> Optional[dict]:
    """
    Return the most recent match for (user_id, title, company) within max_age_days.

    Comparison is case-insensitive and uses substring matching so "Acme Corp" in
    the DB matches "Acme" from the intent extractor.

    Returns None when no row is found or the DB is unavailable.
    Never raises.
    """
    from src.db import get_db_connection

    conn = get_db_connection()
    if not conn:
        return None
    cutoff = datetime.now(_UTC) - timedelta(days=max_age_days)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT title, company, location, apply_url, source_url,
                       verification_status, searched_at
                  FROM user_job_context
                 WHERE user_id = %s
                   AND lower(title)   LIKE lower(%s)
                   AND lower(company) LIKE lower(%s)
                   AND searched_at >= %s
                 ORDER BY searched_at DESC
                 LIMIT 1
                """,
                (user_id, f"%{title}%", f"%{company}%", cutoff),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {
            "title":               row[0],
            "company":             row[1],
            "location":            row[2],
            "apply_url":           row[3] or "",
            "source_url":          row[4] or "",
            "verification_status": row[5] or "lead_needs_verification",
            "searched_at":         row[6],
        }
    except Exception:
        logger.exception("user_job_context_repo_find_failed user=%s", user_id)
        return None
    finally:
        conn.close()
