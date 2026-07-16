"""
Jotform onboarding webhook — real-Postgres atomicity (#1089).

The handler claims the submission and writes user + profile + settings + the
'processed' status in ONE transaction (RicoDB._transaction). A required-persistence
failure therefore rolls the WHOLE thing back — including the idempotency claim —
leaving NO partial rows, and the provider retry can immediately re-claim the same
submission. No DELETE compensation and no lease.

Proves:
  * a mid-write failure leaves no claim row and no user row;
  * an immediate retry after rollback succeeds and marks 'processed';
  * a processed submission stays deduplicated (no double user row);
  * a terminal (missing-user) path commits its status exactly once.

Requires a real Postgres via RICO_TEST_DATABASE_URL; skips cleanly when unset.
Wired to the postgres-integration job in .github/workflows/qa-tests.yml.
"""
from __future__ import annotations

import os
import uuid
from unittest.mock import patch

import pytest

try:
    import psycopg2
except Exception:  # pragma: no cover
    psycopg2 = None

from src.rico_db import RicoDB

TEST_DATABASE_URL = os.environ.get("RICO_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL or psycopg2 is None,
    reason="RICO_TEST_DATABASE_URL not set (or psycopg2 unavailable) — skipped.",
)


@pytest.fixture(scope="module")
def _schema():
    RicoDB(database_url=TEST_DATABASE_URL).connect().close()  # ensure base schema
    yield


@pytest.fixture(autouse=True)
def _point_handler_at_test_db(_schema, monkeypatch):
    # handle_jotform_submission constructs RicoDB() internally (reads DATABASE_URL);
    # point it at the disposable test DB and ensure non-production form/secret rules.
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    for var in ("RICO_ENV", "ENV", "ENVIRONMENT", "JOTFORM_FORM_ID", "JOTFORM_RICO_FORM_ID", "JOTFORM_WEBHOOK_SECRET"):
        monkeypatch.delenv(var, raising=False)
    yield


def _raw():
    return psycopg2.connect(TEST_DATABASE_URL)


def _webhook_rows(sid):
    conn = _raw()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM rico_webhook_events WHERE provider='jotform' AND submission_id=%s",
                (sid,),
            )
            return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def _user_count(email):
    conn = _raw()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM rico_users WHERE email=%s", (email,))
            return int(cur.fetchone()[0])
    finally:
        conn.close()


def _cleanup(sid, email):
    conn = _raw()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rico_webhook_events WHERE submission_id=%s", (sid,))
            cur.execute("DELETE FROM rico_users WHERE email=%s", (email,))
        conn.commit()
    finally:
        conn.close()


def _sid():
    return "itest-jf-" + uuid.uuid4().hex[:16]


class TestJotformAtomicity:
    def test_write_failure_rolls_back_no_partial_rows(self):
        from src.rico_jotform_webhook import handle_jotform_submission

        sid = _sid()
        email = f"{sid}@example.com"
        payload = {"submissionID": sid, "email": email, "consent": True}
        try:
            with patch("src.rico_db.RicoDB.upsert_settings", side_effect=RuntimeError("settings boom")):
                with pytest.raises(RuntimeError, match="settings boom"):
                    handle_jotform_submission(payload)
            # The whole transaction rolled back: no claim row, no user row.
            assert _webhook_rows(sid) == []
            assert _user_count(email) == 0
        finally:
            _cleanup(sid, email)

    def test_retry_after_rollback_succeeds(self):
        from src.rico_jotform_webhook import handle_jotform_submission

        sid = _sid()
        email = f"{sid}@example.com"
        payload = {"submissionID": sid, "email": email, "consent": True}
        try:
            with patch("src.rico_db.RicoDB.upsert_profile", side_effect=RuntimeError("profile boom")):
                with pytest.raises(RuntimeError):
                    handle_jotform_submission(payload)
            assert _webhook_rows(sid) == []  # claim rolled back
            with patch("src.repositories.onboarding_repo.mark_onboarding_complete"):
                r = handle_jotform_submission(payload)  # immediate retry
            assert r["status"] == "ok"
            assert _webhook_rows(sid) == ["processed"]
            assert _user_count(email) == 1
        finally:
            _cleanup(sid, email)

    def test_processed_submission_deduplicated(self):
        from src.rico_jotform_webhook import handle_jotform_submission

        sid = _sid()
        email = f"{sid}@example.com"
        payload = {"submissionID": sid, "email": email, "consent": True}
        try:
            with patch("src.repositories.onboarding_repo.mark_onboarding_complete"):
                r1 = handle_jotform_submission(payload)
                r2 = handle_jotform_submission(payload)
            assert r1["status"] == "ok"
            assert r2["status"] == "ignored" and r2["reason"] == "duplicate"
            assert _webhook_rows(sid) == ["processed"]
            assert _user_count(email) == 1  # not double-inserted
        finally:
            _cleanup(sid, email)

    def test_missing_user_terminal_commits_status_once(self):
        from src.rico_jotform_webhook import handle_jotform_submission

        sid = _sid()
        payload = {"submissionID": sid, "full_name": "Ghost User"}  # no email/telegram
        try:
            r = handle_jotform_submission(payload)
            assert r["status"] == "accepted"
            rows = _webhook_rows(sid)
            assert len(rows) == 1  # committed exactly once
            assert rows[0] != "processing"  # a terminal status
        finally:
            _cleanup(sid, f"{sid}-noemail")
