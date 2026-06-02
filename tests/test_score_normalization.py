"""tests/test_score_normalization.py

Tests for issue #323 — match score normalization.

Backend contract: _format_match() must always emit score as float in [0.0, 1.0].
Frontend contract: JobMatchCard normalizes defensively (tested via parseHistoryContent
unit tests in __tests__/command-chat-history-restore.test.ts).

Acceptance criteria:
  - 0.82 → 0.82  (already normalised float, pass-through)
  - 82   → 0.82  (legacy integer, divide by 100)
  - 100  → 1.0   (max integer, becomes 1.0)
  - 5000 → 1.0   (out-of-range, clamped to 1.0)
  - 0    → 0.0   (zero score, no badge)
  - None → 0.0   (missing score, no badge)
  - 0.0  → 0.0   (explicit zero float)
"""
from __future__ import annotations

import pytest
from unittest.mock import patch


def _format_match_score(raw_score) -> float:
    """Call _format_match with a synthetic job dict and return the score field."""
    from src.rico_chat_api import RicoChatAPI

    job = {"title": "HSE Officer", "company": "Acme"}
    if raw_score is not None:
        job["score"] = raw_score

    result = RicoChatAPI._format_match(job, profile=None)
    return result["score"]


class TestScoreNormalizationBackend:
    """_format_match must always return score in [0.0, 1.0]."""

    def test_float_already_normalised(self):
        assert _format_match_score(0.82) == pytest.approx(0.82, abs=0.001)

    def test_integer_82_becomes_point_82(self):
        assert _format_match_score(82) == pytest.approx(0.82, abs=0.001)

    def test_integer_100_becomes_1(self):
        assert _format_match_score(100) == pytest.approx(1.0, abs=0.001)

    def test_outofrange_5000_clamped_to_1(self):
        assert _format_match_score(5000) == pytest.approx(1.0, abs=0.001)

    def test_zero_integer_is_zero(self):
        assert _format_match_score(0) == 0.0

    def test_zero_float_is_zero(self):
        assert _format_match_score(0.0) == 0.0

    def test_none_score_is_zero(self):
        assert _format_match_score(None) == 0.0

    def test_negative_score_clamped_to_zero(self):
        assert _format_match_score(-10) == 0.0

    def test_score_always_lte_1(self):
        for raw in [0, 50, 82, 100, 5000, 0.5, 0.82, 1.0]:
            assert _format_match_score(raw) <= 1.0, f"score exceeded 1.0 for raw={raw}"

    def test_score_always_gte_0(self):
        for raw in [0, -5, 0.0, None]:
            assert _format_match_score(raw) >= 0.0, f"score below 0 for raw={raw}"

    def test_default_fallback_score_50_normalises(self):
        """The pipeline default score of 50 (set via setdefault) must become 0.5."""
        assert _format_match_score(50) == pytest.approx(0.5, abs=0.001)

    def test_fit_score_float_passthrough(self):
        """FitScore.overall_score is already in [0.0, 1.0] — must not be divided."""
        assert _format_match_score(0.75) == pytest.approx(0.75, abs=0.001)

    def test_rico_score_field_used_when_present(self):
        """rico_score takes priority over score field."""
        from src.rico_chat_api import RicoChatAPI
        job = {"title": "HSE Officer", "company": "Acme", "rico_score": 90, "score": 10}
        result = RicoChatAPI._format_match(job, profile=None)
        assert result["score"] == pytest.approx(0.9, abs=0.001)


class TestScoreDoesNotExceed100Pct:
    """End-to-end: score field from _format_match, multiplied by 100, never > 100."""

    @pytest.mark.parametrize("raw", [0, 50, 82, 100, 5000, 0.82, 1.0, None])
    def test_display_pct_never_exceeds_100(self, raw):
        score = _format_match_score(raw)
        display_pct = round(score * 100)
        assert display_pct <= 100, f"display_pct={display_pct} for raw={raw}"
        assert display_pct >= 0, f"display_pct negative for raw={raw}"
