# -*- coding: utf-8 -*-
"""DEFECT 1 — explicit message role/location precedence over profile & session.

Precedence contract enforced here (highest wins):
  1. explicit constraints in the CURRENT user message
  2. explicit clarification in the immediately preceding turn
  3. saved profile preferences
  4. product defaults

Root cause (proven via the real ``process_message`` path, not browser guessing):
  * ``_UAE_WIDE_SEARCH_RE`` intercepted any message merely CONTAINING a
    whole-country phrase ("anywhere in the UAE") BEFORE ``classify_intent`` ran,
    and searched ``profile.target_roles[0]`` — discarding the roles the user
    actually typed. Fixed by gating that refinement on
    ``_message_names_explicit_role`` so it only fires for a pure location
    broadening with no role of its own.
  * ``extract_role_list`` dropped the final role family when a trailing
    "anywhere in <loc>" phrase followed the last role ("… or operations manager
    jobs anywhere in the UAE" → lost "operations manager"). Fixed by extending
    ``_ROLE_TOKEN_TAIL_RE`` to peel the scope adverb.

These tests exercise the REAL classify → dispatch → search path via ChatHarness
(offline: no DB, no provider, no network). The search stub records the exact role
and location strings that reach JSearch — the ground truth for "what was searched".
"""
from __future__ import annotations

from typing import Any

import pytest

from tests.harness.chat_harness import ChatHarness
from src.agent.intelligence.intent_classifier import classify_intent, extract_role_list
from src.rico_chat_api import RicoChatAPI

PROFILE_ROLE = "Environmental Manager"


class _Harness(ChatHarness):
    """ChatHarness that also records the *location* handed to the job search and
    can be told to return zero matches (to exercise the no-results response)."""

    def __init__(self, empty_results: bool = False) -> None:
        super().__init__()
        self.searched_locations: list[str] = []
        self._empty = empty_results

    def _search(self, role: str, location: str = "", **kw: Any):
        self.searched_locations.append(location or "")
        result = super()._search(role, location=location, **kw)
        if self._empty:
            result.items = []
        return result


def _seed(h: ChatHarness, user: str = "u@test") -> None:
    h.seed(
        user,
        cv_status="parsed",
        cv_filename="cv.pdf",
        target_roles=[PROFILE_ROLE],
        skills=["hse", "environment", "sustainability"],
        years_experience=8,
        preferred_cities=["Dubai"],
        current_role="Environmental Manager",
    )


# ---------------------------------------------------------------------------
# 1. Explicit single role + city overrides the saved profile role.
# ---------------------------------------------------------------------------
def test_explicit_role_and_city_override_profile():
    h = _Harness()
    _seed(h)
    res = h.say("u@test", "Find HSE Manager jobs in Dubai")
    assert h.searched_roles == ["HSE Manager"]
    assert h.searched_locations == ["Dubai"]
    assert PROFILE_ROLE not in h.searched_roles


# ---------------------------------------------------------------------------
# 2. Explicit off-profile role is never collapsed to the saved profile role.
#    (The "search anyway?" opt-in gate for off-profile roles is the fenced
#    adjacent-role policy and is deliberately preserved — but the request must
#    be ABOUT Accountant + Dubai, never rewritten to Environmental Manager.)
# ---------------------------------------------------------------------------
def test_explicit_off_profile_role_not_rewritten_to_profile():
    h = _Harness()
    _seed(h)
    res = h.say("u@test", "Find accountant jobs in Dubai")
    assert PROFILE_ROLE not in h.searched_roles          # never the profile role
    assert "Environmental Manager" not in (res.get("message") or "")
    assert "accountant" in (res.get("message") or "").lower()
    # The classifier itself must extract Accountant + Dubai from the message.
    ir = classify_intent("Find accountant jobs in Dubai", has_cv_profile=True)
    assert (ir.extracted_role or "").lower() == "accountant"
    assert (ir.entities or {}).get("location") == "Dubai"


# ---------------------------------------------------------------------------
# 3. Multi-role request preserves ALL role families, UAE scope, no collapse.
#    This is the exact live-repro message.
# ---------------------------------------------------------------------------
def test_multi_role_anywhere_in_uae_preserves_all_families():
    h = _Harness()
    _seed(h)
    res = h.say(
        "u@test",
        "Show me any HSE, sustainability, or operations manager jobs anywhere in the UAE.",
    )
    # Never collapses to the saved profile role.
    assert PROFILE_ROLE not in h.searched_roles
    # All three requested families are recognised (not just the primary).
    recognised = [r.lower() for r in (res.get("recognized_roles") or [])]
    assert "hse" in recognised
    assert "sustainability" in recognised
    assert "operations manager" in recognised
    # The primary search targets one of the requested roles, not the profile role.
    assert h.searched_roles and h.searched_roles[0].lower() in recognised


# ---------------------------------------------------------------------------
# 4. A later turn's explicit roles override the previous turn's search role.
# ---------------------------------------------------------------------------
def test_second_turn_roles_override_first_turn_role():
    h = _Harness()
    _seed(h)
    h.say("u@test", "Find Environmental Manager jobs")
    assert h.searched_roles == ["Environmental Manager"]
    before = len(h.searched_roles)
    res = h.say("u@test", "Now show HSE or Operations Manager jobs")
    new = h.searched_roles[before:]
    recognised = [r.lower() for r in (res.get("recognized_roles") or [])]
    assert "hse" in recognised and "operations manager" in recognised
    # turn-2 searched a turn-2 role, NOT the reused turn-1 Environmental Manager.
    assert new and new[0].lower() in ("hse", "operations manager")
    assert "Environmental Manager" not in new


# ---------------------------------------------------------------------------
# 5. "matching my profile" still uses the saved profile role (precedence rung 3).
# ---------------------------------------------------------------------------
def test_profile_match_still_uses_profile_role():
    h = _Harness()
    _seed(h)
    h.say("u@test", "Find jobs matching my profile")
    assert h.searched_roles == [PROFILE_ROLE]


# ---------------------------------------------------------------------------
# 6. An exact profile-role request searches that literal role, no alias swap.
# ---------------------------------------------------------------------------
def test_exact_role_no_alias_substitution():
    h = _Harness()
    _seed(h)
    h.say("u@test", "Find Environmental Manager jobs")
    assert h.searched_roles == ["Environmental Manager"]


# ---------------------------------------------------------------------------
# 7. Two different messages produce two different search args — no reuse.
# ---------------------------------------------------------------------------
def test_two_messages_produce_distinct_search_args():
    h = _Harness()
    _seed(h)
    h.say("u@test", "Find HSE Manager jobs in Dubai")
    first = list(zip(h.searched_roles, h.searched_locations))
    before = len(h.searched_roles)
    h.say("u@test", "Find Sales Manager jobs in Abu Dhabi")
    second = list(zip(h.searched_roles[before:], h.searched_locations[before:]))
    assert first == [("HSE Manager", "Dubai")]
    assert second == [("Sales Manager", "Abu Dhabi")]
    assert first != second


# ---------------------------------------------------------------------------
# 8. A no-results response names the ACTUAL searched role, not the profile role.
# ---------------------------------------------------------------------------
def test_no_results_response_names_searched_role_not_profile():
    h = _Harness(empty_results=True)
    _seed(h)
    res = h.say("u@test", "Find HSE Manager jobs in Dubai")
    assert h.searched_roles == ["HSE Manager"]
    msg = (res.get("message") or "")
    assert "HSE Manager" in msg
    assert "Environmental Manager" not in msg


# ---------------------------------------------------------------------------
# Fix-specific unit guards (classifier + refinement path)
# ---------------------------------------------------------------------------
def test_classifier_keeps_all_roles_past_anywhere_in_uae_trailer():
    """extract_role_list must not drop the last family behind an 'anywhere in
    the UAE' scope phrase (the direct root-cause of the dropped 'operations
    manager')."""
    roles, _excluded = extract_role_list(
        "Show me any HSE, sustainability, or operations manager jobs anywhere in the UAE."
    )
    lowered = [r.lower() for r in roles]
    assert "hse" in lowered
    assert "sustainability" in lowered
    assert "operations manager" in lowered


@pytest.mark.parametrize(
    "message,expected",
    [
        ("Find HSE Manager jobs in Dubai", True),
        ("Find HSE Manager jobs anywhere in the UAE", True),
        ("Find accountant jobs in Dubai", True),
        ("Show me any HSE, sustainability, or operations manager jobs anywhere in the UAE.", True),
        # Pure UAE-wide refinements carry NO explicit role of their own.
        ("look all over the UAE", False),
        ("search all over UAE", False),
        ("expand my search to the UAE", False),
        ("anywhere in the UAE", False),
    ],
)
def test_message_names_explicit_role_predicate(message, expected):
    assert RicoChatAPI._message_names_explicit_role(message, True) is expected


def test_uae_wide_refinement_without_role_still_expands_prior_search():
    """The legitimate 'expand my previous search to all of UAE' refinement (no
    role in the message) must STILL reuse the prior search role — the precedence
    guard only suppresses the intercept when the message names its own role."""
    h = _Harness()
    _seed(h)
    h.say("u@test", "Find HSE Manager jobs in Dubai")
    before = len(h.searched_roles)
    res = h.say("u@test", "look all over the UAE")
    new_roles = h.searched_roles[before:]
    new_locs = h.searched_locations[before:]
    assert new_roles == ["HSE Manager"]      # prior role reused, not lost
    # Broadened to the whole country: the prior Dubai constraint is dropped.
    # "UAE" is the default nationwide scope, so it reaches the provider as an
    # empty city filter (real cities like "Dubai" pass through verbatim).
    assert new_locs == [""]
    assert "UAE" in (res.get("message") or "")
