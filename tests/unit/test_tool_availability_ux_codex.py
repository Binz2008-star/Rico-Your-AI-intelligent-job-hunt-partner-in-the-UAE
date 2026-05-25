"""Unit tests for Codex P1/P2 fixes on PR #231 tool-availability UX.

Tests the three helper functions directly — no FastAPI, no send_message.
"""
from unittest.mock import MagicMock

from src.services.chat_service import (
    _unsupported_tool_message,
    _mixed_tool_clarification_response,
    _continue_message_from_reason,
)


def _policy(domain_value="email_gmail_request", lang="en", suggestion=""):
    domain = MagicMock()
    domain.value = domain_value
    p = MagicMock()
    p.domain = domain
    p.language = lang
    p.alternative_suggestion = suggestion
    p.reason = f"unsupported_{domain_value}"
    return p


def _clarification_policy(reason="conflicting_domains:email_gmail_request_vs_job_search", lang="en"):
    p = MagicMock()
    p.language = lang
    p.reason = reason
    p.alternative_suggestion = ""
    return p


# ── P1: _unsupported_tool_message language gate ───────────────────────────────

def test_english_gmail_returns_rich_english_message():
    p = _policy("email_gmail_request", lang="en")
    msg = _unsupported_tool_message(p)
    assert "Gmail" in msg
    assert "Paste" in msg or "paste" in msg


def test_arabic_gmail_returns_policy_arabic_suggestion():
    arabic_msg = "لا أستطيع الوصول إلى Gmail"
    p = _policy("email_gmail_request", lang="ar", suggestion=arabic_msg)
    msg = _unsupported_tool_message(p)
    assert msg == arabic_msg


def test_arabic_no_suggestion_returns_arabic_fallback():
    p = _policy("email_gmail_request", lang="ar", suggestion="")
    msg = _unsupported_tool_message(p)
    assert "لا أستطيع" in msg


def test_english_linkedin_returns_rich_english_message():
    p = _policy("linkedin_request", lang="en")
    msg = _unsupported_tool_message(p)
    assert "LinkedIn" in msg


def test_arabic_whatsapp_returns_policy_suggestion_not_english():
    arabic_msg = "لا أستطيع إرسال رسائل واتساب"
    p = _policy("whatsapp_request", lang="ar", suggestion=arabic_msg)
    msg = _unsupported_tool_message(p)
    assert msg == arabic_msg
    assert "WhatsApp" not in msg  # must not return the English hardcoded string


def test_english_unknown_domain_falls_back_to_suggestion():
    p = _policy("some_new_tool", lang="en", suggestion="Try another way.")
    msg = _unsupported_tool_message(p)
    assert msg == "Try another way."


# ── P2: _continue_message_from_reason maps supported side ─────────────────────

def test_continue_action_job_search():
    assert _continue_message_from_reason("conflicting_domains:email_gmail_request_vs_job_search") \
        == "find live jobs for my target role"


def test_continue_action_application_tracking():
    assert _continue_message_from_reason("conflicting_domains:email_gmail_request_vs_application_tracking") \
        == "show my applications"


def test_continue_action_cv_profile():
    assert _continue_message_from_reason("conflicting_domains:email_gmail_request_vs_cv_profile") \
        == "show my profile"


def test_continue_action_profile_variant():
    assert _continue_message_from_reason("conflicting_domains:whatsapp_request_vs_profile_update") \
        == "show my profile"


def test_continue_action_unknown_defaults_to_job_search():
    assert _continue_message_from_reason("conflicting_domains:unknown_vs_unknown") \
        == "find live jobs for my target role"


# ── P2: mixed-request clarification respects language ─────────────────────────

def test_english_mixed_clarification_message_is_english():
    p = _clarification_policy(lang="en")
    result = _mixed_tool_clarification_response(p, "fetch my Gmail and find HSE jobs")
    assert "mixes" in result["message"] or "can't" in result["message"].lower()
    assert result["type"] == "clarification"
    assert result["intent"] == "mixed_request"


def test_arabic_mixed_clarification_message_is_arabic():
    p = _clarification_policy(
        reason="conflicting_domains:linkedin_request_vs_application_tracking", lang="ar"
    )
    result = _mixed_tool_clarification_response(p, "افحص لينكد إن وأضف الوظيفة")
    assert "لا أستطيع" in result["message"] or "هذا الطلب" in result["message"]
    assert result["type"] == "clarification"


def test_mixed_continue_option_uses_dynamic_action():
    p = _clarification_policy(
        reason="conflicting_domains:email_gmail_request_vs_application_tracking", lang="en"
    )
    result = _mixed_tool_clarification_response(p, "check Gmail for my application")
    continue_opt = next(
        (o for o in result["options"] if o["action"] == "continue_without_external_tool"), None
    )
    assert continue_opt is not None
    assert continue_opt["message"] == "show my applications"


def test_mixed_email_job_search_english_clarification():
    p = _clarification_policy(
        reason="conflicting_domains:email_gmail_request_vs_job_search", lang="en"
    )
    result = _mixed_tool_clarification_response(p, "fetch my Gmail and find HSE jobs")
    assert "Gmail" in result["message"]
    assert result["next_action"] == "choose_supported_path"


def test_mixed_email_job_search_arabic_clarification():
    p = _clarification_policy(
        reason="conflicting_domains:email_gmail_request_vs_job_search", lang="ar"
    )
    result = _mixed_tool_clarification_response(p, "افحص إيميلي وابحث عن وظيفة")
    assert "Gmail" in result["message"]  # product name stays
    assert "لا أستطيع" in result["message"]
    assert result["next_action"] == "choose_supported_path"
