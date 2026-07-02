# -*- coding: utf-8 -*-
"""
P0 regression: "open the apply link for the SECOND/Nth job" must reach the
open_apply_link handler.

#727 added ordinal apply-link classification, but the pre-existing job-detail
gate (`_ORDINAL_JOB_RE`, "the second job") ran earlier in the dispatch and
swallowed every ordinal except "first" — so "open the apply link for the second
job" fell through to a generic clarification instead of resolving/falling back.
A controlled production smoke caught it. This guards the routing for all
ordinals.

No external provider calls — recent_search_matches is seeded directly.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.rico_chat_api import RicoChatAPI


def _profile():
    return SimpleNamespace(
        has_cv=True, name="T", preferred_cities=["Dubai"], location="Dubai",
        years_experience=8, skills=["product"], certifications=[],
        target_roles=["Technical Product Owner"], current_role="Product Owner",
    )


@pytest.fixture()
def api(monkeypatch):
    _api = RicoChatAPI(persist=False)
    # Two seeded results: #1 has a trusted link, #2 has only a Google intermediary
    # (→ no usable link → fallback CTA).
    raw = [
        {"title": "Technical Product Owner", "company": "ADNOC",
         "apply_url": "https://adnoc.ae/careers/123", "location": "Abu Dhabi, UAE"},
        {"title": "Technical Product Owner", "company": "Globex",
         "apply_url": "https://www.google.com/search?q=tpo", "location": "Dubai"},
    ]
    formatted = [RicoChatAPI._format_match(j, _profile()) for j in raw]
    ctx = {"recent_search_matches": formatted}
    monkeypatch.setattr(_api, "_resolve_profile", lambda uid: _profile())
    monkeypatch.setattr(_api, "_get_recent_context", lambda uid: ctx)
    monkeypatch.setattr(_api, "_store_recent_context", lambda uid, c: ctx.update(c))
    monkeypatch.setattr(_api, "_append_chat", lambda *a, **k: None)
    monkeypatch.setattr(
        _api, "_handle_open_apply_link_path",
        lambda **kw: {"type": "open_apply_link", "apply_url": kw["apply_url"]},
    )
    return _api


def _run(api, msg):
    return api._handle_active_user("u-ord", msg)


@pytest.mark.parametrize("msg", [
    "Open the apply link for the first job",
    "open apply link for the first job",
])
def test_first_job_resolves_trusted_link(api, msg):
    r = _run(api, msg)
    assert r.get("type") == "open_apply_link"
    assert r.get("apply_url") == "https://adnoc.ae/careers/123"


@pytest.mark.parametrize("msg", [
    "Open the apply link for the second job",
    "open apply link for job 2",
    "show me the apply link for the second one",
])
def test_second_job_routes_to_apply_link_not_job_detail(api, msg):
    """The ordinal job-detail gate must NOT swallow apply-link requests."""
    r = _run(api, msg)
    assert r.get("type") == "open_apply_link", (
        f"expected open_apply_link, got {r.get('type')}: {(r.get('message') or '')[:80]}"
    )
    # Second job has no usable link → fallback CTA, never a missing-link error.
    assert r.get("link_unavailable") is True
    assert r.get("options"), "fallback CTA options expected"
    assert "missing required 'link'" not in (r.get("message") or "").lower()


def test_job_detail_still_works_for_non_applylink_ordinal(api):
    """A genuine job-detail ordinal request is unaffected by the guard."""
    r = _run(api, "tell me more about the second job")
    # Routed to job-detail (not open_apply_link).
    assert r.get("type") != "open_apply_link"
