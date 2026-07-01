"""src/services/email_alert_service.py
Personalized job-alert emails for Rico (PR-2 sender).

Entry point for the cron-guarded POST /api/v1/pipeline/job-alert-emails sweep.
For each opted-in user it:
  1. loads the profile,
  2. finds matches via the existing match engine (RicoSystem.run_for_profile),
  3. drops jobs the user already applied to / saved / skipped / blocked and any
     job already emailed to them (email_alert_log dedup),
  4. keeps the top MAX_JOBS above the fit threshold,
  5. sends ONE digest email if there are at least MIN_JOBS strong matches,
  6. logs each emailed job so it never repeats, and respects a per-user
     daily/weekly frequency cap.

Safety:
  - Gated behind opt-in (default off) AND the RICO_ENABLE_EMAIL_ALERTS kill-switch.
  - Never emails synthetic/internal accounts (_is_synthetic_email).
  - Only includes jobs with a real destination link.
  - No CV text or PII in the body — only public listing fields + a one-line reason.
  - Every email carries a login-free unsubscribe link.
  - Never raises: failures are logged and counted in the run summary.
"""
from __future__ import annotations

import html as _html
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Tunables (env-overridable, sensible defaults for the MVP).
MIN_JOBS = int(os.getenv("RICO_EMAIL_ALERT_MIN_JOBS", "3"))
MAX_JOBS = int(os.getenv("RICO_EMAIL_ALERT_MAX_JOBS", "5"))
DEFAULT_MIN_SCORE = int(os.getenv("RICO_EMAIL_ALERT_MIN_SCORE", "50"))
MAX_USERS_PER_RUN = int(os.getenv("RICO_EMAIL_ALERT_MAX_USERS", "500"))
# Frequency windows (days). A daily user is skipped if emailed within the last
# ~1 day; a weekly user within the last ~7 days (6 to tolerate cron jitter).
_FREQ_WINDOW_DAYS = {"daily": 1, "weekly": 6}

_APP_BASE_URL = os.getenv("RESET_BASE_URL", "https://ricohunt.com").rstrip("/")
_API_BASE_URL = os.getenv("RICO_PUBLIC_API_URL", _APP_BASE_URL).rstrip("/")


def _enabled() -> bool:
    """Kill-switch: sending is off unless RICO_ENABLE_EMAIL_ALERTS is truthy."""
    return os.getenv("RICO_ENABLE_EMAIL_ALERTS", "false").strip().lower() in {"1", "true", "yes", "on"}


# ── Matching ──────────────────────────────────────────────────────────────────

def _excluded_job_keys(user_id: str) -> set[str]:
    """(title|company) keys the user already acted on — applied/saved/skipped/blocked."""
    try:
        from src.repositories import user_job_context_repo as ujc

        rows = ujc.get_by_status(user_id, ["applied", "saved", "skipped", "blocked"], limit=200)
    except Exception:
        logger.debug("email_alert: excluded-keys lookup failed user=%s", user_id, exc_info=True)
        rows = []
    keys = set()
    for r in rows:
        t = (r.get("title") or "").strip().lower()
        c = (r.get("company") or "").strip().lower()
        if t and c:
            keys.add(f"{t}|{c}")
    return keys


def _match_link(job: Dict[str, Any]) -> str:
    for k in ("link", "apply_link", "url", "alt_link"):
        v = (job.get(k) or "").strip()
        if v:
            return v
    return ""


def _find_matches(profile: Any, user_id: str) -> List[Dict[str, Any]]:
    """Return de-duplicated, above-threshold matches for a user, best first.

    Reuses the existing match engine (search + score + remove-applied). Returns
    at most MAX_JOBS jobs, each with a real destination link.
    """
    try:
        from src.rico_repo_adapter import RicoSystem
        from src.services.email_notifications import was_email_alert_sent
        from src.applications import get_job_id
    except Exception:
        logger.exception("email_alert: match engine import failed user=%s", user_id)
        return []

    try:
        # Pull a wider window than MAX_JOBS so exclusions still leave enough.
        result = RicoSystem().run_for_profile(profile, limit=MAX_JOBS * 3)
    except Exception:
        logger.exception("email_alert: run_for_profile failed user=%s", user_id)
        return []

    if not isinstance(result, dict) or result.get("status") != "completed":
        return []

    excluded = _excluded_job_keys(user_id)
    threshold = _min_score_for(user_id)
    picked: List[Dict[str, Any]] = []
    seen_keys: set[str] = set()

    for m in result.get("matches") or []:
        if len(picked) >= MAX_JOBS:
            break
        title = (m.get("title") or "").strip()
        company = (m.get("company") or "").strip()
        link = _match_link(m)
        if not title or not company or not link:
            continue  # never advertise a job with no real destination
        if int(m.get("score") or 0) < threshold:
            continue
        pair_key = f"{title.lower()}|{company.lower()}"
        if pair_key in excluded or pair_key in seen_keys:
            continue
        job_key = get_job_id({"title": title, "company": company,
                              "location": m.get("location") or "", "link": link})
        if was_email_alert_sent(user_id, job_key):
            continue  # already emailed this job to this user
        seen_keys.add(pair_key)
        picked.append({
            "title": title,
            "company": company,
            "location": (m.get("location") or "").strip(),
            "score": int(m.get("score") or 0),
            "link": link,
            "why": (m.get("rico_explanation") or m.get("profile_explanation") or "").strip(),
            "job_key": job_key,
        })
    return picked


def _min_score_for(user_id: str) -> int:
    try:
        from src.services.settings_service import get_settings

        s = get_settings(user_id=user_id) or {}
        return int(s.get("score_threshold_watch") or s.get("min_score") or DEFAULT_MIN_SCORE)
    except Exception:
        return DEFAULT_MIN_SCORE


# ── Rendering ─────────────────────────────────────────────────────────────────

def _display_name(name: Optional[str], email: str) -> str:
    return name.strip() if name and name.strip() else email.split("@")[0]


def _unsubscribe_url(token: Optional[str]) -> str:
    if not token:
        return f"{_APP_BASE_URL}/settings"
    return f"{_API_BASE_URL}/api/v1/email/unsubscribe?token={token}"


def _subject(jobs: List[Dict[str, Any]]) -> str:
    n = len(jobs)
    # Prefer the top job's city for a concrete, non-spammy subject.
    city = ""
    for j in jobs:
        loc = j.get("location") or ""
        if loc:
            city = loc.split(",")[0].strip()
            break
    if city:
        return f"Rico found {n} new job match{'es' if n != 1 else ''} in {city}"
    return f"Rico found {n} new job match{'es' if n != 1 else ''} for you"


def render_email(
    *,
    name: Optional[str],
    email: str,
    jobs: List[Dict[str, Any]],
    unsubscribe_token: Optional[str],
) -> tuple[str, str, str]:
    """Return (subject, text_body, html_body) for a digest of *jobs*."""
    subject = _subject(jobs)
    greeting = f"Hi {_display_name(name, email)},"
    unsubscribe = _unsubscribe_url(unsubscribe_token)
    jobs_url = f"{_APP_BASE_URL}/jobs"

    # ── Plain text ──
    text_lines = [greeting, "", "Here are your top job matches:", ""]
    for i, j in enumerate(jobs, 1):
        line = f"{i}. {j['title']} — {j['company']}"
        if j.get("location"):
            line += f" · {j['location']}"
        if j.get("score"):
            line += f" · Match {j['score']}%"
        text_lines.append(line)
        if j.get("why"):
            text_lines.append(f"   Why: {j['why']}")
        text_lines.append(f"   View: {j['link']}")
        text_lines.append("")
    text_lines += [
        f"See all matches: {jobs_url}",
        "",
        "You're receiving this because you enabled job alerts in Rico.",
        f"Unsubscribe: {unsubscribe}",
    ]
    text_body = "\n".join(text_lines)

    # ── HTML ──
    def esc(s: str) -> str:
        return _html.escape(s or "")

    cards = []
    for i, j in enumerate(jobs, 1):
        meta = " · ".join(
            filter(None, [esc(j.get("location") or ""),
                          f"Match {j['score']}%" if j.get("score") else ""])
        )
        why = (
            f"<div style='color:#4b5563;font-size:14px;margin:6px 0'>{esc(j['why'])}</div>"
            if j.get("why") else ""
        )
        cards.append(
            "<div style='border:1px solid #e5e7eb;border-radius:10px;padding:16px;margin:0 0 12px'>"
            f"<div style='font-weight:600;font-size:16px;color:#111827'>{i}. {esc(j['title'])}</div>"
            f"<div style='color:#374151;font-size:14px;margin-top:2px'>{esc(j['company'])}</div>"
            + (f"<div style='color:#6b7280;font-size:13px;margin-top:2px'>{meta}</div>" if meta else "")
            + why
            + "<div style='margin-top:10px'>"
            f"<a href='{esc(j['link'])}' style='display:inline-block;background:#2563eb;color:#fff;"
            "text-decoration:none;font-size:14px;padding:8px 14px;border-radius:8px'>View job &rarr;</a>"
            "</div></div>"
        )

    html_body = (
        "<!doctype html><html><body style='margin:0;background:#f9fafb;"
        "font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#111827'>"
        "<div style='max-width:560px;margin:0 auto;padding:24px'>"
        f"<h1 style='font-size:20px;margin:0 0 4px'>{esc(greeting)}</h1>"
        "<p style='color:#4b5563;font-size:15px;margin:0 0 20px'>Here are your top job matches:</p>"
        + "".join(cards)
        + f"<p style='margin:20px 0 0'><a href='{esc(jobs_url)}' "
        "style='color:#2563eb;text-decoration:none;font-weight:600'>See all matches &rarr;</a></p>"
        "<hr style='border:none;border-top:1px solid #e5e7eb;margin:24px 0 12px'>"
        "<p style='color:#9ca3af;font-size:12px;line-height:1.5'>You're receiving this because you "
        "enabled job alerts in Rico.<br>"
        f"<a href='{esc(unsubscribe)}' style='color:#9ca3af'>Unsubscribe</a></p>"
        "</div></body></html>"
    )
    return subject, text_body, html_body


# ── Sending ───────────────────────────────────────────────────────────────────

def send_alert_email(
    user: Dict[str, Any],
    *,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Build and (unless dry_run) send one digest email for a single user.

    *user* is a roster dict: external_user_id, name, email, email_alert_frequency.
    Returns a per-user outcome dict: {status, jobs, ...}. Never raises.
    """
    from src.services.email_notifications import (
        emailed_within_days,
        ensure_unsubscribe_token,
        log_email_alert,
    )
    from src.services.profile_nudge_service import _is_synthetic_email
    from src.repositories.profile_repo import get_profile

    user_id = user.get("external_user_id") or ""
    email = (user.get("email") or "").strip()
    name = user.get("name")
    frequency = (user.get("email_alert_frequency") or "daily").strip().lower()

    if not user_id or not email:
        return {"status": "skipped_no_identity", "jobs": 0}
    if _is_synthetic_email(email):
        return {"status": "skipped_synthetic", "jobs": 0}

    # Frequency cap — skip if we already emailed within the cadence window.
    window = _FREQ_WINDOW_DAYS.get(frequency, 1)
    if emailed_within_days(user_id, window):
        return {"status": "skipped_frequency", "jobs": 0}

    profile = get_profile(user_id)
    if not profile:
        return {"status": "skipped_no_profile", "jobs": 0}

    jobs = _find_matches(profile, user_id)
    if len(jobs) < MIN_JOBS:
        # No strong matches → don't send (avoids spammy/empty emails).
        return {"status": "skipped_no_matches", "jobs": len(jobs)}

    if dry_run:
        return {"status": "would_send", "jobs": len(jobs)}

    token = ensure_unsubscribe_token(user_id)
    subject, text_body, html_body = render_email(
        name=name, email=email, jobs=jobs, unsubscribe_token=token
    )

    from src.services.mailer import send_email

    ok = send_email(to_email=email, subject=subject, body=text_body, html=html_body)
    if not ok:
        return {"status": "send_failed", "jobs": len(jobs)}

    for j in jobs:
        log_email_alert(user_id, j["job_key"])
    logger.info("email_alert: sent user=%s jobs=%d", user_id, len(jobs))
    return {"status": "sent", "jobs": len(jobs)}


def run_email_alert_sweep(*, dry_run: bool = False) -> Dict[str, Any]:
    """Send digest emails to all opted-in users. Cron entry point.

    Returns a summary dict. Honors the RICO_ENABLE_EMAIL_ALERTS kill-switch
    (dry_run bypasses the switch so a dispatch smoke can validate matching
    without actually sending). Never raises.
    """
    if not dry_run and not _enabled():
        logger.info("email_alert: disabled (RICO_ENABLE_EMAIL_ALERTS not set) — no send")
        return {"status": "disabled", "users": 0, "sent": 0, "skipped": 0, "failed": 0}

    try:
        from src.repositories.profile_repo import get_users_with_email_alerts

        users = get_users_with_email_alerts()
    except Exception:
        logger.exception("email_alert: roster lookup failed")
        return {"status": "error", "users": 0, "sent": 0, "skipped": 0, "failed": 0}

    users = users[:MAX_USERS_PER_RUN]
    sent = skipped = failed = 0
    for u in users:
        try:
            outcome = send_alert_email(u, dry_run=dry_run)
        except Exception:
            logger.exception("email_alert: per-user send crashed user=%s", u.get("external_user_id"))
            failed += 1
            continue
        status = outcome.get("status", "")
        if status in {"sent", "would_send"}:
            sent += 1
        elif status in {"send_failed"}:
            failed += 1
        else:
            skipped += 1

    logger.info(
        "email_alert: sweep done users=%d sent=%d skipped=%d failed=%d dry_run=%s",
        len(users), sent, skipped, failed, dry_run,
    )
    return {
        "status": "ok",
        "users": len(users),
        "sent": sent,
        "skipped": skipped,
        "failed": failed,
        "dry_run": dry_run,
    }
