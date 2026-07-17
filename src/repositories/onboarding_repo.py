"""src/repositories/onboarding_repo.py
Persist and retrieve Rico onboarding state from the DB.
Falls back gracefully when the DB is unavailable — callers handle None.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from src.models.onboarding import (
    ONBOARDING_COMPLETED,
    ONBOARDING_IN_PROGRESS,
    ONBOARDING_PENDING,
    OnboardingState,
)

logger = logging.getLogger(__name__)


class OnboardingStateUnavailable(RuntimeError):
    """The onboarding-state store could not be read (DB down / query error).

    Distinct from a legitimately-absent row (returned as ``None``): callers of
    the strict reader use this to avoid misclassifying an infrastructure failure
    as "no persisted onboarding row".
    """


_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS rico_onboarding_states (
    user_id      TEXT        PRIMARY KEY,
    status       TEXT        NOT NULL DEFAULT 'pending'
                                 CHECK (status IN ('pending', 'in_progress', 'completed')),
    completed_at TIMESTAMPTZ,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""


def _get_conn():
    from src.db import get_db_connection, is_db_available
    if not is_db_available():
        return None
    return get_db_connection()


def _ensure_table(conn) -> None:
    """Create table on first use — idempotent."""
    try:
        with conn.cursor() as cur:
            cur.execute(_CREATE_TABLE_SQL)
        conn.commit()
    except Exception:
        logger.exception("onboarding_repo: failed to ensure table")
        try:
            conn.rollback()
        except Exception:
            pass


def get_onboarding_state(user_id: str) -> Optional[OnboardingState]:
    """Return the persisted OnboardingState, or None if DB unavailable / row absent."""
    conn = _get_conn()
    if not conn:
        return None
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, completed_at, updated_at FROM rico_onboarding_states WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return OnboardingState(
            user_id=user_id,
            status=row[0],
            completed_at=row[1],
            updated_at=row[2],
        )
    except Exception:
        logger.exception("onboarding_repo: get_failed user_id=%s", user_id)
        return None
    finally:
        conn.close()


def get_onboarding_state_readonly(user_id: str) -> Optional[OnboardingState]:
    """Strict read-only reader for the onboarding status endpoint.

    Unlike :func:`get_onboarding_state`, this NEVER creates the table, never
    writes, and never commits — a GET must be truly read-only. It also
    distinguishes a legitimate absence from an infrastructure failure:

    * DB unavailable / no connection      → raise ``OnboardingStateUnavailable``
    * SELECT / query failure              → raise ``OnboardingStateUnavailable``
    * table absent (legacy environment)   → return ``None`` (does NOT create it)
    * table present but no row for user   → return ``None``
    * row present                         → return :class:`OnboardingState`

    The connection is always closed. Callers translate the raised error into a
    sanitized ``503`` rather than falling through to a "derived" answer.
    """
    from src.db import get_db_connection, is_db_available

    if not is_db_available():
        raise OnboardingStateUnavailable("database unavailable")

    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            raise OnboardingStateUnavailable("no database connection")

        with conn.cursor() as cur:
            # Read-only existence check — never creates the table (to_regclass
            # returns NULL when the relation is absent). Legacy environments
            # without the table read as "no row", not an error.
            cur.execute("SELECT to_regclass('public.rico_onboarding_states')")
            reg = cur.fetchone()
            if reg is None or reg[0] is None:
                return None

            cur.execute(
                "SELECT status, completed_at, updated_at "
                "FROM rico_onboarding_states WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()

        if row is None:
            return None
        return OnboardingState(
            user_id=user_id,
            status=row[0],
            completed_at=row[1],
            updated_at=row[2],
        )
    except OnboardingStateUnavailable:
        raise
    except Exception as exc:  # DB/driver/query error — never a silent None.
        logger.exception("onboarding_repo: readonly_get_failed user_id=%s", user_id)
        raise OnboardingStateUnavailable("onboarding state read failed") from exc
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def set_onboarding_status(user_id: str, status: str, *, require_db: bool = False) -> None:
    """Upsert the onboarding status for a user.

    ``require_db`` (default ``False`` — preserves existing callers' best-effort
    behavior) makes the write MANDATORY: DB unavailability or a write failure
    raises ``OnboardingStateUnavailable`` instead of being swallowed, so the
    caller can return a retryable non-2xx rather than claiming a completion
    state that was never persisted (#764).
    """
    conn = _get_conn()
    if not conn:
        if require_db:
            raise OnboardingStateUnavailable(
                f"onboarding-state DB unavailable (require_db) user_id={user_id}"
            )
        return
    try:
        _ensure_table(conn)
        now = datetime.now(timezone.utc)
        completed_at = now if status == ONBOARDING_COMPLETED else None
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rico_onboarding_states (user_id, status, completed_at, updated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE
                    SET status       = EXCLUDED.status,
                        completed_at = COALESCE(EXCLUDED.completed_at,
                                                rico_onboarding_states.completed_at),
                        updated_at   = EXCLUDED.updated_at
                """,
                (user_id, status, completed_at, now),
            )
        conn.commit()
    except Exception as exc:
        logger.exception("onboarding_repo: set_status_failed user_id=%s status=%s", user_id, status)
        try:
            conn.rollback()
        except Exception:
            pass
        if require_db:
            raise OnboardingStateUnavailable(
                f"onboarding-state write failed (require_db) user_id={user_id}"
            ) from exc
    finally:
        conn.close()


def is_onboarding_complete(user_id: str) -> bool:
    """Return True only if DB confirms this user completed onboarding."""
    state = get_onboarding_state(user_id)
    return state is not None and state.is_complete()


def mark_onboarding_complete(user_id: str) -> None:
    set_onboarding_status(user_id, ONBOARDING_COMPLETED)
