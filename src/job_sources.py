from pathlib import Path
from urllib.parse import quote_plus

from jobspy import scrape_jobs
import hashlib
import json
import logging
import os
import time
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# ── JSearch Redis cache ────────────────────────────────────────────────────────
_JSEARCH_CACHE_TTL = 1800  # 30 minutes


def _get_redis_client():
    """Return a Redis client if RICO_REDIS_URL / REDIS_URL is configured, else None."""
    try:
        import redis  # type: ignore
        url = os.getenv("RICO_REDIS_URL") or os.getenv("REDIS_URL")
        if not url:
            return None
        r = redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
        r.ping()
        return r
    except Exception:
        return None


def _jsearch_request(url: str, headers: dict, max_retries: int = 3) -> dict:
    """GET a JSearch URL, retrying on HTTP 429 with exponential backoff."""
    import urllib.request
    import urllib.error

    for attempt in range(max_retries):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                wait = 2 ** (attempt + 1)  # 2 → 4 → 8 s
                logger.warning(
                    "jsearch_rate_limited attempt=%d/%d wait=%ds",
                    attempt + 1, max_retries, wait,
                )
                if attempt < max_retries - 1:
                    time.sleep(wait)
                    continue
            raise
    raise RuntimeError("jsearch_request: unreachable")

_QUERIES = [
    "ESG Manager",
    "HSE Manager",
    "Environmental Manager",
    "Sustainability Manager",
    "QHSE Manager",
]

_BROWSER_ROLES = [
    "HSE Manager",
    "QHSE Manager",
    "EHS Manager",
    "Environmental Manager",
    "Compliance Manager",
    "Safety Manager",
]

_PROFILE_DIR = Path(__file__).resolve().parent.parent / "data" / "ng_profile"

_INDEED_BASE = "https://ae.indeed.com"
_BAYT_BASE   = "https://www.bayt.com"


def _slug(role: str) -> str:
    return role.lower().replace(" ", "-")


def _text(el, selector: str) -> str:
    try:
        node = el.query_selector(selector)
        return node.inner_text().strip() if node else ""
    except Exception:
        return ""


def _href(el, selector: str, base: str) -> str:
    try:
        node = el.query_selector(selector)
        if not node:
            return ""
        href = node.get_attribute("href") or ""
        return href if href.startswith("http") else base + href
    except Exception:
        return ""


def _scrape_indeed(page, role: str, seen: set) -> list:
    url = f"{_INDEED_BASE}/jobs?q={quote_plus(role)}&l=UAE"
    jobs = []
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=25_000)
        page.wait_for_timeout(2_500)
        cards = page.query_selector_all(".job_seen_beacon")
        logger.info(f"indeed role={role!r} cards={len(cards)}")
        for card in cards:
            title   = _text(card, ".jobTitle span") or _text(card, "h2 span")
            company = _text(card, ".companyName") or _text(card, "[data-testid='company-name']")
            link    = _href(card, "a.jcs-JobTitle", _INDEED_BASE)
            if not link or link in seen:
                continue
            seen.add(link)
            jobs.append({
                "title":       title,
                "company":     company,
                "location":    "UAE",
                "link":        link,
                "description": "",
                "source":      "indeed_browser",
            })
    except Exception:
        logger.warning(f"indeed_scrape_failed role={role!r}", exc_info=True)
    return jobs


def _scrape_bayt(page, role: str, seen: set) -> list:
    url = f"{_BAYT_BASE}/en/uae/jobs/{_slug(role)}-jobs/"
    jobs = []
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=25_000)
        page.wait_for_timeout(2_500)
        cards = page.query_selector_all("li[data-job-id]")
        logger.info(f"bayt role={role!r} cards={len(cards)}")
        for card in cards:
            title   = _text(card, "a[data-js-aid='jobID']")
            company = _text(card, ".job-company-location-wrapper a.t-bold")
            link    = _href(card, "a[data-js-aid='jobID']", _BAYT_BASE)
            desc    = _text(card, ".jb-descr")
            if not link or link in seen:
                continue
            seen.add(link)
            jobs.append({
                "title":       title,
                "company":     company,
                "location":    "UAE",
                "link":        link,
                "description": desc,
                "source":      "bayt",
            })
    except Exception:
        logger.warning(f"bayt_scrape_failed role={role!r}", exc_info=True)
    return jobs


def fetch_browser_jobs(save_to_db: bool = True) -> list:
    """
    Scrape Indeed UAE and Bayt UAE via Playwright persistent profile.
    Scores each job and optionally saves to DB. Returns scored job list.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("playwright not installed — run: pip install playwright && playwright install chromium")
        return []

    from src.scoring import score_job
    from src.db import save_job as db_save_job

    seen: set = set()
    raw: list = []

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            str(_PROFILE_DIR),
            headless=False,
            slow_mo=150,
            args=["--disable-blink-features=AutomationControlled"],
            ignore_https_errors=True,
        )
        page = ctx.new_page()
        try:
            for role in _BROWSER_ROLES:
                raw.extend(_scrape_indeed(page, role, seen))
                page.wait_for_timeout(1_000)

            for role in _BROWSER_ROLES:
                raw.extend(_scrape_bayt(page, role, seen))
                page.wait_for_timeout(1_000)
        finally:
            ctx.close()

    # Score and optionally persist
    results = []
    for job in raw:
        s = score_job(job)
        job["score"] = s
        if s > 0 and save_to_db:
            db_save_job(job, s)
        results.append(job)

    passed  = sum(1 for j in results if j["score"] > 0)
    rejected = len(results) - passed
    logger.info(f"browser_jobs_fetched total={len(results)} passed={passed} rejected={rejected}")
    return results


def get_jobs():
    seen = set()
    all_jobs = []
    for query in _QUERIES:
        try:
            df = scrape_jobs(
                site_name=["indeed"],
                search_term=query,
                location="United Arab Emirates",
                results_wanted=20,
                hours_old=48,
                country_indeed="united arab emirates",
            )
            for _, row in df.iterrows():
                link = str(row.get("job_url") or "")
                if link and link not in seen:
                    seen.add(link)
                    all_jobs.append({
                        "title": str(row.get("title", "") or ""),
                        "company": str(row.get("company", "") or ""),
                        "location": str(row.get("location", "") or ""),
                        "link": link,
                        "description": str(row.get("description", "") or ""),
                        "source": "indeed",
                    })
            time.sleep(3)
        except Exception:
            logger.warning(f"scrape_failed query={query}", exc_info=True)
    logger.info(f"jobs_fetched total={len(all_jobs)}")
    return all_jobs


_JSEARCH_BASE = "https://jsearch.p.rapidapi.com"
_JSEARCH_HOST = "jsearch.p.rapidapi.com"

_JSEARCH_QUERIES = [
    "HSE Manager UAE",
    "QHSE Manager UAE",
    "ESG Manager UAE",
    "Environmental Manager UAE",
    "Sustainability Manager UAE",
]


def fetch_jsearch_jobs(save_to_db: bool = True) -> List[Dict[str, Any]]:
    """
    Fetch jobs from JSearch (RapidAPI) for UAE-focused HSE/ESG roles.
    Results are cached in Redis for 30 min per query to reduce API usage.
    Retries automatically on HTTP 429 with exponential backoff.
    """
    api_key = os.getenv("RAPIDAPI_KEY", "").strip()
    if not api_key:
        logger.error("jsearch: RAPIDAPI_KEY not set — skipping")
        return []

    from src.scoring import score_job
    from src.db import save_job as db_save_job

    redis_client = _get_redis_client()
    seen: set = set()
    results: List[Dict[str, Any]] = []

    headers = {
        "x-rapidapi-host": _JSEARCH_HOST,
        "x-rapidapi-key": api_key,
        "Content-Type": "application/json",
    }

    for query in _JSEARCH_QUERIES:
        jobs_list = None

        # ── 1. Try Redis cache ────────────────────────────────────────────────
        cache_key = "jsearch:v1:" + hashlib.md5(query.encode()).hexdigest()
        if redis_client:
            try:
                cached = redis_client.get(cache_key)
                if cached:
                    jobs_list = json.loads(cached)
                    logger.info("jsearch_cache_hit query=%r count=%d", query, len(jobs_list))
            except Exception as cache_exc:
                logger.debug("jsearch_cache_read_error: %s", cache_exc)

        # ── 2. Fetch from API if not cached ───────────────────────────────────
        if jobs_list is None:
            url = (
                f"{_JSEARCH_BASE}/search-v2"
                f"?query={quote_plus(query)}&num_pages=1&country=ae&date_posted=all"
            )
            try:
                data = _jsearch_request(url, headers)
            except Exception as exc:
                logger.warning("jsearch_fetch_failed query=%r: %s", query, exc)
                time.sleep(2)
                continue

            jobs_list = (
                data.get("data", {}).get("jobs", [])
                if isinstance(data.get("data"), dict)
                else data.get("data", [])
            )

            # Cache the raw list for next 30 min
            if redis_client and jobs_list:
                try:
                    redis_client.setex(cache_key, _JSEARCH_CACHE_TTL, json.dumps(jobs_list))
                    logger.debug("jsearch_cache_stored query=%r ttl=%ds", query, _JSEARCH_CACHE_TTL)
                except Exception as cache_exc:
                    logger.debug("jsearch_cache_write_error: %s", cache_exc)

            time.sleep(1)  # polite delay only when we actually hit the API

        # ── 3. Process the job list ───────────────────────────────────────────
        for item in jobs_list:
            job_id = item.get("job_id", "")
            apply_link = item.get("job_apply_link") or ""
            google_link = item.get("job_google_link") or ""
            link = apply_link or google_link
            # alt_link is the other URL so users have a fallback if one is unavailable
            alt_link = google_link if link == apply_link else apply_link

            dedup_key = job_id or link
            if not dedup_key or dedup_key in seen:
                continue
            seen.add(dedup_key)

            location = ", ".join(filter(None, [
                item.get("job_city"),
                item.get("job_state"),
                item.get("job_country"),
            ])) or "UAE"

            job: Dict[str, Any] = {
                "title":           item.get("job_title", ""),
                "company":         item.get("employer_name", ""),
                "location":        location,
                "link":            link,
                "alt_link":        alt_link,
                "description":     item.get("job_description", ""),
                "source":          "jsearch",
                "salary_string":   item.get("job_salary_string") or "",
                "employment_type": item.get("job_employment_type") or "",
            }
            score = score_job(job)
            job["score"] = score
            if score > 0 and save_to_db:
                db_save_job(job, score)
            results.append(job)

    passed = sum(1 for j in results if j["score"] > 0)
    logger.info(
        "jsearch_jobs_fetched total=%d passed=%d rejected=%d cache_enabled=%s",
        len(results), passed, len(results) - passed, redis_client is not None,
    )
    return results
