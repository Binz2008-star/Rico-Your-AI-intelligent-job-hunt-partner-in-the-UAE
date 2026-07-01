"""
tests/unit/test_profile_search_intent_routing.py

fix/profile-search-intent-routing — CV/profile-based job search phrasing was
misrouted before this fix in three independent ways, all reproduced here and
proven fixed:

Bug A: `_classified_role_search`'s location guard had no handler for
    `_resolve_profile_search_role` status "none" (empty target_roles) — it fell
    through to a generic "What role? Upload CV to auto-detect role" clarification
    even when a CV was already parsed.
Bug B: `job_search_explicit`'s no-extracted-role fallback blindly searched
    `target_roles[0]` via the legacy workflow with zero staleness check,
    bypassing the T1 stale-role fix entirely for phrasing that doesn't produce
    an extracted_role (e.g. "Find jobs from my CV").
Bug C: the intent classifier had no rule routing CV/profile self-reference
    phrasing to `job_search_profile_match` before `_JOB_SEARCH_EXPLICIT_RE`
    captured it — extracting garbage "roles" like "UAE" or "my strongest
    profile" and either mis-searching or refusing to recognize them.

Mocks/fixtures only — no real provider searches, no quota burn.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.agent.intelligence.intent_classifier import classify_intent
from src.rico_chat_api import RicoChatAPI


# ── fixtures: the 4 acceptance-criteria profile scenarios ────────────────────

def _profile_cv_no_target_roles_key() -> dict:
    """Scenario A: CV parsed, `target_roles` key absent entirely."""
    return {
        "cv_status": "parsed", "cv_filename": "cv.pdf",
        "skills": ["environmental compliance", "hse", "nebosh", "iso 14001"],
        "years_experience": 7, "preferred_cities": ["Abu Dhabi"],
    }


def _profile_cv_target_roles_empty() -> dict:
    """Scenario B: CV parsed, `target_roles` explicitly an empty list."""
    return {
        "target_roles": [],
        "cv_status": "parsed", "cv_filename": "cv.pdf",
        "skills": ["environmental compliance", "hse", "nebosh", "iso 14001"],
        "years_experience": 7, "preferred_cities": ["Abu Dhabi"],
    }


def _profile_cv_stale_target_role() -> dict:
    """Scenario C: CV parsed, saved role no longer matches the CV."""
    return {
        "target_roles": ["Software Engineer"],
        "cv_status": "parsed", "cv_filename": "cv.pdf",
        "skills": ["environmental compliance", "hse", "nebosh", "iso 14001"],
        "years_experience": 7, "preferred_cities": ["Abu Dhabi"],
    }


def _profile_no_cv() -> dict:
    """Scenario D: no CV uploaded/parsed at all."""
    return {"target_roles": [], "cv_status": None, "skills": []}


def _profile_cv_valid_single_role() -> dict:
    """Happy-path regression guard: one CV-aligned saved role, not stale."""
    return {
        "target_roles": ["HSE Officer"],
        "cv_status": "parsed", "cv_filename": "cv.pdf",
        "skills": ["hse", "compliance", "safety"], "years_experience": 5,
        "preferred_cities": ["Dubai"],
    }


SCENARIOS = {
    "A_cv_no_target_roles_key": _profile_cv_no_target_roles_key,
    "B_cv_target_roles_empty": _profile_cv_target_roles_empty,
    "C_cv_stale_target_role": _profile_cv_stale_target_role,
    "D_no_cv": _profile_no_cv,
}

ACCEPTANCE_PHRASES = [
    "Find UAE jobs that match my strongest CV profile",
    "Find jobs matching my CV",
    "Search jobs using my profile",
    "Find jobs for my strongest profile",
    "Find jobs from my CV",
    "Find UAE jobs from my CV",
    "Search jobs based on my CV",
    "Find UAE jobs that match my CV",
    "Search jobs using my CV",
]


def _run_chat(message: str, profile: dict):
    api = RicoChatAPI()
    search_mock = MagicMock(
        return_value={"type": "job_matches", "message": "searched ok", "success": True}
    )
    workflow_mock = MagicMock(return_value={"status": "completed", "matches": []})
    with (
        patch("src.rico_chat_api.get_profile", return_value=profile),
        patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
        patch("src.rico_chat_api.upsert_profile", side_effect=lambda uid, upd: {**profile, **upd}),
        patch.object(api, "_get_recent_context", return_value={}),
        patch.object(api, "_target_role_search_response", search_mock),
    ):
        api.system = MagicMock()
        api.system.run_for_profile = workflow_mock
        result = api._handle_active_user("u-test", message)
    return result, search_mock, workflow_mock


# ── 1. Classifier-level (Bug C): CV/profile self-reference routes correctly ──

@pytest.mark.parametrize("phrase", ACCEPTANCE_PHRASES)
def test_cv_profile_reference_classifies_as_profile_match(phrase):
    result = classify_intent(phrase, has_cv_profile=True)
    assert result.intent == "job_search_profile_match", (
        f"{phrase!r} should route to job_search_profile_match, got {result.intent!r} "
        f"(extracted_role={result.extracted_role!r})"
    )


@pytest.mark.parametrize("phrase", [
    "find HSE Manager jobs that match my CV",
    "find jobs for Environmental Compliance Officer",
    "find Software Engineer jobs in Dubai",
])
def test_genuine_explicit_role_still_wins_over_cv_reference(phrase):
    """A real job title mentioned alongside (or without) a CV reference must
    still take the explicit-role path — the Bug C fix must not swallow these."""
    result = classify_intent(phrase, has_cv_profile=True)
    assert result.intent == "job_search_explicit"
    assert result.extracted_role not in (None, "", "UAE")


def test_cv_profile_reference_without_cv_profile_flag_not_forced():
    """Without has_cv_profile=True, the new routing rule must not fire — there
    is no profile to match against."""
    result = classify_intent("Find jobs matching my CV", has_cv_profile=False)
    assert result.intent != "job_search_profile_match"


# ── 2. End-to-end matrix: acceptance criteria 1-4, 6 ─────────────────────────

@pytest.mark.parametrize("phrase", ACCEPTANCE_PHRASES)
@pytest.mark.parametrize("scenario_name", ["A_cv_no_target_roles_key", "B_cv_target_roles_empty", "C_cv_stale_target_role"])
def test_cv_present_scenarios_search_cv_evidenced_role_never_stale_or_location(phrase, scenario_name):
    """Criteria 1, 2, 3, 4: with a CV present (regardless of target_roles state),
    every acceptance phrase must search a real CV-evidenced role — never the
    stale saved role, never "UAE" as a literal role, never asking to upload a
    CV that already exists."""
    profile = SCENARIOS[scenario_name]()
    result, search_mock, workflow_mock = _run_chat(phrase, profile)

    assert search_mock.call_count == 1, (
        f"{phrase!r} / {scenario_name}: expected exactly one CV-evidenced search, "
        f"got {search_mock.call_count} (workflow calls={workflow_mock.call_count}, "
        f"response type={result.get('type')!r})"
    )
    searched_role = search_mock.call_args.args[1]
    assert searched_role not in ("UAE", "Software Engineer", "my strongest profile"), (
        f"{phrase!r} / {scenario_name}: searched garbage/stale role {searched_role!r}"
    )
    # Never a bogus "upload CV" prompt when a CV already exists.
    options = result.get("options") or []
    assert not any(
        isinstance(o, dict) and o.get("action") == "upload_cv" for o in options
    ), f"{phrase!r} / {scenario_name}: offered to upload a CV that already exists"


@pytest.mark.parametrize("phrase", ACCEPTANCE_PHRASES)
def test_no_cv_scenario_never_searches_and_asks_appropriately(phrase):
    """Criterion 6 (no-CV branch): with no CV, Rico must not run a search, and
    must not produce the raw taxonomy-classifier refusal message."""
    profile = SCENARIOS["D_no_cv"]()
    result, search_mock, workflow_mock = _run_chat(phrase, profile)
    assert search_mock.call_count == 0
    assert workflow_mock.call_count == 0
    msg = (result.get("message") or "").lower()
    assert "i do not recognize" not in msg, (
        f"{phrase!r} (no CV): got raw taxonomy refusal: {result.get('message')!r}"
    )


# ── 3. Bug B direct regression: stale target_roles must never be searched ───

@pytest.mark.parametrize("phrase", ["Find jobs from my CV", "Search jobs based on my CV"])
def test_stale_target_role_never_searched_first(phrase):
    """These two phrases extract no explicit role and, before this fix, fell
    into job_search_explicit's blind `system.run_for_profile(target_roles[0])`
    fallback with zero staleness check (Bug B)."""
    profile = _profile_cv_stale_target_role()
    result, search_mock, workflow_mock = _run_chat(phrase, profile)
    assert workflow_mock.call_count == 0, (
        f"{phrase!r}: blindly ran the legacy workflow on the stale role "
        "instead of checking CV alignment first"
    )
    assert search_mock.call_count == 1
    assert search_mock.call_args.args[1] == "Environmental Compliance Officer"


# ── 4. Criterion 5: "my strongest profile" must never be an unrecognised role ─

def test_my_strongest_profile_never_unrecognised_with_cv():
    profile = _profile_cv_stale_target_role()
    result, search_mock, _ = _run_chat("Find jobs for my strongest profile", profile)
    msg = result.get("message", "")
    assert "I do not recognize 'my strongest profile'" not in msg
    assert search_mock.call_count == 1


def test_my_strongest_profile_no_cv_asks_for_more_info_not_unrecognised():
    profile = _profile_no_cv()
    result, search_mock, _ = _run_chat("Find jobs for my strongest profile", profile)
    assert search_mock.call_count == 0
    msg = result.get("message", "")
    assert "I do not recognize 'my strongest profile'" not in msg


# ── 5. Criterion 7: existing single valid-role happy path is unchanged ──────

def test_valid_single_role_happy_path_unchanged_no_cv_reference():
    """A phrase with NO CV/profile self-reference (so Fix C's classifier
    override never engages) and a valid, non-stale saved role must still
    reach job_search_explicit's legacy `system.run_for_profile` fallback
    exactly as before this fix — Fix B only adds a staleness check ahead of
    it, it must not touch the "single" (valid role) case."""
    profile = _profile_cv_valid_single_role()
    result, search_mock, workflow_mock = _run_chat("Find me some jobs", profile)
    assert workflow_mock.call_count == 1, "single-role happy path must still use the legacy workflow"
    assert search_mock.call_count == 0


def test_valid_single_role_with_cv_reference_still_searches_correct_role():
    """A CV/profile self-reference phrase ("Find jobs from my CV") with a
    valid, non-stale saved role now correctly routes through
    job_search_profile_match (Fix C) instead of job_search_explicit's
    fallback ladder. This is an intentional, verified consequence of Fix C —
    job_search_profile_match's "single" branch already used
    _target_role_search_response (the same modern provider-cascade search
    mechanism used everywhere else) before this PR; only the routing changed,
    not the search behavior. The important invariant is that the correct,
    CV-aligned role gets searched exactly once."""
    profile = _profile_cv_valid_single_role()
    result, search_mock, workflow_mock = _run_chat("Find jobs from my CV", profile)
    assert search_mock.call_count == 1
    assert search_mock.call_args.args[1] == "HSE Officer"


# ── 6. Criterion 8: internal status labels must never leak to the user ──────

@pytest.mark.parametrize("phrase", ACCEPTANCE_PHRASES)
@pytest.mark.parametrize("scenario_name", ["A_cv_no_target_roles_key", "B_cv_target_roles_empty", "C_cv_stale_target_role"])
def test_internal_status_labels_never_leak_to_user(phrase, scenario_name):
    profile = SCENARIOS[scenario_name]()
    result, _, _ = _run_chat(phrase, profile)
    msg = (result.get("message") or "")
    for leaked in ("STALE", "NEEDS_REFRESH", "LOW_CONFIDENCE_ROLE", "status=none", "status=stale"):
        assert leaked not in msg, f"{phrase!r} / {scenario_name}: internal label {leaked!r} leaked to user"
