"""
Regression tests for BUG-3: the same job appears twice (or more) on the /flow
kanban board.

Root cause: job_key is derived independently by several write paths into
rico_job_recommendations, so the same real-world job can be stored under more
than one job_key and bypass the DB-level ON CONFLICT (user_id, job_key) dedup.

Fix history: originally collapsed in Python inside applications_repo.get_all().
As of #1092 the dedup lives in SQL (RicoDB._CANONICAL_APPS_CTE) so pages,
totals, stats, and quota counts all derive from ONE canonical record set.

The dedup SEMANTICS (same job under two keys collapses newest-first,
case/whitespace-insensitive matching, distinct jobs/locations never merge,
blank rows survive, url-identity merging, stats/list agreement) are proven
against real SQL in tests/integration/test_1092_applications_pagination_postgres.py.

This file guards the repo-layer CONTRACT: every read path delegates to the
canonical DB-boundary methods — no capped fetch, no in-Python dedup, no page
scan for single-record lookup.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch


def _rec(job_id, title="T", company="C", status="saved"):
    return {
        "job_id": job_id,
        "title": title,
        "company": company,
        "location": "Dubai",
        "link": "",
        "apply_url": "",
        "score": 80,
        "status": status,
        "notes": "",
        "date_applied": "2026-06-30T10:00:00",
        "date_updated": "2026-06-30T10:00:00",
    }


def _mock_db(recs):
    db = MagicMock()
    db.available = True
    db._exact_auth_lookup_enabled = False
    db.get_user_bundle.side_effect = lambda uid: {"id": f"uuid-{uid}"}
    db.get_applications_page.return_value = list(recs)
    db.count_applications.return_value = len(recs)
    db.get_application_stats.return_value = {"total": len(recs)}
    db.find_recommendation.side_effect = lambda uid, jk: next(
        (r for r in recs if r.get("job_id") == jk), None
    )
    return db


class TestCanonicalDelegation:
    def test_get_all_uses_canonical_page_query_with_no_row_cap(self):
        from src.repositories import applications_repo

        recs = [_rec("j1"), _rec("j2")]
        db = _mock_db(recs)
        with patch.object(applications_repo, "_db", return_value=db):
            result = applications_repo.get_all(user_id="user_a")

        assert result == recs
        db.get_applications_page.assert_called_once_with("uuid-user_a")
        db.get_recommendations.assert_not_called()

    def test_get_stats_uses_canonical_db_aggregate(self):
        from src.repositories import applications_repo

        db = _mock_db([_rec("j1")])
        with patch.object(applications_repo, "_db", return_value=db):
            stats = applications_repo.get_stats(user_id="user_a")

        assert stats == {"total": 1}
        db.get_application_stats.assert_called_once_with("uuid-user_a")
        db.get_recommendations.assert_not_called()

    def test_get_page_returns_db_boundary_totals(self):
        from src.repositories import applications_repo

        recs = [_rec(f"j{i}") for i in range(3)]
        db = _mock_db(recs)
        db.count_applications.return_value = 451  # totals come from COUNT, not len(page)
        with patch.object(applications_repo, "_db", return_value=db):
            page = applications_repo.get_page("user_a", page=2, limit=50, status="saved")

        assert page["total"] == 451
        assert page["pages"] == 10
        assert page["page"] == 2
        db.get_applications_page.assert_called_once_with(
            "uuid-user_a", status="saved", limit=50, offset=50
        )
        db.count_applications.assert_called_once_with("uuid-user_a", status="saved")

    def test_find_by_job_id_is_a_direct_lookup_not_a_page_scan(self):
        from src.repositories import applications_repo

        recs = [_rec("raw-duplicate-key")]
        db = _mock_db(recs)
        with patch.object(applications_repo, "_db", return_value=db):
            found = applications_repo.find_by_job_id(
                "raw-duplicate-key", user_id="user_a"
            )

        assert found is not None
        db.find_recommendation.assert_called_once_with("uuid-user_a", "raw-duplicate-key")
        # Never fetches a page/list to scan for one record.
        db.get_applications_page.assert_not_called()
        db.get_recommendations.assert_not_called()

    def test_count_by_status_uses_canonical_count(self):
        from src.repositories import applications_repo

        db = _mock_db([])
        db.count_applications.return_value = 230
        with patch.object(applications_repo, "_db", return_value=db):
            n = applications_repo.count_by_status("user_a", "saved")

        assert n == 230
        db.count_applications.assert_called_once_with("uuid-user_a", status="saved")
