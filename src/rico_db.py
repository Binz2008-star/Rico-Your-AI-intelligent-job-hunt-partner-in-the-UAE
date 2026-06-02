"""Neon/PostgreSQL database layer for Rico AI.

Uses the same DATABASE_URL as the existing job automation system. This module
creates Rico-specific tables only when they do not already exist, so it can live
beside the current jobs/applications tables safely.
"""

from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime
from threading import Lock
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor, Json
except Exception:  # pragma: no cover - dependency may be installed by cloud later
    psycopg2 = None
    RealDictCursor = None
    Json = None


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
            conn.commit()
            self._schema_ready_urls.add(self.database_url)

    def connect(self, *, ensure_schema: bool = True):
        if not self.available:
            raise RuntimeError("RicoDB unavailable: DATABASE_URL or psycopg2 missing")
        conn = psycopg2.connect(self.database_url, cursor_factory=RealDictCursor, connect_timeout=5)
        if not ensure_schema:
            return conn
        try:
            self._ensure_schema(conn)
        except Exception:
            conn.close()
            raise
        return conn

    @contextmanager
    def _transaction(self, *, ensure_schema: bool = True):
        """Open a connection, yield it, commit on success, always close."""
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
            conn.close()

    def init(self) -> None:
        """Create Rico tables in the existing Neon database."""
        with self._transaction(ensure_schema=False) as conn:
            with conn.cursor() as cur:
                cur.execute(_RICO_SCHEMA_DDL)
        if self.database_url:
            self._schema_ready_urls.add(self.database_url)

    def register_webhook_event(
        self,
        *,
        provider: str,
        submission_id: str,
        form_id: Optional[str] = None,
        external_user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Atomically register a webhook delivery.

        Returns True only for the first delivery of a provider/submission_id pair.
        Returns False for duplicates. This is safe against concurrent retries
        because PostgreSQL enforces the unique constraint.
        """
        if not submission_id or submission_id == "?":
            return True
        with self._transaction() as conn:
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
        return row is not None

    def mark_webhook_event_processed(
        self,
        *,
        provider: str,
        submission_id: str,
        user_id: Optional[str] = None,
        status: str = "processed",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not submission_id or submission_id == "?":
            return
        with self._transaction() as conn:
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
                cur.execute(
                    """
                    SELECT u.id, u.external_user_id, u.name, u.email, u.phone, u.telegram_username, u.telegram_chat_id, u.source, u.created_at, u.updated_at,
                           p.profile, p.cv_file_url, p.cv_text, p.cv_structured, s.settings
                    FROM rico_users u
                    LEFT JOIN rico_profiles p ON p.user_id = u.id
                    LEFT JOIN rico_agent_settings s ON s.user_id = u.id
                    WHERE u.id::text = %s OR u.external_user_id = %s OR u.email = %s OR u.telegram_username = %s
                    ORDER BY
                        CASE WHEN u.external_user_id = %s THEN 0 ELSE 1 END,
                        CASE WHEN u.email = %s THEN 0 ELSE 1 END,
                        CASE WHEN u.telegram_username = %s THEN 0 ELSE 1 END,
                        u.updated_at DESC
                    LIMIT 1
                    """,
                    (user_id, user_id, user_id, user_id, user_id, user_id, user_id),
                )
                row = cur.fetchone()
            return dict(row) if row else None
        finally:
            if should_close:
                conn.close()

    def append_chat(self, user_id: str, role: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
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
        result: List[Dict[str, Any]] = []
        for r in rows:
            job = dict(r["job"]) if isinstance(r["job"], dict) else {}
            result.append({
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
            })
        return result

    def upsert_recommendation(
        self,
        user_id: str,
        job_key: str,
        job_data: Dict[str, Any],
        status: str,
        score: Optional[int] = None,
        explanation: Optional[str] = None,
    ) -> bool:
        """Insert or update a recommendation row. Uses SELECT+INSERT/UPDATE for
        portability since there is no UNIQUE(user_id, job_key) constraint yet."""
        with self._transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM rico_job_recommendations WHERE user_id = %s AND job_key = %s LIMIT 1",
                    (user_id, job_key),
                )
                row = cur.fetchone()
                if row:
                    cur.execute(
                        "UPDATE rico_job_recommendations SET status = %s, updated_at = now() WHERE user_id = %s AND job_key = %s",
                        (status, user_id, job_key),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO rico_job_recommendations
                            (user_id, job_key, job, rico_score, explanation, status)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (user_id, job_key, Json(job_data), score, explanation, status),
                    )
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
        return affected > 0

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


def init_rico_db() -> bool:
    db = RicoDB()
    if not db.available:
        return False
    db.init()
    return True
