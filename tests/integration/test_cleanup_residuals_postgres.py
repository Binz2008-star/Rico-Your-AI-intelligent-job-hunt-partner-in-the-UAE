"""Real-Postgres proof that the cleanup script is fail-closed and deletes exactly the namespace.

Requires a real Postgres via RICO_TEST_DATABASE_URL. Skips cleanly when unset.
"""
from __future__ import annotations

import importlib.util
import os
import urllib.parse as _url
import uuid
from pathlib import Path

import pytest

try:
    import psycopg2
except Exception:  # pragma: no cover
    psycopg2 = None

TEST_DATABASE_URL = os.environ.get("RICO_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL or psycopg2 is None,
    reason="RICO_TEST_DATABASE_URL not set (or psycopg2 unavailable) — "
           "real-Postgres cleanup integration tests skipped.",
)

def _load_cleanup_module():
    script = Path(__file__).resolve().parents[2] / "scripts" / "cleanup_delivery_smoke_residuals.py"
    spec = importlib.util.spec_from_file_location("cleanup_mod", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_RUN = uuid.uuid4().hex[:8]

# Load the cleanup module once with its confirmation gates armed.
os.environ["AUDIT_CONFIRM"] = "AUDIT-DELIVERY-RESIDUALS"
os.environ["CLEANUP_CONFIRM"] = "CLEANUP-DELIVERY-RESIDUALS"
CLEANUP_MOD = _load_cleanup_module()

# Reuse the minimal schema from the audit integration test; the cleanup only
# needs the same key columns and ON DELETE CASCADE contract.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS rico_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_user_id TEXT UNIQUE,
    email TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS rico_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES rico_users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS rico_chat_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES rico_users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS rico_onboarding_states (
    user_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'completed',
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS learning_signals (
    id SERIAL PRIMARY KEY,
    canonical_user_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS user_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS email_verification_tokens (
    id SERIAL PRIMARY KEY,
    user_email TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS chat_operations (
    operation_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS user_job_context (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    searched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS rico_job_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES rico_users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""


def _namespace_email(i: int) -> str:
    return f"smoke-delivery-{_RUN}-{i}@synthetic-rico.test"


@pytest.fixture(scope="module")
def cleanup_mod():
    yield CLEANUP_MOD
    os.environ.pop("CLEANUP_CONFIRM", None)
    os.environ.pop("AUDIT_CONFIRM", None)


@pytest.fixture(scope="module")
def iso_url():
    name = f"rico_cleanup_test_{_RUN}"
    admin = psycopg2.connect(TEST_DATABASE_URL)
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(f'CREATE DATABASE "{name}"')
    admin.close()

    parts = _url.urlsplit(TEST_DATABASE_URL)
    url = _url.urlunsplit((parts.scheme, parts.netloc, f"/{name}", parts.query, parts.fragment))
    os.environ["DATABASE_URL"] = url
    yield url

    admin = psycopg2.connect(TEST_DATABASE_URL)
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s", (name,)
        )
        cur.execute(f'DROP DATABASE IF EXISTS "{name}"')
    admin.close()
    os.environ.pop("DATABASE_URL", None)


@pytest.fixture(scope="module")
def seeded(iso_url):
    conn = psycopg2.connect(iso_url)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(_SCHEMA)

        # 8 synthetic rico_users (the audit expects 8 distinct users here).
        rico_ids = []
        for i in range(8):
            email = _namespace_email(i)
            cur.execute(
                "INSERT INTO rico_users (external_user_id, email) VALUES (%s, %s) RETURNING id",
                (email, email),
            )
            rico_ids.append(cur.fetchone()[0])

        # 48 chat_history rows across 8 users.
        for idx, rico_id in enumerate(rico_ids):
            for _ in range(6):
                cur.execute("INSERT INTO rico_chat_history (user_id) VALUES (%s)", (rico_id,))

        # 4 profiles across the first 4 users.
        for rico_id in rico_ids[:4]:
            cur.execute("INSERT INTO rico_profiles (user_id) VALUES (%s)", (rico_id,))

        # 5 job recommendations for the first user.
        for _ in range(5):
            cur.execute(
                "INSERT INTO rico_job_recommendations (user_id) VALUES (%s)", (rico_ids[0],)
            )

        # 8 onboarding states, one per synthetic email.
        for i in range(8):
            cur.execute(
                "INSERT INTO rico_onboarding_states (user_id) VALUES (%s)",
                (_namespace_email(i),),
            )

        # 3 chat_operations across the first 3 emails.
        for i in range(3):
            cur.execute(
                "INSERT INTO chat_operations (operation_id, user_id) VALUES (%s, %s)",
                (f"op-{_RUN}-{i}", _namespace_email(i)),
            )

        # learning_signals and user_job_context: 3 and 5 rows for the first email.
        for _ in range(3):
            cur.execute(
                "INSERT INTO learning_signals (canonical_user_id) VALUES (%s)",
                (_namespace_email(0),),
            )
        for _ in range(5):
            cur.execute(
                "INSERT INTO user_job_context (user_id) VALUES (%s)",
                (_namespace_email(0),),
            )

        # A real address outside the namespace that must survive every run.
        cur.execute("INSERT INTO users (email) VALUES (%s)", (f"real-person-{_RUN}@example.com",))
        cur.execute(
            "INSERT INTO rico_onboarding_states (user_id) VALUES (%s)",
            (f"real-person-{_RUN}@example.com",),
        )
    conn.close()
    return iso_url


def _count_all(cur) -> dict[str, int]:
    return {
        table: _count_table(cur, table, key_col, mode)
        for table, key_col, mode, _ in CLEANUP_MOD.TABLES
    }


def _count_table(cur, table, key_col, mode):
    predicate = CLEANUP_MOD.build_predicate(key_col, mode)
    cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {predicate}", {"pat": "smoke-delivery-%@synthetic-rico.test"})
    return int(cur.fetchone()[0])


def test_preflight_matches_expected_fingerprint(seeded, cleanup_mod):
    conn = psycopg2.connect(seeded)
    conn.set_session(readonly=True, autocommit=False)
    try:
        counts = cleanup_mod._preflight(conn)
    finally:
        conn.close()
    assert counts == cleanup_mod.EXPECTED_FINGERPRINT


def test_dry_run_leaves_rows_unchanged(seeded, cleanup_mod):
    before = _snapshot(seeded)
    report = cleanup_mod.run_cleanup(commit=False)
    after = _snapshot(seeded)

    assert report["outcome"] == "dry-run (rolled back)"
    assert report["total_deleted"] == 84
    assert before == after


def test_commit_deletes_only_namespace_and_postcheck_zero(seeded, cleanup_mod):
    # After dry_run above rows are still present.
    report = cleanup_mod.run_cleanup(commit=True)
    assert report["outcome"] == "committed"
    assert report["total_deleted"] == 84

    conn = psycopg2.connect(seeded)
    try:
        with conn.cursor() as cur:
            remaining = _count_all(cur)
            for table, count in remaining.items():
                assert count == 0, f"{table} still has {count} synthetic rows after commit"

            # Real row outside the namespace survives.
            cur.execute("SELECT COUNT(*) FROM users WHERE email = %s", (f"real-person-{_RUN}@example.com",))
            assert cur.fetchone()[0] == 1
            cur.execute(
                "SELECT COUNT(*) FROM rico_onboarding_states WHERE user_id = %s",
                (f"real-person-{_RUN}@example.com",),
            )
            assert cur.fetchone()[0] == 1
    finally:
        conn.close()


def _snapshot(url: str) -> dict[str, int]:
    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            return _count_all(cur)
    finally:
        conn.close()
