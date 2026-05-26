"""tests/unit/test_recent_search_matches_context.py

Tests for the recent_search_matches persistence fix.

Before the fix, open_apply_link searched only Application Flow records
(applications_repo.get_all). Jobs returned by a search were never persisted
to that store, so open_apply_link would fail even if the URL existed in the
same search session.

After the fix:
  - Every job_matches response stores recent_search_matches in recent_context.
  - open_apply_link checks recent_search_matches BEFORE Application Flow.
  - Jobs with no URL in recent_search_matches return a lead-verification message.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest

from src.rico_chat_api import RicoChatAPI


# ---------------------------------------------------------------------------
# Helpers shared across test classes
# ---------------------------------------------------------------------------

USER = "test@rico.ai"


def _make_api() -> RicoChatAPI:
    api = RicoChatAPI.__new__(RicoChatAPI)
    api._persist = False
    api._current_operation_id = None
    api._memory = {}
    return api


def _make_profile() -> MagicMock:
    p = MagicMock()
    p.has_cv = False
    p.target_roles = []
    p.skills = []
    p.name = "Test User"
    p.email = USER
    return p


def _open_link_with_context(api: RicoChatAPI, context: dict, apps: list) -> tuple[dict, list]:
    """Call open_apply_link with a pre-set recent_context."""
    from src.agent.intelligence.intent_classifier import IntentResult

    mock_agent = MagicMock()
    mock_agent.openai_available = False
    mock_agent.deepseek_available = False
    mock_agent.hf_available = False
    mock_agent.provider_available = True
    mock_agent.model = ""

    intent = IntentResult(
        intent="job_action.open_apply_link",
        confidence=1.0,
        source="exact",
        extracted_title="HSE Officer",
        extracted_company="Acme Corp",
    )
    stored: list[dict] = []
    with (
        patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
        patch.object(api, "_resolve_profile", return_value=_make_profile()),
        patch.object(api, "_append_chat"),
        patch.object(api, "_get_openai_agent", return_value=mock_agent),
        patch.object(api, "_looks_like_career_execution_request", return_value=False),
        patch.object(api, "_get_recent_context", return_value=dict(context)),
        patch.object(api, "_store_recent_context", side_effect=lambda uid, ctx: stored.append(ctx)),
        patch("src.rico_chat_api.classify_intent", return_value=intent),
        patch("src.repositories.applications_repo.get_all", return_value=apps),
    ):
        result = api.process_message(USER, "open apply link for HSE Officer at Acme Corp")
    return result, stored


# ---------------------------------------------------------------------------
# 1. _store_search_matches_context — unit tests
# ---------------------------------------------------------------------------

class TestStoreSearchMatchesContext:

    def test_stores_all_required_fields(self):
        api = _make_api()
        formatted = [
            {
                "title": "HSE Officer",
                "company": "Acme Corp",
                "location": "Dubai, UAE",
                "apply_url": "https://example.com/apply",
                "source_url": "https://google.com/jobs/123",
                "verification_status": "live",
            }
        ]
        stored: list[dict] = []
        with (
            patch.object(api, "_get_recent_context", return_value={}),
            patch.object(api, "_store_recent_context", side_effect=lambda uid, ctx: stored.append(ctx)),
        ):
            api._store_search_matches_context(USER, formatted)

        assert len(stored) == 1
        matches = stored[0]["recent_search_matches"]
        assert len(matches) == 1
        m = matches[0]
        assert m["title"] == "HSE Officer"
        assert m["company"] == "Acme Corp"
        assert m["location"] == "Dubai, UAE"
        assert m["apply_url"] == "https://example.com/apply"
        assert m["source_url"] == "https://google.com/jobs/123"
        assert m["link"] == "https://example.com/apply"
        assert m["verification_status"] == "live"

    def test_lead_match_stored_with_correct_status(self):
        api = _make_api()
        formatted = [
            {
                "title": "Safety Manager",
                "company": "Global Corp",
                "apply_url": "",
                "source_url": "",
                "verification_status": "lead_needs_verification",
            }
        ]
        stored: list[dict] = []
        with (
            patch.object(api, "_get_recent_context", return_value={}),
            patch.object(api, "_store_recent_context", side_effect=lambda uid, ctx: stored.append(ctx)),
        ):
            api._store_search_matches_context(USER, formatted)

        m = stored[0]["recent_search_matches"][0]
        assert m["verification_status"] == "lead_needs_verification"
        assert m["apply_url"] == ""

    def test_merges_with_existing_context(self):
        api = _make_api()
        existing_ctx = {"recent_application": {"title": "Old Role", "company": "Old Corp"}}
        formatted = [{"title": "HSE Officer", "company": "Acme", "apply_url": "https://x.com",
                      "source_url": "", "verification_status": "live"}]
        stored: list[dict] = []
        with (
            patch.object(api, "_get_recent_context", return_value=dict(existing_ctx)),
            patch.object(api, "_store_recent_context", side_effect=lambda uid, ctx: stored.append(ctx)),
        ):
            api._store_search_matches_context(USER, formatted)

        ctx = stored[0]
        assert "recent_application" in ctx, "existing context keys must be preserved"
        assert "recent_search_matches" in ctx

    def test_empty_formatted_list_stores_empty_matches(self):
        api = _make_api()
        stored: list[dict] = []
        with (
            patch.object(api, "_get_recent_context", return_value={}),
            patch.object(api, "_store_recent_context", side_effect=lambda uid, ctx: stored.append(ctx)),
        ):
            api._store_search_matches_context(USER, [])
        assert stored[0]["recent_search_matches"] == []

    def test_exception_in_get_context_does_not_raise(self):
        api = _make_api()
        with patch.object(api, "_get_recent_context", side_effect=RuntimeError("db down")):
            api._store_search_matches_context(USER, [{"title": "X", "company": "Y"}])


# ---------------------------------------------------------------------------
# 2. open_apply_link — recent_search_matches as URL source
# ---------------------------------------------------------------------------

class TestOpenApplyLinkFromSearchContext:

    def setup_method(self):
        self.api = _make_api()

    def test_finds_url_from_recent_search_matches(self):
        ctx = {
            "recent_search_matches": [
                {
                    "title": "HSE Officer",
                    "company": "Acme Corp",
                    "apply_url": "https://search-result.example.com/apply",
                    "link": "https://search-result.example.com/apply",
                    "verification_status": "live",
                }
            ]
        }
        result, stored = _open_link_with_context(self.api, ctx, apps=[])
        assert result["apply_url"] == "https://search-result.example.com/apply"
        assert "https://search-result.example.com/apply" in result["message"]

    def test_recent_search_takes_priority_over_application_flow(self):
        """URL from recent search session wins over stale Application Flow record."""
        ctx = {
            "recent_search_matches": [
                {
                    "title": "HSE Officer",
                    "company": "Acme Corp",
                    "apply_url": "https://fresh-search.example.com/apply",
                    "link": "https://fresh-search.example.com/apply",
                    "verification_status": "live",
                }
            ]
        }
        stale_apps = [
            {
                "title": "HSE Officer",
                "company": "Acme Corp",
                "link": "https://stale-app-flow.example.com/apply",
                "apply_url": "https://stale-app-flow.example.com/apply",
            }
        ]
        result, _ = _open_link_with_context(self.api, ctx, apps=stale_apps)
        assert result["apply_url"] == "https://fresh-search.example.com/apply"
        assert "fresh-search" in result["message"]

    def test_stores_url_evidence_from_search_match(self):
        """After resolving from recent_search_matches, recent_application evidence is stored."""
        ctx = {
            "recent_search_matches": [
                {
                    "title": "HSE Officer",
                    "company": "Acme Corp",
                    "apply_url": "https://example.com/apply",
                    "link": "https://example.com/apply",
                    "verification_status": "live",
                }
            ]
        }
        result, stored = _open_link_with_context(self.api, ctx, apps=[])
        recent_app = next(
            (s.get("recent_application") for s in stored if s.get("recent_application")),
            None,
        )
        assert recent_app is not None
        assert recent_app["link"] == "https://example.com/apply"

    def test_lead_in_search_matches_returns_lead_message(self):
        """Job with no URL in recent_search_matches gets lead-verification wording, not generic."""
        ctx = {
            "recent_search_matches": [
                {
                    "title": "HSE Officer",
                    "company": "Acme Corp",
                    "apply_url": "",
                    "link": "",
                    "verification_status": "lead_needs_verification",
                }
            ]
        }
        result, _ = _open_link_with_context(self.api, ctx, apps=[])
        assert result["apply_url"] in (None, "")
        msg = result["message"].lower()
        assert "lead" in msg or "verify" in msg or "verified" in msg, (
            f"expected lead-verification wording, got: {result['message']!r}"
        )
        assert "don't have a saved apply link" not in msg

    def test_no_match_in_search_falls_back_to_application_flow(self):
        """If title/company not in recent_search_matches, Application Flow is still checked."""
        ctx = {
            "recent_search_matches": [
                {
                    "title": "Different Role",
                    "company": "Other Corp",
                    "apply_url": "https://other.example.com",
                    "link": "https://other.example.com",
                    "verification_status": "live",
                }
            ]
        }
        apps = [
            {
                "title": "HSE Officer",
                "company": "Acme Corp",
                "link": "https://appflow.example.com/apply",
                "apply_url": "https://appflow.example.com/apply",
            }
        ]
        result, _ = _open_link_with_context(self.api, ctx, apps=apps)
        assert result["apply_url"] == "https://appflow.example.com/apply"

    def test_empty_context_falls_back_to_application_flow(self):
        """No recent_search_matches at all → Application Flow lookup unchanged."""
        apps = [
            {
                "title": "HSE Officer",
                "company": "Acme Corp",
                "link": "https://appflow.example.com/apply",
                "apply_url": "https://appflow.example.com/apply",
            }
        ]
        result, _ = _open_link_with_context(self.api, {}, apps=apps)
        assert result["apply_url"] == "https://appflow.example.com/apply"

    def test_no_url_anywhere_generic_message(self):
        """No match in search or Application Flow → generic 'no saved apply link' message."""
        result, _ = _open_link_with_context(self.api, {}, apps=[])
        assert result["apply_url"] in (None, "")
        assert "don't have" in result["message"].lower() or "no saved" in result["message"].lower()
