"""Tests for audit item 1-B: real fit-score and match_explanation in _format_match."""
from __future__ import annotations

import pytest
from src.rico_chat_api import RicoChatAPI


def _fmt(job: dict, profile=None) -> dict:
    return RicoChatAPI._format_match(job, profile or {})


class TestFormatMatchScore:

    def test_integer_score_normalized_to_float(self):
        result = _fmt({"title": "Engineer", "score": 82})
        assert result["score"] == pytest.approx(0.82, abs=0.01)

    def test_float_score_passed_through(self):
        result = _fmt({"title": "Engineer", "score": 0.75})
        assert result["score"] == pytest.approx(0.75, abs=0.001)

    def test_none_score_emits_zero_sentinel(self):
        result = _fmt({"title": "Engineer"})
        assert result["score"] == 0.0

    def test_zero_score_emits_zero_sentinel(self):
        result = _fmt({"title": "Engineer", "score": 0})
        assert result["score"] == 0.0

    def test_score_capped_at_one(self):
        result = _fmt({"title": "Engineer", "score": 150})
        assert result["score"] == pytest.approx(1.0, abs=0.001)


class TestFormatMatchExplanationField:

    def test_match_explanation_present(self):
        result = _fmt({"title": "Data Analyst", "company": "Acme", "score": 75})
        assert "match_explanation" in result

    def test_match_explanation_has_required_fields(self):
        result = _fmt({"title": "Data Analyst", "company": "Acme", "score": 75})
        me = result["match_explanation"]
        for field in ("verdict", "summary", "why_this_fits", "worth_checking",
                      "recommended_next_step", "confidence"):
            assert field in me, f"missing field: {field}"

    def test_verdict_values_are_valid(self):
        result = _fmt({"title": "Engineer", "score": 85})
        assert result["match_explanation"]["verdict"] in ("strong_fit", "worth_checking", "weak_fit")

    def test_confidence_values_are_valid(self):
        result = _fmt({"title": "Engineer", "score": 85})
        assert result["match_explanation"]["confidence"] in ("high", "medium", "low")

    def test_why_this_fits_is_list(self):
        result = _fmt({"title": "Engineer", "score": 60})
        assert isinstance(result["match_explanation"]["why_this_fits"], list)

    def test_worth_checking_is_list(self):
        result = _fmt({"title": "Engineer", "score": 60})
        assert isinstance(result["match_explanation"]["worth_checking"], list)

    def test_high_score_yields_strong_fit(self):
        result = _fmt({"title": "Engineer", "score": 90})
        assert result["match_explanation"]["verdict"] == "strong_fit"
        assert result["match_explanation"]["confidence"] == "high"

    def test_low_score_yields_weak_fit(self):
        result = _fmt({"title": "Engineer", "score": 30})
        assert result["match_explanation"]["verdict"] == "weak_fit"
        assert result["match_explanation"]["confidence"] == "low"

    def test_flat_fields_still_present_for_backward_compat(self):
        result = _fmt({"title": "Engineer", "score": 75})
        assert "verdict" in result
        assert "summary" in result
        assert "why_this_fits" in result
        assert "worth_checking" in result

    def test_nested_and_flat_verdict_are_consistent(self):
        result = _fmt({"title": "Engineer", "score": 75})
        assert result["match_explanation"]["verdict"] == result["verdict"]
