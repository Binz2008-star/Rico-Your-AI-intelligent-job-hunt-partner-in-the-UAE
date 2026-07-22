# -*- coding: utf-8 -*-
"""
Tests for the job-provider cascade (src/job_providers.py).

Context: the RapidAPI JSearch BASIC subscription hit 100% quota, producing
rate-limited statuses and dead-end job cards. These tests pin the new behaviour:

- cache-first: repeated identical searches never call an external provider again
- internal recent/saved results are preferred over external providers
- cascade order: Jooble → Adzuna → JSearch
- JSearch quota exhaustion does not retry and is not called while degraded
- Jooble missing key is skipped safely; Jooble errors don't break the cascade
- Adzuna stays disabled unless BOTH env vars exist
- provider result normalization
- no secret values are logged

No real network calls are made — every provider HTTP boundary is monkeypatched.
"""
from __future__ import annotations

import io
import json
import logging
import time
import urllib.error

import pytest

from src import job_providers as jp
from src.jsearch_client import FetchResult


# All provider env vars these tests touch — cleared then set per-test.
_PROVIDER_ENV = ["JOOBLE_API_KEY", "ADZUNA_APP_ID", "ADZUNA_APP_KEY", "RAPIDAPI_KEY"]


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    """Clear cache/health and all provider env before each test."""
    jp.clear_state()
    for name in _PROVIDER_ENV:
        monkeypatch.delenv(name, raising=False)
    yield
    jp.clear_state()


def _fake_urlopen(payload: dict):
    """Return a urlopen stand-in yielding *payload* as a JSON HTTP body."""
    def _open(req, timeout=None):
        body = json.dumps(payload).encode()
        resp = io.BytesIO(body)
        resp.__enter__ = lambda: resp  # type: ignore[attr-defined]
        resp.__exit__ = lambda *a: False  # type: ignore[attr-defined]
        return resp
    return _open


# ── Normalization ─────────────────────────────────────────────────────────────

def test_jooble_normalization():
    raw = {
        "title": "Technical Product Owner",
        "company": "ACME",
        "location": "Dubai",
        "snippet": "Own the roadmap.",
        "salary": "AED 30k",
        "type": "Full-time",
        "link": "https://jooble.org/jobs/123",
        "id": "123",
    }
    job = jp._normalize_jooble(raw)
    assert job["title"] == "Technical Product Owner"
    assert job["company"] == "ACME"
    assert job["source"] == "jooble"
    assert job["apply_link"] == "https://jooble.org/jobs/123"
    assert job["link"] == "https://jooble.org/jobs/123"
    assert job["job_id"] == "123"


def test_adzuna_normalization():
    raw = {
        "title": "Product Owner",
        "company": {"display_name": "Globex"},
        "location": {"display_name": "Abu Dhabi"},
        "redirect_url": "https://adzuna.com/jobs/9",
        "description": "Lead delivery.",
        "salary_min": 20000,
        "salary_max": 30000,
        "contract_time": "full_time",
        "id": "9",
    }
    job = jp._normalize_adzuna(raw)
    assert job["title"] == "Product Owner"
    assert job["company"] == "Globex"
    assert job["location"] == "Abu Dhabi"
    assert job["source"] == "adzuna"
    assert job["apply_link"] == "https://adzuna.com/jobs/9"
    assert job["salary_string"] == "20000-30000"


# ── Cache-first ───────────────────────────────────────────────────────────────

def test_repeated_identical_search_uses_cache(monkeypatch):
    monkeypatch.setenv("JOOBLE_API_KEY", "x")
    calls = {"n": 0}

    def _jooble(role, location, page=1, *, cancel=None):
        calls["n"] += 1
        return FetchResult(items=[{"title": role, "company": "ACME"}], provider="jooble")

    monkeypatch.setattr(jp, "_jooble_search", _jooble)

    first = jp.search_jobs("Technical Product Owner", "UAE")
    second = jp.search_jobs("Technical Product Owner", "UAE")

    assert first.provider == "jooble"
    assert second.provider == "cache"
    assert second.cache_hit is True
    # The external provider is called exactly once across two identical searches.
    assert calls["n"] == 1


def test_use_cache_false_bypasses_cache(monkeypatch):
    monkeypatch.setenv("JOOBLE_API_KEY", "x")
    calls = {"n": 0}

    def _jooble(role, location, page=1, *, cancel=None):
        calls["n"] += 1
        return FetchResult(items=[{"title": role}], provider="jooble")

    monkeypatch.setattr(jp, "_jooble_search", _jooble)
    jp.search_jobs("PO", "UAE")
    jp.search_jobs("PO", "UAE", use_cache=False)
    assert calls["n"] == 2


# ── Internal recent/saved ─────────────────────────────────────────────────────

def test_internal_results_preferred_over_external(monkeypatch):
    monkeypatch.setenv("JOOBLE_API_KEY", "x")
    monkeypatch.setattr(
        jp, "_jooble_search",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("provider must not run")),
    )
    res = jp.search_jobs(
        "PO", "UAE",
        internal_lookup=lambda: [{"title": "PO", "company": "Saved", "source": "internal"}],
    )
    assert res.provider == "internal"
    assert res.items[0]["company"] == "Saved"


# ── Cascade order ─────────────────────────────────────────────────────────────

def test_cascade_prefers_jooble_over_jsearch(monkeypatch):
    monkeypatch.setenv("JOOBLE_API_KEY", "x")
    monkeypatch.setenv("RAPIDAPI_KEY", "y")
    monkeypatch.setattr(
        jp, "_jooble_search",
        lambda *a, **k: FetchResult(items=[{"title": "from-jooble"}], provider="jooble"),
    )
    monkeypatch.setattr(
        jp, "_jsearch_search",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("JSearch must not run when Jooble has results")),
    )
    res = jp.search_jobs("PO", "UAE")
    assert res.provider == "jooble"


def test_cascade_falls_through_to_jsearch_when_jooble_empty(monkeypatch):
    monkeypatch.setenv("JOOBLE_API_KEY", "x")
    monkeypatch.setenv("RAPIDAPI_KEY", "y")
    monkeypatch.setattr(jp, "_jooble_search", lambda *a, **k: FetchResult(items=[], provider="jooble"))
    monkeypatch.setattr(
        jp, "_jsearch_search",
        lambda *a, **k: FetchResult(items=[{"title": "from-jsearch"}], provider="jsearch"),
    )
    res = jp.search_jobs("PO", "UAE")
    assert res.provider == "jsearch"
    assert res.items[0]["title"] == "from-jsearch"


# ── JSearch quota exhaustion ──────────────────────────────────────────────────

def test_jsearch_quota_exhausted_marks_degraded_and_does_not_recall(monkeypatch):
    monkeypatch.setenv("RAPIDAPI_KEY", "y")
    calls = {"n": 0}

    def _jsearch(role, location, country, *, cancel=None):
        calls["n"] += 1
        return FetchResult(items=[], provider="jsearch", quota_exhausted=True)

    monkeypatch.setattr(jp, "_jsearch_search", _jsearch)

    first = jp.search_jobs("PO", "UAE")
    assert first.provider == "none"
    assert first.quota_exhausted is True
    assert jp.is_degraded("jsearch") is True

    # Second identical-role but different search: JSearch is skipped while degraded.
    second = jp.search_jobs("PO", "Dubai")
    assert second.provider == "none"
    assert calls["n"] == 1  # JSearch was NOT called again


def test_degraded_provider_skipped(monkeypatch):
    monkeypatch.setenv("JOOBLE_API_KEY", "x")
    jp.mark_degraded("jooble", "error")
    monkeypatch.setattr(
        jp, "_jooble_search",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("degraded provider must be skipped")),
    )
    res = jp.search_jobs("PO", "UAE")
    assert res.provider == "none"


# ── Jooble safety ─────────────────────────────────────────────────────────────

def test_jooble_missing_key_skipped_safely(monkeypatch):
    # No JOOBLE_API_KEY set (fixture cleared it). Should skip without error.
    monkeypatch.setenv("RAPIDAPI_KEY", "y")
    monkeypatch.setattr(
        jp, "_jsearch_search",
        lambda *a, **k: FetchResult(items=[{"title": "js"}], provider="jsearch"),
    )
    res = jp.search_jobs("PO", "UAE")
    assert res.provider == "jsearch"  # fell straight through to JSearch


def test_jooble_missing_key_returns_no_api_key():
    res = jp._jooble_search("PO", "UAE")
    assert res.provider == "jooble"
    assert res.error == "no_api_key"
    assert res.items == []


def test_jooble_http_error_does_not_break_cascade(monkeypatch):
    monkeypatch.setenv("JOOBLE_API_KEY", "x")
    monkeypatch.setenv("RAPIDAPI_KEY", "y")

    def _raise(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 500, "boom", {}, None)

    monkeypatch.setattr(jp.urllib.request, "urlopen", _raise)
    monkeypatch.setattr(
        jp, "_jsearch_search",
        lambda *a, **k: FetchResult(items=[{"title": "js"}], provider="jsearch"),
    )
    res = jp.search_jobs("PO", "UAE")
    # Jooble failed but the cascade recovered via JSearch.
    assert res.provider == "jsearch"
    assert jp.is_degraded("jooble") is True


def test_jooble_network_error_marks_degraded(monkeypatch):
    monkeypatch.setenv("JOOBLE_API_KEY", "x")

    def _raise(req, timeout=None):
        raise TimeoutError("slow")

    monkeypatch.setattr(jp.urllib.request, "urlopen", _raise)
    res = jp._jooble_search("PO", "UAE")
    assert res.items == []
    assert res.provider == "jooble"
    assert jp.is_degraded("jooble") is True


def test_jooble_success_parses_jobs(monkeypatch):
    monkeypatch.setenv("JOOBLE_API_KEY", "x")
    payload = {"jobs": [
        {"title": "PO", "company": "ACME", "link": "https://x/1", "id": "1", "snippet": "s"},
        {"title": "TPO", "company": "Globex", "link": "https://x/2", "id": "2"},
    ]}
    monkeypatch.setattr(jp.urllib.request, "urlopen", _fake_urlopen(payload))
    res = jp._jooble_search("PO", "UAE")
    assert len(res.items) == 2
    assert res.items[0]["source"] == "jooble"


# ── Adzuna gating ─────────────────────────────────────────────────────────────

def test_adzuna_disabled_without_both_keys(monkeypatch):
    monkeypatch.setenv("ADZUNA_APP_ID", "only-id")  # missing key
    assert jp._adzuna_enabled() is False
    res = jp._adzuna_search("PO", "UAE")
    assert res.error == "no_api_key"
    assert res.items == []


def test_adzuna_enabled_only_with_both_keys(monkeypatch):
    monkeypatch.setenv("ADZUNA_APP_ID", "id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "key")
    assert jp._adzuna_enabled() is True


def test_adzuna_skipped_in_cascade_when_disabled(monkeypatch):
    monkeypatch.setenv("RAPIDAPI_KEY", "y")  # only JSearch configured
    monkeypatch.setattr(
        jp, "_adzuna_search",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("Adzuna must be skipped when disabled")),
    )
    monkeypatch.setattr(jp, "_jsearch_search", lambda *a, **k: FetchResult(items=[{"title": "js"}], provider="jsearch"))
    res = jp.search_jobs("PO", "UAE")
    assert res.provider == "jsearch"


# ── Degraded fallback result ──────────────────────────────────────────────────

def test_no_providers_configured_returns_no_providers_configured():
    # No env vars configured at all → distinct from a degraded deployment so the
    # chat layer can fall through to its normal empty-results handling.
    res = jp.search_jobs("PO", "UAE")
    assert res.provider == "none"
    assert res.items == []
    assert res.error == "no_providers_configured"


def test_configured_but_all_failing_returns_all_providers_unavailable(monkeypatch):
    # A provider IS configured but every attempt fails → genuine degraded state.
    monkeypatch.setenv("RAPIDAPI_KEY", "y")
    monkeypatch.setattr(jp, "_jsearch_search", lambda *a, **k: FetchResult(items=[], provider="jsearch"))
    res = jp.search_jobs("PO", "UAE")
    assert res.provider == "none"
    assert res.error == "all_providers_unavailable"


def test_configured_but_degraded_returns_all_providers_unavailable(monkeypatch):
    # JSearch configured but in quota cooldown → still a degraded deployment.
    monkeypatch.setenv("RAPIDAPI_KEY", "y")
    jp.mark_degraded("jsearch", "quota")
    res = jp.search_jobs("PO", "UAE")
    assert res.provider == "none"
    assert res.error == "all_providers_unavailable"


# ── Provider health indicator ─────────────────────────────────────────────────

def test_provider_health_reports_configured_and_degraded(monkeypatch):
    monkeypatch.setenv("JOOBLE_API_KEY", "x")
    jp.mark_degraded("jsearch", "quota")
    health = jp.provider_health()
    assert health["jooble"]["configured"] is True
    assert health["adzuna"]["configured"] is False
    assert health["jsearch"]["degraded"] is True
    assert health["jsearch"]["reason"] == "quota"


# ── No secret logging ─────────────────────────────────────────────────────────

def test_no_secret_values_logged(monkeypatch, caplog):
    secret = "super-secret-jooble-key-123"
    monkeypatch.setenv("JOOBLE_API_KEY", secret)

    def _raise(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 500, "boom", {}, None)

    monkeypatch.setattr(jp.urllib.request, "urlopen", _raise)
    with caplog.at_level(logging.DEBUG, logger="src.job_providers"):
        jp._jooble_search("PO", "UAE")
    # The key must never appear in any log record.
    assert all(secret not in rec.getMessage() for rec in caplog.records)


# ── Hedged cascade (perf regression fix, 2026-07-21) ─────────────────────────
# The serial cascade stacked each provider's full HTTP budget: one slow
# provider pushed production first searches to 30-60s on a warm instance.
# The cascade now hedges: provider N+1 launches after a stagger (or
# immediately once every launched provider finished empty) and the first
# non-empty result wins.

def test_hedge_overtakes_a_slow_provider(monkeypatch):
    """A hanging cheap provider must NOT hold the search hostage — the next
    provider launches after the stagger and its result wins."""
    monkeypatch.setenv("JOOBLE_API_KEY", "x")
    monkeypatch.setenv("RAPIDAPI_KEY", "y")
    monkeypatch.setattr(jp, "_HEDGE_STAGGER_S", 0.1)

    def _slow_jooble(role, location, *, cancel=None):
        time.sleep(1.0)
        return FetchResult(items=[{"title": "late", "company": "j"}], provider="jooble")

    def _fast_jsearch(role, location, country, *, cancel=None):
        return FetchResult(items=[{"title": "fast", "company": "s"}], provider="jsearch")

    monkeypatch.setattr(jp, "_jooble_search", _slow_jooble)
    monkeypatch.setattr(jp, "_jsearch_search", _fast_jsearch)

    t0 = time.time()
    result = jp.search_jobs("HSE Manager", "UAE")
    elapsed = time.time() - t0

    assert result.provider == "jsearch"
    assert result.items[0]["title"] == "fast"
    assert elapsed < 0.9, f"hedge failed to overtake the slow provider ({elapsed:.2f}s)"


def test_stagger_preserves_cost_preference(monkeypatch):
    """A responsive cheap provider wins inside its head start — the more
    expensive provider is never called at all."""
    monkeypatch.setenv("JOOBLE_API_KEY", "x")
    monkeypatch.setenv("RAPIDAPI_KEY", "y")
    monkeypatch.setattr(jp, "_HEDGE_STAGGER_S", 0.5)
    called = {"jsearch": False}

    def _quick_jooble(role, location, *, cancel=None):
        time.sleep(0.05)
        return FetchResult(items=[{"title": "cheap", "company": "j"}], provider="jooble")

    def _jsearch(role, location, country, *, cancel=None):
        called["jsearch"] = True
        return FetchResult(items=[{"title": "pricey", "company": "s"}], provider="jsearch")

    monkeypatch.setattr(jp, "_jooble_search", _quick_jooble)
    monkeypatch.setattr(jp, "_jsearch_search", _jsearch)

    result = jp.search_jobs("HSE Manager", "UAE")

    assert result.provider == "jooble"
    assert called["jsearch"] is False


def test_fast_empty_failures_skip_the_stagger(monkeypatch):
    """Providers that finish empty immediately must NOT make the next
    provider wait out its stagger slot — fall-through stays instant."""
    monkeypatch.setenv("JOOBLE_API_KEY", "x")
    monkeypatch.setenv("RAPIDAPI_KEY", "y")
    monkeypatch.setattr(jp, "_HEDGE_STAGGER_S", 5.0)  # would be visible if waited

    monkeypatch.setattr(jp, "_jooble_search", lambda role, location, *, cancel=None: FetchResult(provider="jooble"))
    monkeypatch.setattr(
        jp, "_jsearch_search",
        lambda role, location, country, *, cancel=None: FetchResult(items=[{"title": "ok", "company": "s"}], provider="jsearch"),
    )

    t0 = time.time()
    result = jp.search_jobs("HSE Manager", "UAE")
    elapsed = time.time() - t0

    assert result.provider == "jsearch"
    assert elapsed < 1.0, f"empty fall-through waited out the stagger ({elapsed:.2f}s)"
