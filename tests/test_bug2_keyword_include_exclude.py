"""
Regression tests for BUG-2: per-user include_keywords/exclude_keywords were
collected on the Settings page ("Jobs matching these are prioritized" /
"...hidden") but had no effect on personalized job scoring.

Root cause: src/scoring.py's per-user scoring path (score_job_for_user /
score_jobs_for_user, used by GET /api/v1/jobs) only ever read the
process-global EXCLUDE_KEYWORDS env var and never read this user's own saved
exclude_keywords from settings, and never read include_keywords at all.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _no_real_profile_or_db():
    with patch("src.scoring.get_user_profile", return_value=None):
        yield


def _job(title: str, description: str = "") -> dict:
    return {"title": title, "company": "Acme", "location": "Dubai", "description": description}


def _settings(include=None, exclude=None):
    return {
        "include_keywords": include or [],
        "exclude_keywords": exclude or [],
        "min_score": 50,
        "max_daily_applies": 10,
        "telegram_chat_id": "",
        "score_threshold_apply": 75,
        "score_threshold_watch": 50,
        "blocked_companies": [],
    }


class TestExcludeKeywordsApplyPerUser:
    def test_user_saved_exclude_keyword_hard_rejects_job(self):
        from src.scoring import score_job_for_user

        job = _job("Senior Python Developer", "Contract role, Python and AWS.")
        with patch(
            "src.services.settings_service.get_settings",
            return_value=_settings(exclude=["contract"]),
        ):
            score = score_job_for_user(job, "user_a")

        assert score == 0
        assert job["score"] == 0
        assert "contract" in job["hard_reject_reason"].lower()

    def test_job_not_matching_exclude_keyword_is_unaffected(self):
        from src.scoring import score_job_for_user

        job = _job("Senior Python Developer", "Permanent role, Python and AWS.")
        with patch(
            "src.services.settings_service.get_settings",
            return_value=_settings(exclude=["contract"]),
        ):
            score = score_job_for_user(job, "user_a")

        assert score != 0

    def test_user_b_does_not_inherit_user_a_excludes(self):
        """Cross-user isolation: each call resolves settings for its own user_id."""
        from src.scoring import score_job_for_user

        job = _job("Senior Python Developer", "Contract role, Python and AWS.")

        def fake_get_settings(user_id=None):
            if user_id == "user_a":
                return _settings(exclude=["contract"])
            return _settings()

        with patch("src.services.settings_service.get_settings", side_effect=fake_get_settings):
            score_b = score_job_for_user(dict(job), "user_b")

        assert score_b != 0


class TestIncludeKeywordsBoostPerUser:
    def test_matching_include_keyword_increases_score(self):
        from src.scoring import score_job_for_user

        job_plain = _job("Software Engineer", "Build APIs.")
        job_matching = _job("Software Engineer", "Build APIs. Fully remote.")

        with patch(
            "src.services.settings_service.get_settings",
            return_value=_settings(),
        ):
            base_score = score_job_for_user(dict(job_plain), "user_a")

        with patch(
            "src.services.settings_service.get_settings",
            return_value=_settings(include=["remote"]),
        ):
            boosted_score = score_job_for_user(dict(job_matching), "user_a")

        assert boosted_score > base_score

    def test_include_keyword_does_not_save_an_excluded_job(self):
        """Exclude must still win even if the same job also matches an include keyword."""
        from src.scoring import score_job_for_user

        job = _job("Software Engineer", "Build APIs. Fully remote. Contract role.")
        with patch(
            "src.services.settings_service.get_settings",
            return_value=_settings(include=["remote"], exclude=["contract"]),
        ):
            score = score_job_for_user(job, "user_a")

        assert score == 0


class TestBatchScoringFetchesSettingsOnce:
    def test_score_jobs_for_user_calls_get_settings_once_per_batch(self):
        """N+1 guard: scoring 50 jobs must not issue 50 settings reads."""
        from src.scoring import score_jobs_for_user

        jobs = [_job(f"Role {i}") for i in range(50)]
        with patch(
            "src.services.settings_service.get_settings",
            return_value=_settings(),
        ) as mock_get_settings:
            score_jobs_for_user(jobs, "user_a")

        assert mock_get_settings.call_count == 1
