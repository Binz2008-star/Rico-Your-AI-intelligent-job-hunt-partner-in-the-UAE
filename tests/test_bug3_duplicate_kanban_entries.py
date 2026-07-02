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


class TestDuplicateApplyUrlCollapsedOnRead:
    """Same posting re-saved with a differently formatted location string but
    an identical apply link (e.g. 'Dubai' vs 'Dubai, UAE') must still collapse
    to one row — this was the reported duplicate Mastercard card."""

    def test_same_title_company_url_different_location_text_merges(self):
        from src.repositories import applications_repo

        rows = [
            {**_rec("key-1", "Manager, Commercial", "Mastercard", location="Dubai, UAE",
                     updated_at="2026-06-30T12:00:00"), "apply_url": "https://jobs.example.com/12345"},
            {**_rec("key-2", "Manager, Commercial", "Mastercard", location="Dubai",
                     updated_at="2026-06-30T09:00:00"), "apply_url": "https://jobs.example.com/12345"},
        ]
        mock_db = MagicMock()
        mock_db.get_recommendations.return_value = rows
        mock_db.available = True

        with patch.object(applications_repo, "_db", return_value=mock_db), \
             patch.object(applications_repo, "_provision_db_user_id", return_value="db-uuid"):
            result = applications_repo.get_all(user_id="user_a")

        assert len(result) == 1
        assert result[0]["job_id"] == "key-1", "must keep the most recently updated row"

    def test_same_url_different_title_or_company_not_merged(self):
        """A shared apply_url alone (e.g. a generic careers page) must not
        merge genuinely different postings — title+company must also match."""
        from src.repositories import applications_repo

        rows = [
            {**_rec("key-1", "Manager, Commercial", "Mastercard", location="Dubai"),
             "apply_url": "https://jobs.example.com/careers"},
            {**_rec("key-2", "Analyst, Risk", "Mastercard", location="Dubai"),
             "apply_url": "https://jobs.example.com/careers"},
        ]
        mock_db = MagicMock()
        mock_db.get_recommendations.return_value = rows
        mock_db.available = True

        with patch.object(applications_repo, "_db", return_value=mock_db), \
             patch.object(applications_repo, "_provision_db_user_id", return_value="db-uuid"):
            result = applications_repo.get_all(user_id="user_a")

        assert len(result) == 2

    def test_blank_url_does_not_false_match_other_blank_url_rows(self):
        """Two distinct postings that both lack an apply_url must rely solely
        on the (title, company, location) identity, not collide on empty url."""
        from src.repositories import applications_repo

        rows = [
            _rec("key-1", "Manager, Commercial", "Mastercard", location="Dubai"),
            _rec("key-2", "Manager, Commercial", "Mastercard", location="Abu Dhabi"),
        ]
        mock_db = MagicMock()
        mock_db.get_recommendations.return_value = rows
        mock_db.available = True

        with patch.object(applications_repo, "_db", return_value=mock_db), \
             patch.object(applications_repo, "_provision_db_user_id", return_value="db-uuid"):
            result = applications_repo.get_all(user_id="user_a")

        assert len(result) == 2


class TestStatsMatchesCanonicalList:
    """applications_repo.get_stats() must derive its total from the same
    deduped list get_all() returns — this is the root-cause fix for chat,
    sidebar, and /flow disagreeing on tracked-application counts."""

    def test_stats_total_equals_deduped_list_length(self):
        from src.repositories import applications_repo

        rows = [
            {**_rec("key-1", "Manager, Commercial", "Mastercard", location="Dubai, UAE"),
             "apply_url": "https://jobs.example.com/12345", "status": "applied"},
            {**_rec("key-2", "Manager, Commercial", "Mastercard", location="Dubai"),
             "apply_url": "https://jobs.example.com/12345", "status": "applied"},  # duplicate, collapses
            {**_rec("key-3", "HSE Officer", "Beta LLC"), "status": "saved"},
            {**_rec("key-4", "QHSE Lead", "Gamma Inc"), "status": "interview"},
        ]
        mock_db = MagicMock()
        mock_db.get_recommendations.return_value = rows
        mock_db.available = True

        with patch.object(applications_repo, "_db", return_value=mock_db), \
             patch.object(applications_repo, "_provision_db_user_id", return_value="db-uuid"):
            apps = applications_repo.get_all(user_id="user_a")
            stats = applications_repo.get_stats(user_id="user_a")

        assert stats["total"] == len(apps) == 3
        assert stats["applied"] == 1
        assert stats["saved"] == 1
        assert stats["by_status"]["interview"] == 1

    def test_stats_includes_all_valid_statuses_as_named_fields(self):
        """Unlike the old raw SQL aggregate (only 6 of 10 statuses named at
        the top level), by_status must always carry all 10 valid statuses,
        defaulting absent ones to 0."""
        from src.repositories import applications_repo

        mock_db = MagicMock()
        mock_db.get_recommendations.return_value = []
        mock_db.available = True

        with patch.object(applications_repo, "_db", return_value=mock_db), \
             patch.object(applications_repo, "_provision_db_user_id", return_value="db-uuid"):
            stats = applications_repo.get_stats(user_id="user_a")

        assert stats["total"] == 0
        for status in (
            "saved", "opened", "opened_external", "prepared", "applied",
            "interview", "rejected", "offer", "decision_made", "follow_up_due",
        ):
            assert stats["by_status"][status] == 0


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
