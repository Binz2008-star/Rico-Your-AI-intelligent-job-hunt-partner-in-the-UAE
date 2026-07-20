"""
Regression tests: search-execution contract on the conversational (AI) path.

Live-QA 2026-07-03 found that all #680 protections (promise-only guard,
pending-search redemption) only ran inside RicoChatAPI.process_message
(the legacy path). Messages routed to answer_conversationally (the AI path)
could:
  1. return a hollow "I'll search now… one moment" reply for an explicit
     job-listing request, arming a pending-search slot that NOTHING on the
     conversational path ever redeemed, and
  2. re-promise forever on the user's follow-up "ok", because Priority-0
     redemption lived only in _resolve_pending_intent (legacy path).

These tests pin the convergence: the conversational path must execute real
searches, never return promises for explicit search requests, and redeem an
armed pending search on affirmative follow-ups.
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from src.rico_chat_api import RicoChatAPI


_PROFILE = {
    "target_roles": ["Environmental Manager", "HSE Manager"],
    "preferred_cities": ["Dubai"],
    "skills": ["ISO 14001", "EHS auditing"],
    "years_experience": 8,
}

_SEARCH_RESULT = {
    "type": "job_matches",
    "message": "Found 3 verified openings.",
    "matches": [{"title": "Environmental Manager", "company": "AESG"}],
}


def _make_api(pending_job_search: dict | None = None) -> RicoChatAPI:
    """Bare RicoChatAPI with mocked memory, mirroring test_job_search_action_contract."""
    api = RicoChatAPI.__new__(RicoChatAPI)
    memory = MagicMock()

    def _get_context(user_id, key):
        if key == RicoChatAPI._PENDING_JOB_SEARCH_KEY and pending_job_search:
            return pending_job_search
        return {}

    memory.get_context.side_effect = _get_context
    memory.set_context.return_value = None
    api.memory = memory
    return api


def _pending(role: str = "Environmental Manager", location: str = "Dubai") -> dict:
    return {"role": role, "location": location, "expires_at": int(time.time()) + 600}


# ── Priority-0 redemption on the conversational path ──────────────────────────

class TestConversationalPendingRedemption:
    def test_affirmative_redeems_pending_search(self):
        api = _make_api(pending_job_search=_pending())
        with patch.object(api, "_classified_role_search", return_value=dict(_SEARCH_RESULT)) as search, \
             patch.object(api, "_append_chat"), \
             patch.object(api, "_answer_with_ai_fallback") as ai:
            result = api.answer_conversationally("u1", "ok", _PROFILE)

        search.assert_called_once()
        args, kwargs = search.call_args
        assert args[1] == "Environmental Manager"
        assert kwargs.get("location") == "Dubai"
        ai.assert_not_called()
        assert result.get("response_source") == "search_contract"
        assert result.get("success") is True
        # Slot must be cleared so the search cannot double-fire.
        api.memory.set_context.assert_any_call(
            "u1", RicoChatAPI._PENDING_JOB_SEARCH_KEY, {}
        )

    def test_continuation_phrase_redeems_pending_search(self):
        api = _make_api(pending_job_search=_pending(role="HSE Manager", location=""))
        with patch.object(api, "_classified_role_search", return_value=dict(_SEARCH_RESULT)) as search, \
             patch.object(api, "_append_chat"), \
             patch.object(api, "_answer_with_ai_fallback") as ai:
            api.answer_conversationally("u1", "keep going", _PROFILE)

        search.assert_called_once()
        ai.assert_not_called()

    def test_unrelated_message_does_not_hijack_pending(self):
        api = _make_api(pending_job_search=_pending())
        ai_reply = {"message": "Here is your profile summary.", "success": True}
        with patch.object(api, "_classified_role_search") as search, \
             patch.object(api, "_append_chat"), \
             patch.object(api, "_answer_with_ai_fallback", return_value=dict(ai_reply)):
            result = api.answer_conversationally("u1", "tell me about my profile", _PROFILE)

        search.assert_not_called()
        assert result["message"] == "Here is your profile summary."

    def test_no_pending_no_redemption(self):
        api = _make_api(pending_job_search=None)
        ai_reply = {"message": "Sure — what would you like?", "success": True}
        with patch.object(api, "_classified_role_search") as search, \
             patch.object(api, "_append_chat"), \
             patch.object(api, "_answer_with_ai_fallback", return_value=dict(ai_reply)):
            api.answer_conversationally("u1", "ok", _PROFILE)

        search.assert_not_called()

    def test_public_session_without_profile_never_searches(self):
        api = _make_api(pending_job_search=_pending())
        ai_reply = {"message": "Please sign up first.", "success": True}
        with patch.object(api, "_classified_role_search") as search, \
             patch.object(api, "_append_chat"), \
             patch.object(api, "_answer_with_ai_fallback", return_value=dict(ai_reply)):
            api.answer_conversationally("u1", "ok", None)

        search.assert_not_called()


# ── Promise-only guard executes instead of promising ──────────────────────────

class TestPromiseExecutesForExplicitSearch:
    def _run_fallback(self, api: RicoChatAPI, message: str, ai_text: str, profile=_PROFILE):
        agent = MagicMock()
        agent.respond.return_value = {"message": ai_text, "type": "openai_response"}
        with patch.object(api, "_get_openai_agent", return_value=agent), \
             patch.object(api, "_build_openai_context", return_value={}), \
             patch.object(api, "_get_blocked_questions", return_value=[]), \
             patch.object(api, "_preserve_ai_message", side_effect=lambda text, _bq: text), \
             patch.object(api, "_append_chat"), \
             patch.object(api, "_classified_role_search", return_value=dict(_SEARCH_RESULT)) as search, \
             patch.object(api, "_finalize", side_effect=lambda resp, _src, profile=None: dict(resp)):
            result = api._answer_with_ai_fallback(
                user_id="u1", message=message, profile=profile, save_user_message=True,
            )
        return result, search

    def test_explicit_search_request_with_promise_reply_executes_search(self):
        api = _make_api()
        result, search = self._run_fallback(
            api,
            message="Find UAE jobs that match my CV and experience.",
            ai_text="I'll search now — one moment.",
        )
        search.assert_called_once()
        assert result.get("type") == "job_matches"
        assert result.get("response_source") == "search_contract"
        # The hollow promise must not be the returned payload.
        assert "one moment" not in str(result.get("message", "")).lower()

    def test_non_search_message_with_promise_reply_keeps_arming_behavior(self):
        api = _make_api()
        stored = {}
        api.memory.set_context.side_effect = lambda u, k, v: stored.__setitem__((u, k), v)
        result, search = self._run_fallback(
            api,
            message="tell me about my profile",
            ai_text="One moment while I gather that.",
        )
        search.assert_not_called()
        armed = stored.get(("u1", RicoChatAPI._PENDING_JOB_SEARCH_KEY))
        assert armed and armed["role"] == "Environmental Manager"
        assert "one moment" in str(result.get("message", "")).lower()

    def test_normal_ai_reply_untouched(self):
        api = _make_api()
        result, search = self._run_fallback(
            api,
            message="Find UAE jobs that match my CV and experience.",
            ai_text="Here are strategies to improve your search…",
        )
        search.assert_not_called()
        assert "strategies" in result["message"]

    def test_promise_without_profile_roles_does_not_search(self):
        api = _make_api()
        result, search = self._run_fallback(
            api,
            message="find me jobs in dubai",
            ai_text="I'll search now — one moment.",
            profile={"skills": ["excel"]},  # no target_roles
        )
        search.assert_not_called()


# ── Assistant turn is persisted only when it is the delivered reply ───────────

class TestPromisePersistenceOrdering:
    """The hollow-promise guard must run BEFORE the assistant turn is persisted.

    A promise ("I'll search now…") that Rico replaces with a real search must
    never land in chat history — otherwise session recovery, later AI context,
    and analytics all see an orphan assistant turn the user never received.
    """

    def _run_capture(self, api, message, ai_text, profile=_PROFILE):
        agent = MagicMock()
        agent.respond.return_value = {"message": ai_text, "type": "openai_response"}
        append = MagicMock()
        with patch.object(api, "_get_openai_agent", return_value=agent), \
             patch.object(api, "_build_openai_context", return_value={}), \
             patch.object(api, "_get_blocked_questions", return_value=[]), \
             patch.object(api, "_preserve_ai_message", side_effect=lambda text, _bq: text), \
             patch.object(api, "_append_chat", append), \
             patch.object(api, "_classified_role_search", return_value=dict(_SEARCH_RESULT)), \
             patch.object(api, "_finalize", side_effect=lambda resp, _src, profile=None: dict(resp)):
            result = api._answer_with_ai_fallback(
                user_id="u1", message=message, profile=profile, save_user_message=True,
            )
        assistant_texts = [
            c.args[2] for c in append.call_args_list
            if len(c.args) >= 3 and c.args[1] == "assistant"
        ]
        return result, assistant_texts

    def test_promise_replaced_by_search_is_not_persisted(self):
        # Explicit search request + hollow promise → real search is returned and
        # the promise is NOT written to history (the search path persists itself).
        api = _make_api()
        result, assistant_texts = self._run_capture(
            api,
            message="Find UAE jobs that match my CV and experience.",
            ai_text="I'll search now — one moment.",
        )
        assert result.get("response_source") == "search_contract"
        assert assistant_texts == []

    def test_ambiguous_promise_reply_is_persisted(self):
        # Non-search message + promise → arm-the-slot path; the promise IS the
        # delivered reply, so it must be persisted exactly once.
        api = _make_api()
        result, assistant_texts = self._run_capture(
            api,
            message="tell me about my profile",
            ai_text="One moment while I gather that.",
        )
        assert assistant_texts == ["One moment while I gather that."]

    def test_normal_reply_is_persisted(self):
        api = _make_api()
        result, assistant_texts = self._run_capture(
            api,
            message="Find UAE jobs that match my CV and experience.",
            ai_text="Here are strategies to improve your search…",
        )
        assert assistant_texts == ["Here are strategies to improve your search…"]
