"""Phase-0 trust gate tests — job-link trust chain + source_quality regression.

Test matrix
-----------
Section A — source_quality regression (Blocker 1)
    A1  classify_url() importable and returns expected values
    A2  is_google_intermediary() importable and behaves correctly
    A3  classify_company() importable and returns expected values
    A4  is_low_quality_company() importable and behaves correctly

Section B — placeholder URL detection
    B1  job without external_url does not show View & Apply             (#1)
    B2  job with source-backed external_url shows View & Apply          (#2)
    B3  Indeed placeholder jk=abc123 / jk=def456 is rejected            (#3)
    B4  sequential LinkedIn URL rejected without trusted source         (#4)
    B5  real LinkedIn URL accepted with trusted provenance

Section C — origin gate hardening (Blocker 2)
    C1  origin=recent_context + provider + source_backed=True => rejected
    C2  origin=llm + provider + source_backed=True => rejected
    C3  origin=chat + provider + source_backed=True => rejected
    C4  origin=db + provider + source_backed=True => accepted
    C5  origin=provider + provider + source_backed=True => accepted
    C6  apply_url + job_id only + origin=llm => rejected
    C7  apply_url + plain job_id only + no trusted origin => rejected (Gate 4)
    C8  apply_url + persisted_job_id => accepted
    C9  apply_url + source_job_id/provider metadata => accepted

Section D — action error surface (Blocker 3)
    D1  no_apply_link_available not leaked; safe message returned        (#5 / #6)
    D2  valid job with source URL resolves correctly                     (#7)
    D3  recent_search_matches simulation — untrusted LLM payload:
        no View & Apply, no raw error code in chat output
"""
from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Section A — source_quality regression imports (Blocker 1)
# ---------------------------------------------------------------------------

from src.services.source_quality import (
    classify_company,
    classify_url,
    is_google_intermediary,
    is_low_quality_company,
    is_placeholder_url,
    is_demo_job_id,
    classify_source_tier,
)


class TestSourceQualityRegressionA:
    """Blocker 1 — pre-existing API still importable and behaves correctly."""

    def test_a1_classify_url_trusted_ats(self) -> None:
        assert classify_url("https://boards.greenhouse.io/acmecorp/jobs/12345") == "live_verified"

    def test_a1_classify_url_login_required(self) -> None:
        assert classify_url("https://www.gulftalent.com/uae/jobs/senior-engineer-123") == "login_required"

    def test_a1_classify_url_rate_limited(self) -> None:
        assert classify_url("https://ae.trabajo.org/job/data-analyst-dubai") == "rate_limited"

    def test_a1_classify_url_aggregator_untrusted(self) -> None:
        assert classify_url("https://www.jooble.org/jooble/0/Dubai") == "aggregator_untrusted"

    def test_a1_classify_url_unknown(self) -> None:
        result = classify_url("https://weirdunknownjobsite.xyz/job/12345")
        assert result == "needs_source_verification"

    def test_a1_classify_url_empty(self) -> None:
        assert classify_url("") == "needs_source_verification"

    def test_a2_is_google_intermediary_true(self) -> None:
        assert is_google_intermediary("https://jobs.google.com/search?q=engineer") is True

    def test_a2_is_google_intermediary_false(self) -> None:
        assert is_google_intermediary("https://www.greenhouse.io/jobs/123") is False

    def test_a2_is_google_intermediary_empty(self) -> None:
        assert is_google_intermediary("") is False

    def test_a3_classify_company_ok(self) -> None:
        assert classify_company("Accenture") == "ok"

    def test_a3_classify_company_anonymous(self) -> None:
        assert classify_company("Confidential") == "anonymous"

    def test_a3_classify_company_low_quality(self) -> None:
        assert classify_company("A Leading Company") == "low_quality"

    def test_a3_classify_company_empty(self) -> None:
        assert classify_company("") == "anonymous"

    def test_a4_is_low_quality_company_true(self) -> None:
        assert is_low_quality_company("confidential") is True

    def test_a4_is_low_quality_company_false(self) -> None:
        assert is_low_quality_company("Google LLC") is False


# ---------------------------------------------------------------------------
# Section B — placeholder URL detection
# ---------------------------------------------------------------------------

from src.services.job_link_trust import (
    resolve_trusted_apply_url,
    should_show_apply_button,
    safe_no_apply_link_message,
    UNTRUSTED_ORIGINS,
)

# Minimal trusted job record — would pass all gates
_TRUSTED_JOB: dict = {
    "title": "Backend Engineer",
    "company": "Acme Corp",
    "external_url": "https://boards.greenhouse.io/acmecorp/jobs/5678901",
    "persisted_job_id": "pjid_abc999",
}


class TestPlaceholderUrlB:
    """B-series: URL pattern rejection."""

    def test_b1_no_external_url_hides_apply_button(self) -> None:  # #1
        job = {"title": "Dev", "persisted_job_id": "pjid_1"}
        assert should_show_apply_button(job) is False

    def test_b2_source_backed_url_shows_apply_button(self) -> None:  # #2
        assert should_show_apply_button(_TRUSTED_JOB) is True

    @pytest.mark.parametrize("jk", ["abc123", "def456", "xyz789", "job001"])
    def test_b3_indeed_placeholder_jk_rejected(self, jk: str) -> None:  # #3
        job = {
            "external_url": f"https://www.indeed.com/viewjob?jk={jk}",
            "persisted_job_id": "pjid_2",
        }
        assert resolve_trusted_apply_url(job) is None

    def test_b4_sequential_linkedin_url_rejected(self) -> None:  # #4
        job = {
            "external_url": "https://www.linkedin.com/jobs/view/123",
            "persisted_job_id": "pjid_3",
        }
        assert resolve_trusted_apply_url(job) is None

    def test_b5_real_linkedin_url_accepted(self) -> None:
        job = {
            "external_url": "https://www.linkedin.com/jobs/view/3987654321",
            "persisted_job_id": "pjid_4",
        }
        result = resolve_trusted_apply_url(job)
        assert result == "https://www.linkedin.com/jobs/view/3987654321"


# ---------------------------------------------------------------------------
# Section C — origin gate hardening (Blocker 2)
# ---------------------------------------------------------------------------

class TestOriginGateC:
    """C-series: UNTRUSTED_ORIGINS covers all untrusted delivery channels."""

    # ---- C1-C3: untrusted origins must be rejected even with full provenance ----

    @pytest.mark.parametrize("bad_origin", ["recent_context", "llm", "chat", "context_window"])
    def test_c1_c3_untrusted_origin_with_full_provenance_rejected(
        self, bad_origin: str
    ) -> None:
        """origin=recent_context / llm / chat + provider + source_backed => rejected."""
        job = {
            "external_url": "https://boards.greenhouse.io/spoof/jobs/999999",
            "provider": "jsearch",
            "source_backed": True,
            "origin": bad_origin,
        }
        assert resolve_trusted_apply_url(job) is None
        assert resolve_trusted_apply_url(job, origin=bad_origin) is None

    # ---- C4-C5: trusted origins must be accepted ----

    @pytest.mark.parametrize("good_origin", ["db", "provider", "ingestion", None])
    def test_c4_c5_trusted_origin_with_full_provenance_accepted(
        self, good_origin: str
    ) -> None:
        """origin=db / provider / None + provider + source_backed => accepted."""
        job = {
            "external_url": "https://boards.greenhouse.io/realco/jobs/44556677",
            "provider": "jsearch",
            "source_backed": True,
        }
        result = resolve_trusted_apply_url(job, origin=good_origin)
        assert result == "https://boards.greenhouse.io/realco/jobs/44556677"

    # ---- C6: apply_url + job_id only + origin=llm => rejected ----

    def test_c6_llm_origin_with_job_id_rejected(self) -> None:
        job = {
            "job_id": "job_42",
            "external_url": "https://boards.greenhouse.io/llmco/jobs/11111",
        }
        assert resolve_trusted_apply_url(job, origin="llm") is None

    # ---- C7: apply_url + plain job_id only + no trusted origin => Gate 4 reject ----

    def test_c7_plain_job_id_only_not_trusted(self) -> None:
        job = {
            "job_id": "job_77",
            "external_url": "https://boards.greenhouse.io/plainco/jobs/99999",
        }
        # No origin passed, no persisted_job_id / source_job_id / provider+source_backed
        assert resolve_trusted_apply_url(job) is None

    # ---- C8: persisted_job_id is trusted ----

    def test_c8_persisted_job_id_is_trusted(self) -> None:
        job = {
            "external_url": "https://boards.greenhouse.io/trustedco/jobs/123456",
            "persisted_job_id": "pjid_persisted_001",
        }
        assert resolve_trusted_apply_url(job) == job["external_url"]

    # ---- C9: source_job_id + provider is trusted ----

    def test_c9_source_job_id_with_provider_trusted(self) -> None:
        job = {
            "external_url": "https://myworkdayjobs.com/en-US/Company/job/Dubai/Engineer_REQ-1234",
            "source_job_id": "jsearch_req_1234",
            "provider": "jsearch",
            "source_backed": True,
        }
        assert resolve_trusted_apply_url(job) == job["external_url"]


# ---------------------------------------------------------------------------
# Section D — action error surface + integration simulation (Blocker 3)
# ---------------------------------------------------------------------------

class TestActionErrorSurfaceD:
    """D-series: no raw internal codes in user output; safe fallback always present."""

    def test_d1_no_apply_link_internal_code_not_leaked(self) -> None:  # #5
        """safe_no_apply_link_message never contains no_apply_link_available."""
        job = {"title": "Data Engineer", "company": "Acme"}
        msg = safe_no_apply_link_message(job)
        assert "no_apply_link_available" not in msg
        assert "Action failed" not in msg

    def test_d1_safe_fallback_message_present_when_no_apply_link(self) -> None:  # #6
        job = {"title": "ML Engineer", "company": "DeepMind Dubai"}
        msg = safe_no_apply_link_message(job)
        assert "verified apply link" in msg.lower() or "pipeline" in msg.lower()

    def test_d2_valid_job_with_source_url_resolves(self) -> None:  # #7
        job = {
            "external_url": "https://jobs.lever.co/acme/abc-def-1234",
            "persisted_job_id": "pjid_lever_001",
            "title": "Staff Engineer",
            "company": "Acme",
        }
        result = resolve_trusted_apply_url(job)
        assert result == "https://jobs.lever.co/acme/abc-def-1234"

    def test_d3_recent_search_matches_sim_no_view_apply_no_raw_error(
        self,
    ) -> None:
        """Simulate recent_search_matches with an untrusted LLM apply_url.

        This mirrors the chat path: when Rico formats job cards from
        recent_search_matches, each match must be passed through
        resolve_trusted_apply_url with origin='recent_context'.

        The test confirms:
          1. should_show_apply_button returns False => no View & Apply button.
          2. The user-facing message does not contain any raw error code.
        """
        # Simulate what the LLM might inject into recent_search_matches:
        # a job dict with a plausible-looking URL, provider, and source_backed
        # — but arriving via the chat / recent_context channel.
        llm_injected_match = {
            "job_id": "job_99",
            "title": "Senior DevOps Engineer",
            "company": "FakeAI Corp",
            "external_url": "https://boards.greenhouse.io/fakeai/jobs/555666",
            "provider": "jsearch",
            "source_backed": True,   # LLM can claim this but it must be ignored
            "origin": "recent_context",
        }

        # --- path 1: UI composer deciding whether to show the button ---
        show_button = should_show_apply_button(
            llm_injected_match,
            origin="recent_context",
        )
        assert show_button is False, (
            "View & Apply must NOT appear for a recent_context match"
        )

        # --- path 2: building the user-facing response text ---
        # If resolve_trusted_apply_url returns None, the handler calls
        # safe_no_apply_link_message.  Verify the output is clean.
        url = resolve_trusted_apply_url(llm_injected_match, origin="recent_context")
        assert url is None

        safe_msg = safe_no_apply_link_message(llm_injected_match)
        assert "no_apply_link_available" not in safe_msg
        assert "Action failed" not in safe_msg
        assert "FakeAI Corp" in safe_msg or "Senior DevOps" in safe_msg

    def test_d3_untrusted_origins_set_is_comprehensive(self) -> None:
        """Confirm UNTRUSTED_ORIGINS covers expected channel names."""
        assert "llm" in UNTRUSTED_ORIGINS
        assert "recent_context" in UNTRUSTED_ORIGINS
        assert "chat" in UNTRUSTED_ORIGINS
        assert "context_window" in UNTRUSTED_ORIGINS
