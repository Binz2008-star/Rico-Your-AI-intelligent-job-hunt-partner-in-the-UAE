"""
src/repositories/career_memory_repo.py
Career Memory Engine persistence (ADR-001 M1).

Owns all SQL against career_memory_events / career_memory_facts (migration
042). Policy — feature flag, kill switch, provenance validation, trust
hierarchy, exclusion filter, canonical-ID resolution, metrics — lives in
src/services/memory_writer.py; this module only stores and retrieves.

Every statement filters by account_id (the canonical immutable rico_users.id
UUID). There is intentionally no cross-account query in this module.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.db import get_db_connection

logger = logging.getLogger(__name__)


class CareerMemoryRepoError(RuntimeError):
    """Raised when a memory write cannot reach or complete in the database."""


def insert_event(
    *,
    account_id: str,
    event_type: str,
    idempotency_key: str,
    occurred_at: datetime,
    actor: str,
    source: str,
    confidence: float,
    payload: Dict[str, Any],
    source_record_id: Optional[str] = None,
    source_uri: Optional[str] = None,
    retention_class: str = "episode",
    version: int = 1,
) -> str:
    """Append one episode. Returns 'written' or 'duplicate' (idempotency hit)."""
    conn = get_db_connection()
    if not conn:
        raise CareerMemoryRepoError("no database connection")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO career_memory_events (
                    account_id, event_type, version, retention_class,
                    idempotency_key, occurred_at, actor, source,
                    source_record_id, source_uri, confidence, payload
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT ON CONSTRAINT uq_career_memory_events_idem DO NOTHING
                RETURNING id
                """,
                (
                    account_id, event_type, version, retention_class,
                    idempotency_key, occurred_at, actor, source,
                    source_record_id, source_uri, confidence, json.dumps(payload),
                ),
            )
            inserted = cur.fetchone() is not None
        conn.commit()
        return "written" if inserted else "duplicate"
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        raise CareerMemoryRepoError(str(exc)) from exc
    finally:
        conn.close()


def insert_fact(
    *,
    account_id: str,
    fact_key: str,
    fact_class: str,
    value: Any,
    idempotency_key: str,
    occurred_at: datetime,
    actor: str,
    source: str,
    confidence: float,
    source_record_id: Optional[str] = None,
    source_uri: Optional[str] = None,
    retention_class: str = "core_fact",
    version: int = 1,
    effective_from: Optional[datetime] = None,
    effective_to: Optional[datetime] = None,
) -> str:
    """Write one fact with history semantics. Returns 'written' or 'duplicate'.

    replaceable / verified_only: the current row (effective_to IS NULL) for
    (account_id, fact_key), if any, is closed in the same transaction — its
    effective_to is set and superseded_by points at the new row. The old value
    is never overwritten in place (ADR §4/§7).

    set_valued: a new member value simply joins the set (its own current row);
    an existing identical current member makes the write idempotent at the
    member level. Removal is explicit via close_set_member(), never implied.

    time_bound: rows carry caller-provided effective_from/effective_to and
    multiple windows may coexist; overlap policy is enforced by the writer.
    """
    conn = get_db_connection()
    if not conn:
        raise CareerMemoryRepoError("no database connection")
    try:
        with conn.cursor() as cur:
            # Idempotency pre-check keeps the supersede logic from closing the
            # current row twice when the same logical write is retried.
            cur.execute(
                """
                SELECT 1 FROM career_memory_facts
                WHERE account_id = %s AND idempotency_key = %s
                """,
                (account_id, idempotency_key),
            )
            if cur.fetchone() is not None:
                conn.rollback()
                return "duplicate"

            prior_id: Optional[int] = None
            if fact_class in ("replaceable", "verified_only"):
                cur.execute(
                    """
                    SELECT id FROM career_memory_facts
                    WHERE account_id = %s AND fact_key = %s AND effective_to IS NULL
                    FOR UPDATE
                    """,
                    (account_id, fact_key),
                )
                row = cur.fetchone()
                prior_id = row[0] if row else None
                if prior_id is not None:
                    # Close the current row BEFORE inserting its successor —
                    # the partial unique index allows only one current row per
                    # (account, fact_key), so the order matters. superseded_by
                    # is linked after the insert returns the new id; a
                    # duplicate-key rollback below undoes this close too.
                    cur.execute(
                        """
                        UPDATE career_memory_facts
                        SET effective_to = NOW()
                        WHERE id = %s AND account_id = %s
                        """,
                        (prior_id, account_id),
                    )

            cur.execute(
                """
                INSERT INTO career_memory_facts (
                    account_id, fact_key, fact_class, version, retention_class,
                    value, source, source_record_id, source_uri, confidence,
                    actor, occurred_at, effective_from, effective_to, idempotency_key
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                          COALESCE(%s, NOW()), %s, %s)
                ON CONFLICT ON CONSTRAINT uq_career_memory_facts_idem DO NOTHING
                RETURNING id
                """,
                (
                    account_id, fact_key, fact_class, version, retention_class,
                    json.dumps(value), source, source_record_id, source_uri, confidence,
                    actor, occurred_at, effective_from, effective_to, idempotency_key,
                ),
            )
            new_row = cur.fetchone()
            if new_row is None:
                conn.rollback()
                return "duplicate"

            if prior_id is not None:
                cur.execute(
                    """
                    UPDATE career_memory_facts
                    SET superseded_by = %s
                    WHERE id = %s AND account_id = %s
                    """,
                    (new_row[0], prior_id, account_id),
                )
        conn.commit()
        return "written"
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        raise CareerMemoryRepoError(str(exc)) from exc
    finally:
        conn.close()


def get_current_fact(*, account_id: str, fact_key: str) -> Optional[Dict[str, Any]]:
    """Return the current row for a replaceable/verified_only fact, else None."""
    conn = get_db_connection()
    if not conn:
        raise CareerMemoryRepoError("no database connection")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, value, source, confidence, effective_from
                FROM career_memory_facts
                WHERE account_id = %s AND fact_key = %s AND effective_to IS NULL
                      AND fact_class IN ('replaceable', 'verified_only')
                LIMIT 1
                """,
                (account_id, fact_key),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "value": row[1],
            "source": row[2],
            "confidence": row[3],
            "effective_from": row[4],
        }
    except CareerMemoryRepoError:
        raise
    except Exception as exc:
        raise CareerMemoryRepoError(str(exc)) from exc
    finally:
        conn.close()


def get_current_set_members(*, account_id: str, fact_key: str) -> List[Dict[str, Any]]:
    """Return current member rows of a set_valued fact."""
    conn = get_db_connection()
    if not conn:
        raise CareerMemoryRepoError("no database connection")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, value, source, confidence
                FROM career_memory_facts
                WHERE account_id = %s AND fact_key = %s AND effective_to IS NULL
                      AND fact_class = 'set_valued'
                ORDER BY effective_from ASC
                """,
                (account_id, fact_key),
            )
            rows = cur.fetchall()
        return [
            {"id": r[0], "value": r[1], "source": r[2], "confidence": r[3]}
            for r in rows
        ]
    except Exception as exc:
        raise CareerMemoryRepoError(str(exc)) from exc
    finally:
        conn.close()


def close_set_member(*, account_id: str, fact_key: str, value: Any) -> bool:
    """Explicitly remove a set member (ADR §7: removal is never implied).

    Closes the matching current row (effective_to = NOW()). Returns True when
    a row was closed.
    """
    conn = get_db_connection()
    if not conn:
        raise CareerMemoryRepoError("no database connection")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE career_memory_facts
                SET effective_to = NOW()
                WHERE account_id = %s AND fact_key = %s AND effective_to IS NULL
                      AND fact_class = 'set_valued' AND md5(value::text) = md5(%s::text)
                """,
                (account_id, fact_key, json.dumps(value)),
            )
            closed = cur.rowcount > 0
        conn.commit()
        return closed
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        raise CareerMemoryRepoError(str(exc)) from exc
    finally:
        conn.close()


def count_events(*, account_id: str, event_type_prefix: Optional[str] = None) -> int:
    """Count one account's episodes — used by drift reconciliation and tests."""
    conn = get_db_connection()
    if not conn:
        raise CareerMemoryRepoError("no database connection")
    try:
        with conn.cursor() as cur:
            if event_type_prefix:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM career_memory_events
                    WHERE account_id = %s AND event_type LIKE %s
                    """,
                    (account_id, event_type_prefix + "%"),
                )
            else:
                cur.execute(
                    "SELECT COUNT(*) FROM career_memory_events WHERE account_id = %s",
                    (account_id,),
                )
            return int(cur.fetchone()[0])
    except Exception as exc:
        raise CareerMemoryRepoError(str(exc)) from exc
    finally:
        conn.close()
