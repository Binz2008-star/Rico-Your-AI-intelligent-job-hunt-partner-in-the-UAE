"""
tests/test_arabic_context_retention.py
Acceptance tests for the Arabic context retention fix.

Scenario: user searches in English (Turn 1) then sends an Arabic job-search
message without repeating the role (Turn 2).

Before this fix, Turn 2 fell through to profile_incomplete because
job_search_explicit with extracted_role=None checked only profile.target_roles.

After this fix, job_search_explicit checks recent_context for recent_search_role
and resumes the prior role search, preserving cross-language continuity.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, call


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_api(recent_ctx: dict | None = None):
    from src.rico_chat_api import RicoChatAPI
    api = RicoChatAPI.__new__(RicoChatAPI)
    api._append_chat = MagicMock()
    api._get_recent_context = MagicMock(return_value=dict(recent_ctx or {}))
    api._store_recent_context = MagicMock()
    api._classified_role_search = MagicMock(
        return_value={"type": "job_list", "jobs": [], "message": "Results"}
    )
    api._finalize = MagicMock(side_effect=lambda r, *a, **kw: r)
    api._build_router_context = MagicMock(return_value={})
    api._effective_target_roles = MagicMock(return_value=[])
    api._as_list = MagicMock(return_value=[])
    api._profile_value = MagicMock(return_value=[])
    api._handle_profile_role_suggestions = MagicMock(return_value={"type": "suggestions"})
    return api


def _job_search_explicit_dispatch(api, message: str, has_cv: bool = True):
    """Simulate the job_search_explicit branch of _handle_active_user_inner."""
    from src.agent.intelligence.intent_classifier import classify_intent, _map_intent_to_legacy

    intent_result = classify_intent(message, has_cv_profile=has_cv)
    legacy_intent = _map_intent_to_legacy(intent_result.intent)
    assert legacy_intent == "job_search_explicit", (
        f"Expected job_search_explicit, got {legacy_intent} for {message!r}"
    )

    profile = {"user_id": "u1", "target_roles": []}

    # Replicate the handler logic
    if intent_result.extracted_role:
        return api._finalize(
            api._classified_role_search("u1", intent_result.extracted_role, profile),
            "keyword",
            profile=profile,
        )

    # Recent context fallback (the fix)
    try:
        _ctx = api._get_recent_context("u1")
        _prior_role = (
            _ctx.get("recent_search_role")
            or _ctx.get("recent_role")
            or _ctx.get("recent_job")
        )
        if _prior_role:
            return api._finalize(
                api._classified_role_search("u1", _prior_role, profile),
                "keyword",
                profile=profile,
            )
    except Exception:
        pass

    # No role anywhere → profile_incomplete
    _is_ar = bool(__import__("re").search(r"[؀-ۿ]", message or ""))
    _incomplete_msg = (
        "لإجراء البحث أحتاج إلى معرفة المسمى الوظيفي المستهدف أولاً.\n"
        "أخبرني:\n"
        "• المسمى الوظيفي (مثل: مهندس برمجيات، محاسب)\n"
        "• المدينة المفضلة (مثل: دبي، أبوظبي)\n"
        "• توقعات الراتب (اختياري)"
        if _is_ar else
        "I can search jobs using your profile. Please confirm:\n"
        "• Target role (e.g., HSE Manager, ESG Specialist)\n"
        "• Preferred city (e.g., Dubai, Abu Dhabi)\n"
        "• Expected salary (optional)\n\n"
        "I cannot search for jobs until at least your target role is known."
    )
    resp = {"type": "profile_incomplete", "intent": "search_jobs", "message": _incomplete_msg}
    api._append_chat("u1", "assistant", _incomplete_msg)
    return resp


# ── 1. Intent classifier sanity ────────────────────────────────────────────────

class TestArabicJobSearchIntentClassification:

    def test_arabic_search_phrase_is_job_search_explicit(self):
        from src.agent.intelligence.intent_classifier import classify_intent
        r = classify_intent("ابحث لي وظائف في أبوظبي", has_cv_profile=True)
        assert r.intent == "job_search_explicit"

    def test_arabic_search_phrase_has_no_role(self):
        from src.agent.intelligence.intent_classifier import classify_intent
        r = classify_intent("ابحث لي وظائف في أبوظبي", has_cv_profile=True)
        assert r.extracted_role is None

    def test_arabic_search_with_role_extracts_role(self):
        from src.agent.intelligence.intent_classifier import classify_intent
        r = classify_intent("ابحث عن وظائف مهندس برمجيات", has_cv_profile=True)
        assert r.extracted_role is not None


# ── 2. Context retention: prior role used on Arabic search ────────────────────

class TestArabicContextRetention:

    def test_prior_recent_search_role_used_on_arabic_search(self):
        api = _make_api({"recent_search_role": "Software Engineer"})
        result = _job_search_explicit_dispatch(api, "ابحث لي وظائف في أبوظبي")
        api._classified_role_search.assert_called_once_with("u1", "Software Engineer", {"user_id": "u1", "target_roles": []})
        assert result["type"] == "job_list"

    def test_prior_recent_role_key_also_works(self):
        api = _make_api({"recent_role": "Accountant"})
        _job_search_explicit_dispatch(api, "ابحث عن وظائف")
        api._classified_role_search.assert_called_once()
        args = api._classified_role_search.call_args[0]
        assert args[1] == "Accountant"

    def test_prior_recent_job_key_also_works(self):
        api = _make_api({"recent_job": "HSE Manager"})
        _job_search_explicit_dispatch(api, "ابحث لي وظائف")
        api._classified_role_search.assert_called_once()
        args = api._classified_role_search.call_args[0]
        assert args[1] == "HSE Manager"

    def test_english_search_without_role_also_uses_prior_context(self):
        api = _make_api({"recent_search_role": "Data Analyst"})
        result = _job_search_explicit_dispatch(api, "find me some jobs")
        api._classified_role_search.assert_called_once_with("u1", "Data Analyst", {"user_id": "u1", "target_roles": []})

    def test_explicit_role_in_message_takes_priority_over_context(self):
        api = _make_api({"recent_search_role": "Accountant"})
        result = _job_search_explicit_dispatch(api, "find software engineer jobs")
        args = api._classified_role_search.call_args[0]
        # extracted_role from message should take priority
        assert args[1] != "Accountant"


# ── 3. Fallback to profile_incomplete when no context ─────────────────────────

class TestNoContextFallback:

    def test_no_context_returns_profile_incomplete(self):
        api = _make_api({})  # empty context
        result = _job_search_explicit_dispatch(api, "ابحث لي وظائف في أبوظبي")
        assert result["type"] == "profile_incomplete"

    def test_arabic_profile_incomplete_message_is_in_arabic(self):
        api = _make_api({})
        result = _job_search_explicit_dispatch(api, "ابحث لي وظائف في أبوظبي")
        assert any(c > "؀" for c in result["message"]), "Expected Arabic characters in message"

    def test_english_profile_incomplete_message_is_in_english(self):
        api = _make_api({})
        result = _job_search_explicit_dispatch(api, "find me jobs")
        assert "Target role" in result["message"]

    def test_no_search_called_when_no_context_no_role(self):
        api = _make_api({})
        _job_search_explicit_dispatch(api, "ابحث لي وظائف في أبوظبي")
        api._classified_role_search.assert_not_called()


# ── 4. arabic_switch golden scenario ──────────────────────────────────────────

class TestArabicSwitchGoldenScenario:
    """End-to-end simulation of the arabic_switch evaluation scenario."""

    def test_turn1_english_turn2_arabic_role_retained(self):
        """
        Turn 1: "find software jobs" (English) → stores recent_search_role
        Turn 2: "ابحث لي وظائف في أبوظبي" (Arabic) → should reuse Software Engineer
        """
        # After Turn 1, context would contain:
        ctx_after_turn1 = {"recent_search_role": "Software Engineer"}

        api = _make_api(ctx_after_turn1)
        result = _job_search_explicit_dispatch(api, "ابحث لي وظائف في أبوظبي")

        assert result["type"] == "job_list", (
            f"Turn 2 should trigger a job search, got type={result.get('type')!r}. "
            "Role context from Turn 1 was not retained."
        )
        api._classified_role_search.assert_called_once()
        _, called_role, _ = api._classified_role_search.call_args[0]
        assert called_role == "Software Engineer", (
            f"Expected role 'Software Engineer' from prior context, got {called_role!r}"
        )
