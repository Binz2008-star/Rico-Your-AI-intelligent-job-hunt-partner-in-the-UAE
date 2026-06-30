"""
tests/test_bug12_arabic_search_locale.py

Regression tests for BUG-12 — search results body ignores Arabic locale.

Problem: _target_role_search_response and _build_role_search_message were
English-only.  Arabic-speaking users received "Got it — I will target …"
and "I couldn't retrieve live jobs right now." regardless of their input
language.

Fix: Arabic is auto-detected from the last user message stored in chat
history (_get_recent_messages).  All prose in the search response
(city_text, basis_text, results header, empty-results message,
adjacent-roles offer, rate-limit notice, provider-degraded message) is
then rendered in Arabic when the trigger message is Arabic.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_profile(roles=None, skills=None, cities=None, years=None):
    from types import SimpleNamespace
    return SimpleNamespace(
        user_id="u@example.com",
        target_roles=roles or ["HSE Manager"],
        skills=skills or ["ISO 14001", "safety"],
        certifications=[],
        years_experience=years,
        industries=[],
        preferred_cities=cities or ["Dubai"],
        current_role="HSE Officer",
        has_cv=True,
        deal_breakers=[],
        nationality="",
    )


def _make_api(last_user_message: str):
    """Build a RicoChatAPI with mocked deps; seed last user message for Arabic detection."""
    from src.rico_chat_api import RicoChatAPI
    from src.jsearch_client import FetchResult

    api = RicoChatAPI(persist=False)
    api.memory = MagicMock()
    api.system = MagicMock()
    api.system.run_for_profile.return_value = {"matches": []}
    api.openai_agent = MagicMock()

    # Seed the recent-messages store so Arabic detection works
    api._get_recent_messages = MagicMock(return_value=[
        {"role": "user", "content": last_user_message},
    ])

    return api


# ---------------------------------------------------------------------------
# _build_role_search_message — unit tests (no I/O)
# ---------------------------------------------------------------------------

class TestBuildRoleSearchMessageArabic:
    """_build_role_search_message must return Arabic prose when arabic=True."""

    def _call(self, top_matches, adjacent=None, arabic=False, from_saved=False):
        from src.rico_chat_api import RicoChatAPI
        ri = {"adjacent_roles": [{"role": r} for r in (adjacent or [])]} if adjacent else None
        return RicoChatAPI._build_role_search_message(
            None,  # self not used
            "مدير السلامة",
            " في دبي" if arabic else " in Dubai",
            " بناءً على ملفك الوظيفي" if arabic else " using your CV profile",
            top_matches,
            ri,
            from_saved_profile=from_saved,
            arabic=arabic,
        )

    def test_results_header_arabic(self):
        match = {"job_apply_link": "https://example.com", "title": "HSE Manager", "company": "Acme"}
        msg = self._call([match], arabic=True)
        assert "حسناً" in msg, f"Expected Arabic header in: {msg!r}"
        assert "Got it" not in msg, f"English leaked into Arabic response: {msg!r}"

    def test_results_header_english(self):
        match = {"job_apply_link": "https://example.com", "title": "HSE Manager", "company": "Acme"}
        msg = self._call([match], arabic=False)
        assert "Got it" in msg
        assert "حسناً" not in msg

    def test_empty_results_arabic(self):
        msg = self._call([], arabic=True)
        assert "لم أتمكن" in msg
        assert "I couldn't" not in msg

    def test_empty_results_english(self):
        msg = self._call([], arabic=False)
        assert "I couldn't" in msg

    def test_adjacent_offer_arabic_no_results(self):
        msg = self._call([], adjacent=["QHSE Manager"], arabic=True)
        assert "هل تريد" in msg or "QHSE Manager" in msg
        assert "Want me to" not in msg

    def test_adjacent_offer_english_no_results(self):
        msg = self._call([], adjacent=["QHSE Manager"], arabic=False)
        assert "Want me to also look at" in msg

    def test_adjacent_offer_arabic_with_results(self):
        match = {"job_apply_link": "https://x.com", "title": "T", "company": "C"}
        msg = self._call([match], adjacent=["QHSE Manager"], arabic=True)
        assert "هذه وظائف" in msg or "QHSE Manager" in msg
        assert "These are" not in msg

    def test_from_saved_profile_arabic(self):
        msg = self._call([], from_saved=True, arabic=True)
        assert "دورك المحفوظ" in msg
        assert "saved target role" not in msg


# ---------------------------------------------------------------------------
# Integration: Arabic detection from recent messages
# ---------------------------------------------------------------------------

class TestArabicDetectionFromChatHistory:
    """When last user message is Arabic, the response body must be Arabic."""

    def _run_search(self, last_user_msg: str, matches=None):
        from src.rico_chat_api import RicoChatAPI  # noqa: F401
        from src.jsearch_client import FetchResult as FR

        api = _make_api(last_user_msg)

        _matches = matches if matches is not None else []

        with patch.object(api, "_search_jsearch_meta", return_value=FR(items=_matches)), \
             patch.object(api, "_enrich_with_role_intelligence", return_value=None), \
             patch.object(api, "_begin_job_search_operation", return_value={"operation_id": "op-1"}), \
             patch.object(api, "_append_chat"), \
             patch("src.rico_chat_api.mark_completed", return_value=None), \
             patch("src.rico_chat_api.mark_failed", return_value=None), \
             patch.object(api, "_store_search_matches_context"):
            result = api._target_role_search_response(
                "u@example.com", "HSE Manager", _make_profile()
            )
        return result

    def test_arabic_message_is_arabic(self):
        """Arabic trigger → response message must contain Arabic prose."""
        result = self._run_search("ابحث عن وظائف مدير HSE في دبي")
        msg = result["message"]
        assert any(ord(c) >= 0x0600 for c in msg), (
            f"Response should contain Arabic text when user wrote Arabic: {msg!r}"
        )
        assert "Got it" not in msg, f"English leaked: {msg!r}"

    def test_english_message_is_english(self):
        """English trigger → response message must be English."""
        result = self._run_search("find HSE Manager jobs in Dubai")
        msg = result["message"]
        assert "Got it" in msg, f"Expected 'Got it' in English response: {msg!r}"

    def test_arabic_empty_results_is_arabic(self):
        """Arabic trigger + no results → Arabic empty-results message."""
        result = self._run_search("ابحث عن وظائف مدير HSE", matches=[])
        msg = result["message"]
        assert any(ord(c) >= 0x0600 for c in msg), (
            f"Empty-results message should be Arabic: {msg!r}"
        )
        assert "I couldn't" not in msg

    def test_english_empty_results_is_english(self):
        result = self._run_search("find HSE Manager jobs", matches=[])
        msg = result["message"]
        assert "I couldn't" in msg or "Got it" in msg


# ---------------------------------------------------------------------------
# _provider_degraded_response — Arabic locale
# ---------------------------------------------------------------------------

class TestProviderDegradedArabic:
    """_provider_degraded_response must return Arabic prose when arabic=True."""

    def _call(self, arabic: bool, quota_exhausted=False, rate_limited=False):
        from src.rico_chat_api import RicoChatAPI
        api = RicoChatAPI(persist=False)
        api.memory = MagicMock()
        api.memory.get_context.return_value = None

        with patch.object(api, "_append_chat"), \
             patch.object(api, "_store_pending_job_search"):
            return api._provider_degraded_response(
                "u@example.com", "HSE Manager",
                location="Dubai",
                quota_exhausted=quota_exhausted,
                rate_limited=rate_limited,
                arabic=arabic,
            )

    def test_quota_exhausted_arabic(self):
        result = self._call(arabic=True, quota_exhausted=True)
        assert any(ord(c) >= 0x0600 for c in result["message"])
        assert "quota" not in result["message"]

    def test_quota_exhausted_english(self):
        result = self._call(arabic=False, quota_exhausted=True)
        assert "quota" in result["message"]

    def test_rate_limited_arabic(self):
        result = self._call(arabic=True, rate_limited=True)
        assert any(ord(c) >= 0x0600 for c in result["message"])
        assert "rate-limited" not in result["message"]

    def test_option_labels_arabic(self):
        result = self._call(arabic=True)
        labels = [o["label"] for o in result["options"]]
        assert any(any(ord(c) >= 0x0600 for c in lbl) for lbl in labels), (
            f"Option labels should be Arabic: {labels}"
        )

    def test_option_labels_english(self):
        result = self._call(arabic=False)
        labels = [o["label"] for o in result["options"]]
        assert all(all(ord(c) < 0x0600 for c in lbl) for lbl in labels)
