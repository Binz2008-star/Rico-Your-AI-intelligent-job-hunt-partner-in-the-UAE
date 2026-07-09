"""Tests for the weekly admin activation digest (issue #922).

Covers:
  - Aggregation: verified/CV/roles/cities counts, synthetic exclusion,
    top-source ranking with "direct / unknown" fallback
  - Idempotency: the same ISO week is claimed once; reruns return
    already_sent and never email twice
  - dry_run computes metrics without claiming or sending
  - Kill-switch (RICO_ENABLE_ADMIN_DIGEST=false) and missing migration
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from src.services.admin_digest_service import run_weekly_admin_digest

NOW = datetime(2026, 7, 8, 9, 0, tzinfo=timezone.utc)  # Wednesday
# Previous ISO week: Mon 2026-06-29 → Mon 2026-07-06
EXPECTED_PERIOD_START = "2026-06-29"
EXPECTED_PERIOD_END = "2026-07-06"


def _signup_row(
    user_id: int,
    email: str,
    verified: bool = True,
    cv: str | None = None,
    roles: list | None = None,
    cities: list | None = None,
    source: str | None = None,
):
    return {
        "id": user_id,
        "email": email,
        "email_verified": verified,
        "cv_filename": cv,
        "target_roles": roles,
        "preferred_cities": cities,
        "signup_source": source,
    }


class FakeCursor:
    """RealDictCursor stand-in routing canned results by SQL shape."""

    def __init__(self, db):
        self.db = db
        self._result = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        sql_flat = " ".join(sql.split())
        if "information_schema.tables" in sql_flat:
            self._result = [{"?column?": 1}] if self.db.migration_applied else []
        elif "INSERT INTO admin_digest_log" in sql_flat:
            key = (params[0], params[1])  # (digest_type, period_start)
            if key in self.db.claimed:
                self._result = []
            else:
                self.db.claimed.add(key)
                self._result = [{"id": len(self.db.claimed)}]
        elif "profile_nudge_sent_at" in sql_flat:
            self._result = [{"n": self.db.nudge_stamps}]
        elif "FROM users u" in sql_flat:
            self._result = list(self.db.signup_rows)
        else:  # pragma: no cover - unexpected query
            raise AssertionError(f"unexpected SQL: {sql_flat}")

    def fetchone(self):
        return self._result[0] if self._result else None

    def fetchall(self):
        return list(self._result)


class FakeConn:
    def __init__(self, db):
        self.db = db

    def cursor(self):
        return FakeCursor(self.db)

    def commit(self):
        pass

    def close(self):
        pass


class FakeDB:
    available = True

    def __init__(self, signup_rows=None, nudge_stamps=2, migration_applied=True):
        self.signup_rows = signup_rows or []
        self.nudge_stamps = nudge_stamps
        self.migration_applied = migration_applied
        self.claimed = set()

    def connect(self, ensure_schema=True):
        return FakeConn(self)


@pytest.fixture()
def digest_env(monkeypatch):
    monkeypatch.setenv("RICO_ENABLE_ADMIN_DIGEST", "true")
    monkeypatch.setenv("ADMIN_SIGNUP_NOTIFICATION_EMAIL", "info@ricohunt.com")


def _run(db, sent_calls=None, dry_run=False):
    sent_calls = sent_calls if sent_calls is not None else []

    def fake_send_email(**kwargs):
        sent_calls.append(kwargs)
        return True

    with patch("src.rico_db.RicoDB", return_value=db), \
         patch("src.services.mailer.send_email", side_effect=fake_send_email):
        return run_weekly_admin_digest(dry_run=dry_run, now=NOW), sent_calls


class TestDigestAggregation:
    def test_metrics_and_top_sources(self, digest_env):
        db = FakeDB(signup_rows=[
            _signup_row(1, "reyaz@gmail.com", verified=True, cv="cv.pdf",
                        roles=["auditor"], cities=["Dubai"], source="google / cpc"),
            _signup_row(2, "sara@outlook.com", verified=False, source="google / cpc"),
            _signup_row(3, "ahmed@yahoo.com", verified=True, source=None),
            # Synthetic/internal — excluded from every metric:
            _signup_row(4, "test@gmail.com", verified=True, cv="cv.pdf", source="x"),
            _signup_row(5, "user_123@gmail.com", verified=True, source="y"),
            _signup_row(6, "admin@ricohunt.com", verified=True, source="z"),
        ], nudge_stamps=2)

        summary, sent = _run(db)

        assert summary["status"] == "ok"
        assert summary["sent"] is True
        assert summary["period_start"] == EXPECTED_PERIOD_START
        assert summary["period_end"] == EXPECTED_PERIOD_END
        m = summary["metrics"]
        assert m["signups"] == 3
        assert m["signups_synthetic_excluded"] == 3
        assert m["verified"] == 2
        assert m["cv_uploaded"] == 1
        assert m["target_roles_set"] == 1
        assert m["preferred_cities_set"] == 1
        assert m["nudges_stamped"] == 2
        assert m["top_sources"][0] == ("google / cpc", 2)
        assert ("direct / unknown", 1) in m["top_sources"]

        assert len(sent) == 1
        assert sent[0]["to_email"] == "info@ricohunt.com"
        body = sent[0]["body"]
        assert "Signups: 3 (3 synthetic/internal excluded)" in body
        assert "Email verified: 2/3 (66%)" in body
        assert "CV uploaded: 1/3 (33%)" in body
        assert "google / cpc — 2" in body
        # Aggregate-only: no signup emails leak into the digest body.
        assert "reyaz@gmail.com" not in body

    def test_zero_signups_week(self, digest_env):
        summary, sent = _run(FakeDB(signup_rows=[], nudge_stamps=0))
        assert summary["status"] == "ok"
        assert summary["metrics"]["signups"] == 0
        assert len(sent) == 1
        assert "no signups this week" in sent[0]["body"]


class TestNudgeMetricSemantics:
    """profile_nudge_sent_at is an idempotency stamp, not a delivery receipt.

    The nudge sweep also stamps (1) synthetic/internal skips, (2) complete-
    profile skips, and (3) stamps BEFORE sending, so a failed send stays
    stamped. The digest must therefore never present this count as emails
    sent — only as processed/stamped. These tests pin that wording so a
    future rename back to "sent" fails loudly.
    """

    def test_stamp_count_reported_as_processed_stamped_never_as_sent(self, digest_env):
        # 3 stamps in the window; in reality these could be one synthetic skip,
        # one complete-profile skip, and one failed-send-after-stamp — the
        # column cannot distinguish them, so the digest must not claim sends.
        db = FakeDB(signup_rows=[_signup_row(1, "reyaz@gmail.com")], nudge_stamps=3)
        summary, sent = _run(db)

        m = summary["metrics"]
        assert m["nudges_stamped"] == 3
        assert "nudges_sent" not in m  # old misleading key must stay gone

        body = sent[0]["body"]
        assert "Profile nudges processed/stamped this week: 3" in body
        assert "not confirmed email sends" in body
        assert "nudges sent" not in body.lower()

    def test_stamp_metric_absent_when_column_unavailable(self, digest_env):
        db = FakeDB(signup_rows=[], nudge_stamps=0)
        original_cursor = FakeCursor.execute

        def failing_nudge_query(self, sql, params=None):
            if "profile_nudge_sent_at" in sql:
                raise RuntimeError("column missing (migration 029 not applied)")
            return original_cursor(self, sql, params)

        with patch.object(FakeCursor, "execute", failing_nudge_query):
            summary, sent = _run(db)

        assert summary["metrics"]["nudges_stamped"] is None
        assert "processed/stamped" not in sent[0]["body"]


class TestDigestIdempotency:
    def test_rerun_same_week_sends_once(self, digest_env):
        db = FakeDB(signup_rows=[_signup_row(1, "reyaz@gmail.com")])
        sent_calls: list = []

        first, _ = _run(db, sent_calls)
        second, _ = _run(db, sent_calls)

        assert first["status"] == "ok" and first["sent"] is True
        assert second["status"] == "already_sent" and second["sent"] is False
        assert len(sent_calls) == 1

    def test_dry_run_does_not_claim_or_send(self, digest_env):
        db = FakeDB(signup_rows=[_signup_row(1, "reyaz@gmail.com")])
        sent_calls: list = []

        dry, _ = _run(db, sent_calls, dry_run=True)
        assert dry["status"] == "ok"
        assert dry["sent"] is False
        assert dry["dry_run"] is True
        assert dry["metrics"]["signups"] == 1
        assert sent_calls == []
        assert db.claimed == set()

        # A real run afterwards still sends — dry_run consumed nothing.
        real, _ = _run(db, sent_calls)
        assert real["sent"] is True
        assert len(sent_calls) == 1


class TestDigestGuards:
    def test_disabled_via_env(self, digest_env, monkeypatch):
        monkeypatch.setenv("RICO_ENABLE_ADMIN_DIGEST", "false")
        summary, sent = _run(FakeDB(signup_rows=[_signup_row(1, "reyaz@gmail.com")]))
        assert summary["status"] == "disabled"
        assert sent == []

    def test_migration_pending(self, digest_env):
        db = FakeDB(signup_rows=[], migration_applied=False)
        summary, sent = _run(db)
        assert summary["status"] == "migration_pending"
        assert summary["sent"] is False
        assert sent == []

    def test_db_unavailable(self, digest_env):
        db = FakeDB()
        db.available = False
        summary, sent = _run(db)
        assert summary["status"] == "unavailable"
        assert sent == []
