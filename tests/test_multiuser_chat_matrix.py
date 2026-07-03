# -*- coding: utf-8 -*-
"""Automated multi-user chat regression matrix (TC-2 / TC-8 and friends).

Scalable, offline replacement for hand-driven production smoke: every case runs
the REAL ``RicoChatAPI.process_message`` path via :class:`tests.harness.ChatHarness`
across several seeded user states, with the DB, job provider, and AI provider all
stubbed. No manual login, no email verification, no live services, no credentials.

Covered:

  * TC-2  update target roles -> confirm ("yes") -> persisted -> propagates
  * TC-8  Richemont interview prep routes to ``interview_prep`` (never a company
          job search)
  * Control: "find jobs at ADNOC" stays a company job search
  * Regression: "what is my profile?" never triggers a job search
  * Regression: an Arabic target-role update never routes to a stale/unrelated
          job search and never silently persists the wrong role
  * Regression: a no-CV / no-profile user gets onboarding guidance, not a broken
          or stale authenticated state
  * Regression: a guest (no profile row) never receives authenticated results

The one non-test change this suite depends on is the fix to
``_build_proposed_changes`` (it must not ``vars()`` a slots ``ProfileContext``);
without it the profile-update confirmation crashes into the generic fallback.
``test_tc2_confirmation_prompt_is_not_the_generic_fallback`` guards that fix.
"""
from __future__ import annotations

import pytest

from tests.harness.chat_harness import ChatHarness


_GENERIC_FALLBACK = "i'm here to help with your uae job search"

# User states in which a target-role update should behave identically.
_TC2_STATES = ["stale_roles", "empty_roles", "cv_present", "english"]


def _run_tc2(harness: ChatHarness, user_id: str) -> dict:
    """Update -> confirm the ESG/Compliance target roles; return the 'yes' result."""
    step1 = harness.say(user_id, "update my target roles to ESG Manager and Compliance Manager")
    # Step 1 must render the real confirmation, not the swallowed-exception fallback.
    assert _GENERIC_FALLBACK not in (step1.get("message") or "").lower(), step1.get("message")
    step2 = harness.say(user_id, "yes")
    return step2


# ── TC-2: multi-role target update persists and propagates ─────────────────────

@pytest.mark.parametrize("state", _TC2_STATES)
def test_tc2_update_persists_both_roles(state):
    h = ChatHarness()
    uid = f"{state}@test"
    h.seed_state(uid, state)

    result = _run_tc2(h, uid)

    assert result.get("type") == "preferences_updated", result
    persisted = [r.lower() for r in (h.profile(uid).target_roles or [])]
    assert persisted == ["esg manager", "compliance manager"], persisted


@pytest.mark.parametrize("state", _TC2_STATES)
def test_tc2_next_search_propagates_to_new_roles_no_stale_leak(state):
    h = ChatHarness()
    uid = f"{state}@test"
    h.seed_state(uid, state)
    _run_tc2(h, uid)

    _role, candidates, _status = h.resolve_search_role(uid)
    picked = [str(c).lower() for c in candidates]
    # The next profile search must target the freshly-confirmed roles …
    assert "esg manager" in picked and "compliance manager" in picked, picked
    # … and must NOT leak the old stale role.
    assert "operations manager" not in picked, picked


def test_tc2_confirmation_prompt_is_not_the_generic_fallback():
    """Regression for the ``_build_proposed_changes`` slots-``ProfileContext`` crash.

    The profile-update confirmation must show the pending change and ask to
    confirm — not silently crash into the generic help fallback.
    """
    h = ChatHarness()
    uid = "confirm@test"
    h.seed_state(uid, "stale_roles")

    step1 = h.say(uid, "update my target roles to ESG Manager and Compliance Manager")

    assert step1.get("type") == "clarification", step1
    msg = (step1.get("message") or "").lower()
    assert _GENERIC_FALLBACK not in msg
    assert "esg manager" in msg and "compliance manager" in msg
    # No write happens until the user confirms.
    assert [r.lower() for r in (h.profile(uid).target_roles or [])] == ["operations manager"]


# ── TC-8: interview prep is grounded, never a company job search ───────────────

@pytest.mark.parametrize("state", ["stale_roles", "esg_compliance", "cv_present"])
def test_tc8_interview_prep_routes_to_interview_not_job_search(state):
    h = ChatHarness()
    uid = f"{state}@test"
    h.seed_state(uid, state)

    result = h.say(
        uid, "prepare me for an interview for the Retail Operations Manager role at Richemont"
    )

    assert result.get("type") == "interview_prep", result
    assert result.get("type") != "job_matches"
    assert result.get("company") == "Richemont"
    assert result.get("target_role") == "Retail Operations Manager"


# ── Control: genuine company search still works ────────────────────────────────

def test_control_company_search_still_returns_job_matches():
    h = ChatHarness()
    uid = "control@test"
    h.seed_state(uid, "cv_present")

    result = h.say(uid, "find jobs at ADNOC")

    assert result.get("type") == "job_matches", result
    assert result.get("company") == "ADNOC"


# ── Regression: self-profile query is never a job search ───────────────────────

def test_profile_query_does_not_trigger_job_search():
    h = ChatHarness()
    uid = "profile@test"
    h.seed_state(uid, "cv_present")

    result = h.say(uid, "what is my profile?")

    assert result.get("type") != "job_matches", result
    assert result.get("intent") not in ("search_jobs", "job_search", "job_search_explicit")


# ── Regression: Arabic target-role update must stay safe ───────────────────────

def test_arabic_target_role_update_does_not_route_to_stale_search():
    """An Arabic target-role update currently classifies as ``unknown`` and is
    handled conversationally. It must never be misread as a job search for a
    stale/unrelated role, and must never silently persist a role change."""
    h = ChatHarness()
    uid = "arabic@test"
    h.seed_state(uid, "arabic")
    before = list(h.profile(uid).target_roles or [])

    result = h.say(uid, "غير الوظائف المستهدفة إلى مدير الامتثال", language="ar")

    # Not misrouted into a job / company search …
    assert result.get("type") != "job_matches", result
    assert result.get("company") is None
    # … and no silent (unconfirmed) write to the profile.
    assert list(h.profile(uid).target_roles or []) == before


# ── Regression: no-CV / no-profile users get guidance, not a stale state ───────

def test_no_cv_user_gets_onboarding_guidance():
    h = ChatHarness()
    uid = "nocv@test"
    h.seed_state(uid, "no_cv")

    result = h.say(uid, "find me a job")

    # Graceful profile/onboarding guidance — asks for the missing profile data —
    # rather than a broken state or a stale/empty job search.
    assert result.get("type") in ("onboarding", "profile_incomplete", "onboarding_cta"), result
    assert result.get("type") != "job_matches"
    assert "target" in (result.get("message") or "").lower()


def test_guest_without_profile_gets_no_authenticated_results():
    """A guest (no profile row) must not receive authenticated-only results such
    as job matches or a 'preferences saved' confirmation."""
    h = ChatHarness()
    uid = "guest-session"  # never seeded -> get_profile returns None

    result = h.say(uid, "find me a job")

    assert result.get("type") not in ("job_matches", "preferences_updated", "profile_summary"), result
