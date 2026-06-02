"""
Tests for the self-reference role resolution guard in _classified_role_search.

When a user says "find live jobs for my target role" (or equivalent phrases),
the intent extractor yields extracted_role="my target role" which previously
hit the 'unknown role' branch. The fix adds a self-reference check at the top
of _classified_role_search that resolves to the user's saved profile roles.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.jsearch_client import FetchResult
from src.rico_chat_api import RicoChatAPI


_JOB_STUB = {
    "title": "HSE Manager",
    "company": "ACME Corp",
    "location": "Dubai, UAE",
    "link": "https://example.test/apply",
    "description": "Lead HSE operations.",
    "score": 88,
}


def _profile(**overrides):
    data = {
        "has_cv": True,
        "target_roles": ["HSE Manager", "QHSE Manager"],
        "skills": ["HSE", "NEBOSH"],
        "certifications": ["NEBOSH"],
        "years_experience": 8,
        "industries": ["construction"],
        "preferred_cities": ["Dubai"],
        "current_role": "HSE Officer",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _make_api(monkeypatch, jobs=None):
    """Return a RicoChatAPI with search and side-effects mocked out."""
    api = RicoChatAPI(persist=False)
    monkeypatch.setattr(api, "_append_chat", lambda *a, **kw: None)
    items = jobs if jobs is not None else [_JOB_STUB]
    monkeypatch.setattr(
        api,
        "_search_jsearch_meta",
        lambda role: FetchResult(items=items),
    )
    monkeypatch.setattr(
        api.system,
        "run_for_profile",
        lambda p: (_ for _ in ()).throw(AssertionError("fallback should not run")),
    )
    return api


# ── _SELF_REF_ROLE_RE coverage ──────────────────────────────────────────────

@pytest.mark.parametrize("phrase", [
    "my target role",
    "my target roles",
    "my saved role",
    "my saved roles",
    "my saved target role",
    "my saved target roles",
    # case-insensitive
    "My Target Role",
    "MY TARGET ROLES",
    # Arabic self-reference forms
    "دوري المستهدف",
    "أدواري المستهدفة",
    "وظيفتي المستهدفة",
    "وظيفتي المحفوظة",
])
def test_self_ref_regex_matches(phrase):
    assert RicoChatAPI._SELF_REF_ROLE_RE.match(phrase.strip()), \
        f"_SELF_REF_ROLE_RE should match '{phrase}'"


@pytest.mark.parametrize("phrase", [
    "HSE Manager",
    "Environmental Manager",
    "my manager",
    "my job",
    "my profile",
    "manager",
    "find me a role",
])
def test_self_ref_regex_does_not_match_real_roles(phrase):
    assert not RicoChatAPI._SELF_REF_ROLE_RE.match(phrase.strip()), \
        f"_SELF_REF_ROLE_RE should NOT match '{phrase}'"


# ── Behaviour: saved roles present ──────────────────────────────────────────

@pytest.mark.parametrize("phrase", [
    "my target role",
    "my target roles",
    "my saved role",
    "my saved target role",
    "my saved target roles",
])
def test_self_ref_with_saved_roles_triggers_job_search(monkeypatch, phrase):
    """All English self-reference phrases resolve to the first saved profile role."""
    api = _make_api(monkeypatch)
    response = api._classified_role_search("u1", phrase, _profile())

    assert response["type"] == "job_matches", (
        f"Expected job_matches for '{phrase}', got {response['type']}: {response.get('message')}"
    )
    # Message should reference the saved role (HSE Manager), not the raw phrase
    assert "my target role" not in response["message"].lower()
    assert "HSE Manager" in response["message"] or response["search_query"] == "HSE Manager"


def test_self_ref_uses_first_saved_role_when_multiple(monkeypatch):
    """With multiple saved roles, the first one is used for the search."""
    api = _make_api(monkeypatch)
    profile = _profile(target_roles=["HSE Manager", "QHSE Manager"])
    response = api._classified_role_search("u2", "my target role", profile)

    assert response["type"] == "job_matches"
    assert response["search_query"] == "HSE Manager"


def test_self_ref_message_includes_saved_role_prefix(monkeypatch):
    """Response message includes the 'Searching based on your saved target role:' prefix."""
    api = _make_api(monkeypatch)
    response = api._classified_role_search("u3", "my target role", _profile())

    assert "Searching based on your saved target role:" in response["message"]


# ── Behaviour: no saved roles ────────────────────────────────────────────────

def test_self_ref_with_no_saved_roles_returns_clarification(monkeypatch):
    """If no target_roles are saved, Rico asks user to set one instead of erroring."""
    api = _make_api(monkeypatch, jobs=[])
    profile = _profile(target_roles=[])
    response = api._classified_role_search("u4", "my target role", profile)

    assert response["type"] == "clarification"
    msg = response["message"].lower()
    assert "target role" in msg or "profile" in msg


def test_self_ref_no_saved_roles_does_not_call_search(monkeypatch):
    """Search must NOT be called when there are no saved roles."""
    api = RicoChatAPI(persist=False)
    monkeypatch.setattr(api, "_append_chat", lambda *a, **kw: None)
    search_called = []
    monkeypatch.setattr(api, "_search_jsearch_meta", lambda r: search_called.append(r) or FetchResult())

    profile = _profile(target_roles=[])
    api._classified_role_search("u5", "my target role", profile)

    assert not search_called, "search should not be called when no roles saved"


# ── Behaviour: normal explicit roles still work ───────────────────────────────

def test_hse_manager_direct_search_still_works(monkeypatch):
    """'HSE Manager' (same as saved role) still resolves correctly via fuzzy match."""
    api = _make_api(monkeypatch)
    response = api._classified_role_search("u7", "HSE Manager", _profile())

    assert response["type"] == "job_matches"


# ── Arabic self-reference ─────────────────────────────────────────────────────

def test_arabic_self_ref_with_saved_roles(monkeypatch):
    """Arabic self-reference phrase resolves to first saved role."""
    api = _make_api(monkeypatch)
    response = api._classified_role_search("u8", "دوري المستهدف", _profile())

    assert response["type"] == "job_matches"
    assert response["search_query"] == "HSE Manager"


def test_arabic_self_ref_no_saved_roles_returns_clarification(monkeypatch):
    """Arabic self-reference with no saved roles returns clarification."""
    api = _make_api(monkeypatch, jobs=[])
    profile = _profile(target_roles=[])
    response = api._classified_role_search("u9", "وظيفتي المستهدفة", profile)

    assert response["type"] == "clarification"
