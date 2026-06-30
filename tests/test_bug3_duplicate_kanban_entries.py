"""
Regression tests for BUG-3: the same job appears twice (or more) on the /flow
kanban board.

Root cause: job_key is derived independently by several write paths into
rico_job_recommendations (daily pipeline, chat "save this job", lifecycle
tracking), each using a different scheme (SHA-256 of link/title|company|
location, raw title::company, MD5 of title|company, etc). The same
real-world job can therefore be stored under more than one job_key, bypass
the DB-level ON CONFLICT (user_id, job_key) dedup, and render as separate
cards on GET /api/v1/applications -> /flow.

Fix: applications_repo.get_all() now collapses rows that share a normalized
(title, company, location) identity, keeping the most recently updated row
(rows already arrive ordered by updated_at DESC from db.get_recommendations).
find_by_job_id() and the write paths are untouched — this is a read-path-only
fix for the list the kanban board renders.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _rec(job_id, title, company, location="Dubai", updated_at="2026-06-30T10:00:00"):
    return {
        "job_id": job_id,
        "title": title,
        "company": company,
        "location": location,
        "link": "",
        "apply_url": "",
        "score": 80,
        "status": "saved",
        "notes": "",
        "date_applied": updated_at,
        "date_updated": updated_at,
    }


class TestDuplicateJobKeyCollapsedOnRead:
    def test_same_job_under_two_job_keys_collapses_to_one(self):
        from src.repositories import applications_repo

        rows = [
            _rec("sha256abc123", "Senior Python Developer", "Acme Corp", updated_at="2026-06-30T12:00:00"),
            _rec("tc:md5xyz789", "Senior Python Developer", "Acme Corp", updated_at="2026-06-30T09:00:00"),
        ]
        mock_db = MagicMock()
        mock_db.get_recommendations.return_value = rows
        mock_db.available = True

        with patch.object(applications_repo, "_db", return_value=mock_db), \
             patch.object(applications_repo, "_provision_db_user_id", return_value="db-uuid"):
            result = applications_repo.get_all(user_id="user_a")

        assert len(result) == 1
        assert result[0]["job_id"] == "sha256abc123", "must keep the most recently updated row"

    def test_matching_is_case_and_whitespace_insensitive(self):
        from src.repositories import applications_repo

        rows = [
            _rec("key-1", "  Senior Python Developer  ", "Acme Corp", updated_at="2026-06-30T12:00:00"),
            _rec("key-2", "senior python developer", "ACME CORP", updated_at="2026-06-30T09:00:00"),
        ]
        mock_db = MagicMock()
        mock_db.get_recommendations.return_value = rows
        mock_db.available = True

        with patch.object(applications_repo, "_db", return_value=mock_db), \
             patch.object(applications_repo, "_provision_db_user_id", return_value="db-uuid"):
            result = applications_repo.get_all(user_id="user_a")

        assert len(result) == 1

    def test_different_jobs_are_not_merged(self):
        from src.repositories import applications_repo

        rows = [
            _rec("key-1", "Senior Python Developer", "Acme Corp"),
            _rec("key-2", "HSE Officer", "Beta LLC"),
            _rec("key-3", "Senior Python Developer", "Different Co"),
        ]
        mock_db = MagicMock()
        mock_db.get_recommendations.return_value = rows
        mock_db.available = True

        with patch.object(applications_repo, "_db", return_value=mock_db), \
             patch.object(applications_repo, "_provision_db_user_id", return_value="db-uuid"):
            result = applications_repo.get_all(user_id="user_a")

        assert len(result) == 3

    def test_same_title_different_location_not_merged(self):
        """Two genuinely distinct postings at different sites must not collapse."""
        from src.repositories import applications_repo

        rows = [
            _rec("key-1", "Senior Python Developer", "Acme Corp", location="Dubai"),
            _rec("key-2", "Senior Python Developer", "Acme Corp", location="Abu Dhabi"),
        ]
        mock_db = MagicMock()
        mock_db.get_recommendations.return_value = rows
        mock_db.available = True

        with patch.object(applications_repo, "_db", return_value=mock_db), \
             patch.object(applications_repo, "_provision_db_user_id", return_value="db-uuid"):
            result = applications_repo.get_all(user_id="user_a")

        assert len(result) == 2

    def test_blank_title_and_company_rows_bypass_dedup(self):
        """Degenerate rows with no identity signal are kept as-is, not silently merged."""
        from src.repositories import applications_repo

        rows = [
            _rec("key-1", "", "", location=""),
            _rec("key-2", "", "", location=""),
        ]
        mock_db = MagicMock()
        mock_db.get_recommendations.return_value = rows
        mock_db.available = True

        with patch.object(applications_repo, "_db", return_value=mock_db), \
             patch.object(applications_repo, "_provision_db_user_id", return_value="db-uuid"):
            result = applications_repo.get_all(user_id="user_a")

        assert len(result) == 2


class TestFindByJobIdUnaffected:
    """find_by_job_id() reads via db.get_recommendations() directly, bypassing
    get_all()'s dedup, so subscription-gating / idempotency checks keyed on a
    specific job_key keep seeing every row exactly as before this fix."""

    def test_find_by_job_id_still_sees_raw_rows(self):
        from src.repositories import applications_repo

        rows = [
            _rec("sha256abc123", "Senior Python Developer", "Acme Corp", updated_at="2026-06-30T12:00:00"),
            _rec("tc:md5xyz789", "Senior Python Developer", "Acme Corp", updated_at="2026-06-30T09:00:00"),
        ]
        mock_db = MagicMock()
        mock_db.get_recommendations.return_value = rows
        mock_db.available = True

        with patch.object(applications_repo, "_db", return_value=mock_db), \
             patch.object(applications_repo, "_provision_db_user_id", return_value="db-uuid"):
            found = applications_repo.find_by_job_id("tc:md5xyz789", user_id="user_a")

        assert found is not None
        assert found["job_id"] == "tc:md5xyz789"
