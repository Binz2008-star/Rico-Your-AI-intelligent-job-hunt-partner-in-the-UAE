"""
tests/test_job_card_trust.py

Trust/truthfulness tests for job card data emitted by the backend.

Covers:
- No default 50% score in _format_match output
- score=None when no scorer ran
- "current live match" wording is gone from _build_role_confirmation_message
- Apply button fields are honest (apply_url only set from provider data)
- Link unavailable when no URLs provided
- "live" wording not used for unverified results
"""
import pytest
from unittest.mock import MagicMock, patch
from src.rico_chat_api import RicoChatAPI


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_job(**kwargs) -> dict:
    defaults = {
        "title": "HSE Manager",
        "company": "Acme Corp",
        "location": "Dubai, UAE",
    }
    return {**defaults, **kwargs}


def _format(job, profile=None) -> dict:
    return RicoChatAPI._format_match(job, profile or MagicMock())


# ── Score tests ───────────────────────────────────────────────────────────────

class TestScoreTruthfulness:

    def test_no_score_field_emits_none(self):
        """When provider returns no score, output score must be None."""
        result = _format(_make_job())
        assert result["score"] is None, f"Expected None, got {result['score']!r}"

    def test_score_zero_emits_none(self):
        """score=0 from provider must not be shown as 0% — emit None."""
        result = _format(_make_job(score=0))
        assert result["score"] is None

    def test_default_50_is_never_emitted(self):
        """The old bug: _search_jsearch_meta stamped score=50 as default.
        Removing that stamp means score field is absent, so _format_match
        must emit None — not 0.5.
        """
        result = _format(_make_job())  # no score key at all
        assert result["score"] != 0.5, "Default 50% score must never be rendered"
        assert result["score"] is None

    def test_real_score_100_int_normalised(self):
        """Legacy scorer emits 0-100 integers — must normalize to [0.0, 1.0]."""
        result = _format(_make_job(score=88))
        assert result["score"] == pytest.approx(0.88, abs=0.001)

    def test_real_score_float_passed_through(self):
        """FitScore already emits 0.0-1.0 floats — preserve them."""
        result = _format(_make_job(rico_score=0.76))
        assert result["score"] == pytest.approx(0.76, abs=0.001)

    def test_score_1_normalised_correctly(self):
        result = _format(_make_job(score=100))
        assert result["score"] == pytest.approx(1.0, abs=0.001)


# ── URL / link tests ──────────────────────────────────────────────────────────

class TestLinkTruthfulness:

    def test_apply_url_set_from_job_apply_link(self):
        job = _make_job(job_apply_link="https://example.com/apply")
        result = _format(job)
        assert result["apply_url"] == "https://example.com/apply"

    def test_apply_url_empty_when_no_link_provided(self):
        result = _format(_make_job())
        assert result["apply_url"] == ""

    def test_source_url_fallback_to_alt_link(self):
        job = _make_job(job_google_link="https://jobs.google.com/abc")
        result = _format(job)
        # Google link goes to alt_link; apply_url cleared
        assert result["alt_link"] == "https://jobs.google.com/abc"

    def test_verification_status_unverified_when_no_url(self):
        """When no URL is provided, verification_status must not claim the job is live."""
        result = _format(_make_job())
        assert result["verification_status"] not in ("live_verified", "live")

    def test_apply_url_not_fabricated(self):
        """apply_url must never be set to a placeholder or hash."""
        result = _format(_make_job())
        assert result["apply_url"] not in ("#", "N/A", "unknown", "https://example.com")


# ── Wording tests ─────────────────────────────────────────────────────────────

class TestConfirmationMessageWording:
    """_build_role_confirmation_message must not use 'current live' wording."""

    def _build_msg(self, top_matches, **kwargs) -> str:
        api = RicoChatAPI.__new__(RicoChatAPI)
        return api._build_role_search_message(
            normalized_role="HSE Manager",
            city_text="",
            basis_text="",
            top_matches=top_matches,
            role_intelligence_data=None,
            **kwargs,
        )

    def test_no_current_live_wording_with_links(self):
        matches = [_make_job(job_apply_link="https://example.com/apply")]
        msg = self._build_msg(matches)
        assert "current live" not in msg.lower()

    def test_no_current_live_wording_with_leads(self):
        matches = [_make_job()]  # no URL = lead
        msg = self._build_msg(matches)
        assert "current live" not in msg.lower()

    def test_uses_candidate_or_provider_wording(self):
        matches = [_make_job(job_apply_link="https://example.com/apply")]
        msg = self._build_msg(matches)
        # Must use truthful wording
        assert any(phrase in msg.lower() for phrase in [
            "candidate match", "provider data", "provider link", "with provider", "source pipeline",
        ])

    def test_empty_matches_uses_honest_no_results_message(self):
        msg = self._build_msg([])
        assert "current live" not in msg.lower()
        # Must not claim live results when there are none
        assert "live match" not in msg.lower()
