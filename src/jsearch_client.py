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
from typing import Any, Callable, Dict, List, Optional
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

# ── Cooperative cancellation (DEC-20260721-001 slice-4 closure) ───────────────
# A cancel check is a zero-argument callable returning True once the caller's
# right to do this work has been revoked — in production it is bound to
# operation_state.ownership_lost(operation_id, attempt), i.e. this worker's
# heartbeat self-fenced after a post-claim DB partition or a takeover. The
# contract at this layer:
#   * NO new network request (first call or retry) is issued once the check
#     reports True — checked before every request attempt;
#   * a response already in flight when ownership is lost is DISCARDED: its
#     items are dropped, nothing is cached, and nothing is written to the
#     job_observations archive;
#   * an HTTP request that is already on the wire is NOT aborted (cooperative
#     model — we never claim to cancel a sent request, we refuse to use it).
# A cancelled outcome is reported as FetchResult(error="cancelled") with no
# items, never served from stale cache.
CancelCheck = Optional[Callable[[], bool]]
CANCELLED_ERROR = "cancelled"


def _is_cancelled(should_cancel: CancelCheck) -> bool:
    if should_cancel is None:
        return False
    try:
        return bool(should_cancel())
    except Exception:
        # FAIL CLOSED (owner review 2026-07-21): a check was SUPPLIED, so this
        # work is ownership-gated — if the check itself is broken we cannot
        # prove we still own the operation, and continuing would risk exactly
        # the duplicate provider work this gate exists to prevent.
        logger.error("cancel check raised — failing closed (treated as cancelled)", exc_info=True)
        return True


def _cancellable_wait(seconds: float, should_cancel: CancelCheck) -> bool:
    """Cancel-aware replacement for time.sleep in backoff paths.

    Waits up to *seconds*, polling the cancel check every 50ms so a backoff
    never delays the cooperative stop by more than one poll interval. Returns
    True when cancellation was observed (the caller must not issue further
    requests). With no check supplied it degrades to a plain sleep."""
    if should_cancel is None:
        time.sleep(seconds)
        return False
    deadline = time.monotonic() + seconds
    while True:
        if _is_cancelled(should_cancel):
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return _is_cancelled(should_cancel)
        time.sleep(min(0.05, remaining))


@dataclass
class FetchResult:
    """Outcome of a job query.

    Shared by every provider (JSearch, Jooble, Adzuna) and the provider
    orchestrator in ``src/job_providers.py`` so callers handle one type.

    - ``rate_limited`` is True when retries were exhausted on a 429 (temporary).
    - ``quota_exhausted`` is True when the subscription's hard quota is spent
      (e.g. RapidAPI BASIC at 100%) — a longer, non-retryable degraded state.
    - ``provider`` names the source that produced ``items`` ("jsearch", "jooble",
      "adzuna", "cache", "internal", or "none" when every provider was skipped).
    - ``error == "cancelled"`` means the caller's cancel check reported the work
      was revoked (ownership lost): no further requests were issued and any
      in-flight response was discarded — ``items`` is always empty then.
    """
    items: List[Dict[str, Any]] = field(default_factory=list)
    cache_hit: bool = False
    rate_limited: bool = False
    retries: int = 0
    error: Optional[str] = None
    quota_exhausted: bool = False
    provider: str = "jsearch"


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
    `employer_url` surfaces the company's own website when JSearch provides it;
    it is never treated as a verified apply link.
    `apply_is_direct` reflects JSearch's own signal that the apply link goes
    straight to the employer/ATS without an intermediate page.
    """
    apply_link = str(item.get("job_apply_link") or "").strip()
    # Best trusted mirror from apply_options beats the Google intermediary,
    # which downstream (resolve_job_link) blanks anyway. Google link stays as
    # the legacy fallback when no trusted mirror exists.
    alt_link = (
        pick_best_alternate_apply_link(apply_link, item.get("apply_options"))
        or str(item.get("job_google_link") or "").strip()
    )
    employer_url = str(item.get("employer_website") or "").strip()
    apply_is_direct = bool(item.get("job_apply_is_direct"))
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
        "employer_url":    employer_url,
        "apply_is_direct": apply_is_direct,
        "description":     str(item.get("job_description") or ""),
        "source":          "jsearch",
        "salary_string":   str(item.get("job_salary_string") or ""),
        "employment_type": str(item.get("job_employment_type") or ""),
        "job_id":          str(item.get("job_id") or ""),
        # Provider's CLAIMED posting date — untrusted; kept for the
        # job_observations archive (observed_at is the authoritative clock).
        "posted_at":       str(item.get("job_posted_at_datetime_utc") or ""),
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


def search(
    query: str,
    *,
    use_cache: bool = True,
    country: str = "ae",
    should_cancel: CancelCheck = None,
) -> FetchResult:
    """Fetch + normalize JSearch results for *query* with cache, retry, backoff.

    Never raises. On a rate-limited source it returns whatever was cached (if
    anything) plus `rate_limited=True`.

    *should_cancel* is the cooperative cancellation check (see CancelCheck):
    once it reports True no new request or retry is issued and an in-flight
    response is discarded (no cache write, no observations archive write).
    """
    if _is_cancelled(should_cancel):
        logger.info("jsearch_cancelled query=%r stage=before_start", query)
        return FetchResult(error=CANCELLED_ERROR)

    api_key = os.getenv("RAPIDAPI_KEY", "").strip()
    if not api_key:
        logger.debug("jsearch: RAPIDAPI_KEY not set — skipping query")
        return FetchResult(error="no_api_key")

    if use_cache:
        cached = _cache_get(query)
        if cached is not None:
            if _is_cancelled(should_cancel):
                # Loss observed between the entry check and the cache read —
                # even a cached result must not be returned to a fenced caller.
                logger.info("jsearch_cancelled query=%r stage=cache_hit_discarded", query)
                return FetchResult(error=CANCELLED_ERROR)
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
        # Cooperative checkpoint: guards the FIRST request and every retry
        # (including one whose backoff sleep just elapsed) — once ownership is
        # lost, no new request goes on the wire.
        if _is_cancelled(should_cancel):
            logger.info(
                "jsearch_cancelled query=%r stage=before_request retries=%d",
                query, retries,
            )
            return FetchResult(error=CANCELLED_ERROR, retries=retries)
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
                data = json.loads(resp.read().decode())
            if _is_cancelled(should_cancel):
                # Ownership was lost while this response was in flight:
                # DISCARD it — no items, no cache write, no observations write.
                logger.info("jsearch_cancelled query=%r stage=response_discarded", query)
                return FetchResult(error=CANCELLED_ERROR, retries=retries)
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
            # Re-check IMMEDIATELY before each side effect (owner review
            # 2026-07-21): loss can flip during normalization, and a fenced
            # worker must not perform storage writes after that point.
            if _is_cancelled(should_cancel):
                logger.info("jsearch_cancelled query=%r stage=before_cache_write", query)
                return FetchResult(error=CANCELLED_ERROR, retries=retries)
            _cache_put(query, items)
            # Posting-history archive: fresh fetches only — a cache hit is the
            # same response re-served, not a new sighting. Never raises.
            if _is_cancelled(should_cancel):
                logger.info("jsearch_cancelled query=%r stage=before_observations", query)
                return FetchResult(error=CANCELLED_ERROR, retries=retries)
            try:
                from src.repositories.job_observations_repo import record_observations
                record_observations(items, provider="jsearch", query_context=query, country=country)
            except Exception:
                logger.debug("job_observations hook skipped", exc_info=True)
            if _is_cancelled(should_cancel):
                logger.info("jsearch_cancelled query=%r stage=before_return", query)
                return FetchResult(error=CANCELLED_ERROR, retries=retries)
            logger.info("jsearch_fetch ok query=%r results=%d retries=%d", query, len(items), retries)
            return FetchResult(items=items, retries=retries)
        except urllib.error.HTTPError as exc:
            code = getattr(exc, "code", 0)
            # 403 on RapidAPI means the monthly quota is fully spent — there is no
            # point retrying, so stop immediately and flag quota_exhausted.
            if code == 403:
                logger.warning("jsearch_quota_exhausted query=%r status=403", query)
                last_error = "http_403"
                break
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
                # Cancel-aware backoff: ownership loss during the wait stops
                # the cooperative flow within one 50ms poll — the retry
                # request is never issued and no stale cache is served.
                if _cancellable_wait(backoff, should_cancel):
                    logger.info(
                        "jsearch_cancelled query=%r stage=during_backoff retries=%d",
                        query, retries,
                    )
                    return FetchResult(error=CANCELLED_ERROR, retries=retries)
                continue
            logger.warning("jsearch_http_error query=%r status=%d", query, code)
            last_error = f"http_{code}"
            break
        except Exception as exc:  # network, JSON, timeout
            logger.warning("jsearch_fetch_failed query=%r err=%s", query, type(exc).__name__)
            last_error = type(exc).__name__
            break

    # Final checkpoint before the stale-cache fallback: a fenced caller gets
    # nothing usable, not even stale items (owner review 2026-07-21).
    if _is_cancelled(should_cancel):
        logger.info("jsearch_cancelled query=%r stage=before_stale_fallback", query)
        return FetchResult(error=CANCELLED_ERROR, retries=retries)
    rate_limited = last_error == "http_429"
    quota_exhausted = last_error == "http_403"
    if rate_limited:
        logger.warning("jsearch_rate_limited query=%r retries=%d", query, retries)
    # Serve stale cache if we have it, even when rate-limited / quota-exhausted.
    stale = _cache_get(query) if use_cache else None
    return FetchResult(
        items=stale or [],
        cache_hit=bool(stale),
        rate_limited=rate_limited,
        quota_exhausted=quota_exhausted,
        retries=retries,
        error=last_error,
        provider="jsearch",
    )
