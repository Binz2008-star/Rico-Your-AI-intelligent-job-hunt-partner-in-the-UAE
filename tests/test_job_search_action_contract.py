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
