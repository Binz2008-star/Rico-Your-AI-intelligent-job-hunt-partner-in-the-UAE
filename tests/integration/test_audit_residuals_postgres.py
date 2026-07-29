"""Real-Postgres proof that the residual audit sees orphans.

The audit exists to find rows Delivery Smoke left behind. Its first draft
resolved synthetic emails through the ``users`` table and then looked for rows
belonging to that set — which inverts the whole point: cleanup deletes the
``users`` row, so the moment an orphan actually exists its parent is gone and
the audit reports zero. Mocked cursors cannot catch that; the query is wrong in
a way that only a real server, holding real orphan rows, demonstrates.

This applies the real table shapes to a disposable Postgres, deletes the parent
``users`` row exactly as Delivery cleanup does, and asserts the audit still
reports the surviving orphans — and, separately, that it refuses to claim a
provable zero for tables whose absence cannot be proven once the parent is gone.

Requires a real Postgres via RICO_TEST_DATABASE_URL (NOT the shared
DATABASE_URL). Skips cleanly when unset. In CI this is wired to the postgres
service container in .github/workflows/qa-tests.yml (job: postgres-integration).
"""
from __future__ import annotations

import importlib.util
import os
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
           "real-Postgres integration tests skipped.",
)

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "audit_delivery_smoke_residuals.py"

#: Emails inside the audited namespace. Distinct per run so repeated CI runs on
#: a reused database cannot collide.
_RUN = uuid.uuid4().hex[:8]
ORPHAN_EMAIL = f"smoke-delivery-{_RUN}@synthetic-rico.test"
OTHER_EMAIL = f"smoke-delivery-{_RUN}b@synthetic-rico.test"
#: A real-looking address that must never be counted.
REAL_EMAIL = f"real-person-{_RUN}@example.com"

#: Minimal shapes matching the production schema for the columns the audit uses.
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
-- No foreign key to users: this is exactly why orphans survive cleanup.
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
-- user_id holds the canonical email, exactly as production does.
CREATE TABLE IF NOT EXISTS chat_operations (
    operation_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- No parent to cascade from: the journey's most likely residual.
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


@pytest.fixture(scope="module")
def audit():
    os.environ["AUDIT_CONFIRM"] = "AUDIT-DELIVERY-RESIDUALS"
    os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)
    spec = importlib.util.spec_from_file_location("audit_mod", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def iso_url():
    """A private database on the same server.

    The audit resolves tables in ``public``, and this file needs minimal table
    shapes it fully controls. The shared CI database already holds the real
    migrated schemas from the other integration tests — `user_documents` there
    carries ``filename NOT NULL``, so a ``CREATE TABLE IF NOT EXISTS`` here is a
    no-op and the seed INSERTs fail. Owning a whole database removes the
    coupling in both directions: this test cannot be broken by another file's
    schema, and cannot leave rows where another file would count them.
    """
    import urllib.parse as _url

    name = f"rico_audit_test_{_RUN}"
    admin = psycopg2.connect(TEST_DATABASE_URL)
    admin.autocommit = True  # CREATE DATABASE cannot run inside a transaction
    with admin.cursor() as cur:
        cur.execute(f'CREATE DATABASE "{name}"')
    admin.close()

    parts = _url.urlsplit(TEST_DATABASE_URL)
    yield _url.urlunsplit((parts.scheme, parts.netloc, f"/{name}", parts.query, parts.fragment))

    admin = psycopg2.connect(TEST_DATABASE_URL)
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s", (name,)
        )
        cur.execute(f'DROP DATABASE IF EXISTS "{name}"')
    admin.close()


@pytest.fixture(scope="module")
def seeded(audit, iso_url):
    """Reproduce the post-cleanup state: parent deleted, orphans surviving."""
    conn = psycopg2.connect(iso_url)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(_SCHEMA)

        # A synthetic account that Delivery cleanup fully removed.
        cur.execute("INSERT INTO users (email) VALUES (%s)", (ORPHAN_EMAIL,))
        # Its email-keyed rows, which cleanup never touched.
        cur.execute("INSERT INTO rico_onboarding_states (user_id) VALUES (%s)", (ORPHAN_EMAIL,))
        cur.execute("INSERT INTO learning_signals (canonical_user_id) VALUES (%s)", (ORPHAN_EMAIL,))
        cur.execute("INSERT INTO user_documents (user_id) VALUES (%s)", (ORPHAN_EMAIL,))
        cur.execute("INSERT INTO email_verification_tokens (user_email) VALUES (%s)", (ORPHAN_EMAIL,))
        # Both keyed on the canonical email in production, and both left behind
        # by the smoke's cleanup — chat_operations because that cleanup matches
        # on row ids, user_job_context because nothing deletes it at all.
        cur.execute(
            "INSERT INTO chat_operations (operation_id, user_id) VALUES (%s, %s)",
            (f"op-{_RUN}", ORPHAN_EMAIL),
        )
        cur.execute("INSERT INTO user_job_context (user_id) VALUES (%s)", (ORPHAN_EMAIL,))
        # Now delete the parent, exactly as delivery_smoke.py does.
        cur.execute("DELETE FROM users WHERE email = %s", (ORPHAN_EMAIL,))

        # A second synthetic account whose rico identity survived (the real
        # delivery bug), so the child tables have something resolvable.
        cur.execute(
            "INSERT INTO rico_users (external_user_id, email) VALUES (%s, %s) RETURNING id",
            (OTHER_EMAIL, OTHER_EMAIL),
        )
        rico_id = cur.fetchone()[0]
        cur.execute("INSERT INTO rico_profiles (user_id) VALUES (%s)", (rico_id,))
        cur.execute("INSERT INTO rico_chat_history (user_id) VALUES (%s)", (rico_id,))
        cur.execute("INSERT INTO rico_job_recommendations (user_id) VALUES (%s)", (rico_id,))

        # A real user with rows that must never be counted.
        cur.execute("INSERT INTO users (email) VALUES (%s)", (REAL_EMAIL,))
        cur.execute("INSERT INTO rico_onboarding_states (user_id) VALUES (%s)", (REAL_EMAIL,))
        cur.execute("INSERT INTO learning_signals (canonical_user_id) VALUES (%s)", (REAL_EMAIL,))
    conn.close()

    ro = psycopg2.connect(iso_url)
    ro.set_session(readonly=True, autocommit=False)
    rows = {r["table"]: r for r in audit.run_audit(ro)}
    ro.close()
    return rows


def test_parent_user_row_is_really_gone(seeded):
    """Guard the premise: if the parent survived, the test proves nothing."""
    assert seeded["users"]["synthetic_row_count"] == 0
    assert seeded["users"]["status"] == "VERIFIED ZERO RESIDUALS"


@pytest.mark.parametrize(
    "table",
    ["rico_onboarding_states", "learning_signals", "user_documents",
     "email_verification_tokens", "chat_operations", "user_job_context"],
)
def test_email_keyed_orphans_are_reported_after_the_parent_is_deleted(seeded, table):
    """The regression: these must NOT be invisible just because users is empty."""
    row = seeded[table]
    assert row["synthetic_row_count"] >= 1, (
        f"{table} orphan went undetected — the audit resolved through users again"
    )
    assert row["status"] == "VERIFIED RESIDUALS PRESENT"


@pytest.mark.parametrize(
    ("table", "key_col"),
    [
        ("rico_onboarding_states", "user_id"),
        ("learning_signals", "canonical_user_id"),
        ("user_documents", "user_id"),
        ("email_verification_tokens", "user_email"),
        ("chat_operations", "user_id"),
        ("user_job_context", "user_id"),
    ],
)
def test_count_is_exactly_the_namespace_and_nothing_else(seeded, audit, iso_url, table, key_col):
    """The filter must cover the whole synthetic namespace and no real address.

    Compared against an independently computed count rather than a hardcoded
    number, so the assertion holds even when other tests share the container.
    """
    conn = psycopg2.connect(iso_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {key_col} LIKE %s",  # noqa: S608 - test-local literals
                (audit.PATTERN,),
            )
            expected = cur.fetchone()[0]
            cur.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {key_col} = %s",  # noqa: S608
                (REAL_EMAIL,),
            )
            real_rows = cur.fetchone()[0]
            # The decisive check: does the real address fall inside the pattern?
            cur.execute(
                f"SELECT COUNT(*) FROM {table} "  # noqa: S608
                f"WHERE {key_col} = %s AND {key_col} LIKE %s",
                (REAL_EMAIL, audit.PATTERN),
            )
            real_rows_inside_namespace = cur.fetchone()[0]
    finally:
        conn.close()

    assert seeded[table]["synthetic_row_count"] == expected
    if table in ("rico_onboarding_states", "learning_signals"):
        # The real account really is present, and really is outside the filter.
        assert real_rows == 1
        assert real_rows_inside_namespace == 0


def test_child_tables_resolve_through_the_surviving_rico_identity(seeded):
    assert seeded["rico_profiles"]["synthetic_row_count"] >= 1
    assert seeded["rico_chat_history"]["synthetic_row_count"] >= 1
    assert seeded["rico_job_recommendations"]["synthetic_row_count"] >= 1


def test_email_keyed_predicates_never_depend_on_the_users_table(audit):
    """Structural guard against reintroducing the resolve-through-users flaw."""
    for table, key_col, mode, _ in audit.TABLES:
        if mode not in ("email_direct", "rico_self"):
            continue
        predicate = audit.build_predicate(key_col, mode)
        assert "users" not in predicate.lower(), (
            f"{table} would become invisible once its parent row is deleted"
        )
        assert "select" not in predicate.lower()


def test_zero_is_not_claimed_provable_for_opaque_parent_ids(audit, seeded, iso_url):
    """chat_operations keys on a parent id that is unrecoverable once deleted."""
    conn = psycopg2.connect(iso_url)
    conn.set_session(readonly=True, autocommit=False)
    try:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            assert audit.zero_is_provable(cur, "chat_operations", "user_id", "text_id_child") is False
            # Children with a real ON DELETE CASCADE FK can prove zero.
            assert audit.zero_is_provable(cur, "rico_profiles", "user_id", "uuid_child") is True
    finally:
        conn.rollback()
        conn.close()
