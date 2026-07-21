"""Atomic Postgres ownership store for chat job-search operations.

DEC-20260721-001 stabilization slice 1: claims are serialized with a row lock
(SELECT ... FOR UPDATE) and liveness is a heartbeat lease, so ownership is
correct across any number of workers/instances — unlike the in-process nonce
model this replaces (see migration 050 header for the full rationale).

Contract with src/services/operation_state.py (the only intended caller):
every function raises RepoUnavailable on infrastructure problems (no
DATABASE_URL, connection failure, table not migrated yet) so the service can
fall back to the legacy in-process behavior; data outcomes ("no such row",
"claim refused", "fence rejected the write") are returned as values, never
as exceptions.
"""
from __future__ import annotations

import logging
import os
from typing import Any

try:  # pragma: no cover - import guard mirrors src/db.py
    import psycopg2
except Exception:  # pragma: no cover
    psycopg2 = None

logger = logging.getLogger(__name__)

_UNDEFINED_TABLE_PGCODE = "42P01"

TERMINAL_STATUSES = ("completed", "failed", "cancelled", "expired")

_COLS = (
    "operation_id, user_id, op_type, role_query, status, attempt, "
    "executor_nonce, result_count, error, "
    "EXTRACT(EPOCH FROM (now() - heartbeat_at)) AS heartbeat_age_seconds, "
    "created_at, updated_at, completed_at"
)


class RepoUnavailable(Exception):
    """The Postgres store cannot be used right now (fallback is expected)."""


def _connect():
    url = os.getenv("DATABASE_URL")
    if not url or psycopg2 is None:
        raise RepoUnavailable("DATABASE_URL or psycopg2 missing")
    try:
        return psycopg2.connect(url, connect_timeout=5)
    except Exception as exc:  # OperationalError and friends
        raise RepoUnavailable(f"connection failed: {exc}") from exc


def _reraise_infra(exc: BaseException) -> None:
    """Translate infrastructure-shaped DB errors into RepoUnavailable."""
    if getattr(exc, "pgcode", None) == _UNDEFINED_TABLE_PGCODE:
        raise RepoUnavailable("chat_operations table not migrated yet") from exc
    if psycopg2 is not None and isinstance(exc, psycopg2.OperationalError):
        raise RepoUnavailable(f"operational error: {exc}") from exc
    raise exc


def _to_operation(row: tuple) -> dict[str, Any]:
    (
        operation_id, user_id, op_type, role_query, status, attempt,
        executor_nonce, result_count, error, heartbeat_age,
        created_at, updated_at, completed_at,
    ) = row
    return {
        "operation_id": operation_id,
        "user_id": user_id,
        "type": op_type,
        "role": role_query,
        "query": role_query,
        "status": status,
        "attempt": int(attempt),
        "executor_nonce": executor_nonce,
        "result_count": result_count,
        "error": error,
        "heartbeat_age_seconds": float(heartbeat_age) if heartbeat_age is not None else None,
        "created_at": created_at.isoformat() if created_at else None,
        "updated_at": updated_at.isoformat() if updated_at else None,
        "completed_at": completed_at.isoformat() if completed_at else None,
        # Marks the record as governed by the shared-store lease semantics
        # (operation_state branches liveness on this).
        "ownership": "db",
    }


def claim(
    *,
    user_id: str,
    operation_id: str,
    role_query: str,
    executor_nonce: str,
    lease_seconds: int,
) -> dict[str, Any]:
    """Atomically claim *operation_id* for execution.

    Returns {"claimed": bool, "reason": str, "operation": dict|None}:
      * claimed=True  — reasons "new" (no row), "restart" (previous row was
        terminal; attempt bumped) or "lease_takeover" (previous executor's
        heartbeat lease expired — proof of death; attempt bumped, which
        revokes the dead execution's write rights via the attempt fence).
      * claimed=False — "refused_live" (same user's operation is live: fresh
        heartbeat, non-terminal; its current row is returned) or
        "refused_foreign" (a DIFFERENT user's live operation holds this id;
        nothing about it is returned — the caller mints a fresh id).

    The SELECT ... FOR UPDATE row lock serializes concurrent claimers: the
    loser observes the winner's committed row and is refused.
    """
    conn = _connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_COLS} FROM chat_operations "
                    "WHERE operation_id = %s FOR UPDATE",
                    (operation_id,),
                )
                row = cur.fetchone()
                if row is None:
                    cur.execute(
                        "INSERT INTO chat_operations "
                        "(operation_id, user_id, op_type, role_query, status, "
                        " attempt, executor_nonce, heartbeat_at) "
                        "VALUES (%s, %s, 'job_search', %s, 'running', 1, %s, now()) "
                        f"RETURNING {_COLS}",
                        (operation_id, user_id, role_query, executor_nonce),
                    )
                    return {
                        "claimed": True,
                        "reason": "new",
                        "operation": _to_operation(cur.fetchone()),
                    }

                existing = _to_operation(row)
                terminal = existing["status"] in TERMINAL_STATUSES
                age = existing.get("heartbeat_age_seconds")
                lease_dead = age is None or age >= lease_seconds
                if not terminal and not lease_dead:
                    if existing["user_id"] != user_id:
                        return {"claimed": False, "reason": "refused_foreign", "operation": None}
                    return {"claimed": False, "reason": "refused_live", "operation": existing}

                cur.execute(
                    "UPDATE chat_operations SET "
                    "user_id = %s, role_query = %s, status = 'running', "
                    "attempt = attempt + 1, executor_nonce = %s, "
                    "heartbeat_at = now(), result_count = NULL, error = NULL, "
                    "completed_at = NULL, created_at = now(), updated_at = now() "
                    "WHERE operation_id = %s "
                    f"RETURNING {_COLS}",
                    (user_id, role_query, executor_nonce, operation_id),
                )
                return {
                    "claimed": True,
                    "reason": "restart" if terminal else "lease_takeover",
                    "operation": _to_operation(cur.fetchone()),
                }
    except RepoUnavailable:
        raise
    except Exception as exc:
        _reraise_infra(exc)
    finally:
        conn.close()


def get(user_id: str, operation_id: str) -> dict[str, Any] | None:
    conn = _connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_COLS} FROM chat_operations "
                    "WHERE operation_id = %s AND user_id = %s",
                    (operation_id, user_id),
                )
                row = cur.fetchone()
                return _to_operation(row) if row else None
    except RepoUnavailable:
        raise
    except Exception as exc:
        _reraise_infra(exc)
    finally:
        conn.close()


def get_latest(user_id: str) -> dict[str, Any] | None:
    conn = _connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_COLS} FROM chat_operations "
                    "WHERE user_id = %s AND op_type = 'job_search' "
                    "ORDER BY created_at DESC, updated_at DESC LIMIT 1",
                    (user_id,),
                )
                row = cur.fetchone()
                return _to_operation(row) if row else None
    except RepoUnavailable:
        raise
    except Exception as exc:
        _reraise_infra(exc)
    finally:
        conn.close()


def heartbeat(*, operation_id: str, attempt: int, executor_nonce: str) -> bool:
    """Renew the executor's lease. False when superseded/terminal (stop renewing)."""
    conn = _connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE chat_operations "
                    "SET heartbeat_at = now(), updated_at = now() "
                    "WHERE operation_id = %s AND attempt = %s "
                    "AND executor_nonce = %s AND status IN ('running', 'timed_out')",
                    (operation_id, attempt, executor_nonce),
                )
                return cur.rowcount > 0
    except RepoUnavailable:
        raise
    except Exception as exc:
        _reraise_infra(exc)
    finally:
        conn.close()


def update_status(
    *,
    user_id: str,
    operation_id: str,
    status: str,
    result_count: int | None = None,
    error: str | None = None,
    attempt: int | None = None,
) -> dict[str, Any] | None:
    """Attempt-fenced status write; returns the updated row or None when the
    fence (stale attempt), the completed-protection (a failed write never
    overwrites completed), or ownership (user/id) rejected it."""
    conn = _connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE chat_operations SET "
                    "status = %(status)s, updated_at = now(), "
                    "result_count = COALESCE(%(result_count)s, result_count), "
                    "error = COALESCE(%(error)s, error), "
                    "completed_at = CASE WHEN %(status)s IN "
                    "  ('completed','failed','cancelled','expired') "
                    "  THEN now() ELSE completed_at END "
                    "WHERE operation_id = %(operation_id)s AND user_id = %(user_id)s "
                    "AND (%(attempt)s::int IS NULL OR attempt = %(attempt)s) "
                    "AND NOT (%(status)s = 'failed' AND status = 'completed') "
                    f"RETURNING {_COLS}",
                    {
                        "status": status,
                        "result_count": result_count,
                        "error": error,
                        "operation_id": operation_id,
                        "user_id": user_id,
                        "attempt": attempt,
                    },
                )
                row = cur.fetchone()
                return _to_operation(row) if row else None
    except RepoUnavailable:
        raise
    except Exception as exc:
        _reraise_infra(exc)
    finally:
        conn.close()


def stats(*, lease_seconds: int) -> dict[str, Any]:
    """Aggregate operations-health counters for admin observability
    (DEC-20260721-001 slice 2). Read-only; one indexed scan.

    "stuck" = running/timed_out whose heartbeat lease already expired but
    which no read path has visited yet to transition to `expired` — the
    exact population an operator needs to see."""
    conn = _connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT "
                    "count(*) FILTER (WHERE status = 'running') AS running, "
                    "count(*) FILTER (WHERE status = 'timed_out') AS timed_out, "
                    "count(*) FILTER (WHERE status IN ('running','timed_out') "
                    "  AND heartbeat_at < now() - make_interval(secs => %(lease)s)) AS stuck_lease_dead, "
                    "count(*) FILTER (WHERE status = 'completed' "
                    "  AND created_at > now() - interval '24 hours') AS completed_24h, "
                    "count(*) FILTER (WHERE status = 'failed' "
                    "  AND created_at > now() - interval '24 hours') AS failed_24h, "
                    "count(*) FILTER (WHERE status = 'expired' "
                    "  AND created_at > now() - interval '24 hours') AS expired_24h, "
                    "count(*) FILTER (WHERE created_at > now() - interval '24 hours') AS started_24h, "
                    "count(*) FILTER (WHERE created_at > now() - interval '7 days') AS started_7d, "
                    "EXTRACT(EPOCH FROM (now() - min(created_at) "
                    "  FILTER (WHERE status IN ('running','timed_out')))) AS oldest_active_age_seconds "
                    "FROM chat_operations",
                    {"lease": lease_seconds},
                )
                row = cur.fetchone()
                keys = (
                    "running", "timed_out", "stuck_lease_dead", "completed_24h",
                    "failed_24h", "expired_24h", "started_24h", "started_7d",
                    "oldest_active_age_seconds",
                )
                out = dict(zip(keys, row))
                if out["oldest_active_age_seconds"] is not None:
                    out["oldest_active_age_seconds"] = float(out["oldest_active_age_seconds"])
                return out
    except RepoUnavailable:
        raise
    except Exception as exc:
        _reraise_infra(exc)
    finally:
        conn.close()


def expire_if_lease_dead(
    *, user_id: str, operation_id: str, lease_seconds: int
) -> dict[str, Any] | None:
    """Atomically transition a lease-dead running/timed_out row to expired.

    The heartbeat-freshness re-check runs inside the UPDATE against the
    database clock, so a concurrent renewal wins and the transition is
    skipped. Returns the expired row, or None when nothing transitioned."""
    conn = _connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE chat_operations "
                    "SET status = 'expired', updated_at = now(), completed_at = now() "
                    "WHERE operation_id = %s AND user_id = %s "
                    "AND status IN ('running', 'timed_out') "
                    "AND heartbeat_at < now() - make_interval(secs => %s) "
                    f"RETURNING {_COLS}",
                    (operation_id, user_id, lease_seconds),
                )
                row = cur.fetchone()
                return _to_operation(row) if row else None
    except RepoUnavailable:
        raise
    except Exception as exc:
        _reraise_infra(exc)
    finally:
        conn.close()
