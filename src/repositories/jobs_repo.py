"""
src/repositories/jobs_repo.py
All data access for the jobs table.
Services call these functions — never reach into the DB directly.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from psycopg2 import sql

from src.db import get_db_connection

logger = logging.getLogger(__name__)


def list_from_db(
    offset: int,
    limit: int,
    min_score: int,
    source: Optional[str],
) -> Optional[Dict[str, Any]]:
    """
    Paginated job query from Postgres.
    jobs table is global feed (no user_id), filtering happens at service/application layer.
    Returns None on any DB error so callers can fall back to JSON.
    """
    conn = get_db_connection()
    if not conn:
        return None
    try:
        filters = ["score >= %s", "date_found >= now() - interval '14 days'"]
        params: list = [min_score]

        # Allow-list for source parameter to prevent SQL injection
        _ALLOWED_SOURCES = {"indeed", "linkedin", "naukrigulf", "reed", "bayt", "monster"}
        if source:
            if source.lower() not in _ALLOWED_SOURCES:
                logger.warning("jobs_repo_invalid_source source=%s", source)
                return None
            filters.append("source = %s")
            params.append(source)

        where_clause = sql.SQL(" AND ").join(sql.SQL(f) for f in filters)

        with conn.cursor() as cur:
            cur.execute(
                sql.SQL("SELECT COUNT(*) FROM jobs WHERE ") + where_clause,
                params,
            )
            total = cur.fetchone()[0]

            query = (
                sql.SQL(
                    "SELECT id, title, company, location, link, score,"
                    " match_reason, source, date_found, seen, link_status, link_verified_at"
                    " FROM jobs WHERE "
                )
                + where_clause
                + sql.SQL(" ORDER BY score DESC, date_found DESC LIMIT %s OFFSET %s")
            )
            cur.execute(query, params + [limit, offset])
            rows = cur.fetchall()

        jobs = [_row_to_job(r) for r in rows]
        return {
            "jobs": jobs,
            "total": total,
            "page": offset // limit + 1,
            "limit": limit,
            "pages": max(1, -(-total // limit)),
        }
    except Exception:
        logger.exception("jobs_repo_list_failed")
        return None
    finally:
        conn.close()


def get_by_db_id(db_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single job by its integer primary key. jobs table is global feed."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, title, company, location, link, score,
                          match_reason, source, date_found, seen, link_status, link_verified_at
                   FROM jobs WHERE id = %s""",
                (db_id,),
            )
            row = cur.fetchone()
        return _row_to_job(row) if row else None
    except Exception:
        logger.exception("jobs_repo_get_failed id=%s", db_id)
        return None
    finally:
        conn.close()


def get_pipeline_stats() -> Dict[str, Any]:
    """
    Aggregate stats for the jobs feed: total available, avg score, new today.
    Returns zeros on any DB error.
    """
    conn = get_db_connection()
    if not conn:
        return {"jobs_total": 0, "avg_score": 0, "new_today": 0}
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) AS jobs_total,
                    ROUND(AVG(score))::int AS avg_score,
                    COUNT(*) FILTER (WHERE date_found >= NOW() - INTERVAL '24 hours') AS new_today
                FROM jobs
                WHERE score >= 0
                  AND date_found >= NOW() - INTERVAL '14 days'
                """
            )
            row = cur.fetchone()
        if not row:
            return {"jobs_total": 0, "avg_score": 0, "new_today": 0}
        return {
            "jobs_total": int(row[0] or 0),
            "avg_score": int(row[1] or 0),
            "new_today": int(row[2] or 0),
        }
    except Exception:
        logger.exception("jobs_repo_pipeline_stats_failed")
        return {"jobs_total": 0, "avg_score": 0, "new_today": 0}
    finally:
        conn.close()


def _row_to_job(row: tuple) -> Dict[str, Any]:
    return {
        "id": str(row[0]),
        "title": row[1] or "",
        "company": row[2] or "",
        "location": row[3] or "",
        "link": row[4] or "",
        "score": row[5] or 0,
        "match_reason": row[6] or "",
        "source": row[7] or "",
        "date_found": row[8].isoformat() if row[8] else None,
        "seen": bool(row[9]),
        "link_status": row[10] if len(row) > 10 else "needs_review",
        "link_verified_at": row[11].isoformat() if len(row) > 11 and row[11] else None,
    }
