# -*- coding: utf-8 -*-
"""Cooperative cancellation of the provider cascade (DEC-20260721-001 slice 4).

Pins the guarantee: "No new provider work after cancellation becomes
observable; any already-in-flight response is discarded without side effects."

- cancel already observable at entry → NO provider is called, distinct
  cancelled FetchResult, no cache write;
- cancel observable before a provider worker starts → that provider's HTTP
  runner is never invoked;
- an in-flight provider result that returns AFTER cancellation is discarded —
  not delivered, not cached, not marked as degraded;
- cancellation is a DISTINCT outcome (cancelled=True, error='ownership_lost'),
  never conflated with no-results / degradation / quota / HTTP error;
- an absent token means 'never cancelled' (unchanged behaviour).

No real network — every provider boundary is monkeypatched.
"""
from __future__ import annotations

import pytest

from src import job_providers as jp
from src.jsearch_client import FetchResult
from src.services.cancellation import CancellationToken

_PROVIDER_ENV = ["JOOBLE_API_KEY", "ADZUNA_APP_ID", "ADZUNA_APP_KEY", "RAPIDAPI_KEY"]


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    jp.clear_state()
    for name in _PROVIDER_ENV:
        monkeypatch.delenv(name, raising=False)
    yield
    jp.clear_state()


def _token(is_cancelled):
    return CancellationToken(operation_id="op_x", attempt=1, is_cancelled=is_cancelled)


def test_cancel_at_entry_calls_no_provider(monkeypatch):
    monkeypatch.setenv("JOOBLE_API_KEY", "k")
    called = {"jooble": 0}

    def _boom(role, location, *, cancel=None):
        called["jooble"] += 1
        return FetchResult(items=[{"title": "x"}], provider="jooble")

    monkeypatch.setattr(jp, "_jooble_search", _boom)

    res = jp.search_jobs("hse manager", cancel=_token(lambda: True))
    assert res.cancelled is True
    assert res.error == "ownership_lost"
    assert res.items == []
    assert res.provider == "none"
    assert called["jooble"] == 0            # NO provider work
    # And nothing was cached.
    assert jp._cache_get(jp._cache_key("hse manager", "", "ae", "")) is None


def test_cancel_before_worker_skips_http_runner(monkeypatch):
    """cancel flips True after entry but before the worker starts → the
    provider's runner is never invoked (the _run_provider new-work guard)."""
    monkeypatch.setenv("JOOBLE_API_KEY", "k")
    flips = {"n": 0}
    calls = {"jooble": 0}

    def _cancelled():
        # not cancelled at the entry check, cancelled by the time the worker runs
        flips["n"] += 1
        return flips["n"] > 1

    def _runner(role, location, *, cancel=None):
        calls["jooble"] += 1
        return FetchResult(items=[{"title": "x"}], provider="jooble")

    monkeypatch.setattr(jp, "_jooble_search", _runner)

    res = jp.search_jobs("hse manager", cancel=_token(_cancelled))
    assert res.cancelled is True
    assert calls["jooble"] == 0             # runner never issued a request


def test_inflight_result_after_cancel_is_discarded_no_side_effects(monkeypatch):
    """A provider that returns rate_limited AFTER cancellation must be
    discarded: not delivered, not cached, and NOT marked degraded."""
    monkeypatch.setenv("JOOBLE_API_KEY", "k")
    state = {"cancelled": False}

    def _runner(role, location, *, cancel=None):
        # simulate the response arriving; by now ownership was lost
        state["cancelled"] = True
        return FetchResult(items=[], provider="jooble", rate_limited=True)

    monkeypatch.setattr(jp, "_jooble_search", _runner)

    res = jp.search_jobs("hse manager", cancel=_token(lambda: state["cancelled"]))
    assert res.cancelled is True
    assert res.error == "ownership_lost"
    # No side effect: the provider was NOT marked degraded by the discarded result.
    assert jp.is_degraded("jooble") is False
    # Not cached.
    assert jp._cache_get(jp._cache_key("hse manager", "", "ae", "")) is None


def test_cancelled_is_distinct_from_empty_and_degraded(monkeypatch):
    """cancelled must never be confused with a normal empty/degraded outcome."""
    monkeypatch.setenv("JOOBLE_API_KEY", "k")
    monkeypatch.setattr(jp, "_jooble_search",
                        lambda r, l, *, cancel=None: FetchResult(items=[], provider="jooble"))

    # No cancellation → normal degraded/empty outcome, cancelled stays False.
    normal = jp.search_jobs("hse manager", cancel=_token(lambda: False))
    assert normal.cancelled is False
    assert normal.error in ("all_providers_unavailable", None)

    # Cancelled → the dedicated outcome.
    cancelled = jp.search_jobs("hse manager", cancel=_token(lambda: True))
    assert cancelled.cancelled is True
    assert cancelled.error == "ownership_lost"


def test_absent_token_is_never_cancelled(monkeypatch):
    monkeypatch.setenv("JOOBLE_API_KEY", "k")
    monkeypatch.setattr(
        jp, "_jooble_search",
        lambda r, l, *, cancel=None: FetchResult(items=[{"title": "x"}], provider="jooble"),
    )
    res = jp.search_jobs("hse manager")  # no cancel arg
    assert res.cancelled is False
    assert res.items and res.provider == "jooble"


def test_token_check_that_raises_fails_closed_to_cancelled():
    """FAIL-CLOSED: a token exists only because the caller wanted this operation
    cancellable. If the ownership check itself breaks, we cannot prove we still
    own the operation, so a broken check must be treated as CANCELLED — never as
    a licence to start more provider work."""
    tok = _token(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert tok.cancelled is True


def test_raising_check_stops_the_cascade(monkeypatch):
    """The fail-closed token, threaded through the real cascade, calls NO
    provider when the ownership check raises."""
    monkeypatch.setenv("JOOBLE_API_KEY", "k")
    called = {"jooble": 0}

    def _boom_provider(role, location, *, cancel=None):
        called["jooble"] += 1
        return FetchResult(items=[{"title": "x"}], provider="jooble")

    monkeypatch.setattr(jp, "_jooble_search", _boom_provider)
    res = jp.search_jobs(
        "hse manager",
        cancel=_token(lambda: (_ for _ in ()).throw(RuntimeError("db gone"))),
    )
    assert res.cancelled is True
    assert res.error == "ownership_lost"
    assert called["jooble"] == 0


def test_absent_token_with_no_check_stays_fail_open():
    """No token → never cancelled (compat): `is_cancelled(None)` is False even
    though a *present* token fails closed."""
    from src.services.cancellation import is_cancelled
    assert is_cancelled(None) is False


def test_jooble_inflight_cancel_records_no_observations_no_degradation(monkeypatch):
    """Finding #2: side effects must not fire for a de-owned in-flight response.
    Jooble's HTTP error path (mark_degraded) and success path
    (_record_observations_safe) are both inside the client — with ownership lost
    after the response, NEITHER runs."""
    monkeypatch.setenv("JOOBLE_API_KEY", "k")
    observed = {"records": 0, "degrades": 0}
    monkeypatch.setattr(jp, "_record_observations_safe",
                        lambda *a, **k: observed.__setitem__("records", observed["records"] + 1))
    monkeypatch.setattr(jp, "mark_degraded",
                        lambda *a, **k: observed.__setitem__("degrades", observed["degrades"] + 1))

    # Real _jooble_search, but the network boundary returns AFTER ownership loss.
    state = {"lost": False}

    class _Resp:
        def __enter__(self):
            state["lost"] = True  # by the time the body is read, ownership is gone
            return self
        def __exit__(self, *a):
            return False
        def read(self):
            return b'{"jobs": [{"title": "HSE", "link": "https://x.test"}]}'

    monkeypatch.setattr(jp.urllib.request, "urlopen", lambda *a, **k: _Resp())

    res = jp.search_jobs("hse manager", cancel=_token(lambda: state["lost"]))
    assert res.cancelled is True
    assert observed["records"] == 0        # no job_observations write
    assert observed["degrades"] == 0       # provider not marked degraded
    assert jp._cache_get(jp._cache_key("hse manager", "", "ae", "")) is None


def test_end_to_end_real_ownership_lost_stops_real_cascade(monkeypatch):
    """End-to-end wiring: the REAL operation_state.ownership_lost self-fence
    outcome, fed through the REAL RicoChatAPI cancellation token into the REAL
    provider cascade, stops new provider work.

    (How ownership_lost is set under a real DB partition is proven separately by
    tests/integration/test_operation_multiworker_postgres.py::
    test_partition_after_claim_starts_second_cascade_window_documented; here we
    take that outcome as given and prove the cascade honors it.)"""
    from src.rico_chat_api import RicoChatAPI
    from src.services import operation_state as ops

    ops.reset_for_tests()
    monkeypatch.setenv("JOOBLE_API_KEY", "k")
    calls = {"n": 0}
    monkeypatch.setattr(
        jp, "_jooble_search",
        lambda r, l, *, cancel=None: (calls.__setitem__("n", calls["n"] + 1)
                      or FetchResult(items=[{"title": "x"}], provider="jooble")),
    )

    api = RicoChatAPI.__new__(RicoChatAPI)
    api._current_operation_id = "op_e2e"
    api._current_operation_attempt = 1
    token = api._current_cancellation_token()

    # Before ownership loss: the cascade runs normally.
    ok = jp.search_jobs("hse manager", cancel=token)
    assert ok.cancelled is False and calls["n"] == 1

    # The self-fence marks ownership lost (what the heartbeat does under a real
    # post-claim partition) → the very same token now cancels the cascade.
    ops._mark_ownership_lost("op_e2e", 1)
    calls["n"] = 0
    cancelled = jp.search_jobs("hse manager", location="dubai", cancel=token)
    assert cancelled.cancelled is True
    assert cancelled.error == "ownership_lost"
    assert calls["n"] == 0            # NO new provider work after cancellation
    ops.reset_for_tests()
