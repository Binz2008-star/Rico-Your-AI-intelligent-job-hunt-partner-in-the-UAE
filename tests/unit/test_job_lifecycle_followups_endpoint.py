from __future__ import annotations

from datetime import datetime, timezone

from src.api.routers import job_lifecycle

UTC = timezone.utc


def _call_list_followups(**kwargs):
    handler = getattr(job_lifecycle.list_followups, "__wrapped__", job_lifecycle.list_followups)
    return handler(**kwargs)


def test_list_followups_returns_applied_jobs_ready_to_revisit(monkeypatch):
    rows = [
        {
            "title": "Environmental Manager",
            "company": "AESG",
            "status": "applied",
            "apply_url": "https://example.com/apply",
            "source_url": "https://example.com/job",
            "applied_at": datetime(2026, 6, 20, 9, 0, tzinfo=UTC),
        },
        {
            "title": "Recent QHSE Manager",
            "company": "Hotel Group",
            "status": "applied",
            "applied_at": datetime.now(UTC),
        },
    ]

    def fake_get_by_status(user_id, status, limit=25):
        assert user_id == "user@example.com"
        assert status == "applied"
        assert limit == 100
        return rows

    monkeypatch.setattr(job_lifecycle.repo, "get_by_status", fake_get_by_status)

    response = _call_list_followups(
        request=None,
        min_days_since_applied=7,
        limit=25,
        user={"email": "user@example.com"},
    )

    assert response.ok is True
    assert response.count == 1
    assert response.jobs[0].title == "Environmental Manager"
    assert response.jobs[0].company == "AESG"
    assert response.jobs[0].apply_url == "https://example.com/apply"
    assert response.jobs[0].days_since_applied >= 7


def test_list_followups_is_read_only_when_no_candidates(monkeypatch):
    calls = []

    def fake_get_by_status(user_id, status, limit=25):
        calls.append((user_id, status, limit))
        return []

    monkeypatch.setattr(job_lifecycle.repo, "get_by_status", fake_get_by_status)

    response = _call_list_followups(
        request=None,
        min_days_since_applied=7,
        limit=25,
        user={"email": "user@example.com"},
    )

    assert calls == [("user@example.com", "applied", 100)]
    assert response.ok is True
    assert response.count == 0
    assert response.jobs == []
