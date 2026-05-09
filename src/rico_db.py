"""Neon/PostgreSQL database layer for Rico AI.

Uses the same DATABASE_URL as the existing job automation system. This module
creates Rico-specific tables only when they do not already exist, so it can live
beside the current jobs/applications tables safely.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor, Json
except Exception:  # pragma: no cover - dependency may be installed by cloud later
    psycopg2 = None
    RealDictCursor = None
    Json = None


class RicoDB:
    """Thin PostgreSQL wrapper for Rico AI multi-user memory."""

    def __init__(self, database_url: Optional[str] = None) -> None:
        self.database_url = database_url or os.getenv("DATABASE_URL")

    @property
    def available(self) -> bool:
        return bool(self.database_url and psycopg2 is not None)

    def connect(self):
        if not self.available:
            raise RuntimeError("RicoDB unavailable: DATABASE_URL or psycopg2 missing")
        return psycopg2.connect(self.database_url, cursor_factory=RealDictCursor)

    def init(self) -> None:
        """Create Rico tables in the existing Neon database."""
        ddl = """
        CREATE EXTENSION IF NOT EXISTS pgcrypto;

        CREATE TABLE IF NOT EXISTS rico_users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            external_user_id TEXT UNIQUE,
            name TEXT,
            email TEXT,
            phone TEXT,
            telegram_username TEXT,
            telegram_chat_id TEXT,
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

        CREATE INDEX IF NOT EXISTS idx_rico_users_email ON rico_users(email);
        CREATE INDEX IF NOT EXISTS idx_rico_users_telegram ON rico_users(telegram_username);
        CREATE INDEX IF NOT EXISTS idx_rico_chat_user_created ON rico_chat_history(user_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_rico_signals_user_created ON rico_learning_signals(user_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_rico_recommendations_user_status ON rico_job_recommendations(user_id, status);
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
            conn.commit()

    def upsert_user(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        external_user_id = payload.get("external_user_id") or payload.get("email") or payload.get("telegram_username") or str(uuid.uuid4())
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO rico_users (external_user_id, name, email, phone, telegram_username, telegram_chat_id, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (external_user_id) DO UPDATE SET
                        name = COALESCE(EXCLUDED.name, rico_users.name),
                        email = COALESCE(EXCLUDED.email, rico_users.email),
                        phone = COALESCE(EXCLUDED.phone, rico_users.phone),
                        telegram_username = COALESCE(EXCLUDED.telegram_username, rico_users.telegram_username),
                        telegram_chat_id = COALESCE(EXCLUDED.telegram_chat_id, rico_users.telegram_chat_id),
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
                        payload.get("source", "rico"),
                    ),
                )
                row = dict(cur.fetchone())
            conn.commit()
        return row

    def upsert_profile(self, user_id: str, profile: Dict[str, Any], cv_file_url: Optional[str] = None, cv_text: Optional[str] = None, cv_structured: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self.connect() as conn:
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
            conn.commit()
        return row

    def upsert_settings(self, user_id: str, settings: Dict[str, Any]) -> Dict[str, Any]:
        with self.connect() as conn:
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
            conn.commit()
        return row

    def get_user_bundle(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT u.*, p.profile, p.cv_file_url, p.cv_text, p.cv_structured, s.settings
                    FROM rico_users u
                    LEFT JOIN rico_profiles p ON p.user_id = u.id
                    LEFT JOIN rico_agent_settings s ON s.user_id = u.id
                    WHERE u.id::text = %s OR u.external_user_id = %s OR u.email = %s OR u.telegram_username = %s
                    LIMIT 1
                    """,
                    (user_id, user_id, user_id, user_id),
                )
                row = cur.fetchone()
        return dict(row) if row else None

    def append_chat(self, user_id: str, role: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO rico_chat_history (user_id, role, message, metadata) VALUES (%s, %s, %s, %s)",
                    (user_id, role, message, Json(metadata or {})),
                )
            conn.commit()

    def record_signal(self, user_id: str, job_id: Optional[str], action: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO rico_learning_signals (user_id, job_id, action, metadata) VALUES (%s, %s, %s, %s)",
                    (user_id, job_id, action, Json(metadata or {})),
                )
            conn.commit()

    def save_recommendations(self, user_id: str, matches: List[Dict[str, Any]]) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                for item in matches:
                    job = item.get("job") or item
                    job_key = item.get("job_key") or job.get("id") or job.get("url") or job.get("job_url") or f"{job.get('title')}::{job.get('company')}"
                    cur.execute(
                        """
                        INSERT INTO rico_job_recommendations (user_id, job_key, job, repo_score, rico_score, explanation, status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            user_id,
                            job_key,
                            Json(job),
                            item.get("repo_score"),
                            item.get("rico_score") or item.get("score"),
                            item.get("explanation") or item.get("rico_explanation"),
                            item.get("status", "found"),
                        ),
                    )
            conn.commit()


def init_rico_db() -> bool:
    db = RicoDB()
    if not db.available:
        return False
    db.init()
    return True
