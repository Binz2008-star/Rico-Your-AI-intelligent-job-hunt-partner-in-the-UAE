# -*- coding: utf-8 -*-
"""Requested-role relevance floor for explicit-title chat search.

An explicit-title search ("ESG Manager jobs") must rank and filter by the role
the user ASKED FOR — not by whatever roles are saved on their profile. Provider
noise from unrelated families must never be shown as a match, and when nothing
clears the relevance floor Rico must give an honest "no strong matches / broaden"
response instead of a fabricated "N matches" card.

Product-generalization: every case here uses SYNTHETIC users and SYNTHETIC jobs.
The behavior is global and user-agnostic — nothing is tuned to any real account,
profile, saved role list, or sampled dataset. External providers are mocked; no
live JSearch/DB/LLM call is made.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.jsearch_client import FetchResult
from src.rico_chat_api import RicoChatAPI
from src.services.role_relevance import (
    RELEVANCE_FLOOR,
    score_role_relevance,
)


def _job(title: str, company: str = "Synthetic Co", **extra):
    data = {
        "title": title,
        "company": company,
        "location": "Dubai, UAE",
        "description": title,
        "job_apply_link": "https://example.com/apply",
    }
    data.update(extra)
    return data


def _profile(**overrides):
    """Synthetic profile. Defaults model a STALE profile whose saved roles are
    unrelated to the explicit query — the exact shape that used to leak noise."""
    data = {
        "has_cv": True,
        "target_roles": ["Operations Manager"],  # deliberately unrelated
        "skills": ["operations", "logistics"],
        "certifications": [],
        "years_experience": 9,
        "industries": ["services"],
        "preferred_cities": ["Dubai"],
        "current_role": "Operations Manager",
        "nationality": "",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


@pytest.fixture()
def api(monkeypatch):
    _api = RicoChatAPI(persist=False)
    monkeypatch.setattr(_api, "_append_chat", lambda *a, **k: None)
    monkeypatch.setattr(_api, "_begin_job_search_operation", lambda *a, **k: {"operation_id": "op-x"})
    monkeypatch.setattr(_api, "_store_search_matches_context", lambda *a, **k: None)
    monkeypatch.setattr(_api, "_store_pending_job_search", lambda *a, **k: None)
    monkeypatch.setattr("src.rico_chat_api.mark_completed", lambda *a, **k: None)
    # Legacy scraper fallback must not invent results.
    _api.system = SimpleNamespace(run_for_profile=lambda *_a, **_k: {"matches": []})
    return _api


def _titles(resp):
    return [str(m.get("title") or "") for m in resp.get("matches", [])]


# ── Pure scorer unit checks ────────────────────────────────────────────────

def test_scorer_exact_and_family_and_unrelated():
    assert score_role_relevance("ESG Analyst", "ESG Manager") >= RELEVANCE_FLOOR
    assert score_role_relevance("Sustainability Manager", "ESG Manager") >= RELEVANCE_FLOOR
    assert score_role_relevance("Operations Manager", "ESG Manager") < RELEVANCE_FLOOR
    # Generic word alone never matches across families.
    assert score_role_relevance("Sales Manager", "ESG Manager") < RELEVANCE_FLOOR


# ── Scenario 1: stale profile, ESG query, ESG + Operations noise ───────────

def test_stale_profile_esg_query_filters_operations_noise(api, monkeypatch):
    jobs = [
        _job("Operations Manager"),
        _job("ESG Manager"),
        _job("Logistics Coordinator"),
        _job("Sustainability Manager"),
        _job("Warehouse Supervisor"),
    ]
    monkeypatch.setattr(
        api, "_search_jsearch_meta",
        lambda role, location="": FetchResult(items=list(jobs), provider="jsearch"),
    )
    # Profile is stale (saved role = Operations Manager) — must NOT pull ops noise.
    resp = api._target_role_search_response("u1", "ESG Manager", _profile())

    assert resp["type"] == "job_matches"
    titles = _titles(resp)
    assert titles, "expected ESG-family matches"
    assert all("operation" not in t.lower() for t in titles)
    assert all("warehouse" not in t.lower() and "logistics" not in t.lower() for t in titles)
    assert any("esg" in t.lower() or "sustainab" in t.lower() for t in titles)


# ── Scenario 2: no-profile / guest, HSE query ──────────────────────────────

def test_no_profile_guest_hse_query_only_safety_family(api, monkeypatch):
    jobs = [
        _job("HSE Manager"),
        _job("EHS Officer"),
        _job("Safety Manager"),
        _job("Sales Executive"),
        _job("Accountant"),
    ]
    monkeypatch.setattr(
        api, "_search_jsearch_meta",
        lambda role, location="": FetchResult(items=list(jobs), provider="jsearch"),
    )
    # Guest / no-profile: empty target roles and skills.
    guest = _profile(has_cv=False, target_roles=[], skills=[], current_role="")
    resp = api._target_role_search_response("guest-1", "HSE Manager", guest)

    titles = [t.lower() for t in _titles(resp)]
    assert titles
    assert all(("hse" in t or "ehs" in t or "safety" in t) for t in titles)
    assert not any("sales" in t or "accountant" in t for t in titles)


# ── Scenario 3: Accountant query → only finance/accounting ─────────────────

def test_accountant_query_only_finance_accounting(api, monkeypatch):
    jobs = [
        _job("Senior Accountant"),
        _job("Finance Manager"),
        _job("Operations Coordinator"),
        _job("HSE Officer"),
        _job("Marketing Executive"),
    ]
    monkeypatch.setattr(
        api, "_search_jsearch_meta",
        lambda role, location="": FetchResult(items=list(jobs), provider="jsearch"),
    )
    resp = api._target_role_search_response("u2", "Accountant", _profile())

    titles = [t.lower() for t in _titles(resp)]
    assert titles
    assert all(("account" in t or "finance" in t) for t in titles)
    assert not any("operation" in t or "hse" in t or "marketing" in t for t in titles)


# ── Scenario 4: no strong matches → honest fallback, no fake "5 matches" ────

def test_no_strong_matches_returns_broaden_fallback(api, monkeypatch):
    # Provider returns 5 results but ALL are unrelated to the requested role.
    jobs = [
        _job("Operations Manager"),
        _job("Warehouse Supervisor"),
        _job("Sales Executive"),
        _job("Receptionist"),
        _job("Driver"),
    ]
    monkeypatch.setattr(
        api, "_search_jsearch_meta",
        lambda role, location="": FetchResult(items=list(jobs), provider="jsearch"),
    )
    resp = api._target_role_search_response("u3", "ESG Manager", _profile())

    assert resp["type"] == "no_strong_matches"
    assert resp["matches"] == []
    assert resp["result_count"] == 0
    # No fabricated "N matches" claim.
    assert "5 matches" not in resp["message"]
    actions = {o["action"] for o in resp["options"]}
    assert "broaden_search" in actions


# ── Scenario 5: Sustainability matches ESG via taxonomy ────────────────────

def test_sustainability_matches_esg_query_via_taxonomy(api, monkeypatch):
    jobs = [
        _job("Sustainability Lead"),
        _job("Operations Manager"),
    ]
    monkeypatch.setattr(
        api, "_search_jsearch_meta",
        lambda role, location="": FetchResult(items=list(jobs), provider="jsearch"),
    )
    resp = api._target_role_search_response("u4", "ESG Manager", _profile())

    titles = [t.lower() for t in _titles(resp)]
    assert any("sustainab" in t for t in titles)
    assert all("operation" not in t for t in titles)


# ── Scenario 6: Operations query still returns valid Operations roles ──────

def test_operations_query_returns_operations_roles(api, monkeypatch):
    jobs = [
        _job("Operations Manager"),
        _job("Logistics Coordinator"),
        _job("ESG Specialist"),
        _job("Accountant"),
    ]
    monkeypatch.setattr(
        api, "_search_jsearch_meta",
        lambda role, location="": FetchResult(items=list(jobs), provider="jsearch"),
    )
    resp = api._target_role_search_response("u5", "Operations Manager", _profile())

    titles = [t.lower() for t in _titles(resp)]
    assert titles
    assert any("operation" in t or "logistics" in t for t in titles)
    assert not any("esg" in t or "accountant" in t for t in titles)
