"""tests/unit/test_intent_classifier.py

Tests for deterministic command/action routing in the intent classifier.

Phase 1 focus: application ownership phrases, profile/CV commands, and the
help menu must never fall through to job-role extraction or job search.

Acceptance criteria from the PR:
  - "show my job applications and their status" → application_tracking, not job search
  - "show my applications"                      → application_tracking
  - "list my applications status"               → application_tracking
  - "how many applied jobs do I have?"          → application_tracking
  - "my profile"                                → profile_summary
  - "my CV"                                     → profile_summary
  - "my jobs"                                   → application_tracking, not job search
  - "show my pipeline"                          → application_tracking, not job search
  - "open applications"                         → application_tracking
  - No response should trigger role-search for "my"
"""
from __future__ import annotations

import pytest

from src.agent.intelligence.intent_classifier import classify_intent, IntentResult

# ── Helpers ───────────────────────────────────────────────────────────────────

JOB_SEARCH_INTENTS = {"job_search_explicit", "job_search_profile_match", "role_change"}


def _intent(phrase: str, *, has_cv: bool = False) -> str:
    return classify_intent(phrase, has_cv_profile=has_cv).intent


def _is_job_search(phrase: str, *, has_cv: bool = False) -> bool:
    return _intent(phrase, has_cv=has_cv) in JOB_SEARCH_INTENTS


# ── show_applications ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("phrase", [
    "show my applications",
    "show my application",
    "list my applications",
    "view my applications",
    "see my applications",
    "display my applications",
    "check my applications",
    "track my applications",
    "my applications",
    "my application",
    # Key acceptance-test phrases from PR
    "show my job applications",
    "show my job applications and their status",
    "list my job applications",
    "my job applications",
    "open applications",
    "applications this month",
    "how many applications do i have",
])
def test_application_phrases_route_to_tracking(phrase):
    """Application ownership phrases must always route to application_tracking."""
    result = classify_intent(phrase)
    assert result.intent == "application_tracking", (
        f"Expected application_tracking for {phrase!r}, got {result.intent!r}"
    )
    assert not _is_job_search(phrase), (
        f"'{phrase}' must not trigger job search"
    )


# ── application_status / count ─────────────────────────────────────────────

@pytest.mark.parametrize("phrase", [
    "application status",
    "applications status",
    "list my applications status",
    "how many applied jobs do i have",
    "how many applied jobs do i have?",
    "how many applications do i have?",
])
def test_application_status_phrases_route_to_tracking(phrase):
    """Status/count queries about applications must route to application_tracking."""
    result = classify_intent(phrase)
    assert result.intent == "application_tracking", (
        f"Expected application_tracking for {phrase!r}, got {result.intent!r}"
    )


# ── show_profile ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("phrase", [
    "my profile",
    "show my profile",
    "profile summary",
    "what do you know about me",
    "my details",
])
def test_profile_phrases_route_to_profile_summary(phrase):
    """Profile ownership phrases must route to profile_summary."""
    result = classify_intent(phrase)
    assert result.intent == "profile_summary", (
        f"Expected profile_summary for {phrase!r}, got {result.intent!r}"
    )
    assert not _is_job_search(phrase), (
        f"'{phrase}' must not trigger job search"
    )


# ── show_cv ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("phrase", [
    "my cv",
    "show my cv",
    "view my cv",
    "see my cv",
    "my resume",
    "show my resume",
    "view my resume",
])
def test_cv_phrases_route_to_profile_summary(phrase):
    """CV show commands must route to profile_summary, not job search."""
    result = classify_intent(phrase)
    assert result.intent == "profile_summary", (
        f"Expected profile_summary for {phrase!r}, got {result.intent!r}"
    )
    assert not _is_job_search(phrase), (
        f"'{phrase}' must not trigger job search"
    )


# ── show_saved_jobs / my jobs ─────────────────────────────────────────────────

@pytest.mark.parametrize("phrase", [
    "my jobs",
    "show my jobs",
    "list my jobs",
])
def test_my_jobs_routes_to_tracking_not_search(phrase):
    """'my jobs' ownership phrases must not trigger job-role search."""
    result = classify_intent(phrase)
    assert result.intent == "application_tracking", (
        f"Expected application_tracking for {phrase!r}, got {result.intent!r}"
    )
    assert not _is_job_search(phrase), (
        f"'{phrase}' must not trigger job search"
    )


# ── show_my_pipeline ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("phrase", [
    "my pipeline",
    "show my pipeline",
    "application pipeline",
])
def test_pipeline_phrases_route_to_tracking(phrase):
    """'my pipeline' / 'show my pipeline' must not become job-role search."""
    result = classify_intent(phrase)
    assert result.intent == "application_tracking", (
        f"Expected application_tracking for {phrase!r}, got {result.intent!r}"
    )
    assert not _is_job_search(phrase), (
        f"'{phrase}' must not trigger job search"
    )


# ── help_menu ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("phrase", [
    "help",
    "menu",
    "options",
    "what can you do",
    "what can you do for me",
    "what can you help me with",
    "how can you help",
    "how can you help me",
    "what do you do",
    "commands",
    "start",
])
def test_help_phrases_route_to_help(phrase):
    """Help/menu commands must always route to help, never to job search."""
    result = classify_intent(phrase)
    assert result.intent == "help", (
        f"Expected help for {phrase!r}, got {result.intent!r}"
    )


# ── Anti-loop: "my" is never a job role ────────────────────────────────────

@pytest.mark.parametrize("phrase", [
    "my profile",
    "my cv",
    "my jobs",
    "my applications",
    "my pipeline",
    "my resume",
])
def test_ownership_word_never_triggers_job_search(phrase):
    """No phrase containing only 'my' + noun should become a job-role search."""
    result = classify_intent(phrase)
    assert result.intent not in JOB_SEARCH_INTENTS, (
        f"'{phrase}' must not trigger job search (got intent={result.intent!r})"
    )
    assert result.extracted_role is None or result.extracted_role.lower() != "my", (
        f"'{phrase}' must not extract 'my' as a job role"
    )


# ── Non-regression: real job role searches still route to job search ──────────

@pytest.mark.parametrize("phrase", [
    # These must match _JOB_SEARCH_EXPLICIT_RE (verb + job noun)
    "find HSE Manager jobs",
    "find me jobs for Environmental Compliance Officer",
    "search for Safety Officer roles in Dubai",
    "any operations manager positions",
    "show me safety engineer roles",
    "looking for project manager jobs",
])
def test_real_job_role_searches_still_route_to_job_search(phrase):
    """Explicit role-search phrases must still reach job-search handlers.

    Note: bare role names ('HSE Manager' alone) return 'unknown' from the
    classifier — the chat API's bare-role handler deals with them separately.
    Only phrases with an explicit verb + job noun trigger job_search_explicit.
    """
    result = classify_intent(phrase, has_cv_profile=True)
    assert result.intent in JOB_SEARCH_INTENTS, (
        f"Expected job search intent for {phrase!r}, got {result.intent!r}"
    )


# ── Non-regression: "open applications" ──────────────────────────────────────

def test_open_applications_routes_to_tracking():
    """'open applications' is an exact phrase in _APPLICATION_TRACKING_PHRASES."""
    result = classify_intent("open applications")
    assert result.intent == "application_tracking"


# ── Case insensitivity ────────────────────────────────────────────────────────

@pytest.mark.parametrize("phrase", [
    "Show My Job Applications And Their Status",
    "MY JOBS",
    "SHOW MY PIPELINE",
    "LIST MY APPLICATIONS STATUS",
    "My CV",
    "MY PROFILE",
])
def test_ownership_commands_are_case_insensitive(phrase):
    """Ownership commands must route correctly regardless of capitalisation."""
    result = classify_intent(phrase)
    assert result.intent in ("application_tracking", "profile_summary"), (
        f"Expected tracking/profile for {phrase!r}, got {result.intent!r}"
    )
    assert not _is_job_search(phrase), (
        f"'{phrase}' must not trigger job search"
    )


# ── Source and confidence ─────────────────────────────────────────────────────

def test_exact_phrase_has_high_confidence():
    """Exact-phrase matches must return confidence 1.0 and source 'exact'."""
    result = classify_intent("show my applications")
    assert result.source == "exact"
    assert result.confidence == 1.0


def test_regex_match_has_high_confidence():
    """Ownership regex matches should return confidence >= 0.9."""
    result = classify_intent("show my job applications and their status")
    assert result.confidence >= 0.9


def test_intent_result_is_frozen():
    """IntentResult must be immutable (frozen dataclass)."""
    result = classify_intent("my jobs")
    with pytest.raises((AttributeError, TypeError)):
        result.intent = "something_else"  # type: ignore[misc]
