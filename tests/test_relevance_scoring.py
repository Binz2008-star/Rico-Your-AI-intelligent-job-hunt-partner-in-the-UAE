"""Unit tests for src.services.relevance_scoring.

No live DB, no external API calls, no environment variables required.
"""

import pytest
from src.services.relevance_scoring import (
    score_relevance,
    _score_title_role,
    _score_skills,
    _score_location,
)


# ---------------------------------------------------------------------------
# _score_title_role
# ---------------------------------------------------------------------------

class TestScoreTitleRole:
    def test_exact_match_returns_max(self):
        assert _score_title_role("hse manager", ["HSE Manager"]) == 50

    def test_phrase_in_longer_title(self):
        assert _score_title_role("senior hse manager dubai", ["HSE Manager"]) == 50

    def test_core_token_overlap(self):
        # "hse" appears in both; seniority stripped
        score = _score_title_role("hse officer", ["HSE Manager"])
        assert score > 0

    def test_completely_different_role(self):
        score = _score_title_role("software engineer", ["HSE Manager"])
        assert score == 0

    def test_empty_target_roles_returns_neutral(self):
        assert _score_title_role("any title", []) == 20

    def test_best_of_multiple_roles(self):
        score = _score_title_role(
            "safety engineer",
            ["IT Manager", "Safety Officer", "Environmental Consultant"],
        )
        assert score >= 20  # safety token match

    def test_case_insensitive(self):
        assert _score_title_role("QHSE SPECIALIST", ["qhse specialist"]) == 50

    def test_partial_core_overlap(self):
        score = _score_title_role("environmental health manager", ["Environmental Consultant"])
        # "environmental" overlaps; partial but > 0
        assert score > 0


# ---------------------------------------------------------------------------
# _score_skills
# ---------------------------------------------------------------------------

class TestScoreSkills:
    def test_all_skills_match(self):
        title = "HSE Manager with ISO 45001 and risk assessment expertise"
        score = _score_skills(title, "", ["ISO 45001", "risk assessment", "HSE"])
        assert score == 30

    def test_no_skills_match(self):
        score = _score_skills("random job", "", ["Python", "React", "AWS"])
        assert score == 0

    def test_empty_skills_returns_neutral(self):
        assert _score_skills("any title", "any desc", []) == 10

    def test_skills_in_description(self):
        desc = "You will perform incident investigation and prepare EHS reports."
        score = _score_skills("safety officer", desc, ["incident investigation", "EHS"])
        assert score > 0

    def test_description_truncated_to_800_chars(self):
        # Skill present only after 800 chars should NOT boost score
        desc = "A" * 801 + " python"
        score = _score_skills("title", desc, ["python"])
        assert score == 0

    def test_partial_match_proportional(self):
        score_2_of_4 = _score_skills("hse risk", "", ["hse", "risk", "iso", "audit"])
        assert 0 < score_2_of_4 < 30


# ---------------------------------------------------------------------------
# _score_location
# ---------------------------------------------------------------------------

class TestScoreLocation:
    def test_preferred_city_match(self):
        assert _score_location("Dubai, UAE", ["Dubai", "Abu Dhabi"]) == 20

    def test_uae_without_preferred_city(self):
        assert _score_location("Sharjah, UAE", ["Dubai"]) == 10

    def test_non_uae_returns_zero(self):
        assert _score_location("London, UK", ["Dubai"]) == 0

    def test_empty_cities_still_detects_uae(self):
        assert _score_location("Abu Dhabi, UAE", []) == 10

    def test_case_insensitive(self):
        assert _score_location("DUBAI, UAE", ["dubai"]) == 20

    def test_uae_keyword_in_varied_forms(self):
        assert _score_location("United Arab Emirates", []) == 10


# ---------------------------------------------------------------------------
# score_relevance (integration)
# ---------------------------------------------------------------------------

class TestScoreRelevance:
    def _make_job(self, title="HSE Manager", location="Dubai, UAE", description=""):
        return {"title": title, "location": location, "description": description}

    def test_perfect_match_scores_high(self):
        job = self._make_job(
            title="Senior HSE Manager",
            location="Dubai, UAE",
            description="Risk assessment, ISO 45001, safety audits.",
        )
        score = score_relevance(
            job,
            target_roles=["HSE Manager"],
            skills=["risk assessment", "ISO 45001"],
            cities=["Dubai"],
        )
        assert score >= 70

    def test_unrelated_role_scores_low(self):
        job = self._make_job(title="Pastry Chef", location="Dubai, UAE")
        score = score_relevance(
            job,
            target_roles=["HSE Manager"],
            skills=["safety", "ISO 45001"],
            cities=["Dubai"],
        )
        assert score < 30

    def test_non_dict_returns_zero(self):
        assert score_relevance("not a dict", [], [], []) == 0

    def test_empty_title_returns_zero(self):
        assert score_relevance({"title": "", "location": "Dubai"}, ["HSE"], [], []) == 0

    def test_score_bounded_0_to_100(self):
        job = self._make_job(title="HSE Manager HSE Manager HSE")
        roles = ["HSE Manager"] * 10
        skills = ["hse"] * 20
        score = score_relevance(job, roles, skills, ["Dubai"])
        assert 0 <= score <= 100

    def test_missing_optional_fields_graceful(self):
        job = {"title": "Safety Officer"}  # no location or description
        score = score_relevance(job, ["Safety Officer"], [], [])
        assert score > 0  # title match alone should score

    def test_uae_location_adds_partial_points(self):
        job = self._make_job(location="Sharjah, UAE")
        score_uae = score_relevance(job, ["HSE Manager"], [], [])
        job_abroad = self._make_job(location="London, UK")
        score_abroad = score_relevance(job_abroad, ["HSE Manager"], [], [])
        assert score_uae > score_abroad

    def test_preferred_city_beats_generic_uae(self):
        dubai_job = self._make_job(location="Dubai, UAE")
        sharjah_job = self._make_job(location="Sharjah, UAE")
        score_dubai = score_relevance(dubai_job, ["HSE Manager"], [], ["Dubai"])
        score_sharjah = score_relevance(sharjah_job, ["HSE Manager"], [], ["Dubai"])
        assert score_dubai > score_sharjah

    def test_multiple_target_roles_picks_best(self):
        job = self._make_job(title="IT Manager")
        score_it = score_relevance(job, ["IT Manager", "HSE Manager"], [], [])
        score_hse_only = score_relevance(job, ["HSE Manager"], [], [])
        assert score_it > score_hse_only

    def test_search_role_can_be_prepended(self):
        # Simulate the caller prepending search_role to target_roles
        job = self._make_job(title="QHSE Specialist")
        score = score_relevance(
            job,
            target_roles=["QHSE Specialist", "HSE Manager"],
            skills=[],
            cities=[],
        )
        assert score >= 50  # exact title match


# ---------------------------------------------------------------------------
# Regression: scores are no longer flat 50
# ---------------------------------------------------------------------------

class TestNoFlatFifty:
    """Verify that relevance_scoring produces differentiated output,
    not the old flat-50 default that made all results look equal."""

    def test_relevant_job_scores_above_50(self):
        job = {
            "title": "HSE Manager",
            "location": "Dubai, UAE",
            "description": "Safety management system, ISO 45001.",
        }
        score = score_relevance(job, ["HSE Manager"], ["ISO 45001"], ["Dubai"])
        assert score > 50

    def test_irrelevant_job_scores_below_50(self):
        job = {
            "title": "Chef de Partie",
            "location": "Dubai, UAE",
            "description": "Culinary skills required.",
        }
        score = score_relevance(job, ["HSE Manager"], ["safety", "ISO 45001"], ["Dubai"])
        assert score < 50

    def test_scores_are_differentiated(self):
        good_job = {
            "title": "HSE Manager",
            "location": "Dubai, UAE",
            "description": "Risk, safety, ISO 45001.",
        }
        weak_job = {
            "title": "Administrative Assistant",
            "location": "UAE",
            "description": "Filing and office support.",
        }
        good_score = score_relevance(
            good_job, ["HSE Manager"], ["ISO 45001", "risk"], ["Dubai"]
        )
        weak_score = score_relevance(
            weak_job, ["HSE Manager"], ["ISO 45001", "risk"], ["Dubai"]
        )
        assert good_score > weak_score + 20, (
            f"Expected good ({good_score}) to beat weak ({weak_score}) by >20 pts"
        )
