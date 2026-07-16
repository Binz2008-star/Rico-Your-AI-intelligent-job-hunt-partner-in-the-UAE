"""
src/repositories/gmail_repo.py
DB I/O for the Gmail read-only connector tables (migration 043).
Callers receive plain dicts — no SQL above this layer.

Style mirrors settings_repo.py:
  * get_db_connection() from src.db; connection closed per call.
  * Read paths NEVER raise — they log and return None/[] so a missing table
    (migration not yet applied) degrades to "not connected / no data".
  * Write paths log and return None/False on failure.
  * user_id is the TEXT external user id (email — the JWT sub), matching
    email_alert_log / telegram_alert_log. NOT the rico_users UUID.
  * No email bodies pass through this layer — subject/sender snippets only.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from src.db import get_db_connection

logger = logging.getLogger(__name__)

_CONNECTION_COLS = (
    "id, user_id, provider, provider_account_email, scopes, "
    "encrypted_refresh_token, token_encryption_key_version, status, "
    "recurring_sync_consent_at, last_connected_at, last_refresh_at, "
    "last_sync_at, last_error, created_at, updated_at"
)


def _connection_row_to_dict(row: Any) -> Dict[str, Any]:
    return {
        "id": str(row[0]),
        "user_id": row[1],
        "provider": row[2],
        "provider_account_email": row[3],
        "scopes": list(row[4] or []),
        "encrypted_refresh_token": row[5],
        "token_encryption_key_version": row[6],
        "status": row[7],
        "recurring_sync_consent_at": row[8],
        "last_connected_at": row[9],
        "last_refresh_at": row[10],
        "last_sync_at": row[11],
        "last_error": row[12],
        "created_at": row[13],
        "updated_at": row[14],
    }


def _pg_text_array(values: Optional[List[str]]) -> str:
    """Python list → PostgreSQL text[] literal (settings_repo idiom)."""
    return "{" + ",".join(
        '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'
        for v in (values or [])
    ) + "}"


# ── Connections ───────────────────────────────────────────────────────────────


def get_connection(user_id: str, provider: str = "gmail") -> Optional[Dict[str, Any]]:
    """Latest non-revoked connection for a user (active or needs_reauth)."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT {_CONNECTION_COLS}
                    FROM gmail_connections
                    WHERE user_id = %s AND provider = %s AND status != 'revoked'
                    ORDER BY updated_at DESC
                    LIMIT 1""",
                (user_id, provider),
            )
            row = cur.fetchone()
        return _connection_row_to_dict(row) if row else None
    except Exception:
        logger.exception("gmail_repo_get_connection_failed")
        return None
    finally:
        conn.close()


def list_active_connections(limit: int = 500) -> List[Dict[str, Any]]:
    """Active connections that opted in to recurring sync — for the cron fleet
    sweep ONLY.

    The OAuth read grant is not consent to recurring background sync, so the
    sweep is restricted to rows where ``recurring_sync_consent_at`` is set
    (see design doc §3 "Sync Modes" and BLOCKER 2). Manual, user-initiated
    sync does not use this method and does not require the consent.
    """
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT {_CONNECTION_COLS}
                    FROM gmail_connections
                    WHERE status = 'active'
                      AND recurring_sync_consent_at IS NOT NULL
                    ORDER BY last_sync_at ASC NULLS FIRST
                    LIMIT %s""",
                (limit,),
            )
            rows = cur.fetchall()
        return [_connection_row_to_dict(r) for r in rows]
    except Exception:
        logger.exception("gmail_repo_list_active_connections_failed")
        return []
    finally:
        conn.close()


def upsert_connection(
    user_id: str,
    encrypted_refresh_token: str,
    provider_account_email: Optional[str] = None,
    scopes: Optional[List[str]] = None,
    key_version: Optional[str] = None,
    provider: str = "gmail",
) -> Optional[Dict[str, Any]]:
    """Create or refresh the user's connection after a successful OAuth callback.

    Any existing non-revoked row for (user_id, provider) is updated in place
    and reactivated; otherwise a new row is inserted. Returns the stored row
    as a dict, or None on failure.
    """
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id FROM gmail_connections
                   WHERE user_id = %s AND provider = %s AND status != 'revoked'
                   ORDER BY updated_at DESC LIMIT 1""",
                (user_id, provider),
            )
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    f"""UPDATE gmail_connections
                        SET encrypted_refresh_token = %s,
                            provider_account_email = COALESCE(%s, provider_account_email),
                            scopes = %s::TEXT[],
                            token_encryption_key_version = %s,
                            status = 'active',
                            last_connected_at = NOW(),
                            last_error = NULL,
                            updated_at = NOW()
                        WHERE id = %s
                        RETURNING {_CONNECTION_COLS}""",
                    (
                        encrypted_refresh_token,
                        provider_account_email,
                        _pg_text_array(scopes),
                        key_version,
                        existing[0],
                    ),
                )
            else:
                cur.execute(
                    f"""INSERT INTO gmail_connections
                        (user_id, provider, provider_account_email, scopes,
                         encrypted_refresh_token, token_encryption_key_version, status)
                        VALUES (%s, %s, %s, %s::TEXT[], %s, %s, 'active')
                        RETURNING {_CONNECTION_COLS}""",
                    (
                        user_id,
                        provider,
                        provider_account_email,
                        _pg_text_array(scopes),
                        encrypted_refresh_token,
                        key_version,
                    ),
                )
            row = cur.fetchone()
        conn.commit()
        return _connection_row_to_dict(row) if row else None
    except Exception:
        logger.exception("gmail_repo_upsert_connection_failed user_id=%s", user_id)
        _safe_rollback(conn)
        return None
    finally:
        conn.close()


def mark_connection_status(
    user_id: str,
    status: str,
    last_error: Optional[str] = None,
    provider: str = "gmail",
) -> bool:
    """Set connection status (e.g. 'needs_reauth') without deleting history."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE gmail_connections
                   SET status = %s, last_error = %s, updated_at = NOW()
                   WHERE user_id = %s AND provider = %s AND status != 'revoked'""",
                (status, last_error, user_id, provider),
            )
            updated = cur.rowcount
        conn.commit()
        return updated > 0
    except Exception:
        logger.exception("gmail_repo_mark_connection_status_failed user_id=%s", user_id)
        _safe_rollback(conn)
        return False
    finally:
        conn.close()


def touch_last_sync(user_id: str, provider: str = "gmail") -> bool:
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE gmail_connections
                   SET last_sync_at = NOW(), updated_at = NOW()
                   WHERE user_id = %s AND provider = %s AND status != 'revoked'""",
                (user_id, provider),
            )
        conn.commit()
        return True
    except Exception:
        logger.exception("gmail_repo_touch_last_sync_failed user_id=%s", user_id)
        _safe_rollback(conn)
        return False
    finally:
        conn.close()


def tombstone_connection(user_id: str, provider: str = "gmail") -> bool:
    """User-requested disconnect: blank the encrypted token, keep audit history."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE gmail_connections
                   SET status = 'revoked', encrypted_refresh_token = '',
                       last_error = NULL, updated_at = NOW()
                   WHERE user_id = %s AND provider = %s AND status != 'revoked'""",
                (user_id, provider),
            )
            updated = cur.rowcount
        conn.commit()
        return updated > 0
    except Exception:
        logger.exception("gmail_repo_tombstone_connection_failed user_id=%s", user_id)
        _safe_rollback(conn)
        return False
    finally:
        conn.close()


def set_recurring_sync_consent(
    user_id: str, granted: bool, provider: str = "gmail"
) -> bool:
    """Grant or revoke recurring (fleet) sync consent for the user's connection.

    Consent is SEPARATE from the OAuth read grant — granting sets
    ``recurring_sync_consent_at = NOW()``; revoking sets it back to NULL,
    which immediately excludes the connection from the next fleet sweep
    (list_active_connections). Only non-revoked rows are touched; imported
    history and the encrypted token are untouched either way.

    Returns True when a connection row was updated (i.e. the user had a
    non-revoked connection to consent on).
    """
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE gmail_connections
                   SET recurring_sync_consent_at = CASE WHEN %s THEN NOW() ELSE NULL END,
                       updated_at = NOW()
                   WHERE user_id = %s AND provider = %s AND status != 'revoked'""",
                (bool(granted), user_id, provider),
            )
            updated = cur.rowcount
        conn.commit()
        return updated > 0
    except Exception:
        logger.exception(
            "gmail_repo_set_recurring_sync_consent_failed user_id=%s", user_id
        )
        _safe_rollback(conn)
        return False
    finally:
        conn.close()


# ── Sync runs ─────────────────────────────────────────────────────────────────


def create_sync_run(
    user_id: str,
    connection_id: str,
    mode: str,
    lookback_days: Optional[int] = None,
) -> Optional[str]:
    """Insert a 'running' sync-run row; returns its id (or None on failure)."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO gmail_sync_runs
                   (user_id, connection_id, mode, status, lookback_days)
                   VALUES (%s, %s, %s, 'running', %s)
                   RETURNING id""",
                (user_id, connection_id, mode, lookback_days),
            )
            row = cur.fetchone()
        conn.commit()
        return str(row[0]) if row else None
    except Exception:
        logger.exception("gmail_repo_create_sync_run_failed user_id=%s", user_id)
        _safe_rollback(conn)
        return None
    finally:
        conn.close()


def finish_sync_run(
    run_id: str,
    status: str,
    counters: Optional[Dict[str, int]] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
) -> bool:
    """Finalize a sync-run row with status + counters."""
    counters = counters or {}
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE gmail_sync_runs
                   SET status = %s, finished_at = NOW(),
                       messages_fetched = %s, messages_classified = %s,
                       messages_skipped = %s, updates_applied = %s,
                       queued_for_review = %s, error_code = %s, error_message = %s
                   WHERE id = %s""",
                (
                    status,
                    int(counters.get("messages_fetched", 0)),
                    int(counters.get("messages_classified", 0)),
                    int(counters.get("messages_skipped", 0)),
                    int(counters.get("updates_applied", 0)),
                    int(counters.get("queued_for_review", 0)),
                    error_code,
                    error_message,
                    run_id,
                ),
            )
        conn.commit()
        return True
    except Exception:
        logger.exception("gmail_repo_finish_sync_run_failed run_id=%s", run_id)
        _safe_rollback(conn)
        return False
    finally:
        conn.close()


def list_sync_runs(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, mode, status, started_at, finished_at, lookback_days,
                          messages_fetched, messages_classified, messages_skipped,
                          updates_applied, queued_for_review, error_code
                   FROM gmail_sync_runs
                   WHERE user_id = %s
                   ORDER BY started_at DESC
                   LIMIT %s""",
                (user_id, limit),
            )
            rows = cur.fetchall()
        return [
            {
                "id": str(r[0]),
                "mode": r[1],
                "status": r[2],
                "started_at": r[3].isoformat() if r[3] else None,
                "finished_at": r[4].isoformat() if r[4] else None,
                "lookback_days": r[5],
                "messages_fetched": r[6],
                "messages_classified": r[7],
                "messages_skipped": r[8],
                "updates_applied": r[9],
                "queued_for_review": r[10],
                "error_code": r[11],
            }
            for r in rows
        ]
    except Exception:
        logger.exception("gmail_repo_list_sync_runs_failed user_id=%s", user_id)
        return []
    finally:
        conn.close()


# ── Review items ──────────────────────────────────────────────────────────────

_REVIEW_COLS = (
    "id, user_id, sync_run_id, gmail_message_id, gmail_thread_id, "
    "subject_snippet, sender, received_at, classified_status, "
    "classification_confidence, company_hint, matched_job_id, matched_company, "
    "matched_title, match_confidence, match_reason, proposed_status, "
    "review_status, created_at"
)


def _review_row_to_dict(row: Any) -> Dict[str, Any]:
    return {
        "id": str(row[0]),
        "user_id": row[1],
        "sync_run_id": str(row[2]) if row[2] else None,
        "gmail_message_id": row[3],
        "gmail_thread_id": row[4],
        "subject_snippet": row[5],
        "sender": row[6],
        "received_at": row[7].isoformat() if row[7] else None,
        "classified_status": row[8],
        "classification_confidence": float(row[9]) if row[9] is not None else None,
        "company_hint": row[10],
        "matched_job_id": row[11],
        "matched_company": row[12],
        "matched_title": row[13],
        "match_confidence": float(row[14]) if row[14] is not None else None,
        "match_reason": row[15],
        "proposed_status": row[16],
        "review_status": row[17],
        "created_at": row[18].isoformat() if row[18] else None,
    }


def insert_review_item(item: Dict[str, Any]) -> bool:
    """Insert a review item; duplicate (user_id, gmail_message_id) is a no-op.

    Returns True only when a NEW row was inserted.
    """
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO gmail_review_items
                   (user_id, sync_run_id, gmail_message_id, gmail_thread_id,
                    subject_snippet, sender, received_at, classified_status,
                    classification_confidence, company_hint, matched_job_id,
                    matched_company, matched_title, match_confidence,
                    match_reason, proposed_status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (user_id, gmail_message_id) DO NOTHING
                   RETURNING id""",
                (
                    item.get("user_id"),
                    item.get("sync_run_id"),
                    item.get("gmail_message_id"),
                    item.get("gmail_thread_id"),
                    (item.get("subject_snippet") or "")[:300] or None,
                    (item.get("sender") or "")[:300] or None,
                    item.get("received_at"),
                    item.get("classified_status"),
                    item.get("classification_confidence"),
                    item.get("company_hint"),
                    item.get("matched_job_id"),
                    item.get("matched_company"),
                    item.get("matched_title"),
                    item.get("match_confidence"),
                    item.get("match_reason"),
                    item.get("proposed_status"),
                ),
            )
            inserted = cur.fetchone()
        conn.commit()
        return inserted is not None
    except Exception:
        logger.exception(
            "gmail_repo_insert_review_item_failed user_id=%s", item.get("user_id")
        )
        _safe_rollback(conn)
        return False
    finally:
        conn.close()


def list_review_items(
    user_id: str, review_status: str = "pending", limit: int = 50
) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT {_REVIEW_COLS}
                    FROM gmail_review_items
                    WHERE user_id = %s AND review_status = %s
                    ORDER BY created_at DESC
                    LIMIT %s""",
                (user_id, review_status, limit),
            )
            rows = cur.fetchall()
        return [_review_row_to_dict(r) for r in rows]
    except Exception:
        logger.exception("gmail_repo_list_review_items_failed user_id=%s", user_id)
        return []
    finally:
        conn.close()


def get_review_item(user_id: str, item_id: str) -> Optional[Dict[str, Any]]:
    """User-scoped single review item lookup (never another user's row)."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT {_REVIEW_COLS}
                    FROM gmail_review_items
                    WHERE user_id = %s AND id = %s""",
                (user_id, item_id),
            )
            row = cur.fetchone()
        return _review_row_to_dict(row) if row else None
    except Exception:
        logger.exception("gmail_repo_get_review_item_failed user_id=%s", user_id)
        return None
    finally:
        conn.close()


def set_review_item_status(user_id: str, item_id: str, review_status: str) -> bool:
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE gmail_review_items
                   SET review_status = %s, updated_at = NOW()
                   WHERE user_id = %s AND id = %s""",
                (review_status, user_id, item_id),
            )
            updated = cur.rowcount
        conn.commit()
        return updated > 0
    except Exception:
        logger.exception("gmail_repo_set_review_item_status_failed user_id=%s", user_id)
        _safe_rollback(conn)
        return False
    finally:
        conn.close()


def claim_review_item_for_approval(
    user_id: str, item_id: str
) -> Optional[Dict[str, Any]]:
    """Atomically claim a pending review item for approval (BLOCKER 3).

    Single conditional UPDATE that flips ``review_status`` pending → approved
    and RETURNS the row ONLY if it was still pending. This is the concurrency
    gate for approval: two racing requests both target the same row, but the
    DB serializes the UPDATE, so exactly one sees ``rowcount == 1`` and gets the
    row back — the loser gets ``None`` (no row matched the ``= 'pending'``
    predicate) and must no-op. This makes the application-status apply run
    exactly once, replacing the old non-atomic read-check-then-mutate that could
    double-apply under concurrent approvals.

    Returns the claimed row as a dict, or None if it was not pending (already
    resolved, not found, or wrong user).
    """
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""UPDATE gmail_review_items
                    SET review_status = 'approved', updated_at = NOW()
                    WHERE user_id = %s AND id = %s AND review_status = 'pending'
                    RETURNING {_REVIEW_COLS}""",
                (user_id, item_id),
            )
            row = cur.fetchone()
        conn.commit()
        return _review_row_to_dict(row) if row else None
    except Exception:
        logger.exception(
            "gmail_repo_claim_review_item_for_approval_failed user_id=%s", user_id
        )
        _safe_rollback(conn)
        return None
    finally:
        conn.close()


# ── Audit events ──────────────────────────────────────────────────────────────


def insert_audit_event(
    user_id: str,
    event_type: str,
    status: str,
    connection_id: Optional[str] = None,
    sync_run_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """Best-effort audit write. Metadata must never contain tokens or bodies."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO gmail_audit_events
                   (user_id, connection_id, sync_run_id, event_type, status, metadata)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    user_id,
                    connection_id,
                    sync_run_id,
                    event_type,
                    status,
                    json.dumps(metadata) if metadata else None,
                ),
            )
        conn.commit()
        return True
    except Exception:
        logger.exception("gmail_repo_insert_audit_event_failed user_id=%s", user_id)
        _safe_rollback(conn)
        return False
    finally:
        conn.close()


# ── Internal ──────────────────────────────────────────────────────────────────


def _safe_rollback(conn: Any) -> None:
    rollback = getattr(conn, "rollback", None)
    if callable(rollback):
        try:
            rollback()
        except Exception:
            logger.exception("gmail_repo_rollback_failed")
