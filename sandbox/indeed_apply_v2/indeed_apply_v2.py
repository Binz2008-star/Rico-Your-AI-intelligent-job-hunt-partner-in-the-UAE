"""
sandbox/indeed_apply_v2/indeed_apply_v2.py
Indeed Easy Apply Engine V2 - Enhanced Version

Improvements over V1:
- Better selector resilience with multiple fallbacks
- Enhanced error handling with specific error types
- LLM-powered screening question answering
- Retry logic with exponential backoff
- Profile data validation before apply
- Better auth detection and handling
- Improved rate limiting with burst protection
- Detailed logging and debugging mode
- Cloudflare challenge handling
- Form field detection improvements

Environment variables:
    INDEED_V2_ENABLED=false
    INDEED_V2_DRY_RUN=false
    INDEED_V2_HEADLESS=false
    INDEED_V2_MAX_PER_RUN=3
    INDEED_V2_DAILY_LIMIT=15
    INDEED_V2_COOLDOWN_SECONDS=120
    INDEED_V2_SLOW_MO=800
    INDEED_V2_MAX_JOB_AGE_DAYS=14
    INDEED_V2_SCORE_THRESHOLD=0
    INDEED_V2_MAX_RETRIES=2
    INDEED_V2_DEBUG=false
    NG_PROFILE_DIR=data/ng_profile_v2
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
from typing import Any, Dict, List, Optional, Tuple
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

from sandbox.indeed_apply_v2.monitoring import get_logger

load_dotenv()
logger = logging.getLogger("indeed_apply_v2")

BASE_DIR       = Path(__file__).resolve().parent.parent.parent
RATE_FILE      = BASE_DIR / "sandbox" / "indeed_apply_v2" / "rate.json"
INDEED_BASE    = "https://ae.indeed.com"


# ── Config ────────────────────────────────────────────────────────────────────

def _env_bool(k: str, d: bool = False) -> bool:
    return os.getenv(k, str(d)).lower() in ("1", "true", "yes")

def _env_int(k: str, d: int) -> int:
    try:
        return int(os.getenv(k, str(d)))
    except ValueError:
        return d


INDEED_V2_ENABLED    = _env_bool("INDEED_V2_ENABLED", False)
INDEED_V2_DRY_RUN    = _env_bool("INDEED_V2_DRY_RUN", False)
INDEED_V2_HEADLESS   = _env_bool("INDEED_V2_HEADLESS", False)
INDEED_V2_DEBUG      = _env_bool("INDEED_V2_DEBUG", False)
INDEED_V2_MAX_PER_RUN    = _env_int("INDEED_V2_MAX_PER_RUN", 3)
INDEED_V2_DAILY_LIMIT    = _env_int("INDEED_V2_DAILY_LIMIT", 15)
INDEED_V2_COOLDOWN       = _env_int("INDEED_V2_COOLDOWN_SECONDS", 120)
INDEED_V2_SLOW_MO        = _env_int("INDEED_V2_SLOW_MO", 800)
INDEED_V2_MAX_AGE_DAYS   = _env_int("INDEED_V2_MAX_JOB_AGE_DAYS", 14)
INDEED_V2_SCORE_THRESHOLD      = _env_int("INDEED_V2_SCORE_THRESHOLD", 0)
INDEED_V2_MAX_RETRIES          = _env_int("INDEED_V2_MAX_RETRIES", 2)
INDEED_V2_STREET_ADDRESS       = os.getenv("INDEED_V2_STREET_ADDRESS", "")
INDEED_V2_RELEVANT_JOB_TITLE   = os.getenv("INDEED_V2_RELEVANT_JOB_TITLE", "")
INDEED_V2_RELEVANT_COMPANY     = os.getenv("INDEED_V2_RELEVANT_COMPANY", "")
INDEED_V2_PROFILE_DIR          = BASE_DIR / os.getenv("NG_PROFILE_DIR", "data/ng_profile_v2")
CV_PATH                 = BASE_DIR / os.getenv("CV_PATH", "data/cv.pdf")
INDEED_V2_SKIP_COMPANIES    = os.getenv("INDEED_V2_SKIP_COMPANIES", "").lower()

# Profile data validation
INDEED_V2_NAME  = os.getenv("INDEED_V2_NAME", "")
INDEED_V2_EMAIL = os.getenv("INDEED_V2_EMAIL", "")
INDEED_V2_PHONE = os.getenv("INDEED_V2_PHONE", "")


# ── Target roles ──────────────────────────────────────────────────────────────

TARGET_ROLES: List[str] = [
    "HSE Manager",
    "QHSE Manager",
    "EHS Manager",
    "Environmental Manager",
    "Compliance Manager",
    "Safety Manager",
]


# ── Title pre-filter ─────────────────────────────────────────────────────────────

KEEP_TITLE_KEYWORDS = [
    "hse", "qhse", "ehs", "hsse", "safety",
    "environmental", "environment", "esg", "sustainability"
]

REJECT_TITLE_KEYWORDS = [
    "project manager", "construction manager", "civil engineer",
    "site engineer", "quantity surveyor", "document controller",
    "coating technician", "automotive workshop", "cad supervisor",
    "f&b", "plumbing engineer", "electrical engineer",
    "architect", "draftsman", "sales", "healthcare",
    "nurse", "doctor", "intern", "uae national",
    "project engineer", "executive - ehs", "assistant manager",
    "hse officer"
]

def _title_allowed(title: str) -> bool:
    """Check if title passes keyword filters."""
    t = title.lower()
    if any(bad in t for bad in REJECT_TITLE_KEYWORDS):
        return False
    return any(good in t for good in KEEP_TITLE_KEYWORDS)


# ── Enhanced Selectors ─────────────────────────────────────────────────────────

class _S:
    # Search results page
    SEARCH_URL   = INDEED_BASE + "/jobs?q={query}&l=UAE&filter=0"
    JOB_CARD     = ".job_seen_beacon, .jobCard, [data-jk]"
    TITLE        = ".jobTitle span, h2 span[title], [data-testid='job-title']"
    COMPANY      = ".companyName, [data-testid='company-name'], .css-1x7z1ps"

    # Easy Apply badge - enhanced with more fallbacks
    EASY_BADGE   = (
        ".iaLabel, "
        "[aria-label*='Easily apply'], "
        "[class*='easyApply'], "
        "[class*='ia-IndeedApply'], "
        "[data-testid='result-footer-item']:has-text('Easily apply'), "
        "[data-testid='attribute_snippet_testid']:has-text('Easily apply'), "
        "span:has-text('Easily apply'), "
        "div:has-text('Easily apply'), "
        ".css-1kptu5g, "  # Additional Indeed class
        "[data-testid='indeed-apply-badge']"
    )
    CARD_LINK    = "a.jcs-JobTitle, h2 a, [data-jk]"

    # Job detail page - enhanced selectors
    APPLY_BTN    = (
        "button[aria-label='Apply with Indeed'], "
        "button:has-text('Apply with Indeed'), "
        "[class*='indeed-apply-st'] button, "
        "#indeedApplyButton, "
        ".ia-IndeedApplyButton, "
        "button[aria-label*='Apply now'], "
        "button:has-text('Apply now'), "
        "button[data-testid='indeed-apply-button'], "
        ".css-1e61u6i"  # Additional Indeed class
    )

    # Easy Apply iframe widget - enhanced
    APPLY_IFRAME = (
        "iframe[title*='Apply'], "
        ".ia-BasePage-iframe, "
        "iframe[src*='apply.indeed'], "
        "iframe[src*='indeed.com/apply'], "
        "[data-testid='apply-iframe']"
    )

    # Inside the apply iframe - enhanced field selectors
    FIELD_NAME    = (
        "[name='applicant.name'], "
        "#applicant\\.name, "
        "input[autocomplete='name'], "
        "input[aria-label*='name' i], "
        "input[placeholder*='name' i]"
    )
    FIELD_EMAIL   = (
        "[name='applicant.emailAddress'], "
        "#applicant\\.emailAddress, "
        "input[type='email'], "
        "input[aria-label*='email' i], "
        "input[placeholder*='email' i]"
    )
    FIELD_PHONE   = (
        "[name='applicant.phoneNumber'], "
        "#applicant\\.phoneNumber, "
        "input[type='tel'], "
        "input[aria-label*='phone' i], "
        "input[placeholder*='phone' i]"
    )
    FIELD_ADDRESS = (
        "input[aria-label*='Street address' i], "
        "input[aria-label*='street' i], "
        "input[id*='streetAddress' i], "
        "input[id*='street_address' i], "
        "input[name*='streetAddress' i], "
        "input[name*='street_address' i], "
        "input[placeholder*='Street address' i], "
        "input[placeholder*='street' i], "
        "textarea[aria-label*='address' i]"
    )
    FIELD_JOB_TITLE = (
        "input[aria-label*='Job title' i], "
        "input[id*='jobTitle' i], "
        "input[name*='jobTitle' i], "
        "input[placeholder*='Job title' i]"
    )
    FIELD_COMPANY = (
        "input[aria-label*='Company' i], "
        "input[id*='company' i], "
        "input[name*='company' i], "
        "input[placeholder*='Company' i]"
    )
    FILE_INPUT    = "input[type='file']"

    # Button selectors - enhanced
    CONTINUE_BTN  = (
        "[data-testid='continue-button'], "
        "button:has-text('Continue'), "
        "button:has-text('Next'), "
        "button[type='button']:has-text('Continue'), "
        ".css-1q2b7ua"  # Additional Indeed class
    )
    SUBMIT_BTN   = (
        "[data-testid='submit-application-button'], "
        "button:has-text('Submit your application'), "
        "button:has-text('Submit application'), "
        "button[type='submit'], "
        ".css-1wc71we"  # Additional Indeed class
    )

    # Success indicators - enhanced
    SUCCESS      = (
        "[data-testid='application-submitted'], "
        "h1:has-text('has been submitted'), "
        "h1:has-text('Application submitted'), "
        "[class*='PostApply'], "
        "button:has-text('Return to job search'), "
        "a:has-text('Return to job search'), "
        "h2:has-text('Application submitted'), "
        ".css-1t5p0pv"  # Additional Indeed class
    )

    # Error indicators
    ERROR_INDICATOR = (
        "[data-testid='error'], "
        ".error, "
        "[class*='error'], "
        "div:has-text('error'), "
        "div:has-text('Error')"
    )


# ── Status + Result ───────────────────────────────────────────────────────────

class IndeedApplyStatus(str, Enum):
    SUCCESS           = "success"
    DRY_RUN           = "dry_run"
    ALREADY_APPLIED   = "already_applied"
    DISABLED          = "disabled"
    NO_EASY_APPLY     = "no_easy_apply"
    EXTERNAL_REDIRECT = "external_redirect"
    NO_APPLY_BUTTON   = "no_apply_button"
    IFRAME_MISSING    = "iframe_missing"
    SUBMIT_FAILED     = "submit_failed"
    NEEDS_PROFILE_DATA= "needs_profile_data"
    RATE_LIMITED      = "rate_limited"
    FAILED            = "failed"
    AUTH_REQUIRED     = "auth_required"
    SKIPPED_COMPANY   = "skipped_company"
    CLOUDFLARE_BLOCK  = "cloudflare_block"
    CAPTCHA_DETECTED  = "captcha_detected"
    RETRY_EXHAUSTED   = "retry_exhausted"
    FORM_ERROR        = "form_error"
    NETWORK_ERROR     = "network_error"


@dataclass
class IndeedApplyResult:
    job_id:    str
    title:     str
    company:   str
    status:    IndeedApplyStatus
    message:   str
    easy_apply: bool = False
    timestamp: str = ""
    retry_count: int = 0
    error_details: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()
        if self.error_details is None:
            self.error_details = {}

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


# ── Enhanced Rate Limiter with Adaptive Control ─────────────────────────────────

class _RateLimiter:
    def __init__(self, path: Path = RATE_FILE) -> None:
        self._path  = path
        self._state = self._load()
        self._burst_count = 0  # Track burst applies
        self._burst_window_start = datetime.utcnow()
        self._success_history: List[bool] = []  # Track recent success/failure
        self._adaptive_cooldown = INDEED_V2_COOLDOWN  # Adaptive cooldown

    def _load(self) -> Dict[str, Any]:
        try:
            with self._path.open() as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                "date": "",
                "count": 0,
                "last_apply": None,
                "success_count": 0,
                "failure_count": 0,
            }

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w") as f:
            json.dump(self._state, f)

    def _reset_if_new_day(self) -> None:
        today = date.today().isoformat()
        if self._state.get("date") != today:
            self._state = {
                "date": today,
                "count": 0,
                "last_apply": None,
                "success_count": 0,
                "failure_count": 0,
            }
            self._save()

    def _check_burst_protection(self) -> bool:
        """Prevent burst applies (more than 3 in 30 seconds)."""
        now = datetime.utcnow()
        if (now - self._burst_window_start).total_seconds() > 30:
            self._burst_count = 0
            self._burst_window_start = now
        return self._burst_count < 3

    def _adaptive_adjust_cooldown(self, success: bool) -> None:
        """Adjust cooldown based on recent success rate."""
        self._success_history.append(success)
        if len(self._success_history) > 10:
            self._success_history.pop(0)

        if len(self._success_history) >= 5:
            success_rate = sum(self._success_history) / len(self._success_history)

            # If success rate is low, increase cooldown
            if success_rate < 0.5:
                self._adaptive_cooldown = min(INDEED_V2_COOLDOWN * 2, 300)
            # If success rate is high, decrease cooldown
            elif success_rate > 0.8:
                self._adaptive_cooldown = max(INDEED_V2_COOLDOWN // 2, 60)
            else:
                self._adaptive_cooldown = INDEED_V2_COOLDOWN

    def can_apply(self) -> tuple[bool, str]:
        self._reset_if_new_day()

        if self._state["count"] >= INDEED_V2_DAILY_LIMIT:
            return False, f"daily_limit {self._state['count']}/{INDEED_V2_DAILY_LIMIT}"

        if not self._check_burst_protection():
            return False, "burst_protection - too many applies in short time"

        last = self._state.get("last_apply")
        if last:
            elapsed = (datetime.utcnow() - datetime.fromisoformat(last)).total_seconds()
            if elapsed < self._adaptive_cooldown:
                return False, f"cooldown remaining={int(self._adaptive_cooldown - elapsed)}s"
        return True, "ok"

    def record(self, success: bool = True) -> None:
        self._reset_if_new_day()
        self._state["count"] += 1
        self._state["last_apply"] = datetime.utcnow().isoformat()
        self._burst_count += 1

        # Track success/failure
        if success:
            self._state["success_count"] = self._state.get("success_count", 0) + 1
        else:
            self._state["failure_count"] = self._state.get("failure_count", 0) + 1

        self._adaptive_adjust_cooldown(success)
        self._save()

    @property
    def today_count(self) -> int:
        self._reset_if_new_day()
        return self._state["count"]

    @property
    def success_rate(self) -> float:
        """Calculate today's success rate."""
        self._reset_if_new_day()
        total = self._state.get("success_count", 0) + self._state.get("failure_count", 0)
        if total == 0:
            return 1.0
        return self._state.get("success_count", 0) / total


# ── Helpers ───────────────────────────────────────────────────────────────────

def _jitter(base: float, extra: float = 60.0) -> None:
    time.sleep(random.uniform(base, base + extra))

def _wait(page: Any, lo: int = 1500, hi: int = 4000) -> None:
    page.wait_for_timeout(random.randint(lo, hi))

def _loc_text(scope: Any, sel: str) -> str:
    try:
        loc = scope.locator(sel)
        if loc.count() > 0:
            return loc.first.inner_text().strip()
    except Exception:
        pass
    return ""

def _loc_href(scope: Any, sel: str) -> str:
    try:
        loc = scope.locator(sel)
        if loc.count() > 0:
            href = loc.first.get_attribute("href") or ""
            return href if href.startswith("http") else urljoin(INDEED_BASE, href)
    except Exception:
        pass
    return ""

def _loc_exists(scope: Any, sel: str) -> bool:
    try:
        return scope.locator(sel).count() > 0
    except Exception:
        return False

def _detect_auth_required(scope: Any) -> bool:
    """Enhanced auth detection with more patterns."""
    try:
        url = scope.url.lower() if hasattr(scope, 'url') else ""
        auth_url_patterns = [
            "secure.indeed.com/auth",
            "/auth?",
            "/account/login",
            "accounts.google.com",
            "signin",
            "login",
        ]
        if any(pattern in url for pattern in auth_url_patterns):
            return True

        if _loc_exists(scope, "body"):
            page_text = scope.inner_text("body").lower()
            auth_text_patterns = [
                "continue with google",
                "create an account or sign in",
                "email address",
                "(not you?)",
                "sign in",
                "google",
                "password",
                "log in",
            ]
            if any(pattern in page_text for pattern in auth_text_patterns):
                return True
    except Exception:
        pass
    return False

def _detect_cloudflare(scope: Any) -> bool:
    """Detect Cloudflare challenge page."""
    try:
        if _loc_exists(scope, "body"):
            page_text = scope.inner_text("body").lower()
            # Require multiple patterns to reduce false positives
            cf_patterns = [
                "just a moment",
                "checking your browser",
                "ray id",
            ]
            matches = sum(1 for pattern in cf_patterns if pattern in page_text)
            # Require at least 2 patterns to match
            return matches >= 2
    except Exception:
        pass
    return False

def _detect_captcha(scope: Any) -> bool:
    """Detect CAPTCHA challenge."""
    try:
        captcha_selectors = [
            "#captcha",
            ".recaptcha",
            "[class*='captcha']",
            "iframe[src*='recaptcha']",
            "iframe[src*='captcha']",
        ]
        return any(_loc_exists(scope, sel) for sel in captcha_selectors)
    except Exception:
        pass
    return False

def _job_key(url: str) -> str:
    """Extract Indeed job key (jk=...) from URL for dedup."""
    if "jk=" in url:
        return url.split("jk=")[1].split("&")[0]
    return url

def _validate_profile_data() -> Tuple[bool, List[str]]:
    """Validate required profile data."""
    missing = []
    if not INDEED_V2_NAME:
        missing.append("INDEED_V2_NAME")
    if not INDEED_V2_EMAIL:
        missing.append("INDEED_V2_EMAIL")
    if not INDEED_V2_STREET_ADDRESS:
        missing.append("INDEED_V2_STREET_ADDRESS")
    return len(missing) == 0, missing


# ── LLM-powered Screening Question Answering ───────────────────────────────────

def _answer_screening_questions(
    questions: List[str],
    job: Dict[str, Any]
) -> Dict[str, str]:
    """
    Use LLM to answer screening questions in the apply form.
    This is a placeholder - actual implementation would call your LLM service.
    """
    if not questions:
        return {}

    try:
        # Placeholder for LLM integration
        # In production, this would call your existing LLM scorer
        from src.llm_scorer import get_llm_response
        from src.profile import get_candidate_profile

        profile = get_candidate_profile()
        context = (
            f"Name: {profile.get('name','N/A')}\n"
            f"Experience: {profile.get('experience_summary','N/A')}\n"
            f"Skills: {', '.join(profile.get('skills',[]))}\n"
            f"Roles: {', '.join(profile.get('target_roles',[]))}\n"
            f"Location: UAE (available immediately)"
        )

        qs_text = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
        prompt = (
            f"Indeed Easy Apply for: {job.get('title')} at {job.get('company')}.\n\n"
            f"CANDIDATE:\n{context}\n\n"
            f"QUESTIONS:\n{qs_text}\n\n"
            'Reply ONLY with JSON: {"1":"answer","2":"answer"}'
        )

        raw = get_llm_response(prompt)
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            parsed = json.loads(raw[start:end])
            return {
                questions[int(k) - 1]: v
                for k, v in parsed.items()
                if k.isdigit() and int(k) <= len(questions)
            }
    except Exception as exc:
        logger.warning("llm_screening_failed error=%s", exc)
    return {}


# ── Engine ────────────────────────────────────────────────────────────────────

class IndeedApplyEngineV2:
    """
    Indeed Easy Apply automation V2 with enhanced features.

    Improvements:
    - Better selector resilience
    - Enhanced error handling
    - Retry logic with exponential backoff
    - Profile data validation
    - Cloudflare detection
    - CAPTCHA detection
    - Burst protection
    - Detailed debugging
    """

    def __init__(self, rate_limiter: Optional[_RateLimiter] = None) -> None:
        self._rate          = rate_limiter or _RateLimiter()
        self._pw:   Optional[Playwright]    = None
        self._ctx:  Optional[BrowserContext] = None
        self._page: Optional[Page]          = None
        self._missing_field: str            = ""
        self._stats = {
            "total_scanned": 0,
            "easy_apply_found": 0,
            "title_filtered": 0,
            "applied": 0,
            "failed": 0,
            "skipped": 0,
        }
        self._monitor = get_logger(debug=INDEED_V2_DEBUG)
        self._run_start_time: Optional[datetime] = None

    def __enter__(self) -> "IndeedApplyEngineV2":
        INDEED_V2_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        self._pw  = sync_playwright().start()
        self._ctx = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(INDEED_V2_PROFILE_DIR),
            headless=INDEED_V2_HEADLESS,
            slow_mo=INDEED_V2_SLOW_MO,
            ignore_https_errors=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
            viewport={"width": 1280, "height": 800},
        )
        self._page = (
            self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        )
        self._page.set_default_timeout(30_000)
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
        dry_run: bool = INDEED_V2_DRY_RUN,
        max_applies: int = INDEED_V2_MAX_PER_RUN,
    ) -> List[IndeedApplyResult]:
        """
        Scan Indeed for Easy Apply jobs and optionally apply.
        """
        self._run_start_time = datetime.utcnow()
        run_id = f"run_{self._run_start_time.strftime('%Y%m%d_%H%M%S')}"

        if INDEED_V2_DEBUG:
            logger.setLevel(logging.DEBUG)
            logger.info("DEBUG mode enabled")

        if not INDEED_V2_ENABLED and not dry_run:
            logger.info("indeed_v2_apply_disabled INDEED_V2_ENABLED=false")
            return [IndeedApplyResult(
                job_id="", title="", company="",
                status=IndeedApplyStatus.DISABLED,
                message="Set INDEED_V2_ENABLED=true to enable live applies",
            )]

        # Validate profile data
        if not dry_run:
            valid, missing = _validate_profile_data()
            if not valid:
                logger.warning("profile_data_missing missing=%s", missing)
                return [IndeedApplyResult(
                    job_id="", title="", company="",
                    status=IndeedApplyStatus.NEEDS_PROFILE_DATA,
                    message=f"Missing profile data: {', '.join(missing)}",
                )]

        easy_jobs, raw_badge_count, title_filtered_count = self._scan_all_roles()
        logger.info("indeed_v2_easy_apply_found count=%d", len(easy_jobs))

        if dry_run:
            self._print_dry_run_report(easy_jobs, raw_badge_count, title_filtered_count)
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
        attempted = 0

        for job in easy_jobs:
            if attempted >= max_applies:
                break

            score = int(job.get("score", 0))
            if score < INDEED_V2_SCORE_THRESHOLD:
                logger.info(
                    "indeed_v2_skip_score score=%d threshold=%d title=%s",
                    score, INDEED_V2_SCORE_THRESHOLD, job.get("title"),
                )
                continue

            r = self._process_job_with_retry(job)
            if r:
                if r.status in {
                    IndeedApplyStatus.SUCCESS,
                    IndeedApplyStatus.AUTH_REQUIRED,
                    IndeedApplyStatus.NEEDS_PROFILE_DATA,
                    IndeedApplyStatus.SUBMIT_FAILED,
                    IndeedApplyStatus.FAILED,
                    IndeedApplyStatus.NO_APPLY_BUTTON,
                    IndeedApplyStatus.IFRAME_MISSING,
                    IndeedApplyStatus.EXTERNAL_REDIRECT,
                    IndeedApplyStatus.CLOUDFLARE_BLOCK,
                    IndeedApplyStatus.CAPTCHA_DETECTED,
                }:
                    attempted += 1
                results.append(r)
                logger.info("indeed_v2_result %s", json.dumps(r.to_dict()))

                if r.status in {IndeedApplyStatus.AUTH_REQUIRED,
                               IndeedApplyStatus.CLOUDFLARE_BLOCK,
                               IndeedApplyStatus.CAPTCHA_DETECTED}:
                    logger.warning("indeed_v2_stopping status=%s msg=%s", r.status.value, r.message)
                    break

                if r.status == IndeedApplyStatus.SUCCESS:
                    self._stats["applied"] += 1
                    _jitter(INDEED_V2_COOLDOWN, extra=60)
                else:
                    self._stats["failed"] += 1

        logger.info(
            "indeed_v2_run_complete applied=%d attempted=%d total=%d stats=%s",
            self._stats["applied"], attempted, len(results), self._stats,
        )
        return results

    def _process_job_with_retry(self, job: Dict[str, Any]) -> Optional[IndeedApplyResult]:
        """Process job with retry logic and advanced error recovery."""
        for attempt in range(INDEED_V2_MAX_RETRIES + 1):
            try:
                result = self._process_job(job)
                if result and result.status == IndeedApplyStatus.SUCCESS:
                    return result

                # Retry on certain failures with recovery strategies
                if result and result.status in {
                    IndeedApplyStatus.NETWORK_ERROR,
                    IndeedApplyStatus.SUBMIT_FAILED,
                    IndeedApplyStatus.FORM_ERROR,
                    IndeedApplyStatus.IFRAME_MISSING,
                }:
                    if attempt < INDEED_V2_MAX_RETRIES:
                        recovery_action = self._get_recovery_action(result.status, attempt)
                        logger.info("retry attempt=%d wait=%ds recovery=%s",
                                   attempt + 1, recovery_action["wait"], recovery_action["action"])

                        # Execute recovery action
                        if recovery_action["action"] == "refresh_page":
                            self._page.reload()
                            _wait(self._page, 2000, 3000)
                        elif recovery_action["action"] == "clear_cookies":
                            self._ctx.clear_cookies()
                        elif recovery_action["action"] == "new_context":
                            # Close and recreate context
                            self._ctx.close()
                            self._ctx = self._pw.chromium.launch_persistent_context(
                                user_data_dir=str(INDEED_V2_PROFILE_DIR),
                                headless=INDEED_V2_HEADLESS,
                                slow_mo=INDEED_V2_SLOW_MO,
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
                            self._page.set_default_timeout(30_000)

                        time.sleep(recovery_action["wait"])
                        continue

                return result
            except Exception as exc:
                if attempt < INDEED_V2_MAX_RETRIES:
                    wait_time = (2 ** attempt) * 5
                    logger.warning("retry_exception attempt=%d wait=%ds error=%s",
                                 attempt + 1, wait_time, exc)
                    time.sleep(wait_time)
                    continue
                return IndeedApplyResult(
                    job_id=job["link"], title=job["title"], company=job["company"],
                    status=IndeedApplyStatus.RETRY_EXHAUSTED,
                    message=f"Failed after {INDEED_V2_MAX_RETRIES} retries: {str(exc)}",
                    retry_count=INDEED_V2_MAX_RETRIES,
                    error_details={"exception": str(exc), "type": type(exc).__name__},
                )

        return None

    def _get_recovery_action(self, status: IndeedApplyStatus, attempt: int) -> Dict[str, Any]:
        """Get recovery action based on error type and attempt number."""
        # First attempt: just wait
        if attempt == 0:
            return {"action": "wait", "wait": 5}

        # Network errors: refresh page
        if status == IndeedApplyStatus.NETWORK_ERROR:
            if attempt == 1:
                return {"action": "refresh_page", "wait": 3}
            return {"action": "clear_cookies", "wait": 5}

        # Form/iframe errors: refresh and wait longer
        if status in {IndeedApplyStatus.SUBMIT_FAILED, IndeedApplyStatus.FORM_ERROR, IndeedApplyStatus.IFRAME_MISSING}:
            if attempt == 1:
                return {"action": "refresh_page", "wait": 5}
            return {"action": "new_context", "wait": 8}

        # Default: exponential backoff
        return {"action": "wait", "wait": (2 ** attempt) * 5}

    # ── Phase 1: scan search pages for Easy Apply cards ───────────────────────

    def _scan_all_roles(self) -> tuple[List[Dict[str, Any]], int, int]:
        seen: set[str] = set()
        jobs: List[Dict[str, Any]] = []
        total_raw_badge = 0
        total_title_filtered = 0

        for role in TARGET_ROLES:
            role_jobs, raw_badge, title_filtered = self._scan_role(role)
            total_raw_badge += raw_badge
            total_title_filtered += title_filtered
            for job in role_jobs:
                key = _job_key(job["link"])
                if key and key not in seen:
                    seen.add(key)
                    jobs.append(job)
            _wait(self._page, 800, 1500)

        self._stats["total_scanned"] = len(jobs)
        self._stats["easy_apply_found"] = total_raw_badge
        self._stats["title_filtered"] = total_title_filtered

        return self._score_jobs(jobs), total_raw_badge, total_title_filtered

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

    def _scan_role(self, role: str) -> tuple[List[Dict[str, Any]], int, int]:
        assert self._page
        url = _S.SEARCH_URL.format(query=quote_plus(role))

        try:
            self._page.goto(url, wait_until="domcontentloaded", timeout=30_000)

            # Check for Cloudflare
            if _detect_cloudflare(self._page):
                logger.warning("cloudflare_detected role=%s", role)
                return [], 0, 0

            _wait(self._page, 2000, 3500)

            try:
                self._page.wait_for_selector(_S.JOB_CARD, timeout=10_000)
            except PWTimeout:
                logger.warning("indeed_v2_no_cards_timeout role=%s url=%s",
                               role, self._page.url[:120])
        except Exception as exc:
            logger.warning("indeed_v2_scan_failed role=%s error=%s", role, exc)
            return [], 0, 0

        cards = self._page.locator(_S.JOB_CARD)
        count = cards.count()
        logger.info("indeed_v2_scan role=%r cards=%d", role, count)

        jobs: List[Dict[str, Any]] = []
        raw_badge_count = 0
        title_filtered_count = 0

        for i in range(count):
            card = cards.nth(i)
            if not _loc_exists(card, _S.EASY_BADGE):
                continue

            raw_badge_count += 1
            title   = _loc_text(card, _S.TITLE)
            company = _loc_text(card, _S.COMPANY)
            link    = _loc_href(card, _S.CARD_LINK)

            if not link:
                continue

            if not _title_allowed(title):
                logger.info("indeed_v2_skip_title title=%s company=%s", title[:80], company[:50])
                title_filtered_count += 1
                continue

            logger.info(
                "indeed_v2_easy_apply_card title=%s company=%s link=%s",
                title[:60], company[:40], link[:80],
            )
            jobs.append({
                "title":    title,
                "company":  company,
                "location": "UAE",
                "link":     link,
                "source":   "indeed_easy_apply_v2",
                "score":    0,
            })

        logger.info("indeed_v2_scan_easy role=%r raw_badge=%d title_filtered=%d found=%d",
                   role, raw_badge_count, title_filtered_count, len(jobs))
        return jobs, raw_badge_count, title_filtered_count

    # ── Phase 2: filter ───────────────────────────────────────────────────────

    def _process_job(self, job: Dict[str, Any]) -> Optional[IndeedApplyResult]:
        # Check if already applied (import from main applications module)
        try:
            from src.applications import is_applied
            if is_applied(job):
                return None
        except ImportError:
            pass

        allowed, reason = self._rate.can_apply()
        if not allowed:
            return IndeedApplyResult(
                job_id=job["link"], title=job["title"], company=job["company"],
                status=IndeedApplyStatus.RATE_LIMITED, message=reason,
            )

        try:
            return self._apply_one(job)
        except Exception as exc:
            logger.exception("indeed_v2_apply_unhandled title=%s", job.get("title"))
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

        # Check if company is in skip list
        if INDEED_V2_SKIP_COMPANIES:
            company_lower = company.lower()
            skip_terms = [term.strip() for term in INDEED_V2_SKIP_COMPANIES.split(",")]
            if any(term in company_lower for term in skip_terms):
                logger.info("indeed_v2_skip_company company=%s", company)
                return r(IndeedApplyStatus.SKIPPED_COMPANY, f"company skipped: {company}")

        try:
            self._page.goto(link, wait_until="domcontentloaded", timeout=30_000)
        except Exception as exc:
            return r(IndeedApplyStatus.NETWORK_ERROR, f"navigation error: {str(exc)}")

        _wait(self._page, 2000, 3500)

        # Check for Cloudflare
        if _detect_cloudflare(self._page):
            return r(IndeedApplyStatus.CLOUDFLARE_BLOCK, "Cloudflare challenge detected")

        # Check for CAPTCHA
        if _detect_captcha(self._page):
            return r(IndeedApplyStatus.CAPTCHA_DETECTED, "CAPTCHA detected")

        # Confirm we're still on Indeed
        if "indeed.com" not in self._page.url:
            return r(IndeedApplyStatus.EXTERNAL_REDIRECT,
                     f"redirected to {self._page.url[:80]}")

        # Click the apply button
        apply_loc = self._page.locator(_S.APPLY_BTN)
        if apply_loc.count() == 0:
            return r(IndeedApplyStatus.NO_APPLY_BUTTON, "apply button not found")

        apply_loc.first.click()
        _wait(self._page, 2000, 4000)

        # Check for auth interruption
        if _detect_auth_required(self._page):
            return r(IndeedApplyStatus.AUTH_REQUIRED,
                     "auth required / Google SSO detected — skipped")

        # If click navigated away from Indeed it's an external ATS link
        if "indeed.com" not in self._page.url:
            return r(IndeedApplyStatus.EXTERNAL_REDIRECT,
                     f"apply redirected to {self._page.url[:80]}")

        # Locate the apply iframe
        frame = self._get_apply_frame()
        if frame is None:
            return r(IndeedApplyStatus.IFRAME_MISSING, "apply iframe not found")

        # Fill multi-step form
        self._missing_field = ""
        success = self._fill_apply_form(frame, job)
        if not success:
            if self._missing_field == "AUTH_REQUIRED":
                return r(IndeedApplyStatus.AUTH_REQUIRED,
                         "auth required / Google SSO detected — skipped")
            if self._missing_field:
                field, self._missing_field = self._missing_field, ""
                return r(IndeedApplyStatus.NEEDS_PROFILE_DATA,
                         f"missing {field} — set env var to fill required field")
            return r(IndeedApplyStatus.SUBMIT_FAILED,
                     "form fill or submit failed — check browser")

        # Mark as applied
        try:
            from src.applications import mark_applied
            mark_applied(job, status="applied")
        except ImportError:
            pass

        self._rate.record(success=True)
        logger.info("indeed_v2_apply_success title=%s daily=%d success_rate=%.2f",
                    title, self._rate.today_count, self._rate.success_rate)
        return IndeedApplyResult(
            job_id=link, title=title, company=company,
            status=IndeedApplyStatus.SUCCESS,
            message="applied via Indeed Easy Apply V2",
            easy_apply=True,
        )

    def _get_apply_frame(self) -> Optional[Frame]:
        """Wait for and return the Indeed apply iframe frame context."""
        assert self._page
        try:
            iframe_el = self._page.wait_for_selector(
                _S.APPLY_IFRAME, timeout=15_000
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
        """Navigate Indeed's multi-step Easy Apply wizard."""
        max_steps = 15  # Increased from 12
        for step in range(max_steps):
            _wait(frame.page, 1500, 2500)

            # Wait for loading to clear
            try:
                frame.wait_for_function(
                    """() => {
                        const el = document.querySelector('[data-testid="loading-indicator"]');
                        return !el || el.offsetParent === null
                            || getComputedStyle(el).display === 'none'
                            || getComputedStyle(el).visibility === 'hidden';
                    }""",
                    timeout=15_000,
                )
            except PWTimeout:
                logger.debug("indeed_v2_loading_timeout step=%d", step)
            _wait(frame.page, 500, 1000)

            # Check for auth interruption
            if _detect_auth_required(frame) or _detect_auth_required(frame.page):
                logger.warning("indeed_v2_auth_detected step=%d", step)
                self._missing_field = "AUTH_REQUIRED"
                return False

            # Check for success
            if _loc_exists(frame, _S.SUCCESS):
                logger.info("indeed_v2_form_success step=%d", step)
                return True

            # Check for error
            if _loc_exists(frame, _S.ERROR_INDICATOR):
                logger.warning("indeed_v2_form_error step=%d", step)
                return False

            # Upload resume if file input visible
            self._maybe_upload_cv(frame)

            # Fill contact fields
            self._fill_field(frame, _S.FIELD_NAME, INDEED_V2_NAME)
            self._fill_field(frame, _S.FIELD_EMAIL, INDEED_V2_EMAIL)
            if INDEED_V2_PHONE:
                self._fill_field(frame, _S.FIELD_PHONE, INDEED_V2_PHONE)

            # Fill address field
            if _loc_exists(frame, _S.FIELD_ADDRESS):
                if not INDEED_V2_STREET_ADDRESS:
                    logger.warning("indeed_v2_form_needs_address step=%d", step)
                    self._missing_field = "INDEED_V2_STREET_ADDRESS"
                    return False
                self._fill_field(frame, _S.FIELD_ADDRESS, INDEED_V2_STREET_ADDRESS)

            # Fill relevant-experience step
            if _loc_exists(frame, _S.FIELD_JOB_TITLE):
                self._fill_field(frame, _S.FIELD_JOB_TITLE, INDEED_V2_RELEVANT_JOB_TITLE)
            if _loc_exists(frame, _S.FIELD_COMPANY):
                self._fill_field(frame, _S.FIELD_COMPANY, INDEED_V2_RELEVANT_COMPANY)

            # Try to answer screening questions with LLM
            self._maybe_answer_questions(frame, job)

            # Try submit first
            if self._click_button(frame, _S.SUBMIT_BTN):
                _wait(frame.page, 2000, 3000)
                if _loc_exists(frame, _S.SUCCESS):
                    return True

            # Not the final step — click Continue/Next
            if not self._click_button(frame, _S.CONTINUE_BTN):
                logger.warning("indeed_v2_stuck step=%d no_continue_button", step)
                return False

        return False

    def _fill_field(self, frame: Frame, selector: str, value: str) -> None:
        """Fill a field if it's empty and value is provided."""
        if not value:
            return
        try:
            loc = frame.locator(selector)
            if loc.count() > 0:
                el = loc.first
                current = el.input_value() if el.get_attribute("type") != "file" else ""
                if not current or not current.strip():
                    el.fill(value)
                    logger.debug("field_filled selector=%s", selector[:50])
        except Exception as exc:
            logger.debug("field_fill_failed selector=%s error=%s", selector[:50], exc)

    def _click_button(self, frame: Frame, selector: str) -> bool:
        """Try to click a button with multiple selector fallbacks."""
        try:
            loc = frame.locator(selector)
            if loc.count() > 0:
                el = loc.first
                if el.is_enabled():
                    el.click()
                    return True
        except Exception as exc:
            logger.debug("button_click_failed selector=%s error=%s", selector[:50], exc)
        return False

    def _maybe_upload_cv(self, frame: Frame) -> None:
        """Upload CV if file input is visible."""
        if not CV_PATH.exists():
            logger.warning("cv_missing path=%s", CV_PATH)
            return
        try:
            loc = frame.locator(_S.FILE_INPUT)
            if loc.count() > 0:
                loc.first.set_input_files(str(CV_PATH))
                _wait(frame.page, 1000, 1500)
                logger.debug("cv_uploaded")
        except Exception as exc:
            logger.debug("cv_upload_failed error=%s", exc)

    def _maybe_answer_questions(self, frame: Frame, job: Dict[str, Any]) -> None:
        """Detect and answer screening questions using LLM."""
        try:
            # Look for text inputs that might be questions
            inputs = frame.locator("input[type='text'], textarea")
            if inputs.count() == 0:
                return

            questions = []
            for i in range(min(inputs.count(), 5)):  # Limit to 5 questions
                inp = inputs.nth(i)
                try:
                    # Try to get label text
                    label = inp.evaluate(
                        """el => {
                            if (el.id) {
                                const l = document.querySelector('label[for="'+el.id+'"]');
                                if (l) return l.innerText.trim();
                            }
                            const wrap = el.closest('.fb-dash-form-element, .jobs-easy-apply-form-section__grouping');
                            return wrap ? (wrap.querySelector('label,legend')?.innerText?.trim() || '') : '';
                        }"""
                    )
                    if label and len(label) < 200:  # Reasonable question length
                        questions.append(label)
                except Exception:
                    pass

            if questions:
                answers = _answer_screening_questions(questions, job)
                for i, inp in enumerate(inputs):
                    if i < len(questions):
                        ans = answers.get(questions[i], "")
                        if ans:
                            try:
                                if not inp.input_value():
                                    inp.fill(ans)
                                    logger.debug("question_answered q=%s", questions[i][:40])
                            except Exception:
                                pass
        except Exception as exc:
            logger.debug("question_answering_failed error=%s", exc)

    def _print_dry_run_report(
        self,
        jobs: List[Dict[str, Any]],
        raw_badge: int,
        title_filtered: int,
        skipped_applied: int = 0
    ) -> None:
        """Print detailed dry run report."""
        print()
        print("=" * 70)
        print("  INDEED EASY APPLY V2 - DRY RUN REPORT")
        print("=" * 70)
        print(f"  Raw Easy Apply badges found: {raw_badge}")
        print(f"  Title-filtered: {title_filtered}")
        print(f"  Already applied: {skipped_applied}")
        print(f"  Eligible jobs: {len(jobs)}")
        print()

        if jobs:
            print("  TOP ELIGIBLE JOBS:")
            print("-" * 70)
            for i, job in enumerate(jobs[:10], 1):
                print(f"  {i:2}. [{job.get('score', 0):3d}] {job['title'][:50]}")
                print(f"       {job['company'][:50]}")
                print(f"       {job['link'][:70]}")
                print()
        else:
            print("  No eligible jobs found.")

        print("=" * 70)


# ── Entry Point ───────────────────────────────────────────────────────────────

def run_indeed_apply_v2(
    dry_run: bool = INDEED_V2_DRY_RUN,
    max_applies: int = INDEED_V2_MAX_PER_RUN,
) -> List[IndeedApplyResult]:
    """
    Entry point for V2 Indeed apply engine.
    """
    with IndeedApplyEngineV2() as engine:
        return engine.run(dry_run=dry_run, max_applies=max_applies)


if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    dry_run = "--dry-run" in sys.argv
    max_applies = 3
    for i, arg in enumerate(sys.argv):
        if arg == "--max" and i + 1 < len(sys.argv):
            max_applies = int(sys.argv[i + 1])

    results = run_indeed_apply_v2(dry_run=dry_run, max_applies=max_applies)

    print()
    print("=" * 70)
    print("  RESULTS SUMMARY")
    print("=" * 70)
    for r in results:
        print(f"  {r.status.value:<25} | {r.title[:40]}")
    print()
    applied = sum(1 for r in results if r.status == IndeedApplyStatus.SUCCESS)
    print(f"  Applied: {applied}/{len(results)}")
    print("=" * 70)
