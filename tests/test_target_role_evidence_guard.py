"""
#732 — Rico must not over-commit to a coding/"Developer" target role without
evidence.

The fix is in ``RicoChatAPI._role_is_cv_aligned``: when the CV yields no role
evidence at all, a software/coding target ("Developer", "Software Engineer") is
treated as NOT aligned, so ``_resolve_profile_search_role`` returns "stale" and
the caller surfaces CV-aligned suggestions / a clarification instead of silently
asserting and searching an unevidenced "Developer". Non-coding tracks keep the
lenient fallback so an ordinary data gap never blocks a legitimate search.

No AI/provider/DB calls — role suggestions are mocked for determinism, with one
end-to-end case exercising the real role suggester.
"""
from __future__ import annotations

from unittest.mock import patch

from src.rico_chat_api import RicoChatAPI


def _api() -> RicoChatAPI:
    return RicoChatAPI(persist=False)


# ── _role_is_cv_aligned ───────────────────────────────────────────────────────

def _aligned(api, role, suggestions, profile=None):
    with patch.object(api, "_generate_role_suggestions", return_value=suggestions):
        return api._role_is_cv_aligned(profile or {"skills": ["x"]}, role)


def test_unevidenced_developer_not_aligned():
    """No CV evidence + coding target → NOT aligned (the #732 over-commit fix)."""
    assert _aligned(_api(), "Developer", []) is False
    assert _aligned(_api(), "Software Engineer", []) is False
    assert _aligned(_api(), "Backend Developer", []) is False


def test_unevidenced_non_coding_role_stays_lenient():
    """No CV evidence + non-coding target → still aligned (no regression)."""
    assert _aligned(_api(), "Marketing Manager", []) is True
    assert _aligned(_api(), "HSE Manager", []) is True
    assert _aligned(_api(), "Environmental Specialist", []) is True


def test_evidenced_developer_is_aligned():
    """A coding suggestion from the CV makes the saved coding role aligned."""
    sugg = [{"label": "Software Developer"}, {"label": "Backend Engineer"}]
    assert _aligned(_api(), "Developer", sugg) is True


def test_developer_not_aligned_when_suggestions_are_other_track():
    """CV evidence exists but points elsewhere → coding role not aligned (pre-existing)."""
    sugg = [{"label": "Environmental Manager"}, {"label": "Sustainability Lead"}]
    assert _aligned(_api(), "Developer", sugg) is False


def test_blank_role_never_aligned():
    assert _aligned(_api(), "", []) is False


# ── _resolve_profile_search_role integration ──────────────────────────────────

def _resolve(api, profile):
    return api._resolve_profile_search_role(profile)


def test_cv_present_unevidenced_developer_is_stale():
    """Acceptance #1: CV on file but no coding evidence + saved 'Developer'
    → 'stale' (Rico offers CV-aligned options, never asserts Developer)."""
    api = _api()
    profile = {"target_roles": ["Developer"], "cv_filename": "cv.pdf"}
    with patch.object(api, "_generate_role_suggestions", return_value=[]):
        role, candidates, status = _resolve(api, profile)
    assert status == "stale"
    assert role == "Developer"  # surfaced as the stale target, not searched


def test_cv_absent_saved_developer_is_used():
    """Acceptance #2 / CV-absent: with no CV, alignment isn't consulted — the
    saved target role is used as-is."""
    api = _api()
    profile = {"target_roles": ["Developer"]}  # no cv_filename/skills/years markers
    role, candidates, status = _resolve(api, profile)
    assert status == "single"
    assert role == "Developer"


def test_cv_present_evidenced_developer_is_used():
    """Acceptance #2 / saved role present: a coding CV makes the saved coding
    role aligned → searched (status 'single')."""
    api = _api()
    profile = {"target_roles": ["Developer"], "cv_filename": "cv.pdf"}
    sugg = [{"label": "Software Developer"}]
    with patch.object(api, "_generate_role_suggestions", return_value=sugg):
        role, candidates, status = _resolve(api, profile)
    assert status == "single"
    assert role == "Developer"


def test_cv_present_unevidenced_non_coding_role_still_searched():
    """No regression: a non-coding saved role with a thin CV stays 'single'."""
    api = _api()
    profile = {"target_roles": ["Marketing Manager"], "cv_filename": "cv.pdf"}
    with patch.object(api, "_generate_role_suggestions", return_value=[]):
        role, candidates, status = _resolve(api, profile)
    assert status == "single"
    assert role == "Marketing Manager"


def test_real_suggester_environmental_cv_does_not_push_developer():
    """End-to-end with the real role suggester: an environmental CV + a leftover
    'Developer' target must not be treated as aligned."""
    api = _api()
    profile = {
        "target_roles": ["Developer"],
        "cv_filename": "cv.pdf",
        "skills": ["NEBOSH", "ISO 14001", "environmental auditing", "sustainability"],
        "industries": ["Oil & Gas"],
        "years_experience": 8,
    }
    role, candidates, status = _resolve(api, profile)
    assert status == "stale"
    assert role == "Developer"


# ── _handle_delegated_decision — #732 career-steering gap ────────────────────
# When user says "I don't know, advise me" Rico must NOT auto-search an
# unevidenced coding role. The delegated-decision handler must check alignment
# via _resolve_profile_search_role before asserting the saved role.

def test_delegated_decision_stale_developer_does_not_auto_search():
    """CV present + Developer saved but no coding evidence → role suggestions,
    NOT job_search_explicit (#732 career-steering gap)."""
    api = _api()
    profile = {
        "target_roles": ["Developer"],
        "cv_status": "parsed",
        "cv_filename": "cv.pdf",
        "skills": ["NEBOSH", "ISO 14001", "environmental auditing"],
    }
    with patch.object(api, "_generate_role_suggestions", return_value=[]):
        result = api._handle_delegated_decision("user1", profile, "ارجوك انصحني انا لا اعلم")
    assert result["type"] == "profile_role_suggestions"
    assert result.get("next_action") != "search_jobs"


def test_delegated_decision_evidenced_developer_proceeds_to_search():
    """CV present + Developer saved + coding evidence → job_search_explicit (no regression)."""
    api = _api()
    profile = {
        "target_roles": ["Developer"],
        "cv_status": "parsed",
        "cv_filename": "cv.pdf",
        "skills": ["Python", "Django", "REST APIs"],
    }
    coding_sugg = [{"label": "Software Developer"}, {"label": "Backend Engineer"}]
    with patch.object(api, "_generate_role_suggestions", return_value=coding_sugg):
        result = api._handle_delegated_decision("user1", profile, "you decide for me")
    assert result["type"] == "job_search_explicit"
    assert result["chosen_role"] == "Developer"
    assert result["next_action"] == "search_jobs"


def test_delegated_decision_no_cv_uses_saved_target_role():
    """No CV → alignment cannot be assessed; saved role used as-is (no regression)."""
    api = _api()
    profile = {"target_roles": ["Developer"]}
    result = api._handle_delegated_decision("user1", profile, "decide for me")
    assert result["type"] == "job_search_explicit"
    assert result["chosen_role"] == "Developer"


def test_delegated_decision_no_target_roles_returns_clarification():
    """No target roles, no CV → clarification asking for context (no regression)."""
    api = _api()
    result = api._handle_delegated_decision("user1", {}, "I don't know what to do")
    assert result["type"] == "clarification"
    assert result.get("next_action") == "need_profile_for_delegation"


def test_delegated_decision_stale_non_coding_role_is_lenient():
    """Non-coding stale role does NOT trigger suggestions — lenient fallback (#732 guard
    is coding-specific; non-coding roles like Marketing Manager keep the search path)."""
    api = _api()
    profile = {
        "target_roles": ["Marketing Manager"],
        "cv_status": "parsed",
        "cv_filename": "cv.pdf",
        "skills": ["campaign management", "brand strategy"],
    }
    with patch.object(api, "_generate_role_suggestions", return_value=[]):
        result = api._handle_delegated_decision("user1", profile, "choose for me")
    assert result["type"] == "job_search_explicit"
    assert result["chosen_role"] == "Marketing Manager"
