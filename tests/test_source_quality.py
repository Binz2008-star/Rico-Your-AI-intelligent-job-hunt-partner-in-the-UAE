"""Tests for source_quality.classify_url domain-based classification."""
from __future__ import annotations

import pytest
from src.services.source_quality import classify_url


class TestTrustedSources:
    def test_greenhouse_is_live_verified(self):
        assert classify_url("https://boards.greenhouse.io/acme/jobs/123") == "live_verified"

    def test_lever_is_live_verified(self):
        assert classify_url("https://jobs.lever.co/acme/abc-def") == "live_verified"

    def test_workday_is_live_verified(self):
        assert classify_url("https://acme.myworkdayjobs.com/en-US/Careers/job/123") == "live_verified"

    def test_naukrigulf_is_live_verified(self):
        assert classify_url("https://www.naukrigulf.com/hse-manager-jobs") == "live_verified"

    def test_indeed_is_live_verified(self):
        assert classify_url("https://ae.indeed.com/viewjob?jk=abc123") == "live_verified"

    def test_linkedin_is_live_verified(self):
        assert classify_url("https://www.linkedin.com/jobs/view/123456") == "live_verified"

    def test_bayt_is_live_verified(self):
        assert classify_url("https://www.bayt.com/en/uae/jobs/hse-manager-jobs/") == "live_verified"

    def test_careers_subdomain_is_live_verified(self):
        assert classify_url("https://careers.acmecompany.com/jobs/456") == "live_verified"

    def test_jobs_subdomain_is_live_verified(self):
        assert classify_url("https://jobs.acmecorp.ae/apply/789") == "live_verified"


class TestLoginRequired:
    def test_gulftalent_is_login_required(self):
        assert classify_url("https://www.gulftalent.com/jobs/hse-manager-123") == "login_required"

    def test_gulftalent_subdomain_is_login_required(self):
        assert classify_url("https://m.gulftalent.com/jobs/456") == "login_required"

    def test_glassdoor_is_login_required(self):
        assert classify_url("https://www.glassdoor.com/job-listing/123") == "login_required"

    def test_monster_is_login_required(self):
        assert classify_url("https://www.monster.com/jobs/search/?q=hse") == "login_required"


class TestRateLimited:
    def test_trabajo_ae_is_rate_limited(self):
        assert classify_url("https://ae.trabajo.org/jobs/search") == "rate_limited"

    def test_trabajo_root_is_rate_limited(self):
        assert classify_url("https://trabajo.org/jobs") == "rate_limited"

    def test_jobtome_is_rate_limited(self):
        assert classify_url("https://www.jobtome.com/j/123") == "rate_limited"


class TestAggregatorUntrusted:
    def test_jooble_is_aggregator_untrusted(self):
        assert classify_url("https://jooble.org/jobs-hse-manager/dubai") == "aggregator_untrusted"

    def test_jora_is_aggregator_untrusted(self):
        assert classify_url("https://jora.com/j?sp=search&q=hse") == "aggregator_untrusted"

    def test_adzuna_is_aggregator_untrusted(self):
        assert classify_url("https://www.adzuna.com/details/123") == "aggregator_untrusted"

    def test_careerjet_is_aggregator_untrusted(self):
        assert classify_url("https://www.careerjet.com/jobad/123") == "aggregator_untrusted"


class TestUnknownDomain:
    def test_unknown_domain_is_needs_verification(self):
        assert classify_url("https://somejobboard.xyz/jobs/123") == "needs_source_verification"

    def test_company_website_no_career_pattern_is_needs_verification(self):
        assert classify_url("https://www.acmecorp.ae/about") == "needs_source_verification"

    def test_empty_url_is_needs_verification(self):
        assert classify_url("") == "needs_source_verification"

    def test_blank_url_is_needs_verification(self):
        assert classify_url("   ") == "needs_source_verification"


class TestLoginRequiredTakesPriorityOverTrusted:
    """Login-required domains must override the trusted list."""

    def test_gulftalent_not_classified_as_live_verified(self):
        status = classify_url("https://www.gulftalent.com/jobs/123")
        assert status == "login_required"
        assert status != "live_verified"
