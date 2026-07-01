"""
tests/unit/test_profile_context_role_selection.py

PR C — production Tests 1 & 7.

T1: "Find UAE jobs that match my strongest CV profile."
    - never silently search a stale/leftover target_role (e.g. "Software Engineer"
      on an environmental CV);
    - a coherent single-track profile (Environmental / Sustainability / ESG / HSE)
      still searches its primary role — multiple roles in ONE family is not ambiguous;
    - genuinely different tracks (software AND environmental) ask the user to choose.

T7: "Search UAE jobs for Environmental Manager."
    - keep the exact requested role; never silently substitute "Environmental Officer";
    - adjacent roles are an opt-in permission ask, not an automatic broaden;
    - an authenticated CV user is never told to sign up / upload again.

Mocks/fixtures only — no real provider searches, no quota burn.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.agent.intelligence.normalizer import normalize_role
from src.rico_chat_api import RicoChatAPI


# ── fixtures ──────────────────────────────────────────────────────────────────

def _api() -> RicoChatAPI:
    return RicoChatAPI()


def _hse_single_profile() -> dict:
    return {
        "target_roles": ["HSE Officer"],
        "cv_status": "parsed", "cv_filename": "cv.pdf",
        "skills": ["hse", "compliance", "safety"], "years_experience": 5,
        "preferred_cities": ["Dubai"],
    }


def _stale_single_profile() -> dict:
    """Lone leftover 'Software Engineer' on an HSE/environmental CV → stale."""
    return {
        "target_roles": ["Software Engineer"],
        "cv_status": "parsed", "cv_filename": "cv.pdf",
        "skills": ["environmental compliance", "hse", "nebosh", "iso 14001"],
        "years_experience": 7, "preferred_cities": ["Abu Dhabi"],
    }


def _ambiguous_profile() -> dict:
    """Two genuinely different tracks (software + environmental) → ask."""
    return {
        "target_roles": ["Software Engineer", "Environmental Manager"],
        "cv_status": "parsed", "cv_filename": "cv.pdf",
        "skills": ["environmental compliance", "hse", "iso 14001"],
        "years_experience": 7, "preferred_cities": ["Dubai"],
    }


def _coherent_env_profile() -> dict:
    """Several roles, all one environmental track → search the primary role."""
    return {
        "target_roles": ["Environmental Manager", "Sustainability Manager", "ESG Manager"],
        "cv_status": "parsed", "cv_filename": "cv.pdf",
        "skills": ["ISO 14001", "environmental compliance"], "years_experience": 10,
        "preferred_cities": ["Dubai"],
    }


# ── 1. role-family grouping ───────────────────────────────────────────────────

@pytest.mark.parametrize("role,family", [
    ("Software Engineer", "software"),
    ("Backend Engineer", "software"),
    ("Environmental Manager", "env_hse"),
    ("Sustainability Manager", "env_hse"),
    ("ESG Manager", "env_hse"),
    ("HSE Officer", "env_hse"),
])
def test_role_family_buckets(role, family):
    assert _api()._role_family(role) == family


# ── 2. resolver logic (deterministic) ─────────────────────────────────────────

def test_single_aligned_role_resolves_to_single():
    role, _c, status = _api()._resolve_profile_search_role(_hse_single_profile())
    assert status == "single" and role == "HSE Officer"


def test_distinct_families_resolve_to_ambiguous():
    role, candidates, status = _api()._resolve_profile_search_role(_ambiguous_profile())
    assert status == "ambiguous"
    assert role is None
    assert "Software Engineer" in candidates and "Environmental Manager" in candidates


def test_lone_stale_role_resolves_to_stale():
    role, _c, status = _api()._resolve_profile_search_role(_stale_single_profile())
    assert status == "stale" and role == "Software Engineer"  # surfaced, never searched


def test_coherent_multi_role_same_family_searches_primary():
    # Regression guard for the giant-blob behaviour: one env track, search the first.
    role, candidates, status = _api()._resolve_profile_search_role(_coherent_env_profile())
    assert status == "single"
    assert role == "Environmental Manager"
    assert len(candidates) == 3


def test_no_candidates_when_all_excluded():
    role, candidates, status = _api()._resolve_profile_search_role(
        _hse_single_profile(), excluded_roles=["HSE Officer"]
    )
    assert status == "none" and candidates == []


def test_dedup_collapses_canonical_variants_keeps_raw_text():
    prof = {"target_roles": ["Product Owner", "PM"], "cv_status": "parsed", "skills": ["x"]}
    role, candidates, status = _api()._resolve_profile_search_role(prof)
    # "Product Owner" and "PM" both normalise to Product Manager → one track, raw kept.
    assert candidates == ["Product Owner"] and role == "Product Owner"


def test_role_is_cv_aligned_true_for_matching_role():
    assert _api()._role_is_cv_aligned(_hse_single_profile(), "HSE Officer") is True


def test_role_is_cv_aligned_false_for_stale_role():
    assert _api()._role_is_cv_aligned(_stale_single_profile(), "Software Engineer") is False


def test_no_cv_never_flags_stale():
    role, _c, status = _api()._resolve_profile_search_role({"target_roles": ["Software Engineer"]})
    assert status == "single"


# ── 3. T1 end-to-end via the chat handler ─────────────────────────────────────

def _run_chat(message: str, profile: dict):
    api = _api()
    search_mock = MagicMock(return_value={"type": "job_matches", "message": "searched", "success": True})
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


# Both phrasings exercise the fix: "what jobs match my profile" → profile_match;
# "Find UAE jobs that match my strongest CV profile" → explicit, role="UAE" → location guard.
_PHRASES = ["what jobs match my profile", "Find UAE jobs that match my strongest CV profile"]


@pytest.mark.parametrize("phrase", _PHRASES)
def test_t1_distinct_tracks_ask_and_do_not_search(phrase):
    result, search_mock, workflow_mock = _run_chat(phrase, _ambiguous_profile())
    assert result.get("type") == "clarification"
    assert search_mock.call_count == 0 and workflow_mock.call_count == 0
    labels = " ".join(o.get("label", "") for o in result.get("options", []))
    assert "Software Engineer" in labels and "Environmental Manager" in labels


@pytest.mark.parametrize("phrase", _PHRASES)
def test_t1_stale_role_not_searched_silently(phrase):
    result, search_mock, workflow_mock = _run_chat(phrase, _stale_single_profile())
    assert search_mock.call_count == 0 and workflow_mock.call_count == 0
    assert result.get("type") == "profile_role_suggestions"


def test_t1_single_aligned_role_searches_normally():
    result, search_mock, _ = _run_chat("what jobs match my profile", _hse_single_profile())
    assert search_mock.call_count == 1
    assert search_mock.call_args.args[1] == "HSE Officer"


def test_t1_coherent_multi_role_searches_primary():
    result, search_mock, _ = _run_chat("what jobs match my profile", _coherent_env_profile())
    assert search_mock.call_count == 1
    assert search_mock.call_args.args[1] == "Environmental Manager"


# ── 4. T7: exact role kept, adjacent is opt-in, no sign-up/upload ─────────────

def test_t7_normalizer_keeps_environmental_manager():
    assert normalize_role("Environmental Manager") == "Environmental Manager"


def test_t7_message_keeps_exact_role_with_matches():
    msg = _api()._build_role_search_message(
        "Environmental Manager", " in UAE", "",
        [{"title": "Env Mgr", "company": "X", "link": "http://x"}],
        {"fit_score": 0.4, "adjacent_roles": [{"role": "Environmental Officer"}]},
    )
    assert "Environmental Manager" in msg
    assert "I'll search those too" not in msg   # never a silent substitution
    assert "just say the word" in msg           # opt-in only
    assert "Environmental Officer" in msg        # offered, not swapped in


def test_t7_no_matches_offers_adjacent_as_permission():
    msg = _api()._build_role_search_message(
        "Environmental Manager", " in UAE", "", [],
        {"fit_score": 0.4, "adjacent_roles": [{"role": "Environmental Officer"}, {"role": "HSE Manager"}]},
    )
    assert "Environmental Manager" in msg
    assert "Want me to also look at" in msg
    assert "I'll search those too" not in msg


def test_t7_message_never_prompts_signup_or_upload():
    for top in ([], [{"title": "E", "company": "C", "link": "http://x"}]):
        msg = _api()._build_role_search_message(
            "Environmental Manager", " in UAE", "", top,
            {"fit_score": 0.4, "adjacent_roles": [{"role": "Environmental Officer"}]},
        ).lower()
        assert "sign up" not in msg and "signup" not in msg
        assert "upload your cv" not in msg and "register" not in msg


def test_t7_classified_role_search_uses_verbatim_role_not_taxonomy_alias():
    """_classified_role_search must pass the user's exact role text to
    _target_role_search_response, not the taxonomy canonical alias.

    Regression: resolve_taxonomy_role('Environmental Manager') -> 'Environmental Officer'.
    Before the fix, the search ran for 'Environmental Officer' silently.

    The bug path fires when the user's role is NOT already in target_roles
    (so the fuzzy early-exit is skipped) and the taxonomy classifier returns a
    different canonical alias.
    """
    api = _api()
    search_mock = MagicMock(return_value={"type": "job_matches", "message": "ok"})
    # Profile has HSE skills but target_roles is EMPTY — so the fuzzy-match
    # early exit (which correctly uses role_text) is skipped, and the call reaches
    # classify_role_candidate at line 18184.
    profile = {
        "target_roles": [],
        "cv_status": "parsed", "cv_filename": "cv.pdf",
        "skills": ["environmental compliance", "hse", "nebosh"],
        "years_experience": 7,
    }
    # classify_role_candidate returns profile_relevant with a *different* canonical alias.
    with (
        patch("src.rico_chat_api.classify_role_candidate",
              return_value=("profile_relevant", "Environmental Officer")),
        patch.object(api, "_target_role_search_response", search_mock),
        patch.object(api, "_get_recent_context", return_value={}),
        patch.object(api, "_store_recent_context", return_value=None),
        patch.object(api, "_append_chat", return_value=None),
    ):
        api._classified_role_search("u-test", "Environmental Manager", profile)

    assert search_mock.call_count == 1
    called_role = search_mock.call_args.args[1]
    assert called_role == "Environmental Manager", (
        f"Expected search for 'Environmental Manager' but got '{called_role}'. "
        "Taxonomy alias must not silently substitute the user's verbatim role."
    )
