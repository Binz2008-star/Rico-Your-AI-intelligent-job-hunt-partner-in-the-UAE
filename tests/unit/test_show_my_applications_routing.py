"""
Tests for the "show my applications" explicit routing guard.

Bug: phrases like "show my applications", "my applications", "اعرض طلباتي", and "طلباتي"
were caught by the _is_list_followup block, which requires a prior lifecycle context.
Without that context the block fell through to job-search results or a wrong clarification.

Fix: _SHOW_MY_APPLICATIONS_RE guard fires before the list-followup block and routes
directly to _handle_application_tracking regardless of prior conversation context.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.rico_chat_api import RicoChatAPI


# ── Helpers ──────────────────────────────────────────────────────────────────

_APP_TRACKING_RESPONSE = {
    "type": "application_status",
    "message": "You have 2 tracked applications.",
    "applications": [],
    "stats": {"total": 2},
    "follow_up_needed": [],
}


def _profile(**overrides):
    data = {
        "has_cv": True,
        "target_roles": ["HSE Manager"],
        "skills": ["HSE", "NEBOSH"],
        "certifications": ["NEBOSH"],
        "years_experience": 5,
        "industries": ["construction"],
        "preferred_cities": ["Dubai"],
        "current_role": "HSE Officer",
        "telegram_username": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _make_api(monkeypatch):
    """RicoChatAPI with DB-touching methods stubbed out."""
    import src.rico_chat_api as mod

    mock_route = MagicMock()
    mock_route.tool_name = None
    mock_route.entities = {}
    mock_route.tool_args = {}
    mock_route.confirmation_prompt = None
    mock_route.source = "keyword"

    monkeypatch.setattr(mod, "get_profile", lambda uid: _profile())
    monkeypatch.setattr(mod, "_route", lambda *a, **kw: mock_route)
    monkeypatch.setattr(mod, "hf_ok", lambda: False)

    api = RicoChatAPI(persist=False)
    monkeypatch.setattr(api, "_append_chat", lambda *a, **kw: None)
    monkeypatch.setattr(
        api, "_handle_application_tracking", lambda *a, **kw: _APP_TRACKING_RESPONSE
    )
    return api


# ── _SHOW_MY_APPLICATIONS_RE unit tests ──────────────────────────────────────

@pytest.mark.parametrize("phrase", [
    # English — full variants
    "show my applications",
    "show my application",
    "list my applications",
    "list my application",
    "view my applications",
    "see my applications",
    "display my applications",
    "check my applications",
    "track my applications",
    "my applications",
    "my application",
    # Case insensitive
    "Show My Applications",
    "MY APPLICATIONS",
    "LIST MY APPLICATION",
    # Arabic variants
    "طلباتي",
    "اعرض طلباتي",
    "أعرض طلباتي",
    "عرض طلباتي",
    "اظهر طلباتي",
    "أظهر طلباتي",
    "ارني طلباتي",
    "أريني طلباتي",
])
def test_regex_matches(phrase):
    norm = RicoChatAPI._normalize_followup_phrase(phrase)
    assert RicoChatAPI._SHOW_MY_APPLICATIONS_RE.match(norm), (
        f"_SHOW_MY_APPLICATIONS_RE should match '{phrase}' (normalized: '{norm}')"
    )


@pytest.mark.parametrize("phrase", [
    # Real job titles — must NOT match
    "HSE Manager",
    "Environmental Manager",
    "find me applications for HSE Manager",
    # Generic job search
    "find me jobs",
    "show me jobs",
    # Bare forms without "my" — context-aware, stay in list-followup block
    "show applications",
    "list applications",
    "display applications",
    # Other list followups that should still go through list-followup block
    "list them",
    "show them",
    "show saved",
    "list saved",
    # Conversational
    "what are my applications?",
    "where are my applications",
    "how are my applications going",
    # Partial matches that should not fire
    "applications management",
    "my application strategy",
])
def test_regex_does_not_match(phrase):
    norm = RicoChatAPI._normalize_followup_phrase(phrase)
    assert not RicoChatAPI._SHOW_MY_APPLICATIONS_RE.match(norm), (
        f"_SHOW_MY_APPLICATIONS_RE should NOT match '{phrase}' (normalized: '{norm}')"
    )


# ── Routing: direct intents always go to application_tracking ────────────────

@pytest.mark.parametrize("phrase", [
    "show my applications",
    "list my applications",
    "my applications",
    "view my applications",
    "see my applications",
    "display my applications",
    "check my applications",
    "track my applications",
])
def test_english_phrases_route_to_application_tracking(monkeypatch, phrase):
    """All English explicit-application phrases reach _handle_application_tracking."""
    api = _make_api(monkeypatch)
    result = api._handle_active_user("u1", phrase)
    assert result["type"] == "application_status", (
        f"Expected application_status for '{phrase}', got {result.get('type')}"
    )


@pytest.mark.parametrize("phrase", [
    "طلباتي",
    "اعرض طلباتي",
    "أعرض طلباتي",
    "عرض طلباتي",
    "اظهر طلباتي",
])
def test_arabic_phrases_route_to_application_tracking(monkeypatch, phrase):
    """Arabic explicit-application phrases reach _handle_application_tracking."""
    api = _make_api(monkeypatch)
    result = api._handle_active_user("u2", phrase)
    assert result["type"] == "application_status", (
        f"Expected application_status for '{phrase}', got {result.get('type')}"
    )


def test_routing_fires_without_prior_lifecycle_context(monkeypatch):
    """Guard must work even when there is no prior application/lifecycle turn stored."""
    api = _make_api(monkeypatch)
    # Ensure there is no stored lifecycle or last-turn context.
    monkeypatch.setattr(api, "_resolve_lifecycle_query_for_followup", lambda uid: None)
    monkeypatch.setattr(api, "_get_recent_context", lambda uid: {})

    result = api._handle_active_user("u3", "show my applications")
    assert result["type"] == "application_status"


def test_routing_fires_even_after_job_search_turn(monkeypatch):
    """Guard must override cached job-search results — not show them instead."""
    api = _make_api(monkeypatch)
    # Simulate a prior job search with cached results.
    api.memory.set_context("u4", "recent_context", {
        "recent_search_matches": [
            {"title": "QHSE Manager", "company": "Acme", "location": "Dubai", "apply_url": ""}
        ],
        "recent_search_role": "QHSE Manager",
    })

    result = api._handle_active_user("u4", "show my applications")
    # Must route to application_status, NOT to job_matches with the cached results.
    assert result["type"] == "application_status"


# ── Non-regression: real job roles still work ────────────────────────────────

def test_hse_manager_search_is_unaffected(monkeypatch):
    """'HSE Manager' must not be caught by the applications guard."""
    import src.rico_chat_api as mod
    from src.jsearch_client import FetchResult

    mock_route = MagicMock()
    mock_route.tool_name = None
    mock_route.entities = {}
    mock_route.tool_args = {}
    mock_route.confirmation_prompt = None
    mock_route.source = "keyword"

    monkeypatch.setattr(mod, "get_profile", lambda uid: _profile())
    monkeypatch.setattr(mod, "_route", lambda *a, **kw: mock_route)
    monkeypatch.setattr(mod, "hf_ok", lambda: False)

    api = RicoChatAPI(persist=False)
    monkeypatch.setattr(api, "_append_chat", lambda *a, **kw: None)

    # Ensure application tracking is NOT called.
    tracking_called = []
    monkeypatch.setattr(
        api,
        "_handle_application_tracking",
        lambda *a, **kw: tracking_called.append(True) or _APP_TRACKING_RESPONSE,
    )

    # Stub job search so it doesn't hit the network.
    monkeypatch.setattr(
        api, "_search_jsearch_meta", lambda role: FetchResult(items=[])
    )

    api._handle_active_user("u5", "HSE Manager")
    assert not tracking_called, "Application tracking should not fire for a real job title"
