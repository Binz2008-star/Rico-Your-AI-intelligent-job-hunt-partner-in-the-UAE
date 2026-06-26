"""Tests for employer_url / apply_is_direct passthrough — issue #721.

Verifies that:
- normalize_item() extracts employer_website → employer_url and job_apply_is_direct → apply_is_direct
- apply_is_direct=True upgrades display status to live_verified on unknown domains
- apply_is_direct=True does NOT override aggregator_untrusted, login_required, or rate_limited
- employer_url is returned separately and never placed into alt_link
- employer_url is never usable_link (not an apply link)
- Existing alt_link fallback chain is unaffected
"""
import pytest

from src.jsearch_client import normalize_item
from src.services.job_link import resolve_job_link


# ── normalize_item ────────────────────────────────────────────────────────────

class TestNormalizeItemEmployerFields:
    def test_employer_url_extracted(self):
        item = {
            "job_apply_link": "https://aesg.com/apply/123",
            "employer_website": "https://aesg.com",
        }
        result = normalize_item(item)
        assert result["employer_url"] == "https://aesg.com"

    def test_apply_is_direct_true(self):
        item = {
            "job_apply_link": "https://aesg.com/apply/123",
            "job_apply_is_direct": True,
        }
        result = normalize_item(item)
        assert result["apply_is_direct"] is True

    def test_apply_is_direct_false(self):
        item = {
            "job_apply_link": "https://aesg.com/apply/123",
            "job_apply_is_direct": False,
        }
        result = normalize_item(item)
        assert result["apply_is_direct"] is False

    def test_apply_is_direct_absent_defaults_false(self):
        item = {"job_apply_link": "https://aesg.com/apply/123"}
        result = normalize_item(item)
        assert result["apply_is_direct"] is False

    def test_employer_url_absent_defaults_empty(self):
        item = {"job_apply_link": "https://aesg.com/apply/123"}
        result = normalize_item(item)
        assert result["employer_url"] == ""

    def test_existing_fields_unchanged(self):
        """apply_link and alt_link survive alongside the new fields."""
        item = {
            "job_apply_link": "https://aesg.com/apply/123",
            "job_google_link": "https://google.com/search?q=aesg",
            "employer_website": "https://aesg.com",
            "job_apply_is_direct": True,
        }
        result = normalize_item(item)
        assert result["apply_link"] == "https://aesg.com/apply/123"
        assert result["alt_link"] == "https://google.com/search?q=aesg"
        assert result["employer_url"] == "https://aesg.com"
        assert result["apply_is_direct"] is True


# ── resolve_job_link — apply_is_direct upgrade ────────────────────────────────

class TestApplyIsDirectUpgrade:
    def test_direct_apply_upgrades_unknown_domain_to_live_verified(self):
        # Use a domain not in any known list — would normally be needs_source_verification.
        job = {
            "apply_link": "https://unknownstartup999.io/jobs/123",
            "apply_is_direct": True,
        }
        result = resolve_job_link(job)
        assert result["verification_status"] == "live_verified"
        assert result["apply_url"] == "https://unknownstartup999.io/jobs/123"

    def test_direct_apply_false_keeps_needs_source_verification(self):
        # Use a domain not in any known list (no career-substring heuristic hit).
        job = {
            "apply_link": "https://unknownstartup999.io/jobs/123",
            "apply_is_direct": False,
        }
        result = resolve_job_link(job)
        assert result["verification_status"] == "needs_source_verification"

    def test_direct_apply_does_not_upgrade_aggregator_untrusted(self):
        """apply_is_direct=True must NOT override a known-bad aggregator domain."""
        job = {
            "apply_link": "https://jooble.org/jdp/123",
            "apply_is_direct": True,
        }
        result = resolve_job_link(job)
        assert result["verification_status"] != "live_verified"
        assert result["verification_status"] == "aggregator_untrusted"

    def test_direct_apply_does_not_upgrade_login_required(self):
        """apply_is_direct=True must NOT mark a login-gated domain as verified."""
        job = {
            "apply_link": "https://www.gulftalent.com/jobs/123",
            "apply_is_direct": True,
        }
        result = resolve_job_link(job)
        assert result["verification_status"] != "live_verified"
        assert result["verification_status"] == "login_required"

    def test_direct_apply_does_not_upgrade_rate_limited(self):
        """apply_is_direct=True must NOT override rate_limited status."""
        job = {
            "apply_link": "https://ae.trabajo.org/job/123",
            "apply_is_direct": True,
        }
        result = resolve_job_link(job)
        assert result["verification_status"] != "live_verified"
        assert result["verification_status"] == "rate_limited"

    def test_direct_apply_on_trusted_ats_keeps_live_verified(self):
        """Trusted ATS domains already classify as live_verified; direct signal is consistent."""
        job = {
            "apply_link": "https://boards.greenhouse.io/aesg/jobs/123",
            "apply_is_direct": True,
        }
        result = resolve_job_link(job)
        assert result["verification_status"] == "live_verified"


# ── resolve_job_link — employer_url passthrough ───────────────────────────────

class TestEmployerUrlPassthrough:
    def test_employer_url_returned_in_result(self):
        job = {
            "apply_link": "https://aesg.com/apply/123",
            "employer_url": "https://aesg.com",
        }
        result = resolve_job_link(job)
        assert result["employer_url"] == "https://aesg.com"

    def test_employer_url_not_in_alt_link(self):
        """employer_url must never end up in alt_link — it is a separate field."""
        job = {
            "apply_link": "https://aesg.com/apply/123",
            "employer_url": "https://aesg.com",
        }
        result = resolve_job_link(job)
        assert result["alt_link"] != "https://aesg.com"

    def test_employer_url_not_usable_link(self):
        """employer_url must never become the usable_link used for the Apply button."""
        job = {
            # Bad primary apply link
            "apply_link": "https://jooble.org/jdp/123",
            "employer_url": "https://aesg.com",
        }
        result = resolve_job_link(job)
        assert result["usable_link"] != "https://aesg.com"
        assert result["employer_url"] == "https://aesg.com"

    def test_employer_url_empty_when_absent(self):
        job = {"apply_link": "https://aesg.com/apply/123"}
        result = resolve_job_link(job)
        assert result["employer_url"] == ""

    def test_employer_url_preserved_alongside_bad_primary(self):
        """When primary link is a known aggregator, employer_url is still returned for frontend CTA."""
        job = {
            "apply_link": "https://jooble.org/jdp/123",
            "employer_url": "https://aesg.com",
        }
        result = resolve_job_link(job)
        # aggregator_untrusted is in _UNUSABLE_STATUSES → link_unavailable=True
        assert result["link_unavailable"] is True
        assert result["employer_url"] == "https://aesg.com"

    def test_no_link_result_has_employer_url_key(self):
        """Non-dict input returns employer_url key in result."""
        result = resolve_job_link(None)  # type: ignore[arg-type]
        assert "employer_url" in result
        assert result["employer_url"] == ""
