"""User-data erasure orchestrator (#1088 — durable erasure wiring).

ONE shared purge path for every user erasure surface:

  - ``erase_conversation_data``  — "Delete all chat history"
  - ``erase_memory_data``        — "Delete Rico memory"
  - ``erase_account_data``       — account deletion (superset of both)

Contracts:

  * **Truthful failure** — any store that cannot be verifiably erased raises
    :class:`ErasureError`; HTTP callers translate it into a retryable non-2xx.
    A DB outage never produces a success claim (#1088 item 2, #764).
  * **Deletion receipt** — success returns content-free affected counts by
    storage class (#1088 item 6). No message content, no email, no tokens.
  * **No resurrection** — the memory-engine purge advances the account's
    deletion generation inside the same transaction that deletes its rows
    (``career_memory_repo.purge_account_memory``), so a stale pre-erasure
    engine write is refused by the writer's admission check (#1088 item 5).
  * **Never provisions** — resolution of the canonical account row is strict
    and read-only; erasing data for a user who has no DB rows is a successful
    no-op, but an *unverifiable* store (DB down) is a hard failure.
  * **Not flag-gated** — erasure works while ``RICO_MEMORY_ENGINE_ENABLED`` is
    off and while memory writes are disabled; a user's deletion request is
    honored regardless of feature state.

Known residual gap (documented, NOT closed here): the legacy chat append is a
fire-and-forget daemon thread with no per-user history generation, so a DB
append already in flight when the clear commits can still land afterwards
(#1088 item 3 for the *legacy* store). Serializing that path needs its own
schema (generation column on rico_chat_history) and is deliberately out of
scope for this wiring PR.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ErasureError(RuntimeError):
    """A user-erasure step could not be verifiably completed."""


# ─────────────────────────────────────────────────────────────────────────────
# Strict canonical-account resolution (read-only; never provisions)
# ─────────────────────────────────────────────────────────────────────────────

def _rico_db():
    from src.rico_db import RicoDB

    return RicoDB()


def _resolve_db_account_strict(user_id: str) -> Optional[str]:
    """Resolve *user_id* to the canonical rico_users UUID, or None when no row
    exists. Raises :class:`ErasureError` when the database cannot be reached —
    "cannot verify" is never treated as "nothing to erase".

    Same precedence as chat_service._resolve_db_user_id (id > email >
    external_user_id) but strictly read-only: erasure must never auto-provision
    the very row family it is erasing.
    """
    db = _rico_db()
    if not getattr(db, "available", False):
        raise ErasureError(f"erasure: database unavailable for user resolution user={user_id}")
    try:
        conn = db.connect()
    except Exception as exc:
        raise ErasureError(f"erasure: database connect failed: {exc}") from exc
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text FROM rico_users
                WHERE external_user_id = %s OR email = %s OR id::text = %s
                ORDER BY
                    CASE WHEN id::text = %s THEN 0 ELSE 1 END,
                    CASE WHEN email = %s THEN 0 ELSE 1 END,
                    updated_at DESC NULLS LAST
                LIMIT 1
                """,
                (user_id, user_id, user_id, user_id, user_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            return row[0] if not isinstance(row, dict) else row["id"]
    except Exception as exc:
        raise ErasureError(f"erasure: account resolution failed: {exc}") from exc
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Storage-class erasers
# ─────────────────────────────────────────────────────────────────────────────

def _delete_chat_rows(db_uid: str) -> int:
    """DELETE the user's rico_chat_history rows. Mandatory: raises on failure."""
    db = _rico_db()
    if not getattr(db, "available", False):
        raise ErasureError("erasure: database unavailable for chat deletion")
    try:
        conn = db.connect()
    except Exception as exc:
        raise ErasureError(f"erasure: database connect failed: {exc}") from exc
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rico_chat_history WHERE user_id = %s", (db_uid,))
            deleted = cur.rowcount or 0
        conn.commit()
        return deleted
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        raise ErasureError(f"erasure: chat deletion failed: {exc}") from exc
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _memory_store():
    from src.rico_memory import RicoMemoryStore

    return RicoMemoryStore()


def _erase_conversation_memories(user_id: str) -> int:
    """Remove memory_type == 'conversation' entries from the legacy memory file.

    Other memory types are retained (chat-clear scope). Returns removed count.
    Raises ErasureError when the file exists but cannot be rewritten — a
    partial local erase must not be reported as success (#1088 item 4).
    """
    store = _memory_store()
    try:
        memories = store.load_memories(user_id)
    except Exception as exc:
        raise ErasureError(f"erasure: conversation-memory read failed: {exc}") from exc
    if not memories:
        return 0
    kept = [m for m in memories if (m or {}).get("memory_type") != "conversation"]
    removed = len(memories) - len(kept)
    if removed == 0:
        return 0
    try:
        path = store._memories_path(user_id)
        if kept:
            import json

            path.write_text(
                json.dumps(kept, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        else:
            path.unlink(missing_ok=True)
    except Exception as exc:
        raise ErasureError(f"erasure: conversation-memory rewrite failed: {exc}") from exc
    return removed


def _erase_memory_file(user_id: str) -> int:
    """Delete the ENTIRE legacy memories file (memory/account scope).

    Returns the number of entries erased. Absent file → 0 (idempotent).
    """
    store = _memory_store()
    try:
        entries = len(store.load_memories(user_id) or [])
        store._memories_path(user_id).unlink(missing_ok=True)
        return entries
    except Exception as exc:
        raise ErasureError(f"erasure: memory-file removal failed: {exc}") from exc


def _remove_local_file(path_getter_name: str, user_id: str) -> bool:
    """Unlink one per-user local JSON file. True when a file was removed."""
    store = _memory_store()
    try:
        path = getattr(store, path_getter_name)(user_id)
        existed = path.exists()
        path.unlink(missing_ok=True)
        return existed
    except Exception as exc:
        raise ErasureError(
            f"erasure: local file removal failed ({path_getter_name}): {exc}"
        ) from exc


def _purge_engine(db_uid: Optional[str]) -> Optional[Dict[str, Any]]:
    """Purge the career-memory engine for the account (tombstone + delete).

    Tolerates an unprovisioned engine (migration 042 not applied): with no
    tables there can be no engine rows, so that is a successful no-op reported
    as ``provisioned: False``. Any other engine-DB failure raises.
    """
    if not db_uid:
        return None
    from src.repositories.career_memory_repo import purge_account_memory

    try:
        receipt = purge_account_memory(account_id=db_uid, missing_ok=True)
    except Exception as exc:
        raise ErasureError(f"erasure: engine purge failed: {exc}") from exc
    return receipt


# ─────────────────────────────────────────────────────────────────────────────
# Public erasure surfaces
# ─────────────────────────────────────────────────────────────────────────────

def _receipt(scope: str, **classes: Any) -> Dict[str, Any]:
    return {
        "scope": scope,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        **classes,
    }


def erase_conversation_data(user_id: str) -> Dict[str, Any]:
    """'Delete all chat history': DB chat rows + local chat file + the derived
    conversation-memory copies (#1088 item 1). Facts/other memory types and
    engine job-action episodes are NOT touched by this scope."""
    db_uid = _resolve_db_account_strict(user_id)
    chat_rows = _delete_chat_rows(db_uid) if db_uid else 0
    chat_file_removed = _remove_local_file("_chat_path", user_id)
    conversation_memories = _erase_conversation_memories(user_id)
    receipt = _receipt(
        "chat",
        chat_rows_deleted=chat_rows,
        chat_file_removed=chat_file_removed,
        conversation_memories_deleted=conversation_memories,
    )
    logger.info(
        "erasure: chat scope completed rows=%d conv_memories=%d",
        chat_rows, conversation_memories,
    )
    return receipt


def erase_memory_data(user_id: str) -> Dict[str, Any]:
    """'Delete Rico memory': the entire legacy derived-memory file plus the
    memory-engine rows (purge + deletion-generation bump)."""
    db_uid = _resolve_db_account_strict(user_id)
    memory_entries = _erase_memory_file(user_id)
    engine = _purge_engine(db_uid)
    receipt = _receipt(
        "memory",
        memory_entries_deleted=memory_entries,
        engine=engine,
    )
    logger.info(
        "erasure: memory scope completed entries=%d engine_events=%s",
        memory_entries, (engine or {}).get("events_deleted"),
    )
    return receipt


def erase_account_data(user_id: str) -> Dict[str, Any]:
    """Account-deletion erasure: chat rows, chat/memories/signals local files,
    and the full engine purge. Profile/application row deletion remains the
    account-deletion flow's own responsibility — this erases the conversation
    and derived-memory storage classes it is canonical for."""
    db_uid = _resolve_db_account_strict(user_id)
    chat_rows = _delete_chat_rows(db_uid) if db_uid else 0
    chat_file_removed = _remove_local_file("_chat_path", user_id)
    memory_entries = _erase_memory_file(user_id)
    signals_file_removed = _remove_local_file("_signals_path", user_id)
    engine = _purge_engine(db_uid)
    receipt = _receipt(
        "account",
        chat_rows_deleted=chat_rows,
        chat_file_removed=chat_file_removed,
        memory_entries_deleted=memory_entries,
        signals_file_removed=signals_file_removed,
        engine=engine,
    )
    logger.info(
        "erasure: account scope completed rows=%d entries=%d engine_events=%s",
        chat_rows, memory_entries, (engine or {}).get("events_deleted"),
    )
    return receipt
