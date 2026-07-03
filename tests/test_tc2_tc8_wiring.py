"""Regression tests for the TC-2 / TC-8 live-path wiring fixes.

These close the gap between "the new contracts exist" and "the dispatched chat
path actually uses them", found on ricohunt.com/command:

  TC-2: after confirming new target roles, a bare "search for jobs now" still
        searched the previous role because `job_search_explicit` prefers a cached
        `recent_search_role` over the profile's target_roles. Confirming a
        target-role change must invalidate that cache.

  TC-8: "prepare me for an interview for the Retail Operations Manager role at
        Richemont" was hijacked by the company-openings search because
        `_COMPANY_SEARCH_RE` matches "role at Richemont". Interview-prep requests
        must not trigger the company search.
"""

from unittest.mock import MagicMock, patch

import pytest

import src.rico_chat_api as chat
from src.rico_chat_api import RicoChatAPI


# ── TC-8: company-search guard ─────────────────────────────────────────────────

def _company_search_fires(message: str) -> bool:
    """Replicate the guarded dispatch condition for the company-openings path."""
    return bool(
        chat._COMPANY_SEARCH_RE.search(message)
        and not chat._COVER_LETTER_COMMAND_RE.search(message)
        and not chat._INTERVIEW_REQUEST_RE.search(message)
    )


@pytest.mark.parametrize("message", [
    "prepare me for an interview for the Retail Operations Manager role at Richemont",
    "prepare me for an interview at Richemont",
    "prepare me for an interview for a Compliance Manager at ADNOC",
    "interview prep for jobs at Richemont",
])
def test_interview_requests_do_not_trigger_company_search(message):
    assert _company_search_fires(message) is False


@pytest.mark.parametrize("message", [
    "find jobs at ADNOC",
    "any openings at Emirates NBD",
    "show me roles at DEWA",
    "search for jobs at Careem",
])
def test_genuine_company_searches_still_fire(message):
    assert _company_search_fires(message) is True


# ── TC-2: confirming a target-role change clears the stale search-role cache ────

class _CtxHarness:
    """Drive `_resolve_pending_field`'s confirm branch with a real context dict."""

    def run(self, message, prefs, ctx_extra=None):
        api = RicoChatAPI()
        ctx = {
            "_pending_field": "confirm_profile_update",
            "_pending_profile_update": prefs,
        }
        if ctx_extra:
            ctx.update(ctx_extra)
        with patch.object(api, "_get_recent_context", return_value=ctx), \
             patch.object(api, "_store_recent_context"), \
             patch.object(api, "_append_chat"), \
             patch("src.rico_chat_api.upsert_profile") as mock_upsert:
            result = api._resolve_pending_field(
                user_id="test@example.com", message=message, profile=MagicMock(),
            )
        return result, mock_upsert, ctx


def test_confirming_target_roles_clears_recent_search_role():
    result, mock_upsert, ctx = _CtxHarness().run(
        "yes",
        {"target_roles": ["Esg Manager", "Compliance Manager"]},
        ctx_extra={"recent_search_role": "Operations Manager", "recent_role": "Operations Manager"},
    )
    assert result and result["type"] == "preferences_updated"
    mock_upsert.assert_called_once()
    # The stale cached role must be gone so the next bare search uses the new targets.
    assert "recent_search_role" not in ctx
    assert "recent_role" not in ctx


def test_confirming_non_role_update_leaves_search_cache_intact():
    # A city-only update must NOT wipe the search-role continuity cache.
    _result, _mock, ctx = _CtxHarness().run(
        "yes",
        {"preferred_cities": ["Dubai"]},
        ctx_extra={"recent_search_role": "Compliance Manager"},
    )
    assert ctx.get("recent_search_role") == "Compliance Manager"
