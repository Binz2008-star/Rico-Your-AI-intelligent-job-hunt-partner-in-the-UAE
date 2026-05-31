"""Tests for acknowledgement intent handling.

Verifies that short acknowledgement phrases (Thanks, OK, Great, Perfect) are:
1. Classified as 'acknowledgement', NOT 'smalltalk' or any job-search intent
2. Return a warm short reply without triggering the cold-start greeting
3. Do not trigger greeting/help/job-search/onboarding intents
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# 1. Intent classifier — classification tests
# ---------------------------------------------------------------------------

class TestAcknowledgementClassification:
    """classify_intent must return 'acknowledgement' for short positive replies."""

    def _classify(self, text: str) -> str:
        from src.agent.intelligence.intent_classifier import classify_intent
        return classify_intent(text).intent

    def test_thanks(self):
        assert self._classify("thanks") == "acknowledgement"

    def test_thank_you(self):
        assert self._classify("thank you") == "acknowledgement"

    def test_ok(self):
        assert self._classify("ok") == "acknowledgement"

    def test_okay(self):
        assert self._classify("okay") == "acknowledgement"

    def test_great(self):
        assert self._classify("great") == "acknowledgement"

    def test_perfect(self):
        assert self._classify("perfect") == "acknowledgement"

    def test_got_it(self):
        assert self._classify("got it") == "acknowledgement"

    def test_sounds_good(self):
        assert self._classify("sounds good") == "acknowledgement"

    def test_arabic_shukran(self):
        assert self._classify("شكرا") == "acknowledgement"

    def test_arabic_tamam(self):
        assert self._classify("تمام") == "acknowledgement"


class TestAcknowledgementNotOtherIntents:
    """Acknowledgement phrases must NOT resolve to greeting/help/job-search."""

    def _classify(self, text: str) -> str:
        from src.agent.intelligence.intent_classifier import classify_intent
        return classify_intent(text).intent

    def test_thanks_is_not_smalltalk(self):
        assert self._classify("thanks") != "smalltalk"

    def test_ok_is_not_smalltalk(self):
        assert self._classify("ok") != "smalltalk"

    def test_great_is_not_smalltalk(self):
        assert self._classify("great") != "smalltalk"

    def test_thanks_is_not_help(self):
        assert self._classify("thanks") != "help"

    def test_thanks_is_not_job_search(self):
        intent = self._classify("thanks")
        assert not intent.startswith("job_search")

    def test_ok_is_not_job_search(self):
        intent = self._classify("ok")
        assert not intent.startswith("job_search")


class TestGreetingsRemainSmallTalk:
    """True greetings (hi/hello/hey) must still be 'smalltalk'."""

    def _classify(self, text: str) -> str:
        from src.agent.intelligence.intent_classifier import classify_intent
        return classify_intent(text).intent

    def test_hi_is_smalltalk(self):
        assert self._classify("hi") == "smalltalk"

    def test_hello_is_smalltalk(self):
        assert self._classify("hello") == "smalltalk"

    def test_hey_is_smalltalk(self):
        assert self._classify("hey") == "smalltalk"


# ---------------------------------------------------------------------------
# 2. Rico API — acknowledgement response (no cold-start greeting)
# ---------------------------------------------------------------------------

class TestAcknowledgementResponse:
    """The acknowledgement routing in _handle_active_user_inner must return a
    short warm reply and never the cold-start greeting string."""

    def _call_inner(self, message: str, recent_messages: list) -> dict:
        from src.rico_chat_api import RicoChatAPI
        api = RicoChatAPI.__new__(RicoChatAPI)
        api.memory = MagicMock()

        mock_profile = MagicMock()
        mock_profile.has_cv = True
        mock_profile.name = "Test User"

        with (
            patch.object(api, "_resolve_profile", return_value=mock_profile),
            patch.object(api, "_get_recent_messages", return_value=recent_messages),
            patch.object(api, "_append_chat"),
            patch.object(api, "_finalize", side_effect=lambda r, *a, **kw: r),
            patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
        ):
            result = api._handle_active_user_inner("user@test.com", message)
        return result

    def test_thanks_returns_youre_welcome(self):
        result = self._call_inner("thank you", [
            {"role": "user", "content": "show my details"},
            {"role": "assistant", "content": "Here are your details..."},
        ])
        assert result.get("type") == "acknowledgement"
        msg = result.get("message", "")
        assert "welcome" in msg.lower() or "happy" in msg.lower() or "glad" in msg.lower()

    def test_thanks_does_not_contain_greeting_text(self):
        result = self._call_inner("thanks", [
            {"role": "user", "content": "what is my email?"},
            {"role": "assistant", "content": "Your email is test@example.com"},
        ])
        msg = result.get("message", "")
        assert "Hi! I am Rico" not in msg, f"Cold-start greeting appeared: {msg!r}"
        assert "job search assistant" not in msg.lower(), f"Intro text appeared: {msg!r}"

    def test_ok_returns_short_reply(self):
        result = self._call_inner("ok", [
            {"role": "user", "content": "anything"},
            {"role": "assistant", "content": "Here you go"},
        ])
        assert result.get("type") == "acknowledgement"
        msg = result.get("message", "")
        assert len(msg) < 100, f"Reply too long for 'ok': {msg!r}"

    def test_great_reply_is_not_cold_start(self):
        result = self._call_inner("great", [])
        msg = result.get("message", "")
        assert "Hi! I am Rico" not in msg


# ---------------------------------------------------------------------------
# 3. _acknowledgement_reply helper
# ---------------------------------------------------------------------------

class TestAcknowledgementReplyHelper:
    def test_thanks_mapping(self):
        from src.rico_chat_api import _acknowledgement_reply
        assert "welcome" in _acknowledgement_reply("thanks").lower()

    def test_thank_you_mapping(self):
        from src.rico_chat_api import _acknowledgement_reply
        assert "welcome" in _acknowledgement_reply("thank you").lower()

    def test_great_mapping(self):
        from src.rico_chat_api import _acknowledgement_reply
        assert _acknowledgement_reply("great") != ""

    def test_perfect_mapping(self):
        from src.rico_chat_api import _acknowledgement_reply
        reply = _acknowledgement_reply("perfect")
        assert reply != ""

    def test_unknown_phrase_returns_default(self):
        from src.rico_chat_api import _acknowledgement_reply
        reply = _acknowledgement_reply("xyzzy unknown")
        assert reply != ""
        assert "Hi! I am Rico" not in reply
