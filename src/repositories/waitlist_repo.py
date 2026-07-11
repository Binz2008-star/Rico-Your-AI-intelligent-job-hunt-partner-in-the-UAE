"""Neon-backed waitlist persistence.

The repository keeps one durable row per normalized email. Repeated submissions
refresh optional profile/attribution fields without creating duplicates.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

logger = logging.getLogger(__name__)


class WaitlistUnavailable(RuntimeError):
    """Raised when waitlist persistence is unavailable."""


@dataclass(frozen=True)
class WaitlistEntry:
    id: int
    email: str
    email_normalized: str
    status: str
    created_at: datetime
    updated_at: datetime


def upsert_waitlist_entry(
    *,
    email: str,
    first_name: str | None,
    target_role: str | None,
    location: str | None,
    consent: bool,
    source: Mapping[str, Any],
) -> tuple[WaitlistEntry, bool]:
    from psycopg2.extras import Json
    from src.db import get_db_connection, is_db_available

    if not consent:
        raise ValueError("consent is required")

    if not is_db_available():
        raise WaitlistUnavailable("database unavailable")

    conn = get_db_connection()
    if not conn:
        raise WaitlistUnavailable("database unavailable")

    normalised = email.strip().lower()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO waitlist_entries (
                    email,
                    email_normalized,
                    first_name,
                    target_role,
                    location,
                    consent,
                    source
                )
                VALUES (%s, %s, %s, %s, %s, TRUE, %s)
                ON CONFLICT (email_normalized) DO UPDATE
                SET email = EXCLUDED.email,
                    first_name = COALESCE(EXCLUDED.first_name, waitlist_entries.first_name),
                    target_role = COALESCE(EXCLUDED.target_role, waitlist_entries.target_role),
                    location = COALESCE(EXCLUDED.location, waitlist_entries.location),
                    consent = TRUE,
                    source = CASE
                        WHEN EXCLUDED.source = '{}'::jsonb THEN waitlist_entries.source
                        ELSE waitlist_entries.source || EXCLUDED.source
                    END,
                    updated_at = NOW()
                RETURNING id, email, email_normalized, status, created_at, updated_at,
                          (xmax = 0) AS inserted
                """,
                (
                    email.strip(),
                    normalised,
                    first_name,
                    target_role,
                    location,
                    Json(dict(source)),
                ),
            )
            row = cur.fetchone()
        conn.commit()
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.exception("waitlist_upsert_failed")
        raise WaitlistUnavailable("waitlist persistence unavailable") from exc
    finally:
        conn.close()

    return (
        WaitlistEntry(
            id=row[0],
            email=row[1],
            email_normalized=row[2],
            status=row[3],
            created_at=row[4],
            updated_at=row[5],
        ),
        bool(row[6]),
    )
