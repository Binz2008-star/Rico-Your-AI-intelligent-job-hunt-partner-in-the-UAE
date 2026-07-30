"""src/api/bounded_cache.py

Bounded LRU cache with TTL, copy-on-read, and metrics.

This module provides a single reusable cache class that:
- Bounds memory by evicting least-recently-used entries (maxsize).
- Expires entries after a configurable TTL (seconds).
- Returns a *copy* of cached values on read so callers cannot mutate
  the stored object and corrupt the cache for the next reader.
- Exposes hit/miss/eviction/expiry counters for observability.

No existing cache is swapped in this PR — this is the foundation.
Callers adopt it incrementally in follow-up PRs.
"""
from __future__ import annotations

import copy
import logging
import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_MAXSIZE = int(os.getenv("RICO_CACHE_MAXSIZE", "512"))
_DEFAULT_TTL_S = float(os.getenv("RICO_CACHE_TTL_S", "300"))


@dataclass
class CacheMetrics:
    """Snapshot of cache counters (zero-allocation reads)."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    size: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "expirations": self.expirations,
            "size": self.size,
        }


class BoundedLRUCache:
    """Thread-safe bounded LRU cache with TTL and copy-on-read.

    Parameters
    ----------
    maxsize:
        Maximum number of entries. When exceeded, the least-recently-used
        entry is evicted. Defaults to ``RICO_CACHE_MAXSIZE`` (512).
    ttl_s:
        Time-to-live in seconds. Entries older than this are expired on
        next access. Defaults to ``RICO_CACHE_TTL_S`` (300s = 5 min).
        Set to 0 to disable TTL (expiry checked only on eviction pressure).
    copy_on_read:
        When True (default), ``get`` returns a deep copy of the stored
        value so callers cannot mutate the cache indirectly. Set to False
        only when the cached values are known-immutable.
    """

    def __init__(
        self,
        maxsize: int = _DEFAULT_MAXSIZE,
        ttl_s: float = _DEFAULT_TTL_S,
        *,
        copy_on_read: bool = True,
    ) -> None:
        if maxsize < 1:
            raise ValueError("maxsize must be >= 1")
        if ttl_s < 0:
            raise ValueError("ttl_s must be >= 0")
        self._maxsize = maxsize
        self._ttl_s = ttl_s
        self._copy_on_read = copy_on_read
        self._data: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expirations = 0

    def _is_expired(self, expires_at: float, now: float) -> bool:
        return self._ttl_s > 0 and now >= expires_at

    def _expire_stale(self, now: float) -> None:
        """Remove TTL-expired entries before they affect capacity or metrics.

        Expired removals are recorded as expirations, not evictions.
        """
        expired = [key for key, (expires_at, _) in self._data.items() if self._is_expired(expires_at, now)]
        for key in expired:
            del self._data[key]
            self._expirations += 1

    def _live_count(self, now: float) -> int:
        """Number of entries that have not yet passed their TTL."""
        if self._ttl_s <= 0:
            return len(self._data)
        return sum(1 for expires_at, _ in self._data.values() if not self._is_expired(expires_at, now))

    def get(self, key: str) -> Any | None:
        """Return a copy of the cached value, or None on miss/expiry.

        A miss increments the miss counter. A hit increments the hit
        counter, moves the entry to most-recently-used, and returns a
        deep copy (when ``copy_on_read`` is True).
        """
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self._misses += 1
                return None
            expires_at, value = entry
            now = time.monotonic()
            if self._ttl_s > 0 and now >= expires_at:
                del self._data[key]
                self._expirations += 1
                self._misses += 1
                return None
            self._data.move_to_end(key)
            self._hits += 1
            if self._copy_on_read:
                return copy.deepcopy(value)
            return value

    def put(self, key: str, value: Any) -> None:
        """Store a defensive copy of *value* under *key*, expiring stale
        entries and evicting the least-recently-used live item if over
        capacity.
        """
        with self._lock:
            now = time.monotonic()
            expires_at = now + self._ttl_s if self._ttl_s > 0 else float("inf")
            stored = copy.deepcopy(value)
            self._data[key] = (expires_at, stored)
            self._data.move_to_end(key)
            self._expire_stale(now)
            while len(self._data) > self._maxsize:
                self._data.popitem(last=False)
                self._evictions += 1

    def invalidate(self, key: str) -> bool:
        """Remove *key* from the cache. Returns True if it was present."""
        with self._lock:
            if key in self._data:
                del self._data[key]
                return True
            return False

    def clear(self) -> None:
        """Drop all entries."""
        with self._lock:
            self._data.clear()

    def metrics(self) -> CacheMetrics:
        """Return a snapshot of hit/miss/eviction/expiry counters."""
        with self._lock:
            now = time.monotonic()
            return CacheMetrics(
                hits=self._hits,
                misses=self._misses,
                evictions=self._evictions,
                expirations=self._expirations,
                size=self._live_count(now),
            )

    @property
    def maxsize(self) -> int:
        return self._maxsize

    @property
    def ttl_s(self) -> float:
        return self._ttl_s
