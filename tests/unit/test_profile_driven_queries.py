"""Unit tests for jsearch_client.build_queries_for_profile."""
import pytest
from src.jsearch_client import build_queries_for_profile


class TestBuildQueriesForProfile:
    def test_single_role_two_uae_cities(self):
        q = build_queries_for_profile(["HSE Manager"], ["Dubai", "Abu Dhabi"])
        assert "HSE Manager Dubai UAE" in q
        assert "HSE Manager Abu Dhabi UAE" in q
        assert "HSE Manager UAE" in q

    def test_city_qualified_before_base(self):
        q = build_queries_for_profile(["HSE Manager"], ["Dubai"])
        assert q.index("HSE Manager Dubai UAE") < q.index("HSE Manager UAE")

    def test_non_uae_cities_ignored(self):
        q = build_queries_for_profile(["HSE Manager"], ["London", "Remote", "New York"])
        assert q == ["HSE Manager UAE"]

    def test_empty_roles_returns_empty(self):
        assert build_queries_for_profile([], ["Dubai"]) == []

    def test_empty_cities_returns_base_queries(self):
        q = build_queries_for_profile(["HSE Manager", "QHSE Manager"], [])
        assert q == ["HSE Manager UAE", "QHSE Manager UAE"]

    def test_max_queries_cap_respected(self):
        roles = ["R1", "R2", "R3", "R4", "R5", "R6", "R7"]
        cities = ["Dubai", "Abu Dhabi", "Sharjah"]
        q = build_queries_for_profile(roles, cities, max_queries=8)
        assert len(q) <= 8

    def test_no_duplicates(self):
        roles = ["HSE Manager", "HSE Manager"]
        q = build_queries_for_profile(roles, ["Dubai"])
        assert len(q) == len(set(s.lower() for s in q))

    def test_multi_role_ordering(self):
        roles = ["Sustainability Manager", "ESG Manager"]
        q = build_queries_for_profile(roles, ["Dubai"])
        # Sustainability queries should come before ESG queries
        sust_first = next(i for i, x in enumerate(q) if "Sustainability" in x)
        esg_first = next(i for i, x in enumerate(q) if "ESG" in x)
        assert sust_first < esg_first

    def test_all_queries_end_with_uae(self):
        roles = ["HSE Manager", "QHSE Manager"]
        q = build_queries_for_profile(roles, ["Dubai", "Sharjah"])
        assert all(qry.endswith("UAE") for qry in q)

    def test_sharjah_recognised_as_uae_city(self):
        q = build_queries_for_profile(["Safety Manager"], ["Sharjah"])
        assert "Safety Manager Sharjah UAE" in q

    def test_city_with_uae_in_name_not_doubled(self):
        # "Dubai, UAE" should still match and produce a sensible query.
        q = build_queries_for_profile(["HSE Manager"], ["Dubai, UAE"])
        assert any("Dubai" in qry for qry in q)
