"""
tests/test_cover_letter_intent_routing.py

Regression tests for cover letter intent routing fix.

Covers:
  1. "make me cover letter" and variants → draft_message intent
  2. Standalone "cover letter" → draft_message intent
  3. Arabic cover letter phrases → draft_message intent
  4. Handler fallback when no job in context: returns cover_letter_prompt with target roles
  5. Handler fallback when no job and no profile: returns generic prompt
  6. Non-cover-letter phrases are NOT mis-classified as draft_message
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


# ---------------------------------------------------------------------------
# 1. Intent classifier — cover letter phrases → draft_message
# ---------------------------------------------------------------------------

class TestCoverLetterIntent:

    @pytest.fixture(autouse=True)
    def _import(self):
        from src.agent.intelligence.intent_classifier import classify_intent
        self.classify = classify_intent

    @pytest.mark.parametrize("phrase", [
        # English — "make" was the missing verb
        "make me cover letter",
        "make me a cover letter",
        "make a cover letter",
        # Other verbs that must also work
        "write me a cover letter",
        "draft a cover letter",
        "generate a cover letter",
        "create a cover letter",
        "prepare a cover letter",
        "build a cover letter",
        # Standalone — no verb at all
        "cover letter",
        "a cover letter",
        "I need a cover letter",
        # Arabic
        "اكتب لي خطاب تغطية",
        "اعمل لي رسالة تقديم",
        "خطاب تقديم",
        "رسالة تغطية",
    ])
    def test_cover_letter_routes_to_draft_message(self, phrase: str):
        result = self.classify(phrase, has_cv_profile=True)
        assert result.intent == "draft_message", (
            f"Expected draft_message for {phrase!r}, got {result.intent!r}"
        )

    @pytest.mark.parametrize("phrase", [
        # These should NOT fire draft_message
        "find me a job",
        "search for software engineer",
        "show my profile",
        "rewrite my CV",
    ])
    def test_non_cover_letter_not_misrouted(self, phrase: str):
        result = self.classify(phrase, has_cv_profile=True)
        assert result.intent != "draft_message", (
            f"{phrase!r} should not classify as draft_message, got {result.intent!r}"
        )


# ---------------------------------------------------------------------------
# 2. Handler fallback when no job in context
# ---------------------------------------------------------------------------

class TestDraftMessageFallback:

    @pytest.fixture(autouse=True)
    def _setup(self):
        from src.rico_chat_api import RicoChatAPI
        self.api = RicoChatAPI.__new__(RicoChatAPI)
        self.api._append_chat = MagicMock()
        self.api._profile_value = RicoChatAPI._profile_value
        self.api._as_list = RicoChatAPI._as_list

    def _profile(self, **kw):
        defaults = dict(
            name="Ahmed",
            target_roles=["Environmental Manager", "ESG Manager"],
            skills=["compliance", "ISO 14001"],
        )
        defaults.update(kw)
        return SimpleNamespace(**defaults)

    def test_fallback_includes_target_roles(self):
        profile = self._profile()
        msg = self.api._cover_letter_clarification_message(profile)

        assert "Environmental Manager" in msg
        assert "Ahmed" in msg
        assert "cover letter" in msg.lower()
        assert "Which role and company" in msg
        # Must NOT claim it cannot help
        assert "cannot" not in msg.lower()
        assert "don't have" not in msg.lower()

    def test_fallback_no_profile_generic_prompt(self):
        profile = self._profile(name="", target_roles=[])
        msg = self.api._cover_letter_clarification_message(profile)

        assert "cover letter" in msg.lower()
        assert "role" in msg.lower()
        assert "company" in msg.lower()
        assert "cannot" not in msg.lower()
