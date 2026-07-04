# -*- coding: utf-8 -*-
"""C+B fix: mixed-language explicit-search routing + requested-location display.

C — an Arabic/mixed query that names a role and a city ("...ESG Manager في دبي")
    must reach the floored, location-aware ``_target_role_search_response`` instead
    of falling through to the profile-based ``run_for_profile`` path (which emits
    "I found N strong UAE job matches", ignores the requested location, and has no
    #844 relevance floor).
B — ``_target_role_search_response`` must display the location the user actually
    requested (incl. through the known-but-off-profile confirmation flow), falling
    back to the profile's preferred cities only when no location was requested.

Global / data-driven (taxonomy + a UAE-wide Arabic city map); no account, city,
role, or language is special-cased. Fully offline: synthetic users + synthetic
jobs, no DB / provider / network / credentials.
"""
from __future__ import annotations

import os
from contextlib import ExitStack
from typing import Any
from unittest.mock import PropertyMock, patch

from src.jsearch_client import FetchResult
from src.rico_agent import RicoProfile
from tests.harness.chat_harness import ChatHarness


# --- direct _target_role_search_response driver (for the B display assertions) ---

class _TRSDriver:
    def __init__(self, provider_title: str = "Accountant") -> None:
        self._title = provider_title
        self.searched_locations: list[str] = []

    def _search(self, role: str, location: str = "", **_kw: Any) -> FetchResult:
        self.searched_locations.append(location)
        return FetchResult(
            items=[{
                "title": self._title,
                "company": "SynthCo",
                "apply_url": "https://synthco.example/jobs/1",
                "job_apply_link": "https://synthco.example/jobs/1",
                "location": "UAE",
                "description": f"{self._title} position.",
            }],
            provider="jsearch",
        )

    def run(self, role: str, *, location: str, preferred_cities: list[str]) -> dict[str, Any]:
        profile = RicoProfile(user_id="synthetic@test")
        if hasattr(profile, "target_roles"):
            profile.target_roles = [role]
        if hasattr(profile, "preferred_cities"):
            profile.preferred_cities = list(preferred_cities)
        rctx: dict[str, Any] = {}
        from src.rico_chat_api import RicoChatAPI
        with ExitStack() as stack:
            p = stack.enter_context
            p(patch("src.rico_db.RicoDB.available", new_callable=PropertyMock, return_value=False))
            p(patch("src.db.DB_ENABLED", False))
            os.environ.pop("REDIS_URL", None)
            p(patch("src.rico_chat_api.RicoChatAPI._search_jsearch_meta", side_effect=self._search))
            p(patch("src.rico_chat_api.RicoChatAPI._get_recent_context", lambda _s, _u: dict(rctx)))
            p(patch("src.rico_chat_api.RicoChatAPI._store_recent_context",
                    lambda _s, _u, c: rctx.update(c or {})))
            p(patch("src.llm_scorer._embed", return_value=None))
            api = RicoChatAPI()
            return api._target_role_search_response(profile.user_id, role, profile, location=location)


# --- C: routing ---------------------------------------------------------------

def test_arabic_mixed_query_routes_to_explicit_search_not_run_for_profile():
    h = ChatHarness()
    h.seed("u1@test", target_roles=["ESG Manager"], skills=["esg", "compliance"],
           years_experience=6, current_role="ESG Manager",
           preferred_cities=["Abu Dhabi"], cv_status="parsed", cv_filename="cv.pdf")
    res = h.say("u1@test", "ابحث لي عن وظائف ESG Manager في دبي")
    msg = str(res.get("message") or "")

    # (2) the profile-based fallback wording must NOT appear.
    assert "strong UAE job matches" not in msg
    # (1) the explicit-title path ran: the provider was queried for the requested role.
    assert any("esg manager" in str(r).lower() for r in h.searched_roles), h.searched_roles
    # the requested city (mapped to "Dubai"), not the profile's Abu Dhabi, is shown.
    assert "Dubai" in msg
    assert "Abu Dhabi" not in msg and "أبوظبي" not in msg


# --- B: requested location displayed over profile city ------------------------

def test_requested_city_displayed_over_profile_city():
    d = _TRSDriver(provider_title="ESG Manager")
    res = d.run("ESG Manager", location="Dubai", preferred_cities=["Abu Dhabi"])
    msg = str(res.get("message") or "")
    assert "Dubai" in msg
    assert "Abu Dhabi" not in msg
    # A specific requested city is passed to the provider unchanged.
    assert d.searched_locations == ["Dubai"]


def test_country_scope_uae_displayed_and_provider_scope_preserved():
    d = _TRSDriver(provider_title="Accountant")
    res = d.run("Accountant", location="UAE", preferred_cities=["Dubai"])
    msg = str(res.get("message") or "")
    assert "UAE" in msg          # requested country scope shown
    assert "Dubai" not in msg    # not the profile city
    # Country-level scope maps to the default (empty) provider location — the
    # provider query is byte-identical to an unlocated search (no behaviour change).
    assert d.searched_locations == [""]


def test_no_requested_location_falls_back_to_profile_city():
    d = _TRSDriver(provider_title="Accountant")
    res = d.run("Accountant", location="", preferred_cities=["Sharjah"])
    msg = str(res.get("message") or "")
    # Requirement 3: fall back to profile.preferred_cities only when none requested.
    assert "Sharjah" in msg


# --- B: known-but-off-profile confirmation preserves the requested location ----

def test_confirmation_flow_preserves_requested_uae_not_profile_city():
    h = ChatHarness()
    # Profile targets ESG/Compliance and prefers Dubai → "Accountant" is a known
    # role off-profile, so it triggers the confirmation flow.
    h.seed("u2@test", target_roles=["ESG Manager", "Compliance Manager"],
           skills=["compliance"], years_experience=6, current_role="Compliance Manager",
           preferred_cities=["Dubai"], cv_status="parsed", cv_filename="cv.pdf")

    first = h.say("u2@test", "find Accountant jobs in UAE")
    # A confirmation (clarification) should be offered for the off-profile role.
    assert first.get("type") == "clarification", first.get("type")

    # The confirmation UI sends the button label "Yes, search {role}" verbatim.
    second = h.say("u2@test", "Yes, search Accountant")
    assert "Accountant" in h.searched_roles, h.searched_roles
    msg = str(second.get("message") or "")
    assert "UAE" in msg          # requested scope preserved through the confirmation
    assert "Dubai" not in msg    # not the profile city
