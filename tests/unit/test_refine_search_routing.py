"""
tests/unit/test_refine_search_routing.py

Regression: "Refine search" (a UI affordance / natural phrasing) must not be
misread as an unknown job role. A live Rico conversation showed:

    USER: Refine search
    RICO: I understood you want a new job, but I didn't catch 'Refine search'
          as a specific role...

After the fix it returns actionable refinement guidance and never reaches the
role-miss fallback — while a genuine role like "refined petroleum engineer"
still runs a real search.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


class TestRefineSearchRegex:
    @pytest.mark.parametrize("msg", [
        "Refine search",
        "refine my search",
        "refine the search",
        "Refine results",
        "narrow the results",
        "narrow down my search",
        "تحسين البحث",
        "تضييق البحث",
    ])
    def test_matches(self, msg):
        from src.rico_chat_api import _REFINE_SEARCH_RE
        assert _REFINE_SEARCH_RE.search(msg), f"{msg!r} should match refine-search"

    @pytest.mark.parametrize("msg", [
        "find refined petroleum engineer jobs",
        "search for a manager role",
        "show my applications",
        "find me a job in Dubai",
        "save this job",
    ])
    def test_does_not_match(self, msg):
        from src.rico_chat_api import _REFINE_SEARCH_RE
        assert not _REFINE_SEARCH_RE.search(msg), f"{msg!r} should NOT match refine-search"


class TestHandleRefineSearch:
    @pytest.fixture(autouse=True)
    def _api(self):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        self.api = RicoChatAPI.__new__(RicoChatAPI)
        self.api._append_chat = MagicMock()
        self.api._profile_value = lambda p, k: getattr(p, k, None)
        self.api._as_list = lambda v: list(v) if isinstance(v, list) else ([v] if v else [])
        self.api._is_arabic_text = lambda m: any(ord(c) > 0x600 for c in (m or ""))

    def test_english_guidance_uses_profile_roles(self):
        from types import SimpleNamespace
        profile = SimpleNamespace(target_roles=["HSE Manager", "QHSE Manager"])
        res = self.api._handle_refine_search("u1", profile, "Refine search")
        assert res["type"] == "clarification"
        assert res.get("intent") == "refine_search"
        assert "didn't catch" not in res["message"]
        assert "HSE Manager" in res["message"]
        assert "city" in res["message"].lower()

    def test_arabic_guidance(self):
        from types import SimpleNamespace
        profile = SimpleNamespace(target_roles=["مدير بيئة"])
        res = self.api._handle_refine_search("u1", profile, "تحسين البحث")
        assert res["type"] == "clarification"
        assert any(ord(c) > 0x600 for c in res["message"])

    def test_no_roles_uses_neutral_placeholder(self):
        from types import SimpleNamespace
        profile = SimpleNamespace(target_roles=[])
        res = self.api._handle_refine_search("u1", profile, "narrow the results")
        assert res["type"] == "clarification"
        assert "a role" in res["message"]


class TestRefineSearchEndToEnd:
    def test_refine_search_not_treated_as_role(self):
        from tests.harness.chat_harness import ChatHarness
        h = ChatHarness()
        h.seed("u@t", cv_status="parsed", cv_filename="cv.pdf",
               target_roles=["Environmental Manager"], skills=["iso"],
               years_experience=10, preferred_cities=["Dubai"])
        res = h.say("u@t", "Refine search")
        assert res.get("type") == "clarification"
        assert "as a specific role" not in (res.get("message") or "")
        assert res.get("intent") == "refine_search"

    def test_real_role_still_searches(self):
        from tests.harness.chat_harness import ChatHarness
        h = ChatHarness()
        h.seed("u@t", cv_status="parsed", cv_filename="cv.pdf",
               target_roles=["Environmental Manager"], skills=["iso"],
               years_experience=10, preferred_cities=["Dubai"])
        res = h.say("u@t", "find refined petroleum engineer jobs")
        assert res.get("type") == "job_matches"
