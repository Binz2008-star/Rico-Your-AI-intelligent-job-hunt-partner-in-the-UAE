from __future__ import annotations

import src.db as legacy_db


class FakeCursor:
    def __init__(self, *, fail: bool = False):
        self.fail = fail

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, *args, **kwargs):
        if self.fail:
            raise RuntimeError("write failed")


class FakeConnection:
    def __init__(self, *, fail: bool = False):
        self.autocommit = False
        self.closed = False
        self.committed = False
        self.rolled_back = False
        self.fail = fail

    def cursor(self):
        return FakeCursor(fail=self.fail)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_get_db_connection_keeps_transactional_default(monkeypatch):
    conn = FakeConnection()
    monkeypatch.setattr(legacy_db, "DB_ENABLED", True)
    monkeypatch.setattr(legacy_db, "DATABASE_URL", "postgresql://example")
    monkeypatch.setattr(legacy_db.psycopg2, "connect", lambda url, **kw: conn)

    assert legacy_db.get_db_connection() is conn
    assert conn.autocommit is False


def test_save_job_commits_on_success(monkeypatch):
    conn = FakeConnection()
    monkeypatch.setattr(legacy_db, "get_db_connection", lambda: conn)

    ok = legacy_db.save_job(
        {
            "title": "Role",
            "company": "Company",
            "location": "Dubai",
            "link": "https://example.test/job",
            "description": "desc",
            "profile_explanation": "match",
        },
        80,
    )

    assert ok is True
    assert conn.committed is True
    assert conn.rolled_back is False
    assert conn.closed is True


def test_save_job_rolls_back_on_failure(monkeypatch):
    conn = FakeConnection(fail=True)
    monkeypatch.setattr(legacy_db, "get_db_connection", lambda: conn)

    ok = legacy_db.save_job({"link": "https://example.test/job"}, 80)

    assert ok is False
    assert conn.committed is False
    assert conn.rolled_back is True
    assert conn.closed is True
