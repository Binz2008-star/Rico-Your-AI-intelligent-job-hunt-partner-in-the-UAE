"""
src/jsearch_client.py
Resilient JSearch (RapidAPI) fetch layer shared by the legacy pipeline
(src/job_sources.py) and the live chat path (src/rico_chat_api.py).

Responsibilities (none of which existed before this module):
  * In-memory TTL cache keyed by the query string, so repeated searches reuse
    a recent response instead of burning RapidAPI quota.
  * 429 / 5xx retry with exponential backoff and a hard retry cap.
  * Normalization that preserves BOTH apply and alternate links:
        apply_link  ← job_apply_link
        alt_link    ← best trusted apply_options mirror, else job_google_link
  * Structured logging that never leaks user data — only query text, cache
    hit/miss, retry count, status codes, and result counts.

Returns a FetchResult so callers can tell a genuine "no results" apart from a
rate-limited source and surface the right message to the user.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from src.services.source_quality import pick_best_alternate_apply_link

logger = logging.getLogger(__name__)

_JSEARCH_HOST = "jsearch.p.rapidapi.com"
_JSEARCH_BASE = f"https://{_JSEARCH_HOST}"

# Cache + retry knobs (overridable via env without code changes).
_CACHE_TTL_S = int(os.getenv("JSEARCH_CACHE_TTL_S", "900"))      # 15 min
_MAX_RETRIES = int(os.getenv("JSEARCH_MAX_RETRIES", "3"))         # on 429/5xx
_BACKOFF_BASE_S = float(os.getenv("JSEARCH_BACKOFF_BASE_S", "1"))  # 1s,2s,4s
_TIMEOUT_S = int(os.getenv("JSEARCH_TIMEOUT_S", "12"))

# Process-local cache: query -> (expires_at_epoch, items).
_cache: Dict[str, "tuple[float, List[Dict[str, Any]]]"] = {}
_cache_lock = RLock()


@dataclass
class FetchResult:
    """Outcome of a JSearch query. `rate_limited` is True when retries were
    exhausted on a 429 so callers can show an alternate-link message."""
    items: List[Dict[str, Any]] = field(default_factory=list)
    cache_hit: bool = False
    rate_limited: bool = False
    retries: int = 0
    error: Optional[str] = None


def clear_cache() -> None:
    """Drop all cached responses (used by tests)."""
    with _cache_lock:
        _cache.clear()


def _cache_get(query: str) -> Optional[List[Dict[str, Any]]]:
    with _cache_lock:
        entry = _cache.get(query)
        if not entry:
            return None
        expires_at, items = entry
        if time.time() >= expires_at:
            _cache.pop(query, None)
            return None
        return items


def _cache_put(query: str, items: List[Dict[str, Any]]) -> None:
    with _cache_lock:
        _cache[query] = (time.time() + _CACHE_TTL_S, items)


def normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Map a raw JSearch job into Rico's job dict, preserving both links.

    `link` stays as the best single URL for legacy callers; `apply_link` and
    `alt_link` are kept separately so the apply-fallback chain can use them.
    """
    apply_link = str(item.get("job_apply_link") or "").strip()
    # Best trusted mirror from apply_options beats the Google intermediary,
    # which downstream (_format_match) blanks anyway. Google link stays as the
    # legacy fallback when no trusted mirror exists.
    alt_link = (
        pick_best_alternate_apply_link(apply_link, item.get("apply_options"))
        or str(item.get("job_google_link") or "").strip()
    )
    location = ", ".join(filter(None, [
        item.get("job_city") or "",
        item.get("job_state") or "",
        item.get("job_country") or "",
    ])) or "UAE"
    return {
        "title":           str(item.get("job_title") or ""),
        "company":         str(item.get("employer_name") or ""),
        "location":        location,
        "link":            apply_link or alt_link,
        "apply_link":      apply_link,
        "alt_link":        alt_link,
        "description":     str(item.get("job_description") or ""),
        "source":          "jsearch",
        "salary_string":   str(item.get("job_salary_string") or ""),
        "employment_type": str(item.get("job_employment_type") or ""),
        "job_id":          str(item.get("job_id") or ""),
    }


def _raw_items(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, dict):
        inner = data.get("data")
        if isinstance(inner, dict):
            return inner.get("jobs", []) or []
        if isinstance(inner, list):
            return inner
    return []


_UAE_CITY_NAMES = frozenset([
    "dubai", "abu dhabi", "sharjah", "ajman",
    "ras al khaimah", "fujairah", "al ain", "umm al quwain",
])

# Accepted values of JSearch's `job_country` field for a UAE job. JSearch usually
# returns the ISO alpha-2 code "AE", but full names show up too.
_UAE_COUNTRY_VALUES = frozenset([
    "ae", "are", "uae", "u.a.e.", "united arab emirates", "emirates",
])


def _is_uae_job(item: Dict[str, Any]) -> bool:
    """True unless the raw JSearch item is explicitly tagged with a non-UAE country.

    JSearch occasionally returns out-of-country jobs even when `country=ae` is
    requested (e.g. a Texas role surfacing in a UAE search). We reject an item
    only when its `job_country` is present AND clearly not the UAE; a missing or
    unknown country is kept because the query already targeted `country=ae`.
    """
    country = str(item.get("job_country") or "").strip().lower()
    if not country:
        return True
    return country in _UAE_COUNTRY_VALUES


def build_queries_for_profile(
    target_roles: List[str],
    preferred_cities: List[str],
    *,
    max_queries: int = 12,
) -> List[str]:
    """Return deduplicated JSearch query strings derived from a user's profile.

    Strategy: city-qualified variants first (most targeted), then base "Role UAE"
    fallback. Capped at *max_queries* to stay within rate-limit budgets.

    Cities that don't look like UAE cities are silently ignored so a user who typed
    "Remote" or "Open to relocation" doesn't generate nonsense queries.
    """
    queries: list[str] = []
    seen: set[str] = set()

    def _add(q: str) -> None:
        norm = q.strip()
        if norm.lower() not in seen:
            seen.add(norm.lower())
            queries.append(norm)

    # Keep only recognisable UAE cities; fall back to empty list (UAE-wide search).
    uae_cities: list[str] = [
        c.strip() for c in preferred_cities
        if any(uae.lower() in c.lower() for uae in _UAE_CITY_NAMES)
    ]

    for role in target_roles[:6]:
        role = (role or "").strip()
        if not role:
            continue
        for city in uae_cities[:3]:
            _add(f"{role} {city} UAE")
        _add(f"{role} UAE")
        if len(queries) >= max_queries:
            break

    return queries[:max_queries]


def search(query: str, *, use_cache: bool = True, country: str = "ae") -> FetchResult:
    """Fetch + normalize JSearch results for *query* with cache, retry, backoff.

    Never raises. On a rate-limited source it returns whatever was cached (if
    anything) plus `rate_limited=True`.
    """
    api_key = os.getenv("RAPIDAPI_KEY", "").strip()
    if not api_key:
        logger.debug("jsearch: RAPIDAPI_KEY not set — skipping query")
        return FetchResult(error="no_api_key")

    if use_cache:
        cached = _cache_get(query)
        if cached is not None:
            logger.info("jsearch_cache hit query=%r results=%d", query, len(cached))
            return FetchResult(items=cached, cache_hit=True)
    logger.info("jsearch_cache miss query=%r", query)

    url = (
        f"{_JSEARCH_BASE}/search-v2"
        f"?query={quote_plus(query)}&num_pages=1&country={country}&date_posted=all"
    )
    headers = {
        "x-rapidapi-host": _JSEARCH_HOST,
        "x-rapidapi-key": api_key,
        "Content-Type": "application/json",
    }

    retries = 0
    last_error: Optional[str] = None
    while retries <= _MAX_RETRIES:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
                data = json.loads(resp.read().decode())
            raw_items = [
                normalize_item(it) for it in _raw_items(data) if _is_uae_job(it)
            ]
            seen_ids: set = set()
            items = []
            for it in raw_items:
                jid = it.get("job_id", "")
                if jid and jid in seen_ids:
                    continue
                if jid:
                    seen_ids.add(jid)
                items.append(it)
            _cache_put(query, items)
            logger.info("jsearch_fetch ok query=%r results=%d retries=%d", query, len(items), retries)
            return FetchResult(items=items, retries=retries)
        except urllib.error.HTTPError as exc:
            code = getattr(exc, "code", 0)
            if code == 429 or 500 <= code < 600:
                retries += 1
                last_error = f"http_{code}"
                if retries > _MAX_RETRIES:
                    break
                backoff = _BACKOFF_BASE_S * (2 ** (retries - 1))
                logger.warning(
                    "jsearch_retry query=%r status=%d retry=%d/%d backoff=%.1fs",
                    query, code, retries, _MAX_RETRIES, backoff,
                )
                time.sleep(backoff)
                continue
            logger.warning("jsearch_http_error query=%r status=%d", query, code)
            last_error = f"http_{code}"
            break
        except Exception as exc:  # network, JSON, timeout
            logger.warning("jsearch_fetch_failed query=%r err=%s", query, type(exc).__name__)
            last_error = type(exc).__name__
            break

    rate_limited = last_error == "http_429"
    if rate_limited:
        logger.warning("jsearch_rate_limited query=%r retries=%d", query, retries)
    # Serve stale cache if we have it, even when rate-limited.
    stale = _cache_get(query) if use_cache else None
    return FetchResult(
        items=stale or [],
        cache_hit=bool(stale),
        rate_limited=rate_limited,
        retries=retries,
        error=last_error,
    )
