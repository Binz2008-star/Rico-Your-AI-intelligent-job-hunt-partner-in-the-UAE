"""
tests/unit/test_chat_followup_readiness.py

Phase 3 chat integration: "what should I follow up?" / "which jobs are due for
follow-up?" (EN + AR) list the applied jobs old enough to revisit, reusing the
merged #885 readiness logic (get_by_status + select_revisit_candidates).

Guards:
- Follow-up readiness phrases route to the readiness path (not job_search).
- Genuine follow-up TIMING questions still belong to the timing path only.
- Existing lifecycle phrases (applications list / saved / opened-not-applied)
  are not hijacked by the new readiness regex.
- Empty state is safe (no fake success).

DB is mocked — no live Neon connection opened.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import src.rico_chat_api as mod
from src.rico_chat_api import (
    RicoChatAPI,
    _FOLLOWUP_READINESS_RE,
    _FOLLOWUP_TIMING_RE,
    _APPLICATIONS_LIST_RE,
    _SAVED_JOBS_LIST_RE,
)

UTC = timezone.utc


# ── 1. classification: readiness phrases match the readiness regex ────────────

READINESS_PHRASES = [
    "what should I follow up?",
    "what should I follow up on?",
    "which jobs should I follow up on?",
    "which jobs are due for follow-up?",
    "what jobs need a follow up?",
    "show my follow-ups",
    "what are my follow ups?",
    "ما الوظائف التي يجب أن أتابعها؟",
    "أي وظائف يجب أن أتابعها",
    "وظائف تحتاج متابعة",
]


def test_readiness_phrases_match_readiness_regex():
    for p in READINESS_PHRASES:
        assert _FOLLOWUP_READINESS_RE.search(p), f"readiness regex should match: {p!r}"


# ── 2. no hijack: genuine TIMING questions do NOT match readiness ─────────────

TIMING_PHRASES = [
    "when should I follow up?",
    "how many days before following up?",
    "is it too early to follow up?",
    "how do I follow up?",
    "should I follow up with Emirates now?",
    "متى أتابع؟",
]


def test_timing_phrases_do_not_match_readiness_regex():
    for p in TIMING_PHRASES:
        assert not _FOLLOWUP_READINESS_RE.search(p), f"readiness must NOT swallow timing: {p!r}"
    # ...and they still belong to the timing path.
    for p in TIMING_PHRASES:
        assert _FOLLOWUP_TIMING_RE.search(p), f"timing regex should still match: {p!r}"


# ── 3. existing lifecycle routes remain unchanged ─────────────────────────────

def test_readiness_regex_does_not_hijack_existing_lifecycle_phrases():
    # Application list / saved-jobs phrases must not be captured by readiness.
    for p in ["what jobs did I apply to?", "show my applications", "list my applied jobs"]:
        assert not _FOLLOWUP_READINESS_RE.search(p), f"readiness must not steal: {p!r}"
        assert _APPLICATIONS_LIST_RE.search(p), f"applications-list regex should still match: {p!r}"
    for p in ["show my saved jobs", "my saved jobs"]:
        assert not _FOLLOWUP_READINESS_RE.search(p), f"readiness must not steal: {p!r}"
        assert _SAVED_JOBS_LIST_RE.search(p), f"saved-jobs regex should still match: {p!r}"


# ── 4. handler reuses readiness logic and is safe when empty ──────────────────

def _api():
    # Bypass the heavy constructor: the handler only needs _is_arabic_text.
    return RicoChatAPI.__new__(RicoChatAPI)


def _applied_row(title, company, days_ago):
    return {
        "title": title,
        "company": company,
        "status": "applied",
        "apply_url": f"https://careers.example.com/{title}",
        "source_url": f"https://jsearch.example/{title}",
        "applied_at": datetime.now(UTC) - timedelta(days=days_ago),
    }


def test_handler_lists_only_jobs_old_enough_to_revisit():
    rows = [
        _applied_row("Aged Role", "AESG", days_ago=10),     # ready (>= 7 days)
        _applied_row("Fresh Role", "G42", days_ago=1),      # too recent
    ]
    with patch("src.repositories.user_job_context_repo.get_by_status", return_value=rows):
        api = _api()
        resp = api._handle_followup_readiness("user:synthetic@example.com", "what should I follow up?")

    assert resp["type"] == "lifecycle_query"
    assert resp["intent"] == "lifecycle_show_followup_due"
    assert resp["count"] == 1
    assert resp["jobs"][0]["title"] == "Aged Role"
    assert resp["jobs"][0]["company"] == "AESG"
    assert resp["jobs"][0]["days_since_applied"] >= 7
    assert "Aged Role" in resp["message"] and "Fresh Role" not in resp["message"]


def test_handler_empty_state_is_safe():
    with patch("src.repositories.user_job_context_repo.get_by_status", return_value=[]):
        api = _api()
        resp = api._handle_followup_readiness("user:synthetic@example.com", "what should I follow up?")
    assert resp["count"] == 0
    assert resp["jobs"] == []
    assert "follow" in resp["message"].lower()  # a real, non-empty guidance message


def test_handler_arabic_empty_state_is_arabic():
    with patch("src.repositories.user_job_context_repo.get_by_status", return_value=[]):
        api = _api()
        resp = api._handle_followup_readiness("user:synthetic@example.com", "ما الوظائف التي يجب أن أتابعها؟")
    assert resp["count"] == 0
    assert "متابعة" in resp["message"]
