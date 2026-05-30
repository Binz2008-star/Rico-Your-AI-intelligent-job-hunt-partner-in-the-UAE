"""Tests for the Application Lifecycle feature.

Covers:
- src/job_lifecycle.py  — pure vocabulary / state-machine rules
- intent classifier lifecycle phrases and regex
- _handle_lifecycle_query response shape (mocked repo)

No DB, no network.
"""
from __future__ import annotations

import types
from unittest.mock import MagicMock, patch

import pytest

from src.job_lifecycle import (
    LIFECYCLE_STATUSES,
    is_valid_status,
    lifecycle_for_action,
    normalize_status,
    stamp_column_for_status,
)


# ── job_lifecycle.py ──────────────────────────────────────────────────────────

class TestJobLifecycleVocabulary:
    def test_all_required_statuses_present(self):
        required = {
            "found", "saved", "opened_external", "prepared",
            "applied", "interviewing", "offer", "rejected",
            "archived", "needs_review",
        }
        assert required.issubset(set(LIFECYCLE_STATUSES))

    def test_is_valid_status_true(self):
        for s in LIFECYCLE_STATUSES:
            assert is_valid_status(s), f"Expected {s!r} to be valid"

    def test_is_valid_status_false(self):
        assert not is_valid_status("unknown_stage")
        assert not is_valid_status("")
        assert not is_valid_status(None)

    def test_normalize_status_case_insensitive(self):
        assert normalize_status("APPLIED") == "applied"
        assert normalize_status("  Saved  ") == "saved"

    def test_normalize_status_unknown_returns_none(self):
        assert normalize_status("ghost") is None

    @pytest.mark.parametrize("action,expected_status,expected_col", [
        ("save",         "saved",           "saved_at"),
        ("open_apply",   "opened_external", "opened_at"),
        ("opened",       "opened_external", "opened_at"),
        ("prepare",      "prepared",        "prepared_at"),
        ("mark_applied", "applied",         "applied_at"),
        ("archive",      "archived",        None),
    ])
    def test_lifecycle_for_action(self, action, expected_status, expected_col):
        result = lifecycle_for_action(action)
        assert result is not None, f"Expected lifecycle mapping for {action!r}"
        status, col = result
        assert status == expected_status
        assert col == expected_col

    def test_lifecycle_for_unknown_action(self):
        assert lifecycle_for_action("why") is None
        assert lifecycle_for_action("block") is None

    @pytest.mark.parametrize("status,col", [
        ("saved",           "saved_at"),
        ("opened_external", "opened_at"),
        ("prepared",        "prepared_at"),
        ("applied",         "applied_at"),
        ("found",           None),
        ("interviewing",    None),
        ("rejected",        None),
    ])
    def test_stamp_column_for_status(self, status, col):
        assert stamp_column_for_status(status) == col


# ── Intent classifier lifecycle phrases ──────────────────────────────────────

from src.agent.intelligence.intent_classifier import classify_intent


class TestLifecycleIntentClassifier:
    @pytest.mark.parametrize("text,expected", [
        ("show my saved jobs",      "lifecycle_show_saved"),
        ("saved jobs",              "lifecycle_show_saved"),
        ("my saved jobs",           "lifecycle_show_saved"),
        ("jobs i applied to",       "lifecycle_show_applied"),
        ("what jobs did i apply to","lifecycle_show_applied"),
        ("show applied jobs",       "lifecycle_show_applied"),
        ("show jobs i opened but did not apply to", "lifecycle_show_opened_not_applied"),
        ("opened but not applied",  "lifecycle_show_opened_not_applied"),
    ])
    def test_exact_lifecycle_phrases(self, text, expected):
        result = classify_intent(text)
        assert result.intent == expected, (
            f"{text!r} → {result.intent!r}, expected {expected!r}"
        )

    @pytest.mark.parametrize("text,expected", [
        ("my saved jobs list",           "lifecycle_show_saved"),
        ("list my saved jobs",           "lifecycle_show_saved"),
        ("jobs I opened without applying", "lifecycle_show_opened_not_applied"),
    ])
    def test_regex_lifecycle_phrases(self, text, expected):
        result = classify_intent(text)
        assert result.intent == expected, (
            f"{text!r} → {result.intent!r}, expected {expected!r}"
        )


# ── _handle_lifecycle_query ───────────────────────────────────────────────────

from src.rico_chat_api import RicoChatAPI


_FAKE_JOBS = [
    {"title": "Systems Engineer", "company": "AESG", "apply_url": "https://a/1", "source_url": ""},
    {"title": "Data Analyst", "company": "Mott MacDonald", "apply_url": "", "source_url": "https://s/2"},
]


class TestHandleLifecycleQuery:
    def _api(self):
        api = RicoChatAPI.__new__(RicoChatAPI)
        api.memory = MagicMock()
        api.memory.get_context.return_value = {}
        api.memory.set_context.return_value = None
        return api

    def test_show_saved_with_results(self):
        api = self._api()
        with patch("src.repositories.user_job_context_repo.get_by_status", return_value=_FAKE_JOBS):
            resp = api._handle_lifecycle_query("user@test.com", "lifecycle_show_saved")
        assert resp["count"] == 2
        assert "saved" in resp["message"].lower()
        assert "Systems Engineer" in resp["message"]

    def test_show_applied_empty(self):
        api = self._api()
        with patch("src.repositories.user_job_context_repo.get_by_status", return_value=[]):
            resp = api._handle_lifecycle_query("user@test.com", "lifecycle_show_applied")
        assert resp["count"] == 0
        assert "don't have" in resp["message"].lower() or "no jobs" in resp["message"].lower() or "haven't" in resp["message"].lower() or "don't" in resp["message"].lower()

    def test_show_opened_not_applied(self):
        api = self._api()
        with patch("src.repositories.user_job_context_repo.get_opened_not_applied", return_value=_FAKE_JOBS):
            resp = api._handle_lifecycle_query("user@test.com", "lifecycle_show_opened_not_applied")
        assert resp["type"] == "lifecycle_query"
        assert resp["count"] == 2

    def test_response_shape(self):
        api = self._api()
        with patch("src.repositories.user_job_context_repo.get_by_status", return_value=_FAKE_JOBS):
            resp = api._handle_lifecycle_query("user@test.com", "lifecycle_show_saved")
        assert "type" in resp
        assert "message" in resp
        assert "jobs" in resp
        assert "count" in resp
