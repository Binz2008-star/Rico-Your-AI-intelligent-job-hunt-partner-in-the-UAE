"""Phase-0 trust gate tests — job apply URL trust chain.

Covers all 7 required cases from issue #746 plus 4 additional edge-cases
for the LLM-origin guard and the plain-job_id-only rejection rule.

Run with::

    pytest tests/test_p0_job_link_trust.py -v
"""

from __future__ import annotations

import pytest

from src.services.job_link_trust import (
    resolve_trusted_apply_url,
    should_show_apply_button,
    safe_no_apply_link_message,
    _has_trusted_provenance,
)
from src.services.source_quality import is_placeholder_url, is_demo_job_id
from src.services.apply_service import resolve_apply_action, wrap_action_error


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _sourced_job(
    url: str,
    *,
    persisted_job_id: str | None = "pjid_001",
    source_job_id: str | None = None,
    provider: str | None = None,
    source_backed: bool | None = None,
    job_id: str | None = None,
) -> dict:
    """Return a minimal trusted job dict with *url* as the apply URL."""
    rec: dict = {"external_url": url}
    if persisted_job_id is not None:
        rec["persisted_job_id"] = persisted_job_id
    if source_job_id is not None:
        rec["source_job_id"] = source_job_id
    if provider is not None:
        rec["provider"] = provider
    if source_backed is not None:
        rec["source_backed"] = source_backed
    if job_id is not None:
        rec["job_id"] = job_id
    return rec


# ---------------------------------------------------------------------------
# 1. Job WITHOUT external_url must NOT show View & Apply
# ---------------------------------------------------------------------------


def test_no_external_url_hides_apply_button() -> None:
    """Required test #1 from issue #746."""
    job: dict = {"persisted_job_id": "pjid_001", "title": "HSE Manager"}
    assert should_show_apply_button(job) is False


# ---------------------------------------------------------------------------
# 2. Job WITH a source-backed external_url MUST show View & Apply
# ---------------------------------------------------------------------------


def test_source_backed_url_shows_apply_button() -> None:
    """Required test #2 from issue #746."""
    job = _sourced_job("https://www.indeed.com/viewjob?jk=a1b2c3d4e5f6g7h8")
    assert should_show_apply_button(job) is True


# ---------------------------------------------------------------------------
# 3. Indeed placeholder jk=abc123 / jk=def456 is REJECTED
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "placeholder_url",
    [
        "https://www.indeed.com/viewjob?jk=abc123",
        "https://www.indeed.com/viewjob?jk=def456",
        "https://ae.indeed.com/viewjob?jk=xyz789&from=app",
        "https://www.indeed.com/viewjob?jk=job001",
    ],
)
def test_indeed_placeholder_jk_is_rejected(placeholder_url: str) -> None:
    """Required test #3 from issue #746."""
    assert is_placeholder_url(placeholder_url) is True
    job = _sourced_job(placeholder_url)
    assert resolve_trusted_apply_url(job) is None
    assert should_show_apply_button(job) is False


# ---------------------------------------------------------------------------
# 4. Generated LinkedIn-looking URL is REJECTED unless from source data
# ---------------------------------------------------------------------------


def test_sequential_linkedin_url_rejected_without_source() -> None:
    """Required test #4 from issue #746 — fake sequential LinkedIn job ID."""
    fake_url = "https://www.linkedin.com/jobs/view/123456"
    job = _sourced_job(
        fake_url,
        persisted_job_id=None,  # no trusted provenance
        source_job_id=None,
    )
    assert resolve_trusted_apply_url(job) is None


def test_real_linkedin_url_accepted_with_source() -> None:
    """Real LinkedIn job ID (10+ digits) with source provenance must pass."""
    real_url = "https://www.linkedin.com/jobs/view/3987654321"
    job = _sourced_job(
        real_url,
        persisted_job_id=None,
        source_job_id="li_3987654321",
        provider="linkedin",
        source_backed=True,
    )
    assert resolve_trusted_apply_url(job) == real_url


# ---------------------------------------------------------------------------
# 5. no_apply_link_available must NOT be shown to the user
# ---------------------------------------------------------------------------


def test_no_apply_link_internal_code_not_leaked() -> None:
    """Required test #5 — raw error code must not appear in user-facing text."""
    user_msg = wrap_action_error("no_apply_link_available")
    assert "no_apply_link_available" not in user_msg
    assert "Action failed" not in user_msg


# ---------------------------------------------------------------------------
# 6. User receives safe fallback when apply link is missing
# ---------------------------------------------------------------------------


def test_safe_fallback_message_when_no_apply_link() -> None:
    """Required test #6 from issue #746."""
    job = {"persisted_job_id": "pjid_002", "title": "Safety Officer", "company": "ADNOC"}
    result = resolve_apply_action(job)
    assert result.success is False
    assert result.show_apply_button is False
    assert result.apply_url is None
    assert "no_apply_link_available" not in result.message
    assert "Action failed" not in result.message
    # Message must be genuinely helpful
    assert len(result.message) > 20


# ---------------------------------------------------------------------------
# 7. Existing valid job-search behaviour still works
# ---------------------------------------------------------------------------


def test_valid_job_with_source_url_resolves_correctly() -> None:
    """Required test #7 — normal source-backed job must pass the full chain."""
    job = _sourced_job(
        "https://www.bayt.com/en/uae/jobs/safety-engineer-12345678/",
        persisted_job_id="pjid_bayt_001",
        source_job_id="bayt_12345678",
        provider="bayt",
        source_backed=True,
    )
    result = resolve_apply_action(job)
    assert result.success is True
    assert result.show_apply_button is True
    assert result.apply_url == "https://www.bayt.com/en/uae/jobs/safety-engineer-12345678/"
    assert result.message == ""


# ---------------------------------------------------------------------------
# 8. apply_url + job_id only + origin=llm => rejected
# ---------------------------------------------------------------------------


def test_llm_origin_with_job_id_rejected() -> None:
    """Extra: LLM-origin payload with a real-looking URL must be rejected."""
    job = {
        "job_id": "job_42",
        "external_url": "https://www.bayt.com/en/uae/jobs/safety-engineer-99999999/",
        # no persisted_job_id, no source_job_id, no provider+source_backed
    }
    assert resolve_trusted_apply_url(job, origin="llm") is None
    result = resolve_apply_action(job, origin="llm")
    assert result.success is False
    assert result.show_apply_button is False


# ---------------------------------------------------------------------------
# 9. apply_url + plain job_id only + no trusted origin => rejected
# ---------------------------------------------------------------------------


def test_plain_job_id_only_not_trusted() -> None:
    """Extra: job_id alone (no persisted_job_id/source_job_id) is not trusted."""
    job = {
        "job_id": "abc_001",
        "external_url": "https://www.linkedin.com/jobs/view/3987654322",
    }
    # _has_trusted_provenance must return False
    assert _has_trusted_provenance(job) is False
    assert resolve_trusted_apply_url(job) is None


# ---------------------------------------------------------------------------
# 10. apply_url + persisted_job_id => accepted
# ---------------------------------------------------------------------------


def test_persisted_job_id_is_trusted() -> None:
    """Extra: persisted_job_id alone is sufficient trusted provenance."""
    job = {
        "persisted_job_id": "pjid_99",
        "external_url": "https://careers.emiratesnbd.com/job/45678",
    }
    assert _has_trusted_provenance(job) is True
    assert resolve_trusted_apply_url(job) == "https://careers.emiratesnbd.com/job/45678"


# ---------------------------------------------------------------------------
# 11. apply_url + source_job_id + provider-backed metadata => accepted
# ---------------------------------------------------------------------------


def test_source_job_id_with_provider_is_trusted() -> None:
    """Extra: source_job_id + provider + source_backed=True is trusted."""
    job = {
        "source_job_id": "jsearch_AE_8812334",
        "provider": "jsearch",
        "source_backed": True,
        "external_url": "https://ae.indeed.com/viewjob?jk=a1b2c3d4e5f60000",
    }
    assert _has_trusted_provenance(job) is True
    result = resolve_apply_action(job)
    assert result.success is True
    assert result.apply_url == "https://ae.indeed.com/viewjob?jk=a1b2c3d4e5f60000"
