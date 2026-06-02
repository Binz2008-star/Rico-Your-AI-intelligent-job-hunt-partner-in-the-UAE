from pathlib import Path
from urllib.parse import quote_plus

from jobspy import scrape_jobs
import logging
import os
import time
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

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


def fetch_jsearch_jobs(
    save_to_db: bool = True,
    target_roles: List[str] | None = None,
    preferred_cities: List[str] | None = None,
) -> List[Dict[str, Any]]:
    """Fetch jobs from JSearch (RapidAPI) for UAE roles.

    When *target_roles* / *preferred_cities* are supplied (typically from a user's
    DB profile) the function builds profile-driven, city-qualified queries instead
    of using the hardcoded ``_JSEARCH_QUERIES`` list. This produces results that
    are personalised to the authenticated user rather than a fixed role set.

    Falls back to ``_JSEARCH_QUERIES`` when no profile data is provided so the
    legacy single-user pipeline continues to work unchanged.
    """
    api_key = os.getenv("RAPIDAPI_KEY", "").strip()
    if not api_key:
        logger.error("jsearch: RAPIDAPI_KEY not set — skipping")
        return []

    from src.scoring import score_job
    from src.db import save_job as db_save_job
    from src import jsearch_client

    # Build query list: profile-driven when we have roles, else hardcoded fallback.
    if target_roles:
        queries = jsearch_client.build_queries_for_profile(
            target_roles=target_roles,
            preferred_cities=preferred_cities or [],
        )
        logger.info(
            "jsearch_jobs: profile-driven queries count=%d roles=%r cities=%r",
            len(queries), target_roles[:4], (preferred_cities or [])[:3],
        )
    else:
        queries = _JSEARCH_QUERIES

    seen: set = set()
    results: List[Dict[str, Any]] = []

    for query in queries:
        # Shared client adds caching, 429/5xx retry+backoff and alt_link capture.
        fetch = jsearch_client.search(query)
        if fetch.rate_limited:
            logger.warning("jsearch_jobs: source rate-limited query=%r — backing off", query)
            time.sleep(2)
        for job in fetch.items:
            dedup_key = job.get("job_id") or job.get("link") or ""
            if not dedup_key or dedup_key in seen:
                continue
            seen.add(dedup_key)
            score = score_job(job)
            job["score"] = score
            if score > 0 and save_to_db:
                db_save_job(job, score)
            results.append(job)

        # Be polite between distinct queries (cache hits return instantly anyway).
        if not fetch.cache_hit:
            time.sleep(1)

    passed = sum(1 for j in results if j["score"] > 0)
    logger.info(
        "jsearch_jobs_fetched total=%d passed=%d rejected=%d",
        len(results), passed, len(results) - passed,
    )
    return results
