"""
tests/test_bug05_confirmation_loop.py

Regression tests for BUG-05 — "Yes, search {role}" quick-reply button causes
an infinite loop.

Root cause:
  1. User types "Search Software Engineer".
  2. `_classified_role_search` classifies it as `known_but_off_profile` (not
     in the user's target roles), stores `_pending_role_confirmation` in
     context, and returns a confirmation prompt with a quick-reply button
     labelled "Yes, search Software Engineer".
  3. User clicks the button → the full label is sent verbatim.
  4. `_is_affirmative("Yes, search Software Engineer")` returns False — it only
     matches single-word affirmatives.
  5. The message falls through to role extraction → "Software Engineer" is
     extracted → `_classified_role_search` fires again → same confirmation
     prompt → infinite loop.

Fix: intercept the "Yes, search {role}" pattern in `_handle_active_user_inner`
before role classification, check `_pending_role_confirmation` in context, and
execute the search directly.

These tests call `_handle_active_user_inner` directly (where the fix lives) with
mocked external calls (DB, JSearch, OpenAI). They must not touch the live DB.
"""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


# ---------------------------------------------------------------------------
# Minimal helpers
# ---------------------------------------------------------------------------

class _Any:
    """Stand-in for unittest.mock.ANY: matches anything in assert calls."""
    def __eq__(self, other): return True
    def __repr__(self): return "ANY"

ANY = _Any()


def _make_api():
    from src.rico_chat_api import RicoChatAPI
    api = RicoChatAPI()
    api.memory = MagicMock()
    return api


def _mock_search_result(role: str) -> dict:
    return {
        "type": "job_listings",
        "message": f"Here are jobs for {role}",
        "jobs": [],
        "response_source": "keyword",
    }


def _stub_profile(target_roles=None) -> SimpleNamespace:
    return SimpleNamespace(
        user_id="test@example.com",
        has_cv=True,
        target_roles=target_roles or ["HSE Manager"],
        skills=["ISO 14001"],
        certifications=[],
        years_experience=5,
        industries=[],
        preferred_cities=["Dubai"],
        current_role="HSE Officer",
        name="Test User",
        visa_status="employed",
        salary_expectation_aed=15000,
    )


# ===========================================================================
# Core fix — "Yes, search {role}" must resolve the pending confirmation
# ===========================================================================

class TestYesSearchButtonFix:
    """The quick-reply button click must execute the search, not loop."""

    def _call_inner(self, role: str, message: str, ctx_override: dict | None = None):
        api = _make_api()
        profile = _stub_profile()
        ctx = {"_pending_role_confirmation": {"role": role}}
        if ctx_override is not None:
            ctx = ctx_override
        search_result = _mock_search_result(role)

        with patch.object(api, "_append_chat"), \
             patch.object(api, "_resolve_profile", return_value=profile), \
             patch.object(api, "_get_recent_context", return_value=ctx), \
             patch.object(api, "_store_recent_context") as mock_store, \
             patch.object(api, "_clear_pending_job_search") as mock_clear, \
             patch.object(api, "_target_role_search_response", return_value=search_result) as mock_search, \
             patch.object(api, "_resolve_pending_field", return_value=None), \
             patch.object(api, "_resolve_letter_choice", return_value=None), \
             patch.object(api, "_looks_like_pasted_cv_text", return_value=False), \
             patch.object(api, "_handle_application_channel_followup", return_value=None), \
             patch.object(api, "_resolve_settings_command", return_value=None), \
             patch.object(api, "_looks_like_cv_intent_no_file", return_value=False), \
             patch.object(api, "_is_list_followup", return_value=False), \
             patch.object(api, "_is_verify_followup", return_value=False), \
             patch.object(api, "_finalize", side_effect=lambda r, *a, **kw: r):
            result = api._handle_active_user_inner(
                user_id="test@example.com",
                message=message,
            )
        return result, mock_store, mock_clear, mock_search, ctx

    def test_button_click_executes_search(self):
        result, _, _, mock_search, _ = self._call_inner(
            "Software Engineer", "Yes, search Software Engineer"
        )
        mock_search.assert_called_once_with("test@example.com", "Software Engineer", ANY)
        assert result["type"] == "job_listings"

    def test_button_click_clears_pending_role_confirmation(self):
        _, mock_store, _, _, ctx = self._call_inner(
            "Software Engineer", "Yes, search Software Engineer"
        )
        assert "_pending_role_confirmation" not in ctx
        mock_store.assert_called()

    def test_button_click_clears_pending_job_search(self):
        _, _, mock_clear, _, _ = self._call_inner(
            "Software Engineer", "Yes, search Software Engineer"
        )
        mock_clear.assert_called_once()

    def test_varies_role_in_button_label(self):
        """Confirm the fix handles any role name in the button label."""
        for role in ("Data Analyst", "HSE Manager", "Marketing Director"):
            result, _, _, mock_search, _ = self._call_inner(role, f"Yes, search {role}")
            mock_search.assert_called_once_with("test@example.com", role, ANY)
            assert result["type"] == "job_listings"

    def test_case_insensitive_prefix(self):
        """YES/yes/Yes variants are all matched."""
        api = _make_api()
        profile = _stub_profile()
        role = "Project Manager"
        search_result = _mock_search_result(role)

        for prefix in ("YES, search", "yes, search", "yes search"):
            ctx = {"_pending_role_confirmation": {"role": role}}
            with patch.object(api, "_append_chat"), \
                 patch.object(api, "_resolve_profile", return_value=profile), \
                 patch.object(api, "_get_recent_context", return_value=ctx), \
                 patch.object(api, "_store_recent_context"), \
                 patch.object(api, "_clear_pending_job_search"), \
                 patch.object(api, "_target_role_search_response", return_value=search_result) as mock_search, \
                 patch.object(api, "_resolve_pending_field", return_value=None), \
                 patch.object(api, "_resolve_letter_choice", return_value=None), \
                 patch.object(api, "_looks_like_pasted_cv_text", return_value=False), \
                 patch.object(api, "_handle_application_channel_followup", return_value=None), \
                 patch.object(api, "_resolve_settings_command", return_value=None), \
                 patch.object(api, "_looks_like_cv_intent_no_file", return_value=False), \
                 patch.object(api, "_is_list_followup", return_value=False), \
                 patch.object(api, "_is_verify_followup", return_value=False), \
                 patch.object(api, "_finalize", side_effect=lambda r, *a, **kw: r):
                result = api._handle_active_user_inner(
                    user_id="test@example.com",
                    message=f"{prefix} {role}",
                )
            mock_search.assert_called_once_with("test@example.com", role, ANY)


# ===========================================================================
# No-op when context is absent — the fix must not interfere
# ===========================================================================

class TestYesSearchWithoutPendingContext:
    """Without _pending_role_confirmation, the interceptor must be a no-op."""

    def test_no_pending_context_falls_through(self):
        """If no pending confirmation exists the message routes normally (no early exit)."""
        api = _make_api()
        profile = _stub_profile()
        # Empty context — no pending confirmation
        ctx = {}

        with patch.object(api, "_append_chat"), \
             patch.object(api, "_resolve_profile", return_value=profile), \
             patch.object(api, "_get_recent_context", return_value=ctx), \
             patch.object(api, "_store_recent_context"), \
             patch.object(api, "_clear_pending_job_search") as mock_clear, \
             patch.object(api, "_target_role_search_response") as mock_search_via_interceptor, \
             patch.object(api, "_resolve_pending_field", return_value=None), \
             patch.object(api, "_resolve_letter_choice", return_value=None), \
             patch.object(api, "_looks_like_pasted_cv_text", return_value=False), \
             patch.object(api, "_handle_application_channel_followup", return_value=None), \
             patch.object(api, "_resolve_settings_command", return_value=None), \
             patch.object(api, "_looks_like_cv_intent_no_file", return_value=False), \
             patch.object(api, "_is_list_followup", return_value=False), \
             patch.object(api, "_is_verify_followup", return_value=False), \
             patch.object(api, "_finalize", side_effect=lambda r, *a, **kw: r), \
             patch.object(api, "_is_affirmative", return_value=False), \
             patch.object(api, "_is_continuation_intent", return_value=False), \
             patch.object(api, "_is_negative", return_value=False), \
             patch.object(api, "_classified_role_search",
                          return_value={"type": "clarification", "message": "confirm?"}) as mock_classify:
            result = api._handle_active_user_inner(
                user_id="test@example.com",
                message="Yes, search Software Engineer",
            )

        # The interceptor must not have called _target_role_search_response
        # (normal routing still calls _classified_role_search from intent dispatch).
        mock_clear.assert_not_called()
        # _pending_role_confirmation was never set so nothing to clear
        assert "_pending_role_confirmation" not in ctx


# ===========================================================================
# _is_affirmative must still reject compound phrases (no regression)
# ===========================================================================

class TestAffirmativeUnchanged:

    def test_is_affirmative_yes(self):
        from src.rico_chat_api import RicoChatAPI
        api = RicoChatAPI()
        assert api._is_affirmative("yes") is True
        assert api._is_affirmative("Yes") is True
        assert api._is_affirmative("نعم") is True

    def test_is_affirmative_rejects_compound(self):
        from src.rico_chat_api import RicoChatAPI
        api = RicoChatAPI()
        assert api._is_affirmative("Yes, search Software Engineer") is False
        assert api._is_affirmative("Yes please search") is False
