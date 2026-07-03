"""
Audit finding D2: the in-process idempotency cache (_DEDUP_CACHE) must not grow
unbounded. _mem_seed opportunistically sweeps entries older than the TTL once the
cache crosses _DEDUP_SWEEP_THRESHOLD. Expired entries are already treated as
non-duplicates, so eviction is a pure memory reclaim with no behavior change.
"""
import time

import src.repositories.audit_repo as ar


def _seed(action_id: str, status: str = "success") -> None:
    ar._mem_seed({"action_id": action_id, "result_status": status})


def setup_function(_fn):
    with ar._DEDUP_LOCK:
        ar._DEDUP_CACHE.clear()


def test_sweep_evicts_expired_entries_when_threshold_crossed():
    now = time.monotonic()
    stale_ts = now - ar._DEDUP_TTL_S - 100  # older than the TTL
    with ar._DEDUP_LOCK:
        for i in range(ar._DEDUP_SWEEP_THRESHOLD):
            ar._DEDUP_CACHE[f"stale-{i}"] = (stale_ts, "success")

    # One more seed crosses the threshold and triggers the sweep.
    _seed("fresh-action")

    # All expired entries are gone; only the fresh one remains.
    assert "fresh-action" in ar._DEDUP_CACHE
    assert not any(k.startswith("stale-") for k in ar._DEDUP_CACHE)
    assert len(ar._DEDUP_CACHE) == 1


def test_sweep_does_not_evict_live_entries():
    now = time.monotonic()
    with ar._DEDUP_LOCK:
        for i in range(ar._DEDUP_SWEEP_THRESHOLD):
            ar._DEDUP_CACHE[f"live-{i}"] = (now, "success")

    _seed("another-live")

    # Nothing is expired, so the sweep must not drop any live dedup entry —
    # evicting a live entry would allow a real double-apply.
    assert len(ar._DEDUP_CACHE) == ar._DEDUP_SWEEP_THRESHOLD + 1
    assert "another-live" in ar._DEDUP_CACHE


def test_below_threshold_keeps_all_entries():
    # No sweep below the threshold; small caches are untouched.
    for i in range(50):
        _seed(f"small-{i}")
    assert len(ar._DEDUP_CACHE) == 50


def test_expired_live_entry_still_reads_as_not_duplicate():
    # Behavioral guard: an expired entry is a non-duplicate whether or not it was
    # swept, so the sweep cannot change dedup outcomes.
    with ar._DEDUP_LOCK:
        ar._DEDUP_CACHE["old"] = (time.monotonic() - ar._DEDUP_TTL_S - 1, "success")
    assert ar._mem_check_duplicate("old") is False
