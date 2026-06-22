# -*- coding: utf-8 -*-
"""
Regression tests for job-card / apply-link integrity (Production Test 9 / P0).

Test 9 failed:
    Prompt: "Open the apply link for the first job."
    Actual: "Action failed: Job payload is missing required 'link' field."

Root cause: card rendering and the chat "open apply link" action looked at
different link fields, and an Apply button could render with no usable URL. This
suite pins:
  - one canonical normalized link field (usable_link) on the card
  - card with a valid link is actionable; card with no link exposes a fallback CTA
  - "open the apply link for the first/Nth job" resolves from recent-search context
    and uses the same normalized link
  - a missing link returns a fallback CTA, never the raw missing-link error
  - a provider-normalized job always has either a usable_link or an explicit
    link_unavailable reason

No external provider/network calls — everything is in-process.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.rico_chat_api import RicoChatAPI
from src.services.job_link import resolve_job_link, build_link_fallback_cta
from src.agent.intelligence.intent_classifier import classify_intent


def _profile() -> SimpleNamespace:
    return SimpleNamespace(
        has_cv=True, name="Test User", preferred_cities=["Dubai"], location="Dubai",
        years_experience=5, skills=["HSE"], certifications=[],
        target_roles=["HSE Manager"], current_role="HSE Officer",
    )


# ── resolve_job_link: canonical normalization ─────────────────────────────────

def test_provider_field_names_all_resolve():
    for field in ("job_apply_link", "apply_link", "apply_url", "link"):
        r = resolve_job_link({"title": "X", field: "https://acme.com/jobs/1"})
        assert r["usable_link"] == "https://acme.com/jobs/1", field
        assert r["link_unavailable"] is False, field


def test_source_url_used_when_no_apply_link():
    r = resolve_job_link({"source_url": "https://bayt.com/en/uae/jobs/x"})
    assert r["usable_link"] == "https://bayt.com/en/uae/jobs/x"
    assert r["link_unavailable"] is False


def test_google_intermediary_is_not_usable():
    r = resolve_job_link({"apply_url": "https://www.google.com/search?q=jobs"})
    assert r["usable_link"] == ""
    assert r["link_unavailable"] is True
    assert r["reason"] == "google_intermediary_only"
    assert r["apply_url"] == ""  # demoted


def test_no_link_at_all_is_unavailable_with_reason():
    r = resolve_job_link({"title": "X", "company": "Y"})
    assert r["usable_link"] == ""
    assert r["link_unavailable"] is True
    assert r["reason"] == "no_link"


def test_expired_link_is_unavailable():
    r = resolve_job_link({
        "apply_url": "https://acme.com/jobs/1", "verification_status": "expired",
    })
    assert r["usable_link"] == ""
    assert r["link_unavailable"] is True
    assert r["reason"] == "expired"


def test_provider_job_always_has_usable_link_or_reason():
    """Invariant: every resolved job has a non-empty usable_link XOR an explicit
    link_unavailable reason — never an undefined in-between state."""
    samples = [
        {"apply_url": "https://acme.com/1"},
        {"source_url": "https://bayt.com/2"},
        {"apply_url": "https://www.google.com/search?q=jobs"},
        {"title": "no link"},
        {"apply_url": "https://x.com/3", "verification_status": "expired"},
        {},
        "not-a-dict",
    ]
    for s in samples:
        r = resolve_job_link(s)  # type: ignore[arg-type]
        if r["usable_link"]:
            assert r["link_unavailable"] is False and r["reason"] == ""
        else:
            assert r["link_unavailable"] is True and r["reason"] in (
                "expired", "google_intermediary_only", "untrusted_aggregator", "no_link",
            )


def test_fallback_cta_offers_safe_search_options():
    cta = build_link_fallback_cta("HSE Manager", "ADNOC", "Abu Dhabi")
    labels = {o["label"] for o in cta}
    assert "Search company career site" in labels
    assert "Search on Google" in labels
    assert "Search on LinkedIn" in labels
    assert any(o["action"] == "copy_text" for o in cta)
    assert any(o["action"] == "save_job" for o in cta)
    # All open_url CTAs are plain search links — never scraped destinations.
    for o in cta:
        if o["action"] == "open_url":
            assert o["url"].startswith("https://www.google.com/search") or \
                   o["url"].startswith("https://www.linkedin.com/jobs/search")


# ── Card rendering via _format_match ──────────────────────────────────────────

def test_card_with_valid_link_is_actionable():
    card = RicoChatAPI._format_match(
        {"title": "HSE Manager", "company": "ADNOC", "apply_url": "https://adnoc.ae/jobs/1"},
        _profile(),
    )
    assert card["usable_link"] == "https://adnoc.ae/jobs/1"
    assert card["link_unavailable"] is False
    assert "fallback_cta" not in card


def test_card_with_missing_link_exposes_fallback_cta():
    card = RicoChatAPI._format_match(
        {"title": "HSE Manager", "company": "ADNOC"}, _profile(),
    )
    assert card["usable_link"] == ""
    assert card["link_unavailable"] is True
    assert "fallback_cta" in card and len(card["fallback_cta"]) >= 3


# ── Ordinal "open the apply link for the Nth job" ─────────────────────────────

def test_open_first_job_classifies_with_ordinal():
    r = classify_intent("Open the apply link for the first job", has_cv_profile=True)
    assert r.legacy_intent == "open_apply_link"
    assert r.entities.get("ordinal") == 1


@pytest.fixture()
def api(monkeypatch):
    _api = RicoChatAPI(persist=False)
    monkeypatch.setattr(_api, "_append_chat", lambda *a, **k: None)
    return _api


def test_open_first_job_resolves_from_recent_context(api, monkeypatch):
    job = {"title": "HSE Manager", "company": "ADNOC", "apply_url": "https://adnoc.ae/jobs/1"}
    monkeypatch.setattr(api, "_recent_search_matches", lambda uid: [job])
    captured = {}
    monkeypatch.setattr(
        api, "_handle_open_apply_link_path",
        lambda **kw: captured.update(kw) or {"type": "open_apply_link", "apply_url": kw["apply_url"]},
    )
    resp = api._open_apply_link_by_ordinal("u1", 1, _profile())
    # Used the SAME canonical usable_link the card would expose.
    assert captured["apply_url"] == "https://adnoc.ae/jobs/1"
    assert captured["title"] == "HSE Manager"
    assert resp["type"] == "open_apply_link"


def test_open_first_job_missing_link_returns_fallback_not_error(api, monkeypatch):
    job = {"title": "HSE Manager", "company": "ADNOC"}  # no link anywhere
    monkeypatch.setattr(api, "_recent_search_matches", lambda uid: [job])
    monkeypatch.setattr(
        api, "_handle_open_apply_link_path",
        lambda **kw: pytest.fail("must not open a path when there is no usable link"),
    )
    resp = api._open_apply_link_by_ordinal("u1", 1, _profile())
    assert resp["type"] == "open_apply_link"
    assert resp["link_unavailable"] is True
    assert resp["options"], "fallback CTA options must be present"
    assert "missing required 'link'" not in resp["message"].lower()


def test_open_last_job_resolves_last(api, monkeypatch):
    jobs = [
        {"title": "A", "company": "C1", "apply_url": "https://x.com/a"},
        {"title": "B", "company": "C2", "apply_url": "https://x.com/b"},
    ]
    monkeypatch.setattr(api, "_recent_search_matches", lambda uid: jobs)
    captured = {}
    monkeypatch.setattr(
        api, "_handle_open_apply_link_path",
        lambda **kw: captured.update(kw) or {"type": "open_apply_link"},
    )
    api._open_apply_link_by_ordinal("u1", -1, _profile())
    assert captured["apply_url"] == "https://x.com/b"


def test_open_job_no_recent_list_asks_to_search(api, monkeypatch):
    monkeypatch.setattr(api, "_recent_search_matches", lambda uid: [])
    resp = api._open_apply_link_by_ordinal("u1", 1, _profile())
    assert resp["type"] == "open_apply_link"
    assert resp["apply_url"] is None
    assert "search" in resp["message"].lower()


def test_open_job_index_out_of_range(api, monkeypatch):
    monkeypatch.setattr(
        api, "_recent_search_matches",
        lambda uid: [{"title": "A", "company": "C", "apply_url": "https://x.com/a"}],
    )
    resp = api._open_apply_link_by_ordinal("u1", 5, _profile())
    assert resp["apply_url"] is None
    assert "between 1 and 1" in resp["message"]


# ── apply_job tool never raises the missing-link error ────────────────────────

def test_apply_job_tool_no_link_returns_safe_code():
    from src.agent.tools.job_tools import apply_job
    res = apply_job({"title": "X"})  # no link of any kind
    assert res.success is False
    assert res.error == "no_apply_link_available"
    assert "missing required 'link'" not in (res.error or "")


def test_apply_job_tool_accepts_apply_url_field(monkeypatch):
    from src.agent.tools import job_tools
    monkeypatch.setattr(
        "src.services.apply_service.apply_to_job",
        lambda job, approved=False: {"status": "approval_required"},
    )
    res = job_tools.apply_job({"title": "X", "apply_url": "https://acme.com/jobs/1"})
    assert res.success is True
