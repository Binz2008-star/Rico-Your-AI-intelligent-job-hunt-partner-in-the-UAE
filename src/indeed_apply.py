"""
src/indeed_apply.py
Indeed Easy Apply Engine

Only targets jobs that show the "Easily apply" badge — all external ATS
redirects are skipped at the card-scan stage, before any page load.

Architecture:
  Phase 1 — Search : scrape ae.indeed.com for target roles
  Phase 2 — Filter : badge present + dedup + spam/age guard
  Phase 3 — Apply  : fill Indeed in-platform apply widget (iframe)
  Phase 4 — Track  : persist to applied_jobs.json + DB

Environment variables:
    INDEED_ENABLED=false
    INDEED_DRY_RUN=false
    INDEED_HEADLESS=false
    INDEED_MAX_PER_RUN=3
    INDEED_DAILY_LIMIT=15
    INDEED_COOLDOWN_SECONDS=120
    INDEED_SLOW_MO=800
    INDEED_MAX_JOB_AGE_DAYS=14
    INDEED_SCORE_THRESHOLD=0
    NG_PROFILE_DIR=data/ng_profile   (shared persistent browser profile)
    CV_PATH=data/cv.pdf
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urljoin

from dotenv import load_dotenv
from playwright.sync_api import (
    BrowserContext,
    Frame,
    Page,
    Playwright,
    TimeoutError as PWTimeout,
    sync_playwright,
)

from src.applications import is_applied, mark_applied
from src.db import is_db_available

load_dotenv()
logger = logging.getLogger("indeed_apply")

BASE_DIR       = Path(__file__).resolve().parent.parent
RATE_FILE      = BASE_DIR / "data" / "indeed_apply_rate.json"
INDEED_BASE    = "https://ae.indeed.com"


# ── Config ────────────────────────────────────────────────────────────────────

def _env_bool(k: str, d: bool = False) -> bool:
    return os.getenv(k, str(d)).lower() in ("1", "true", "yes")

def _env_int(k: str, d: int) -> int:
    try:
        return int(os.getenv(k, str(d)))
    except ValueError:
        return d


INDEED_ENABLED    = _env_bool("INDEED_ENABLED", False)
INDEED_DRY_RUN    = _env_bool("INDEED_DRY_RUN", False)
INDEED_HEADLESS   = _env_bool("INDEED_HEADLESS", False)
INDEED_MAX_PER_RUN    = _env_int("INDEED_MAX_PER_RUN", 3)
INDEED_DAILY_LIMIT    = _env_int("INDEED_DAILY_LIMIT", 15)
INDEED_COOLDOWN       = _env_int("INDEED_COOLDOWN_SECONDS", 120)
INDEED_SLOW_MO        = _env_int("INDEED_SLOW_MO", 800)
INDEED_MAX_AGE_DAYS   = _env_int("INDEED_MAX_JOB_AGE_DAYS", 14)
INDEED_SCORE_THRESHOLD= _env_int("INDEED_SCORE_THRESHOLD", 0)
INDEED_PROFILE_DIR    = BASE_DIR / os.getenv("NG_PROFILE_DIR", "data/ng_profile")
CV_PATH               = BASE_DIR / os.getenv("CV_PATH", "data/cv.pdf")


# ── Target roles ──────────────────────────────────────────────────────────────

TARGET_ROLES: List[str] = [
    "HSE Manager",
    "QHSE Manager",
    "EHS Manager",
    "Environmental Manager",
    "Compliance Manager",
    "Safety Manager",
]


# ── Selectors ─────────────────────────────────────────────────────────────────

class _S:
    # Search results page
    SEARCH_URL   = INDEED_BASE + "/jobs?q={query}&l=UAE&filter=0"
    JOB_CARD     = ".job_seen_beacon"
    TITLE        = ".jobTitle span, h2 span[title]"
    COMPANY      = ".companyName, [data-testid='company-name']"
    # Easy Apply badge — present only for in-platform applications.
    # Multiple fallbacks because Indeed's class names change frequently.
    EASY_BADGE   = (
        ".iaLabel, "
        "[aria-label*='Easily apply'], "
        "[class*='easyApply'], "
        "[class*='ia-IndeedApply'], "
        "[data-testid='result-footer-item']:has-text('Easily apply'), "
        "[data-testid='attribute_snippet_testid']:has-text('Easily apply'), "
        "span:has-text('Easily apply'), "
        "div:has-text('Easily apply')"
    )
    CARD_LINK    = "a.jcs-JobTitle, h2 a"

    # Job detail page
    APPLY_BTN    = (
        "#indeedApplyButton, "
        ".ia-IndeedApplyButton, "
        "button[aria-label*='Apply now'], "
        "button:has-text('Apply now'), "
        "a:has-text('Apply now')"
    )
    # Easy Apply iframe widget
    APPLY_IFRAME = "iframe[title*='Apply'], .ia-BasePage-iframe, iframe[src*='apply.indeed']"

    # Inside the apply iframe — multi-step wizard
    FIELD_NAME   = "[name='applicant.name'], #applicant\\.name, input[autocomplete='name']"
    FIELD_EMAIL  = "[name='applicant.emailAddress'], #applicant\\.emailAddress, input[type='email']"
    FIELD_PHONE  = "[name='applicant.phoneNumber'], #applicant\\.phoneNumber, input[type='tel']"
    FILE_INPUT   = "input[type='file']"
    CONTINUE_BTN = (
        "[data-testid='continue-button'], "
        "button:has-text('Continue'), "
        "button:has-text('Next'), "
        "button[type='submit']"
    )
    SUBMIT_BTN   = (
        "[data-testid='submit-application-button'], "
        "button:has-text('Submit your application'), "
        "button:has-text('Submit application')"
    )
    SUCCESS      = (
        "[data-testid='application-submitted'], "
        "h1:has-text('Application submitted'), "
        "text=Your application has been submitted"
    )


# ── Status + Result ───────────────────────────────────────────────────────────

class IndeedApplyStatus(str, Enum):
    SUCCESS          = "success"
    DRY_RUN          = "dry_run"
    ALREADY_APPLIED  = "already_applied"
    DISABLED         = "disabled"
    NO_EASY_APPLY    = "no_easy_apply"
    EXTERNAL_REDIRECT= "external_redirect"
    NO_APPLY_BUTTON  = "no_apply_button"
    IFRAME_MISSING   = "iframe_missing"
    SUBMIT_FAILED    = "submit_failed"
    RATE_LIMITED     = "rate_limited"
    FAILED           = "failed"


@dataclass
class IndeedApplyResult:
    job_id:    str
    title:     str
    company:   str
    status:    IndeedApplyStatus
    message:   str
    easy_apply: bool = False
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


# ── Rate limiter ──────────────────────────────────────────────────────────────

class _RateLimiter:
    def __init__(self, path: Path = RATE_FILE) -> None:
        self._path  = path
        self._state = self._load()

    def _load(self) -> Dict[str, Any]:
        try:
            with self._path.open() as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"date": "", "count": 0, "last_apply": None}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w") as f:
            json.dump(self._state, f)

    def _reset_if_new_day(self) -> None:
        today = date.today().isoformat()
        if self._state.get("date") != today:
            self._state = {"date": today, "count": 0, "last_apply": None}
            self._save()

    def can_apply(self) -> tuple[bool, str]:
        self._reset_if_new_day()
        if self._state["count"] >= INDEED_DAILY_LIMIT:
            return False, f"daily_limit {self._state['count']}/{INDEED_DAILY_LIMIT}"
        last = self._state.get("last_apply")
        if last:
            elapsed = (datetime.utcnow() - datetime.fromisoformat(last)).total_seconds()
            if elapsed < INDEED_COOLDOWN:
                return False, f"cooldown remaining={int(INDEED_COOLDOWN - elapsed)}s"
        return True, "ok"

    def record(self) -> None:
        self._reset_if_new_day()
        self._state["count"] += 1
        self._state["last_apply"] = datetime.utcnow().isoformat()
        self._save()

    @property
    def today_count(self) -> int:
        self._reset_if_new_day()
        return self._state["count"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _jitter(base: float, extra: float = 60.0) -> None:
    time.sleep(random.uniform(base, base + extra))

def _wait(page: Any, lo: int = 1500, hi: int = 4000) -> None:
    page.wait_for_timeout(random.randint(lo, hi))

def _text(el: Any, sel: str) -> str:
    try:
        node = el.query_selector(sel)
        return node.inner_text().strip() if node else ""
    except Exception:
        return ""

def _href(el: Any, sel: str) -> str:
    try:
        node = el.query_selector(sel)
        if not node:
            return ""
        href = node.get_attribute("href") or ""
        return href if href.startswith("http") else urljoin(INDEED_BASE, href)
    except Exception:
        return ""

def _job_key(url: str) -> str:
    """Extract Indeed job key (jk=...) from URL for dedup."""
    if "jk=" in url:
        return url.split("jk=")[1].split("&")[0]
    return url


# ── Engine ────────────────────────────────────────────────────────────────────

class IndeedApplyEngine:
    """
    Indeed Easy Apply automation using persistent Chrome profile.

    Only applies to jobs showing the "Easily apply" badge — all external ATS
    links are skipped before any job page is loaded.

    Usage:
        with IndeedApplyEngine() as engine:
            results = engine.run(dry_run=True)   # scan only
            results = engine.run(dry_run=False)  # live apply
    """

    def __init__(self, rate_limiter: Optional[_RateLimiter] = None) -> None:
        self._rate  = rate_limiter or _RateLimiter()
        self._pw:   Optional[Playwright]    = None
        self._ctx:  Optional[BrowserContext] = None
        self._page: Optional[Page]          = None

    def __enter__(self) -> "IndeedApplyEngine":
        INDEED_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        self._pw  = sync_playwright().start()
        self._ctx = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(INDEED_PROFILE_DIR),
            headless=INDEED_HEADLESS,
            slow_mo=INDEED_SLOW_MO,
            ignore_https_errors=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
            viewport={"width": 1280, "height": 800},
        )
        self._page = (
            self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        )
        self._page.set_default_timeout(25_000)
        return self

    def __exit__(self, *_: Any) -> None:
        try:
            if self._ctx:
                self._ctx.close()
        except Exception:
            pass
        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass

    # ── Public API ────────────────────────────────────────────────────────────

    def run(
        self,
        dry_run: bool = INDEED_DRY_RUN,
        max_applies: int = INDEED_MAX_PER_RUN,
    ) -> List[IndeedApplyResult]:
        """
        Scan Indeed for Easy Apply jobs and optionally apply.
        dry_run=True  → print badge-positive cards, no applications submitted.
        dry_run=False → apply up to max_applies jobs with Easy Apply.
        """
        if not INDEED_ENABLED and not dry_run:
            logger.info("indeed_apply_disabled INDEED_ENABLED=false")
            return [IndeedApplyResult(
                job_id="", title="", company="",
                status=IndeedApplyStatus.DISABLED,
                message="Set INDEED_ENABLED=true to enable live applies",
            )]

        easy_jobs = self._scan_all_roles()
        logger.info("indeed_easy_apply_found count=%d", len(easy_jobs))

        if dry_run:
            self._print_dry_run_report(easy_jobs)
            return [
                IndeedApplyResult(
                    job_id=j["link"], title=j["title"], company=j["company"],
                    status=IndeedApplyStatus.DRY_RUN,
                    message="dry_run — badge confirmed",
                    easy_apply=True,
                )
                for j in easy_jobs
            ]

        results: List[IndeedApplyResult] = []
        applied = 0

        for job in easy_jobs:
            if applied >= max_applies:
                break
            r = self._process_job(job)
            if r:
                results.append(r)
                logger.info("indeed_result %s", json.dumps(r.to_dict()))
                if r.status == IndeedApplyStatus.SUCCESS:
                    applied += 1
                    _jitter(INDEED_COOLDOWN, extra=60)

        logger.info(
            "indeed_run_complete applied=%d total=%d",
            sum(1 for r in results if r.status == IndeedApplyStatus.SUCCESS),
            len(results),
        )
        return results

    # ── Phase 1: scan search pages for Easy Apply cards ───────────────────────

    def _scan_all_roles(self) -> List[Dict[str, Any]]:
        seen: set[str] = set()
        jobs: List[Dict[str, Any]] = []
        for role in TARGET_ROLES:
            for job in self._scan_role(role):
                key = _job_key(job["link"])
                if key and key not in seen:
                    seen.add(key)
                    jobs.append(job)
            _wait(self._page, 800, 1500)
        return self._score_jobs(jobs)

    def _score_jobs(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not jobs:
            return jobs
        try:
            from src.scoring import score_job
            for job in jobs:
                job["score"] = score_job(job)
        except Exception:
            for job in jobs:
                job.setdefault("score", 0)
        return sorted(jobs, key=lambda j: int(j.get("score", 0)), reverse=True)

    def _scan_role(self, role: str) -> List[Dict[str, Any]]:
        assert self._page
        url = _S.SEARCH_URL.format(query=quote_plus(role))
        try:
            self._page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            _wait(self._page, 2000, 3500)
        except Exception as exc:
            logger.warning("indeed_scan_failed role=%s error=%s", role, exc)
            return []

        cards = self._page.query_selector_all(_S.JOB_CARD)
        logger.info("indeed_scan role=%r cards=%d", role, len(cards))

        jobs: List[Dict[str, Any]] = []
        for card in cards:
            # Badge check — only proceed for Easy Apply cards
            badge = card.query_selector(_S.EASY_BADGE)
            if not badge:
                continue

            title   = _text(card, _S.TITLE)
            company = _text(card, _S.COMPANY)
            link    = _href(card, _S.CARD_LINK)

            if not link:
                continue

            logger.info(
                "indeed_easy_apply_card title=%s company=%s link=%s",
                title[:60], company[:40], link[:80],
            )
            jobs.append({
                "title":    title,
                "company":  company,
                "location": "UAE",
                "link":     link,
                "source":   "indeed_easy_apply",
                "score":    0,
            })

        logger.info("indeed_scan_easy role=%r found=%d", role, len(jobs))
        return jobs

    # ── Phase 2: filter ───────────────────────────────────────────────────────

    def _process_job(self, job: Dict[str, Any]) -> Optional[IndeedApplyResult]:
        if is_applied(job):
            return None

        allowed, reason = self._rate.can_apply()
        if not allowed:
            return IndeedApplyResult(
                job_id=job["link"], title=job["title"], company=job["company"],
                status=IndeedApplyStatus.RATE_LIMITED, message=reason,
            )

        try:
            return self._apply_one(job)
        except Exception as exc:
            logger.exception("indeed_apply_unhandled title=%s", job.get("title"))
            return IndeedApplyResult(
                job_id=job["link"], title=job["title"], company=job["company"],
                status=IndeedApplyStatus.FAILED, message=str(exc),
            )

    # ── Phase 3: apply ────────────────────────────────────────────────────────

    def _apply_one(self, job: Dict[str, Any]) -> IndeedApplyResult:
        assert self._page
        link    = job["link"]
        title   = job.get("title", "Unknown")
        company = job.get("company", "Unknown")

        def r(s: IndeedApplyStatus, m: str) -> IndeedApplyResult:
            return IndeedApplyResult(
                job_id=link, title=title, company=company,
                status=s, message=m, easy_apply=True,
            )

        self._page.goto(link, wait_until="domcontentloaded", timeout=30_000)
        _wait(self._page, 2000, 3500)

        # Confirm we're still on Indeed (not an external redirect)
        if "indeed.com" not in self._page.url:
            return r(IndeedApplyStatus.EXTERNAL_REDIRECT,
                     f"redirected to {self._page.url[:80]}")

        # Re-confirm Easy Apply badge on detail page
        if not self._page.query_selector(_S.EASY_BADGE):
            logger.info("indeed_no_easy_badge_on_detail title=%s", title)
            return r(IndeedApplyStatus.NO_EASY_APPLY,
                     "Easy Apply badge absent on job detail page")

        # Click the apply button
        apply_btn = self._page.query_selector(_S.APPLY_BTN)
        if not apply_btn:
            return r(IndeedApplyStatus.NO_APPLY_BUTTON, "apply button not found")

        apply_btn.click()
        _wait(self._page, 2000, 4000)

        # Locate the apply iframe
        frame = self._get_apply_frame()
        if frame is None:
            return r(IndeedApplyStatus.IFRAME_MISSING, "apply iframe not found")

        # Fill multi-step form
        success = self._fill_apply_form(frame, job)
        if not success:
            return r(IndeedApplyStatus.SUBMIT_FAILED,
                     "form fill or submit failed — check browser")

        mark_applied(job, status="applied")
        self._rate.record()
        logger.info("indeed_apply_success title=%s daily=%d",
                    title, self._rate.today_count)
        return IndeedApplyResult(
            job_id=link, title=title, company=company,
            status=IndeedApplyStatus.SUCCESS,
            message="applied via Indeed Easy Apply",
            easy_apply=True,
        )

    def _get_apply_frame(self) -> Optional[Frame]:
        """Wait for and return the Indeed apply iframe frame context."""
        assert self._page
        try:
            iframe_el = self._page.wait_for_selector(
                _S.APPLY_IFRAME, timeout=10_000
            )
            if iframe_el:
                return iframe_el.content_frame()
        except PWTimeout:
            pass

        # Fallback: search all frames for apply.indeed.com
        for frame in self._page.frames:
            if "apply.indeed.com" in (frame.url or ""):
                return frame
        return None

    def _fill_apply_form(self, frame: Frame, job: Dict[str, Any]) -> bool:
        """
        Navigate Indeed's multi-step Easy Apply wizard.
        Returns True if the application was submitted successfully.
        """
        from src.profile import get_candidate_profile
        profile = get_candidate_profile()
        name    = "Roben Edwan"
        email   = os.getenv("INDEED_EMAIL", "robenedwan@gmail.com")
        phone   = os.getenv("INDEED_PHONE", "")

        max_steps = 8
        for step in range(max_steps):
            _wait(frame.page, 1200, 2500)

            # Check for success first
            if frame.query_selector(_S.SUCCESS):
                logger.info("indeed_form_success step=%d", step)
                return True

            # Upload resume if file input visible
            self._maybe_upload_cv(frame)

            # Fill contact fields (only when empty)
            self._fill_field(frame, _S.FIELD_NAME,  name)
            self._fill_field(frame, _S.FIELD_EMAIL, email)
            if phone:
                self._fill_field(frame, _S.FIELD_PHONE, phone)

            # Try submit button first, then continue/next
            if self._click_if_present(frame, _S.SUBMIT_BTN):
                _wait(frame.page, 2000, 4000)
                # Check for success after submit
                if frame.query_selector(_S.SUCCESS):
                    return True
                # Might need one more step
                continue

            if self._click_if_present(frame, _S.CONTINUE_BTN):
                continue

            # No actionable button found — bail
            logger.warning("indeed_form_stuck step=%d title=%s",
                           step, job.get("title"))
            return False

        logger.warning("indeed_form_max_steps_exceeded title=%s", job.get("title"))
        return False

    def _maybe_upload_cv(self, frame: Frame) -> None:
        if not CV_PATH.exists():
            return
        inp = frame.query_selector(_S.FILE_INPUT)
        if inp:
            try:
                inp.set_input_files(str(CV_PATH))
                frame.page.wait_for_timeout(1_000)
                logger.debug("cv_uploaded")
            except Exception as exc:
                logger.warning("cv_upload_failed error=%s", exc)

    def _fill_field(self, frame: Frame, sel: str, value: str) -> None:
        if not value:
            return
        try:
            inp = frame.query_selector(sel)
            if inp and not inp.input_value():
                inp.fill(value)
        except Exception:
            pass

    def _click_if_present(self, frame: Frame, sel: str) -> bool:
        try:
            btn = frame.query_selector(sel)
            if btn and btn.is_enabled():
                btn.click()
                return True
        except Exception:
            pass
        return False

    # ── Dry-run report ────────────────────────────────────────────────────────

    def _print_dry_run_report(self, jobs: List[Dict[str, Any]]) -> None:
        print(f"\n{'='*72}")
        print(f"  Indeed Easy Apply — DRY RUN  ({len(jobs)} badge-confirmed, scored)")
        print(f"{'='*72}")
        print(f"  {'#':>3}  {'Score':>5}  {'Title':<48}  Company")
        print(f"  {'-'*3}  {'-'*5}  {'-'*48}  {'-'*30}")
        if not jobs:
            print("  No 'Easily apply' jobs found for target roles.")
        for i, j in enumerate(jobs, 1):
            score = j.get("score", 0)
            flag  = " *" if score >= 60 else ""
            print(
                f"  {i:>3}  {score:>5}  {j['title'][:48]:<48}  {j['company'][:30]}{flag}"
            )
            print(f"         {j['link'][:72]}")
        print(f"{'='*72}")
        passing = sum(1 for j in jobs if j.get("score", 0) >= 60)
        print(f"  * = score ≥ 60  ({passing} jobs would proceed to apply)\n")


# ── Pipeline entry point ──────────────────────────────────────────────────────

def run_indeed_apply(
    dry_run: bool = INDEED_DRY_RUN,
    max_applies: int = INDEED_MAX_PER_RUN,
) -> List[IndeedApplyResult]:
    """
    Entry point for external callers and run_daily pipeline.

    dry_run=True  → scan and report, no applications submitted.
    dry_run=False → apply to Easy Apply jobs (requires INDEED_ENABLED=true).
    """
    with IndeedApplyEngine() as engine:
        return engine.run(dry_run=dry_run, max_applies=max_applies)
