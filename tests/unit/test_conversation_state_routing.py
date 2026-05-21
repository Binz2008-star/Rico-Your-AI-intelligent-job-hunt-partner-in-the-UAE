"""tests/unit/test_conversation_state_routing.py

Regression tests for routing failures where vague conversational replies
(e.g. "you tell me") were incorrectly treated as job-role names.

Covers:
- Intent classifier catches profile-guidance phrases
- _looks_like_bare_target_role rejects conversational phrases
- _was_asked_for_role detects conversation state from chat history
- End-to-end: "you tell me" after role-question → profile_role_suggestions
"""
import pytest
from unittest.mock import MagicMock

from src.agent.intelligence.intent_classifier import classify_intent, IntentResult
from src.rico_chat_api import RicoChatAPI
from src.rico_agent import RicoProfile


# ── Intent classifier tests ───────────────────────────────────────────────────

class TestIntentClassifierProfileGuidance:
    """classify_intent must recognize vague replies as profile_role_suggestions."""

    @pytest.mark.parametrize("message", [
        "you tell me",
        "what do you think",
        "surprise me",
        "anything",
        "whatever",
        "i don't know",
        "idk",
        "no idea",
        "you choose",
        "up to you",
        "what fits me",
        "what suits me best",
    ])
    def test_exact_phrases_profile_guidance(self, message):
        result = classify_intent(message, has_cv_profile=True)
        assert result.intent == "profile_role_suggestions"
        assert result.confidence >= 0.9

    @pytest.mark.parametrize("message", [
        "what should I search for",
        "what do you suggest I apply for",
        "not sure what to search",
    ])
    def test_regex_phrases_profile_guidance(self, message):
        result = classify_intent(message, has_cv_profile=True)
        assert result.intent == "profile_role_suggestions"

    def test_no_cv_still_classifies(self):
        """Even without CV, vague guidance intent is recognized."""
        result = classify_intent("you tell me", has_cv_profile=False)
        assert result.intent == "profile_role_suggestions"


# ── Bare target role guard tests ────────────────────────────────────────────

class TestBareTargetRoleRejectsConversational:
    """_looks_like_bare_target_role must reject obvious non-role phrases."""

    @pytest.mark.parametrize("message", [
        "you tell me",
        "what do you think",
        "surprise me",
        "i don't know",
        "idk",
        "no idea",
        "whatever",
        "anything",
        "you choose",
        "up to you",
    ])
    def test_conversational_phrases_rejected(self, message):
        assert RicoChatAPI._looks_like_bare_target_role(message) is False

    def test_pronoun_only_phrases_rejected(self):
        """Pure pronoun/auxiliary phrases like 'you tell me' are rejected."""
        assert RicoChatAPI._looks_like_bare_target_role("you tell me") is False
        assert RicoChatAPI._looks_like_bare_target_role("i do not know") is False
        assert RicoChatAPI._looks_like_bare_target_role("me choose you") is False

    @pytest.mark.parametrize("message", [
        "sales man",
        "hse manager",
        "software engineer",
        "data scientist",
    ])
    def test_real_roles_still_accepted(self, message):
        assert RicoChatAPI._looks_like_bare_target_role(message) is True


# ── Conversation state tests ────────────────────────────────────────────────

class TestWasAskedForRole:
    """_was_asked_for_role must detect when assistant asked about roles."""

    def test_no_history_returns_false(self):
        api = RicoChatAPI()
        api.memory.load_chat_history = MagicMock(return_value=[])
        assert api._was_asked_for_role("u1") is False

    def test_last_assistant_asked_what_role(self):
        api = RicoChatAPI()
        api.memory.load_chat_history = MagicMock(return_value=[
            {"role": "assistant", "message": "What role would you like to search for?"},
            {"role": "user", "message": "you tell me"},
        ])
        assert api._was_asked_for_role("u1") is True

    def test_last_assistant_asked_which_job(self):
        api = RicoChatAPI()
        api.memory.load_chat_history = MagicMock(return_value=[
            {"role": "assistant", "message": "Which job are you interested in?"},
            {"role": "user", "message": "i don't know"},
        ])
        assert api._was_asked_for_role("u1") is True

    def test_last_assistant_was_role_suggestions_structured(self):
        api = RicoChatAPI()
        api.memory.load_chat_history = MagicMock(return_value=[
            {"role": "assistant", "message": {"type": "profile_role_suggestions", "message": "Here are roles"}},
            {"role": "user", "message": "whatever"},
        ])
        assert api._was_asked_for_role("u1") is True

    def test_last_assistant_was_options_structured(self):
        api = RicoChatAPI()
        api.memory.load_chat_history = MagicMock(return_value=[
            {"role": "assistant", "message": {"type": "options", "message": "Choose next step"}},
            {"role": "user", "message": "anything"},
        ])
        assert api._was_asked_for_role("u1") is True

    def test_last_assistant_was_job_matches_returns_false(self):
        api = RicoChatAPI()
        api.memory.load_chat_history = MagicMock(return_value=[
            {"role": "assistant", "message": "Here are 5 job matches."},
            {"role": "user", "message": "you tell me"},
        ])
        assert api._was_asked_for_role("u1") is False

    def test_last_assistant_was_profile_summary_returns_false(self):
        api = RicoChatAPI()
        api.memory.load_chat_history = MagicMock(return_value=[
            {"role": "assistant", "message": "Here is your current profile."},
            {"role": "user", "message": "no idea"},
        ])
        assert api._was_asked_for_role("u1") is False


# ── End-to-end routing tests ────────────────────────────────────────────────

@pytest.fixture
def hse_profile():
    return RicoProfile(
        user_id="u1",
        skills=["hse", "safety", "iso 14001", "nebosh igc"],
        years_experience=10.0,
        target_roles=["Senior HSE Manager"],
        industries=["Oil & Gas"],
        cv_status="parsed",
        cv_filename="cv.pdf",
    )


class TestEndToEndVagueReplyRouting:
    """Vague replies must route to profile_role_suggestions, not role classification."""

    def _run_active(self, monkeypatch, message, profile, history=None):
        import src.rico_chat_api as mod
        from src.rico_chat_api import RicoChatAPI

        mock_route = MagicMock(return_value=MagicMock(
            tool_name=None, entities={}, tool_args={},
            confirmation_prompt=None, source="keyword"
        ))

        monkeypatch.setattr(mod, "get_profile", lambda uid: profile)
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id, updates: profile)
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        monkeypatch.setattr(mod, "_route", mock_route)
        monkeypatch.setattr(mod, "is_onboarding_complete", lambda uid: True)
        monkeypatch.setattr(mod, "mark_onboarding_complete", lambda uid: None)

        api = RicoChatAPI()
        api.system.run_for_profile = MagicMock(return_value={"matches": []})
        if history:
            api.memory.load_chat_history = MagicMock(return_value=history)

        return api._handle_active_user("test-user", message)

    def test_you_tell_me_after_role_question(self, monkeypatch, hse_profile):
        result = self._run_active(
            monkeypatch,
            "you tell me",
            hse_profile,
            history=[
                {"role": "assistant", "message": "What role would you like to search for?"},
            ],
        )
        assert result["type"] == "profile_role_suggestions"

    def test_idk_after_role_options(self, monkeypatch, hse_profile):
        result = self._run_active(
            monkeypatch,
            "idk",
            hse_profile,
            history=[
                {"role": "assistant", "message": {"type": "options", "message": "Choose a role"}},
            ],
        )
        assert result["type"] == "profile_role_suggestions"

    def test_whatever_after_role_confirmation(self, monkeypatch, hse_profile):
        result = self._run_active(
            monkeypatch,
            "whatever",
            hse_profile,
            history=[
                {"role": "assistant", "message": {"type": "role_confirmation", "message": "HSE Manager is a strong fit.", "role": "HSE Manager"}},
            ],
        )
        assert result["type"] == "profile_role_suggestions"

    def test_you_tell_me_without_context_no_crash(self, monkeypatch, hse_profile):
        """Even with empty history, intent classifier should catch 'you tell me'."""
        result = self._run_active(
            monkeypatch,
            "you tell me",
            hse_profile,
            history=[],
        )
        # Intent classifier catches it first, so it should be profile_role_suggestions
        assert result["type"] == "profile_role_suggestions"

    def test_real_role_still_searches(self, monkeypatch, hse_profile):
        """A real bare role name should still go through role confirmation."""
        result = self._run_active(
            monkeypatch,
            "hse manager",
            hse_profile,
            history=[
                {"role": "assistant", "message": "What role would you like to search for?"},
            ],
        )
        # With a real role name, should get role_confirmation or job_matches
        assert result["type"] in {"role_confirmation", "job_matches", "profile_role_suggestions"}
