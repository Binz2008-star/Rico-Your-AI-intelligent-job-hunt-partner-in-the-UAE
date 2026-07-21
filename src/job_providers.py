"""
src/job_providers.py
Provider orchestration for live job search.

Background
----------
The RapidAPI JSearch BASIC subscription hit 100% of its monthly quota, which
surfaced as rate-limited statuses, "Link unavailable", and dead-end job cards.
This module adds a low-cost / free provider cascade in front of JSearch so the
product keeps working (and stops burning quota) when one provider is degraded.

Cascade (``search_jobs``)
-------------------------
1. Cache first (24h normalized cache — identical searches never hit the network).
2. Internal recent/saved results (optional ``internal_lookup`` callback).
3. Jooble       — if ``JOOBLE_API_KEY`` is set and the provider is healthy.
4. Adzuna       — if ``ADZUNA_APP_ID`` + ``ADZUNA_APP_KEY`` are set (opt-in).
5. JSearch      — if ``RAPIDAPI_KEY`` is set and the provider is healthy.
6. Degraded     — empty result flagged so the chat layer shows a safe-fallback CTA
                  instead of dead-end cards.

Design rules
------------
* No API keys are hardcoded — every key is read from the environment.
* Secrets are never logged (we log provider name, counts, status — never keys/URLs
  that embed a key).
* A provider that returns a quota / rate-limit / hard error is marked *degraded*
  for a cooldown window so we stop hammering it and burning calls.
* All providers return :class:`jsearch_client.FetchResult` so callers handle one
  type. Never raises — failures degrade gracefully.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from threading import RLock
from typing import Any, Callable, Dict, List, Optional

from src.jsearch_client import FetchResult
from src.services.cancellation import CancellationToken, is_cancelled as _is_cancelled

logger = logging.getLogger(__name__)


def _cancelled_result() -> FetchResult:
    """The single, distinct cancellation outcome (never no-results/degradation/
    quota/HTTP). Empty, flagged ``cancelled`` with ``error='ownership_lost'``;
    callers discard it without side effects."""
    return FetchResult(items=[], provider="none", cancelled=True, error="ownership_lost")

# ── Tunables (env-overridable, no code change needed) ─────────────────────────
# 24h shared result cache: identical (role, location) searches reuse results and
# never call an external provider again within the TTL.
_RESULT_CACHE_TTL_S = int(os.getenv("JOB_RESULT_CACHE_TTL_S", str(24 * 60 * 60)))
# How long a provider stays "degraded" after a transient error / rate-limit.
_DEGRADED_COOLDOWN_S = int(os.getenv("PROVIDER_DEGRADED_COOLDOWN_S", str(30 * 60)))
# How long a provider stays "degraded" after a hard quota exhaustion (longer).
_QUOTA_COOLDOWN_S = int(os.getenv("PROVIDER_QUOTA_COOLDOWN_S", str(6 * 60 * 60)))
# Per-provider HTTP budget. 6s (was 12s): a provider that cannot answer in
# 6 seconds is not worth the first-search wall time — production showed the
# old serial cascade stacking 12s timeouts into 30-60s first searches.
_HTTP_TIMEOUT_S = int(os.getenv("JOB_PROVIDER_TIMEOUT_S", "6"))
# Hedge stagger: provider N+1 launches this many seconds after provider N
# (or immediately once every already-launched provider finished empty).
# The stagger IS the cost preference — the cheaper provider gets a head
# start instead of an exclusive serial slot.
_HEDGE_STAGGER_S = float(os.getenv("JOB_PROVIDER_HEDGE_STAGGER_S", "2.5"))

_DEFAULT_UAE_LOCATION = "United Arab Emirates"

# ── 24h normalized result cache ───────────────────────────────────────────────
# key -> (expires_at_epoch, items)
_result_cache: Dict[str, "tuple[float, List[Dict[str, Any]]]"] = {}
_cache_lock = RLock()

# ── Provider health registry ──────────────────────────────────────────────────
# name -> {"degraded_until": epoch, "reason": str}
_health: Dict[str, Dict[str, Any]] = {}
_health_lock = RLock()


# ── State management (also used by tests) ─────────────────────────────────────

def clear_state() -> None:
    """Drop the result cache and all provider-health state (test isolation)."""
    with _cache_lock:
        _result_cache.clear()
    with _health_lock:
        _health.clear()


def _cache_key(role: str, location: str, country: str, context: str) -> str:
    return "|".join([
        (country or "ae").strip().lower(),
        (role or "").strip().lower(),
        (location or "").strip().lower(),
        (context or "").strip().lower(),
    ])


def _cache_get(key: str) -> Optional[List[Dict[str, Any]]]:
    with _cache_lock:
        entry = _result_cache.get(key)
        if not entry:
            return None
        expires_at, items = entry
        if time.time() >= expires_at:
            _result_cache.pop(key, None)
            return None
        return items


def _cache_put(key: str, items: List[Dict[str, Any]]) -> None:
    with _cache_lock:
        _result_cache[key] = (time.time() + _RESULT_CACHE_TTL_S, items)


def mark_degraded(provider: str, reason: str, cooldown_s: Optional[int] = None) -> None:
    """Flag *provider* as degraded for a cooldown window so we stop calling it."""
    cooldown = _QUOTA_COOLDOWN_S if reason == "quota" else _DEGRADED_COOLDOWN_S
    if cooldown_s is not None:
        cooldown = cooldown_s
    with _health_lock:
        _health[provider] = {
            "degraded_until": time.time() + cooldown,
            "reason": reason,
        }
    logger.warning(
        "provider_degraded provider=%s reason=%s cooldown_s=%d",
        provider, reason, cooldown,
    )


def is_degraded(provider: str) -> bool:
    """True while *provider* is inside its degraded cooldown window."""
    with _health_lock:
        entry = _health.get(provider)
        if not entry:
            return False
        if time.time() >= entry["degraded_until"]:
            _health.pop(provider, None)
            return False
        return True


def provider_health() -> Dict[str, Any]:
    """Admin/health indicator: per-provider configuration + degraded state.

    Safe to expose — reports only whether keys are *present* (never their values)
    and the current degraded reason/seconds-remaining.
    """
    now = time.time()
    out: Dict[str, Any] = {}
    for name in ("jooble", "adzuna", "jsearch"):
        with _health_lock:
            entry = _health.get(name)
        degraded = bool(entry and now < entry["degraded_until"])
        out[name] = {
            "configured": _provider_configured(name),
            "degraded": degraded,
            "reason": (entry or {}).get("reason") if degraded else None,
            "cooldown_remaining_s": (
                int(entry["degraded_until"] - now) if degraded else 0
            ),
        }
    return out


def _provider_configured(name: str) -> bool:
    if name == "jooble":
        return bool(os.getenv("JOOBLE_API_KEY", "").strip())
    if name == "adzuna":
        return bool(
            os.getenv("ADZUNA_APP_ID", "").strip()
            and os.getenv("ADZUNA_APP_KEY", "").strip()
        )
    if name == "jsearch":
        return bool(os.getenv("RAPIDAPI_KEY", "").strip())
    return False


def _record_observations_safe(
    items: List[Dict[str, Any]],
    *,
    provider: str,
    query_context: str,
    country: str = "ae",
) -> None:
    """Posting-history archive hook for fresh provider fetches. Never raises.

    Called only on fresh network responses — the caches above these clients
    mean a cache hit is the same response re-served, not a new sighting.
    (JSearch records inside jsearch_client.search() for the same reason.)
    """
    try:
        from src.repositories.job_observations_repo import record_observations
        record_observations(items, provider=provider, query_context=query_context, country=country)
    except Exception:
        logger.debug("job_observations hook skipped provider=%s", provider, exc_info=True)


# ── Jooble client ─────────────────────────────────────────────────────────────

def _normalize_jooble(item: Dict[str, Any]) -> Dict[str, Any]:
    """Map a raw Jooble job into Rico's normalized job dict."""
    link = str(item.get("link") or "").strip()
    return {
        "title":           str(item.get("title") or ""),
        "company":         str(item.get("company") or ""),
        "location":        str(item.get("location") or _DEFAULT_UAE_LOCATION),
        "link":            link,
        "apply_link":      link,
        "alt_link":        "",
        "description":     str(item.get("snippet") or ""),
        "source":          "jooble",
        "salary_string":   str(item.get("salary") or ""),
        "employment_type": str(item.get("type") or ""),
        "job_id":          str(item.get("id") or ""),
    }


def _jooble_search(role: str, location: str, *, page: int = 1) -> FetchResult:
    """Query Jooble for *role* in *location*. Never raises.

    Jooble's quota is small, so callers must front this with the cache. The key is
    embedded in the URL path per Jooble's API contract — it is therefore NEVER
    logged.
    """
    api_key = os.getenv("JOOBLE_API_KEY", "").strip()
    if not api_key:
        return FetchResult(error="no_api_key", provider="jooble")

    url = f"https://jooble.org/api/{api_key}"
    payload = json.dumps({
        "keywords": role,
        "location": location or _DEFAULT_UAE_LOCATION,
        "page": str(page),
    }).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        code = getattr(exc, "code", 0)
        rate_limited = code == 429
        # 401/403 from Jooble == bad/expired key or quota → degrade hard.
        quota = code in (401, 403)
        reason = "quota" if quota else ("rate_limit" if rate_limited else "http_error")
        mark_degraded("jooble", reason)
        logger.warning("jooble_http_error status=%d role=%r", code, role)
        return FetchResult(
            error=f"http_{code}", provider="jooble",
            rate_limited=rate_limited, quota_exhausted=quota,
        )
    except Exception as exc:  # network, JSON, timeout
        mark_degraded("jooble", "error")
        logger.warning("jooble_fetch_failed role=%r err=%s", role, type(exc).__name__)
        return FetchResult(error=type(exc).__name__, provider="jooble")

    raw_jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(raw_jobs, list):
        raw_jobs = []
    items = [_normalize_jooble(j) for j in raw_jobs if isinstance(j, dict)]
    _record_observations_safe(items, provider="jooble", query_context=f"{role} {location}".strip())
    logger.info("jooble_fetch ok role=%r results=%d", role, len(items))
    return FetchResult(items=items, provider="jooble")


# ── Adzuna client (optional / opt-in) ─────────────────────────────────────────

def _adzuna_enabled() -> bool:
    """Adzuna is disabled unless BOTH credentials are present in the environment."""
    return bool(
        os.getenv("ADZUNA_APP_ID", "").strip()
        and os.getenv("ADZUNA_APP_KEY", "").strip()
    )


def _adzuna_serves_country(country: str) -> bool:
    """True only when Adzuna's configured index matches the requested market.

    Adzuna is country-scoped by URL path and its coverage does NOT include the
    UAE (default ``ADZUNA_COUNTRY=gb``). Querying it for a UAE search returns
    GB-market listings (e.g. Manchester/Antrim) that must never surface in a
    UAE workflow, so Adzuna is dropped from the cascade whenever the requested
    country differs from the index it is configured to serve. This prevents the
    cascade from short-circuiting on out-of-market Adzuna results before the
    UAE-capable JSearch provider is reached.
    """
    requested = (country or "").strip().lower()
    configured = os.getenv("ADZUNA_COUNTRY", "gb").strip().lower()
    return bool(requested) and requested == configured


def _normalize_adzuna(item: Dict[str, Any]) -> Dict[str, Any]:
    """Map a raw Adzuna result into Rico's normalized job dict."""
    company = ""
    if isinstance(item.get("company"), dict):
        company = str(item["company"].get("display_name") or "")
    location = ""
    if isinstance(item.get("location"), dict):
        location = str(item["location"].get("display_name") or "")
    link = str(item.get("redirect_url") or "").strip()
    salary = ""
    smin, smax = item.get("salary_min"), item.get("salary_max")
    if smin or smax:
        salary = f"{smin or ''}-{smax or ''}".strip("-")
    return {
        "title":           str(item.get("title") or ""),
        "company":         company,
        "location":        location or _DEFAULT_UAE_LOCATION,
        "link":            link,
        "apply_link":      link,
        "alt_link":        "",
        "description":     str(item.get("description") or ""),
        "source":          "adzuna",
        "salary_string":   salary,
        "employment_type": str(item.get("contract_time") or ""),
        "job_id":          str(item.get("id") or ""),
    }


def _adzuna_search(role: str, location: str, *, page: int = 1) -> FetchResult:
    """Query Adzuna for *role* in *location*. Never raises.

    Adzuna's country coverage does not currently include the UAE; this client is
    provided as opt-in scaffolding (enabled only when both keys exist) and the
    target country is configurable via ``ADZUNA_COUNTRY`` (default "gb").
    """
    app_id = os.getenv("ADZUNA_APP_ID", "").strip()
    app_key = os.getenv("ADZUNA_APP_KEY", "").strip()
    if not (app_id and app_key):
        return FetchResult(error="no_api_key", provider="adzuna")

    country = os.getenv("ADZUNA_COUNTRY", "gb").strip().lower()
    from urllib.parse import urlencode, quote
    params = urlencode({
        "app_id": app_id,
        "app_key": app_key,
        "what": role,
        "where": location or "",
        "results_per_page": "20",
        "content-type": "application/json",
    })
    url = f"https://api.adzuna.com/v1/api/jobs/{quote(country)}/search/{page}?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        code = getattr(exc, "code", 0)
        rate_limited = code == 429
        quota = code in (401, 403)
        reason = "quota" if quota else ("rate_limit" if rate_limited else "http_error")
        mark_degraded("adzuna", reason)
        logger.warning("adzuna_http_error status=%d role=%r", code, role)
        return FetchResult(
            error=f"http_{code}", provider="adzuna",
            rate_limited=rate_limited, quota_exhausted=quota,
        )
    except Exception as exc:
        mark_degraded("adzuna", "error")
        logger.warning("adzuna_fetch_failed role=%r err=%s", role, type(exc).__name__)
        return FetchResult(error=type(exc).__name__, provider="adzuna")

    raw = data.get("results") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        raw = []
    items = [_normalize_adzuna(j) for j in raw if isinstance(j, dict)]
    _record_observations_safe(
        items, provider="adzuna",
        query_context=f"{role} {location}".strip(), country=country,
    )
    logger.info("adzuna_fetch ok role=%r results=%d", role, len(items))
    return FetchResult(items=items, provider="adzuna")


# ── JSearch (existing client, wrapped) ────────────────────────────────────────

def _jsearch_search(role: str, location: str, country: str) -> FetchResult:
    from src import jsearch_client
    query = f"{role} {location}".strip() if location else f"{role} UAE"
    result = jsearch_client.search(query, country=country)
    result.provider = "jsearch"
    return result


# ── Orchestrator ──────────────────────────────────────────────────────────────

def search_jobs(
    role: str,
    location: str = "",
    *,
    country: str = "ae",
    use_cache: bool = True,
    internal_lookup: Optional[Callable[[], List[Dict[str, Any]]]] = None,
    cache_context: str = "",
    cancel: Optional[CancellationToken] = None,
) -> FetchResult:
    """Run the provider cascade for *role* / *location* and return a FetchResult.

    The cascade short-circuits at the first provider that yields results, caches
    the normalized output for 24h, and degrades gracefully (never raises) when
    every provider is unavailable.

    Cooperative cancellation (``cancel``, DEC-20260721-001 slice 4): if the
    operation loses ownership at any observable checkpoint, the cascade stops
    launching NEW providers, discards any in-flight/harvested result WITHOUT
    side effects (no cache write, no winner), and returns the distinct
    cancelled FetchResult. An absent token means 'never cancelled'.
    """
    role = (role or "").strip()
    key = _cache_key(role, location, country, cache_context)

    # Cancelled before we start any work: no provider request, no cache read to
    # deliver — return the distinct cancelled outcome immediately.
    if _is_cancelled(cancel):
        logger.info("provider_cascade_cancelled role=%r stage=entry", role)
        return _cancelled_result()

    # 1. Cache first — identical searches never touch the network within the TTL.
    if use_cache:
        cached = _cache_get(key)
        if cached is not None:
            logger.info("provider_cache hit role=%r results=%d", role, len(cached))
            return FetchResult(items=cached, cache_hit=True, provider="cache")

    # 2. Internal recent/saved results (caller-supplied; e.g. recent matches).
    if internal_lookup is not None:
        try:
            internal_items = internal_lookup() or []
        except Exception as exc:
            internal_items = []
            logger.debug("internal_lookup failed err=%s", type(exc).__name__)
        if internal_items:
            logger.info("provider_internal hit role=%r results=%d", role, len(internal_items))
            _cache_put(key, internal_items)
            return FetchResult(items=internal_items, provider="internal")

    aggregate_rate_limited = False
    aggregate_quota = False

    # 3-5. External providers in cost order: Jooble → Adzuna → JSearch.
    #
    # HEDGED, not serial (perf regression fix, 2026-07-21): the old loop gave
    # each provider an exclusive serial slot, so one slow/timing-out provider
    # stacked its full HTTP budget in front of the others — production first
    # searches reached 30-60s on a warm instance. Now provider N+1 launches
    # _HEDGE_STAGGER_S after provider N (or IMMEDIATELY once every launched
    # provider has finished empty — fast failures keep the old fast
    # fall-through), and the first non-empty result wins. The stagger is the
    # cost preference: the cheaper provider keeps a head start, and a later
    # provider fires only when the cheaper one is slow or empty — the same
    # situations the serial cascade would have fired it anyway. Worst-case
    # wall time drops from sum(timeouts) to ~timeout + last stagger.
    cascade = [
        ("jooble", _provider_configured("jooble"), lambda: _jooble_search(role, location)),
        ("adzuna", _adzuna_enabled() and _adzuna_serves_country(country), lambda: _adzuna_search(role, location)),
        ("jsearch", _provider_configured("jsearch"), lambda: _jsearch_search(role, location, country)),
    ]
    # Whether any provider is configured at all. This separates a genuinely
    # *degraded* deployment (keys present but providers failing / quota-spent)
    # from one where no provider keys are set (e.g. local/test env). Only the
    # former should surface degraded-provider UX; the latter falls through to the
    # caller's existing empty/legacy handling so behaviour is unchanged.
    configured_any = any(configured for _, configured, _ in cascade)

    eligible: List[tuple] = []
    for name, configured, runner in cascade:
        if not configured:
            logger.debug("provider_skip provider=%s reason=not_configured", name)
            continue
        if is_degraded(name):
            logger.info("provider_skip provider=%s reason=degraded", name)
            continue
        eligible.append((name, runner))

    def _run_provider(name: str, runner: Callable[[], FetchResult]) -> FetchResult:
        # NEW-work guard: if ownership was already lost when this worker starts,
        # do NOT issue the provider request at all — this is the core "no new
        # provider work after cancellation" guarantee.
        if _is_cancelled(cancel):
            return _cancelled_result()
        # Degradation marking lives in the worker thread so a provider that
        # finishes AFTER a winner was chosen still records its rate/quota
        # state for the cooldown registry — UNLESS we've been cancelled, in
        # which case the in-flight response is discarded without side effects.
        result = runner()
        if _is_cancelled(cancel):
            return _cancelled_result()
        if result.rate_limited:
            mark_degraded(name, "rate_limit")
        if result.quota_exhausted:
            mark_degraded(name, "quota")
        return result

    if eligible:
        import concurrent.futures as _futures

        pool = _futures.ThreadPoolExecutor(
            max_workers=len(eligible), thread_name_prefix="jobprov"
        )
        pending: Dict[Any, str] = {}
        winner: Optional[FetchResult] = None
        started = 0
        t0 = time.time()
        cancelled = False
        try:
            while True:
                # Cancellation observed mid-cascade: stop launching NEW
                # providers and discard whatever is pending — no winner, no
                # cache write, no side effects.
                if _is_cancelled(cancel):
                    cancelled = True
                    break
                elapsed = time.time() - t0
                # Launch the next provider when its stagger slot arrives, or
                # immediately when everything launched so far finished empty.
                while started < len(eligible) and (
                    elapsed >= started * _HEDGE_STAGGER_S or not pending
                ):
                    nm, rn = eligible[started]
                    pending[pool.submit(_run_provider, nm, rn)] = nm
                    started += 1
                if not pending:
                    break  # everything launched and harvested, no winner
                done, _ = _futures.wait(
                    list(pending), timeout=0.2,
                    return_when=_futures.FIRST_COMPLETED,
                )
                for fut in done:
                    nm = pending.pop(fut)
                    try:
                        result = fut.result()
                    except Exception as exc:  # defensive: providers never raise
                        logger.warning("provider_worker_error provider=%s err=%s", nm, type(exc).__name__)
                        continue
                    if result.cancelled:
                        continue  # a de-owned in-flight result — discard it
                    if result.rate_limited:
                        aggregate_rate_limited = True
                    if result.quota_exhausted:
                        aggregate_quota = True
                    if result.items and winner is None:
                        winner = result
                if winner is not None:
                    break
        finally:
            pool.shutdown(wait=False)

        # Final ownership re-check before delivering a winner: if ownership was
        # lost after the winner was picked, discard it (no cache, not delivered).
        if cancelled or _is_cancelled(cancel):
            logger.info("provider_cascade_cancelled role=%r stage=harvest", role)
            return _cancelled_result()

        if winner is not None:
            _cache_put(key, winner.items)
            logger.info(
                "provider_hit provider=%s role=%r results=%d",
                winner.provider, role, len(winner.items),
            )
            return winner

    # 6. Degraded — every configured provider was skipped, degraded, or empty.
    error = "all_providers_unavailable" if configured_any else "no_providers_configured"
    logger.warning(
        "provider_cascade_exhausted role=%r configured_any=%s rate_limited=%s quota=%s",
        role, configured_any, aggregate_rate_limited, aggregate_quota,
    )
    return FetchResult(
        items=[],
        provider="none",
        rate_limited=aggregate_rate_limited,
        quota_exhausted=aggregate_quota,
        error=error,
    )
