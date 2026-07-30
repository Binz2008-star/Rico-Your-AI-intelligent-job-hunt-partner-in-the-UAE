"""Atomic PendingJobSearch consume under concurrent access — real Postgres.

Proves that ``PendingJobSearchRepo.consume()`` with ``FOR UPDATE`` row lock
produces exactly one winner when two callers race on the same token.

Requires a real Postgres via ``RICO_TEST_DATABASE_URL``; skips cleanly when
unset.  Wired to the ``postgres-integration`` CI job.
"""
from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from src.services.pending_job_search import PendingJobSearchRepo, new_pending

try:
    import psycopg2
except Exception:
    psycopg2 = None

TEST_DATABASE_URL = os.environ.get("RICO_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL or psycopg2 is None,
    reason="RICO_TEST_DATABASE_URL not set (or psycopg2 unavailable) — skipped.",
)

_USER = "concurrency@test.com"
_PJS_KEY = "_pjs"


def _raw():
    return psycopg2.connect(TEST_DATABASE_URL)


@pytest.fixture(scope="module")
def _schema():
    """Ensure the rico_agent_settings table exists."""
    from src.rico_db import RicoDB
    db = RicoDB(database_url=TEST_DATABASE_URL)
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS rico_agent_settings (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID REFERENCES rico_users(id) ON DELETE CASCADE,
                    settings JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ DEFAULT now(),
                    updated_at TIMESTAMPTZ DEFAULT now(),
                    UNIQUE(user_id)
                );
            """)
        conn.commit()
    yield


@pytest.fixture(autouse=True)
def _cleanup(_schema, monkeypatch):
    """Set up a clean user and pending state before each test.

    We use direct SQL to insert a rico_users row and set the _pjs key
    in rico_agent_settings, then the test drives PendingJobSearchRepo.
    """
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    conn = _raw()
    try:
        with conn:
            with conn.cursor() as cur:
                # Clean slate for our test user
                cur.execute(
                    "DELETE FROM rico_agent_settings WHERE user_id IN "
                    "(SELECT id FROM rico_users WHERE email = %s)",
                    (_USER,),
                )
                cur.execute("DELETE FROM rico_users WHERE email = %s", (_USER,))
                # Create the test user row
                cur.execute(
                    "INSERT INTO rico_users (id, email) "
                    "VALUES (gen_random_uuid(), %s) RETURNING id",
                    (_USER,),
                )
                user_row = cur.fetchone()
                user_id = str(user_row["id"] if isinstance(user_row, dict) else user_row[0])
                # Pre-populate a pending job search in rico_agent_settings
                pjs = new_pending(role="Accountant", location="Dubai", reason="promise")
                cur.execute(
                    "INSERT INTO rico_agent_settings (user_id, settings) "
                    "VALUES (%s, %s::jsonb) "
                    "ON CONFLICT (user_id) DO UPDATE SET settings = EXCLUDED.settings",
                    (user_id, '{"' + _PJS_KEY + '": ' + psycopg2.extras.Json(pjs.to_dict()).adapted + '}'),
                )
                # Store the token for the test
                _cleanup._token = pjs.token
        yield
    finally:
        conn.close()


def test_atomic_consume_one_winner():
    """Two concurrent callers reading the same token — only one wins."""
    import json
    from src.rico_db import RicoDB

    # Resolve the DB user UUID
    db = RicoDB(database_url=TEST_DATABASE_URL)
    conn = _raw()
    db_user_id = None
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM rico_users WHERE email = %s", (_USER,))
                row = cur.fetchone()
                db_user_id = str(row["id"] if isinstance(row, dict) else row[0])
    finally:
        conn.close()

    assert db_user_id is not None, "Test user must exist"
    token = getattr(_cleanup, "_token", None)
    assert token is not None, "Pending job search must have a token"

    repo = PendingJobSearchRepo(db)

    def _attempt() -> bool:
        """One consumer attempt — returns True if it got the payload."""
        result = repo.consume(_USER, token)
        return result is not None

    # Launch two concurrent consumers
    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_attempt)
        f2 = pool.submit(_attempt)
        r1 = f1.result()
        r2 = f2.result()

    # Exactly one winner
    winner_count = sum([bool(r1), bool(r2)])
    assert winner_count == 1, f"Expected 1 winner, got {winner_count}"

    # The row must no longer contain _pjs
    conn2 = _raw()
    try:
        with conn2:
            with conn2.cursor() as cur:
                cur.execute(
                    "SELECT settings FROM rico_agent_settings WHERE user_id = %s",
                    (db_user_id,),
                )
                row = cur.fetchone()
        if row:
            settings = row["settings"] if isinstance(row, dict) else row[0]
            if settings and isinstance(settings, dict):
                assert _PJS_KEY not in settings, "_pjs must be removed after consume"
    finally:
        conn2.close()
