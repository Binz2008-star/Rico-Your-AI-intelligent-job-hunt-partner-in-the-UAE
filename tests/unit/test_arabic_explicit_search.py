"""
tests/unit/test_arabic_explicit_search.py

Regression: an explicit Arabic job search phrased with a colloquial command was
routed to the generic AI conversational fallback instead of the search path. A
live conversation showed "دورلي على وظائف مدير بيئة في دبي" answered generically.

Cause & fix (this PR — guard only):
  The Arabic conversational guard routes search-classified Arabic messages to the
  AI fallback UNLESS they carry an explicit search trigger. Its trigger regex
  recognised only formal commands (ابحث / بحث / دور عن …); the colloquial
  imperatives دورلي / دور لي / دورلنا, لقيلي / لاقيلي, شوفلي / شوف لي were missing.
  They are now recognised, so a real command reaches the search path.

Scope guard: recognising *unmapped* Arabic role titles (e.g. مدير بيئة) is
intentionally OUT of this PR. Once routed, an unmapped role yields a role
clarification (not a generic fallback) — which is exactly what these tests prove.

Non-goals proven by the negative cases:
  * declarative / negated / unrelated Arabic must NOT run a search
  * a دورلي / شوفلي phrase that is not about jobs must NOT run a search
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

_PROFILE = dict(
    cv_status="parsed", cv_filename="cv.pdf", target_roles=["Accountant"],
    skills=["excel"], years_experience=5, preferred_cities=["Dubai"],
)


def _say(uid, msg):
    # Force _get_recent_messages empty: (a) makes these E2E assertions
    # deterministic regardless of what other Arabic-heavy test files ran first in
    # the same process (the harness message store is process-global), and (b)
    # proves the guard works under the postgres memory backend, where chat-history
    # reads are a no-op. The guard reads only the CURRENT message, so this is sound.
    from unittest.mock import patch
    from tests.harness.chat_harness import ChatHarness
    from src.rico_chat_api import RicoChatAPI
    h = ChatHarness()
    h.seed(uid, **_PROFILE)
    with patch.object(RicoChatAPI, "_get_recent_messages", return_value=[]):
        return h.say(uid, msg), h


# ── trigger regex: positive colloquial + formal, negative declarative ────────

class TestArabicSearchTriggerRegex:
    @pytest.mark.parametrize("msg", [
        "دورلي على وظائف مدير بيئة في دبي",
        "دور لي على وظيفة محاسب",
        "دورلنا وظائف",
        "لقيلي وظيفة مهندس",
        "لاقيلي وظيفة",
        "شوفلي وظيفة في دبي",
        "ابحث عن وظائف",          # existing formal trigger still matches
        "دور عن وظيفة",
    ])
    def test_trigger_matches(self, msg):
        from src.rico_chat_api import _ARABIC_SEARCH_TRIGGER_RE
        assert _ARABIC_SEARCH_TRIGGER_RE.search(msg), f"{msg!r} should be a search trigger"

    @pytest.mark.parametrize("msg", [
        "أريد وظيفة براتب جيد",     # declarative
        "عندي خبرة في الإدارة",     # declarative
        "شكرا على المساعدة",        # unrelated / gratitude
    ])
    def test_declarative_not_trigger(self, msg):
        from src.rico_chat_api import _ARABIC_SEARCH_TRIGGER_RE
        assert not _ARABIC_SEARCH_TRIGGER_RE.search(msg), f"{msg!r} must not be a search trigger"


# ── guard routes genuine colloquial commands to the search path ──────────────

class TestGuardRoutesToSearch:
    def test_colloquial_mapped_role_runs_search(self):
        res, h = _say("ar_coll@t", "دورلي على وظيفة محاسب")
        assert res.get("type") == "job_matches"
        assert "Accountant" in h.searched_roles

    def test_formal_mapped_role_runs_search(self):
        res, h = _say("ar_formal@t", "ابحث عن وظيفة محاسب")
        assert res.get("type") == "job_matches"
        assert "Accountant" in h.searched_roles

    def test_reported_case_reaches_search_path_not_fallback(self):
        """The reported message reaches the search/classification path (an unmapped
        role → clarification), NOT the generic AI fallback (which has no type)."""
        res, h = _say("ar_report@t", "دورلي على وظائف مدير بيئة في دبي")
        assert res.get("type") == "clarification"   # reached classification, not fallback


# ── negatives: declarative / negated / unrelated / non-job دورلي,شوفلي ───────

class TestArabicNegativesRunNoSearch:
    @pytest.mark.parametrize("msg", [
        "أريد وظيفة براتب جيد",          # declarative
        "عندي خبرة في الإدارة",          # declarative
        "لا تبحث عن وظائف",              # negated command
        "ما ابغى ابحث عن وظيفة",         # negated intent
        "شكرا على المساعدة",             # unrelated
        "دورلي على رقم مطعم قريب",       # دورلي but NOT about jobs
        "شوفلي الصورة",                  # شوفلي but NOT about jobs
    ])
    def test_no_provider_search_runs(self, msg):
        res, h = _say("ar_neg@t", msg)
        assert h.searched_roles == [], f"{msg!r} must not run a provider search"
        assert res.get("type") != "job_matches"
