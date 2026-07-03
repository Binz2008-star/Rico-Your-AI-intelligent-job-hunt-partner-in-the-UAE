"""
P0 regression tests for job-search action contract.

Ensures Rico never emits promise-only replies for job-search contexts and
always executes the search when the user confirms a pending job-search.
"""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import time
import pytest

from src.rico_chat_api import RicoChatAPI


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


def _make_api_with_profile(pending_job_search=None):
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


# ── pending job search state ────────────────────────────────────────────────────

class TestPendingJobSearchState:
    def test_store_and_retrieve(self):
        api = _make_api_with_profile()
        stored = {}
        api.memory.set_context.side_effect = lambda u, k, v: stored.__setitem__((u, k), v)
        api._store_pending_job_search("u1", role="Environmental Manager", location="Dubai")
        val = stored.get(("u1", RicoChatAPI._PENDING_JOB_SEARCH_KEY))
        assert val is not None
        assert val["role"] == "Environmental Manager"
        assert val["location"] == "Dubai"
        assert "expires_at" in val

    def test_expired_state_returns_empty(self):
        api = _make_api_with_profile()
        api.memory.get_context.side_effect = lambda u, k: {
            "role": "HSE Manager",
            "expires_at": int(time.time()) - 1,  # already expired
        }
        result = api._get_pending_job_search("u1")
        assert result == {}

    def test_clear_pending_state(self):
        api = _make_api_with_profile()
        api._clear_pending_job_search("u1")
        api.memory.set_context.assert_called_once_with(
            "u1", RicoChatAPI._PENDING_JOB_SEARCH_KEY, {}
        )


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
            "query_type": "profile_based",
            "created_at": int(time.time()),
            "expires_at": int(time.time()) + 900,
        }
        api = _make_api_with_profile(pending_job_search=pending)

        with patch.object(api, "_classified_role_search", return_value={"type": "job_results", "jobs": _JOBS, "message": "Found 1 job"}) as mock_search, \
             patch.object(api, "_clear_pending_job_search") as mock_clear:
            result = api._resolve_pending_intent(
                user_id="u1",
                message="تمام",
                profile=_PROFILE,
            )

        mock_clear.assert_called_once_with("u1")
        mock_search.assert_called_once()
        assert result["type"] == "job_results"

    def test_tamam_does_not_return_good_luck(self):
        pending = {
            "role": "Environmental Manager",
            "location": "",
            "query_type": "profile_based",
            "created_at": int(time.time()),
            "expires_at": int(time.time()) + 900,
        }
        api = _make_api_with_profile(pending_job_search=pending)
        with patch.object(api, "_classified_role_search", return_value={"type": "job_results", "jobs": _JOBS, "message": "Found 1 job"}):
            result = api._resolve_pending_intent("u1", "تمام", _PROFILE)
        # Must not contain good-luck or conversation-close phrases
        msg = result.get("message", "").lower()
        assert "بالتوفيق" not in msg
        assert "good luck" not in msg

    def test_ok_english_also_continues_pending_job_search(self):
        pending = {
            "role": "HSE Manager",
            "location": "Abu Dhabi",
            "query_type": "profile_based",
            "created_at": int(time.time()),
            "expires_at": int(time.time()) + 900,
        }
        api = _make_api_with_profile(pending_job_search=pending)
        with patch.object(api, "_classified_role_search", return_value={"type": "job_results", "jobs": _JOBS, "message": "Found 1 job"}) as mock_search:
            api._resolve_pending_intent("u1", "ok", _PROFILE)
        mock_search.assert_called_once()


# ── no promise-only replies ────────────────────────────────────────────────────

class TestNoPromiseOnlyReplies:
    def test_promise_only_pattern_detection(self):
        for phrase in ["جاري البحث", "ببحث الآن", "ثواني", "انتظرني", "لحظة"]:
            assert RicoChatAPI._is_promise_only_reply(phrase), f"{phrase!r} should be detected as promise-only"

    def test_resolve_pending_intent_never_emits_promise_only(self):
        """When job search signals exist in last turn, resolve must not emit a promise-only reply."""
        pending = {
            "role": "Environmental Manager",
            "location": "",
            "query_type": "profile_based",
            "created_at": int(time.time()),
            "expires_at": int(time.time()) + 900,
        }
        api = _make_api_with_profile(pending_job_search=pending)
        with patch.object(api, "_classified_role_search", return_value={"type": "job_results", "jobs": [], "message": "لم أجد وظائف متاحة الآن"}):
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
        pending = {
            "role": "Environmental Manager",
            "location": "",
            "query_type": "profile_based",
            "created_at": int(time.time()),
            "expires_at": int(time.time()) + 900,
        }
        api = _make_api_with_profile(pending_job_search=pending)
        # Simulate provider failure by mocking _classified_role_search to return error response
        error_resp = {
            "type": "error",
            "message": "بحثت لكن مزود الوظائف لم يرجع نتائج صالحة الآن.",
            "jobs": [],
        }
        with patch.object(api, "_classified_role_search", return_value=error_resp):
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
        memory = MagicMock()
        _store: dict = {}

        def _get(user_id, key):
            return _store.get((user_id, key), {})

        def _set(user_id, key, value):
            _store[(user_id, key)] = value

        memory.get_context.side_effect = _get
        memory.set_context.side_effect = _set
        api.memory = memory
        api._store = _store  # expose for assertions
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
        stored = api._store.get(("u1", RicoChatAPI._PENDING_JOB_SEARCH_KEY))
        assert stored is not None, "_store_pending_job_search was not called for known_but_off_profile"
        assert stored["role"] == "Data Scientist"
        assert stored["query_type"] == "known_but_off_profile"

    def test_tamam_after_off_profile_offer_executes_search(self):
        """Full turn: off-profile offer → user says تمام → _classified_role_search runs."""
        api = self._make_api()
        profile_no_role = {"target_roles": [], "skills": [], "years_experience": 3}

        # Turn 1: Rico offers to search for an off-profile role
        with patch("src.rico_chat_api.classify_role_candidate", return_value=("known_but_off_profile", "Data Scientist")), \
             patch.object(api, "_append_chat"), \
             patch.object(api, "_get_recent_context", return_value={}), \
             patch.object(api, "_store_recent_context"):
            api._classified_role_search("u1", "Data Scientist", profile_no_role)

        # Turn 2: user replies تمام — pending state must now trigger the search
        with patch.object(api, "_classified_role_search", return_value={"type": "job_results", "message": "Found jobs", "jobs": _JOBS}) as mock_search:
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
        # Slot must be left cleared — the search already ran.
        stored = api._store.get(("u1", RicoChatAPI._PENDING_JOB_SEARCH_KEY))
        assert not stored, "pending slot must not remain armed after immediate execution"


# ── wiring: search-offer responses store a pending search ─────────────────────
# Regression for the gap where _store_pending_job_search() was defined but never
# called in src/, so the "تمام" confirmation path could never fire in production.

class TestPendingSearchWiring:
    def test_offer_response_stores_pending_with_profile_role(self):
        api = _make_api_with_profile()
        with patch.object(api, "_resolve_profile", return_value=_PROFILE), \
             patch.object(api, "_store_pending_job_search") as mock_store:
            api._maybe_store_pending_job_search(
                "u1",
                {"type": "clarification", "message": "Shall I search for live jobs now?"},
            )
        mock_store.assert_called_once()
        assert mock_store.call_args.kwargs.get("role") == "Environmental Manager"

    def test_arabic_offer_response_stores_pending(self):
        api = _make_api_with_profile()
        with patch.object(api, "_resolve_profile", return_value=_PROFILE), \
             patch.object(api, "_store_pending_job_search") as mock_store:
            api._maybe_store_pending_job_search(
                "u1",
                {"type": "clarification", "message": "تمام، سأبحث عن وظائف مناسبة لك."},
            )
        mock_store.assert_called_once()

    def test_executed_search_result_does_not_store(self):
        api = _make_api_with_profile()
        with patch.object(api, "_resolve_profile", return_value=_PROFILE), \
             patch.object(api, "_store_pending_job_search") as mock_store:
            api._maybe_store_pending_job_search(
                "u1",
                {"type": "job_matches", "message": "Found 5 roles for you."},
            )
        mock_store.assert_not_called()

    def test_non_offer_response_does_not_store(self):
        api = _make_api_with_profile()
        with patch.object(api, "_resolve_profile", return_value=_PROFILE), \
             patch.object(api, "_store_pending_job_search") as mock_store:
            api._maybe_store_pending_job_search(
                "u1",
                {"type": "acknowledgement", "message": "You're welcome!"},
            )
        mock_store.assert_not_called()

    def test_offer_without_target_roles_does_not_store(self):
        api = _make_api_with_profile()
        with patch.object(api, "_resolve_profile", return_value={"target_roles": []}), \
             patch.object(api, "_store_pending_job_search") as mock_store:
            api._maybe_store_pending_job_search(
                "u1",
                {"type": "clarification", "message": "Shall I search for roles?"},
            )
        mock_store.assert_not_called()

    def test_handle_active_user_invokes_wiring(self):
        """_handle_active_user must call the wiring on every active-user turn."""
        api = _make_api_with_profile()
        offer = {"type": "clarification", "message": "Shall I search for live jobs?"}
        with patch.object(api, "_handle_active_user_inner", return_value=offer), \
             patch.object(api, "_maybe_store_pending_job_search") as mock_wire:
            api._handle_active_user("u1", "find me work")
        mock_wire.assert_called_once_with("u1", offer)

    def test_arabic_career_change_offer_signal_matched(self):
        """Arabic 'هل تريد البحث' must be in _SEARCH_OFFER_SIGNALS."""
        assert "هل تريد البحث" in RicoChatAPI._SEARCH_OFFER_SIGNALS

    def test_should_i_search_signal_matched(self):
        """English 'should i search' (known_but_off_profile) must be in _SEARCH_OFFER_SIGNALS."""
        assert "should i search" in RicoChatAPI._SEARCH_OFFER_SIGNALS

    def test_off_profile_clarification_stores_canonical_role(self):
        """known_but_off_profile path must store canonical_role, not profile.target_roles[0]."""
        api = _make_api_with_profile()
        stored_calls: list = []
        api.memory.set_context.side_effect = lambda u, k, v: stored_calls.append((u, k, v))
        with patch.object(api, "_append_chat"), \
             patch.object(api, "_get_recent_context", return_value={}), \
             patch.object(api, "_store_recent_context"):
            api._store_pending_job_search("u1", role="Data Scientist", query_type="off_profile_confirmation")
        stored = next((v for u, k, v in stored_calls if k == RicoChatAPI._PENDING_JOB_SEARCH_KEY), None)
        assert stored is not None
        assert stored["role"] == "Data Scientist"


# ── full-turn: handler arms state, confirmation fires search ──────────────────

def _make_api_live_memory():
    """API with an in-process dict memory so store/get round-trips work."""
    api = RicoChatAPI.__new__(RicoChatAPI)
    _store: dict = {}
    memory = MagicMock()
    memory.get_context.side_effect = lambda u, k: _store.get((u, k), {})
    memory.set_context.side_effect = lambda u, k, v: _store.__setitem__((u, k), v)
    api.memory = memory
    return api


class TestFullTurnPendingArmedByHandler:
    """No pre-seeded state — handler stores via signal detection, confirmation fires search."""

    def test_maybe_store_then_tamam_fires_search(self):
        """_maybe_store_pending_job_search arms state → _resolve_pending_intent fires search."""
        api = _make_api_live_memory()

        offer_response = {
            "type": "career_change_advice",
            "message": "Want me to search for Environmental Manager jobs?",
        }

        with patch.object(api, "_resolve_profile", return_value=_PROFILE), \
             patch.object(api, "_classified_role_search",
                          return_value={"type": "job_results", "jobs": _JOBS, "message": "Found 1 job"}) as mock_search:

            api._maybe_store_pending_job_search("u1", offer_response)
            assert api._get_pending_job_search("u1").get("role"), (
                "_maybe_store_pending_job_search must arm a pending search when signal found"
            )
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
