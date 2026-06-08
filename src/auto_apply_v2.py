"""
src/auto_apply_v2.py
LinkedIn Easy Apply Automation Engine V2

Enhanced version with:
- Adaptive rate limiting based on success rate
- Advanced error recovery with multiple strategies
- Comprehensive monitoring and metrics
- Enhanced selectors with fallbacks
- Detection systems (CAPTCHA, auth)
- Performance tracking
- History tracking

Based on auto_apply.py with V2 enhancements from indeed_apply_v2.py
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import threading
from collections import deque

from dotenv import load_dotenv
from filelock import FileLock, Timeout as FileLockTimeout
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PWTimeout,
    sync_playwright,
)

from src.applications import is_applied, mark_applied
from src.db import is_db_available

load_dotenv()
logger = logging.getLogger("auto_apply_v2")

BASE_DIR = Path(__file__).resolve().parent.parent
RATE_FILE = BASE_DIR / "data" / "auto_apply_rate_v2.json"
METRICS_FILE = BASE_DIR / "data" / "auto_apply_metrics_v2.json"
LOGS_DIR = BASE_DIR / "data" / "logs"

# ── Config ────────────────────────────────────────────────────────────────────

def _env_bool(k: str, d: bool = False) -> bool:
    return os.getenv(k, str(d)).lower() in ("1", "true", "yes")

def _env_int(k: str, d: int) -> int:
    try:
        return int(os.getenv(k, str(d)))
    except ValueError:
        return d

AUTO_APPLY_ENABLED = _env_bool("AUTO_APPLY_ENABLED", False)
MAX_PER_RUN = _env_int("AUTO_APPLY_MAX_PER_RUN", 5)
SCORE_THRESHOLD = _env_int("AUTO_APPLY_SCORE_THRESHOLD", 75)
COOLDOWN_SECONDS = _env_int("AUTO_APPLY_COOLDOWN_SECONDS", 90)
DAILY_LIMIT = _env_int("AUTO_APPLY_DAILY_LIMIT", 30)
DRY_RUN = _env_bool("AUTO_APPLY_DRY_RUN", False)
ALLOW_CI_APPLY = _env_bool("ALLOW_CI_APPLY", False)
CV_PATH = BASE_DIR / os.getenv("CV_PATH", "data/cv.pdf")

LI_EMAIL = os.getenv("LINKEDIN_EMAIL", "")
LI_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "")

_EXCLUDE: List[str] = [
    k.strip().lower()
    for k in os.getenv(
        "AUTO_APPLY_EXCLUDE_KEYWORDS",
        "uae national,uae nationals only,uae national only,emirati only,"
        "graduate uae national only,quantity surveyor,surveyor,civil engineer,"
        "estimator,site engineer,co-founder,owner,founding partner,intern,internship",
    ).split(",")
    if k.strip()
]

def _is_excluded(job: Dict[str, Any]) -> bool:
    """True if any exclusion keyword is present in the job's combined text."""
    text = " ".join(
        str(job.get(f, ""))
        for f in ("title", "company", "location",
                  "description", "match_reason", "profile_explanation")
    ).lower()
    return any(kw in text for kw in _EXCLUDE)

# ── Status ────────────────────────────────────────────────────────────────────

class ApplyStatus(str, Enum):
    SUCCESS = "success"
    ALREADY_APPLIED = "already_applied"
    BELOW_THRESHOLD = "below_threshold"
    DISABLED = "disabled"
    RATE_LIMITED = "rate_limited"
    NO_EASY_APPLY = "no_easy_apply"
    LOGIN_FAILED = "login_failed"
    CAPTCHA = "captcha"
    SCREENING_REQUIRED = "screening_required"
    DRY_RUN = "dry_run"
    FAILED = "failed"
    RETRY_EXHAUSTED = "retry_exhausted"

@dataclass
class ApplyResult:
    job_id: str
    title: str
    company: str
    status: ApplyStatus
    message: str
    score: int = 0
    timestamp: str = ""
    retry_count: int = 0
    error_details: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

# ── Performance Metrics ───────────────────────────────────────────────────────

@dataclass
class PerformanceMetrics:
    jobs_scanned: int = 0
    easy_apply_found: int = 0
    applied: int = 0
    failed: int = 0
    skipped: int = 0
    total_duration_seconds: float = 0.0
    avg_apply_time_seconds: float = 0.0
    success_rate: float = 0.0

class MetricsTracker:
    """Track performance metrics over time."""

    def __init__(self, max_history: int = 100):
        self._max_history = max_history
        self._history: deque = deque(maxlen=max_history)
        self._current = PerformanceMetrics()
        self._run_start_time: Optional[float] = None

    def start_run(self) -> None:
        self._current = PerformanceMetrics()
        self._run_start_time = time.time()

    def end_run(self) -> PerformanceMetrics:
        if self._run_start_time:
            self._current.total_duration_seconds = time.time() - self._run_start_time
            if self._current.applied > 0:
                self._current.avg_apply_time_seconds = (
                    self._current.total_duration_seconds / self._current.applied
                )
            if self._current.applied + self._current.failed > 0:
                self._current.success_rate = (
                    self._current.applied / (self._current.applied + self._current.failed)
                )
        self._history.append(asdict(self._current))
        self._save()
        return self._current

    def record_scan(self, count: int) -> None:
        self._current.jobs_scanned += count

    def record_easy_apply(self, count: int) -> None:
        self._current.easy_apply_found += count

    def record_apply(self, success: bool) -> None:
        if success:
            self._current.applied += 1
        else:
            self._current.failed += 1

    def record_skip(self) -> None:
        self._current.skipped += 1

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self._history)

    def get_success_rate_trend(self) -> List[float]:
        return [h.get("success_rate", 0.0) for h in self._history]

    def _save(self) -> None:
        try:
            METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(METRICS_FILE, "w") as f:
                json.dump({"history": list(self._history)}, f, indent=2)
        except Exception as exc:
            logger.warning("metrics_save_failed error=%s", exc)

    def load(self) -> None:
        try:
            if METRICS_FILE.exists():
                with open(METRICS_FILE) as f:
                    data = json.load(f)
                    self._history = deque(data.get("history", []), maxlen=self._max_history)
        except Exception as exc:
            logger.warning("metrics_load_failed error=%s", exc)

# ── Enhanced Rate Limiter with Adaptive Cooldown ─────────────────────────────

class _RateLimiterV2:
    """
    Enhanced rate limiter with adaptive cooldown based on success rate.
    """

    _LOCK_TIMEOUT_S = 8
    _BURST_WINDOW_SECONDS = 30
    _BURST_MAX_APPLIES = 3

    def __init__(self, path: Path = RATE_FILE) -> None:
        self._path = path
        self._lock_path = Path(str(path) + ".lock")
        self._thread_lock = threading.Lock()
        self._adaptive_cooldown = COOLDOWN_SECONDS
        self._success_history: deque = deque(maxlen=10)
        self._burst_history: deque = deque(maxlen=self._BURST_MAX_APPLIES)

    def _load(self) -> Dict[str, Any]:
        try:
            with self._path.open() as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass
        return {
            "date": "",
            "count": 0,
            "last_apply": None,
            "success_count": 0,
            "failure_count": 0,
            "adaptive_cooldown": COOLDOWN_SECONDS,
        }

    def _save(self, state: Dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        import tempfile
        fd, tmp = tempfile.mkstemp(dir=str(self._path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(state, f)
            os.replace(tmp, str(self._path))
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _adaptive_adjust_cooldown(self) -> None:
        """Adjust cooldown based on recent success rate."""
        if len(self._success_history) < 5:
            return

        success_rate = sum(self._success_history) / len(self._success_history)

        if success_rate < 0.5:
            # Low success rate - increase cooldown
            self._adaptive_cooldown = min(self._adaptive_cooldown * 1.5, COOLDOWN_SECONDS * 3)
        elif success_rate > 0.8:
            # High success rate - decrease cooldown
            self._adaptive_cooldown = max(self._adaptive_cooldown * 0.8, COOLDOWN_SECONDS * 0.5)

    def _check_burst_protection(self) -> bool:
        """Check if burst protection is active."""
        now = time.time()
        # Remove old entries outside burst window
        while self._burst_history and now - self._burst_history[0] > self._BURST_WINDOW_SECONDS:
            self._burst_history.popleft()

        return len(self._burst_history) < self._BURST_MAX_APPLIES

    def _reset_if_new_day(self, state: Dict[str, Any]) -> Dict[str, Any]:
        today = date.today().isoformat()
        if state.get("date") != today:
            return {
                "date": today,
                "count": 0,
                "last_apply": None,
                "success_count": 0,
                "failure_count": 0,
                "adaptive_cooldown": COOLDOWN_SECONDS,
            }
        return state

    def can_apply(self) -> tuple[bool, str]:
        """Check if apply is allowed."""
        try:
            with FileLock(str(self._lock_path), timeout=self._LOCK_TIMEOUT_S):
                with self._thread_lock:
                    state = self._load()
                    state = self._reset_if_new_day(state)

                    if state["count"] >= DAILY_LIMIT:
                        return False, f"daily_limit {state['count']}/{DAILY_LIMIT}"

                    if not self._check_burst_protection():
                        return False, "burst_protection - too many applies in short time"

                    last = state.get("last_apply")
                    if last:
                        try:
                            elapsed = (
                                datetime.now(timezone.utc) -
                                datetime.fromisoformat(last).replace(tzinfo=timezone.utc)
                            ).total_seconds()
                            if elapsed < self._adaptive_cooldown:
                                return False, f"cooldown remaining={int(self._adaptive_cooldown - elapsed)}s"
                        except (ValueError, TypeError, AttributeError):
                            pass

                    return True, "ok"
        except FileLockTimeout:
            logger.warning("rate_limiter_lock_timeout - allowing apply")
            return True, "lock_timeout"

    def record(self, success: bool = True) -> None:
        """Record an apply attempt."""
        try:
            with FileLock(str(self._lock_path), timeout=self._LOCK_TIMEOUT_S):
                with self._thread_lock:
                    state = self._load()
                    state = self._reset_if_new_day(state)
                    state["count"] += 1
                    state["last_apply"] = datetime.now(timezone.utc).isoformat()

                    if success:
                        state["success_count"] += 1
                    else:
                        state["failure_count"] += 1

                    self._success_history.append(success)
                    self._adaptive_adjust_cooldown()
                    state["adaptive_cooldown"] = self._adaptive_cooldown

                    self._burst_history.append(time.time())
                    self._save(state)
        except FileLockTimeout:
            logger.warning("rate_limiter_record_lock_timeout - count may be inaccurate")

    @property
    def success_rate(self) -> float:
        """Calculate current success rate."""
        if len(self._success_history) == 0:
            return 0.0
        return sum(self._success_history) / len(self._success_history)

    @property
    def today_count(self) -> int:
        try:
            with FileLock(str(self._lock_path), timeout=self._LOCK_TIMEOUT_S):
                with self._thread_lock:
                    state = self._load()
                    state = self._reset_if_new_day(state)
                    return state["count"]
        except FileLockTimeout:
            return 0

# ── Browser setup ─────────────────────────────────────────────────────────────

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_STEALTH = """
Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});
Object.defineProperty(navigator,'languages',{get:()=>['en-US','en']});
window.chrome={runtime:{}};
"""

def _new_context(browser: Browser) -> BrowserContext:
    ctx = browser.new_context(
        user_agent=_UA,
        viewport={"width": 1366, "height": 768},
        locale="en-US",
        timezone_id="Asia/Dubai",
    )
    ctx.add_init_script(_STEALTH)
    return ctx

# ── Enhanced LinkedIn selectors with fallbacks ───────────────────────────────

class _LiV2:
    # Login selectors
    EMAIL = [
        "#username",
        "input[name='session_key']",
        "input[type='email']",
    ]
    PASSWORD = [
        "#password",
        "input[name='session_password']",
        "input[type='password']",
    ]
    LOGIN_BTN = [
        "button[type='submit']",
        "#login-submit",
        "button:has-text('Sign in')",
    ]

    # Apply selectors
    EASY_APPLY = [
        "button.jobs-apply-button[aria-label*='Easy Apply']",
        "button[aria-label*='Easy Apply']",
        ".jobs-apply-button",
        "button:has-text('Easy Apply')",
    ]
    MODAL = [
        ".jobs-easy-apply-modal",
        ".artdeco-modal",
        "[data-test-modal-id='easy-apply-modal']",
    ]
    NEXT_BTN = [
        "button[aria-label='Continue to next step']",
        "button:has-text('Next')",
        ".artdeco-button--primary:has-text('Next')",
    ]
    REVIEW_BTN = [
        "button[aria-label='Review your application']",
        "button:has-text('Review')",
        ".artdeco-button--primary:has-text('Review')",
    ]
    SUBMIT_BTN = [
        "button[aria-label='Submit application']",
        "button:has-text('Submit')",
        ".artdeco-button--primary:has-text('Submit')",
    ]
    DISMISS_BTN = [
        "button[aria-label='Dismiss']",
        "button:has-text('Dismiss')",
        ".artdeco-modal__dismiss",
    ]

    # Form selectors
    TEXT_INPUTS = [
        "input[type='text']:visible",
        "textarea:visible",
        "input[type='email']:visible",
    ]
    FILE_INPUT = [
        "input[type='file']",
    ]

    # Success/CAPTCHA selectors
    SUCCESS = [
        "h3:has-text('Application submitted')",
        ".artdeco-inline-feedback--success",
        "[data-test-modal-id='easy-apply-success-modal']",
        "button:has-text('Done')",
    ]
    CAPTCHA = [
        "#captcha-internal",
        ".recaptcha-checkbox",
        "[data-test-captcha]",
    ]

def _try_selectors(page: Page, selectors: List[str], timeout: int = 5000) -> Optional[Any]:
    """Try multiple selectors and return first match."""
    for selector in selectors:
        try:
            return page.wait_for_selector(selector, timeout=timeout)
        except PWTimeout:
            continue
    return None

# ── LLM screening ─────────────────────────────────────────────────────────────

def _llm_answers(questions: List[str], job: Dict[str, Any]) -> Dict[str, str]:
    if not questions:
        return {}
    try:
        from src.llm_scorer import get_llm_response
        from src.profile import get_candidate_profile

        p = get_candidate_profile()
        ctx = (
            f"Name: {p.get('name','N/A')}\n"
            f"Experience: {p.get('experience_summary','N/A')}\n"
            f"Skills: {', '.join(p.get('skills',[]))}\n"
            f"Roles: {', '.join(p.get('target_roles',[]))}\n"
            "Location: UAE (available immediately)"
        )
        qs = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
        prompt = (
            f"LinkedIn Easy Apply for: {job.get('title')} at {job.get('company')}.\n\n"
            f"CANDIDATE:\n{ctx}\n\nQUESTIONS:\n{qs}\n\n"
            'Reply ONLY with JSON: {"1":"answer","2":"answer"}'
        )
        raw = get_llm_response(prompt)
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            parsed: Dict[str, str] = json.loads(raw[start:end])
            return {
                questions[int(k) - 1]: v
                for k, v in parsed.items()
                if k.isdigit() and int(k) <= len(questions)
            }
    except Exception as exc:
        logger.warning("llm_screening_failed error=%s", exc)
    return {}

# ── Detection functions ───────────────────────────────────────────────────────

def _detect_captcha(page: Page) -> bool:
    """Detect CAPTCHA challenge."""
    try:
        for selector in _LiV2.CAPTCHA:
            if page.query_selector(selector):
                return True
    except Exception:
        pass
    return False

def _detect_auth_required(page: Page) -> bool:
    """Detect if authentication is required."""
    try:
        return "login" in page.url.lower() or "signin" in page.url.lower()
    except Exception:
        return False

# ── Error Recovery ───────────────────────────────────────────────────────────

def _get_recovery_action(error_type: str, attempt: int) -> str:
    """Determine recovery action based on error type and attempt."""
    if attempt == 0:
        return "wait"
    elif attempt == 1:
        if error_type in ("network", "timeout"):
            return "refresh_page"
        elif error_type in ("captcha", "auth"):
            return "new_context"
        else:
            return "wait"
    else:
        return "new_context"

def _apply_recovery(page: Page, action: str, browser: Browser) -> Optional[BrowserContext]:
    """Apply recovery action."""
    if action == "wait":
        time.sleep(5)
    elif action == "refresh_page":
        page.reload(wait_until="domcontentloaded")
        time.sleep(2)
    elif action == "clear_cookies":
        page.context.clear_cookies()
        page.reload(wait_until="domcontentloaded")
        time.sleep(2)
    elif action == "new_context":
        old_ctx = page.context
        new_ctx = _new_context(browser)
        new_page = new_ctx.new_page()
        try:
            old_ctx.close()
        except Exception:
            pass
        return new_ctx
    return None

# ── Engine V2 ───────────────────────────────────────────────────────────────

class LinkedInEasyApplyEngineV2:
    """
    LinkedIn Easy Apply automation V2 with enhanced features.
    """

    def __init__(
        self,
        headless: bool = False,
        rate_limiter: Optional[_RateLimiterV2] = None,
        max_retries: int = 2,
    ) -> None:
        self._headless = headless
        self._rate = rate_limiter or _RateLimiterV2()
        self._max_retries = max_retries
        self._pw: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._ctx: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._logged_in = False
        self._metrics = MetricsTracker()
        self._metrics.load()

    def __enter__(self) -> "LinkedInEasyApplyEngineV2":
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self._headless,
            args=["--no-sandbox", "--disable-dev-shm-usage",
                  "--disable-blink-features=AutomationControlled"],
        )
        self._ctx = _new_context(self._browser)
        self._page = self._ctx.new_page()
        self._page.set_default_timeout(25_000)
        self._metrics.start_run()
        return self

    def __exit__(self, *_: Any) -> None:
        metrics = self._metrics.end_run()
        logger.info(
            "run_metrics scanned=%d applied=%d failed=%d success_rate=%.1f%%",
            metrics.jobs_scanned,
            metrics.applied,
            metrics.failed,
            metrics.success_rate * 100,
        )
        for obj in (self._page, self._ctx, self._browser):
            try:
                if obj:
                    obj.close()
            except Exception:
                pass
        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass

    def apply_batch(
        self,
        jobs: List[Dict[str, Any]],
        max_applies: int = MAX_PER_RUN,
    ) -> List[ApplyResult]:
        eligible = [
            j for j in jobs
            if "linkedin.com/jobs/view" in j.get("link", "")
            and int(j.get("score") or 0) >= SCORE_THRESHOLD
            and not is_applied(j)
            and not _is_excluded(j)
        ]
        excluded_count = sum(1 for j in jobs if _is_excluded(j))
        if excluded_count:
            logger.info("apply_batch_excluded count=%d", excluded_count)

        self._metrics.record_scan(len(jobs))
        self._metrics.record_easy_apply(len(eligible))

        logger.info(
            "apply_batch total=%d eligible=%d max=%d dry_run=%s",
            len(jobs), len(eligible), max_applies, DRY_RUN,
        )

        results: List[ApplyResult] = []
        for job in eligible[:max_applies]:
            r = self._apply_one_with_retry(job)
            results.append(r)
            logger.info("apply_result %s", json.dumps(r.to_dict()))
            if r.status == ApplyStatus.SUCCESS:
                self._metrics.record_apply(success=True)
                time.sleep(self._rate._adaptive_cooldown)
            else:
                self._metrics.record_apply(success=False)

        return results

    def _apply_one_with_retry(self, job: Dict[str, Any]) -> ApplyResult:
        """Apply with retry logic and error recovery."""
        link = job.get("link", "")
        title = job.get("title", "Unknown")
        company = job.get("company", "Unknown")
        score = int(job.get("score") or 0)

        def r(s: ApplyStatus, m: str, retry_count: int = 0) -> ApplyResult:
            return ApplyResult(
                job_id=link,
                title=title,
                company=company,
                status=s,
                message=m,
                score=score,
                retry_count=retry_count,
            )

        for attempt in range(self._max_retries + 1):
            try:
                result = self._apply_one(job)
                if result.status in (ApplyStatus.SUCCESS, ApplyStatus.DRY_RUN):
                    self._rate.record(success=True)
                    return result
                elif result.status == ApplyStatus.FAILED:
                    # Determine error type and recovery action
                    error_type = self._classify_error(result.message)
                    recovery = _get_recovery_action(error_type, attempt)

                    if attempt < self._max_retries:
                        logger.warning(
                            "apply_failed attempt=%d error=%s recovery=%s",
                            attempt, result.message, recovery
                        )
                        _apply_recovery(self._page, recovery, self._browser)
                        time.sleep((2 ** attempt) * 5)  # Exponential backoff
                        continue
                    else:
                        self._rate.record(success=False)
                        return r(ApplyStatus.RETRY_EXHAUSTED,
                               f"Retries exhausted: {result.message}", attempt)
                else:
                    # Non-retryable status
                    if result.status == ApplyStatus.SUCCESS:
                        self._rate.record(success=True)
                    else:
                        self._rate.record(success=False)
                    return result
            except Exception as exc:
                logger.exception("apply_unhandled attempt=%d title=%s", attempt, title)
                if attempt < self._max_retries:
                    recovery = _get_recovery_action("network", attempt)
                    _apply_recovery(self._page, recovery, self._browser)
                    time.sleep((2 ** attempt) * 5)
                    continue
                else:
                    self._rate.record(success=False)
                    return r(ApplyStatus.RETRY_EXHAUSTED, str(exc), attempt)

        return r(ApplyStatus.RETRY_EXHAUSTED, "Max retries reached", self._max_retries)

    def _classify_error(self, message: str) -> str:
        """Classify error type for recovery strategy."""
        message_lower = message.lower()
        if "timeout" in message_lower or "network" in message_lower:
            return "network"
        elif "captcha" in message_lower:
            return "captcha"
        elif "login" in message_lower or "auth" in message_lower:
            return "auth"
        else:
            return "unknown"

    def _apply_one(self, job: Dict[str, Any]) -> ApplyResult:
        link = job.get("link", "")
        title = job.get("title", "Unknown")
        company = job.get("company", "Unknown")
        score = int(job.get("score") or 0)

        def r(s: ApplyStatus, m: str) -> ApplyResult:
            return ApplyResult(job_id=link, title=title, company=company,
                           status=s, message=m, score=score)

        if not AUTO_APPLY_ENABLED:
            return r(ApplyStatus.DISABLED, "AUTO_APPLY_ENABLED=false")

        if os.getenv("GITHUB_ACTIONS") and not ALLOW_CI_APPLY:
            return r(ApplyStatus.DISABLED,
                     "CI detected — LinkedIn blocks datacenter IPs")

        if not LI_EMAIL or not LI_PASSWORD:
            return r(ApplyStatus.DISABLED,
                     "LINKEDIN_EMAIL / LINKEDIN_PASSWORD missing in .env")

        if is_applied(job):
            return r(ApplyStatus.ALREADY_APPLIED, "already in tracking")

        if score < SCORE_THRESHOLD:
            return r(ApplyStatus.BELOW_THRESHOLD, f"score={score} < {SCORE_THRESHOLD}")

        allowed, reason = self._rate.can_apply()
        if not allowed:
            return r(ApplyStatus.RATE_LIMITED, reason)

        if DRY_RUN:
            logger.info("dry_run title=%s company=%s score=%d", title, company, score)
            return r(ApplyStatus.DRY_RUN, f"would_apply score={score}")

        try:
            return self._do_apply(job)
        except Exception as exc:
            logger.exception("apply_unhandled title=%s", title)
            self._save_attempt(link, title, company, "failed", str(exc))
            return r(ApplyStatus.FAILED, str(exc))

    def _ensure_logged_in(self) -> bool:
        if self._logged_in:
            return True
        page = self._page
        if page is None:
            raise RuntimeError("Browser page not initialised")

        page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
        page.wait_for_timeout(2_000)

        if "feed" in page.url.lower():
            self._logged_in = True
            return True

        try:
            email_input = _try_selectors(page, _LiV2.EMAIL, timeout=5000)
            password_input = _try_selectors(page, _LiV2.PASSWORD, timeout=5000)
            login_btn = _try_selectors(page, _LiV2.LOGIN_BTN, timeout=5000)

            if not (email_input and password_input and login_btn):
                logger.error("linkedin_login_selectors_not_found")
                return False

            email_input.fill(LI_EMAIL)
            password_input.fill(LI_PASSWORD)
            login_btn.click()
            page.wait_for_url("**/feed/**", timeout=20_000)
            self._logged_in = True
            logger.info("linkedin_login_success")
            return True
        except PWTimeout:
            if _detect_captcha(page):
                logger.error("linkedin_captcha_detected")
            else:
                logger.error("linkedin_login_timeout url=%s", page.url)
            return False
        except Exception as exc:
            logger.error("linkedin_login_error error=%s", exc)
            return False

    def _do_apply(self, job: Dict[str, Any]) -> ApplyResult:
        if self._page is None:
            raise RuntimeError("Browser page not initialised")

        link = job.get("link", "")
        title = job.get("title", "Unknown")
        company = job.get("company", "Unknown")
        score = int(job.get("score") or 0)

        def r(s: ApplyStatus, m: str) -> ApplyResult:
            return ApplyResult(job_id=link, title=title, company=company,
                           status=s, message=m, score=score)

        if not self._ensure_logged_in():
            return r(ApplyStatus.LOGIN_FAILED, "login failed")

        self._page.goto(link, wait_until="domcontentloaded", timeout=30_000)
        self._page.wait_for_timeout(2_500)

        if _detect_captcha(self._page):
            return r(ApplyStatus.CAPTCHA, "captcha triggered")

        try:
            btn = _try_selectors(self._page, _LiV2.EASY_APPLY, timeout=8_000)
        except PWTimeout:
            return r(ApplyStatus.NO_EASY_APPLY, "Easy Apply button not found")

        if not btn:
            return r(ApplyStatus.NO_EASY_APPLY, "Easy Apply button not found")

        btn.click()
        self._page.wait_for_timeout(2_000)

        steps = 0
        while steps < 12:
            steps += 1

            if steps == 1:
                self._maybe_upload_cv()

            self._fill_visible_fields(job)

            if _try_selectors(self._page, _LiV2.SUCCESS, timeout=1000):
                break

            review = _try_selectors(self._page, _LiV2.REVIEW_BTN, timeout=1000)
            if review and review.is_enabled():
                review.click()
                self._page.wait_for_timeout(1_500)
                continue

            submit = _try_selectors(self._page, _LiV2.SUBMIT_BTN, timeout=1000)
            if submit and submit.is_enabled():
                submit.click()
                self._page.wait_for_timeout(3_000)
                break

            nxt = _try_selectors(self._page, _LiV2.NEXT_BTN, timeout=1000)
            if nxt and nxt.is_enabled():
                nxt.click()
                self._page.wait_for_timeout(1_500)
                continue

            return r(ApplyStatus.SCREENING_REQUIRED,
                     f"stuck at step {steps}")

        if not _try_selectors(self._page, _LiV2.SUCCESS, timeout=1000):
            return r(ApplyStatus.FAILED, "no success confirmation")

        mark_applied(job, status="applied",
                     notes="Auto-applied via LinkedIn Easy Apply V2")
        self._rate.record(success=True)
        self._save_attempt(link, title, company, "success")
        logger.info("apply_success title=%s score=%d daily=%d",
                    title, score, self._rate.today_count)
        return r(ApplyStatus.SUCCESS, f"submitted in {steps} step(s)")

    def _maybe_upload_cv(self) -> None:
        if not CV_PATH.exists():
            logger.warning("cv_missing path=%s", CV_PATH)
            return
        inp = _try_selectors(self._page, _LiV2.FILE_INPUT, timeout=2000)
        if inp:
            try:
                inp.set_input_files(str(CV_PATH))
                self._page.wait_for_timeout(1_000)
                logger.debug("cv_uploaded")
            except Exception as exc:
                logger.warning("cv_upload_failed error=%s", exc)

    def _fill_visible_fields(self, job: Dict[str, Any]) -> None:
        questions: List[str] = []
        inputs = self._page.query_selector_all(_LiV2.TEXT_INPUTS[0])

        for inp in inputs:
            try:
                lbl: str = inp.evaluate(
                    """el => {
                        if (el.id) {
                            const l = document.querySelector('label[for="'+el.id+'"]');
                            if (l) return l.innerText.trim();
                        }
                        const wrap = el.closest(
                            '.fb-dash-form-element,'
                            + '.jobs-easy-apply-form-section__grouping,'
                            + '[data-test-form-element]'
                        );
                        return wrap
                            ? (wrap.querySelector('label,legend')?.innerText?.trim() || '')
                            : '';
                    }"""
                )
                if lbl:
                    questions.append(lbl)
            except Exception:
                pass

        if not questions:
            return

        answers = _llm_answers(questions, job)
        for inp, q in zip(inputs, questions):
            ans = answers.get(q, "")
            if not ans:
                continue
            try:
                if not inp.input_value():
                    inp.fill(ans)
            except Exception as exc:
                logger.debug("fill_failed q=%s err=%s", q[:40], exc)

    def _save_attempt(
        self,
        job_id: str, title: str, company: str,
        status: str, error: Optional[str] = None,
    ) -> None:
        if not is_db_available():
            return
        try:
            from src.db import get_db_connection
            conn = get_db_connection()
            if not conn:
                return
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO auto_apply_attempts
                        (job_id, title, company, status, error, timestamp)
                    VALUES (%s,%s,%s,%s,%s,NOW())
                    ON CONFLICT (job_id) DO UPDATE SET
                        status=EXCLUDED.status,
                        error=EXCLUDED.error,
                        timestamp=NOW()
                    """,
                    (job_id, title, company, status, error),
                )
        except Exception as exc:
            logger.warning("db_save_failed error=%s", exc)

# ── Pipeline entry point ──────────────────────────────────────────────────────

def run_auto_apply_v2(
    jobs: List[Dict[str, Any]],
    max_applies: int = MAX_PER_RUN,
    headless: bool = False,
) -> List[ApplyResult]:
    """
    Entry point for LinkedIn Easy Apply V2.
    """
    if not AUTO_APPLY_ENABLED:
        logger.info("auto_apply_disabled AUTO_APPLY_ENABLED=false")
        return []

    with LinkedInEasyApplyEngineV2(headless=headless) as engine:
        return engine.apply_batch(jobs, max_applies=max_applies)
