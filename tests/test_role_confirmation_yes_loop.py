"""Typed-YES on the role-fit clarification must execute the search, not re-ask.

Production evidence (delivery-smoke runs 29916155222 / 29916274691,
2026-07-22): a profile-less user asked "Find accountant jobs in Dubai", got
the role-fit clarification ("'Accountant' is a real role, but it does not
look close to your CV profile. Should I search for Accountant jobs anyway?
Reply YES or tell me a different role."), replied YES — and received the
SAME clarification again. The quick-reply button path was fixed in BUG-05,
but the typed-YES path redeemed the pending slot through
``_classified_role_search``, whose off-profile gate re-fired, re-emitted the
identical question, and re-armed the slot: an infinite confirmation loop.

Global contract pinned here (user-agnostic — any profile state, any role):
redeeming a pending job search executes the search DIRECTLY via
``_target_role_search_response``; the armed role was already validated at arm
time, so it is never re-classified.

Two more recurrences of the same bug class were found in
``_handle_active_user_inner``, reached instead of the two sites above for
bare short confirmations that never hit ``_is_affirmative``/
``_is_continuation_intent``: the acknowledgement-replies fast path ("تمام",
"حسنا", "ok", "okay") and the ``legacy_intent == "follow_up_confirmation"``
dispatch ("اي", "اوكي", "طيب", "continue", "confirm", "confirmed"). Both
called ``_classified_role_search`` and never discarded
``_pending_role_confirmation``, so either loops for any off-profile role.
"""
from __future__ import annotations

import contextlib
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.rico_chat_api import RicoChatAPI

_SEARCH_RESULT = {
    "type": "job_matches",
    "message": "Found verified openings.",
    "matches": [{"title": "Accountant", "company": "Synthetic Co"}],
}

# What the off-profile gate would emit if the redemption re-entered
# _classified_role_search (the pre-fix loop behaviour).
_GATE_CLARIFICATION = {
    "type": "clarification",
    "message": (
        "'Accountant' is a real role, but it does not look close to your CV "
        "profile. Should I search for Accountant jobs anyway? Reply YES or "
        "tell me a different role."
    ),
}


def _pending(role: str = "Accountant", location: str = "Dubai") -> dict:
    return {
        "role": role,
        "location": location,
        "query_type": "known_but_off_profile",
        "expires_at": int(time.time()) + 600,
    }


def _make_api(pending_job_search: dict | None = None) -> RicoChatAPI:
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


class TestTypedYesRedemption:
    """_resolve_pending_intent Priority-0 — the path production YES takes."""

    def test_typed_yes_executes_confirmed_search_directly(self):
        api = _make_api(pending_job_search=_pending())
        with patch.object(
            api, "_target_role_search_response", return_value=dict(_SEARCH_RESULT)
        ) as direct, patch.object(
            api, "_classified_role_search", return_value=dict(_GATE_CLARIFICATION)
        ) as gated, patch.object(
            api, "_get_recent_context", return_value={}
        ), patch.object(api, "_store_recent_context"):
            # Profile-less user (the state that exposed the loop) — the fix is
            # global: no re-classification for ANY profile state.
            result = api._resolve_pending_intent("u1", "YES", profile={})

        gated.assert_not_called()
        direct.assert_called_once()
        args, kwargs = direct.call_args
        assert args[1] == "Accountant"
        assert kwargs.get("location") == "Dubai"
        assert result["type"] == "job_matches"
        # Slot cleared so the search cannot double-fire.
        api.memory.set_context.assert_any_call(
            "u1", RicoChatAPI._PENDING_JOB_SEARCH_KEY, {}
        )

    def test_confirmation_marker_discarded_on_redemption(self):
        api = _make_api(pending_job_search=_pending())
        ctx = {"_pending_role_confirmation": {"role": "Accountant", "location": "Dubai"}}
        with patch.object(
            api, "_target_role_search_response", return_value=dict(_SEARCH_RESULT)
        ), patch.object(
            api, "_get_recent_context", return_value=ctx
        ), patch.object(api, "_store_recent_context") as store_ctx:
            api._resolve_pending_intent("u1", "yes", profile={})

        store_ctx.assert_called_once()
        stored = store_ctx.call_args[0][1]
        assert "_pending_role_confirmation" not in stored


class TestConversationalYesRedemption:
    """answer_conversationally Priority-0 — the AI-path 'ok/تمام' variant."""

    def test_conversational_yes_executes_directly_not_reclassified(self):
        api = _make_api(pending_job_search=_pending(role="Accountant", location=""))
        with patch.object(
            api, "_target_role_search_response", return_value=dict(_SEARCH_RESULT)
        ) as direct, patch.object(
            api, "_classified_role_search", return_value=dict(_GATE_CLARIFICATION)
        ) as gated, patch.object(api, "_append_chat"), patch.object(
            api, "_get_recent_context", return_value={}
        ), patch.object(api, "_store_recent_context"), patch.object(
            api, "_answer_with_ai_fallback"
        ) as ai:
            result = api.answer_conversationally("u1", "yes", profile={})

        gated.assert_not_called()
        ai.assert_not_called()
        direct.assert_called_once()
        assert result["type"] == "job_matches"
        assert result.get("response_source") == "search_contract"


class TestAcknowledgementReplyRedemption:
    """_handle_active_user_inner's acknowledgement-replies fast path — the
    ACTUAL live route for bare "تمام"/"حسنا"/"ok"/"okay" (they never reach
    _is_affirmative/_is_continuation_intent, so _resolve_pending_intent's
    Priority-0 never runs for them). This site independently redeemed the
    pending slot through ``_classified_role_search`` and never discarded
    ``_pending_role_confirmation`` — the same infinite-loop bug class as
    #1314, recurring here for the most common Arabic acknowledgement word.
    """

    def _run(self, message: str, recent_context: dict | None = None):
        api = _make_api(pending_job_search=_pending(role="Accountant", location="Dubai"))
        api._resolve_profile = MagicMock(return_value=SimpleNamespace(has_cv=False))
        patches = [
            patch.object(api, "_resolve_pending_field", return_value=None),
            patch.object(api, "_resolve_letter_choice", return_value=None),
            patch.object(api, "_get_recent_context", return_value=recent_context if recent_context is not None else {}),
            patch.object(api, "_store_recent_context"),
            patch.object(api, "_handle_pending_pipeline_reset", return_value=None),
            patch.object(api, "_handle_pending_delete_saved_jobs", return_value=None),
            patch.object(api, "_intercept_unsupported_delete_mutation", return_value=None),
            patch.object(api, "_resolve_settings_command", return_value=None),
            patch.object(api, "_extract_explicit_draft_job_from_message", return_value=None),
            patch.object(api, "_handle_application_channel_followup", return_value=None),
            patch.object(api, "_looks_like_cv_intent_no_file", return_value=False),
            patch.object(api, "_is_list_followup", return_value=False),
            patch.object(api, "_is_verify_followup", return_value=False),
            patch.object(api, "_append_chat"),
            patch.object(api, "_finalize", side_effect=lambda response, source, **kw: response),
            patch.object(
                api, "_target_role_search_response", return_value=dict(_SEARCH_RESULT)
            ),
            patch.object(
                api, "_classified_role_search", return_value=dict(_GATE_CLARIFICATION)
            ),
        ]
        with contextlib.ExitStack() as stack:
            mocks = {p.attribute: stack.enter_context(p) for p in patches}
            result = api._handle_active_user_inner("u1", message)
        return api, result, mocks

    def test_bare_tamam_executes_confirmed_search_directly(self):
        api, result, mocks = self._run("تمام")

        mocks["_classified_role_search"].assert_not_called()
        mocks["_target_role_search_response"].assert_called_once()
        args, kwargs = mocks["_target_role_search_response"].call_args
        assert args[1] == "Accountant"
        assert kwargs.get("location") == "Dubai"
        assert result["type"] == "job_matches"
        # Pending job-search slot cleared so the search cannot double-fire.
        api.memory.set_context.assert_any_call(
            "u1", RicoChatAPI._PENDING_JOB_SEARCH_KEY, {}
        )

    def test_bare_tamam_discards_confirmation_marker(self):
        ctx = {"_pending_role_confirmation": {"role": "Accountant", "location": "Dubai"}}
        api, result, mocks = self._run("تمام", recent_context=ctx)

        mocks["_classified_role_search"].assert_not_called()
        mocks["_target_role_search_response"].assert_called_once()
        store_ctx = mocks["_store_recent_context"]
        store_ctx.assert_called_once()
        stored = store_ctx.call_args[0][1]
        assert "_pending_role_confirmation" not in stored
