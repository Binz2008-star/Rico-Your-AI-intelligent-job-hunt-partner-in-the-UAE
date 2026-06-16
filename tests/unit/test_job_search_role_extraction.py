# -*- coding: utf-8 -*-
"""
Tests for job-search role extraction in natural word order (English + Arabic).

Bug: classify_intent only extracted a role from the "jobs for <role>" word order
(_JOB_SEARCH_FOR_ROLE_RE) and, for Arabic, only a trailing *English* role. So the very
common phrasings users actually type —

    "find operations manager jobs in ajman"   (English, role before the noun)
    "ابحث عن وظيفة مدير عمليات في عجمان"        (pure Arabic role)

extracted no role and the handler fell back to the profile's saved target_roles, returning
the wrong jobs (e.g. HSE Manager results for an Operations Manager search).

Fix:
- H1: _extract_role_before_noun captures "<role> jobs/roles/positions" and strips leading
  command/filler words.
- H2: _extract_arabic_role captures a pure-Arabic role after a job noun / "عن", before
  "في/بـ <city>" or end.

Both are additive — they only populate extracted_role where it was previously None, so
generic searches ("find me jobs") and the existing "jobs for <role>" path are unchanged.
"""
from __future__ import annotations

import pytest

from src.agent.intelligence.intent_classifier import (
    classify_intent,
    _extract_arabic_role,
    _extract_role_before_noun,
)


def _role(message: str):
    r = classify_intent(message, has_cv_profile=True)
    return r.legacy_intent, r.extracted_role


# ── H1: English "<role> jobs" word order ──────────────────────────────────────

@pytest.mark.parametrize("message,expected_role", [
    ("find operations manager jobs in ajman", "operations manager"),
    ("show me HSE manager roles", "HSE manager"),
    ("any nursing positions", "nursing"),
    ("find marketing jobs", "marketing"),
    ("looking for accountant jobs in dubai", "accountant"),
    ("search electrical engineer vacancies", "electrical engineer"),
    ("get me sales executive openings", "sales executive"),
])
def test_english_role_before_noun_is_extracted(message, expected_role):
    intent, role = _role(message)
    assert intent == "job_search_explicit"
    assert role == expected_role


@pytest.mark.parametrize("message", [
    "find me jobs",
    "show jobs",
    "find a job",
    "any jobs please",
    "find jobs in dubai",   # city is not a role
    "i need a job",
    "am looking for job",
    "i am looking for a job",
])
def test_generic_search_extracts_no_role(message):
    """Generic searches must still fall back to profile roles (extracted_role None)."""
    intent, role = _role(message)
    assert intent == "job_search_explicit"
    assert role is None


def test_jobs_for_role_word_order_still_wins():
    """The existing "jobs for <role>" extraction must be unchanged."""
    intent, role = _role("find jobs for Environmental Compliance Officer")
    assert intent == "job_search_explicit"
    assert role == "Environmental Compliance Officer"


def test_extract_role_before_noun_helper():
    assert _extract_role_before_noun("find operations manager jobs in ajman") == "operations manager"
    assert _extract_role_before_noun("any nursing positions") == "nursing"
    # Filler-heavy leads (contractions / extra verbs) are stripped down to the role.
    # NOTE: end-to-end these depend on _JOB_SEARCH_EXPLICIT_RE also recognising the verb;
    # the helper itself strips them regardless.
    assert _extract_role_before_noun("i'm searching for accountant jobs") == "accountant"
    assert _extract_role_before_noun("currently seeking marketing roles") == "marketing"
    # Nothing meaningful left after stripping command/filler words.
    assert _extract_role_before_noun("find me jobs") is None
    assert _extract_role_before_noun("am looking for job") is None
    assert _extract_role_before_noun("i am looking for a job") is None
    assert _extract_role_before_noun("show jobs") is None
    # No job noun at all.
    assert _extract_role_before_noun("hello there") is None


def test_application_tracking_not_misread_as_role_search():
    """'show my applications' has no job noun → must not become a role search."""
    intent, role = _role("show my applications")
    assert intent != "job_search_explicit"
    assert role is None


# ── H2: pure-Arabic role extraction ───────────────────────────────────────────

@pytest.mark.parametrize("message,expected_role", [
    # Known roles are translated to English via _ARABIC_TO_ENGLISH_ROLE_MAP so
    # the JSearch pipeline receives a recognisable English title.
    ("ابحث عن وظيفة مدير عمليات في عجمان", "Operations Manager"),
    ("ابحث عن مدير عمليات في عجمان", "Operations Manager"),
    ("اريد وظائف محاسب في دبي", "Accountant"),
    # "مصمم جرافيك" is not in the map → returned as-is in Arabic.
    ("ابحث عن وظيفة مصمم جرافيك في الشارقة", "مصمم جرافيك"),
])
def test_arabic_role_is_extracted(message, expected_role):
    intent, role = _role(message)
    assert intent == "job_search_explicit"
    assert role == expected_role


def test_mixed_language_falls_back_to_english_role():
    """Arabic request verb + English role still extracts the English role."""
    intent, role = _role("دور لي safety officer")
    assert intent == "job_search_explicit"
    assert role == "safety officer"


@pytest.mark.parametrize("message", [
    "ابحث عن وظيفة",        # "looking for a job" — no role named
    "ابحث عن عمل في دبي",   # "looking for work in Dubai" — no role named
])
def test_arabic_generic_search_extracts_no_role(message):
    intent, role = _role(message)
    assert intent == "job_search_explicit"
    assert role is None


def test_extract_arabic_role_helper():
    # Operates on normalised Arabic text (ة already folded to ه by the caller).
    assert _extract_arabic_role("ابحث عن وظيفه مدير عمليات في عجمان") == "مدير عمليات"
    assert _extract_arabic_role("اريد وظائف محاسب في دبي") == "محاسب"
    # Job word only, no role → None.
    assert _extract_arabic_role("ابحث عن عمل في دبي") is None
