"""Tests for:
  1. applications_repo.create() writes to DB (not JSON file) when user_id present
  2. jobs_repo.list_from_db() applies 14-day freshness filter
"""
import pytest


# ── Bug 1: apply tracking ──────────────────────────────────────────────────────

def test_create_application_calls_db_upsert(monkeypatch):
    """create() must call db.upsert_recommendation(), NOT mark_applied(), for SaaS users."""
    import src.repositories.applications_repo as repo

    upsert_calls = {}
    mark_applied_calls = []

    class FakeDB:
        def upsert_recommendation(self, user_id, job_key, job_data, status, **kwargs):
            upsert_calls.update(
                {"user_id": user_id, "job_key": job_key, "job_data": job_data, "status": status}
            )
            return True

    def fake_db():
        return FakeDB()

    def fake_provision(db, user_id):
        return "uuid-abc-123"

    def fake_mark_applied(job, status="applied", user_id=None):
        mark_applied_calls.append({"job": job, "status": status, "user_id": user_id})
        return True

    monkeypatch.setattr(repo, "_db", fake_db)
    monkeypatch.setattr(repo, "_provision_db_user_id", fake_provision)
    monkeypatch.setattr(repo, "_mark_applied", fake_mark_applied)

    result = repo.create(
        job_id="job-001",
        title="Senior Audit Manager",
        company="TalentMate",
        location="Abu Dhabi",
        url="https://example.com/job/1",
        status="opened",
        user_id="user@example.com",
    )

    assert result is True
    # DB upsert must be called with correct args
    assert upsert_calls["job_key"] == "job-001"
    assert upsert_calls["status"] == "opened"
    assert upsert_calls["job_data"]["title"] == "Senior Audit Manager"
    assert upsert_calls["job_data"]["company"] == "TalentMate"
    assert upsert_calls["user_id"] == "uuid-abc-123"
    # Legacy JSON writer must NOT be called for SaaS users
    assert mark_applied_calls == [], "mark_applied should not be called for authenticated users"


def test_create_application_no_user_falls_back_to_json(monkeypatch):
    """create() without user_id must use legacy mark_applied (JSON path)."""
    import src.repositories.applications_repo as repo

    mark_applied_calls = []

    def fake_mark_applied(job, status="applied", user_id=None):
        mark_applied_calls.append({"job": job, "status": status, "user_id": user_id})
        return True

    monkeypatch.setattr(repo, "_mark_applied", fake_mark_applied)

    result = repo.create(
        job_id="job-002",
        title="HSE Manager",
        company="ADNOC",
        location="Abu Dhabi",
        status="applied",
        user_id=None,
    )

    assert result is True
    assert len(mark_applied_calls) == 1
    assert mark_applied_calls[0]["job"]["job_id"] == "job-002"


def test_create_manual_delegates_to_create_db_path(monkeypatch):
    """create_manual() must ultimately write to DB (via create()) for SaaS users."""
    import src.repositories.applications_repo as repo

    upsert_calls = {}

    class FakeDB:
        def upsert_recommendation(self, user_id, job_key, job_data, status, **kwargs):
            upsert_calls.update({"user_id": user_id, "status": status, "title": job_data.get("title")})
            return True

    monkeypatch.setattr(repo, "_db", lambda: FakeDB())
    monkeypatch.setattr(repo, "_provision_db_user_id", lambda db, uid: "uuid-xyz")

    result = repo.create_manual(
        title="Environmental Compliance Officer",
        company="EAD",
        location="Abu Dhabi",
        status="applied",
        user_id="user@example.com",
    )

    assert result is True
    assert upsert_calls["title"] == "Environmental Compliance Officer"
    assert upsert_calls["status"] == "applied"


# ── Bug 2: jobs freshness ──────────────────────────────────────────────────────

def test_list_from_db_includes_freshness_filter(monkeypatch):
    """list_from_db() must include a 14-day date_found filter in the SQL WHERE clause."""
    import src.repositories.jobs_repo as jobs_repo

    captured_sql: list = []

    class FakeCursor:
        def __init__(self):
            self.rowcount = 0

        def execute(self, sql, params=None):
            captured_sql.append(sql)

        def fetchone(self):
            return [0]

        def fetchall(self):
            return []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr(jobs_repo, "get_db_connection", lambda: FakeConn())

    jobs_repo.list_from_db(offset=0, limit=20, min_score=60, source=None)

    # At least one of the captured SQL statements must contain the freshness clause.
    # SQL may be built with psycopg2.sql.Composed objects, so stringify each first.
    combined = " ".join(str(s) for s in captured_sql)
    assert "14 days" in combined or "interval" in combined, (
        "jobs query must filter by date_found >= now() - interval '14 days'"
    )
