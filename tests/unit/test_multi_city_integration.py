"""
tests/unit/test_multi_city_integration.py

Integration-proof suite for the multi-city job search (#1202). Proves, against
the REAL RicoChatAPI.process_message via the offline harness:

  * exactly ONE provider call for a multi-city request (cost guard)
  * server-side filtering of results to the requested cities (off-city dropped)
  * AND / OR / comma city forms all parse
  * de-duplication + stable ordering of requested cities
  * unknown / non-UAE tokens are ignored, not searched
  * works under the postgres memory backend (empty _get_recent_messages)
  * no stale location carry-over from a prior search into a later one
"""
from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

_PROFILE = dict(
    cv_status="parsed", cv_filename="cv.pdf", target_roles=["Data Analyst"],
    skills=["sql"], years_experience=4, preferred_cities=["Dubai"],
)


def _job(company, location, title="Data Analyst"):
    return {"title": title, "company": company,
            "apply_url": f"https://x.example/{company}", "location": location}


def _harness(items, uid):
    """ChatHarness whose provider returns *items* and records each call."""
    from tests.harness.chat_harness import ChatHarness
    from src.jsearch_client import FetchResult
    h = ChatHarness()
    h.provider_calls = []

    def _search(role, location="", **kw):
        h.provider_calls.append((role, location))
        return FetchResult(items=[dict(i) for i in items], provider="jsearch")

    h._search = _search           # shadows ChatHarness._search (used as side_effect)
    h.seed(uid, **_PROFILE)
    return h


# ── canonical-city matcher unit tests ────────────────────────────────────────

class TestCityMatcher:
    def test_alias_and_district(self):
        from src.rico_chat_api import (_canonical_requested_cities,
                                        _location_matches_requested_cities)
        canon = _canonical_requested_cities(["Dubai", "Sharjah"])
        assert _location_matches_requested_cities("Deira, Dubai, UAE", canon)   # district
        assert _location_matches_requested_cities("Sharjah", canon)
        assert not _location_matches_requested_cities("Abu Dhabi, UAE", canon)
        assert not _location_matches_requested_cities("", canon)

    def test_arabic_location_matches_english_request(self):
        from src.rico_chat_api import (_canonical_requested_cities,
                                        _location_matches_requested_cities)
        canon = _canonical_requested_cities(["Dubai"])
        assert _location_matches_requested_cities("دبي, الإمارات", canon)

    def test_empty_constraint_is_unfiltered(self):
        from src.rico_chat_api import _location_matches_requested_cities
        assert _location_matches_requested_cities("anywhere", set())


# ── one provider call + server-side filtering ────────────────────────────────

class TestOneCallAndFilter:
    def test_single_provider_call(self):
        h = _harness([_job("DubaiCo", "Dubai, UAE")], "mci_call@t")
        h.say("mci_call@t", "Find Data Analyst jobs in Dubai and Sharjah")
        assert len(h.provider_calls) == 1, h.provider_calls
        # widened to UAE scope → provider location is empty (one UAE-wide call)
        assert h.provider_calls[0][1] == ""

    def test_offcity_results_filtered_out(self):
        items = [_job("DubaiCo", "Dubai, UAE"),
                 _job("SharjahCo", "Sharjah, UAE"),
                 _job("AbuDhabiCo", "Abu Dhabi, UAE")]
        h = _harness(items, "mci_filter@t")
        res = h.say("mci_filter@t", "Find Data Analyst jobs in Dubai and Sharjah")
        assert res.get("type") == "job_matches"
        blob = str(res.get("matches")) + res.get("message", "")
        assert "DubaiCo" in blob and "SharjahCo" in blob
        assert "AbuDhabiCo" not in blob, "off-city result must be filtered server-side"
        assert res.get("result_count") == 2

    def test_all_offcity_yields_zero(self):
        items = [_job("AbuDhabiCo", "Abu Dhabi, UAE"),
                 _job("AinCo", "Al Ain, UAE")]
        h = _harness(items, "mci_zero@t")
        res = h.say("mci_zero@t", "Find Data Analyst jobs in Dubai and Sharjah")
        assert res.get("result_count") == 0
        assert "AbuDhabiCo" not in (str(res.get("matches")) + res.get("message", ""))


# ── city-list forms: AND / OR / comma, dedupe, ordering, unknowns ────────────

class TestCityFormsParsing:
    @pytest.mark.parametrize("phrase,expected", [
        ("Find Data Analyst jobs in Dubai and Sharjah", "Dubai, Sharjah"),
        ("Find Data Analyst jobs in Dubai or Sharjah", "Dubai, Sharjah"),
        ("Find Data Analyst jobs in Dubai, Sharjah", "Dubai, Sharjah"),
        ("Find Data Analyst jobs in Dubai, Sharjah and Ajman", "Dubai, Sharjah, Ajman"),
    ])
    def test_connector_forms(self, phrase, expected):
        from src.agent.intelligence.intent_classifier import classify_intent
        assert (classify_intent(phrase).entities or {}).get("location") == expected

    def test_dedupe_and_stable_order(self):
        from src.agent.intelligence.intent_classifier import classify_intent
        r = classify_intent("Find Data Analyst jobs in Sharjah, Dubai and Sharjah")
        assert (r.entities or {}).get("location") == "Sharjah, Dubai"

    def test_unknown_city_ignored(self):
        from src.agent.intelligence.intent_classifier import classify_intent
        # "Gotham" is not a UAE city → only Dubai survives → single-city (unchanged)
        assert (classify_intent("Find Data Analyst jobs in Dubai and Gotham")
                .entities or {}).get("location") == "Dubai"

    def test_or_form_end_to_end_filters(self):
        items = [_job("DubaiCo", "Dubai, UAE"), _job("AbuDhabiCo", "Abu Dhabi, UAE")]
        h = _harness(items, "mci_or@t")
        res = h.say("mci_or@t", "Find Data Analyst jobs in Dubai or Sharjah")
        assert "AbuDhabiCo" not in (str(res.get("matches")) + res.get("message", ""))
        assert len(h.provider_calls) == 1


# ── robustness: postgres memory mode (no chat-history reads) ──────────────────

class TestPostgresMemoryMode:
    def test_multi_city_without_recent_messages(self):
        """Detection must not depend on _get_recent_messages (a no-op under the
        postgres memory backend). Force it empty and prove multi-city still works."""
        from src.rico_chat_api import RicoChatAPI
        h = _harness([_job("DubaiCo", "Dubai, UAE"), _job("AbuDhabiCo", "Abu Dhabi, UAE")],
                     "mci_pg@t")
        with patch.object(RicoChatAPI, "_get_recent_messages", return_value=[]):
            res = h.say("mci_pg@t", "Find Data Analyst jobs in Dubai and Sharjah")
        assert res.get("type") == "job_matches"
        assert "Dubai, Sharjah" in res.get("message", "")
        assert "AbuDhabiCo" not in (str(res.get("matches")) + res.get("message", ""))


# ── no stale location carry-over ─────────────────────────────────────────────

class TestNoStaleCarryOver:
    def test_later_search_without_city_does_not_reuse_prior_cities(self):
        h = _harness([_job("DubaiCo", "Dubai, UAE")], "mci_stale@t")
        h.say("mci_stale@t", "Find Data Analyst jobs in Dubai and Sharjah")
        # A fresh explicit search naming NO city must not inherit Dubai/Sharjah.
        res2 = h.say("mci_stale@t", "Find Accountant jobs")
        msg2 = res2.get("message", "")
        assert "Sharjah" not in msg2, f"stale city carried over: {msg2!r}"
