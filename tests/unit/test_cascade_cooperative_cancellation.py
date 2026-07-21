"""End-to-end cooperative cascade cancellation (DEC-20260721-001 slice-4 closure).

Acceptance criterion under test (owner-approved, 2026-07-21):

    After ownership loss becomes observable, the old worker starts NO new
    provider request, retry, or side effect; any response already in flight
    is DISCARDED and never reaches the user or storage.

The cancel check is passed EXPLICITLY through every layer of the cascade —
job_providers.search_jobs (hedged threads) → _jooble_search/_adzuna_search/
_jsearch_search → jsearch_client.search (sync requests + backoff retries) —
and the chat flow consumes operation_state.ownership_lost directly. No test
here claims an already-sent HTTP request is aborted: cooperative cancellation
means refusing to START work and refusing to USE late responses.
"""
from __future__ import annotations

import io
import json
import urllib.error
from types import SimpleNamespace

import pytest

from src import job_providers, jsearch_client
from src.jsearch_client import CANCELLED_ERROR, FetchResult
from src.services import operation_state


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    operation_state.reset_for_tests()
    jsearch_client.clear_cache()
    job_providers.clear_state()
    monkeypatch.delenv("RICO_OPERATION_STORE", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    yield
    operation_state.reset_for_tests()
    jsearch_client.clear_cache()
    job_providers.clear_state()


def _http_response(payload: dict) -> object:
    body = io.BytesIO(json.dumps(payload).encode())

    class _Resp:
        def read(self):
            return body.read()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    return _Resp()


class _FlippingCancel:
    """Cancel check that flips True after N observations (simulates the
    heartbeat self-fencing while work is underway)."""

    def __init__(self, flip_after: int):
        self.calls = 0
        self.flip_after = flip_after

    def __call__(self) -> bool:
        self.calls += 1
        return self.calls > self.flip_after


# ── jsearch_client.search ─────────────────────────────────────────────────────

def test_jsearch_cancelled_before_start_issues_no_request(monkeypatch):
    monkeypatch.setenv("RAPIDAPI_KEY", "test-key")
    monkeypatch.setattr(
        jsearch_client.urllib.request, "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no request may be issued")),
    )
    result = jsearch_client.search("hse manager UAE", should_cancel=lambda: True)
    assert result.error == CANCELLED_ERROR
    assert result.items == []


def test_jsearch_cancellation_between_retries_stops_new_requests(monkeypatch):
    """First attempt 429s; ownership is lost during the backoff → the retry
    request must NOT be issued (exactly one request total)."""
    monkeypatch.setenv("RAPIDAPI_KEY", "test-key")
    calls = {"n": 0}

    def _urlopen(*a, **k):
        calls["n"] += 1
        raise urllib.error.HTTPError("u", 429, "too many", {}, io.BytesIO(b""))

    monkeypatch.setattr(jsearch_client.urllib.request, "urlopen", _urlopen)
    monkeypatch.setattr(jsearch_client.time, "sleep", lambda s: None)

    # Ownership loss becomes observable only AFTER the first request went out
    # (the heartbeat self-fences while the 429 backoff elapses).
    result = jsearch_client.search(
        "hse manager UAE", should_cancel=lambda: calls["n"] >= 1
    )
    assert calls["n"] == 1, "no retry request after ownership loss"
    assert result.error == CANCELLED_ERROR
    assert result.items == []


def test_jsearch_inflight_response_discarded_no_cache_no_observations(monkeypatch):
    """Ownership is lost while the (successful) response is in flight: items
    are dropped, nothing is cached, nothing reaches the observations archive."""
    monkeypatch.setenv("RAPIDAPI_KEY", "test-key")
    payload = {"data": [{"job_id": "j1", "job_title": "HSE Manager", "job_country": "AE"}]}
    sent = {"n": 0}

    def _urlopen(*a, **k):
        sent["n"] += 1
        return _http_response(payload)

    monkeypatch.setattr(jsearch_client.urllib.request, "urlopen", _urlopen)
    recorded = []
    import src.repositories.job_observations_repo as obs_repo
    monkeypatch.setattr(obs_repo, "record_observations", lambda *a, **k: recorded.append(a))

    # Loss becomes observable only once the request is on the wire.
    result = jsearch_client.search("hse manager UAE", should_cancel=lambda: sent["n"] >= 1)

    assert sent["n"] == 1, "exactly one request went out"
    assert result.error == CANCELLED_ERROR
    assert result.items == [], "in-flight response must be discarded"
    assert recorded == [], "observations archive must not be written"
    assert jsearch_client._cache_get("hse manager UAE") is None, "cache must not be written"


def test_jsearch_backoff_is_interruptible_with_bounded_latency(monkeypatch):
    """Owner item 2: the retry backoff must be a cancel-aware wait — with a
    5s backoff pending, a loss observed right after the first 429 must stop
    the flow in well under a second (REAL clock, no mocked sleep)."""
    import time as _time

    monkeypatch.setenv("RAPIDAPI_KEY", "test-key")
    monkeypatch.setattr(jsearch_client, "_BACKOFF_BASE_S", 5.0)
    sent = {"n": 0}

    def _urlopen(*a, **k):
        sent["n"] += 1
        raise urllib.error.HTTPError("u", 429, "too many", {}, io.BytesIO(b""))

    monkeypatch.setattr(jsearch_client.urllib.request, "urlopen", _urlopen)

    t0 = _time.monotonic()
    result = jsearch_client.search("hse manager UAE", should_cancel=lambda: sent["n"] >= 1)
    elapsed = _time.monotonic() - t0

    assert sent["n"] == 1, "no retry request after the loss"
    assert result.error == CANCELLED_ERROR
    assert elapsed < 1.0, f"cancellation latency {elapsed:.2f}s — backoff wait not interruptible"


def test_jsearch_no_cache_write_when_loss_flips_during_normalization(monkeypatch):
    """Owner item 1: loss flipping AFTER the post-response check but before
    the cache write must suppress both storage side effects."""
    monkeypatch.setenv("RAPIDAPI_KEY", "test-key")
    payload = {"data": [{"job_id": "j1", "job_title": "HSE Manager", "job_country": "AE"}]}
    monkeypatch.setattr(
        jsearch_client.urllib.request, "urlopen", lambda *a, **k: _http_response(payload)
    )
    recorded = []
    import src.repositories.job_observations_repo as obs_repo
    monkeypatch.setattr(obs_repo, "record_observations", lambda *a, **k: recorded.append(a))

    # Checkpoint order: entry(1), before_request(2), post-response(3),
    # before_cache_write(4). flip_after=3 → the write-gate sees the loss.
    cancel = _FlippingCancel(flip_after=3)
    result = jsearch_client.search("hse manager UAE", should_cancel=cancel)

    assert result.error == CANCELLED_ERROR and result.items == []
    assert jsearch_client._cache_get("hse manager UAE") is None, "cache write must be suppressed"
    assert recorded == [], "observations write must be suppressed"


def test_jsearch_stale_cache_not_served_to_fenced_caller(monkeypatch):
    """Owner item 1: the terminal-error stale-cache fallback must re-check
    cancellation — a fenced caller gets nothing, not even stale items."""
    monkeypatch.setenv("RAPIDAPI_KEY", "test-key")
    payload = {"data": [{"job_id": "j1", "job_title": "HSE Manager", "job_country": "AE"}]}
    monkeypatch.setattr(
        jsearch_client.urllib.request, "urlopen", lambda *a, **k: _http_response(payload)
    )
    assert len(jsearch_client.search("hse manager UAE").items) == 1  # primes the cache

    sent = {"n": 0}

    def _quota(*a, **k):
        sent["n"] += 1
        raise urllib.error.HTTPError("u", 403, "quota", {}, io.BytesIO(b""))

    monkeypatch.setattr(jsearch_client.urllib.request, "urlopen", _quota)
    result = jsearch_client.search("hse manager UAE", use_cache=False, should_cancel=lambda: sent["n"] >= 1)
    assert result.error == CANCELLED_ERROR
    assert result.items == [], "stale cache must not be served after the fence"


def test_jsearch_cache_hit_not_served_when_loss_flips_before_it(monkeypatch):
    monkeypatch.setenv("RAPIDAPI_KEY", "test-key")
    payload = {"data": [{"job_id": "j1", "job_title": "HSE Manager", "job_country": "AE"}]}
    monkeypatch.setattr(
        jsearch_client.urllib.request, "urlopen", lambda *a, **k: _http_response(payload)
    )
    assert len(jsearch_client.search("hse manager UAE").items) == 1  # primes the cache

    cancel = _FlippingCancel(flip_after=1)  # entry passes; cache-hit gate sees loss
    result = jsearch_client.search("hse manager UAE", should_cancel=cancel)
    assert result.error == CANCELLED_ERROR and result.items == []


def test_raising_cancel_check_fails_closed(monkeypatch):
    """Owner item 5: a SUPPLIED but broken check cannot prove ownership —
    the gate fails closed (no request), never open."""
    monkeypatch.setenv("RAPIDAPI_KEY", "test-key")
    monkeypatch.setattr(
        jsearch_client.urllib.request, "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no request may be issued")),
    )

    def _broken():
        raise RuntimeError("token backend unreachable")

    result = jsearch_client.search("hse manager UAE", should_cancel=_broken)
    assert result.error == CANCELLED_ERROR and result.items == []


def test_jsearch_without_cancel_check_behaves_as_before(monkeypatch):
    monkeypatch.setenv("RAPIDAPI_KEY", "test-key")
    payload = {"data": [{"job_id": "j1", "job_title": "HSE Manager", "job_country": "AE"}]}
    monkeypatch.setattr(
        jsearch_client.urllib.request, "urlopen", lambda *a, **k: _http_response(payload)
    )
    result = jsearch_client.search("hse manager UAE")
    assert result.error is None
    assert len(result.items) == 1


# ── provider clients (jooble / adzuna) ────────────────────────────────────────

def test_jooble_cancelled_before_start_issues_no_request(monkeypatch):
    monkeypatch.setenv("JOOBLE_API_KEY", "jk")
    monkeypatch.setattr(
        job_providers.urllib.request, "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no request may be issued")),
    )
    result = job_providers._jooble_search("hse", "", should_cancel=lambda: True)
    assert result.error == CANCELLED_ERROR and result.items == []


def test_jooble_inflight_response_discarded(monkeypatch):
    monkeypatch.setenv("JOOBLE_API_KEY", "jk")
    monkeypatch.setattr(
        job_providers.urllib.request, "urlopen",
        lambda *a, **k: _http_response({"jobs": [{"title": "HSE", "id": "1"}]}),
    )
    recorded = []
    monkeypatch.setattr(
        job_providers, "_record_observations_safe", lambda *a, **k: recorded.append(a)
    )
    cancel = _FlippingCancel(flip_after=1)
    result = job_providers._jooble_search("hse", "", should_cancel=cancel)
    assert result.error == CANCELLED_ERROR and result.items == []
    assert recorded == []


def test_adzuna_cancelled_before_start_issues_no_request(monkeypatch):
    monkeypatch.setenv("ADZUNA_APP_ID", "a")
    monkeypatch.setenv("ADZUNA_APP_KEY", "b")
    monkeypatch.setattr(
        job_providers.urllib.request, "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no request may be issued")),
    )
    result = job_providers._adzuna_search("hse", "", should_cancel=lambda: True)
    assert result.error == CANCELLED_ERROR and result.items == []


def test_jooble_error_path_does_not_mark_degraded_when_fenced(monkeypatch):
    """Owner item 1: a fenced worker performs NO provider-health mutation —
    even when the in-flight request came back as a rate-limit error."""
    monkeypatch.setenv("JOOBLE_API_KEY", "jk")
    sent = {"n": 0}

    def _urlopen(*a, **k):
        sent["n"] += 1
        raise urllib.error.HTTPError("u", 429, "too many", {}, io.BytesIO(b""))

    monkeypatch.setattr(job_providers.urllib.request, "urlopen", _urlopen)
    result = job_providers._jooble_search("hse", "", should_cancel=lambda: sent["n"] >= 1)
    assert result.error == CANCELLED_ERROR
    assert job_providers.is_degraded("jooble") is False, "no health mutation for a fenced worker"


def test_jooble_observations_gated_immediately_before_write(monkeypatch):
    """Owner item 1: loss flipping between the post-response check and the
    observations write must suppress the write."""
    monkeypatch.setenv("JOOBLE_API_KEY", "jk")
    monkeypatch.setattr(
        job_providers.urllib.request, "urlopen",
        lambda *a, **k: _http_response({"jobs": [{"title": "HSE", "id": "1"}]}),
    )
    recorded = []
    monkeypatch.setattr(
        job_providers, "_record_observations_safe", lambda *a, **k: recorded.append(a)
    )
    # Checkpoint order: entry(1), post-response(2), before_observations(3).
    cancel = _FlippingCancel(flip_after=2)
    result = job_providers._jooble_search("hse", "", should_cancel=cancel)
    assert result.error == CANCELLED_ERROR and recorded == []


# ── job_providers.search_jobs orchestrator ────────────────────────────────────

def test_cascade_cancelled_before_start_launches_nothing(monkeypatch):
    monkeypatch.setenv("JOOBLE_API_KEY", "jk")
    monkeypatch.setenv("RAPIDAPI_KEY", "rk")
    for fn in ("_jooble_search", "_adzuna_search", "_jsearch_search"):
        monkeypatch.setattr(
            job_providers, fn,
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("provider must not launch")),
        )
    result = job_providers.search_jobs("hse manager", should_cancel=lambda: True)
    assert result.error == CANCELLED_ERROR
    assert result.items == [] and result.provider == "none"


def test_cascade_stops_launching_next_provider_after_loss(monkeypatch):
    """Jooble finishes empty; ownership is lost before the next hedge slot →
    JSearch must never be launched."""
    monkeypatch.setenv("JOOBLE_API_KEY", "jk")
    monkeypatch.setenv("RAPIDAPI_KEY", "rk")

    state = {"lost": False}
    jsearch_called = []

    def _jooble(role, location, **kw):
        state["lost"] = True  # loss becomes observable as jooble completes
        return FetchResult(items=[], provider="jooble")

    monkeypatch.setattr(job_providers, "_jooble_search", _jooble)
    monkeypatch.setattr(
        job_providers, "_jsearch_search",
        lambda *a, **k: jsearch_called.append(1) or FetchResult(items=[], provider="jsearch"),
    )

    result = job_providers.search_jobs(
        "hse manager", should_cancel=lambda: state["lost"]
    )
    assert jsearch_called == [], "no NEW provider may launch after ownership loss"
    assert result.error == CANCELLED_ERROR


def test_cascade_winner_discarded_when_loss_observed_same_pass(monkeypatch):
    """A provider returns items, but ownership loss is observed in the same
    harvest pass: the winner is discarded and nothing is cached."""
    monkeypatch.setenv("JOOBLE_API_KEY", "jk")
    state = {"lost": False}

    def _jooble(role, location, **kw):
        state["lost"] = True
        return FetchResult(items=[{"title": "HSE", "job_id": "1"}], provider="jooble")

    monkeypatch.setattr(job_providers, "_jooble_search", _jooble)

    result = job_providers.search_jobs("hse manager", should_cancel=lambda: state["lost"])
    assert result.error == CANCELLED_ERROR and result.items == []
    with job_providers._cache_lock:
        assert job_providers._result_cache == {}, "discarded winner must not be cached"


def test_cascade_cancels_not_yet_started_futures(monkeypatch):
    """Owner item 3: pending hedge futures that have NOT started must be
    cancelled outright (future.cancel + shutdown(cancel_futures=True)), not
    merely abandoned. Deterministic via a fake pool that never runs work."""
    import concurrent.futures as real_futures

    monkeypatch.setenv("JOOBLE_API_KEY", "jk")

    class _FakePool:
        instances = []

        def __init__(self, *a, **k):
            self.futures = []
            self.shutdown_kwargs = None
            _FakePool.instances.append(self)

        def submit(self, fn, *a, **k):
            fut = real_futures.Future()  # stays PENDING — worker never starts
            self.futures.append(fut)
            return fut

        def shutdown(self, wait=True, cancel_futures=False):
            self.shutdown_kwargs = {"wait": wait, "cancel_futures": cancel_futures}
            if cancel_futures:
                for f in self.futures:
                    f.cancel()

    monkeypatch.setattr(real_futures, "ThreadPoolExecutor", _FakePool)

    # Checkpoint order: entry(1), loop-top(2) → submit jooble, loop-top(3)
    # sees the loss with the future still queued.
    cancel = _FlippingCancel(flip_after=2)
    result = job_providers.search_jobs("hse manager", should_cancel=cancel)

    assert result.error == CANCELLED_ERROR
    pool = _FakePool.instances[-1]
    assert len(pool.futures) == 1, "one hedge future was queued before the loss"
    assert pool.futures[0].cancelled() is True, "queued future must be cancelled"
    assert pool.shutdown_kwargs == {"wait": False, "cancel_futures": True}


def test_run_provider_skips_health_mutation_after_fenced_runner(monkeypatch):
    """Owner item 1: degradation marking after runner() is a side effect —
    it must be re-gated so a fenced worker never mutates provider health."""
    monkeypatch.setenv("JOOBLE_API_KEY", "jk")
    state = {"lost": False}

    def _jooble(role, location, **kw):
        state["lost"] = True  # loss flips while the runner is executing
        return FetchResult(items=[], provider="jooble", rate_limited=True)

    monkeypatch.setattr(job_providers, "_jooble_search", _jooble)
    result = job_providers.search_jobs("hse manager", should_cancel=lambda: state["lost"])
    assert result.error == CANCELLED_ERROR
    assert job_providers.is_degraded("jooble") is False, "fenced worker must not mark health"


def test_internal_lookup_not_started_after_loss(monkeypatch):
    """Owner item 1: internal_lookup is caller-supplied work — a fenced
    worker must not invoke it, and nothing may be cached."""
    monkeypatch.setenv("JOOBLE_API_KEY", "jk")
    called = []
    # Checkpoint order: entry(1), before_internal_lookup(2).
    cancel = _FlippingCancel(flip_after=1)
    result = job_providers.search_jobs(
        "hse manager",
        internal_lookup=lambda: called.append(1) or [{"title": "x"}],
        should_cancel=cancel,
    )
    assert called == [], "internal_lookup must not start after the loss"
    assert result.error == CANCELLED_ERROR
    with job_providers._cache_lock:
        assert job_providers._result_cache == {}


def test_cascade_without_cancel_check_unchanged(monkeypatch):
    monkeypatch.setenv("JOOBLE_API_KEY", "jk")
    monkeypatch.setattr(
        job_providers, "_jooble_search",
        lambda role, location, **kw: FetchResult(
            items=[{"title": "HSE", "job_id": "1"}], provider="jooble"
        ),
    )
    result = job_providers.search_jobs("hse manager")
    assert result.provider == "jooble" and len(result.items) == 1


# ── chat-flow consumer (rico_chat_api) ────────────────────────────────────────

def _profile(**overrides):
    data = {
        "has_cv": True,
        "target_roles": ["HSE Manager"],
        "skills": ["HSE", "NEBOSH"],
        "certifications": ["NEBOSH"],
        "years_experience": 10,
        "industries": ["construction"],
        "preferred_cities": ["Dubai"],
        "current_role": "HSE Officer",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_flow_discards_pending_result_after_ownership_loss(monkeypatch):
    """Ownership is lost while the provider fetch is in flight: the reply is
    search_superseded, NOTHING is appended to chat history, and this worker
    does not complete the operation."""
    import uuid as _uuid
    from src.rico_chat_api import RicoChatAPI

    api = RicoChatAPI(persist=False)
    # Unique ids: the memory backend mirrors operations into a persistent
    # store, so a fixed id would resume with a bumped attempt on re-runs.
    op_id = f"op_lost_{_uuid.uuid4().hex[:12]}"
    user_id = f"user-lost-{_uuid.uuid4().hex[:8]}"
    api._current_operation_id = op_id
    appended = []
    monkeypatch.setattr(api, "_append_chat", lambda *a, **k: appended.append(a))

    def _fetch(role, location=""):
        # Simulate the heartbeat self-fencing while the response is in flight
        # — for THIS execution's actual (operation, attempt) generation.
        operation_state._mark_ownership_lost(
            str(api._current_operation_id), int(api._operation_attempt())
        )
        return FetchResult(items=[{
            "title": "HSE Manager", "company": "ACME", "location": "Dubai, UAE",
            "link": "https://example.test/apply", "description": "x", "score": 90,
        }])

    monkeypatch.setattr(api, "_search_jsearch_meta", _fetch)
    monkeypatch.setattr(
        api.system, "run_for_profile",
        lambda p: (_ for _ in ()).throw(AssertionError("legacy fallback must not start")),
    )

    response = api._classified_role_search(user_id, "HSE Manager", _profile())

    assert response["type"] == "search_superseded"
    assert response["superseded"] is True
    assert appended == [], "a discarded result must never reach chat history"
    latest = operation_state.get_latest_job_search_operation(user_id)
    assert latest is not None and latest["status"] == "running", (
        "the fenced worker must not write a terminal status — the takeover owns it"
    )


def test_flow_completes_normally_when_ownership_retained(monkeypatch):
    from src.rico_chat_api import RicoChatAPI

    api = RicoChatAPI(persist=False)
    api._current_operation_id = "op_retained"
    monkeypatch.setattr(api, "_append_chat", lambda *a, **k: None)
    monkeypatch.setattr(
        api, "_search_jsearch_meta",
        lambda role, location="": FetchResult(items=[{
            "title": "HSE Manager", "company": "ACME", "location": "Dubai, UAE",
            "link": "https://example.test/apply", "description": "x", "score": 90,
        }]),
    )
    response = api._classified_role_search("user-kept", "HSE Manager", _profile())
    assert response["type"] == "job_matches"
    assert response["operation_status"] == "completed"


def test_seam_passes_cancel_check_explicitly_into_cascade(monkeypatch):
    """_begin_job_search_operation binds the check; the _search_jsearch_meta
    seam must hand it EXPLICITLY to job_providers.search_jobs."""
    import uuid as _uuid
    from src import rico_chat_api as rca

    api = rca.RicoChatAPI(persist=False)
    op_id = f"op_seam_{_uuid.uuid4().hex[:12]}"
    api._current_operation_id = op_id
    api._begin_job_search_operation(f"user-seam-{_uuid.uuid4().hex[:8]}", "hse manager")

    captured = {}

    def _capture(role, location="", **kwargs):
        captured["should_cancel"] = kwargs.get("should_cancel")
        return FetchResult(items=[])

    monkeypatch.setattr(job_providers, "search_jobs", _capture)
    rca.RicoChatAPI._search_jsearch_meta("hse manager")

    check = captured.get("should_cancel")
    assert callable(check), "cancel check must be passed explicitly to the cascade"
    assert check() is False, "ownership currently held → not cancelled"
    operation_state._mark_ownership_lost(op_id, int(api._operation_attempt()))
    assert check() is True, "self-fenced generation → check flips True"
