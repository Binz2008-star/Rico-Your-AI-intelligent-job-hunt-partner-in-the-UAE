"""
tests/test_bug03_source_url_fallback.py

Regression tests for BUG-03 — View Source / Google Jobs root fallback.

Problem:
  "View Source" on rate-limited/aggregator job cards opened a generic
  google.com/search?q=jobs URL instead of a specific job or source page.

Root cause:
  _format_match fell back to alt_link (job_google_link) when no source_url was
  present, but did not check whether alt_link was itself a Google intermediary
  page. The is_google_intermediary guard only ran on apply_url, not source_url.

Fix:
  After the apply_url google_intermediary check, clear source_url when it also
  resolves to a Google intermediary URL (google.com/search or jobs.google.com).

Covers:
  1. source_url cleared when it is the generic Google Jobs root.
  2. source_url cleared when alt_link fallback is a Google intermediary.
  3. source_url kept when it is a specific job-board URL.
  4. apply_url google_intermediary flow: source_url also cleared.
  5. opened_external not recorded when apply_url is empty.
  6. Existing apply-link flow unaffected.
"""
from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

from src.rico_chat_api import RicoChatAPI


def _profile() -> SimpleNamespace:
    return SimpleNamespace(
        has_cv=True,
        name="Test User",
        preferred_cities=["Dubai"],
        location="Dubai",
        years_experience=5,
        skills=["HSE"],
        certifications=[],
        target_roles=["HSE Manager"],
        current_role="HSE Officer",
    )


def _fmt(m: dict) -> dict:
    return RicoChatAPI._format_match(m, _profile())


# ---------------------------------------------------------------------------
# 1. source_url cleared when it IS a generic Google Jobs root
# ---------------------------------------------------------------------------

class TestGenericGoogleSourceUrlCleared:

    def test_google_search_root_source_url_cleared(self):
        result = _fmt({
            "title": "HSE Manager",
            "company": "Dutco Group",
            "job_apply_link": "",
            "source_url": "https://google.com/search?q=jobs",
        })
        assert result["source_url"] == "", (
            f"Expected source_url to be cleared, got: {result['source_url']!r}"
        )

    def test_google_search_jobs_source_url_cleared(self):
        result = _fmt({
            "title": "HSE Manager",
            "company": "Dutco Group",
            "job_apply_link": "",
            "source_url": "https://www.google.com/search?q=HSE+Manager+jobs",
        })
        assert result["source_url"] == "", (
            f"Expected source_url to be cleared, got: {result['source_url']!r}"
        )

    def test_jobs_google_com_source_url_cleared(self):
        result = _fmt({
            "title": "HSE Manager",
            "company": "Dutco Group",
            "job_apply_link": "",
            "source_url": "https://jobs.google.com/jobs/results/1234567890",
        })
        assert result["source_url"] == "", (
            f"Expected jobs.google.com source_url to be cleared, got: {result['source_url']!r}"
        )


# ---------------------------------------------------------------------------
# 2. source_url cleared when alt_link fallback is a Google intermediary
# ---------------------------------------------------------------------------

class TestGoogleIntermediaryAltLinkFallback:

    def test_alt_link_google_root_not_leaked_to_source_url(self):
        """When no source_url is provided and alt_link is google.com/search, source_url must be empty."""
        result = _fmt({
            "title": "HSE Manager",
            "company": "Dutco Group",
            "job_apply_link": "https://ae.trabajo.org/job/123",
            "job_google_link": "https://google.com/search?q=jobs",
        })
        assert result["source_url"] == "", (
            f"Expected source_url to be empty (alt_link was google intermediary), "
            f"got: {result['source_url']!r}"
        )

    def test_alt_link_google_root_not_leaked_when_apply_is_also_bad(self):
        """Rate-limited apply_url + google alt_link: source_url must still be empty."""
        result = _fmt({
            "title": "HSE Manager",
            "company": "Dutco Group",
            "job_apply_link": "https://ae.trabajo.org/job/123",
            "job_google_link": "https://www.google.com/search?q=jobs",
            "source_url": "",
        })
        assert result["source_url"] == "", (
            f"source_url should not be the google root: {result['source_url']!r}"
        )


# ---------------------------------------------------------------------------
# 3. source_url kept when it is a specific job-board URL
# ---------------------------------------------------------------------------

class TestSpecificSourceUrlKept:

    def test_naukrigulf_source_url_kept(self):
        result = _fmt({
            "title": "HSE Manager",
            "company": "Dutco Group",
            "job_apply_link": "https://ae.trabajo.org/job/123",
            "source_url": "https://www.naukrigulf.com/hse-manager-jobs-in-uae-123456",
        })
        assert result["source_url"] == "https://www.naukrigulf.com/hse-manager-jobs-in-uae-123456", (
            f"Specific source URL should not be cleared: {result['source_url']!r}"
        )

    def test_linkedin_source_url_kept(self):
        result = _fmt({
            "title": "HSE Manager",
            "company": "Dutco Group",
            "job_apply_link": "",
            "source_url": "https://www.linkedin.com/jobs/view/3456789012",
        })
        assert result["source_url"] == "https://www.linkedin.com/jobs/view/3456789012"

    def test_bayt_source_url_kept(self):
        result = _fmt({
            "title": "HSE Manager",
            "company": "Dutco Group",
            "job_apply_link": "",
            "source_url": "https://www.bayt.com/en/uae/jobs/hse-manager-jobs/",
        })
        assert result["source_url"] == "https://www.bayt.com/en/uae/jobs/hse-manager-jobs/"


# ---------------------------------------------------------------------------
# 4. apply_url google_intermediary flow: source_url also cleared
# ---------------------------------------------------------------------------

class TestApplyUrlGoogleIntermediaryFlowSourceUrlAlsoCleared:

    def test_apply_url_is_google_intermediary_source_url_also_cleared(self):
        """When apply_url is a google_intermediary, source_url must not inherit the google URL."""
        result = _fmt({
            "title": "HSE Manager",
            "company": "Dutco Group",
            "job_apply_link": "https://google.com/search?q=HSE+Manager+Dutco",
        })
        assert result["apply_url"] == "", "apply_url should be cleared for google_intermediary"
        assert result["verification_status"] == "google_intermediary"
        assert result["source_url"] == "", (
            f"source_url must not be the google URL: {result['source_url']!r}"
        )

    def test_apply_url_google_intermediary_real_alt_link_preserved(self):
        """alt_link with a real job-board URL is preserved and populates source_url correctly."""
        result = _fmt({
            "title": "HSE Manager",
            "company": "Dutco Group",
            "job_apply_link": "https://google.com/search?q=HSE+Manager+Dutco",
            "job_google_link": "https://naukrigulf.com/job/999",
        })
        assert result["alt_link"] == "https://naukrigulf.com/job/999"
        # naukrigulf.com is not a google intermediary — it propagates to source_url correctly.
        assert result["source_url"] == "https://naukrigulf.com/job/999"


# ---------------------------------------------------------------------------
# 5. opened_external not recorded when apply_url is empty (existing behavior)
# ---------------------------------------------------------------------------

class TestOpenedExternalNotRecordedWithoutApplyUrl:

    def test_empty_apply_url_not_in_result(self):
        """When there is no valid apply_url, the result apply_url must be empty."""
        result = _fmt({
            "title": "HSE Manager",
            "company": "Dutco Group",
            "job_apply_link": "",
            "source_url": "",
        })
        assert result["apply_url"] == ""

    def test_google_intermediary_apply_url_cleared_in_result(self):
        """After google_intermediary check, apply_url in result must be empty."""
        result = _fmt({
            "title": "HSE Manager",
            "company": "Dutco Group",
            "job_apply_link": "https://google.com/search?q=jobs",
        })
        assert result["apply_url"] == ""


# ---------------------------------------------------------------------------
# 6. Existing apply-link flow unaffected
# ---------------------------------------------------------------------------

class TestExistingApplyLinkFlowUnaffected:

    def test_clean_apply_url_preserved(self):
        result = _fmt({
            "title": "HSE Manager",
            "company": "Dutco Group",
            "job_apply_link": "https://greenhouse.io/apply/123",
        })
        assert result["apply_url"] == "https://greenhouse.io/apply/123"
        assert result["verification_status"] == "live_verified"

    def test_rate_limited_apply_url_preserved_in_apply_url_field(self):
        """Rate-limited URLs are not cleared from apply_url — only flagged by verification_status."""
        result = _fmt({
            "title": "HSE Manager",
            "company": "Dutco Group",
            "job_apply_link": "https://ae.trabajo.org/job/456",
        })
        assert result["apply_url"] == "https://ae.trabajo.org/job/456"
        assert result["verification_status"] == "rate_limited"
