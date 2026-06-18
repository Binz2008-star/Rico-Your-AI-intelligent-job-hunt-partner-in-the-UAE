"""Tests for Issue #354 — Apply-Link Verification.

Verifies that the open_apply_link handler calls the existing LinkVerifier
service before presenting an apply URL, and handles all outcomes correctly:
  - LIVE     → normal response with apply_url
  - EXPIRED  → fallback message with options, no apply_url
  - BLOCKED  → same fallback as EXPIRED
  - NEEDS_REVIEW / None (timeout/error) → non-blocking fallback, normal response
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.rico_chat_api import RicoChatAPI
from src.services.link_verifier import LinkStatus, VerificationResult
from datetime import datetime, timezone


def _make_result(status: LinkStatus) -> VerificationResult:
    return VerificationResult(
        status=status,
        http_status=200 if status == LinkStatus.LIVE else 404,
        error_message=None,
        verified_at=datetime.now(timezone.utc),
    )


def _api_with_context(title: str, company: str, apply_url: str) -> RicoChatAPI:
    """Return a RicoChatAPI instance with a stubbed recent search-match context."""
    api = RicoChatAPI()
    api._get_recent_context = MagicMock(return_value={
        "recent_search_matches": [
            {
                "title": title,
                "company": company,
                "apply_url": apply_url,
                "verification_status": "lead_needs_verification",
            }
        ]
    })
    api._store_recent_context = MagicMock()
    api._append_chat = MagicMock()
    api._finalize = MagicMock(side_effect=lambda r, *a, **kw: r)
    return api


# ── Test 1: reachable link proceeds normally ──────────────────────────────────

def test_live_link_returns_apply_url():
    """A LIVE verification result → response carries the apply_url."""
    title, company, url = "HSE Manager", "Archirodon", "https://archirodon.com/apply/123"
    api = _api_with_context(title, company, url)

    with patch.object(api, "_verify_link_sync", return_value=_make_result(LinkStatus.LIVE)):
        with patch.object(api, "_persist_application_lifecycle_event"):
            with patch("src.repositories.user_job_context_repo.update_verification_status"):
                with patch("src.repositories.applications_repo.get_all", return_value=[]):
                    with patch("src.repositories.user_job_context_repo.find_by_title_company", return_value=None):
                        result = api._handle_open_apply_link_path(
                            user_id="test@example.com",
                            title=title,
                            company=company,
                            apply_url=url,
                            profile=None,
                        )

    assert result.get("apply_url") == url
    assert "expired" not in (result.get("message") or "").lower()


# ── Test 2: broken link returns fallback ─────────────────────────────────────

def test_expired_link_returns_fallback_message():
    """An EXPIRED verification result → response has fallback message, no apply_url."""
    title, company, url = "HSE Manager", "Archirodon", "https://archirodon.com/apply/old"
    api = _api_with_context(title, company, url)

    with patch.object(api, "_verify_link_sync", return_value=_make_result(LinkStatus.EXPIRED)):
        with patch("src.repositories.user_job_context_repo.update_verification_status"):
            with patch("src.repositories.applications_repo.get_all", return_value=[]):
                with patch("src.repositories.user_job_context_repo.find_by_title_company", return_value=None):
                    result = api._handle_open_apply_link_path(
                        user_id="test@example.com",
                        title=title,
                        company=company,
                        apply_url=url,
                        profile=None,
                    )

    assert result.get("apply_url") is None
    assert result.get("verification_status") == "expired"
    assert "expired" in (result.get("message") or "").lower()
    assert "options" in result
    assert len(result["options"]) == 3


def test_blocked_link_returns_fallback_message():
    """A BLOCKED verification result is treated the same as EXPIRED."""
    title, company, url = "Engineer", "ADNOC", "https://adnoc.ae/careers/old"
    api = _api_with_context(title, company, url)

    with patch.object(api, "_verify_link_sync", return_value=_make_result(LinkStatus.BLOCKED)):
        with patch("src.repositories.user_job_context_repo.update_verification_status"):
            with patch("src.repositories.applications_repo.get_all", return_value=[]):
                with patch("src.repositories.user_job_context_repo.find_by_title_company", return_value=None):
                    result = api._handle_open_apply_link_path(
                        user_id="test@example.com",
                        title=title,
                        company=company,
                        apply_url=url,
                        profile=None,
                    )

    assert result.get("apply_url") is None
    assert result.get("verification_status") == "expired"


# ── Test 3: verifier timeout/error does not crash ────────────────────────────

def test_verifier_returns_none_does_not_crash():
    """_verify_link_sync returning None (timeout/error) → normal response returned."""
    title, company, url = "Project Manager", "Emaar", "https://emaar.com/apply/pm"
    api = _api_with_context(title, company, url)

    with patch.object(api, "_verify_link_sync", return_value=None):
        with patch.object(api, "_persist_application_lifecycle_event"):
            with patch("src.repositories.applications_repo.get_all", return_value=[]):
                with patch("src.repositories.user_job_context_repo.find_by_title_company", return_value=None):
                    result = api._handle_open_apply_link_path(
                        user_id="test@example.com",
                        title=title,
                        company=company,
                        apply_url=url,
                        profile=None,
                    )

    # Must not raise; should return a valid response with the apply_url
    assert result is not None
    assert result.get("apply_url") == url


def test_needs_review_does_not_crash():
    """NEEDS_REVIEW (403/rate-limit/server error) → non-blocking, returns apply_url."""
    title, company, url = "Analyst", "FAB", "https://fab.ae/jobs/analyst"
    api = _api_with_context(title, company, url)

    with patch.object(api, "_verify_link_sync", return_value=_make_result(LinkStatus.NEEDS_REVIEW)):
        with patch.object(api, "_persist_application_lifecycle_event"):
            with patch("src.repositories.applications_repo.get_all", return_value=[]):
                with patch("src.repositories.user_job_context_repo.find_by_title_company", return_value=None):
                    result = api._handle_open_apply_link_path(
                        user_id="test@example.com",
                        title=title,
                        company=company,
                        apply_url=url,
                        profile=None,
                    )

    assert result.get("apply_url") == url


# ── Test 4: verification status recorded ─────────────────────────────────────

def test_live_verification_writes_live_verified_status():
    """LIVE result writes 'live_verified' to user_job_context via update_verification_status."""
    title, company, url = "HSE Manager", "Archirodon", "https://archirodon.com/apply/live"
    api = _api_with_context(title, company, url)
    uvs_calls = []

    def mock_uvs(u, t, c, vs):
        uvs_calls.append({"user_id": u, "title": t, "company": c, "status": vs})

    with patch.object(api, "_verify_link_sync", return_value=_make_result(LinkStatus.LIVE)):
        with patch.object(api, "_persist_application_lifecycle_event"):
            with patch(
                "src.repositories.user_job_context_repo.update_verification_status",
                side_effect=mock_uvs,
            ):
                with patch("src.repositories.applications_repo.get_all", return_value=[]):
                    with patch("src.repositories.user_job_context_repo.find_by_title_company", return_value=None):
                        api._handle_open_apply_link_path(
                            user_id="test@example.com",
                            title=title,
                            company=company,
                            apply_url=url,
                            profile=None,
                        )

    assert len(uvs_calls) == 1
    assert uvs_calls[0]["status"] == "live_verified"
    assert uvs_calls[0]["title"] == title


def test_expired_verification_writes_expired_status():
    """EXPIRED result writes 'expired' to user_job_context via update_verification_status."""
    title, company, url = "HSE Manager", "Archirodon", "https://archirodon.com/apply/dead"
    api = _api_with_context(title, company, url)
    uvs_calls = []

    def mock_uvs(u, t, c, vs):
        uvs_calls.append({"status": vs})

    with patch.object(api, "_verify_link_sync", return_value=_make_result(LinkStatus.EXPIRED)):
        with patch(
            "src.repositories.user_job_context_repo.update_verification_status",
            side_effect=mock_uvs,
        ):
            with patch("src.repositories.applications_repo.get_all", return_value=[]):
                with patch("src.repositories.user_job_context_repo.find_by_title_company", return_value=None):
                    api._handle_open_apply_link_path(
                        user_id="test@example.com",
                        title=title,
                        company=company,
                        apply_url=url,
                        profile=None,
                    )

    assert len(uvs_calls) == 1
    assert uvs_calls[0]["status"] == "expired"


def test_needs_review_does_not_write_live_verified():
    """NEEDS_REVIEW does not write 'live_verified' — do not falsely mark uncertain links."""
    title, company, url = "Analyst", "FAB", "https://fab.ae/jobs/analyst"
    api = _api_with_context(title, company, url)
    uvs_calls = []

    def mock_uvs(u, t, c, vs):
        uvs_calls.append({"status": vs})

    with patch.object(api, "_verify_link_sync", return_value=_make_result(LinkStatus.NEEDS_REVIEW)):
        with patch.object(api, "_persist_application_lifecycle_event"):
            with patch(
                "src.repositories.user_job_context_repo.update_verification_status",
                side_effect=mock_uvs,
            ):
                with patch("src.repositories.applications_repo.get_all", return_value=[]):
                    with patch("src.repositories.user_job_context_repo.find_by_title_company", return_value=None):
                        api._handle_open_apply_link_path(
                            user_id="test@example.com",
                            title=title,
                            company=company,
                            apply_url=url,
                            profile=None,
                        )

    assert not any(c["status"] == "live_verified" for c in uvs_calls)


# ── Test 5: lifecycle record not downgraded on live link ─────────────────────

def test_live_link_records_opened_external_lifecycle():
    """A live link still calls _persist_application_lifecycle_event with opened_external."""
    title, company, url = "HSE Manager", "Archirodon", "https://archirodon.com/apply/live"
    api = _api_with_context(title, company, url)
    persist_calls = []

    def mock_persist(**kwargs):
        persist_calls.append(kwargs)

    with patch.object(api, "_verify_link_sync", return_value=_make_result(LinkStatus.LIVE)):
        with patch.object(api, "_persist_application_lifecycle_event", side_effect=mock_persist):
            with patch("src.repositories.user_job_context_repo.update_verification_status"):
                with patch("src.repositories.applications_repo.get_all", return_value=[]):
                    with patch("src.repositories.user_job_context_repo.find_by_title_company", return_value=None):
                        api._handle_open_apply_link_path(
                            user_id="test@example.com",
                            title=title,
                            company=company,
                            apply_url=url,
                            profile=None,
                        )

    assert any(c.get("status") == "opened_external" for c in persist_calls)


def test_expired_link_does_not_record_opened_external():
    """An expired link must NOT call _persist_application_lifecycle_event."""
    title, company, url = "HSE Manager", "Archirodon", "https://archirodon.com/apply/dead"
    api = _api_with_context(title, company, url)
    persist_calls = []

    with patch.object(api, "_verify_link_sync", return_value=_make_result(LinkStatus.EXPIRED)):
        with patch.object(api, "_persist_application_lifecycle_event",
                          side_effect=lambda **kw: persist_calls.append(kw)):
            with patch("src.repositories.user_job_context_repo.update_verification_status"):
                with patch("src.repositories.applications_repo.get_all", return_value=[]):
                    with patch("src.repositories.user_job_context_repo.find_by_title_company", return_value=None):
                        api._handle_open_apply_link_path(
                            user_id="test@example.com",
                            title=title,
                            company=company,
                            apply_url=url,
                            profile=None,
                        )

    assert not any(c.get("status") == "opened_external" for c in persist_calls)
