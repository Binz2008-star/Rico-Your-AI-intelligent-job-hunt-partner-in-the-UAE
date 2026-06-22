# -*- coding: utf-8 -*-
"""
Tests for degraded job-card UX when the provider cascade is exhausted.

When JSearch quota is spent (or every provider is degraded), Rico must NOT render
empty/dead-end "results" cards. It must show a safe fallback CTA instead:
try-again, search company site, Google/LinkedIn search, copy, save.

External boundaries are mocked — no live provider call is made.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.jsearch_client import FetchResult
from src.rico_chat_api import RicoChatAPI


def _profile(**overrides):
    data = {
        "has_cv": True,
        "target_roles": ["Technical Product Owner"],
        "skills": ["product"],
        "certifications": [],
        "years_experience": 8,
        "industries": ["tech"],
        "preferred_cities": ["Dubai"],
        "current_role": "Product Owner",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


@pytest.fixture()
def api(monkeypatch):
    _api = RicoChatAPI(persist=False)
    monkeypatch.setattr(_api, "_append_chat", lambda *a, **k: None)
    monkeypatch.setattr(_api, "_begin_job_search_operation", lambda *a, **k: {"operation_id": "op-x"})
    monkeypatch.setattr("src.rico_chat_api.mark_completed", lambda *a, **k: None)
    # Legacy scraper fallback must not invent results during these tests.
    _api.system = SimpleNamespace(run_for_profile=lambda *_a, **_k: {"matches": []})
    return _api


def test_quota_exhausted_renders_fallback_not_dead_end_cards(api, monkeypatch):
    monkeypatch.setattr(
        api, "_search_jsearch_meta",
        lambda role, location="": FetchResult(
            items=[], provider="none", quota_exhausted=True,
        ),
    )
    resp = api._target_role_search_response("u1", "Technical Product Owner", _profile())

    assert resp["type"] == "provider_degraded"
    assert resp["degraded"] is True
    assert resp["provider_state"] == "quota_exhausted"
    assert resp["matches"] == []
    assert resp["result_count"] == 0
    # Safe CTAs present; no dead-end job cards.
    actions = {o["action"] for o in resp["options"]}
    assert {"retry_search", "search_company_site", "save_role_search"} <= actions
    assert "linkedin" in resp["links"] and "google" in resp["links"]


def test_rate_limited_renders_fallback(api, monkeypatch):
    monkeypatch.setattr(
        api, "_search_jsearch_meta",
        lambda role, location="": FetchResult(items=[], provider="jsearch", rate_limited=True),
    )
    resp = api._target_role_search_response("u1", "Product Owner", _profile())
    assert resp["type"] == "provider_degraded"
    assert resp["provider_state"] == "rate_limited"


def test_all_providers_unavailable_renders_fallback(api, monkeypatch):
    monkeypatch.setattr(
        api, "_search_jsearch_meta",
        lambda role, location="": FetchResult(items=[], provider="none", error="all_providers_unavailable"),
    )
    resp = api._target_role_search_response("u1", "Product Owner", _profile())
    assert resp["type"] == "provider_degraded"
    assert resp["provider_state"] == "unavailable"


def test_healthy_empty_result_is_not_degraded(api, monkeypatch):
    """A genuine empty result from a HEALTHY provider must NOT trip degraded UX —
    it should still flow through the normal (broadened) job_matches path."""
    monkeypatch.setattr(
        api, "_search_jsearch_meta",
        lambda role, location="": FetchResult(items=[], provider="jsearch"),
    )
    resp = api._target_role_search_response("u1", "Product Owner", _profile())
    assert resp["type"] == "job_matches"
    assert resp.get("degraded") is None


def test_fallback_links_are_search_urls_not_scrapes(api, monkeypatch):
    monkeypatch.setattr(
        api, "_search_jsearch_meta",
        lambda role, location="": FetchResult(items=[], provider="none", quota_exhausted=True),
    )
    resp = api._target_role_search_response("u1", "Data Engineer", _profile())
    assert resp["links"]["google"].startswith("https://www.google.com/search?q=")
    assert resp["links"]["linkedin"].startswith("https://www.linkedin.com/jobs/search/")
