"""Unit tests for llm_scorer.rank_by_profile_fit."""
from src.llm_scorer import rank_by_profile_fit


class TestRankByProfileFit:
    def _sample_jobs(self):
        return [
            {"title": "Software Developer", "location": "Dubai", "description": "Python React"},
            {"title": "HSE Manager UAE", "location": "Dubai, UAE", "description": "ISO 14001 environmental compliance"},
            {"title": "QHSE Manager", "location": "Abu Dhabi UAE", "description": "quality health safety environment ISO 45001"},
            {"title": "Sales Manager", "location": "Dubai UAE", "description": "B2B sales account management"},
        ]

    def test_relevant_role_ranks_above_irrelevant(self):
        ranked = rank_by_profile_fit(
            self._sample_jobs(),
            target_roles=["HSE Manager", "QHSE Manager", "Environmental Manager"],
            skills=["ISO 14001", "environmental", "compliance"],
        )
        titles = [j["title"] for j in ranked]
        assert titles[0] in ("HSE Manager UAE", "QHSE Manager")
        # Software Developer should rank below the HSE roles
        assert titles.index("Software Developer") > titles.index("HSE Manager UAE")

    def test_deal_breaker_zeroes_score(self):
        ranked = rank_by_profile_fit(
            self._sample_jobs(),
            target_roles=["HSE Manager"],
            skills=["environmental"],
            deal_breakers=["sales", "software"],
        )
        by_title = {j["title"]: j["profile_fit_score"] for j in ranked}
        assert by_title["Sales Manager"] == 0
        assert by_title["Software Developer"] == 0

    def test_every_job_gets_a_score(self):
        ranked = rank_by_profile_fit(
            self._sample_jobs(),
            target_roles=["HSE Manager"],
            skills=["environmental"],
        )
        assert all("profile_fit_score" in j for j in ranked)

    def test_score_is_bounded_0_to_100(self):
        ranked = rank_by_profile_fit(
            self._sample_jobs(),
            target_roles=["HSE Manager", "QHSE Manager"],
            skills=["iso", "environmental", "compliance", "safety", "health"],
        )
        assert all(0 <= j["profile_fit_score"] <= 100 for j in ranked)

    def test_uae_location_bonus_applied(self):
        jobs = [
            {"title": "HSE Manager", "location": "London", "description": "safety"},
            {"title": "HSE Manager", "location": "Dubai UAE", "description": "safety"},
        ]
        ranked = rank_by_profile_fit(jobs, target_roles=["HSE Manager"], skills=[])
        uae_job = next(j for j in ranked if "Dubai" in j["location"])
        non_uae = next(j for j in ranked if "London" in j["location"])
        assert uae_job["profile_fit_score"] > non_uae["profile_fit_score"]

    def test_results_sorted_descending(self):
        ranked = rank_by_profile_fit(
            self._sample_jobs(),
            target_roles=["HSE Manager", "QHSE Manager"],
            skills=["environmental", "iso"],
        )
        scores = [j["profile_fit_score"] for j in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_empty_jobs_returns_empty(self):
        assert rank_by_profile_fit([], target_roles=["HSE Manager"], skills=[]) == []

    def test_title_match_weighted_above_description(self):
        jobs = [
            {"title": "HSE Manager", "location": "UAE", "description": "generic role"},
            {"title": "Office Admin", "location": "UAE", "description": "supports the HSE Manager team"},
        ]
        ranked = rank_by_profile_fit(jobs, target_roles=["HSE Manager"], skills=[])
        assert ranked[0]["title"] == "HSE Manager"
