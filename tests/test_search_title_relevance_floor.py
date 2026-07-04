# -*- coding: utf-8 -*-
"""Explicit-title chat search relevance floor (global, all users).

Pins the fix for the live-QA finding where "find ESG Manager jobs in UAE"
returned Operations / CDD / Customer Success jobs and still claimed "5 matches
for ESG Manager". The two defects fixed:

  1. Ranking used the user's *saved profile* target_roles instead of the
     *requested* title, so a stale profile floated off-title jobs.
  2. Nothing ever dropped off-title results — the top 5 of whatever the provider
     returned were shown as "matches".

These tests drive the REAL ``RicoChatAPI._target_role_search_response`` with the
live-job provider stubbed to a controlled mix of relevant + noise jobs. Fully
offline: no DB, no provider, no network, no credentials, no user-specific data.
The relevance vocabulary is data-driven from ``src/data/job_role_taxonomy.json``.
"""
from __future__ import annotations

import os
from contextlib import ExitStack
from typing import Any
from unittest.mock import PropertyMock, patch

import pytest

from src.jsearch_client import FetchResult
from src.rico_agent import RicoProfile


def _job(title: str, company: str = "SynthCo") -> dict[str, Any]:
    url = f"https://synthco.example/jobs/{abs(hash(title)) % 10000}"
    return {
        "title": title,
        "company": company,
        "apply_url": url,
        "job_apply_link": url,
        "location": "Dubai, UAE",
        "description": f"{title} position based in Dubai, UAE.",
    }


class _Driver:
    """Hermetic driver: controllable provider payload → real search handler."""

    def __init__(self, provider_titles: list[str]) -> None:
        self._items = [_job(t) for t in provider_titles]
        self.searched_roles: list[str] = []

    def _search(self, role: str, location: str = "", **_kw: Any) -> FetchResult:
        self.searched_roles.append(role)
        # Fresh copies — the pipeline mutates job dicts (adds fit scores etc.).
        return FetchResult(items=[dict(j) for j in self._items], provider="jsearch")

    def run(self, requested_role: str, *, target_roles: list[str] | None = None,
            skills: list[str] | None = None) -> dict[str, Any]:
        profile = RicoProfile(user_id="synthetic@test")
        if hasattr(profile, "target_roles"):
            profile.target_roles = list(target_roles or [])
        if hasattr(profile, "skills"):
            profile.skills = list(skills or [])

        rctx: dict[str, Any] = {}

        def _get_rctx(_self: Any, uid: str) -> dict[str, Any]:
            return dict(rctx)

        def _store_rctx(_self: Any, uid: str, ctx: dict[str, Any]) -> None:
            rctx.clear()
            rctx.update(ctx or {})

        from src.rico_chat_api import RicoChatAPI

        with ExitStack() as stack:
            p = stack.enter_context
            # Force both DB layers off so untouched paths never hit a real DSN.
            p(patch("src.rico_db.RicoDB.available", new_callable=PropertyMock, return_value=False))
            p(patch("src.db.DB_ENABLED", False))
            os.environ.pop("REDIS_URL", None)
            p(patch("src.rico_chat_api.RicoChatAPI._search_jsearch_meta", side_effect=self._search))
            p(patch("src.rico_chat_api.RicoChatAPI._get_recent_context", _get_rctx))
            p(patch("src.rico_chat_api.RicoChatAPI._store_recent_context", _store_rctx))
            p(patch("src.llm_scorer._embed", return_value=None))
            api = RicoChatAPI()
            return api._target_role_search_response(profile.user_id, requested_role, profile)


def _titles(resp: dict[str, Any]) -> list[str]:
    return [str(m.get("title") or "") for m in (resp.get("matches") or [])]


def _lower(titles: list[str]) -> str:
    return " || ".join(titles).lower()


# --- 1. stale-profile user asks ESG Manager, provider returns ESG + noise ------

def test_stale_profile_esg_query_shows_only_esg_family():
    resp = _Driver([
        "ESG Manager",
        "Sustainability Manager",
        "Compliance Manager",
        "Overseas Operations Manager (P2P)",
        "Manager, CDD Operations",
        "Senior Operations Manager",
        "Manager, EEMEA Customer Success Enablement, Services",
    ]).run("ESG Manager", target_roles=["Operations Manager"], skills=["operations"])

    titles = _titles(resp)
    assert titles, "expected ESG-family matches to survive the floor"
    blob = _lower(titles)
    # No off-title noise, despite the stale Operations profile.
    assert "operations" not in blob
    assert "customer success" not in blob
    # At least one genuine ESG-domain result is shown.
    assert any(k in blob for k in ("esg", "sustainability", "compliance"))


# --- 2. no-profile / guest asks HSE Manager -----------------------------------

def test_guest_hse_query_shows_only_hse_family():
    resp = _Driver([
        "HSE Manager",
        "Health & Safety Officer",
        "EHS / Safety Manager",
        "Sales Manager",
        "Senior Accountant",
    ]).run("HSE Manager", target_roles=[], skills=[])

    titles = _titles(resp)
    assert titles
    blob = _lower(titles)
    assert "sales" not in blob
    assert "accountant" not in blob
    assert any(k in blob for k in ("hse", "safety", "ehs"))


# --- 3. Accountant query → only finance / accounting --------------------------

def test_accountant_query_shows_only_finance_family():
    resp = _Driver([
        "Senior Accountant",
        "Finance Manager",
        "Accounts Payable Clerk",
        "Taxi Driver",     # must NOT match on the "tax" family token
        "Receptionist",
    ]).run("Accountant", target_roles=[], skills=[])

    titles = _titles(resp)
    assert titles
    blob = _lower(titles)
    assert "taxi" not in blob and "driver" not in blob
    assert "receptionist" not in blob
    assert any(k in blob for k in ("accountant", "finance", "accounts"))


# --- 4. no strong matches → honest broaden fallback, no fake count ------------

def test_no_strong_matches_returns_honest_fallback():
    resp = _Driver([
        "Overseas Operations Manager (P2P)",
        "Sales Executive",
    ]).run("ESG Manager", target_roles=["Operations Manager"])

    assert _titles(resp) == [], "off-title jobs must not be presented as matches"
    msg = str(resp.get("message") or "").lower()
    # No fabricated "I found N match(es)" claim for the requested title.
    assert "i found" not in msg
    assert "match(es)" not in msg
    # Honest broaden language instead.
    assert "broaden" in msg or "didn't strongly match" in msg


# --- 5. synonym coverage: a Sustainability role matches an ESG query ----------

def test_synonym_sustainability_matches_esg_query():
    resp = _Driver(["Sustainability Manager"]).run("ESG Manager", target_roles=[])
    titles = _titles(resp)
    assert len(titles) == 1
    assert "sustainability" in titles[0].lower()


# --- 6. control: Operations Manager query still returns valid Operations ------

def test_control_operations_query_returns_operations_roles():
    resp = _Driver([
        "Operations Manager",
        "Senior Operations Manager",
        "Process Improvement Lead",
    ]).run("Operations Manager", target_roles=["Operations Manager"], skills=["operations"])

    titles = _titles(resp)
    assert len(titles) == 3, "the floor must not over-reject genuine in-domain roles"
    blob = _lower(titles)
    assert "operations" in blob or "process" in blob


# --- bonus: requested title is the PRIMARY ranking signal ---------------------

def test_requested_title_ranks_above_looser_family_match():
    # Stale Operations profile; provider returns an exact requested-title job, a
    # looser same-family job, and off-title noise.
    resp = _Driver([
        "ESG Analyst",     # family match, not the exact requested title
        "ESG Manager",     # exact requested title
        "Operations Manager",  # off-title noise (stale profile) — must be dropped
    ]).run("ESG Manager", target_roles=["Operations Manager"])

    titles = _titles(resp)
    assert titles, "expected ESG results"
    assert "operations" not in _lower(titles)
    # Exact requested title outranks the looser same-family title.
    assert titles[0] == "ESG Manager"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
