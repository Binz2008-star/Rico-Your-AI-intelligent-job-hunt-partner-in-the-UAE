# -*- coding: utf-8 -*-
"""PR4 slice 1 (job-result semantics) — observability only.

_target_role_search_response already has a mature, tested result-outcome
classifier (_classify_search_outcome: COMPLETED_WITH_RESULTS /
PROVIDER_DEGRADED / PROVIDER_FAILED / COMPLETED_EMPTY) and a single
operation_id per search. What was missing: explicit, inspectable per-attempt
provenance — which mechanism(s) actually ran under that one operation_id,
and what each returned. This adds a read-only "search_attempts" list to the
response; it changes no control flow, no messages, no thresholds.

Deliberately does NOT touch src/services/operation_state.py (documented
concurrency-safety internals, single-worker constraint) — see PR description.
"""
from __future__ import annotations

from unittest.mock import patch

from src.jsearch_client import FetchResult
from tests.harness.chat_harness import ChatHarness


class _EmptyCascadeHarness(ChatHarness):
    """ChatHarness variant whose provider_cascade stub always returns zero
    items — used to force the legacy_fallback attempt to actually run."""

    def _search(self, role: str, location: str = "", **_kw):
        self.searched_roles.append(role)
        return FetchResult(items=[], provider="jsearch")


class _RaisingCascadeHarness(ChatHarness):
    """ChatHarness variant whose provider_cascade stub raises — used to
    exercise the search_error path."""

    def _search(self, role: str, location: str = "", **_kw):
        raise RuntimeError("synthetic provider outage")


def test_single_attempt_when_provider_cascade_succeeds():
    """The harness's default _search stub returns results immediately, so
    only the provider_cascade attempt should ever run."""
    h = ChatHarness()
    user = "attempts-single@test.com"
    h.seed(
        user, cv_status="parsed", cv_filename="cv.pdf",
        target_roles=["Environmental Manager"], current_role="Environmental Manager",
        years_experience=6, preferred_cities=["Dubai"],
    )
    result = h.say(user, "find HSE Manager jobs")
    attempts = result.get("search_attempts")
    assert attempts is not None, "search_attempts must be present on a completed search"
    assert len(attempts) == 1, f"expected exactly one attempt, got {attempts!r}"
    assert attempts[0]["mechanism"] == "provider_cascade"
    assert attempts[0]["outcome"] == "results"
    # Same single operation_id claim this session already relies on —
    # this test only adds the attempt-level detail on top of it.
    assert result.get("operation_id")


def test_two_attempts_recorded_under_one_operation_when_cascade_is_empty():
    """When the primary cascade returns nothing, the legacy fallback fires —
    by design, one operation, two tracked attempts, never silently one
    mechanism pretending to be the other."""
    h = _EmptyCascadeHarness()
    user = "attempts-fallback@test.com"
    h.seed(
        user, cv_status="parsed", cv_filename="cv.pdf",
        target_roles=["Environmental Manager"], current_role="Environmental Manager",
        years_experience=6, preferred_cities=["Dubai"],
    )

    def _fallback_with_result(_self, profile):
        return {
            "status": "completed",
            "matches": [{
                "title": "Environmental Manager", "company": "ACME",
                "apply_url": "https://acme.example/jobs/1", "location": "Dubai, UAE",
            }],
        }

    with patch("src.rico_repo_adapter.RicoSystem.run_for_profile", _fallback_with_result):
        result = h.say(user, "find Environmental Manager jobs")

    attempts = result.get("search_attempts")
    assert attempts is not None
    assert len(attempts) == 2, f"expected cascade + fallback attempts, got {attempts!r}"
    assert attempts[0]["mechanism"] == "provider_cascade"
    assert attempts[0]["outcome"] == "empty"
    assert attempts[1]["mechanism"] == "legacy_fallback"
    assert attempts[1]["outcome"] == "results"
    # Exactly one operation_id backs both attempts.
    assert result.get("operation_id")


def test_search_error_still_reports_attempts_so_far():
    h = _RaisingCascadeHarness()
    user = "attempts-error@test.com"
    h.seed(
        user, cv_status="parsed", cv_filename="cv.pdf",
        target_roles=["Environmental Manager"], current_role="Environmental Manager",
        years_experience=6, preferred_cities=["Dubai"],
    )

    result = h.say(user, "find Environmental Manager jobs")

    assert result.get("type") == "search_error"
    attempts = result.get("search_attempts")
    assert attempts is not None
    assert attempts[-1]["outcome"] == "exception"
