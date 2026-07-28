# -*- coding: utf-8 -*-
"""Zero-result recovery for an explicit-title search (global, all users).

Pins the two behaviours added after the live finding that a real user asking
for a real role in a real UAE city was handed nothing at all, twice in one
session, while live listings had in fact been retrieved:

  1. **City-scope widening.** When a search is pinned to ONE city and the title
     floor drops every result, Rico widens the GEOGRAPHY — keeping the title the
     user explicitly asked for — instead of substituting an adjacent role. It is
     one extra provider call, not two: the adjacent-role hop is skipped when the
     city hop already ran.
  2. **Related tier.** Floor-rejected listings have already passed the integrity
     gate, so they are real, UAE, available listings. They are surfaced in their
     OWN ``related_matches`` field, tagged ``match_tier="related"`` and named as
     related in the copy. ``matches`` keeps its contract — it means "matches what
     you asked for" — so the 2026-07 "5 matches for ESG Manager" defect stays
     fixed.

Plus the truthfulness correction that ``broadened`` now means "Rico actually
widened this search", not "this search returned zero".

Fully offline and synthetic: no DB, no provider, no network, no credentials, and
no user-specific data. Every assertion is about product behaviour for any user in
any thin market — no city, role or account is special-cased.
"""
from __future__ import annotations

import os
import re
from contextlib import ExitStack
from typing import Any
from unittest.mock import PropertyMock, patch

import pytest

from src.jsearch_client import FetchResult
from src.rico_agent import RicoProfile

ON_TITLE = ["Quality Manager", "Quality Assurance Manager", "Senior Quality Manager"]
OFF_TITLE = ["Sales Executive", "Delivery Driver", "Receptionist"]


def _job(title: str, city: str) -> dict[str, Any]:
    url = f"https://synthco.example/jobs/{abs(hash(title + city)) % 10000}"
    return {
        "title": title,
        "company": "SynthCo",
        "apply_url": url,
        "job_apply_link": url,
        "location": f"{city}, UAE",
        "description": f"{title} position based in {city}, UAE.",
    }


class _NoLegacyResults:
    """Stand-in for the legacy scraper pipeline: always an honest zero."""

    def run_for_profile(self, _profile: Any) -> dict[str, Any]:
        return {"matches": []}


class _Driver:
    """Hermetic driver with a LOCATION-AWARE provider stub.

    ``by_location`` maps the provider-level location string ("" is UAE-wide) to
    the titles that location returns, so a thin city and a deep country can be
    modelled in one run without any real provider.
    """

    def __init__(self, by_location: dict[str, list[str]]) -> None:
        self._by_location = by_location
        self.calls: list[tuple[str, str]] = []

    def _search(self, role: str, location: str = "", **_kw: Any) -> FetchResult:
        self.calls.append((role, location))
        titles = self._by_location.get(location, [])
        city = location or "Dubai"
        return FetchResult(
            items=[_job(t, city) for t in titles], provider="jsearch",
        )

    def run(
        self,
        requested_role: str,
        *,
        location: str = "",
        target_roles: list[str] | None = None,
        arabic_turn: bool = False,
    ) -> dict[str, Any]:
        profile = RicoProfile(user_id="synthetic@test")
        if hasattr(profile, "target_roles"):
            profile.target_roles = list(target_roles or [])
        if hasattr(profile, "skills"):
            profile.skills = ["quality", "iso"]

        rctx: dict[str, Any] = {}

        def _get_rctx(_self: Any, uid: str) -> dict[str, Any]:
            return dict(rctx)

        def _store_rctx(_self: Any, uid: str, ctx: dict[str, Any]) -> None:
            rctx.clear()
            rctx.update(ctx or {})

        def _recent_msgs(_self: Any, uid: str, limit: int = 5) -> list[dict[str, Any]]:
            return [{"role": "user", "content": "ابحث لي عن وظائف"}] if arabic_turn else []

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
            p(patch("src.rico_chat_api.RicoChatAPI._get_recent_messages", _recent_msgs))
            p(patch("src.llm_scorer._embed", return_value=None))
            api = RicoChatAPI()
            # An empty provider payload falls through to the legacy scraper
            # pipeline; stub it so "the provider returned nothing" stays exactly
            # that and no local job file leaks into the assertions.
            api.system = _NoLegacyResults()
            return api._target_role_search_response(
                profile.user_id, requested_role, profile, location=location,
            )


def _titles(resp: dict[str, Any], key: str = "matches") -> list[str]:
    return [str(m.get("title") or "") for m in (resp.get(key) or [])]


# ── 1. City widening ──────────────────────────────────────────────────────────

def test_thin_city_widens_to_uae_and_keeps_the_requested_title():
    """A thin city returns only noise; the country returns the real title.

    Rico must relax the IMPLICIT constraint (city) and keep the EXPLICIT one
    (title) — the reverse of substituting an adjacent role.
    """
    d = _Driver({"Ajman": OFF_TITLE, "": ON_TITLE})
    resp = d.run("Quality Manager", location="Ajman")

    assert _titles(resp), "widening to UAE must deliver the on-title results"
    assert all("quality" in t.lower() for t in _titles(resp))
    # The requested title survived the widening — no adjacent-role substitution.
    assert [role for role, _ in d.calls] == ["Quality Manager", "Quality Manager"]
    # Second call is country-wide (empty provider location).
    assert d.calls[1][1] == ""
    assert resp.get("widened_from_location") == "Ajman"


def test_city_widening_is_disclosed_in_the_reply():
    d = _Driver({"Ajman": OFF_TITLE, "": ON_TITLE})
    resp = d.run("Quality Manager", location="Ajman")

    msg = str(resp.get("message") or "").lower()
    assert "ajman" in msg and "uae" in msg
    assert "widened" in msg
    # `broadened` is the machine-readable half of the same disclosure.
    assert resp.get("broadened") is True


def test_city_widening_consumes_cascade_budget_and_prevents_adjacent_hop():
    """City widening spends the one-hop cascade budget; no adjacent-role hop follows.

    When the widening finds nothing either, the request must stop there rather
    than buy a third provider call by also hopping the role — and the user must
    still be handed the related tier instead of a blank screen.
    """
    # Market: no Quality Manager anywhere — not in Ajman, not country-wide.
    d = _Driver({"Ajman": OFF_TITLE, "": OFF_TITLE})

    resp = d.run("Quality Manager", location="Ajman")

    # Exactly two calls: the original city search, then the geographic widening.
    # No third (adjacent-role) call — `_widened_city` suppresses it.
    assert len(d.calls) == 2
    assert d.calls[0] == ("Quality Manager", "Ajman")
    assert d.calls[1] == ("Quality Manager", "")

    # Honest zero on the requested title, with the related tier still delivered.
    assert len(resp.get("matches", [])) == 0
    assert len(resp.get("related_matches", [])) > 0


def test_country_scope_search_does_not_widen():
    """Already UAE-wide → nothing to widen; the city hop must not fire."""
    d = _Driver({"": OFF_TITLE})
    d.run("Quality Manager", location="UAE")

    assert [loc for _, loc in d.calls] == [""], f"unexpected extra call: {d.calls}"


def test_widening_failure_is_stated_not_hidden():
    """A widening that found nothing is disclosed, so the user is not invited to
    ask for a broadening Rico has already tried."""
    d = _Driver({"Ajman": OFF_TITLE, "": OFF_TITLE})
    resp = d.run("Quality Manager", location="Ajman")

    msg = str(resp.get("message") or "").lower()
    assert "whole uae" in msg
    # It did not deliver widened results, so it must not claim it broadened.
    assert resp.get("broadened") is False


# ── 2. Related tier ───────────────────────────────────────────────────────────

def test_off_title_results_ship_as_related_never_as_matches():
    d = _Driver({"": OFF_TITLE})
    resp = d.run("Quality Manager")

    assert _titles(resp) == [], "off-title jobs must never be presented as matches"
    related = resp.get("related_matches") or []
    assert related, "the closest live listings must still reach the user"
    assert all(r.get("match_tier") == "related" for r in related)
    assert resp.get("related_to_role") == "Quality Manager"


def test_related_tier_is_capped_below_the_match_window():
    d = _Driver({"": OFF_TITLE + ["Barista", "Warehouse Packer", "Security Guard"]})
    resp = d.run("Quality Manager")

    assert 0 < len(resp.get("related_matches") or []) <= 3


def test_related_copy_names_them_as_related_not_as_the_requested_role():
    d = _Driver({"": OFF_TITLE})
    resp = d.run("Quality Manager")

    msg = str(resp.get("message") or "")
    low = msg.lower()
    assert "didn't strongly match" in low
    assert "related" in low
    # No fabricated count claim for the requested title — the same guard the
    # relevance-floor suite pins on the no-related variant of this reply.
    assert "match(es)" not in low
    assert "i found" not in low
    assert not re.search(r"\d+ match", low)
    assert resp.get("result_count") == 0


def test_related_copy_is_arabic_for_an_arabic_turn():
    d = _Driver({"": OFF_TITLE})
    resp = d.run("Quality Manager", arabic_turn=True)

    msg = str(resp.get("message") or "")
    assert resp.get("related_matches"), "related tier is language-independent"
    assert "أضعف" in msg or "قريبة" in msg
    assert "didn't strongly match" not in msg.lower()


def test_on_title_search_carries_no_related_tier():
    """The tier is a zero-result fallback, not a permanent extra section."""
    d = _Driver({"": ON_TITLE + OFF_TITLE})
    resp = d.run("Quality Manager")

    assert _titles(resp), "on-title results expected"
    assert "related_matches" not in resp


# ── 3. `broadened` tells the truth ────────────────────────────────────────────

def test_zero_results_alone_does_not_claim_a_broadened_search():
    """`broadened` previously carried `len(all_matches) == 0`, so the UI rendered
    a "· broadened" badge on a search that was never broadened."""
    d = _Driver({"": []})
    resp = d.run("Quality Manager")

    assert _titles(resp) == []
    assert resp.get("broadened") is False


def test_successful_search_is_not_marked_broadened():
    d = _Driver({"": ON_TITLE})
    resp = d.run("Quality Manager")

    assert _titles(resp)
    assert resp.get("broadened") is False


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
