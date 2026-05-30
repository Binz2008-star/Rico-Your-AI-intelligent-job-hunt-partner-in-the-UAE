"""
tests/test_chat_regression.py

Regression tests for P0 production crash scenarios (refs 07b233d26df9,
f07da51cb699, 1a0912a0031e, 4302f66c5732).

This file covers:
  - Intent classifier unit tests (no DB / filesystem needed)
  - Memory store resilience tests
  - Integration process_message tests live in tests/unit/test_chat_crash_regression.py
    (where conftest.py auto-mocks all DB dependencies)
"""
from __future__ import annotations

import sys
import os
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agent.intelligence.intent_classifier import classify_intent


# ── Intent classifier unit tests ──────────────────────────────────────────────


class TestSubscriptionIntentClassification:
    """'how can subscribe today?' and variants must classify as subscription."""

    def test_how_can_subscribe_today_exact(self) -> None:
        result = classify_intent("how can subscribe today?")
        assert result.intent == "subscription.show_plans"

    def test_how_can_subscribe_today_natural(self) -> None:
        result = classify_intent("how can subscribe today")
        assert result.intent == "subscription.show_plans"

    def test_i_need_to_buy_subscription(self) -> None:
        result = classify_intent("i need to buy subscription from you how?")
        assert result.intent == "subscription.show_plans"

    def test_buy_subscription(self) -> None:
        result = classify_intent("buy subscription")
        assert result.intent == "subscription.show_plans"

    def test_subscribe_today(self) -> None:
        result = classify_intent("subscribe today")
        assert result.intent == "subscription.show_plans"

    def test_how_can_i_subscribe(self) -> None:
        result = classify_intent("how can i subscribe")
        assert result.intent == "subscription.show_plans"


class TestFriendCVIntentClassification:
    """Friend-CV delegation question: classifier may return cv_upload_or_parse
    but rico_chat_api._is_cv_question guard redirects it to AI. Here we
    just verify the classifier doesn't crash and returns a defined intent."""

    def test_friend_cv_question_classifies_without_crash(self) -> None:
        result = classify_intent(
            "can i use my friend cv here, so u help him or he needs his own account?"
        )
        assert result.intent is not None
        assert isinstance(result.intent, str)

    def test_use_friend_cv_phrasing_classifies_without_crash(self) -> None:
        result = classify_intent("use my friend cv here")
        assert result.intent is not None


class TestApplicationTrackingIntentClassification:
    """'what jobs i applied for?' must classify as application tracking."""

    def test_what_jobs_applied_for(self) -> None:
        result = classify_intent("what jobs i applied for?")
        assert result.intent in (
            "application_tracking",
            "application.show_flow",
            "lifecycle_show_applied",
            "lifecycle.show_applied",
        )

    def test_list_them_classifies_without_crash(self) -> None:
        # "list them" is handled by _is_list_followup() in rico_chat_api before
        # intent classification; the classifier itself may return 'unknown'.
        # What matters is no crash and a defined intent.
        result = classify_intent("list them")
        assert result.intent is not None


# ── Memory store resilience — filesystem failure must not propagate ───────────


class TestMemoryAppendChatResilience:
    """append_chat_message must not raise even when filesystem write fails."""

    def test_write_failure_is_swallowed(self) -> None:
        from src.rico_memory import RicoMemoryStore

        store = RicoMemoryStore()
        with patch.object(store, "load_chat_history", return_value=[]), patch.object(
            store, "add_memory", return_value={}
        ), patch.object(store, "_chat_path") as mock_path:
            mock_path.return_value = MagicMock()
            mock_path.return_value.write_text = MagicMock(side_effect=OSError("disk full"))
            # Should not raise
            store.append_chat_message("user@test.com", "user", "hello")

    def test_add_memory_failure_is_swallowed(self) -> None:
        from src.rico_memory import RicoMemoryStore

        store = RicoMemoryStore()
        with patch.object(store, "load_chat_history", return_value=[]), patch.object(
            store, "_chat_path"
        ) as mock_path, patch.object(
            store, "add_memory", side_effect=RuntimeError("db exploded")
        ):
            mock_path.return_value = MagicMock()
            mock_path.return_value.write_text = MagicMock()
            # Should not raise despite add_memory failing
            store.append_chat_message("user@test.com", "user", "hello")

    def test_append_chat_with_json_write_disabled(self) -> None:
        """When RICO_MEMORY_BACKEND=postgres, append_chat_message is a no-op."""
        import src.rico_memory as mem_module

        original = mem_module._JSON_WRITE_ENABLED
        try:
            mem_module._JSON_WRITE_ENABLED = False
            store = mem_module.RicoMemoryStore()
            # Should return without doing anything — no filesystem calls
            store.append_chat_message("user@test.com", "user", "hello")
        finally:
            mem_module._JSON_WRITE_ENABLED = original
