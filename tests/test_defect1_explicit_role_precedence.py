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
    # The fenced off-profile opt-in gate (DO-NOT-CHANGE) still fires AND holds the
    # ACTUAL requested target — Accountant + Dubai — as the pending confirmation,
    # never the saved profile role.
    assert res.get("type") == "clarification"
    pending = (h._rctx.get("u@test") or {}).get("_pending_role_confirmation")
    assert pending == {"role": "Accountant", "location": "Dubai"}


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


def test_search_all_across_uae_refinement_reuses_prior_role_exact_wording():
    """Owner's exact wording: T1 'Find HSE Manager jobs in Dubai.' then
    T2 'Search all across the UAE.' — T2 must reuse HSE Manager, broaden to
    UAE, invent no new role, and the UAE-wide intercept must still fire."""
    h = _Harness()
    _seed(h)
    h.say("u@test", "Find HSE Manager jobs in Dubai.")
    before = len(h.searched_roles)
    res = h.say("u@test", "Search all across the UAE.")
    new_roles = h.searched_roles[before:]
    assert new_roles == ["HSE Manager"]              # prior role reused
    assert h.searched_locations[before:] == [""]     # broadened to UAE default
    assert "UAE" in (res.get("message") or "")
    # No new explicit role invented from the refinement phrase.
    assert RicoChatAPI._message_names_explicit_role("Search all across the UAE.", True) is False


def test_executable_search_state_contains_all_requested_roles():
    """The multi-role contract must keep EVERY requested family in executable
    search state — not merely name them in prose. All three are persisted in
    ``multi_role_candidates`` and each, when selected, is searched directly
    (bypassing taxonomy / profile fallback). JSearch takes one role per query,
    so the primary runs now and the rest run on selection — this is the existing
    product contract, exercised here end-to-end, not a parallel engine."""
    h = _Harness()
    _seed(h)
    res = h.say(
        "u@test",
        "Show me any HSE, sustainability, or operations manager jobs anywhere in the UAE.",
    )
    candidates = [c.lower() for c in ((h._rctx.get("u@test") or {}).get("multi_role_candidates") or [])]
    assert candidates == ["hse", "sustainability", "operations manager"]
    # Each remaining family executes directly when its offered option is selected
    # (the option label "Search <role>" is what the UI sends on tap).
    for label, expected in [
        ("Search operations manager", "operations manager"),
        ("Search sustainability", "sustainability"),
    ]:
        h2 = _Harness()
        _seed(h2)
        h2.say(
            "u@test",
            "Show me any HSE, sustainability, or operations manager jobs anywhere in the UAE.",
        )
        before = len(h2.searched_roles)
        follow = h2.say("u@test", label)
        selected = h2.searched_roles[before:]
        assert selected and selected[0].lower() == expected
        assert PROFILE_ROLE not in selected           # never the profile role
        assert follow.get("type") == "job_matches"


def test_prior_role_cannot_overwrite_new_multi_role_request():
    """A previous single-role search must not bleed into a later multi-role
    request — even one carrying a 'anywhere in the UAE' scope phrase."""
    h = _Harness()
    _seed(h)
    h.say("u@test", "Find Environmental Manager jobs")
    assert h.searched_roles == ["Environmental Manager"]
    before = len(h.searched_roles)
    res = h.say(
        "u@test",
        "Show me any HSE, sustainability, or operations manager jobs anywhere in the UAE.",
    )
    new = [r.lower() for r in h.searched_roles[before:]]
    recognised = [r.lower() for r in (res.get("recognized_roles") or [])]
    assert recognised == ["hse", "sustainability", "operations manager"]
    assert "environmental manager" not in new         # prior role not reused
    assert new and new[0] in recognised


def test_classify_intent_is_deterministic_for_the_guard():
    """The precedence guard calls ``classify_intent`` once and routing calls it
    again at dispatch. ``classify_intent`` is a pure regex/exact-phrase function,
    so the two calls are provably identical — the extra call cannot diverge from
    the value routing acts on. (Moving the single classification up would instead
    force it onto ~88 early-return handlers that never classify today, so the
    localized guard is the smallest safe change.)"""
    for message in [
        "Show me any HSE, sustainability, or operations manager jobs anywhere in the UAE.",
        "Find HSE Manager jobs in Dubai",
        "search all over the UAE",
        "Find jobs matching my profile",
    ]:
        first = classify_intent(message, has_cv_profile=True)
        second = classify_intent(message, has_cv_profile=True)
        assert first.intent == second.intent
        assert getattr(first, "entities", None) == getattr(second, "entities", None)
        assert first.extracted_role == second.extracted_role
        assert first.confidence == second.confidence


# ===========================================================================
# Search-context CONTINUITY contract (Defect 1, outcome-aware):
#   1. A technically completed search (results OR truthfully empty) becomes the
#      current search context.
#   2. A provider degraded/failed/unconfigured must NOT overwrite the last
#      completed context.
#   3. A pending, unconfirmed role never becomes the current context.
#   4. A pure location refinement reuses the latest technically completed role.
#   5. Profile ranks but never rewrites an explicit current request.
# recent_search_role is written only on a completed outcome — never on
# bool(matches) alone.
# ===========================================================================
from unittest.mock import patch  # noqa: E402
from src.jsearch_client import FetchResult  # noqa: E402


class _OutcomeHarness(ChatHarness):
    """Drive the real path while dictating each search's *provider outcome*.

    ``outcomes`` is a per-call queue of:
      "RESULTS"          → real provider, ≥1 job   (COMPLETED_WITH_RESULTS)
      "EMPTY"            → real provider, 0 jobs    (COMPLETED_EMPTY)
      "DEGRADED"         → rate-limited, 0 jobs     (PROVIDER_DEGRADED, truthful)
      "NO_PROVIDER"      → nothing configured/ran   (PROVIDER_DEGRADED)
    The legacy scraper fallback is stubbed empty so EMPTY/DEGRADED outcomes are
    not masked by it.
    """

    def __init__(self, outcomes: list[str]) -> None:
        super().__init__()
        self._outcomes = list(outcomes)
        self._i = 0
        self.searched_locations: list[str] = []

    def _search(self, role: str, location: str = "", **_kw: Any) -> FetchResult:
        self.searched_roles.append(role)
        self.searched_locations.append(location or "")
        oc = self._outcomes[min(self._i, len(self._outcomes) - 1)]
        self._i += 1
        if oc == "RESULTS":
            return FetchResult(
                items=[{"title": role, "company": "ACME",
                        "apply_url": "https://acme.example/jobs/1", "location": "Dubai, UAE"}],
                provider="jsearch",
            )
        if oc == "EMPTY":
            return FetchResult(items=[], provider="jsearch")
        if oc == "DEGRADED":
            return FetchResult(items=[], provider="jsearch", rate_limited=True)
        if oc == "NO_PROVIDER":
            return FetchResult(items=[], provider="none", error="no_providers_configured")
        raise AssertionError(f"unknown outcome {oc!r}")

    def say(self, user_id: str, message: str, language=None):
        with patch("src.rico_repo_adapter.RicoSystem.run_for_profile",
                   return_value={"matches": []}):
            return super().say(user_id, message, language=language)


def _recent_role(h: ChatHarness, user: str = "u@test"):
    return (h._rctx.get(user) or {}).get("recent_search_role")


def _seed_outcome(h: _OutcomeHarness) -> None:
    h.seed("u@test", cv_status="parsed", cv_filename="cv.pdf",
           target_roles=[PROFILE_ROLE], skills=["hse", "environment", "sustainability"],
           years_experience=8, preferred_cities=["Dubai"], current_role="Environmental Manager")


# --- outcome classifier unit (never bool(matches) alone) --------------------
@pytest.mark.parametrize("kwargs,expected", [
    (dict(provider="jsearch", rate_limited=False, quota_exhausted=False, error="", matches=[{"t": 1}]), "COMPLETED_WITH_RESULTS"),
    (dict(provider="jsearch", rate_limited=False, quota_exhausted=False, error="", matches=[]), "COMPLETED_EMPTY"),
    (dict(provider="jsearch", rate_limited=True, quota_exhausted=False, error="", matches=[]), "PROVIDER_DEGRADED"),
    (dict(provider="jsearch", rate_limited=False, quota_exhausted=True, error="", matches=[]), "PROVIDER_DEGRADED"),
    (dict(provider="none", rate_limited=False, quota_exhausted=False, error="all_providers_unavailable", matches=[]), "PROVIDER_FAILED"),
    (dict(provider="none", rate_limited=False, quota_exhausted=False, error="no_providers_configured", matches=[]), "PROVIDER_DEGRADED"),
])
def test_classify_search_outcome_states(kwargs, expected):
    assert RicoChatAPI._classify_search_outcome(**kwargs) == expected
    assert RicoChatAPI._search_outcome_is_completed(expected) is expected.startswith("COMPLETED")


# --- Test 3: selecting Operations Manager becomes current even on 0 results --
def test_selected_operations_manager_becomes_current_even_zero_results():
    h = _OutcomeHarness(["RESULTS", "EMPTY"])   # B primary HSE=results, C ops=empty
    _seed_outcome(h)
    h.say("u@test", "Show me any HSE, sustainability, or operations manager jobs anywhere in the UAE")
    before = len(h.searched_roles)
    res = h.say("u@test", "Search operations manager")
    assert h.searched_roles[before:] == ["Operations Manager"]        # executed
    assert res.get("search_outcome") == "COMPLETED_EMPTY"             # truthful, technically completed
    assert _recent_role(h) == "Operations Manager"                    # became current context


# --- Test 4: selecting Sustainability becomes current even on 0 results ------
def test_selected_sustainability_becomes_current_even_zero_results():
    h = _OutcomeHarness(["RESULTS", "EMPTY"])
    _seed_outcome(h)
    h.say("u@test", "Show me any HSE, sustainability, or operations manager jobs anywhere in the UAE")
    before = len(h.searched_roles)
    res = h.say("u@test", "Search sustainability")
    assert h.searched_roles[before:] == ["Sustainability"]
    assert res.get("search_outcome") == "COMPLETED_EMPTY"
    assert _recent_role(h) == "Sustainability"


# --- Test 5: provider-degraded does NOT overwrite last completed role --------
def test_provider_degraded_does_not_overwrite_last_completed_role():
    h = _OutcomeHarness(["RESULTS", "DEGRADED"])   # C ops=results, D sustainability=degraded
    _seed_outcome(h)
    h.say("u@test", "Search operations manager")
    assert _recent_role(h) == "Operations Manager"
    res = h.say("u@test", "Search sustainability")
    # degradation is reported truthfully…
    assert res.get("type") == "provider_degraded"
    # …and the last technically completed role is preserved.
    assert _recent_role(h) == "Operations Manager"
    before = len(h.searched_roles)
    h.say("u@test", "Search all across the UAE")
    assert h.searched_roles[before:] == ["Operations Manager"]        # refinement reuses completed role


def test_no_provider_run_does_not_overwrite_last_completed_role():
    h = _OutcomeHarness(["RESULTS", "NO_PROVIDER"])
    _seed_outcome(h)
    h.say("u@test", "Search operations manager")
    assert _recent_role(h) == "Operations Manager"
    res = h.say("u@test", "Search sustainability")
    assert res.get("search_outcome") == "PROVIDER_DEGRADED"           # nothing actually ran
    assert _recent_role(h) == "Operations Manager"                    # context untouched


# --- Test 1 (continuity): explicit search overrides prior context, 0 results -
def test_explicit_completed_empty_search_overrides_prior_context():
    h = _OutcomeHarness(["RESULTS", "EMPTY"])
    _seed_outcome(h)
    h.say("u@test", "Search operations manager")                      # completed w/ results
    assert _recent_role(h) == "Operations Manager"
    res = h.say("u@test", "Find Environmental Manager jobs in the UAE")  # explicit, 0 results
    assert res.get("search_outcome") == "COMPLETED_EMPTY"
    assert _recent_role(h) == "Environmental Manager"                 # explicit request wins even empty


# --- Test 6: pending Accountant never becomes current, never profile ---------
def test_pending_accountant_never_becomes_current_context():
    h = _OutcomeHarness(["RESULTS", "RESULTS"])
    _seed_outcome(h)
    h.say("u@test", "Search operations manager")                      # current = Operations Manager
    assert _recent_role(h) == "Operations Manager"
    res = h.say("u@test", "Find accountant jobs in Dubai")            # off-profile → clarification
    assert res.get("type") == "clarification"
    pending = (h._rctx.get("u@test") or {}).get("_pending_role_confirmation")
    assert pending == {"role": "Accountant", "location": "Dubai"}     # pending, not executed
    assert _recent_role(h) == "Operations Manager"                    # NOT Accountant, NOT Environmental Manager
    before = len(h.searched_roles)
    h.say("u@test", "Search all across the UAE")
    assert h.searched_roles[before:] == ["Operations Manager"]        # refinement ignores the pending role


# --- Test 7: pure UAE refinement reuses the latest COMPLETED role ------------
def test_uae_refinement_reuses_latest_completed_role_location_only():
    h = _OutcomeHarness(["RESULTS", "RESULTS"])
    _seed_outcome(h)
    h.say("u@test", "Find HSE Manager jobs in Dubai")                 # completed, current = HSE Manager
    assert _recent_role(h) == "HSE Manager"
    before = len(h.searched_roles)
    res = h.say("u@test", "Search all across the UAE")
    assert h.searched_roles[before:] == ["HSE Manager"]              # same role, no new role invented
    assert h.searched_locations[before:] == [""]                    # nationwide (UAE default)
    assert "UAE" in (res.get("message") or "")


# --- Test 10: strong-title filter & adjacent-role opt-in gate unchanged ------
def test_strong_title_filter_and_adjacent_opt_in_unchanged():
    # Off-profile explicit role still triggers the opt-in confirmation gate
    # (adjacent-role opt-in policy preserved) — never auto-searched, never
    # rewritten to the profile role.
    h = _OutcomeHarness(["RESULTS"])
    _seed_outcome(h)
    res = h.say("u@test", "Find accountant jobs in Dubai")
    assert res.get("type") == "clarification"
    assert "accountant" in (res.get("message") or "").lower()
    assert "Environmental Manager" not in (res.get("message") or "")
    # The strong-title matcher itself is unchanged and still title-only.
    assert RicoChatAPI._job_matches_requested_domain(
        {"title": "Senior Accountant"}, {"accountant"}, set()) is True
    assert RicoChatAPI._job_matches_requested_domain(
        {"title": "Environmental Manager"}, {"accountant"}, set()) is False
