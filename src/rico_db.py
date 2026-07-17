"""Neon/PostgreSQL database layer for Rico AI.

Uses the same DATABASE_URL as the existing job automation system. This module
creates Rico-specific tables only when they do not already exist, so it can live
beside the current jobs/applications tables safely.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from contextlib import contextmanager
from datetime import datetime
from threading import Lock
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from dotenv import load_dotenv

load_dotenv()

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor, Json
    from psycopg2 import pool as _pg_pool
except Exception:  # pragma: no cover - dependency may be installed by cloud later
    psycopg2 = None
    RealDictCursor = None
    Json = None
    _pg_pool = None


# ---------------------------------------------------------------------------
# Module-level connection pool — one pool per DATABASE_URL, shared across all
# RicoDB instances and threads.  ThreadedConnectionPool is safe for use in
# multi-threaded FastAPI workers.  Min=1 keeps a warm connection alive between
# requests; max=10 is conservative for Neon's serverless connection limits.
# ---------------------------------------------------------------------------
_pool_lock = Lock()
_pool_registry: Dict[str, Any] = {}


def _get_pool(database_url: str) -> Optional[Any]:
    """Return (creating if necessary) the ThreadedConnectionPool for this URL."""
    if not psycopg2 or not _pg_pool or not database_url:
        return None
    with _pool_lock:
        if database_url not in _pool_registry:
            try:
                _pool_registry[database_url] = _pg_pool.ThreadedConnectionPool(
                    minconn=1,
                    maxconn=10,
                    dsn=database_url,
                    cursor_factory=RealDictCursor,
                    connect_timeout=5,
                )
                logger.info("db_pool_created minconn=1 maxconn=10")
            except Exception as exc:
                logger.warning("db_pool_init_failed: %s — falling back to per-request connections", exc)
                return None
        return _pool_registry.get(database_url)


_RICO_SCHEMA_DDL = """
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS rico_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_user_id TEXT UNIQUE,
    name TEXT,
    email TEXT,
    phone TEXT,
    telegram_username TEXT,
    telegram_chat_id TEXT,
    telegram_notifications_enabled BOOLEAN DEFAULT TRUE,
    source TEXT DEFAULT 'rico',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rico_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES rico_users(id) ON DELETE CASCADE,
    profile JSONB NOT NULL DEFAULT '{}'::jsonb,
    cv_file_url TEXT,
    cv_text TEXT,
    cv_structured JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id)
);

CREATE TABLE IF NOT EXISTS rico_agent_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES rico_users(id) ON DELETE CASCADE,
    settings JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id)
);

CREATE TABLE IF NOT EXISTS rico_chat_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES rico_users(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rico_learning_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES rico_users(id) ON DELETE CASCADE,
    job_id TEXT,
    action TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rico_job_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES rico_users(id) ON DELETE CASCADE,
    job_key TEXT,
    job JSONB NOT NULL DEFAULT '{}'::jsonb,
    repo_score INTEGER,
    rico_score INTEGER,
    explanation TEXT,
    status TEXT DEFAULT 'found',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rico_saved_searches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES rico_users(id) ON DELETE CASCADE,
    query TEXT NOT NULL,
    filters JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, query)
);

CREATE TABLE IF NOT EXISTS rico_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES rico_users(id) ON DELETE CASCADE,
    channel TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    message TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    sent_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS rico_webhook_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider TEXT NOT NULL DEFAULT 'jotform',
    form_id TEXT,
    submission_id TEXT NOT NULL,
    user_id UUID REFERENCES rico_users(id) ON DELETE SET NULL,
    external_user_id TEXT,
    status TEXT NOT NULL DEFAULT 'processing',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    processed_at TIMESTAMPTZ,
    UNIQUE(provider, submission_id)
);

CREATE INDEX IF NOT EXISTS idx_rico_users_email ON rico_users(email);
CREATE INDEX IF NOT EXISTS idx_rico_users_telegram ON rico_users(telegram_username);
CREATE INDEX IF NOT EXISTS idx_rico_users_chat_id ON rico_users(telegram_chat_id);

-- telegram_alert_log: duplicate guard + rate limiting for job-alert sends
CREATE TABLE IF NOT EXISTS telegram_alert_log (
    id          SERIAL      PRIMARY KEY,
    user_id     TEXT        NOT NULL,
    job_key     TEXT        NOT NULL,
    alert_type  TEXT        NOT NULL DEFAULT 'job_match',
    sent_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, job_key, alert_type)
);
CREATE INDEX IF NOT EXISTS idx_tal_user_sent ON telegram_alert_log (user_id, sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_rico_chat_user_created ON rico_chat_history(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rico_signals_user_created ON rico_learning_signals(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rico_recommendations_user_status ON rico_job_recommendations(user_id, status);
CREATE INDEX IF NOT EXISTS idx_rico_saved_searches_user_created ON rico_saved_searches(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rico_webhook_events_submission ON rico_webhook_events(provider, submission_id);
CREATE INDEX IF NOT EXISTS idx_rico_webhook_events_user ON rico_webhook_events(user_id);
"""

_USER_DOCUMENTS_DDL = """
CREATE TABLE IF NOT EXISTS user_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    doc_type TEXT NOT NULL DEFAULT 'cv',
    file_size INTEGER DEFAULT 0,
    label TEXT,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    skills_count INTEGER DEFAULT 0,
    skills_json JSONB DEFAULT '[]'::jsonb,
    years_experience NUMERIC(4,1),
    "current_role" TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_user_documents_user_created
    ON user_documents(user_id, created_at DESC);
-- Idempotent column migration for existing installations (migration 026).
ALTER TABLE user_documents ADD COLUMN IF NOT EXISTS skills_json JSONB DEFAULT '[]'::jsonb;
"""
# NOTE: migration 037 (content_hash column + uq_user_documents_user_type_hash +
# uq_user_documents_one_primary_per_type) is intentionally NOT included here.
# _USER_DOCUMENTS_DDL runs automatically on every process's first DB connect
# (_ensure_schema) and on every app startup (RicoDB.init() via app.py's
# lifespan) — an implicit, untested production schema mutation is exactly the
# failure mode that caused the duplicate-DDL production 500 documented in
# tests/test_user_documents_ddl.py. Migration 037 must be applied explicitly,
# before deploy, per the sequence documented in
# migrations/037_user_documents_content_hash.sql. A fresh/local/test database
# gets the same explicit treatment — run migrations/*.sql in order — rather
# than relying on this auto-applied DDL string.

_APPLY_DRAFTS_DDL = """
CREATE TABLE IF NOT EXISTS application_drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    job_key TEXT NOT NULL,
    job_title TEXT,
    company TEXT,
    job_description TEXT,
    apply_url TEXT,
    tailored_cv TEXT NOT NULL,
    cover_letter TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    follow_up_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_application_drafts_user_status
    ON application_drafts(user_id, status);
ALTER TABLE application_drafts ADD COLUMN IF NOT EXISTS follow_up_at TIMESTAMPTZ;
"""


class DocumentConflictError(Exception):
    """A user_documents write would violate a uniqueness invariant.

    Raised instead of letting the underlying unique-violation propagate as an
    unhandled 500 (e.g. a doc_type rename colliding with an existing row that
    has the same content_hash, or a primary-flag collision). Callers should
    catch this and return a controlled conflict response.
    """


_UNIQUE_VIOLATION_PGCODE = "23505"


def _is_unique_violation(exc: BaseException) -> bool:
    """True when *exc* is a Postgres unique-violation (SQLSTATE 23505).

    Checked via ``pgcode`` rather than ``isinstance(exc, psycopg2.errors.UniqueViolation)``
    so this also works against plain mocked exceptions in tests, not only a
    real psycopg2 driver error.
    """
    return getattr(exc, "pgcode", None) == _UNIQUE_VIOLATION_PGCODE


class RicoDB:
    """Thin PostgreSQL wrapper for Rico AI multi-user memory."""

    _schema_lock = Lock()
    _schema_ready_urls: set[str] = set()

    def __init__(self, database_url: Optional[str] = None) -> None:
        self.database_url = database_url or os.getenv("DATABASE_URL")

    @property
    def available(self) -> bool:
        return bool(self.database_url and psycopg2 is not None)

    def _ensure_schema(self, conn) -> None:
        if not self.database_url:
            return
        if self.database_url in self._schema_ready_urls:
            return

        with self._schema_lock:
            if self.database_url in self._schema_ready_urls:
                return
            with conn.cursor() as cur:
                cur.execute(_RICO_SCHEMA_DDL)
                cur.execute(_APPLY_DRAFTS_DDL)
                cur.execute(_USER_DOCUMENTS_DDL)
            conn.commit()
            self._schema_ready_urls.add(self.database_url)

    def connect(self, *, ensure_schema: bool = True):
        if not self.available:
            raise RuntimeError("RicoDB unavailable: DATABASE_URL or psycopg2 missing")

        # Connection pooling is intentionally DISABLED here.
        #
        # The pooling path stashed the pool on the connection object
        # (`conn._rico_pool = pool`), but psycopg2 connection objects have no
        # __dict__, so that assignment raised
        #   AttributeError: 'psycopg2.extensions.connection' object has no attribute '_rico_pool'
        # on EVERY db.connect() call — taking down all DB-backed endpoints.
        #
        # Pooling is also incompatible with the many direct `db.connect()` callers
        # (subscription_repo / applications_repo / profile_repo), including
        # `with db.connect() as conn:` blocks that never close the connection —
        # those would leak pooled connections (and memory) because they never
        # return the connection to the pool.
        #
        # Re-enabling pooling safely requires routing ALL connection consumers
        # through a single acquire/release path; tracked as a follow-up. For now
        # use a direct per-request connection (the proven pre-overhaul behavior).
        conn = psycopg2.connect(
            self.database_url, cursor_factory=RealDictCursor, connect_timeout=5
        )

        if not ensure_schema:
            return conn
        try:
            self._ensure_schema(conn)
        except Exception:
            self._return_or_close(conn)
            raise
        return conn

    @staticmethod
    def _return_or_close(conn) -> None:
        """Close the connection. (Pooling disabled — see connect().)"""
        try:
            conn.close()
        except Exception:
            pass

    @contextmanager
    def _transaction(self, *, ensure_schema: bool = True):
        """Acquire a connection from the pool (or open one), commit on success."""
        conn = self.connect(ensure_schema=ensure_schema)
        try:
            yield conn
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            self._return_or_close(conn)

    def init(self) -> None:
        """Create Rico tables in the existing Neon database."""
        with self._transaction(ensure_schema=False) as conn:
            with conn.cursor() as cur:
                cur.execute(_RICO_SCHEMA_DDL)
                cur.execute(_APPLY_DRAFTS_DDL)
                cur.execute(_USER_DOCUMENTS_DDL)
        if self.database_url:
            self._schema_ready_urls.add(self.database_url)

    # ── User Documents ─────────────────────────────────────────────────────────

    def count_user_documents(self, user_id: str, doc_type: str) -> int:
        """Return the number of documents of a given type stored for user_id."""
        with self._transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM user_documents WHERE user_id = %s AND doc_type = %s",
                    (user_id, doc_type),
                )
                row = cur.fetchone()
        return int(row["cnt"] if isinstance(row, dict) else row[0])


    def find_user_document_by_hash(
        self, user_id: str, doc_type: str, content_hash: str
    ) -> Optional[Dict[str, Any]]:
        """Return the existing document with this exact content hash, or None.

        Used by the upload path to detect an exact re-upload BEFORE enforcing
        quota, so a duplicate re-upload is never blocked by the storage limit
        (it consumes nothing).
        """
        if not (user_id and doc_type and content_hash):
            return None
        with self._transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, filename, doc_type, is_primary
                      FROM user_documents
                     WHERE user_id = %s AND doc_type = %s AND content_hash = %s
                     LIMIT 1
                    """,
                    (user_id, doc_type, content_hash),
                )
                row = cur.fetchone()
        if not row:
            return None
        return {
            "id": str(row["id"] if isinstance(row, dict) else row[0]),
            "filename": (row["filename"] if isinstance(row, dict) else row[1]),
            "doc_type": (row["doc_type"] if isinstance(row, dict) else row[2]),
            "is_primary": bool(row["is_primary"] if isinstance(row, dict) else row[3]),
        }

    @staticmethod
    def _lock_primary_slot(cur, user_id: str, doc_type: str) -> None:
        """Serialize every write that can change the primary flag for this
        (user_id, doc_type) pair, for the rest of the current transaction.

        A transaction-scoped Postgres advisory lock, not a row lock — it
        works even when the user has zero document rows yet (the first-ever
        upload with is_primary=True), which `SELECT ... FOR UPDATE` cannot do
        since there is no row to lock. Held until COMMIT/ROLLBACK
        (pg_advisory_xact_lock), so two concurrent primary-changing calls for
        the same (user_id, doc_type) are fully ordered: the second blocks
        until the first's transaction ends, then sees its committed result.
        """
        cur.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))",
            (f"user_documents_primary:{user_id}:{doc_type}",),
        )

    @staticmethod
    def _lock_content_slot(cur, user_id: str, doc_type: str, content_hash: str) -> None:
        """Serialize get_or_create_user_document calls for this exact
        (user_id, doc_type, content_hash) tuple, for the rest of the current
        transaction.

        Without this, only is_primary=True uploads were protected (via
        `_lock_primary_slot`) — an ordinary is_primary=False upload had no
        lock at all, so two concurrent identical uploads (double-click,
        client retry) could both pass the duplicate pre-check, both attempt
        the INSERT, and the losing one's `ON CONFLICT DO NOTHING` returned no
        row. This lock makes that pre-check-then-insert sequence safe for
        EVERY call, not only primary ones.

        Always acquired BEFORE `_lock_primary_slot` in
        `get_or_create_user_document` — one consistent lock order across the
        whole class, since the two lock keys are different
        (`content:{hash}` vs `primary:{doc_type}`), so two transactions can
        never deadlock by acquiring them in opposite order.
        """
        cur.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))",
            (f"user_documents_content:{user_id}:{doc_type}:{content_hash}",),
        )

    @staticmethod
    def _document_row_to_dict(row, *, inserted: bool) -> Dict[str, Any]:
        """Normalize a user_documents row (dict-cursor or tuple) into the
        get_or_create_user_document response shape."""
        return {
            "id": str(row["id"] if isinstance(row, dict) else row[0]),
            "filename": (row["filename"] if isinstance(row, dict) else row[1]),
            "doc_type": (row["doc_type"] if isinstance(row, dict) else row[2]),
            "is_primary": bool(row["is_primary"] if isinstance(row, dict) else row[3]),
            "inserted": inserted,
        }

    @staticmethod
    def _promote_if_requested(cur, existing_row, *, user_id: str, doc_type: str, is_primary: bool) -> Dict[str, Any]:
        """Return the get_or_create_user_document response for a found
        pre-existing row, honoring `is_primary=True` even for a deduped
        reupload — promotes the row (clearing any other primary first) if
        it isn't already primary. Requires `_lock_primary_slot` to already
        be held by the caller whenever `is_primary` is True.

        Used by BOTH the fast "found on the upfront pre-check" path and the
        "found after an ON CONFLICT DO NOTHING" fallback — a request for
        `is_primary=True` must be honored the same way regardless of which
        one happened to find the row, or the outcome would depend on lock
        race timing (exactly the class of bug this method exists to avoid).
        """
        existing_id = existing_row["id"] if isinstance(existing_row, dict) else existing_row[0]
        existing_is_primary = bool(existing_row["is_primary"] if isinstance(existing_row, dict) else existing_row[3])
        if is_primary and not existing_is_primary:
            # Clear any other primary first — a redundant no-op if the
            # is_primary=True flow already cleared it earlier in this same
            # transaction; never skip it, since the fast pre-check path
            # reaches here without having cleared anything yet.
            cur.execute(
                """
                UPDATE user_documents SET is_primary = FALSE, updated_at = now()
                 WHERE user_id = %s AND doc_type = %s AND id <> %s AND is_primary = TRUE
                """,
                (user_id, doc_type, existing_id),
            )
            cur.execute(
                "UPDATE user_documents SET is_primary = TRUE, updated_at = now() WHERE id = %s",
                (existing_id,),
            )
            existing_is_primary = True
        return {
            "id": str(existing_id),
            "filename": (existing_row["filename"] if isinstance(existing_row, dict) else existing_row[1]),
            "doc_type": (existing_row["doc_type"] if isinstance(existing_row, dict) else existing_row[2]),
            "is_primary": existing_is_primary,
            "inserted": False,
        }

    def save_user_document(
        self,
        *,
        user_id: str,
        filename: str,
        original_filename: str,
        doc_type: str = "cv",
        file_size: int = 0,
        label: Optional[str] = None,
        skills_count: int = 0,
        skills_json: Optional[List[str]] = None,
        years_experience: Optional[float] = None,
        current_role: Optional[str] = None,
        is_primary: bool = False,
    ) -> Optional[str]:
        """Insert a new document record. Returns the new row's UUID id.

        When ``is_primary``, the old primary is cleared BEFORE the new row is
        inserted, inside one locked transaction. Clearing first (rather than
        inserting the new primary first) matters under migration 037's
        partial unique index `uq_user_documents_one_primary_per_type` —
        that index is not deferrable, so it is checked immediately per
        statement; inserting a second is_primary=TRUE row while the old one
        still carries the flag would violate it right at the INSERT. The
        advisory lock (see `_lock_primary_slot`) serializes concurrent
        primary-setting calls so two of them can never both pass the clear
        step before either has inserted.
        """
        with self._transaction() as conn:
            with conn.cursor() as cur:
                if is_primary:
                    self._lock_primary_slot(cur, user_id, doc_type)
                    cur.execute(
                        """
                        UPDATE user_documents SET is_primary = FALSE, updated_at = now()
                         WHERE user_id = %s AND doc_type = %s AND is_primary = TRUE
                        """,
                        (user_id, doc_type),
                    )
                cur.execute(
                    """
                    INSERT INTO user_documents
                        (user_id, filename, original_filename, doc_type, file_size,
                         label, is_primary, skills_count, skills_json,
                         years_experience, "current_role")
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (user_id, filename, original_filename, doc_type, file_size,
                     label, is_primary, skills_count, Json(skills_json or []),
                     years_experience, current_role),
                )
                row = cur.fetchone()
        return str(row["id"] if isinstance(row, dict) else row[0]) if row else None

    def get_or_create_user_document(
        self,
        *,
        user_id: str,
        filename: str,
        original_filename: str,
        content_hash: str,
        doc_type: str = "cv",
        file_size: int = 0,
        label: Optional[str] = None,
        skills_count: int = 0,
        skills_json: Optional[List[str]] = None,
        years_experience: Optional[float] = None,
        current_role: Optional[str] = None,
        is_primary: bool = False,
    ) -> Dict[str, Any]:
        """Atomic get-or-create keyed by (user_id, doc_type, content_hash).

        Returns ``{"id", "filename", "doc_type", "is_primary", "inserted"}``.

        ``inserted=False`` means a row with this exact hash already existed —
        either because a caller-side pre-check missed it, or because this
        call itself found one. In both cases the response reflects the
        EXISTING row's canonical filename/id, never the just-uploaded
        filename, so the caller can't report metadata that doesn't match what
        is actually stored. No new row is created on a duplicate.

        A concurrent identical upload — TWO calls with the exact same
        (user_id, doc_type, content_hash), is_primary or not — is a NORMAL,
        expected outcome (double-click, client retry), never an error: this
        method never raises for it. Every call acquires
        `_lock_content_slot(user_id, doc_type, content_hash)` first, so the
        duplicate check-then-insert sequence below is race-free for ALL
        uploads, not only primary ones. When ``is_primary``,
        `_lock_primary_slot(user_id, doc_type)` is acquired SECOND — this
        fixed order (content lock, then primary lock) is used everywhere in
        this class so two transactions can never deadlock by acquiring the
        two different lock keys in opposite order. Holding both means it's
        safe to clear the old primary BEFORE inserting the new one (required
        by the non-deferrable partial unique index
        `uq_user_documents_one_primary_per_type` — see `save_user_document`'s
        docstring): nothing else can insert a conflicting content_hash row or
        touch is_primary for this (user_id, doc_type) while we hold both.

        The `ON CONFLICT DO NOTHING` insert is still handled gracefully even
        though the lock above should make it unreachable for a genuine race —
        defense in depth for the same class of edge case `save_user_document`
        already guards (e.g. a legacy pre-lock duplicate). On that path, if
        is_primary was requested and the row we find isn't already primary,
        it's promoted in the same transaction — never let this method commit
        having cleared the old primary with nothing to replace it.

        Requires migration 037 (content_hash column + partial unique indexes)
        to already be applied — see migrations/037_user_documents_content_hash.sql.
        """
        with self._transaction() as conn:
            with conn.cursor() as cur:
                # Fixed lock order everywhere: content lock, then (if
                # requested) primary lock — see docstring.
                self._lock_content_slot(cur, user_id, doc_type, content_hash)
                if is_primary:
                    self._lock_primary_slot(cur, user_id, doc_type)

                # Validate/check the target WITHOUT mutating anything yet.
                cur.execute(
                    """
                    SELECT id, filename, doc_type, is_primary
                      FROM user_documents
                     WHERE user_id = %s AND doc_type = %s AND content_hash = %s
                     LIMIT 1
                    """,
                    (user_id, doc_type, content_hash),
                )
                existing = cur.fetchone()
                if existing is not None:
                    return self._promote_if_requested(
                        cur, existing, user_id=user_id, doc_type=doc_type, is_primary=is_primary
                    )

                if is_primary:
                    # Clear the old primary BEFORE inserting the new one — see
                    # docstring. Safe under the lock: no concurrent writer can
                    # have inserted a matching row since our check above.
                    cur.execute(
                        """
                        UPDATE user_documents SET is_primary = FALSE, updated_at = now()
                         WHERE user_id = %s AND doc_type = %s AND is_primary = TRUE
                        """,
                        (user_id, doc_type),
                    )

                cur.execute(
                    """
                    INSERT INTO user_documents
                        (user_id, filename, original_filename, doc_type, file_size,
                         label, is_primary, skills_count, skills_json,
                         years_experience, "current_role", content_hash)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, doc_type, content_hash)
                        WHERE content_hash IS NOT NULL
                        DO NOTHING
                    RETURNING id, filename, doc_type, is_primary
                    """,
                    (user_id, filename, original_filename, doc_type, file_size,
                     label, is_primary, skills_count, Json(skills_json or []),
                     years_experience, current_role, content_hash),
                )
                row = cur.fetchone()
                if row is not None:
                    return self._document_row_to_dict(row, inserted=True)

                # A duplicate race even under the content lock — treat it as
                # the normal outcome it is, never an error. Re-fetch the
                # winner's canonical row.
                cur.execute(
                    """
                    SELECT id, filename, doc_type, is_primary
                      FROM user_documents
                     WHERE user_id = %s AND doc_type = %s AND content_hash = %s
                     LIMIT 1
                    """,
                    (user_id, doc_type, content_hash),
                )
                erow = cur.fetchone()
                if erow is None:
                    # Not a normal duplicate race (ON CONFLICT DO NOTHING
                    # implies a conflicting row exists) — genuinely anomalous.
                    # Let the transaction roll back rather than fabricate a
                    # document that isn't there.
                    raise RuntimeError(
                        "get_or_create_user_document: insert conflicted but no "
                        "matching row could be found"
                    )
                return self._promote_if_requested(
                    cur, erow, user_id=user_id, doc_type=doc_type, is_primary=is_primary
                )

    def list_user_documents(self, user_id: str) -> List[Dict[str, Any]]:
        """Return all documents for a user, newest first."""
        with self._transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, user_id, filename, original_filename, doc_type,
                           file_size, label, is_primary,
                           skills_count, skills_json, years_experience, "current_role",
                           created_at, updated_at
                    FROM user_documents
                    WHERE user_id = %s
                    ORDER BY is_primary DESC, created_at DESC
                    """,
                    (user_id,),
                )
                rows = cur.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["id"] = str(d["id"])
            if d.get("created_at"):
                d["created_at"] = d["created_at"].isoformat()
            if d.get("updated_at"):
                d["updated_at"] = d["updated_at"].isoformat()
            if d.get("years_experience") is not None:
                d["years_experience"] = int(float(d["years_experience"]))
            result.append(d)
        return result

    def get_primary_document(self, user_id: str, doc_type: str = "cv") -> Optional[Dict[str, Any]]:
        """Return the primary document of given type, or None."""
        with self._transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, user_id, filename, original_filename, doc_type,
                           file_size, label, is_primary,
                           skills_count, skills_json, years_experience, "current_role",
                           created_at, updated_at
                    FROM user_documents
                    WHERE user_id = %s AND doc_type = %s AND is_primary = TRUE
                    LIMIT 1
                    """,
                    (user_id, doc_type),
                )
                row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["id"] = str(d["id"])
        if d.get("created_at"):
            d["created_at"] = d["created_at"].isoformat()
        if d.get("updated_at"):
            d["updated_at"] = d["updated_at"].isoformat()
        if d.get("years_experience") is not None:
            d["years_experience"] = int(float(d["years_experience"]))
        return d


    def delete_user_document(self, user_id: str, doc_id: str) -> bool:
        """Delete a document. Returns True if a row was deleted."""
        with self._transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM user_documents WHERE id = %s AND user_id = %s RETURNING id",
                    (doc_id, user_id),
                )
                row = cur.fetchone()
        return row is not None

    def clear_cv_grounding(self, user_id: str) -> bool:
        """Remove the CV grounding derived from an uploaded CV (privacy, #1083).

        Clears the raw extracted text and file record that ground matching/chat,
        plus the JSONB keys that would otherwise resurrect an *undeletable*
        synthetic 'profile-cv' card: the ``cv_text`` / ``cv_file_url`` /
        ``cv_structured`` columns and the ``profile.cv_filename`` /
        ``profile.cv_extracted_at`` keys. Structured profile facts (skills,
        experience, current role) are intentionally retained — they are the
        user's editable profile, cleared separately in Settings. Returns True if
        a profile row was updated.
        """
        bundle = self.get_user_bundle(user_id)
        if not bundle:
            return False
        db_user_id = str(bundle["id"])
        with self._transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE rico_profiles
                    SET cv_text = NULL,
                        cv_file_url = NULL,
                        cv_structured = '{}'::jsonb,
                        profile = (profile - 'cv_filename' - 'cv_extracted_at'),
                        updated_at = now()
                    WHERE user_id = %s
                    RETURNING user_id
                    """,
                    (db_user_id,),
                )
                row = cur.fetchone()
        return row is not None

    def update_user_document(
        self,
        user_id: str,
        doc_id: str,
        *,
        label: Optional[str] = None,
        doc_type: Optional[str] = None,
    ) -> bool:
        """Update label and/or doc_type. Returns True if updated.

        Raises ``DocumentConflictError`` instead of letting an unhandled
        unique-violation surface as a 500 — e.g. retyping a document to a
        doc_type where a row with the same content_hash already exists for
        this user (uq_user_documents_user_type_hash), or a primary-flag
        collision (uq_user_documents_one_primary_per_type, migration 037).
        """
        updates: list[str] = ["updated_at = now()"]
        params: list[Any] = []
        if label is not None:
            updates.append("label = %s")
            params.append(label if label.strip() else None)
        if doc_type is not None:
            updates.append("doc_type = %s")
            params.append(doc_type)
        if len(updates) == 1:
            return False
        params.extend([doc_id, user_id])
        with self._transaction() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        f"UPDATE user_documents SET {', '.join(updates)} "
                        "WHERE id = %s AND user_id = %s RETURNING id",
                        params,
                    )
                except Exception as exc:
                    if _is_unique_violation(exc):
                        raise DocumentConflictError(
                            "A document of this type with identical content already exists."
                        ) from exc
                    raise
                row = cur.fetchone()
        return row is not None

    def set_primary_document(self, user_id: str, doc_id: str) -> bool:
        """Set one CV document as primary, clearing is_primary on all others.

        Runs under the same advisory lock as `save_user_document` /
        `get_or_create_user_document` (see `_lock_primary_slot`), and in an
        order that never leaves the user with zero primary documents AND
        never trips migration 037's non-deferrable partial unique index
        (`uq_user_documents_one_primary_per_type`): the target is validated
        FIRST with a plain SELECT (no flags touched), the whole transaction
        aborts with no side effects if it doesn't exist/isn't owned by this
        user/isn't a CV, THEN the old primary is cleared, and only THEN is
        the (already-validated) target set TRUE. That ordering means at no
        point do two rows carry is_primary=TRUE at once — inserting/updating
        a second TRUE row while the first still has it would violate the
        index immediately, since the index isn't deferrable.
        """
        with self._transaction() as conn:
            with conn.cursor() as cur:
                self._lock_primary_slot(cur, user_id, "cv")
                cur.execute(
                    "SELECT id FROM user_documents WHERE id = %s AND user_id = %s AND doc_type = 'cv'",
                    (doc_id, user_id),
                )
                if cur.fetchone() is None:
                    # Nothing matched — abort before touching any row so a
                    # bad doc_id can never wipe out the existing primary.
                    return False
                cur.execute(
                    """
                    UPDATE user_documents SET is_primary = FALSE, updated_at = now()
                     WHERE user_id = %s AND doc_type = 'cv' AND id <> %s AND is_primary = TRUE
                    """,
                    (user_id, doc_id),
                )
                cur.execute(
                    """
                    UPDATE user_documents SET is_primary = TRUE, updated_at = now()
                     WHERE id = %s AND user_id = %s AND doc_type = 'cv'
                    """,
                    (doc_id, user_id),
                )
        return True

    def register_webhook_event(
        self,
        *,
        provider: str,
        submission_id: str,
        form_id: Optional[str] = None,
        external_user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        conn=None,
    ) -> bool:
        """Atomically register a webhook delivery.

        Returns True only for the first delivery of a provider/submission_id pair.
        Returns False for duplicates. Safe against concurrent retries because
        PostgreSQL enforces the unique constraint.

        Pass ``conn`` to join a caller-owned transaction (e.g. the Jotform handler
        claims the submission in the SAME transaction as the user/profile/settings
        writes, so a failure rolls the claim back and the provider retry can
        immediately re-claim — #1089). When ``conn`` is omitted this opens, commits
        and closes its own connection exactly as before.
        """
        if not submission_id or submission_id == "?":
            return True
        should_close = conn is None
        if conn is None:
            conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO rico_webhook_events (provider, form_id, submission_id, external_user_id, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (provider, submission_id) DO NOTHING
                    RETURNING id
                    """,
                    (provider, form_id, submission_id, external_user_id, Json(metadata or {})),
                )
                row = cur.fetchone()
            if should_close:
                conn.commit()
            return row is not None
        except Exception:
            if should_close:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
        finally:
            if should_close:
                self._return_or_close(conn)

    def mark_webhook_event_processed(
        self,
        *,
        provider: str,
        submission_id: str,
        user_id: Optional[str] = None,
        status: str = "processed",
        metadata: Optional[Dict[str, Any]] = None,
        conn=None,
    ) -> None:
        """Set a webhook event's terminal status.

        Pass ``conn`` to run inside a caller-owned transaction (so the status is
        committed together with — or rolled back alongside — the writes it
        describes). When ``conn`` is omitted this opens/commits/closes its own
        connection exactly as before.
        """
        if not submission_id or submission_id == "?":
            return
        should_close = conn is None
        if conn is None:
            conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE rico_webhook_events
                    SET user_id = COALESCE(%s, user_id),
                        status = %s,
                        metadata = rico_webhook_events.metadata || %s,
                        processed_at = now()
                    WHERE provider = %s AND submission_id = %s
                    """,
                    (user_id, status, Json(metadata or {}), provider, submission_id),
                )
            if should_close:
                conn.commit()
        except Exception:
            if should_close:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
        finally:
            if should_close:
                self._return_or_close(conn)

    def upsert_user(self, payload: Dict[str, Any], conn=None) -> Dict[str, Any]:
        external_user_id = payload.get("external_user_id") or payload.get("email") or payload.get("telegram_username") or str(uuid.uuid4())

        should_close = conn is None
        if conn is None:
            conn = self.connect()

        try:
            with conn.cursor() as cur:
                notif_enabled = payload.get("telegram_notifications_enabled")
                cur.execute(
                    """
                    INSERT INTO rico_users (external_user_id, name, email, phone, telegram_username, telegram_chat_id, telegram_notifications_enabled, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (external_user_id) DO UPDATE SET
                        name = COALESCE(EXCLUDED.name, rico_users.name),
                        email = COALESCE(EXCLUDED.email, rico_users.email),
                        phone = COALESCE(EXCLUDED.phone, rico_users.phone),
                        telegram_username = COALESCE(EXCLUDED.telegram_username, rico_users.telegram_username),
                        telegram_chat_id = COALESCE(EXCLUDED.telegram_chat_id, rico_users.telegram_chat_id),
                        telegram_notifications_enabled = CASE
                            WHEN EXCLUDED.telegram_notifications_enabled IS NOT NULL
                            THEN EXCLUDED.telegram_notifications_enabled
                            ELSE rico_users.telegram_notifications_enabled
                        END,
                        updated_at = now()
                    RETURNING *
                    """,
                    (
                        external_user_id,
                        payload.get("name"),
                        payload.get("email"),
                        payload.get("phone"),
                        payload.get("telegram_username"),
                        payload.get("telegram_chat_id"),
                        notif_enabled,
                        payload.get("source", "rico"),
                    ),
                )
                row = dict(cur.fetchone())
            if should_close:
                conn.commit()
            return row
        except Exception:
            if should_close:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
        finally:
            if should_close:
                conn.close()

    def upsert_profile(self, user_id: str, profile: Dict[str, Any], cv_file_url: Optional[str] = None, cv_text: Optional[str] = None, cv_structured: Optional[Dict[str, Any]] = None, conn=None) -> Dict[str, Any]:
        should_close = conn is None
        if conn is None:
            conn = self.connect()

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO rico_profiles (user_id, profile, cv_file_url, cv_text, cv_structured)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        profile = rico_profiles.profile || EXCLUDED.profile,
                        cv_file_url = COALESCE(EXCLUDED.cv_file_url, rico_profiles.cv_file_url),
                        cv_text = COALESCE(EXCLUDED.cv_text, rico_profiles.cv_text),
                        cv_structured = rico_profiles.cv_structured || EXCLUDED.cv_structured,
                        updated_at = now()
                    RETURNING *
                    """,
                    (user_id, Json(profile), cv_file_url, cv_text, Json(cv_structured or {})),
                )
                row = dict(cur.fetchone())
            if should_close:
                conn.commit()
            return row
        except Exception:
            if should_close:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
        finally:
            if should_close:
                conn.close()

    def upsert_settings(self, user_id: str, settings: Dict[str, Any], conn=None) -> Dict[str, Any]:
        should_close = conn is None
        if conn is None:
            conn = self.connect()

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO rico_agent_settings (user_id, settings)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        settings = rico_agent_settings.settings || EXCLUDED.settings,
                        updated_at = now()
                    RETURNING *
                    """,
                    (user_id, Json(settings)),
                )
                row = dict(cur.fetchone())
            if should_close:
                conn.commit()
            return row
        except Exception:
            if should_close:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
        finally:
            if should_close:
                conn.close()

    def get_user_bundle(self, user_id: str, conn=None) -> Optional[Dict[str, Any]]:
        should_close = conn is None
        if conn is None:
            conn = self.connect()

        try:
            with conn.cursor() as cur:
                # For email-authenticated web users, apply canonical selection rule
                # For non-email identifiers (UUID, telegram_username), prefer exact match
                is_email = "@" in user_id
                if is_email:
                    cur.execute(
                        """
                        SELECT u.id, u.external_user_id, u.name, u.email, u.phone, u.telegram_username, u.telegram_chat_id, u.source, u.created_at, u.updated_at,
                               p.profile, p.cv_file_url, p.cv_text, p.cv_structured, s.settings
                        FROM rico_users u
                        LEFT JOIN rico_profiles p ON p.user_id = u.id
                        LEFT JOIN rico_agent_settings s ON s.user_id = u.id
                        WHERE LOWER(u.email) = LOWER(%s) OR LOWER(u.external_user_id) = LOWER(%s)
                        ORDER BY
                            -- 1. Prefer rows with the email stored in the email column.
                            CASE WHEN LOWER(u.email) = LOWER(%s) THEN 0 ELSE 1 END,
                            -- 2. Prefer rows where external_user_id != email (canonical UUID rows)
                            CASE WHEN LOWER(u.external_user_id) = LOWER(u.email) THEN 1 ELSE 0 END,
                            -- 3. Prefer UUID-like external_user_id
                            CASE WHEN u.external_user_id ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN 0 ELSE 1 END,
                            -- 4. Prefer row with existing profile
                            CASE WHEN p.id IS NOT NULL THEN 0 ELSE 1 END,
                            -- 5. Prefer most recently updated
                            u.updated_at DESC,
                            -- 6. Deterministic id tie-breaker
                            u.id ASC
                        LIMIT 1
                        """,
                        (user_id, user_id, user_id),
                    )
                else:
                    # Non-email identifiers: prefer exact match (id, external_user_id, telegram_username)
                    cur.execute(
                        """
                        SELECT u.id, u.external_user_id, u.name, u.email, u.phone, u.telegram_username, u.telegram_chat_id, u.source, u.created_at, u.updated_at,
                               p.profile, p.cv_file_url, p.cv_text, p.cv_structured, s.settings
                        FROM rico_users u
                        LEFT JOIN rico_profiles p ON p.user_id = u.id
                        LEFT JOIN rico_agent_settings s ON s.user_id = u.id
                        WHERE u.id::text = %s OR u.external_user_id = %s OR u.telegram_username = %s
                        ORDER BY
                            -- 1. Prefer exact id match
                            CASE WHEN u.id::text = %s THEN 0 ELSE 1 END,
                            -- 2. Prefer exact external_user_id match
                            CASE WHEN u.external_user_id = %s THEN 0 ELSE 1 END,
                            -- 3. Prefer exact telegram_username match
                            CASE WHEN u.telegram_username = %s THEN 0 ELSE 1 END,
                            -- 4. Prefer most recently updated
                            u.updated_at DESC,
                            -- 5. Deterministic id tie-breaker
                            u.id ASC
                        LIMIT 1
                        """,
                        (user_id, user_id, user_id, user_id, user_id, user_id),
                    )
                row = cur.fetchone()
            return dict(row) if row else None
        finally:
            if should_close:
                conn.close()

    _ALLOWED_CHAT_ROLES: frozenset = frozenset({"user", "assistant", "system"})

    def append_chat(self, user_id: str, role: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        if role not in self._ALLOWED_CHAT_ROLES:
            logger.warning("rico_db: append_chat rejected unknown role=%r user=%s", role, user_id)
            return
        with self._transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO rico_chat_history (user_id, role, message, metadata) VALUES (%s, %s, %s, %s)",
                    (user_id, role, message, Json(metadata or {})),
                )

    def record_signal(self, user_id: str, job_id: Optional[str], action: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        with self._transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO rico_learning_signals (user_id, job_id, action, metadata) VALUES (%s, %s, %s, %s)",
                    (user_id, job_id, action, Json(metadata or {})),
                )

    def save_recommendations(self, user_id: str, matches: List[Dict[str, Any]]) -> None:
        for item in matches:
            job = item.get("job") or item
            job_key = item.get("job_key") or job.get("id") or job.get("url") or job.get("job_url") or f"{job.get('title')}::{job.get('company')}"
            self.upsert_recommendation(
                user_id=user_id,
                job_key=job_key,
                job_data=job,
                status=item.get("status", "found"),
                score=item.get("rico_score") or item.get("score"),
                explanation=item.get("explanation") or item.get("rico_explanation"),
            )

    def get_recommendations(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        where_clauses = ["user_id = %s"]
        params: List[Any] = [user_id]
        if status:
            where_clauses.append("status = %s")
            params.append(status)
        where = " AND ".join(where_clauses)
        sql = (
            "SELECT job_key, job, repo_score, rico_score, explanation, status, created_at, updated_at "
            "FROM rico_job_recommendations "
            f"WHERE {where} "
            "ORDER BY updated_at DESC "
            "LIMIT %s OFFSET %s"
        )
        with self._transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params + [limit, offset])
                rows = cur.fetchall()
        return [self._shape_recommendation_row(r) for r in rows]

    @staticmethod
    def _shape_recommendation_row(r: Dict[str, Any]) -> Dict[str, Any]:
        job = dict(r["job"]) if isinstance(r["job"], dict) else {}
        return {
            "job_id": r["job_key"],
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "location": job.get("location", ""),
            "link": (
                job.get("link")
                or job.get("apply_url")
                or job.get("job_apply_link")
                or job.get("apply_link")
                or ""
            ),
            "apply_url": (
                job.get("apply_url")
                or job.get("job_apply_link")
                or job.get("apply_link")
                or job.get("link")
                or ""
            ),
            "score": r["rico_score"] or r["repo_score"] or 0,
            "status": r["status"],
            "notes": r["explanation"] or "",
            "date_applied": r["created_at"].isoformat() if r["created_at"] else None,
            "date_updated": r["updated_at"].isoformat() if r["updated_at"] else None,
        }

    # ── Canonical application set (#1092) ────────────────────────────────────
    #
    # (user_id, job_key) is unique (migrations 011/035), but several write
    # paths derive job_key independently, so the same real-world job can exist
    # under more than one job_key. The CANONICAL set collapses those physical
    # rows with ONE deterministic rule, applied identically to pages, totals,
    # stats, and quota counts so they can never disagree:
    #
    #   A row is canonical iff it is the newest (updated_at DESC, id DESC)
    #   within BOTH its location-identity group (title, company, location)
    #   and its url-identity group (title, company, apply-url). Rows with no
    #   title AND no company are always canonical; the url rule only applies
    #   when the row has a non-empty apply url. Chains of duplicates collapse
    #   to the single newest row.
    #
    # Pagination is a documented stable offset over (updated_at DESC, id DESC):
    # newest first with a unique tiebreak. A row inserted or touched between
    # page reads shifts later offsets, so a client may see an item REPEATED on
    # a subsequent page — items are never silently skipped by an insert.

    _CANONICAL_APPS_CTE = """
        WITH recs AS (
            SELECT id, job_key, job, repo_score, rico_score, explanation,
                   status, created_at, updated_at,
                   lower(btrim(coalesce(job->>'title', '')))    AS norm_title,
                   lower(btrim(coalesce(job->>'company', '')))  AS norm_company,
                   lower(btrim(coalesce(job->>'location', ''))) AS norm_location,
                   lower(btrim(coalesce(
                       nullif(job->>'apply_url', ''),
                       nullif(job->>'job_apply_link', ''),
                       nullif(job->>'apply_link', ''),
                       nullif(job->>'link', ''),
                       ''
                   ))) AS norm_url
            FROM rico_job_recommendations
            WHERE user_id = %s
        ),
        ranked AS (
            SELECT *,
                   CASE WHEN norm_title = '' AND norm_company = '' THEN 1
                        ELSE row_number() OVER (
                            PARTITION BY norm_title, norm_company, norm_location
                            ORDER BY updated_at DESC, id DESC)
                   END AS rn_location,
                   CASE WHEN norm_title = '' AND norm_company = '' THEN 1
                        WHEN norm_url = '' THEN 1
                        ELSE row_number() OVER (
                            PARTITION BY norm_title, norm_company, norm_url
                            ORDER BY updated_at DESC, id DESC)
                   END AS rn_url
            FROM recs
        ),
        canonical AS (
            SELECT * FROM ranked WHERE rn_location = 1 AND rn_url = 1
        )
    """

    def get_applications_page(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """One page of the canonical application set, newest first.

        ``limit=None`` returns the complete canonical set (no 200-row cap).
        """
        params: List[Any] = [user_id]
        where = ""
        if status:
            where = "WHERE status = %s"
            params.append(status)
        sql = (
            self._CANONICAL_APPS_CTE
            + f"SELECT * FROM canonical {where} "
            + "ORDER BY updated_at DESC, id DESC"
        )
        if limit is not None:
            sql += " LIMIT %s"
            params.append(limit)
        sql += " OFFSET %s"
        params.append(offset)
        with self._transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        return [self._shape_recommendation_row(r) for r in rows]

    def count_applications(self, user_id: str, status: Optional[str] = None) -> int:
        """Total logical applications in the canonical set (optionally by status)."""
        params: List[Any] = [user_id]
        where = ""
        if status:
            where = "WHERE status = %s"
            params.append(status)
        sql = self._CANONICAL_APPS_CTE + f"SELECT COUNT(*) AS cnt FROM canonical {where}"
        with self._transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
        return int(row["cnt"] if isinstance(row, dict) else row[0])

    def get_application_stats(self, user_id: str) -> Dict[str, Any]:
        """Status counts over the SAME canonical set the pages are served from."""
        sql = (
            self._CANONICAL_APPS_CTE
            + "SELECT status, COUNT(*) AS cnt FROM canonical GROUP BY status"
        )
        with self._transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (user_id,))
                rows = cur.fetchall()
        total = sum(r["cnt"] for r in rows)
        by_status = {r["status"]: r["cnt"] for r in rows}
        return {
            "total": total,
            "by_status": by_status,
            "applied": by_status.get("applied", 0),
            "saved": by_status.get("saved", 0),
            "interview": by_status.get("interview", 0),
            "rejected": by_status.get("rejected", 0),
            "offer": by_status.get("offer", 0),
            "follow_up_due": by_status.get("follow_up_due", 0),
        }

    def find_recommendation(self, user_id: str, job_key: str) -> Optional[Dict[str, Any]]:
        """Fetch ONE owned row directly by job_key — no page scan, no row cap.

        Queries the physical row: every stored job_key stays directly
        addressable for PATCH even when the canonical view collapses it as a
        duplicate for listing purposes.
        """
        with self._transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, job_key, job, repo_score, rico_score, explanation,
                           status, created_at, updated_at
                    FROM rico_job_recommendations
                    WHERE user_id = %s AND job_key = %s
                    LIMIT 1
                    """,
                    (user_id, job_key),
                )
                row = cur.fetchone()
        return self._shape_recommendation_row(row) if row else None

    def upsert_recommendation(
        self,
        user_id: str,
        job_key: str,
        job_data: Dict[str, Any],
        status: str,
        score: Optional[int] = None,
        explanation: Optional[str] = None,
    ) -> bool:
        """Insert or update a recommendation row atomically via ON CONFLICT."""
        with self._transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO rico_job_recommendations
                        (user_id, job_key, job, rico_score, explanation, status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, job_key) WHERE job_key IS NOT NULL
                    DO UPDATE SET
                        status      = EXCLUDED.status,
                        rico_score  = COALESCE(EXCLUDED.rico_score, rico_job_recommendations.rico_score),
                        explanation = COALESCE(EXCLUDED.explanation, rico_job_recommendations.explanation),
                        updated_at  = now()
                    """,
                    (user_id, job_key, Json(job_data), score, explanation, status),
                )
        self._stamp_status_timestamp(user_id, job_key, status)
        return True

    def update_recommendation_status(
        self,
        user_id: str,
        job_key: str,
        status: str,
        notes: Optional[str] = None,
    ) -> bool:
        with self._transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE rico_job_recommendations
                    SET status = %s, updated_at = now()
                    WHERE user_id = %s AND job_key = %s
                    """,
                    (status, user_id, job_key),
                )
                affected = cur.rowcount
        if affected > 0:
            self._stamp_status_timestamp(user_id, job_key, status)
        return affected > 0

    def _stamp_status_timestamp(self, user_id: str, job_key: str, status: str) -> None:
        """Best-effort: record the first time a row reaches a lifecycle stage.

        Stamps ``applied_at`` / ``follow_up_due_at`` the first time a row reaches
        that status (Issue #355). Runs in its own transaction and swallows all
        errors so a missing column (pre-migration 027) or any DB hiccup never
        affects the core recommendation write. ``column`` is from a fixed
        whitelist, never user input.
        """
        column = {"applied": "applied_at", "follow_up_due": "follow_up_due_at"}.get(status)
        if not column:
            return
        try:
            with self._transaction() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        UPDATE rico_job_recommendations
                        SET {column} = now()
                        WHERE user_id = %s AND job_key = %s AND {column} IS NULL
                        """,
                        (user_id, job_key),
                    )
        except Exception:
            logger.debug(
                "rico_db: skipped %s stamp (column may pre-date migration 027) user=%s job=%s",
                column, user_id, job_key,
            )

    def delete_saved_jobs(self, user_id: str) -> int:
        """Delete all rows with status='saved' for the user.

        Application history (status='applied', 'interview', etc.) is deliberately
        excluded — those records must never be deleted through the chat interface.
        Returns the number of rows deleted.
        """
        with self._transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM rico_job_recommendations WHERE user_id = %s AND status = 'saved'",
                    (user_id,),
                )
                return cur.rowcount or 0

    def archive_all_applications(self, user_id: str) -> int:
        """Reversibly archive all of the user's active tracked applications.

        Sets ``status = 'archived'`` (the canonical archived lifecycle status,
        see src/job_lifecycle.py) on every row for this user that is not already
        archived. This is REVERSIBLE — no row is deleted, only its status
        changes, so the records can be restored later. Idempotent: rows already
        at ``archived`` are excluded, so re-running archives nothing and returns
        0. Scoped to the single ``user_id`` (per-user isolation). Returns the
        number of rows newly archived.
        """
        with self._transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE rico_job_recommendations
                    SET status = 'archived', updated_at = now()
                    WHERE user_id = %s AND status <> 'archived'
                    """,
                    (user_id,),
                )
                return cur.rowcount or 0

    def mark_followups_due(self, interval_days: int = 7) -> int:
        """Transition aged ``applied`` jobs to ``follow_up_due`` (Issue #355).

        Idempotent: only rows currently at status='applied' whose ``applied_at``
        is older than ``interval_days`` are transitioned, so re-running the sweep
        produces no duplicate transitions. Returns the number of rows updated.
        """
        days = max(1, int(interval_days))
        with self._transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE rico_job_recommendations
                    SET status = 'follow_up_due',
                        follow_up_due_at = now(),
                        updated_at = now()
                    WHERE status = 'applied'
                      AND applied_at IS NOT NULL
                      AND applied_at <= now() - make_interval(days => %s)
                    """,
                    (days,),
                )
                return cur.rowcount or 0

    def get_recommendation_stats(self, user_id: str) -> Dict[str, Any]:
        with self._transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT status, COUNT(*) AS cnt
                    FROM rico_job_recommendations
                    WHERE user_id = %s
                    GROUP BY status
                    """,
                    (user_id,),
                )
                rows = cur.fetchall()
        total = sum(r["cnt"] for r in rows)
        by_status = {r["status"]: r["cnt"] for r in rows}
        return {
            "total": total,
            "by_status": by_status,
            "applied": by_status.get("applied", 0),
            "saved": by_status.get("saved", 0),
            "interview": by_status.get("interview", 0),
            "rejected": by_status.get("rejected", 0),
            "offer": by_status.get("offer", 0),
            "follow_up_due": by_status.get("follow_up_due", 0),
        }


    def get_users_with_active_telegram_notifications(self) -> list[dict]:
        """Return users who have a chat_id bound and notifications enabled."""
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT external_user_id, telegram_chat_id, telegram_username
                    FROM rico_users
                    WHERE telegram_chat_id IS NOT NULL
                      AND (telegram_notifications_enabled IS NULL OR telegram_notifications_enabled = TRUE)
                    """,
                )
                return [dict(row) for row in cur.fetchall()]
        except Exception:
            return []
        finally:
            conn.close()

    def log_telegram_alert(self, user_id: str, job_key: str, alert_type: str = "job_match") -> bool:
        """Record that this alert was sent. Returns True if newly inserted (not duplicate)."""
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO telegram_alert_log (user_id, job_key, alert_type)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, job_key, alert_type) DO NOTHING
                    """,
                    (user_id, job_key, alert_type),
                )
                inserted = cur.rowcount > 0
            conn.commit()
            return inserted
        except Exception:
            conn.rollback()
            return False
        finally:
            conn.close()

    def was_alert_sent(self, user_id: str, job_key: str, alert_type: str = "job_match") -> bool:
        """Check if this (user, job, type) combination was already sent."""
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM telegram_alert_log WHERE user_id=%s AND job_key=%s AND alert_type=%s",
                    (user_id, job_key, alert_type),
                )
                return cur.fetchone() is not None
        except Exception:
            return False
        finally:
            conn.close()

    def count_alerts_today(self, user_id: str, alert_type: str = "job_match") -> int:
        """Count how many alerts of this type were sent today for rate-limiting."""
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) AS cnt FROM telegram_alert_log
                    WHERE user_id = %s
                      AND alert_type = %s
                      AND sent_at >= NOW() - INTERVAL '24 hours'
                    """,
                    (user_id, alert_type),
                )
                row = cur.fetchone()
                return row["cnt"] if row else 0
        except Exception:
            return 0
        finally:
            conn.close()


    def create_application_draft(
        self,
        user_id: str,
        job_key: str,
        job_title: str,
        company: str,
        job_description: str,
        apply_url: str,
        tailored_cv: str,
        cover_letter: str,
        conn=None,
    ) -> Dict[str, Any]:
        should_close = conn is None
        if conn is None:
            conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO application_drafts
                        (user_id, job_key, job_title, company, job_description, apply_url, tailored_cv, cover_letter)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (user_id, job_key, job_title, company, job_description, apply_url, tailored_cv, cover_letter),
                )
                row = dict(cur.fetchone())
            if should_close:
                conn.commit()
            return row
        except Exception:
            if should_close:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
        finally:
            if should_close:
                conn.close()

    def get_application_drafts(
        self, user_id: str, status: str = "pending", conn=None
    ) -> List[Dict[str, Any]]:
        should_close = conn is None
        if conn is None:
            conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM application_drafts
                    WHERE user_id = %s AND status = %s
                    ORDER BY created_at DESC
                    """,
                    (user_id, status),
                )
                return [dict(r) for r in cur.fetchall()]
        finally:
            if should_close:
                conn.close()

    def update_draft_status(
        self, draft_id: str, user_id: str, status: str, conn=None
    ) -> bool:
        should_close = conn is None
        if conn is None:
            conn = self.connect()
        try:
            with conn.cursor() as cur:
                if status == "approved":
                    cur.execute(
                        """
                        UPDATE application_drafts
                        SET status = %s, updated_at = now(),
                            follow_up_at = now() + INTERVAL '7 days'
                        WHERE id = %s AND user_id = %s
                        RETURNING id
                        """,
                        (status, draft_id, user_id),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE application_drafts
                        SET status = %s, updated_at = now()
                        WHERE id = %s AND user_id = %s
                        RETURNING id
                        """,
                        (status, draft_id, user_id),
                    )
                updated = cur.fetchone() is not None
            if should_close:
                conn.commit()
            return updated
        except Exception:
            if should_close:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
        finally:
            if should_close:
                conn.close()

    def get_follow_up_drafts(self, user_id: str, conn=None) -> List[Dict[str, Any]]:
        """Return approved drafts where follow-up reminder is due (follow_up_at <= now())."""
        should_close = conn is None
        if conn is None:
            conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM application_drafts
                    WHERE user_id = %s AND status = 'approved'
                      AND follow_up_at IS NOT NULL AND follow_up_at <= now()
                    ORDER BY follow_up_at ASC
                    """,
                    (user_id,),
                )
                return [dict(r) for r in cur.fetchall()]
        finally:
            if should_close:
                conn.close()



def init_rico_db() -> bool:
    db = RicoDB()
    if not db.available:
        return False
    db.init()
    return True
