"""
tests/test_apply_link_resolver.py

PR A — apply-link integrity.

Covers the canonical link resolver and the three consumers that must agree on
one apply-link field so a job card built with `apply_url` is never rejected by
`apply_job` with "Job payload is missing required 'link' field":

  1. resolve_job_link / is_usable_link / with_canonical_link (alias coverage)
  2. apply_job() — missing-link fallback CTA + alias resolution + delegation
  3. ordinal recent-search resolution ("apply to the first/second job")

Mocked fixtures only — no DB, no network, no provider quota.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from src.rico_link_resolver import (
    LINK_FIELD_ALIASES,
    has_usable_link,
    is_usable_link,
    resolve_job_link,
    with_canonical_link,
)


# ── 1. Canonical resolver ─────────────────────────────────────────────────────

@pytest.mark.parametrize("field", [
    "link", "apply_url", "apply_link", "job_apply_link",
    "url", "job_url", "source_url", "alt_url", "alt_link", "job_google_link",
])
def test_each_known_alias_resolves(field):
    assert field in LINK_FIELD_ALIASES
    url = f"https://example.com/{field}"
    assert resolve_job_link({field: url}) == url
    assert has_usable_link({field: url}) is True


def test_priority_prefers_direct_link_over_alternates():
    job = {
        "link": "https://canonical",
        "apply_url": "https://apply",
        "source_url": "https://source",
        "job_google_link": "https://jobs.google.com/x",
    }
    assert resolve_job_link(job) == "https://canonical"


def test_apply_url_beats_google_intermediary():
    job = {
        "apply_url": "https://acme.com/careers/123",
        "job_google_link": "https://jobs.google.com/search",
    }
    assert resolve_job_link(job) == "https://acme.com/careers/123"


def test_google_link_is_last_resort_but_usable():
    job = {"job_google_link": "https://jobs.google.com/search?q=hse"}
    assert resolve_job_link(job) == "https://jobs.google.com/search?q=hse"


def test_raw_jsearch_aliases_resolve():
    # Raw provider shape (job_apply_link / job_google_link) must resolve too.
    raw = {"title": "QA", "company": "X", "job_apply_link": "https://board/qa"}
    assert resolve_job_link(raw) == "https://board/qa"


def test_persisted_context_aliases_resolve():
    # user_job_context shape uses apply_url / source_url / alt_url.
    row = {"title": "QA", "apply_url": "", "source_url": "https://src/qa", "alt_url": ""}
    assert resolve_job_link(row) == "https://src/qa"


def test_missing_link_returns_empty():
    assert resolve_job_link({"title": "X", "company": "Y"}) == ""
    assert resolve_job_link({}) == ""
    assert resolve_job_link(None) == ""
    assert has_usable_link({"title": "X"}) is False


def test_blank_and_nonstring_values_skipped():
    job = {"link": "   ", "apply_url": None, "apply_link": 123, "source_url": "https://ok"}
    assert resolve_job_link(job) == "https://ok"


def test_nested_job_payload_resolves():
    assert resolve_job_link({"job": {"apply_url": "https://nested/1"}}) == "https://nested/1"
    assert resolve_job_link({"job_data": {"alt_link": "https://nested/2"}}) == "https://nested/2"


def test_is_usable_link():
    assert is_usable_link("https://x.com")
    assert is_usable_link("http://x.com")
    assert not is_usable_link("ftp://x.com")
    assert not is_usable_link("careers.example.com")
    assert not is_usable_link("")
    assert not is_usable_link(None)


def test_with_canonical_link_sets_field():
    out = with_canonical_link({"title": "X", "apply_url": "https://acme/1"})
    assert out["link"] == "https://acme/1"


def test_with_canonical_link_never_sets_empty():
    out = with_canonical_link({"title": "X"})
    assert "link" not in out


# ── 2. apply_job() — fallback + resolution + delegation ───────────────────────

def test_apply_job_missing_link_returns_manual_fallback():
    from src.agent.tools.job_tools import apply_job
    result = apply_job({"title": "HSE Manager", "company": "ACME"})
    assert result.success is True
    assert result.data.get("status") == "manual_required"
    assert result.data.get("fallback") is True
    msg = (result.data.get("message") or "")
    # The raw internal error string must never reach the user.
    assert "missing required 'link'" not in msg.lower()
    assert "HSE Manager" in msg and "ACME" in msg


def test_apply_job_resolves_alias_and_injects_canonical_link():
    """A card carrying only apply_url must reach apply_to_job with job['link'] set."""
    from src.agent.tools.job_tools import apply_job

    captured: dict = {}

    def fake_apply(job, approved=False):
        captured["link"] = job.get("link")
        captured["approved"] = approved
        return {"status": "approval_required", "message": "needs approval"}

    with patch("src.services.apply_service.apply_to_job", side_effect=fake_apply):
        result = apply_job({
            "title": "Data Analyst",
            "company": "Alpha",
            "apply_url": "https://alpha.com/jobs/da",  # note: no 'link' key
        })

    assert result.success is True
    assert result.data["status"] == "approval_required"
    assert captured["link"] == "https://alpha.com/jobs/da"
    assert captured["approved"] is False


def test_apply_job_preserves_approved_sentinel():
    from src.agent.tools.job_tools import apply_job

    captured: dict = {}

    def fake_apply(job, approved=False):
        captured["approved"] = approved
        return {"status": "applied", "message": "done"}

    with patch("src.services.apply_service.apply_to_job", side_effect=fake_apply):
        apply_job({
            "title": "X", "company": "Y",
            "apply_url": "https://x.com/1", "_approved": True,
        })

    assert captured["approved"] is True


# ── 3. Ordinal recent-search resolution ───────────────────────────────────────

def _stored_matches() -> list[dict]:
    """recent_search_matches in the shape _store_search_matches_context persists:
    each match carries a canonical 'link' resolved from apply_url/source_url."""
    return [
        {"title": "Data Analyst", "company": "Alpha",
         "apply_url": "https://alpha.com/da", "source_url": "", "link": "https://alpha.com/da"},
        {"title": "BI Engineer", "company": "Beta",
         "apply_url": "", "source_url": "https://beta.com/bi", "link": "https://beta.com/bi"},
        {"title": "ML Engineer", "company": "Gamma",
         "apply_url": "https://gamma.com/ml", "source_url": "", "link": "https://gamma.com/ml"},
    ]


@pytest.mark.parametrize("ordinal,expected", [
    ("first", "https://alpha.com/da"),
    ("1", "https://alpha.com/da"),
    ("second", "https://beta.com/bi"),
    ("2", "https://beta.com/bi"),
    ("third", "https://gamma.com/ml"),
])
def test_ordinal_recent_search_resolves_to_usable_link(ordinal, expected):
    from src.rico_chat_api import RicoChatAPI

    matches = _stored_matches()
    idx = RicoChatAPI._ordinal_to_index(ordinal)
    picked = matches[idx]
    link = resolve_job_link(picked)
    assert link == expected
    assert is_usable_link(link)


def test_ordinal_pick_feeds_apply_job_without_missing_link_error():
    """End-to-end of the bug: pick the first cached match → apply → no raw error."""
    from src.rico_chat_api import RicoChatAPI
    from src.agent.tools.job_tools import apply_job

    matches = _stored_matches()
    first = matches[RicoChatAPI._ordinal_to_index("first")]

    with patch("src.services.apply_service.apply_to_job",
               return_value={"status": "approval_required", "message": "needs approval"}):
        result = apply_job(first)

    assert result.success is True
    assert "missing required 'link'" not in (result.data.get("message") or "").lower()
