from pathlib import Path
from urllib.parse import quote_plus, urlparse

from jobspy import scrape_jobs
import logging
import os
import time
from typing import List, Dict, Any, Optional

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


def get_jobs(
    target_roles: List[str] | None = None,
    preferred_cities: List[str] | None = None,
) -> List[Dict[str, Any]]:
    """Scrape jobs from Indeed + Bayt UAE via jobspy.

    When *target_roles* are supplied the function builds queries from the
    user's profile instead of the hardcoded ``_QUERIES`` list, so each
    authenticated user gets results relevant to their own career goals.

    Bayt.com is included alongside Indeed as it is the largest UAE-focused
    job board and not covered by JSearch.
    """
    queries = target_roles if target_roles else _QUERIES
    seen: set = set()
    all_jobs: list = []

    # Sources: Indeed (international) + Bayt (UAE-native)
    _SOURCES: List[Dict[str, Any]] = [
        {
            "site_name": ["indeed"],
            "extra": {"country_indeed": "united arab emirates"},
            "source_label": "indeed",
        },
        {
            "site_name": ["bayt"],
            "extra": {},
            "source_label": "bayt",
        },
    ]

    location = "United Arab Emirates"
    if preferred_cities:
        from src.jsearch_client import _UAE_CITY_NAMES
        uae_cities = [
            c for c in preferred_cities
            if any(uae.lower() in c.lower() for uae in _UAE_CITY_NAMES)
        ]
        if uae_cities:
            location = uae_cities[0]  # jobspy takes a single location string

    for query in queries:
        for src in _SOURCES:
            try:
                df = scrape_jobs(
                    site_name=src["site_name"],
                    search_term=query,
                    location=location,
                    results_wanted=20,
                    hours_old=48,
                    **src["extra"],
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
                            "source": src["source_label"],
                        })
                time.sleep(2)
            except Exception:
                logger.warning(
                    "scrape_failed query=%r source=%s", query, src["source_label"], exc_info=True
                )

    logger.info("jobs_fetched total=%d sources=indeed,bayt", len(all_jobs))
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

_SOURCE_QUALITY_SCORE_ADJUSTMENTS = {
    "needs_source_verification": 0,
    "google_intermediary": -10,
    "login_required": -12,
    "rate_limited": -15,
    "aggregator_untrusted": -25,
}

_DIRECT_APPLY_DOMAINS: frozenset[str] = frozenset(
    {
        "greenhouse.io",
        "lever.co",
        "workday.com",
        "myworkdayjobs.com",
        "smartrecruiters.com",
        "taleo.net",
        "icims.com",
        "bamboohr.com",
        "jobvite.com",
        "recruitee.com",
        "ashbyhq.com",
        "rippling.com",
    }
)

_TRUSTED_JOB_BOARD_DOMAINS: frozenset[str] = frozenset(
    {
        "bayt.com",
        "dubizzle.com",
        "indeed.com",
        "linkedin.com",
        "monstergulf.com",
        "naukrigulf.com",
    }
)

_CAREER_HOST_HINTS: tuple[str, ...] = (
    "careers.",
    ".careers.",
    "jobs.",
    ".jobs.",
    "recruit.",
    ".recruit.",
    "talent.",
    ".talent.",
)


def _score_bounds(score: int) -> int:
    return max(0, min(100, int(score or 0)))


def _job_source_quality(job: Dict[str, Any]) -> str:
    """Classify the best available URL so profile ranking favours usable jobs."""
    try:
        from src.services.source_quality import classify_url, is_google_intermediary

        url = str(
            job.get("job_apply_link")
            or job.get("apply_link")
            or job.get("link")
            or ""
        ).strip()
        if is_google_intermediary(url):
            return "google_intermediary"
        return classify_url(url)
    except Exception:
        return "needs_source_verification"


def _job_url(job: Dict[str, Any]) -> str:
    return str(
        job.get("job_apply_link")
        or job.get("apply_link")
        or job.get("link")
        or ""
    ).strip()


def _hostname(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower().lstrip("www.")
    except Exception:
        return ""


def _hostname_matches(hostname: str, domains: frozenset[str]) -> bool:
    return any(hostname == domain or hostname.endswith("." + domain) for domain in domains)


def _source_quality_adjustment(job: Dict[str, Any], source_quality: str) -> int:
    if source_quality != "live_verified":
        return _SOURCE_QUALITY_SCORE_ADJUSTMENTS.get(source_quality, 0)

    hostname = _hostname(_job_url(job))
    if _hostname_matches(hostname, _DIRECT_APPLY_DOMAINS) or any(hint in hostname for hint in _CAREER_HOST_HINTS):
        return 12
    if _hostname_matches(hostname, _TRUSTED_JOB_BOARD_DOMAINS):
        return 3
    return 6


def _profile_fit_reason(
    job: Dict[str, Any],
    target_roles: List[str],
    skills: List[str],
    source_quality: str,
) -> str:
    title = str(job.get("title") or "").lower()
    description = str(job.get("description") or "").lower()
    text = f"{title} {description}"

    reasons: list[str] = []
    for role in target_roles:
        role_text = str(role or "").strip()
        if role_text and role_text.lower() in title:
            reasons.append(f"Target role: {role_text}")
            break

    matched_skills = []
    for skill in skills:
        skill_text = str(skill or "").strip()
        if skill_text and skill_text.lower() in text:
            matched_skills.append(skill_text)
        if len(matched_skills) >= 3:
            break
    if matched_skills:
        reasons.append("Skills: " + ", ".join(matched_skills))

    if source_quality == "live_verified":
        reasons.append("Direct/trusted source")
    elif source_quality in {"aggregator_untrusted", "google_intermediary", "login_required"}:
        reasons.append(f"Source needs caution: {source_quality}")

    return " | ".join(reasons) or "Profile-fit ranking"


def _score_profile_driven_jobs(
    jobs: List[Dict[str, Any]],
    *,
    target_roles: Optional[List[str]],
    skills: Optional[List[str]],
    deal_breakers: Optional[List[str]],
    preferred_cities: Optional[List[str]],
) -> List[Dict[str, Any]]:
    """Score JSearch jobs against the requested profile instead of the legacy HSE profile."""
    from src.llm_scorer import rank_by_profile_fit

    role_list = [str(role) for role in (target_roles or []) if str(role or "").strip()]
    skill_list = [str(skill) for skill in (skills or []) if str(skill or "").strip()]
    breaker_list = [str(item) for item in (deal_breakers or []) if str(item or "").strip()]

    ranked = rank_by_profile_fit(
        jobs,
        target_roles=role_list,
        skills=skill_list,
        deal_breakers=breaker_list,
        preferred_cities=preferred_cities or [],
    )

    for job in ranked:
        base_score = _score_bounds(job.get("profile_fit_score", 0))
        source_quality = _job_source_quality(job)
        adjusted_score = 0 if base_score <= 0 else _score_bounds(
            base_score + _source_quality_adjustment(job, source_quality)
        )
        job["score"] = adjusted_score
        job["score_source"] = "profile_fit"
        job["source_quality"] = source_quality
        job["profile_explanation"] = _profile_fit_reason(
            job,
            role_list,
            skill_list,
            source_quality,
        )

    sorted_jobs = sorted(
        ranked,
        key=lambda job: (
            -_score_bounds(job.get("score", 0)),
            -_score_bounds(job.get("profile_fit_score", 0)),
            str(job.get("title") or "").lower(),
            str(job.get("company") or "").lower(),
        ),
    )
    return _dedupe_profile_ranked_jobs(sorted_jobs)


def _dedupe_profile_ranked_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: list[Dict[str, Any]] = []
    seen: set[str] = set()
    for job in jobs:
        key = _dedupe_key(job)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(job)
    return deduped


def _dedupe_key(job: Dict[str, Any]) -> str:
    title = " ".join(str(job.get("title") or "").lower().split())
    company = " ".join(str(job.get("company") or "").lower().split())
    if title and company:
        return f"title_company:{title}|{company}"
    return f"job:{job.get('job_id') or _job_url(job)}"


def fetch_jsearch_jobs(
    save_to_db: bool = True,
    target_roles: List[str] | None = None,
    preferred_cities: List[str] | None = None,
    skills: Optional[List[str]] = None,
    deal_breakers: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Fetch jobs from JSearch (RapidAPI) for UAE roles.

    When *target_roles* / *preferred_cities* are supplied (typically from a user's
    DB profile) the function builds profile-driven, city-qualified queries instead
    of using the hardcoded ``_JSEARCH_QUERIES`` list. Those results are scored
    with zero-latency profile-fit ranking, not the legacy single-profile HSE
    scorer, so non-HSE roles are not discarded before they can be shown.

    Falls back to ``_JSEARCH_QUERIES`` when no profile data is provided so the
    legacy single-user pipeline continues to work unchanged.
    """
    api_key = os.getenv("RAPIDAPI_KEY", "").strip()
    if not api_key:
        logger.error("jsearch: RAPIDAPI_KEY not set — skipping")
        return []

    from src.db import save_job as db_save_job
    from src import jsearch_client

    # Build query list: profile-driven when we have roles, else hardcoded fallback.
    profile_driven = bool(target_roles)
    if profile_driven:
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
            results.append(job)

        # Be polite between distinct queries (cache hits return instantly anyway).
        if not fetch.cache_hit:
            time.sleep(1)

    if profile_driven:
        try:
            results = _score_profile_driven_jobs(
                results,
                target_roles=target_roles,
                skills=skills,
                deal_breakers=deal_breakers,
                preferred_cities=preferred_cities,
            )
        except Exception:
            logger.warning("jsearch_jobs: profile-fit scoring failed; falling back to legacy scorer", exc_info=True)
            profile_driven = False

    if not profile_driven:
        from src.scoring import score_job

        for job in results:
            score = score_job(job)
            job["score"] = score

    if save_to_db:
        for job in results:
            score = _score_bounds(job.get("score", 0))
            if score > 0:
                db_save_job(job, score)

    passed = sum(1 for j in results if j["score"] > 0)
    logger.info(
        "jsearch_jobs_fetched total=%d passed=%d rejected=%d",
        len(results), passed, len(results) - passed,
    )
    return results
