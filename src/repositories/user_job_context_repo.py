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

# Maps a runtime/chat action verb to the coarse `status` column value.
_ACTION_STATUS_MAP = {
    "apply": "applied",
    "mark_applied": "applied",
    "save": "saved",
    "track": "saved",
    "skip": "skipped",
    "not_relevant": "skipped",
    "block": "blocked",
    "draft": "discussed",
    "why": "discussed",
    "remind": "discussed",
    "discussed": "discussed",
}


def _status_for_action(action: str) -> str:
    return _ACTION_STATUS_MAP.get((action or "").strip().lower(), "discussed")


def upsert_matches(user_id: str, matches: list[dict]) -> None:
    """
    Write formatted job-search matches to user_job_context.

    Uses INSERT … ON CONFLICT DO UPDATE so re-running the same search
    refreshes searched_at without creating duplicate rows.

    Never raises — failures are logged and swallowed so the chat response
    is not affected by a transient DB error.
    """
    if not user_id or not matches:
        return
    from src.db import get_db_connection

    conn = get_db_connection()
    if not conn:
        logger.debug("user_job_context_repo: DB unavailable, skipping upsert user=%s", user_id)
        return
    try:
        with conn.cursor() as cur:
            for m in matches:
                t = (m.get("title") or "").strip()
                c = (m.get("company") or "").strip()
                if not t or not c:
                    continue  # cannot uniquely identify; skip rather than clobber
                au = (m.get("apply_url") or "").strip()
                su = (m.get("source_url") or "").strip()
                # When _format_match promotes a source listing URL (job_google_link)
                # into apply_url with no actual direct apply link, both fields end up
                # identical. Store it as source_url only so the DB lookup returns the
                # correct source-URL fallback instead of a Google link as apply_url.
                if au and su and au == su:
                    au = ""
                alt = (m.get("alt_link") or m.get("alt_url") or "").strip()
                vs = m.get("verification_status") or "lead_needs_verification"
                cur.execute(
                    """
                    INSERT INTO user_job_context
                        (user_id, title, company, location, apply_url, source_url,
                         alt_url, verification_status, searched_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (user_id, lower(title), lower(company))
                    DO UPDATE SET
                        apply_url           = CASE
                                                WHEN EXCLUDED.apply_url <> ''
                                                THEN EXCLUDED.apply_url
                                                ELSE user_job_context.apply_url
                                              END,
                        source_url          = COALESCE(
                                                NULLIF(EXCLUDED.source_url, ''),
                                                user_job_context.source_url
                                              ),
                        alt_url             = COALESCE(
                                                NULLIF(EXCLUDED.alt_url, ''),
                                                user_job_context.alt_url
                                              ),
                        verification_status = EXCLUDED.verification_status,
                        searched_at         = NOW()
                    """,
                    (
                        user_id,
                        t,
                        c,
                        (m.get("location") or "").strip() or None,
                        au,
                        su,
                        alt,
                        vs,
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

    Comparison is case-insensitive. Exact normalized title/company matches are
    preferred; substring fallback is limited to multi-word titles so a generic
    title like "Manager" does not match "General Manager".

    Returns None when no row is found or the DB is unavailable.
    Never raises.
    """
    from src.db import get_db_connection

    conn = get_db_connection()
    if not conn:
        return None
    cutoff = datetime.now(_UTC) - timedelta(days=max_age_days)
    try:
        normalized_title = (title or "").strip()
        normalized_company = (company or "").strip()
        if not user_id or not normalized_title or not normalized_company:
            return None

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT title, company, location, apply_url, source_url,
                       alt_url, verification_status, searched_at
                  FROM user_job_context
                 WHERE user_id = %s
                   AND lower(title) = lower(%s)
                   AND lower(company) = lower(%s)
                   AND searched_at >= %s
                 ORDER BY searched_at DESC
                 LIMIT 1
                """,
                (user_id, normalized_title, normalized_company, cutoff),
            )
            row = cur.fetchone()
            if not row and len(normalized_title.split()) >= 2:
                cur.execute(
                    """
                    SELECT title, company, location, apply_url, source_url,
                           verification_status, searched_at
                      FROM user_job_context
                     WHERE user_id = %s
                       AND lower(title) LIKE lower(%s)
                       AND lower(company) LIKE lower(%s)
                       AND searched_at >= %s
                     ORDER BY searched_at DESC
                     LIMIT 1
                    """,
                    (user_id, f"%{normalized_title}%", f"%{normalized_company}%", cutoff),
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
            "alt_url":             row[5] or "",
            "verification_status": row[6] or "lead_needs_verification",
            "searched_at":         row[7],
        }
    except Exception:
        logger.exception("user_job_context_repo_find_failed user=%s", user_id)
        return None
    finally:
        conn.close()


def record_interaction(
    user_id: str,
    title: str,
    company: str,
    action: str,
    note: Optional[str] = None,
) -> None:
    """
    Persist that a user interacted with a specific job (took an action or
    meaningfully discussed it). Upserts on (user_id, lower(title), lower(company))
    so a job mentioned before any search match still gets a row.

    Updates last_action, last_action_at, last_discussed_at, interaction_count,
    status (and user_note when provided). Never raises.
    """
    t = (title or "").strip()
    c = (company or "").strip()
    if not user_id or not t or not c:
        return
    from src.db import get_db_connection

    conn = get_db_connection()
    if not conn:
        logger.debug("user_job_context_repo: DB unavailable, skipping interaction user=%s", user_id)
        return
    status = _status_for_action(action)
    act = (action or "discussed").strip().lower()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_job_context
                    (user_id, title, company, last_action, last_action_at,
                     last_discussed_at, user_note, interaction_count, status, searched_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW(), %s, 1, %s, NOW())
                ON CONFLICT (user_id, lower(title), lower(company))
                DO UPDATE SET
                    last_action       = EXCLUDED.last_action,
                    last_action_at    = NOW(),
                    last_discussed_at = NOW(),
                    user_note         = COALESCE(EXCLUDED.user_note, user_job_context.user_note),
                    interaction_count = user_job_context.interaction_count + 1,
                    status            = EXCLUDED.status
                """,
                (user_id, t, c, act, (note or None), status),
            )
        conn.commit()
        logger.debug("user_job_context_repo: recorded %s on %s @ %s user=%s", act, t, c, user_id)
    except Exception:
        logger.exception("user_job_context_repo_record_failed user=%s", user_id)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def _recent_rows(user_id: str, order_col: str, limit: int, max_age_days: int) -> list[dict]:
    """Shared reader for recently-interacted / recently-discussed queries."""
    if not user_id:
        return []
    from src.db import get_db_connection

    conn = get_db_connection()
    if not conn:
        return []
    cutoff = datetime.now(_UTC) - timedelta(days=max_age_days)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT title, company, location, last_action, last_action_at,
                       last_discussed_at, status, apply_url, source_url
                  FROM user_job_context
                 WHERE user_id = %s
                   AND {order_col} IS NOT NULL
                   AND {order_col} >= %s
                 ORDER BY {order_col} DESC
                 LIMIT %s
                """,
                (user_id, cutoff, limit),
            )
            rows = cur.fetchall() or []
        return [
            {
                "title":             r[0],
                "company":           r[1],
                "location":          r[2],
                "last_action":       r[3],
                "last_action_at":    r[4],
                "last_discussed_at": r[5],
                "status":            r[6],
                "apply_url":         r[7] or "",
                "source_url":        r[8] or "",
            }
            for r in rows
        ]
    except Exception:
        logger.exception("user_job_context_repo_recent_failed user=%s", user_id)
        return []
    finally:
        conn.close()


def get_recently_interacted(user_id: str, limit: int = 5, max_age_days: int = 30) -> list[dict]:
    """Jobs the user took an action on, most recent first."""
    return _recent_rows(user_id, "last_action_at", limit, max_age_days)


def get_recently_discussed(user_id: str, limit: int = 3, max_age_days: int = 14) -> list[dict]:
    """Jobs the user discussed in chat, most recent first."""
    return _recent_rows(user_id, "last_discussed_at", limit, max_age_days)
