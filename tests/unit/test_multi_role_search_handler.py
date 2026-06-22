# -*- coding: utf-8 -*-
"""
Handler-level regression tests for the multi-role search flow.

Before the fix, the production prompt below produced:
    "I do not recognize 'Technical Product Owner, Product Owner, … roles in UAE …'
     as a job role."

After the fix, RicoChatAPI._multi_role_search_response recognises every role,
searches the primary (first) role via the live search path, surfaces the rest as
one-tap alternatives, and persists the "do not search …" exclusion guard for the
session. No live search provider is contacted — _target_role_search_response is
mocked.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.rico_chat_api import RicoChatAPI


PROD_PROMPT = (
    "Search for Technical Product Owner, Product Owner, Technical Project Manager, "
    "Digital Transformation Manager, and Operations Technology Manager roles in UAE. "
    "Do not search pure Software Engineer, Full Stack, Backend, Golang, or Machine "
    "Learning roles unless I explicitly ask for coding jobs."
)

ROLES = [
    "Technical Product Owner",
    "Product Owner",
    "Technical Project Manager",
    "Digital Transformation Manager",
    "Operations Technology Manager",
]
EXCLUSIONS = ["Software Engineer", "Full Stack", "Backend", "Golang", "Machine Learning"]


def _profile(**overrides):
    data = {
        "has_cv": True,
        "target_roles": [],
        "skills": ["product management", "agile"],
        "certifications": [],
        "years_experience": 8,
        "industries": ["technology"],
        "current_role": "Product Owner",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


@pytest.fixture()
def api(monkeypatch):
    _api = RicoChatAPI(persist=False)
    monkeypatch.setattr(_api, "_append_chat", lambda *a, **k: None)
    # Dict-backed recent-context so the exclusion guard can be asserted.
    store: dict = {}
    monkeypatch.setattr(_api, "_get_recent_context", lambda uid: store)
    monkeypatch.setattr(_api, "_store_recent_context", lambda uid, ctx: store.update(ctx))
    _api._ctx_store = store  # expose for assertions
    return _api


def _canned_search(captured=None):
    """Return a stand-in for _target_role_search_response that records its role arg
    into the supplied ``captured`` dict."""
    captured = captured if captured is not None else {}
    def _impl(user_id, role, profile, **kwargs):
        captured["role"] = role
        captured["location"] = kwargs.get("location", "")
        return {
            "type": "job_matches",
            "message": f"Found 2 live matches for {role}.",
            "matches": [{"title": role, "company": "ACME"}],
            "result_count": 2,
        }
    return _impl


def test_primary_role_is_searched_first(api, monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(api, "_target_role_search_response", _canned_search(captured))

    resp = api._multi_role_search_response(
        "u1", ROLES, _profile(), excluded_roles=EXCLUSIONS, location="",
    )

    assert captured["role"] == "Technical Product Owner"
    assert resp["type"] == "job_matches"
    assert resp["primary_role"] == "Technical Product Owner"


def test_response_never_says_do_not_recognize(api, monkeypatch):
    monkeypatch.setattr(api, "_target_role_search_response", _canned_search())
    resp = api._multi_role_search_response("u1", ROLES, _profile(), excluded_roles=EXCLUSIONS)
    assert "do not recognize" not in resp["message"].lower()
    assert "do not recognise" not in resp["message"].lower()


def test_all_recognized_roles_listed_in_message(api, monkeypatch):
    monkeypatch.setattr(api, "_target_role_search_response", _canned_search())
    resp = api._multi_role_search_response("u1", ROLES, _profile(), excluded_roles=EXCLUSIONS)
    for role in ROLES:
        assert role in resp["message"]
    assert resp["recognized_roles"] == ROLES


def test_alternate_roles_offered_as_options(api, monkeypatch):
    monkeypatch.setattr(api, "_target_role_search_response", _canned_search())
    resp = api._multi_role_search_response("u1", ROLES, _profile(), excluded_roles=EXCLUSIONS)
    option_actions = [o["action"] for o in resp.get("options", [])]
    # Every non-primary role is a re-prioritise option; the primary is not.
    assert option_actions == ROLES[1:]
    assert resp["next_action"] == "select_role_to_search"


def test_exclusion_guard_persisted(api, monkeypatch):
    monkeypatch.setattr(api, "_target_role_search_response", _canned_search())
    api._multi_role_search_response("u1", ROLES, _profile(), excluded_roles=EXCLUSIONS)
    assert api._ctx_store.get("excluded_roles") == EXCLUSIONS
    assert api._ctx_store.get("multi_role_candidates") == ROLES


def test_excluded_roles_surfaced_in_message(api, monkeypatch):
    monkeypatch.setattr(api, "_target_role_search_response", _canned_search())
    resp = api._multi_role_search_response("u1", ROLES, _profile(), excluded_roles=EXCLUSIONS)
    for excl in EXCLUSIONS:
        assert excl in resp["message"]


def test_recognized_candidate_searched_directly_on_followup(api, monkeypatch):
    """After the multi-role turn, tapping/repeating one role searches it directly
    rather than bouncing through taxonomy as an unknown role."""
    captured: dict = {}
    monkeypatch.setattr(api, "_target_role_search_response", _canned_search(captured))
    # Seed the session context as the multi-role turn would have.
    api._ctx_store["multi_role_candidates"] = ROLES

    resp = api._classified_role_search("u1", "Product Owner", _profile())

    assert captured["role"] == "Product Owner"
    assert resp["type"] == "job_matches"
    assert "do not recognize" not in (resp.get("message") or "").lower()
