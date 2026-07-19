"""
tests/unit/test_multi_city_search.py

Regression: a job search naming several UAE cities must cover — and report —
all of them, not silently collapse to the first. A live conversation showed
"Find Data Analyst jobs in Dubai and Sharjah" answered as "...roles in Dubai".

The fix recovers every requested city from the message and, when two or more are
present, widens the provider query to UAE scope (a single, cost-neutral call
whose results span every requested city) and lists all cities in the reply.
Single-city / no-city behavior is unchanged.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


class TestRequestedCitiesFromText:
    def test_two_cities(self):
        from src.rico_chat_api import _requested_cities_from_text
        assert _requested_cities_from_text("Data Analyst jobs in Dubai and Sharjah") == [
            "Dubai", "Sharjah"
        ]

    def test_three_cities_titlecased(self):
        from src.rico_chat_api import _requested_cities_from_text
        assert _requested_cities_from_text("jobs in dubai, abu dhabi and ajman") == [
            "Dubai", "Abu Dhabi", "Ajman"
        ]

    def test_single_city(self):
        from src.rico_chat_api import _requested_cities_from_text
        assert _requested_cities_from_text("jobs in Dubai") == ["Dubai"]

    def test_no_city(self):
        from src.rico_chat_api import _requested_cities_from_text
        assert _requested_cities_from_text("find me a data analyst job") == []

    def test_uae_scope_excluded(self):
        from src.rico_chat_api import _requested_cities_from_text
        assert _requested_cities_from_text("any jobs in the UAE") == []

    def test_dedup(self):
        from src.rico_chat_api import _requested_cities_from_text
        assert _requested_cities_from_text("Dubai jobs, more Dubai and Sharjah") == [
            "Dubai", "Sharjah"
        ]

    def test_arabic_two_cities(self):
        from src.rico_chat_api import _requested_cities_from_text
        assert _requested_cities_from_text("وظائف في دبي والشارقة") == ["دبي", "الشارقة"]


class TestClassifierEmitsAllCities:
    def test_two_cities_joined(self):
        from src.agent.intelligence.intent_classifier import classify_intent
        r = classify_intent("Find Data Analyst jobs in Dubai and Sharjah")
        assert r.intent == "job_search_explicit"
        assert (r.entities or {}).get("location") == "Dubai, Sharjah"

    def test_single_city_unchanged(self):
        from src.agent.intelligence.intent_classifier import classify_intent
        r = classify_intent("find software jobs in Dubai")
        assert (r.entities or {}).get("location") == "Dubai"

    def test_uae_scope_preserved(self):
        from src.agent.intelligence.intent_classifier import classify_intent
        r = classify_intent("any jobs in UAE")
        assert (r.entities or {}).get("location") == "UAE"

    def test_specific_city_wins_over_uae(self):
        from src.agent.intelligence.intent_classifier import classify_intent
        r = classify_intent("find HSE jobs in Dubai and UAE")
        assert (r.entities or {}).get("location") == "Dubai"


class TestMultiCitySearchEndToEnd:
    # Each test uses a UNIQUE user id: the harness chat-history store is
    # process-global, so reusing one id bleeds the previous turn's message into
    # `_get_recent_messages` and corrupts language / multi-city detection.
    def _h(self, uid):
        from tests.harness.chat_harness import ChatHarness
        h = ChatHarness()
        h.seed(uid, cv_status="parsed", cv_filename="cv.pdf",
               target_roles=["Data Analyst"], skills=["sql"],
               years_experience=4, preferred_cities=["Dubai"])
        return h

    def test_two_cities_both_reported(self):
        uid = "mc_two@t"
        h = self._h(uid)
        res = h.say(uid, "Find Data Analyst jobs in Dubai and Sharjah")
        assert res.get("type") == "job_matches"
        msg = res.get("message", "")
        assert "Dubai" in msg and "Sharjah" in msg

    def test_two_cities_single_provider_call(self):
        """Cost guard: several cities must NOT fan out into one provider call
        per city — the UAE-wide widening keeps it to a single call."""
        uid = "mc_cost@t"
        h = self._h(uid)
        h.say(uid, "Find Data Analyst jobs in Dubai and Sharjah")
        assert len(h.searched_roles) == 1

    def test_single_city_unchanged(self):
        uid = "mc_one@t"
        h = self._h(uid)
        res = h.say(uid, "Find Data Analyst jobs in Dubai")
        msg = res.get("message", "")
        assert "Dubai" in msg
        assert "Sharjah" not in msg

    def test_no_city_uses_profile_default(self):
        uid = "mc_none@t"
        h = self._h(uid)
        res = h.say(uid, "Find Data Analyst jobs")
        assert res.get("type") == "job_matches"
        # Falls back to the profile's preferred city; no crash, no empty scope.
        assert "Dubai" in res.get("message", "")

    def test_three_cities_all_reported(self):
        uid = "mc_three@t"
        h = self._h(uid)
        res = h.say(uid, "Find Data Analyst jobs in Dubai, Abu Dhabi and Ajman")
        assert res.get("type") == "job_matches"
        msg = res.get("message", "")
        assert "Dubai" in msg and "Abu Dhabi" in msg and "Ajman" in msg
