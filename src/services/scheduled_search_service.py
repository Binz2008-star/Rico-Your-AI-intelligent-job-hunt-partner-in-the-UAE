"""
src/services/scheduled_search_service.py

Issue #1249 Phase A — scheduled saved searches (backend only, inert by default).

A natural-language command such as
``ابحث يوميًا عن وظائف مناسبة في دبي براتب 10,000+ درهم`` or
``search daily for jobs in Dubai with salary 10,000+ AED`` becomes ONE
canonical saved search per (user, cadence, city, salary) stored in the
existing ``rico_saved_searches`` row — schedule metadata lives inside the
``filters`` JSONB under ``"schedule"`` (purely additive; no DDL, no
migration). Repeating the command upserts the same canonical row instead of
creating duplicates (the table's UNIQUE(user_id, query) does the work).

The cron sweep (``run_scheduled_search_sweep``) executes each enabled
schedule against the real match engine with the SAVED constraints (city,
minimum AED salary), excludes jobs the user already acted on and jobs already
delivered by a previous run, and stores the results IN-APP on the schedule
row. It never sends email — email job alerts remain a separate, opt-in
channel behind ``RICO_ENABLE_EMAIL_ALERTS`` (src/services/email_alert_service).

Honest-salary rule: a job's salary is only compared against the minimum when
the source actually states one. Unknown salary is carried as
``salary_known=False`` and NEVER invented or inferred.

Kill switch: ``RICO_ENABLE_SCHEDULED_SEARCHES`` (default false). While off the
sweep is a no-op (``{"status": "disabled"}``); ``dry_run=True`` bypasses the
switch to evaluate matching without persisting anything, mirroring the email
sweep's smoke-test semantics.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Limits / defaults ─────────────────────────────────────────────────────────

MAX_RESULTS_PER_RUN = 10          # jobs stored per schedule per sweep
MAX_DELIVERED_KEYS = 500          # cross-run dedup memory per schedule
MAX_SCHEDULES_PER_SWEEP = 200     # provider-cost cap per sweep run
DEFAULT_MIN_SCORE = 60            # same override keys as the email alerts

_SCHEDULE_KEY = "schedule"


def scheduled_searches_enabled() -> bool:
    """Kill switch: scheduled execution is off unless explicitly enabled."""
    return os.getenv("RICO_ENABLE_SCHEDULED_SEARCHES", "false").strip().lower() in {
        "1", "true", "yes", "on",
    }


# ── Natural-language parsing (AR/EN) ─────────────────────────────────────────

# Arabic-Indic and Extended Arabic-Indic digits → ASCII, so ١٠٠٠٠ parses too.
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

# "daily" cadence markers. NOTE: Arabic اليوم ("today") must NOT match — the
# pattern requires the يومي stem or an explicit كل يوم.
_CADENCE_DAILY_RE = re.compile(
    r"\bdaily\b|\bevery\s+day\b|\beach\s+day\b|يومي(?:اً|ًا|ا|ة|ًّا)?\b|كل\s+يوم",
    re.IGNORECASE,
)

_JOBS_WORD_RE = re.compile(r"\bjobs?\b|\bvacanc(?:y|ies)\b|\bpositions?\b|وظائف|وظيفة|شواغر", re.IGNORECASE)

# A create command needs an explicit search/notify verb — "daily paid jobs"
# (no verb) must stay a normal one-shot search, not silently become a schedule.
_SEARCH_VERB_RE = re.compile(
    r"\b(?:search|find|look|get|send|alert|notify|show)\b|ابحث|إبحث|دور|دوّر|جد|أرسل|ارسل|نبه|نبّه|اعرض",
    re.IGNORECASE,
)

# Management phrasing targets the existing daily/scheduled search, not jobs.
_SEARCH_NOUN_RE = re.compile(
    r"\b(?:search(?:es)?|alerts?)\b|البحث|بحثي|التنبيه(?:ات)?", re.IGNORECASE
)
_PAUSE_RE = re.compile(r"\b(?:pause|stop|disable|turn\s+off|suspend)\b|أوقف|اوقف|علق|علّق|عط[لّ]ل?", re.IGNORECASE)
_RESUME_RE = re.compile(r"\b(?:resume|enable|restart|reactivate|turn\s+on)\b|استأنف|استانف|شغل|شغّل|فع[لّ]ل?", re.IGNORECASE)
_DELETE_RE = re.compile(r"\b(?:delete|remove|cancel)\b|احذف|امسح|ألغ|الغ", re.IGNORECASE)
_STATUS_RE = re.compile(r"\b(?:status|show|list|view)\b|حالة|وضع|أرني|اعرض|اظهر", re.IGNORECASE)

# Canonical UAE city names (EN) keyed by the aliases users actually type.
_CITY_ALIASES: Dict[str, str] = {
    "dubai": "Dubai", "دبي": "Dubai",
    "abu dhabi": "Abu Dhabi", "abudhabi": "Abu Dhabi",
    "أبوظبي": "Abu Dhabi", "أبو ظبي": "Abu Dhabi", "ابوظبي": "Abu Dhabi", "ابو ظبي": "Abu Dhabi",
    "sharjah": "Sharjah", "الشارقة": "Sharjah",
    "ajman": "Ajman", "عجمان": "Ajman",
    "al ain": "Al Ain", "العين": "Al Ain",
    "ras al khaimah": "Ras Al Khaimah", "رأس الخيمة": "Ras Al Khaimah", "راس الخيمة": "Ras Al Khaimah",
    "fujairah": "Fujairah", "الفجيرة": "Fujairah",
    "umm al quwain": "Umm Al Quwain", "أم القيوين": "Umm Al Quwain", "ام القيوين": "Umm Al Quwain",
}

# Salary: "10,000", "10000", "10k", "١٠٠٠٠", optionally suffixed +, with an
# AED/dirham marker somewhere in the message (numbers alone are ambiguous).
_SALARY_NUM_RE = re.compile(r"(\d{1,3}(?:[.,]\d{3})+|\d+)\s*(k)?\s*\+?", re.IGNORECASE)
_CURRENCY_RE = re.compile(r"\baed\b|\bdhs?\b|\bdirhams?\b|درهم|دراهم", re.IGNORECASE)


def _normalize_digits(text: str) -> str:
    return (text or "").translate(_ARABIC_DIGITS)


def parse_min_salary_aed(text: str) -> Optional[int]:
    """Extract a monthly minimum salary in AED from a command, if stated.

    Returns None when the message carries no currency marker or no plausible
    figure — the caller must treat that as "no salary constraint", never guess.
    """
    text = _normalize_digits(text)
    if not _CURRENCY_RE.search(text):
        return None
    best: Optional[int] = None
    for m in _SALARY_NUM_RE.finditer(text):
        raw = m.group(1).replace(",", "").replace(".", "")
        try:
            value = int(raw)
        except ValueError:
            continue
        if m.group(2):  # k suffix
            value *= 1000
        # Plausible monthly AED range; skips stray small numbers ("top 5 jobs").
        if 1000 <= value <= 1_000_000 and (best is None or value > best):
            best = value
    return best


def parse_city(text: str) -> Optional[str]:
    lowered = _normalize_digits(text).lower()
    for alias, canonical in _CITY_ALIASES.items():
        if alias in lowered:
            return canonical
    return None


def parse_scheduled_search_command(text: str) -> Optional[Dict[str, Any]]:
    """Parse a create-style scheduled-search command (AR or EN).

    Requires a daily-cadence marker AND a jobs word AND an explicit
    search/notify verb; city and salary are optional refinements. Returns None
    when the message is not a scheduled search request (plain searches must
    keep their existing routing).
    """
    if not text or not text.strip():
        return None
    if not _CADENCE_DAILY_RE.search(text):
        return None
    if not _JOBS_WORD_RE.search(text):
        return None
    if not _SEARCH_VERB_RE.search(text):
        return None
    return {
        "cadence": "daily",
        "city": parse_city(text),
        "min_salary_aed": parse_min_salary_aed(text),
    }


def parse_management_command(text: str) -> Optional[str]:
    """Return 'pause' | 'resume' | 'delete' | 'status' for a manage command.

    Only fires when the message targets the daily/scheduled search itself
    (cadence marker + search/alert noun, without being a create command).
    """
    if not text or not text.strip():
        return None
    if not _CADENCE_DAILY_RE.search(text) or not _SEARCH_NOUN_RE.search(text):
        return None
    # Order matters: delete beats pause ("cancel and remove"), status is last.
    if _DELETE_RE.search(text):
        return "delete"
    if _PAUSE_RE.search(text):
        return "pause"
    if _RESUME_RE.search(text):
        return "resume"
    if _STATUS_RE.search(text):
        return "status"
    return None


def canonical_query(params: Dict[str, Any]) -> str:
    """Stable identity string for a schedule — same params (in AR or EN)
    always map to the same saved-search row via UNIQUE(user_id, query)."""
    city = params.get("city") or "All UAE"
    salary = params.get("min_salary_aed")
    salary_part = f"{salary}+ AED" if salary else "any salary"
    return f"Scheduled {params.get('cadence', 'daily')} job search — {city} — {salary_part}"


# ── Identity guard ───────────────────────────────────────────────────────────

_PUBLIC_EMAIL_KEY_RE = re.compile(r"^e-[0-9a-f]{40}$")


def _is_public_identity(user_id: str) -> bool:
    """Public/guest chat identities can never own scheduled searches."""
    uid = (user_id or "").strip()
    return not uid or uid.startswith("public") or bool(_PUBLIC_EMAIL_KEY_RE.match(uid))


# ── Persistence (existing rico_saved_searches; JSONB only) ───────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_user_schedules(user_id: str) -> List[Dict[str, Any]]:
    """The user's scheduled searches (saved searches carrying a schedule)."""
    from src.repositories.profile_repo import list_saved_searches

    out: List[Dict[str, Any]] = []
    for row in list_saved_searches(user_id, limit=50):
        filters = row.get("filters") or {}
        sched = filters.get(_SCHEDULE_KEY)
        if not isinstance(sched, dict):
            continue
        item = {
            "id": str(row.get("id")) if row.get("id") is not None else None,
            "query": row.get("query"),
            "schedule": sched,
        }
        for ts_key in ("created_at", "updated_at"):
            v = row.get(ts_key)
            if hasattr(v, "isoformat"):
                item[ts_key] = v.isoformat()
        out.append(item)
    return out


def create_or_update_scheduled_search(user_id: str, message: str) -> Optional[Dict[str, Any]]:
    """Create (or canonically update) the schedule described by *message*.

    Returns {"query", "schedule", "search_id", "outcome"} or None when the
    message does not parse as a scheduled-search command.
    """
    params = parse_scheduled_search_command(message)
    if params is None:
        return None

    from src.repositories.profile_repo import save_search

    query = canonical_query(params)
    outcome = "created"
    schedule: Dict[str, Any] = {
        "enabled": True,
        "cadence": params["cadence"],
        "city": params["city"],
        "min_salary_aed": params["min_salary_aed"],
        "created_at": _now_iso(),
        "last_run_at": None,
        "last_run_new": 0,
        "delivered_keys": [],
        "last_results": [],
    }

    # Reuse run history when the same canonical schedule already exists so an
    # update never resets dedup memory or the visible last results.
    for existing in get_user_schedules(user_id):
        if existing.get("query") == query:
            prev = existing["schedule"]
            schedule["created_at"] = prev.get("created_at") or schedule["created_at"]
            schedule["last_run_at"] = prev.get("last_run_at")
            schedule["last_run_new"] = prev.get("last_run_new", 0)
            schedule["delivered_keys"] = list(prev.get("delivered_keys") or [])[-MAX_DELIVERED_KEYS:]
            schedule["last_results"] = list(prev.get("last_results") or [])
            outcome = "updated"
            break

    search_id = save_search(user_id, query, {_SCHEDULE_KEY: schedule})
    if search_id is None and outcome == "created":
        # DB unavailable or identity could not be resolved — nothing persisted.
        return {"query": query, "schedule": schedule, "search_id": None, "outcome": "failed"}
    return {"query": query, "schedule": schedule, "search_id": search_id, "outcome": outcome}


def set_schedules_enabled(user_id: str, enabled: bool) -> int:
    """Pause/resume every schedule the user owns. Returns affected count."""
    from src.repositories.profile_repo import save_search

    count = 0
    for item in get_user_schedules(user_id):
        sched = dict(item["schedule"])
        if bool(sched.get("enabled")) == enabled:
            continue
        sched["enabled"] = enabled
        if save_search(user_id, item["query"], {_SCHEDULE_KEY: sched}, search_id=item["id"]):
            count += 1
    return count


def set_schedule_enabled_by_id(user_id: str, search_id: str, enabled: bool) -> bool:
    """Pause/resume ONE schedule by id, strictly within the user's own rows.

    Returns False when the id doesn't resolve to one of the user's scheduled
    searches — the caller maps that to 404, so ids can't be probed cross-user.
    """
    from src.repositories.profile_repo import save_search

    for item in get_user_schedules(user_id):
        if str(item.get("id")) == str(search_id):
            sched = dict(item["schedule"])
            sched["enabled"] = bool(enabled)
            return bool(save_search(user_id, item["query"], {_SCHEDULE_KEY: sched},
                                    search_id=item["id"]))
    return False


def delete_schedules(user_id: str) -> int:
    """Delete every scheduled search the user owns. Returns deleted count."""
    from src.repositories.profile_repo import delete_search

    count = 0
    for item in get_user_schedules(user_id):
        if item.get("id") and delete_search(user_id, item["id"]):
            count += 1
    return count


# ── Matching (saved-search constraints on the real engine) ───────────────────

_SALARY_FIELDS = (
    "salary_min", "min_salary", "job_min_salary",
    "salary", "salary_max", "max_salary", "job_max_salary",
)


def extract_salary_aed(job: Dict[str, Any]) -> Tuple[bool, Optional[int]]:
    """(salary_known, monthly_amount) from whatever the source stated.

    Never guesses: absent/unparseable salary → (False, None). The first field
    hit wins, preferring stated minimums so filtering is conservative.
    """
    for field in _SALARY_FIELDS:
        raw = job.get(field)
        if raw is None or raw == "":
            continue
        if isinstance(raw, (int, float)) and raw > 0:
            return True, int(raw)
        digits = re.sub(r"[^\d]", "", _normalize_digits(str(raw)))
        if digits:
            try:
                value = int(digits)
            except ValueError:
                continue
            if 100 <= value <= 10_000_000:
                return True, value
    return False, None


def _min_score_for(user_id: str) -> int:
    try:
        from src.services.settings_service import get_settings

        s = get_settings(user_id=user_id) or {}
        return int(s.get("score_threshold_watch") or s.get("min_score") or DEFAULT_MIN_SCORE)
    except Exception:
        return DEFAULT_MIN_SCORE


def _excluded_pair_keys(user_id: str) -> set:
    """(title|company) keys the user already acted on — never re-deliver."""
    try:
        from src.repositories import user_job_context_repo as ujc

        rows = ujc.get_by_status(user_id, ["applied", "saved", "skipped", "blocked", "hidden"], limit=200)
    except Exception:
        logger.debug("scheduled_search: excluded-keys lookup failed user=%s", user_id, exc_info=True)
        rows = []
    keys = set()
    for r in rows:
        t = (r.get("title") or "").strip().lower()
        c = (r.get("company") or "").strip().lower()
        if t and c:
            keys.add(f"{t}|{c}")
    return keys


def _job_link(job: Dict[str, Any]) -> str:
    for k in ("link", "apply_link", "url", "alt_link"):
        v = (job.get(k) or "").strip()
        if v:
            return v
    return ""


def find_constrained_matches(profile: Any, user_id: str, schedule: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Run the existing match engine, then enforce the SAVED constraints.

    City filter, honest salary filter (known-below-minimum excluded; unknown
    kept and labeled), lifecycle exclusions, cross-run dedup, and the
    every-job-has-a-real-link rule. Best-scored first, capped.
    """
    try:
        from src.rico_repo_adapter import RicoSystem
        from src.applications import get_job_id
    except Exception:
        logger.exception("scheduled_search: match engine import failed user=%s", user_id)
        return []

    try:
        result = RicoSystem().run_for_profile(profile, limit=MAX_RESULTS_PER_RUN * 3)
    except Exception:
        logger.exception("scheduled_search: run_for_profile failed user=%s", user_id)
        return []
    if not isinstance(result, dict) or result.get("status") != "completed":
        return []

    city = (schedule.get("city") or "").strip()
    min_salary = schedule.get("min_salary_aed")
    delivered = set(schedule.get("delivered_keys") or [])
    excluded = _excluded_pair_keys(user_id)
    threshold = _min_score_for(user_id)

    picked: List[Dict[str, Any]] = []
    seen: set = set()
    for m in result.get("matches") or []:
        if len(picked) >= MAX_RESULTS_PER_RUN:
            break
        title = (m.get("title") or "").strip()
        company = (m.get("company") or "").strip()
        link = _job_link(m)
        if not title or not company or not link:
            continue  # never surface a job without a real destination
        if int(m.get("score") or 0) < threshold:
            continue
        location = (m.get("location") or "").strip()
        if city and city.lower() not in location.lower():
            continue
        salary_known, salary_amount = extract_salary_aed(m)
        if min_salary and salary_known and salary_amount is not None and salary_amount < int(min_salary):
            continue  # stated salary below the saved minimum
        pair = f"{title.lower()}|{company.lower()}"
        if pair in excluded or pair in seen:
            continue
        job_key = get_job_id({"title": title, "company": company, "location": location, "link": link})
        if job_key in delivered:
            continue  # already delivered by a previous run
        seen.add(pair)
        picked.append({
            "title": title,
            "company": company,
            "location": location,
            "score": int(m.get("score") or 0),
            "link": link,
            "salary_known": salary_known,
            "salary_aed": salary_amount if salary_known else None,
            "why": (m.get("rico_explanation") or m.get("profile_explanation") or "").strip(),
            "job_key": job_key,
        })
    return picked


# ── Cron sweep (in-app delivery only; no email) ──────────────────────────────

def run_scheduled_search_sweep(*, dry_run: bool = False) -> Dict[str, Any]:
    """Execute every enabled schedule once. Cron entry point; never raises.

    Honors the RICO_ENABLE_SCHEDULED_SEARCHES kill switch (dry_run bypasses it
    to evaluate matching WITHOUT persisting results or dedup keys).
    """
    if not dry_run and not scheduled_searches_enabled():
        logger.info("scheduled_search: disabled (RICO_ENABLE_SCHEDULED_SEARCHES not set)")
        return {"status": "disabled", "searches": 0, "users": 0,
                "new_results": 0, "skipped": 0, "failed": 0, "dry_run": dry_run}

    try:
        from src.repositories.profile_repo import list_enabled_scheduled_searches

        rows = list_enabled_scheduled_searches()
    except Exception:
        logger.exception("scheduled_search: roster lookup failed")
        return {"status": "error", "searches": 0, "users": 0,
                "new_results": 0, "skipped": 0, "failed": 0, "dry_run": dry_run}

    rows = rows[:MAX_SCHEDULES_PER_SWEEP]
    users = {r.get("external_user_id") for r in rows if r.get("external_user_id")}
    new_total = skipped = failed = 0

    for row in rows:
        user_id = (row.get("external_user_id") or "").strip()
        filters = row.get("filters") or {}
        sched = filters.get(_SCHEDULE_KEY)
        if not user_id or not isinstance(sched, dict) or not sched.get("enabled"):
            skipped += 1
            continue
        try:
            from src.repositories.profile_repo import get_profile

            profile = get_profile(user_id)
            if not profile:
                skipped += 1
                continue
            matches = find_constrained_matches(profile, user_id, sched)
            new_total += len(matches)
            if dry_run:
                continue

            from src.repositories.profile_repo import save_search

            updated = dict(sched)
            updated["last_run_at"] = _now_iso()
            updated["last_run_new"] = len(matches)
            if matches:
                # No matches → keep previous results visible; no noisy reset.
                updated["last_results"] = matches
                delivered = list(sched.get("delivered_keys") or [])
                delivered.extend(m["job_key"] for m in matches)
                updated["delivered_keys"] = delivered[-MAX_DELIVERED_KEYS:]
            save_search(user_id, row.get("query") or "", {_SCHEDULE_KEY: updated},
                        search_id=str(row.get("id")) if row.get("id") is not None else None)
        except Exception:
            logger.exception("scheduled_search: per-schedule run crashed user=%s", user_id)
            failed += 1

    logger.info(
        "scheduled_search: sweep done searches=%d users=%d new=%d skipped=%d failed=%d dry_run=%s",
        len(rows), len(users), new_total, skipped, failed, dry_run,
    )
    return {"status": "ok", "searches": len(rows), "users": len(users),
            "new_results": new_total, "skipped": skipped, "failed": failed, "dry_run": dry_run}


# ── Chat handler (deterministic; no AI dependency) ───────────────────────────

def _profile_roles(profile: Any) -> List[str]:
    roles = None
    if isinstance(profile, dict):
        roles = profile.get("target_roles")
    else:
        roles = getattr(profile, "target_roles", None)
    if not isinstance(roles, (list, tuple)):
        return []
    return [str(r) for r in roles if r][:3]


def _fmt_schedule_line(sched: Dict[str, Any], arabic: bool) -> str:
    city = sched.get("city") or ("كل الإمارات" if arabic else "All UAE")
    salary = sched.get("min_salary_aed")
    if arabic:
        salary_part = f"براتب {salary:,}+ درهم" if salary else "بدون حد أدنى للراتب"
        state = "مفعّل" if sched.get("enabled") else "متوقف"
        return f"بحث يومي — {city} — {salary_part} — {state}"
    salary_part = f"AED {salary:,}+" if salary else "no salary minimum"
    state = "enabled" if sched.get("enabled") else "paused"
    return f"Daily search — {city} — {salary_part} — {state}"


def handle_chat_intent(user_id: str, intent: str, message: str, *, arabic: bool = False) -> Dict[str, Any]:
    """Deterministic chat entry point for the scheduled_search_* intents.

    Returns a structured chat response dict ({"type": "scheduled_search", ...});
    never raises. Public/guest identities are asked to sign in — schedules are
    an account feature (they run when the user is offline).
    """
    if _is_public_identity(user_id):
        msg = (
            "البحث المجدول ميزة للحسابات المسجلة — سجّل دخولك أولاً حتى أستطيع تشغيل البحث يوميًا وحفظ نتائجك."
            if arabic else
            "Scheduled searches are an account feature — please sign in so I can run your search daily and keep your results."
        )
        return {"type": "scheduled_search", "action": "signin_required", "message": msg}

    try:
        if intent == "scheduled_search_create":
            result = create_or_update_scheduled_search(user_id, message)
            if result is None or result.get("outcome") == "failed":
                msg = (
                    "لم أستطع حفظ البحث المجدول الآن — حاول مرة أخرى بعد قليل."
                    if arabic else
                    "I couldn't save that scheduled search right now — please try again shortly."
                )
                return {"type": "scheduled_search", "action": "create_failed", "message": msg}

            sched = result["schedule"]
            roles: List[str] = []
            try:
                from src.repositories.profile_repo import get_profile

                roles = _profile_roles(get_profile(user_id))
            except Exception:
                roles = []
            roles_part_ar = ("الأدوار من ملفك: " + "، ".join(roles)) if roles else "سأستهدف الأدوار المستخرجة من ملفك الشخصي"
            roles_part_en = ("Target roles from your profile: " + ", ".join(roles)) if roles else "I'll target the roles from your profile"
            if arabic:
                msg = (
                    f"تم! {_fmt_schedule_line(sched, True)}.\n"
                    f"{roles_part_ar}. النتائج ستظهر هنا داخل ريكو — "
                    "ولن أرسل بريدًا إلا إذا فعّلت تنبيهات البريد بنفسك. "
                    "يمكنك قول: أوقف البحث اليومي، أو احذف البحث اليومي، في أي وقت."
                )
            else:
                msg = (
                    f"Done! {_fmt_schedule_line(sched, False)}.\n"
                    f"{roles_part_en}. Results will appear here inside Rico — "
                    "no emails unless you explicitly enable email alerts. "
                    "You can say: pause my daily search, or delete my daily search, anytime."
                )
            return {
                "type": "scheduled_search",
                "action": result["outcome"],  # created | updated
                "message": msg,
                "schedule": {k: sched.get(k) for k in ("enabled", "cadence", "city", "min_salary_aed")},
                "query": result["query"],
            }

        if intent == "scheduled_search_status":
            items = get_user_schedules(user_id)
            if not items:
                msg = ("لا يوجد لديك بحث مجدول بعد. جرّب: ابحث يوميًا عن وظائف في دبي."
                       if arabic else
                       "You have no scheduled searches yet. Try: search daily for jobs in Dubai.")
                return {"type": "scheduled_search", "action": "status", "message": msg, "schedules": []}
            lines = [_fmt_schedule_line(i["schedule"], arabic) for i in items]
            last = items[0]["schedule"]
            results = last.get("last_results") or []
            if arabic:
                msg = "بحثك المجدول:\n" + "\n".join(f"• {ln}" for ln in lines)
                msg += f"\nآخر تشغيل: {last.get('last_run_at') or 'لم يعمل بعد'} — نتائج جديدة: {last.get('last_run_new', 0)}"
            else:
                msg = "Your scheduled searches:\n" + "\n".join(f"• {ln}" for ln in lines)
                msg += f"\nLast run: {last.get('last_run_at') or 'not run yet'} — new results: {last.get('last_run_new', 0)}"
            return {"type": "scheduled_search", "action": "status", "message": msg,
                    "schedules": items, "last_results": results[:MAX_RESULTS_PER_RUN]}

        if intent in ("scheduled_search_pause", "scheduled_search_resume"):
            enabled = intent.endswith("resume")
            n = set_schedules_enabled(user_id, enabled)
            if arabic:
                msg = ("تم استئناف البحث اليومي." if enabled else "تم إيقاف البحث اليومي مؤقتًا.") if n else "لا يوجد بحث مجدول لتغييره."
            else:
                msg = ("Your daily search is resumed." if enabled else "Your daily search is paused.") if n else "You have no scheduled search to change."
            return {"type": "scheduled_search",
                    "action": "resumed" if enabled else "paused", "message": msg, "affected": n}

        if intent == "scheduled_search_delete":
            n = delete_schedules(user_id)
            if arabic:
                msg = "تم حذف البحث المجدول." if n else "لا يوجد بحث مجدول لحذفه."
            else:
                msg = "Your scheduled search was deleted." if n else "You have no scheduled search to delete."
            return {"type": "scheduled_search", "action": "deleted", "message": msg, "affected": n}
    except Exception:
        logger.exception("scheduled_search: chat intent crashed user=%s intent=%s", user_id, intent)

    msg = ("حدث خطأ أثناء معالجة البحث المجدول — حاول مجددًا."
           if arabic else "Something went wrong handling that scheduled search — please try again.")
    return {"type": "scheduled_search", "action": "error", "message": msg}
