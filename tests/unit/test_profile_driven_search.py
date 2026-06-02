"""Unit tests for profile-driven JSearch query building."""
import pytest
from unittest.mock import patch, MagicMock
from dataclasses import dataclass, field
from typing import List, Optional

from src.rico_chat_api import RicoChatAPI


@dataclass
class _FakeProfile:
    preferred_cities: List[str] = field(default_factory=list)
    years_experience: Optional[float] = None


class TestBuildProfileSearchQueries:

    def test_no_profile_returns_generic_uae(self):
        queries = RicoChatAPI._build_profile_search_queries("HSE Manager", None)
        assert queries == ["HSE Manager UAE"]

    def test_profile_with_city_uses_city_first(self):
        profile = _FakeProfile(preferred_cities=["Dubai"])
        queries = RicoChatAPI._build_profile_search_queries("HSE Manager", profile)
        assert queries[0] == "HSE Manager Dubai"

    def test_profile_with_city_includes_uae_fallback(self):
        profile = _FakeProfile(preferred_cities=["Abu Dhabi"])
        queries = RicoChatAPI._build_profile_search_queries("HSE Manager", profile)
        assert "HSE Manager UAE" in queries

    def test_profile_with_no_city_returns_uae(self):
        profile = _FakeProfile(preferred_cities=[])
        queries = RicoChatAPI._build_profile_search_queries("HSE Officer", profile)
        assert queries == ["HSE Officer UAE"]

    def test_senior_seniority_when_10_plus_years(self):
        profile = _FakeProfile(years_experience=12.0)
        queries = RicoChatAPI._build_profile_search_queries("HSE Manager", profile)
        assert any("senior" in q.lower() for q in queries)

    def test_junior_seniority_when_2_or_fewer_years(self):
        profile = _FakeProfile(years_experience=1.5)
        queries = RicoChatAPI._build_profile_search_queries("HSE Officer", profile)
        assert any("junior" in q.lower() for q in queries)

    def test_no_seniority_for_mid_level(self):
        profile = _FakeProfile(years_experience=5.0)
        queries = RicoChatAPI._build_profile_search_queries("HSE Officer", profile)
        assert not any("senior" in q.lower() or "junior" in q.lower() for q in queries)

    def test_city_takes_precedence_over_seniority(self):
        profile = _FakeProfile(preferred_cities=["Dubai"], years_experience=15.0)
        queries = RicoChatAPI._build_profile_search_queries("HSE Manager", profile)
        # First query should be city-based, not seniority-based
        assert queries[0] == "HSE Manager Dubai"

    def test_max_two_queries_returned(self):
        profile = _FakeProfile(preferred_cities=["Dubai"], years_experience=12.0)
        queries = RicoChatAPI._build_profile_search_queries("HSE Manager", profile)
        assert len(queries) <= 2

    def test_no_duplicate_queries(self):
        profile = _FakeProfile(preferred_cities=["UAE"])
        queries = RicoChatAPI._build_profile_search_queries("HSE Manager", profile)
        assert len(queries) == len(set(queries))

    def test_empty_city_string_ignored(self):
        profile = _FakeProfile(preferred_cities=["", "  "])
        queries = RicoChatAPI._build_profile_search_queries("HSE Officer", profile)
        assert queries == ["HSE Officer UAE"]

    def test_profile_none_equivalent_to_no_profile(self):
        queries_none = RicoChatAPI._build_profile_search_queries("HSE Manager", None)
        queries_empty = RicoChatAPI._build_profile_search_queries("HSE Manager", _FakeProfile())
        assert queries_none == queries_empty


class TestJSearchMetaWithProfile:

    def test_profile_city_used_in_primary_query(self):
        """_search_jsearch_meta should use city query when profile has preferred_cities."""
        profile = _FakeProfile(preferred_cities=["Dubai"])
        captured_queries = []

        def mock_search(query, **kwargs):
            captured_queries.append(query)
            return MagicMock(items=[], cache_hit=False, rate_limited=False, retries=0, error=None)

        with patch("src.jsearch_client.search", side_effect=mock_search):
            RicoChatAPI._search_jsearch_meta("HSE Manager", profile=profile)

        assert captured_queries[0] == "HSE Manager Dubai", (
            f"Expected 'HSE Manager Dubai' as first query, got {captured_queries!r}"
        )

    def test_no_profile_uses_uae_query(self):
        """Without profile, primary query should be '{role} UAE'."""
        captured_queries = []

        def mock_search(query, **kwargs):
            captured_queries.append(query)
            return MagicMock(items=[], cache_hit=False, rate_limited=False, retries=0, error=None)

        with patch("src.jsearch_client.search", side_effect=mock_search):
            RicoChatAPI._search_jsearch_meta("HSE Manager")

        assert captured_queries[0] == "HSE Manager UAE"

    def test_title_relevance_boost_applied(self):
        """Jobs whose title matches the search role should get a score boost."""
        profile = _FakeProfile()
        matching_job = {"job_id": "1", "title": "HSE Manager", "company": "ADNOC",
                        "link": "https://example.com", "source": "jsearch"}
        unrelated_job = {"job_id": "2", "title": "Driver Required", "company": "ACME",
                         "link": "https://example.com", "source": "jsearch"}

        def mock_search(query, **kwargs):
            return MagicMock(items=[matching_job.copy(), unrelated_job.copy()],
                             cache_hit=False, rate_limited=False, retries=0, error=None)

        with patch("src.jsearch_client.search", side_effect=mock_search):
            result = RicoChatAPI._search_jsearch_meta("HSE Manager", profile=profile)

        scores = {j["title"]: j.get("score", 0) for j in result.items}
        assert scores["HSE Manager"] > scores["Driver Required"], (
            "Matching title should have higher score than unrelated title"
        )
