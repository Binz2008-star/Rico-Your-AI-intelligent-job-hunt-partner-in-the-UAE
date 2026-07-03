"""
tests/test_profile_query_intent.py

Regression tests for the self-profile attribute query intent (chat QA 2026-07-03,
TASK-20260703-038 / TC-11).

Covers:
  1. "what is my current role and years of experience" and variants route to
     profile_summary (a profile READ), not job search and not the ``unknown``
     fallback that previously flashed a search.
  2. Job-search / profile-match phrasing ("what jobs match my experience") is NOT
     captured by the profile-query path — the veto keeps it in search.
  3. Adjacent profile intents (profile_update) and the interview-prep path are not
     regressed.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


@pytest.fixture(scope="module")
def classify():
    from src.agent.intelligence.intent_classifier import classify_intent
    return classify_intent


@pytest.mark.parametrize("message", [
    "what is my current role and years of experience",
    "tell me my current role, years of experience, and skills",
    "how many years of experience do I have",
    "what is my position",
    "what's my seniority",
    "what do you know about my background",
])
def test_profile_queries_route_to_profile_summary(classify, message):
    result = classify(message, has_cv_profile=True)
    assert result.legacy_intent == "profile_summary", (
        f"{message!r} -> {result.legacy_intent} (expected profile_summary)"
    )


@pytest.mark.parametrize("message", [
    "what jobs match my experience",
    "positions that match my cv",
    "find operations manager jobs in dubai",
])
def test_job_search_phrasing_is_not_captured_as_profile_query(classify, message):
    result = classify(message, has_cv_profile=True)
    assert result.legacy_intent != "profile_summary", (
        f"{message!r} was wrongly captured as profile_summary"
    )


@pytest.mark.parametrize("message,expected", [
    ("update my role", "profile_update"),
    ("show my profile", "profile_summary"),
    ("prepare me for an interview for the Retail Operations Manager role at Richemont",
     "interview_prep"),
])
def test_adjacent_intents_not_regressed(classify, message, expected):
    result = classify(message, has_cv_profile=True)
    assert result.legacy_intent == expected, (
        f"{message!r} -> {result.legacy_intent} (expected {expected})"
    )
