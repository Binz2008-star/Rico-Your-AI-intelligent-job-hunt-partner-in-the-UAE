"""
Tests for context grounding / match rehydration (active application context).

Scenarios covered:
1. Numeric choice on a VISIBLE match set → job_selection response
2. Numeric choice on a STALE match set → rehydration (job_matches re-display)
3. Numeric choice out of range → clarification
4. Numeric choice with no match set → falls through (None)
5. Constraint update on active context: "don't set as favorite"
6. _increment_match_set_turn bumps staleness counter
7. "what were we talking about" context message includes selected job
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.rico_chat_api import RicoChatAPI


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_api() -> RicoChatAPI:
    api = RicoChatAPI.__new__(RicoChatAPI)
    api._persist = False
    api.memory = MagicMock()
    api.memory.append_chat_message = MagicMock()
    api._context_store: dict[str, dict] = {}
    return api


def _mock_context(api: RicoChatAPI, user_id: str, **fields: Any) -> None:
    api._context_store[user_id] = dict(fields)


def _get_context(api: RicoChatAPI, user_id: str) -> dict:
    return api._context_store.get(user_id, {})


def _patch_context(api: RicoChatAPI) -> None:
    """Replace get/store context so they use in-memory dict."""
    api._get_recent_context = lambda uid: api._context_store.get(uid, {})  # type: ignore[assignment]
    api._store_recent_context = lambda uid, ctx: api._context_store.update({uid: ctx})  # type: ignore[assignment]


SAMPLE_MATCHES = [
    {
        "title": "HSE Manager",
        "company": "ACME",
        "location": "Dubai, UAE",
        "salary": "25000 AED",
        "apply_url": "https://example.test/apply1",
        "source_url": "",
        "verification_status": "live",
    },
    {
        "title": "Environmental Compliance Officer",
        "company": "EnviroGroup",
        "location": "Abu Dhabi, UAE",
        "salary": "",
        "apply_url": "https://example.test/apply2",
        "source_url": "",
        "verification_status": "lead_needs_verification",
    },
]


# ── _is_numeric_choice ────────────────────────────────────────────────────────

class TestIsNumericChoice:
    @pytest.mark.parametrize("msg", ["1", "2", "3rd", "1st", "2nd", " 1 ", "9th"])
    def test_true_for_ordinals(self, msg):
        assert RicoChatAPI._is_numeric_choice(msg) is True

    @pytest.mark.parametrize("msg", ["10", "0", "yes", "hse manager", "find jobs", "1 please"])
    def test_false_for_non_ordinals(self, msg):
        assert RicoChatAPI._is_numeric_choice(msg) is False


# ── _resolve_numeric_choice ───────────────────────────────────────────────────

class TestResolveNumericChoice:
    def setup_method(self):
        self.api = _make_api()
        _patch_context(self.api)
        self.uid = "test-user"

    def _load_visible_matches(self):
        _mock_context(
            self.api, self.uid,
            recent_search_matches=SAMPLE_MATCHES,
            recent_search_role="HSE Manager",
            active_match_set_turn=0,
        )

    def _load_stale_matches(self):
        _mock_context(
            self.api, self.uid,
            recent_search_matches=SAMPLE_MATCHES,
            recent_search_role="HSE Manager",
            active_match_set_turn=5,  # beyond _MATCH_VISIBILITY_TURNS=3
        )

    def test_visible_match_set_returns_job_selection(self):
        self._load_visible_matches()
        result = self.api._resolve_numeric_choice(self.uid, "1", None)
        assert result is not None
        assert result["type"] == "job_selection"
        assert result["selected_match_number"] == 1
        assert result["selected_job"]["title"] == "HSE Manager"

    def test_job_selection_stores_active_context(self):
        self._load_visible_matches()
        self.api._resolve_numeric_choice(self.uid, "1", None)
        ctx = _get_context(self.api, self.uid)
        active = ctx.get("active_application_context")
        assert active is not None
        assert active["title"] == "HSE Manager"
        assert active["company"] == "ACME"
        assert active["favorite"] is True
        assert active["approval_to_prepare"] is False
        assert active["next_step"] == "confirm_or_prepare"

    def test_stale_match_set_rehydrates(self):
        self._load_stale_matches()
        result = self.api._resolve_numeric_choice(self.uid, "1", None)
        assert result is not None
        assert result["type"] == "job_matches"
        assert "listed those jobs a few messages ago" in result["message"]
        # After rehydration, turn counter is reset
        ctx = _get_context(self.api, self.uid)
        assert ctx["active_match_set_turn"] == 0

    def test_out_of_range_returns_clarification(self):
        self._load_visible_matches()
        result = self.api._resolve_numeric_choice(self.uid, "9", None)
        assert result is not None
        assert result["type"] == "clarification"
        assert "2" in result["message"]  # "only have 2 jobs listed"

    def test_no_match_set_returns_none(self):
        _mock_context(self.api, self.uid)
        result = self.api._resolve_numeric_choice(self.uid, "1", None)
        assert result is None

    def test_job_selection_includes_apply_url(self):
        self._load_visible_matches()
        result = self.api._resolve_numeric_choice(self.uid, "1", None)
        assert result["apply_url"] == "https://example.test/apply1"

    def test_selection_2_picks_second_job(self):
        self._load_visible_matches()
        result = self.api._resolve_numeric_choice(self.uid, "2", None)
        assert result["type"] == "job_selection"
        assert result["selected_job"]["title"] == "Environmental Compliance Officer"


# ── _parse_job_constraints ────────────────────────────────────────────────────

class TestParseJobConstraints:
    @pytest.mark.parametrize("msg", [
        "go ahead but don't set it as favorite",
        "don't favorite it",
        "proceed, no favorites",
        "don't save as favorite",
        "without saving as favourite",
    ])
    def test_no_favorite_extracted(self, msg):
        c = RicoChatAPI._parse_job_constraints(msg)
        assert c.get("favorite") is False

    @pytest.mark.parametrize("msg", [
        "go ahead",
        "proceed",
        "yes prepare it",
        "do it",
        "submit",
    ])
    def test_approval_extracted(self, msg):
        c = RicoChatAPI._parse_job_constraints(msg)
        assert c.get("approval_to_prepare") is True

    def test_combined_no_favorite_and_approval(self):
        c = RicoChatAPI._parse_job_constraints("go ahead but don't set as favorite")
        assert c.get("approval_to_prepare") is True
        assert c.get("favorite") is False

    def test_empty_message_returns_empty(self):
        c = RicoChatAPI._parse_job_constraints("random unrelated text")
        assert c == {}


# ── _apply_active_job_constraints ─────────────────────────────────────────────

class TestApplyActiveJobConstraints:
    def setup_method(self):
        self.api = _make_api()
        _patch_context(self.api)
        self.uid = "test-user"

    def _load_with_active_context(self):
        _mock_context(
            self.api, self.uid,
            active_application_context={
                "title": "HSE Manager",
                "company": "ACME",
                "favorite": True,
                "approval_to_prepare": False,
                "next_step": "confirm_or_prepare",
            },
        )

    def test_no_favorite_constraint_acknowledged(self):
        self._load_with_active_context()
        result = self.api._apply_active_job_constraints(self.uid, "don't set it as favorite")
        assert result is not None
        assert result["type"] == "job_constraint_update"
        assert "won't set it as a favorite" in result["message"].lower()

    def test_no_favorite_is_persisted_in_context(self):
        self._load_with_active_context()
        self.api._apply_active_job_constraints(self.uid, "no favorites")
        ctx = _get_context(self.api, self.uid)
        assert ctx["active_application_context"]["favorite"] is False

    def test_no_active_context_returns_none(self):
        _mock_context(self.api, self.uid)
        result = self.api._apply_active_job_constraints(self.uid, "don't save as favorite")
        assert result is None

    def test_unrelated_message_returns_none(self):
        self._load_with_active_context()
        result = self.api._apply_active_job_constraints(self.uid, "find more jobs")
        assert result is None


# ── _increment_match_set_turn ─────────────────────────────────────────────────

class TestIncrementMatchSetTurn:
    def setup_method(self):
        self.api = _make_api()
        _patch_context(self.api)
        self.uid = "test-user"

    def test_increments_from_zero(self):
        _mock_context(self.api, self.uid, active_match_set_turn=0)
        self.api._increment_match_set_turn(self.uid)
        assert _get_context(self.api, self.uid)["active_match_set_turn"] == 1

    def test_no_key_does_nothing(self):
        _mock_context(self.api, self.uid)  # no active_match_set_turn
        self.api._increment_match_set_turn(self.uid)
        assert "active_match_set_turn" not in _get_context(self.api, self.uid)

    def test_does_not_increment_if_no_key(self):
        """No active_match_set_turn key → no-op."""
        _mock_context(self.api, self.uid)  # no active_match_set_turn
        self.api._increment_match_set_turn(self.uid)
        assert "active_match_set_turn" not in _get_context(self.api, self.uid)

    def test_does_not_increment_on_non_int(self):
        """Non-int value → no-op (guards against MagicMock pollution)."""
        _mock_context(self.api, self.uid, active_match_set_turn="bad")
        self.api._increment_match_set_turn(self.uid)
        assert _get_context(self.api, self.uid)["active_match_set_turn"] == "bad"
