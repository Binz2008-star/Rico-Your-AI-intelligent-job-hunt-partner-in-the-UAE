"""
tests/unit/test_city_loop_integration.py

Integration proofs for #1198 against the real RicoChatAPI.process_message:

  1. No clarification loop — a gated search asks for the city ONCE; the user's
     next reply (a bare city) resumes the search instead of re-asking.
  2. Refine Search preserves the current role/location — it returns guidance,
     runs no search, and does not mutate the profile's role/city.
  3. One user action = one search operation — a single search message triggers
     exactly one provider call.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


def _harness(uid, provider_items=None, **profile):
    from tests.harness.chat_harness import ChatHarness
    from src.jsearch_client import FetchResult
    h = ChatHarness()
    h.provider_calls = []
    items = provider_items if provider_items is not None else [
        {"title": "HSE Manager", "company": "ACME",
         "apply_url": "https://x.example/1", "location": "Dubai, UAE"},
    ]

    def _search(role, location="", **kw):
        h.provider_calls.append((role, location))
        return FetchResult(items=[dict(i) for i in items], provider="jsearch")

    h._search = _search
    h.seed(uid, **profile)
    return h


_GATED_PROFILE = dict(
    cv_status="parsed", cv_filename="cv.pdf", target_roles=["HSE Manager"],
    skills=["nebosh"], years_experience=6,  # preferred_cities intentionally absent
)


_FORWARD_TYPES = {"job_matches", "no_results_recovery", "profile_role_suggestions"}


class TestNoClarificationLoop:
    def test_city_reply_resumes_search_no_reask(self):
        uid = "cl_loop@t"
        h = _harness(uid, **_GATED_PROFILE)
        with patch("src.rico_chat_api.set_onboarding_status"):
            r1 = h.say(uid, "find me a job")               # gated → ask for city
            assert r1.get("type") == "onboarding"
            assert "preferred_cities" in r1.get("missing_fields", [])
            r2 = h.say(uid, "Ajman")                        # bare city → resume
            # A THIRD, city-less search must not re-enter the gate now that the
            # city is saved (the loop is genuinely broken, not just deferred).
            r3 = h.say(uid, "find me a job")
        # Turn 2 moved the search FORWARD — it is not another city re-ask.
        assert r2.get("type") != "onboarding", r2.get("type")
        assert "preferred_cities" not in (r2.get("missing_fields") or [])
        assert r2.get("type") in _FORWARD_TYPES, r2.get("type")
        # City persisted from the bare reply.
        assert h.profile(uid).preferred_cities == ["Ajman"]
        # Turn 3 does not loop back to onboarding.
        assert r3.get("type") != "onboarding", r3.get("type")


class TestRefineSearchPreservesContext:
    def test_refine_runs_no_search_and_keeps_role_city(self):
        uid = "cl_refine@t"
        h = _harness(uid, cv_status="parsed", cv_filename="cv.pdf",
                     target_roles=["HSE Manager"], skills=["nebosh"],
                     years_experience=6, preferred_cities=["Dubai"])
        r = h.say(uid, "Refine search")
        assert r.get("type") == "clarification"
        assert r.get("intent") == "refine_search"
        assert "as a specific role" not in (r.get("message") or "")
        # No provider search triggered by a refine request.
        assert h.provider_calls == []
        # Current role/location untouched.
        p = h.profile(uid)
        assert p.target_roles == ["HSE Manager"]
        assert p.preferred_cities == ["Dubai"]
        # Guidance references the user's current role.
        assert "HSE Manager" in r.get("message", "")


class TestOneActionOneOperation:
    def test_single_search_one_provider_call(self):
        uid = "cl_op@t"
        h = _harness(uid, cv_status="parsed", cv_filename="cv.pdf",
                     target_roles=["HSE Manager"], skills=["nebosh"],
                     years_experience=6, preferred_cities=["Dubai"])
        r = h.say(uid, "Find HSE Manager jobs in Dubai")
        assert r.get("type") == "job_matches"
        assert len(h.provider_calls) == 1, h.provider_calls
        # The response carries a single completed operation id.
        assert r.get("operation_status") == "completed"
        assert r.get("operation_id")
