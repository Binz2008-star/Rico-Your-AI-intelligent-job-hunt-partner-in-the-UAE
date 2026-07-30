"""Tests for src/api/bounded_cache.py — BoundedLRUCache.

Covers:
1. Basic get/put
2. LRU eviction at maxsize
3. TTL expiry
4. Copy-on-read isolation (caller mutation does not corrupt cache)
5. Metrics accuracy (hits, misses, evictions, expirations, size)
6. Thread safety (concurrent put/get does not crash or lose data)
7. invalidate and clear
"""
from __future__ import annotations

import threading

import pytest

import src.api.bounded_cache as _bounded_cache
from src.api.bounded_cache import BoundedLRUCache, CacheMetrics


class _FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def monotonic(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


@pytest.fixture
def clock(monkeypatch):
    c = _FakeClock()
    monkeypatch.setattr(_bounded_cache.time, "monotonic", c.monotonic)
    return c



# ── 1. Basic get/put ──────────────────────────────────────────────────────────

class TestBasicGetPut:
    def test_put_then_get_returns_value(self):
        cache = BoundedLRUCache(maxsize=10, ttl_s=60)
        cache.put("k1", {"a": 1})
        assert cache.get("k1") == {"a": 1}

    def test_get_missing_key_returns_none(self):
        cache = BoundedLRUCache(maxsize=10, ttl_s=60)
        assert cache.get("nope") is None

    def test_put_overwrites_existing_key(self):
        cache = BoundedLRUCache(maxsize=10, ttl_s=60)
        cache.put("k", "v1")
        cache.put("k", "v2")
        assert cache.get("k") == "v2"


# ── 2. LRU eviction ───────────────────────────────────────────────────────────

class TestLRUEviction:
    def test_evicts_lru_when_full(self):
        cache = BoundedLRUCache(maxsize=3, ttl_s=60)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        # Access "a" to make it most-recently-used
        cache.get("a")
        # Insert "d" — "b" should be evicted (least recently used)
        cache.put("d", 4)
        assert cache.get("b") is None
        assert cache.get("a") == 1
        assert cache.get("c") == 3
        assert cache.get("d") == 4

    def test_eviction_counter_increments(self):
        cache = BoundedLRUCache(maxsize=2, ttl_s=60)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)  # evicts "a"
        m = cache.metrics()
        assert m.evictions == 1
        assert m.size == 2


# ── 3. TTL expiry ─────────────────────────────────────────────────────────────

class TestTTLExpiry:
    def test_expired_entry_returns_none(self, clock):
        cache = BoundedLRUCache(maxsize=10, ttl_s=0.1)
        cache.put("k", "v")
        clock.advance(0.15)
        assert cache.get("k") is None

    def test_expiration_counter_increments(self, clock):
        cache = BoundedLRUCache(maxsize=10, ttl_s=0.1)
        cache.put("k", "v")
        clock.advance(0.15)
        cache.get("k")
        m = cache.metrics()
        assert m.expirations == 1
        assert m.misses == 1

    def test_ttl_zero_disables_expiry(self, clock):
        cache = BoundedLRUCache(maxsize=10, ttl_s=0)
        cache.put("k", "v")
        clock.advance(0.05)
        assert cache.get("k") == "v"


# ── 4. Copy-on-read isolation ─────────────────────────────────────────────────

class TestCopyOnRead:
    def test_caller_mutation_does_not_corrupt_cache(self):
        cache = BoundedLRUCache(maxsize=10, ttl_s=60, copy_on_read=True)
        cache.put("k", {"list": [1, 2, 3]})
        val = cache.get("k")
        assert val is not None
        val["list"].append(999)
        # Cache should be unaffected
        fresh = cache.get("k")
        assert fresh == {"list": [1, 2, 3]}

    def test_copy_on_read_false_returns_same_object(self):
        cache = BoundedLRUCache(maxsize=10, ttl_s=60, copy_on_read=False)
        cache.put("k", {"list": [1, 2]})
        val = cache.get("k")
        assert val is not None
        val["list"].append(999)
        # Now cache IS mutated (caller asked for no-copy)
        assert cache.get("k") == {"list": [1, 2, 999]}

    def test_put_defensive_copy_isolation(self):
        cache = BoundedLRUCache(maxsize=10, ttl_s=60)
        value = {"list": [1, 2, 3]}
        cache.put("k", value)
        value["list"].append(999)
        # Cache should hold a copy, not the original reference
        assert cache.get("k") == {"list": [1, 2, 3]}


# ── 5. Metrics ────────────────────────────────────────────────────────────────

class TestMetrics:
    def test_metrics_track_hits_and_misses(self):
        cache = BoundedLRUCache(maxsize=10, ttl_s=60)
        cache.put("k", "v")
        cache.get("k")  # hit
        cache.get("k")  # hit
        cache.get("x")  # miss
        m = cache.metrics()
        assert m.hits == 2
        assert m.misses == 1
        assert m.size == 1

    def test_metrics_as_dict(self):
        cache = BoundedLRUCache(maxsize=10, ttl_s=60)
        cache.put("k", "v")
        cache.get("k")
        d = cache.metrics().as_dict()
        assert "hits" in d
        assert "misses" in d
        assert "evictions" in d
        assert "expirations" in d
        assert "size" in d
        assert d["hits"] == 1


# ── 6. Thread safety ──────────────────────────────────────────────────────────

class TestThreadSafety:
    def test_concurrent_access_does_not_crash(self):
        cache = BoundedLRUCache(maxsize=100, ttl_s=60)
        errors: list[Exception] = []

        def worker():
            try:
                for i in range(200):
                    cache.put(f"key_{i}", i)
                    cache.get(f"key_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        m = cache.metrics()
        assert m.size <= 100  # bounded


# ── 7. invalidate and clear ───────────────────────────────────────────────────

class TestInvalidateClear:
    def test_invalidate_removes_key(self):
        cache = BoundedLRUCache(maxsize=10, ttl_s=60)
        cache.put("k", "v")
        assert cache.invalidate("k") is True
        assert cache.get("k") is None
        assert cache.invalidate("k") is False

    def test_clear_removes_all(self):
        cache = BoundedLRUCache(maxsize=10, ttl_s=60)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None
        m = cache.metrics()
        assert m.size == 0


# ── 8. Expired-item cleanup ───────────────────────────────────────────────────

class TestExpiryCleanup:
    def test_expired_item_cleaned_by_put(self, clock):
        cache = BoundedLRUCache(maxsize=3, ttl_s=1.0)
        cache.put("a", 1)
        clock.advance(2.0)
        cache.put("b", 2)
        cache.put("c", 3)
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3
        m = cache.metrics()
        assert m.expirations == 1
        assert m.evictions == 0
        assert m.size == 2

    def test_expired_items_counted_as_expirations_not_evictions(self, clock):
        cache = BoundedLRUCache(maxsize=2, ttl_s=1.0)
        cache.put("a", 1)
        cache.put("b", 2)
        clock.advance(2.0)
        cache.put("c", 3)
        m = cache.metrics()
        assert m.expirations == 2
        assert m.evictions == 0
        assert m.size == 1

    def test_metrics_size_excludes_expired_items(self, clock):
        cache = BoundedLRUCache(maxsize=10, ttl_s=1.0)
        cache.put("k", "v")
        clock.advance(2.0)
        m = cache.metrics()
        assert m.size == 0
        assert m.expirations == 0  # not removed, only not counted in size


# ── 9. Constructor validation ─────────────────────────────────────────────────

class TestConstructorValidation:
    def test_zero_maxsize_raises(self):
        import pytest
        with pytest.raises(ValueError):
            BoundedLRUCache(maxsize=0)

    def test_negative_ttl_raises(self):
        import pytest
        with pytest.raises(ValueError):
            BoundedLRUCache(maxsize=10, ttl_s=-1)
