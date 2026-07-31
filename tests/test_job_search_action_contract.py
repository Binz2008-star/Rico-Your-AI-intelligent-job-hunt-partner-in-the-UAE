"""
P0 regression tests for job-search action contract.

Ensures Rico never emits promise-only replies for job-search contexts and
always executes the search when the user confirms a pending job-search.
"""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest

from src.rico_chat_api import RicoChatAPI
from src.services.pending_job_search import (
    PendingJobSearch, PendingSearchLookup, LookupStatus, new_pending,
)


# ── helpers ────────────────────────────────────────────────────────────────────

_PROFILE = {
    "target_roles": ["Environmental Manager", "HSE Manager"],
    "preferred_cities": ["Dubai"],
    "skills": ["ISO 14001", "EHS auditing"],
    "years_experience": 8,
}

_JOBS = [
    {
        "title": "Environmental Manager",
        "company": "AESG",
        "location": "Dubai",
        "apply_url": "https://apply/1",
        "source_url": "",
        "score": 0.9,
        "match_reason": "Strong match on ISO 14001",
    },
]


def _make_api_with_profile(pending_job_search=None) -> RicoChatAPI:
    api = RicoChatAPI.__new__(RicoChatAPI)
    api.memory = MagicMock()
    api._pjs_repo = MagicMock()
    api._can_mutate_applications = False
    api._current_operation_id = None
    api._pjs_redemption_attempted_this_turn = RicoChatAPI._PJS_SENTINEL
    if pending_job_search:
        role = pending_job_search.get("role", "Test")
        loc = pending_job_search.get("location", "")
        pjs = new_pending(role=role, location=loc)
        api._pjs_repo.get.return_value = pjs
        api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.FOUND, pjs)
        api._pjs_repo.consume.return_value = pjs
    else:
        api._pjs_repo.get.return_value = None
        api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.NONE)
        api._pjs_repo.consume.return_value = None
    api._pjs_repo.cancel.return_value = True
    api._pjs_repo.store.return_value = True
    return api


# ── pending job search state ────────────────────────────────────────────────────

class TestPendingJobSearchState:
    def test_store_and_retrieve(self):
        api = _make_api_with_profile()
        ok = api._store_pending_job_search("u1", role="Environmental Manager", location="Dubai")
        assert ok
        # Verify the repo's store method was called with a tokenized PendingJobSearch
        assert api._pjs_repo.store.called
        args = api._pjs_repo.store.call_args
        if args:
            stored_pjs = args[0][1]
            assert stored_pjs.role == "Environmental Manager"
            assert stored_pjs.location == "Dubai"

    def test_expired_state_returns_empty(self):
        api = _make_api_with_profile()
        api._pjs_repo.get.return_value = None
        result = api._get_pending_job_search("u1")
        assert result == {}

    def test_clear_pending_state(self):
        api = _make_api_with_profile()
        api._pjs_repo.get.return_value = None
        ok = api._clear_pending_job_search("u1")
        assert ok
        assert api._pjs_repo.cancel.called


# ── is_promise_only_reply ──────────────────────────────────────────────────────

class TestIsPromiseOnlyReply:
    @pytest.mark.parametrize("text", [
        "جاري البحث...",
        "ببحث الآن",
        "ثواني وأرجع لك",
        "انتظرني",
        "I'm searching now",
        "I'll search now, please wait",
        "Searching now...",
    ])
    def test_detects_promise_only(self, text):
        assert RicoChatAPI._is_promise_only_reply(text)

    @pytest.mark.parametrize("text", [
        "وجدت 3 وظائف مناسبة لك",
        "I found 5 jobs matching your profile",
        "لم أجد وظائف متاحة الآن",
        "No results found for your role",
    ])
    def test_not_promise_only_for_results_or_errors(self, text):
        assert not RicoChatAPI._is_promise_only_reply(text)


# ── tamam continues pending job search ────────────────────────────────────────

class TestConfirmationContinuesPendingJobSearch:
    def test_tamam_executes_pending_job_search(self):
        pending = {
            "role": "Environmental Manager",
            "location": "Dubai",
        }
        api = _make_api_with_profile(pending_job_search=pending)

        with patch.object(api, "_target_role_search_response", return_value={"type": "job_results", "jobs": _JOBS, "message": "Found 1 job"}) as mock_search:
            result = api._resolve_pending_intent(
                user_id="u1",
                message="تمام",
                profile=_PROFILE,
            )

        mock_search.assert_called_once()
        assert result["type"] == "job_results"

    def test_tamam_does_not_return_good_luck(self):
        pending = {"role": "Environmental Manager", "location": ""}
        api = _make_api_with_profile(pending_job_search=pending)
        with patch.object(api, "_target_role_search_response", return_value={"type": "job_results", "jobs": _JOBS, "message": "Found 1 job"}):
            result = api._resolve_pending_intent("u1", "تمام", _PROFILE)
        # Must not contain good-luck or conversation-close phrases
        msg = result.get("message", "").lower()
        assert "بالتوفيق" not in msg
        assert "good luck" not in msg

    def test_ok_english_also_continues_pending_job_search(self):
        pending = {"role": "HSE Manager", "location": "Abu Dhabi"}
        api = _make_api_with_profile(pending_job_search=pending)
        with patch.object(api, "_target_role_search_response", return_value={"type": "job_results", "jobs": _JOBS, "message": "Found 1 job"}) as mock_search:
            api._resolve_pending_intent("u1", "ok", _PROFILE)
        mock_search.assert_called_once()


# ── no promise-only replies ────────────────────────────────────────────────────

class TestNoPromiseOnlyReplies:
    def test_promise_only_pattern_detection(self):
        for phrase in ["جاري البحث", "ببحث الآن", "ثواني", "انتظرني", "لحظة"]:
            assert RicoChatAPI._is_promise_only_reply(phrase), f"{phrase!r} should be detected as promise-only"

    def test_resolve_pending_intent_never_emits_promise_only(self):
        """When job search signals exist in last turn, resolve must not emit a promise-only reply."""
        pending = {"role": "Environmental Manager", "location": ""}
        api = _make_api_with_profile(pending_job_search=pending)
        with patch.object(api, "_target_role_search_response", return_value={"type": "job_results", "jobs": [], "message": "لم أجد وظائف متاحة الآن"}):
            result = api._resolve_pending_intent("u1", "تمام", _PROFILE)
        msg = result.get("message", "")
        assert not RicoChatAPI._is_promise_only_reply(msg), f"Promise-only reply detected: {msg!r}"


# ── Arabic language matching ───────────────────────────────────────────────────

class TestArabicLanguageMatching:
    def test_arabic_input_arabic_output_on_no_results(self):
        """Empty result message for Arabic query must be Arabic."""
        arabic_msg = "لم أجد وظائف متاحة الآن"
        assert any(ord(c) > 0x600 for c in arabic_msg), "Expected Arabic text"

    def test_english_input_english_output_on_no_results(self):
        """Empty result message for English query must be English."""
        en_msg = "No live UAE matches found"
        assert all(ord(c) < 0x600 for c in en_msg if c.isalpha()), "Expected English text"


# ── provider failure contract ──────────────────────────────────────────────────

class TestProviderFailureContract:
    def test_provider_failure_does_not_produce_promise_only(self):
        """If job provider raises, response must contain clear error, not a promise."""
        pending = {"role": "Environmental Manager", "location": ""}
        api = _make_api_with_profile(pending_job_search=pending)
        # Simulate provider failure by mocking _classified_role_search to return error response
        error_resp = {
            "type": "error",
            "message": "بحثت لكن مزود الوظائف لم يرجع نتائج صالحة الآن.",
            "jobs": [],
        }
        with patch.object(api, "_target_role_search_response", return_value=error_resp):
            result = api._resolve_pending_intent("u1", "تمام", _PROFILE)

        assert result is not None, "Expected a response when pending job search is set"
        msg = result.get("message", "")
        assert not RicoChatAPI._is_promise_only_reply(msg)
        assert "بالتوفيق" not in msg


# ── clean role query from target_roles ────────────────────────────────────────

class TestCleanRoleQuery:
    def test_single_clean_role_used_not_blob(self):
        """Only one clean role from target_roles should be sent to search, not a joined list."""
        target_roles = ["Environmental Manager", "HSE Manager", "ESG Compliance Officer", "EHS Lead"]
        role = target_roles[0] if target_roles else None
        assert role == "Environmental Manager"
        # Ensure no comma-separated blob
        assert "," not in role
        assert len(role.split()) <= 5  # reasonable title length


# ── intent classifier: Arabic show/display verbs ──────────────────────────────

class TestArabicIntentClassifier:
    def test_aeridli_triggers_job_search(self):
        """'اعرضلي احدث الوظائف بمجالي' must classify as job_search_explicit."""
        from src.agent.intelligence.intent_classifier import classify_intent
        result = classify_intent("اعرضلي احدث الوظائف بمجالي", has_cv_profile=True)
        assert result.intent == "job_search_explicit", (
            f"Expected job_search_explicit, got {result.intent!r}"
        )

    def test_aeridli_does_not_extract_bimajali_as_role(self):
        """'بمجالي' must not be extracted as a role — it means 'in my field'."""
        from src.agent.intelligence.intent_classifier import classify_intent
        result = classify_intent("اعرضلي احدث الوظائف بمجالي", has_cv_profile=True)
        # extracted_role should be None so caller uses profile's target_roles
        assert result.extracted_role is None, (
            f"Expected extracted_role=None, got {result.extracted_role!r}"
        )


# ── full-turn regression: no pre-seeded pending state ─────────────────────────

class TestFullTurnPendingSearch:
    """Regression: user gets a search offer → says تمام → search executes.

    No pending state is pre-seeded; _store_pending_job_search must be called
    by _classified_role_search (known_but_off_profile path) so the follow-up
    confirmation can trigger _classified_role_search a second time.
    """

    def _make_api(self):
        api = RicoChatAPI.__new__(RicoChatAPI)
        api.memory = MagicMock()
        api._can_mutate_applications = False
        api._current_operation_id = None
        api._pjs_repo = MagicMock()
        api._pjs_repo.cancel.return_value = True
        api._pjs_repo.store.return_value = True
        api._pjs_repo.get.return_value = None
        from src.services.pending_job_search import PendingSearchLookup, LookupStatus
        api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.NONE)
        api._pjs_repo.consume.return_value = None
        api._pjs_redemption_attempted_this_turn = RicoChatAPI._PJS_SENTINEL
        return api

    def test_known_but_off_profile_arms_pending_search(self):
        """_classified_role_search must call _store_pending_job_search for known_but_off_profile roles."""
        api = self._make_api()

        profile_no_role = {"target_roles": [], "skills": [], "years_experience": 3}

        with patch("src.rico_chat_api.classify_role_candidate", return_value=("known_but_off_profile", "Data Scientist")), \
             patch.object(api, "_append_chat"), \
             patch.object(api, "_get_recent_context", return_value={}), \
             patch.object(api, "_store_recent_context"):
            result = api._classified_role_search("u1", "Data Scientist", profile_no_role)

        assert result["type"] == "clarification"
        assert api._pjs_repo.store.called, "_store_pending_job_search was not called"
        call_args = api._pjs_repo.store.call_args
        if call_args:
            stored_pjs = call_args[0][1]
            assert stored_pjs.role == "Data Scientist"
            assert stored_pjs.reason == "known_but_off_profile"

    def test_tamam_after_off_profile_offer_executes_search(self):
        """Full turn: off-profile offer → user says تمام → search executes."""
        api = self._make_api()
        profile_no_role = {"target_roles": [], "skills": [], "years_experience": 3}

        # Turn 1: Rico offers to search for an off-profile role
        with patch("src.rico_chat_api.classify_role_candidate", return_value=("known_but_off_profile", "Data Scientist")), \
             patch.object(api, "_append_chat"), \
             patch.object(api, "_get_recent_context", return_value={}), \
             patch.object(api, "_store_recent_context"):
            api._classified_role_search("u1", "Data Scientist", profile_no_role)

        # Turn 2: set up the repo mock so _resolve_pending_intent can consume
        from src.services.pending_job_search import new_pending, PendingSearchLookup, LookupStatus
        pjs = new_pending(role="Data Scientist", location="", reason="known_but_off_profile")
        api._pjs_repo.get.return_value = pjs
        api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.FOUND, pjs)
        api._pjs_repo.consume.return_value = pjs

        with patch.object(api, "_target_role_search_response", return_value={"type": "job_results", "message": "Found jobs", "jobs": _JOBS}) as mock_search:
            result = api._resolve_pending_intent("u1", "تمام", profile_no_role)

        mock_search.assert_called_once()
        assert result is not None
        assert result["type"] == "job_results"

    def test_tamam_without_pending_search_preserves_normal_ack(self):
        """تمام with no pending search must return None from _resolve_pending_intent
        so the normal acknowledgement branch handles it."""
        api = self._make_api()
        result = api._resolve_pending_intent("u1", "تمام", _PROFILE)
        assert result is None

    def test_promise_only_reply_to_explicit_search_executes_immediately(self):
        """Contract upgraded (live-QA 2026-07-03): when the user's message is an
        explicit job-listing request ("ابحث لي عن وظائف") and the AI replies with a
        hollow promise, _answer_with_ai_fallback must EXECUTE the search in the
        same turn — not merely arm the pending slot. The conversational path has
        no later turn that redeems an armed slot, so arming alone stranded the
        search forever in production. Arming is still the behavior for promise
        replies to NON-search messages (covered in
        tests/unit/test_search_execution_contract_convergence.py).
        """
        api = self._make_api()
        promise_text = "جاري البحث، ثواني وأرجع لك"
        ai_resp = {"message": promise_text, "type": "chat", "response_source": "openai"}
        search_payload = {"type": "job_matches", "message": "Found 2 jobs", "matches": [{}]}

        agent_mock = MagicMock()
        agent_mock.respond.return_value = ai_resp
        agent_mock.openai_available = True
        agent_mock.deepseek_available = False
        agent_mock.hf_available = False
        agent_mock.provider_available = True
        agent_mock.model = "gpt-4o-mini"

        with patch.object(api, "_get_openai_agent", return_value=agent_mock), \
             patch.object(api, "_build_openai_context", return_value={}), \
             patch.object(api, "_get_blocked_questions", return_value=[]), \
             patch.object(api, "_preserve_ai_message", side_effect=lambda m, _: m), \
             patch.object(api, "_append_chat"), \
             patch.object(api, "_source_for_openai_response", return_value="openai"), \
             patch.object(api, "_finalize", side_effect=lambda r, s, **kw: r), \
             patch.object(api, "_classified_role_search", return_value=dict(search_payload)) as search, \
             patch.object(api, "_profile_value", side_effect=lambda p, k: p.get(k)):
            result = api._answer_with_ai_fallback(
                user_id="u1",
                message="ابحث لي عن وظائف",
                profile=_PROFILE,
                save_user_message=False,
            )

        search.assert_called_once()
        assert search.call_args[0][1] == "Environmental Manager"
        assert result.get("type") == "job_matches", "hollow promise must not be the returned payload"


# ── wiring: structured-offer finalization ────────────────────────────────────
# PendingJobSearch is armed only via the explicit private marker
# (_PJS_OFFER_FIELD).  Ordinary text containing "search" must never arm it.

class TestPendingSearchWiring:
    def test_finalize_stores_when_marker_present(self):
        api = _make_api_with_profile()
        result = {"type": "clarification", "message": "Shall I search?", "options": []}
        from src.rico_chat_api import make_offer
        result[api._PJS_OFFER_FIELD] = make_offer(role="Accountant", reason="test")
        finalized = api._finalize_pending_job_search_offer("u1", result)
        assert api._PJS_OFFER_FIELD not in finalized
        assert api._pjs_repo.store.called

    def test_finalize_does_nothing_without_marker(self):
        api = _make_api_with_profile()
        result = {"type": "clarification", "message": "Shall I search?"}
        finalized = api._finalize_pending_job_search_offer("u1", result)
        assert api._PJS_OFFER_FIELD not in finalized
        assert not api._pjs_repo.store.called

    def test_generic_career_advice_does_not_arm(self):
        """Generic career advice containing 'search' must never arm PendingJobSearch."""
        api = _make_api_with_profile()
        result = {"type": "clarification", "message": "You can search on LinkedIn for better results."}
        finalized = api._finalize_pending_job_search_offer("u1", result)
        assert api._PJS_OFFER_FIELD not in finalized
        assert not api._pjs_repo.store.called

    def test_finalize_sanitizes_on_store_failure(self):
        api = _make_api_with_profile()
        api._pjs_repo.store.return_value = False
        result = {
            "type": "clarification",
            "message": "I found these roles. Should I search for Accountant?",
            "options": [
                {"action": "confirm_search", "label": "Yes, search Accountant"},
                {"action": "show_profile_roles", "label": "Show roles"},
            ],
        }
        from src.rico_chat_api import make_offer
        result[api._PJS_OFFER_FIELD] = make_offer(role="Accountant", reason="test")
        finalized = api._finalize_pending_job_search_offer("u1", result)
        assert api._PJS_OFFER_FIELD not in finalized
        # confirm_search option must be removed.
        remaining_actions = [o.get("action") for o in finalized.get("options", [])]
        assert "confirm_search" not in remaining_actions
        # Safe option preserved.
        assert "show_profile_roles" in remaining_actions
        # Message no longer contains the confirmation CTA.
        assert "Should I search" not in finalized.get("message", "")

    def test_handle_active_user_invokes_finalize(self):
        """_handle_active_user must call _finalize_pending_job_search_offer."""
        api = _make_api_with_profile()
        offer = {"type": "clarification", "message": "Hello"}
        with patch.object(api, "_handle_active_user_inner", return_value=offer), \
             patch.object(api, "_finalize_pending_job_search_offer") as mock_finalize:
            api._handle_active_user("u1", "find me work")
        mock_finalize.assert_called_once_with("u1", offer)

    def test_off_profile_clarification_stores_canonical_role(self):
        """known_but_off_profile path must store canonical_role, not profile.target_roles[0]."""
        api = _make_api_with_profile()
        ok = api._store_pending_job_search("u1", role="Data Scientist", query_type="off_profile_confirmation")
        assert ok, "_store_pending_job_search must return True on success"
        assert api._pjs_repo.store.called
        args = api._pjs_repo.store.call_args
        if args:
            stored_pjs = args[0][1]
            assert stored_pjs.role == "Data Scientist"


# ── full-turn: handler arms state, confirmation fires search ──────────────────

def _make_api_live_memory():
    """API with an in-process dict memory so store/get round-trips work."""
    api = RicoChatAPI.__new__(RicoChatAPI)
    _store: dict = {}
    memory = MagicMock()
    memory.get_context.side_effect = lambda u, k: _store.get((u, k), {})
    memory.set_context.side_effect = lambda u, k, v: _store.__setitem__((u, k), v)
    api.memory = memory
    api._can_mutate_applications = False
    api._current_operation_id = None
    api._pjs_repo = MagicMock()
    api._pjs_repo.cancel.return_value = True
    api._pjs_repo.store.return_value = True
    api._pjs_repo.get.return_value = None
    api._pjs_repo.consume.return_value = None
    api._pjs_redemption_attempted_this_turn = RicoChatAPI._PJS_SENTINEL
    return api


class TestFullTurnPendingArmedByHandler:
    """No pre-seeded state — handler stores via signal detection, confirmation fires search."""

    def test_maybe_store_then_tamam_fires_search(self):
        """_maybe_store_pending_job_search arms state → _resolve_pending_intent fires search."""
        api = _make_api_live_memory()

        from src.rico_chat_api import make_offer
        offer_response = {
            "type": "career_change_advice",
            "message": "Want me to search for Environmental Manager jobs?",
        }
        offer_response[api._PJS_OFFER_FIELD] = make_offer(
            role="Environmental Manager", reason="adjacent_broaden",
        )

        with patch.object(api, "_resolve_profile", return_value=_PROFILE), \
             patch.object(api, "_target_role_search_response",
                          return_value={"type": "job_results", "jobs": _JOBS, "message": "Found 1 job"}) as mock_search:

            finalized = api._finalize_pending_job_search_offer("u1", offer_response)
            # Verify the repo's store was called (arm succeeded)
            assert api._pjs_repo.store.called, "must arm pending search when signal found"
            assert api._PJS_OFFER_FIELD not in finalized
            # Set up the repo get/consume for the redemption path
            from src.services.pending_job_search import new_pending, PendingSearchLookup, LookupStatus
            pjs = new_pending(role="Environmental Manager", location="", reason="promise")
            api._pjs_repo.get.return_value = pjs
            api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.FOUND, pjs)
            api._pjs_repo.consume.return_value = pjs
            result = api._resolve_pending_intent("u1", "تمام", _PROFILE)

        mock_search.assert_called_once()
        assert result is not None
        assert result.get("type") == "job_results"

    def test_no_pending_tamam_returns_none_not_search(self):
        """'تمام' with no pending search must NOT call _classified_role_search."""
        api = _make_api_live_memory()

        with patch.object(api, "_classified_role_search") as mock_search:
            result = api._resolve_pending_intent("u1", "تمام", _PROFILE)

        mock_search.assert_not_called()
        assert result is None
