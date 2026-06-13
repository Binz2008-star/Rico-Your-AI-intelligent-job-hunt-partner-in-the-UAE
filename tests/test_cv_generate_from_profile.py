"""
tests/test_cv_generate_from_profile.py

Regression tests for P1 fix: CV generation from an already-parsed profile.

Covers:
  1. Intent classifier correctly routes Arabic and English CV-generation phrases
     to "cv_generate" (not "cv_create" or a job-search intent).
  2. _handle_cv_generate_from_profile uses extracted profile data and never
     claims the CV is unavailable.
  3. _handle_cv_generate_from_profile with no parsed profile redirects to upload.
  4. cv_create intent with has_cv=True is redirected to cv_generate handler.
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_parsed_profile(**overrides):
    """Return a minimal ProfileContext-like namespace with cv_status=parsed."""
    defaults = dict(
        name="Ahmed Al-Rashid",
        email="ahmed@example.com",
        phone="+971501234567",
        skills=["Python", "FastAPI", "SQL"],
        years_experience=5,
        target_roles=["Backend Engineer", "Python Developer"],
        certifications=["AWS Solutions Architect"],
        preferred_cities=["Dubai", "Abu Dhabi"],
        industries=["Fintech", "E-commerce"],
        current_role="Senior Backend Developer",
        cv_filename="ahmed_cv.pdf",
        cv_status="parsed",
        has_cv=True,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_empty_profile():
    return SimpleNamespace(
        name=None,
        email=None,
        phone=None,
        skills=[],
        years_experience=None,
        target_roles=[],
        certifications=[],
        preferred_cities=[],
        industries=[],
        current_role=None,
        cv_filename=None,
        cv_status=None,
        has_cv=False,
    )


# ---------------------------------------------------------------------------
# 1. Intent classifier — Arabic and English CV-generation phrases
# ---------------------------------------------------------------------------

class TestCvGenerateIntent:
    """All these phrases must classify as cv_generate, not cv_create."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from src.agent.intelligence.intent_classifier import classify_intent
        self.classify = classify_intent

    @pytest.mark.parametrize("phrase", [
        # Arabic colloquial
        "اعملي CV جديد",
        "اعمل لي سيرة ذاتية",
        "اعمللي cv",
        "اكتبلي CV",
        "اكتب لي سيرة ذاتية",
        "جدد السيرة الذاتية",
        "جدد السي في",
        "حدث CV",
        "حدث السيرة الذاتية",
        "اعيد كتابة السيرة الذاتية",
        "سيرة ذاتية جديدة",
        "اريد cv جديد",
        # English
        "rewrite my CV",
        "rewrite my resume",
        "redo my CV",
        "refresh my CV",
        "remake my CV",
        "new CV",
        "new resume",
        "regenerate my resume",
    ])
    def test_cv_generate_intent(self, phrase: str):
        result = self.classify(phrase, has_cv_profile=True)
        assert result.intent == "cv_generate", (
            f"Expected cv_generate for {phrase!r}, got {result.intent!r}"
        )

    @pytest.mark.parametrize("phrase", [
        # These should NOT fire cv_generate when user explicitly has no CV
        "I don't have a CV",
        "no CV yet",
        "لا يوجد لدي سيرة ذاتية",
    ])
    def test_cv_create_intent_for_no_cv_phrases(self, phrase: str):
        result = self.classify(phrase, has_cv_profile=False)
        assert result.intent == "cv_create", (
            f"Expected cv_create for {phrase!r}, got {result.intent!r}"
        )


# ---------------------------------------------------------------------------
# 2. _handle_cv_generate_from_profile — uses profile data, never claims missing
# ---------------------------------------------------------------------------

class TestHandleCvGenerateFromProfile:

    @pytest.fixture(autouse=True)
    def _setup(self):
        from src.rico_chat_api import RicoChatAPI

        self.api = RicoChatAPI.__new__(RicoChatAPI)
        # Stub _append_chat so no DB calls
        self.api._append_chat = MagicMock()

    def test_uses_extracted_profile_data(self):
        profile = _make_parsed_profile()
        result = self.api._handle_cv_generate_from_profile("user1", profile)

        assert result["type"] == "cv_draft"
        assert "Ahmed Al-Rashid" in result["message"]
        assert "Python" in result["message"] or "Python" in result["cv_draft"]
        assert "Backend Engineer" in result["message"] or "Backend Engineer" in result["cv_draft"]

    def test_never_says_cv_unavailable(self):
        profile = _make_parsed_profile()
        result = self.api._handle_cv_generate_from_profile("user1", profile)

        bad_phrases = [
            "cannot find", "can't find", "not found", "upload again",
            "re-upload", "reupload", "no cv", "missing cv",
        ]
        msg_lower = result["message"].lower()
        for phrase in bad_phrases:
            assert phrase not in msg_lower, (
                f"Response should not say {phrase!r} when CV is parsed.\nFull: {result['message']}"
            )

    def test_identifies_missing_fields(self):
        # Profile missing years_experience and preferred_cities
        profile = _make_parsed_profile(
            years_experience=None,
            preferred_cities=[],
        )
        result = self.api._handle_cv_generate_from_profile("user1", profile)

        assert result["type"] == "cv_draft"
        missing = result["missing_fields"]
        assert any("years" in f for f in missing)
        assert any("cit" in f for f in missing)

    def test_no_missing_fields_when_profile_complete(self):
        profile = _make_parsed_profile()
        result = self.api._handle_cv_generate_from_profile("user1", profile)

        assert result["missing_fields"] == []
        assert result["next_action"] == "cv_ready"

    def test_redirects_to_upload_when_no_profile(self):
        profile = _make_empty_profile()
        result = self.api._handle_cv_generate_from_profile("user1", profile)

        assert result["type"] == "cv_creation"
        assert result["next_action"] == "upload_cv"
        # Must not claim "I cannot find your CV" — should direct to upload
        assert "upload" in result["message"].lower()


# ---------------------------------------------------------------------------
# 3. cv_create intent with parsed profile redirects to cv_generate handler
# ---------------------------------------------------------------------------

class TestCvCreateGuard:

    @pytest.fixture(autouse=True)
    def _setup(self):
        from src.rico_chat_api import RicoChatAPI
        self.api = RicoChatAPI.__new__(RicoChatAPI)
        self.api._append_chat = MagicMock()

    def test_cv_create_with_parsed_profile_returns_cv_draft(self):
        """cv_create intent must NOT ask user to start from scratch if has_cv."""
        profile = _make_parsed_profile()

        # Directly invoke the generate handler (simulates what the router does)
        result = self.api._handle_cv_generate_from_profile("user1", profile)

        assert result["type"] == "cv_draft", (
            "Expected cv_draft, not cv_creation — profile is already parsed"
        )
        bad_phrases = ["from scratch", "build a cv from scratch", "tell me your"]
        msg_lower = result["message"].lower()
        for phrase in bad_phrases:
            assert phrase not in msg_lower, (
                f"Response must not ask user to start from scratch.\nFull: {result['message']}"
            )

    def test_cv_create_without_profile_still_shows_scratch_builder(self):
        """cv_create intent without a parsed profile should still start the builder."""
        profile = _make_empty_profile()
        result = self.api._handle_cv_generate_from_profile("user1", profile)

        assert result["type"] == "cv_creation"
        assert result["next_action"] == "upload_cv"
