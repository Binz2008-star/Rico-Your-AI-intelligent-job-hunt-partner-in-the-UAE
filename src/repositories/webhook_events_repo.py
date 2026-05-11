"""src/repositories/webhook_events_repo.py

Idempotency guard for inbound webhooks.

A processed submission is recorded in ``rico_webhook_events`` keyed by
``(source, event_id)``.  Before processing any submission the handler
calls ``is_processed()``; after a successful write it calls
``mark_processed()``.  Both are safe to call when the DB is unavailable
— ``is_processed`` returns False (allow through) and ``mark_processed``
logs a warning and returns without raising.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS rico_webhook_events (
    id          BIGSERIAL   PRIMARY KEY,
    source      TEXT        NOT NULL,
    event_id    TEXT        NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT rico_webhook_events_source_event_uq UNIQUE (source, event_id)
)
"""


def _get_conn():
    from src.db import get_db_connection, is_db_available
    if not is_db_available():
        return None
    return get_db_connection()


def _ensure_table(conn) -> None:
    try:
        with conn.cursor() as cur:
            cur.execute(_CREATE_TABLE_SQL)
        conn.commit()
    except Exception:
        logger.exception("webhook_events_repo: failed to ensure table")
        try:
            conn.rollback()
        except Exception:
            pass


def is_processed(source: str, event_id: str) -> bool:
    """Return True if this (source, event_id) pair has already been processed.

    Returns False on DB unavailability so the webhook is allowed through —
    the idempotency guarantee degrades gracefully rather than blocking all
    submissions when the DB is down.
    """
    conn = _get_conn()
    if not conn:
        logger.warning(
            "webhook_events_repo: DB unavailable — skipping duplicate check source=%s event_id=%s",
            source, event_id,
        )
        return False
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM rico_webhook_events WHERE source = %s AND event_id = %s LIMIT 1",
                (source, event_id),
            )
            return cur.fetchone() is not None
    except Exception:
        logger.exception(
            "webhook_events_repo: is_processed failed source=%s event_id=%s", source, event_id
        )
        return False
    finally:
        conn.close()


def mark_processed(source: str, event_id: str) -> None:
    """Record (source, event_id) as processed.

    Uses INSERT … ON CONFLICT DO NOTHING so concurrent duplicate calls are safe.
    Logs a warning and returns without raising when the DB is unavailable.
    """
    conn = _get_conn()
    if not conn:
        logger.warning(
            "webhook_events_repo: DB unavailable — cannot mark processed source=%s event_id=%s",
            source, event_id,
        )
        return
    try:
        _ensure_table(conn)
        now = datetime.now(timezone.utc)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rico_webhook_events (source, event_id, processed_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (source, event_id) DO NOTHING
                """,
                (source, event_id, now),
            )
        conn.commit()
        logger.debug(
            "webhook_events_repo: marked processed source=%s event_id=%s", source, event_id
        )
    except Exception:
        logger.exception(
            "webhook_events_repo: mark_processed failed source=%s event_id=%s", source, event_id
        )
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()
