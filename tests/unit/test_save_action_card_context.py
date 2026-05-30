"""tests/unit/test_save_action_card_context.py

Regression tests for: Save action loses job context.

When a user clicks the "Save" button on a Rico-generated job card, the
frontend sends:  "Save — {title} at {company}".

Before the fix:
  - The classifier only knew the label "Save job", so "Save — ..." classified
    as `unknown` and fell through to the AI fallback, which asked the user for
    a link ("To save it properly, I need a link...").

After the fix:
  - "Save — {title} at {company}" classifies as save_job.
  - The save_job handler resolves the job from recent_search_matches /
    user_job_context and saves it through agent_runtime WITHOUT asking for a URL.
  - status=saved + saved_at + interaction fields are stamped via the runtime.
  - Missing apply_url falls back to source_url/alt_url and flags verification.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.rico_chat_api import RicoChatAPI


USER = "save-test@rico.ai"

# Phrases the response must NEVER contain — these mean Rico asked for a URL.
FORBIDDEN = ("i need a link", "share the url", "could you share the link", "additional details")


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


def _runtime_ok() -> MagicMock:
    result = MagicMock()
    result.ok = True
    result.message = "Saved. Rico will keep this job in your tracker."
    result.error = None
    return result


def _save_via_chat(api: RicoChatAPI, message: str, context: dict, *, runtime=None):
    """Drive process_message through the save_job handler with a given recent
    context. Returns (result, captured_handle_action_kwargs)."""
    runtime = runtime or _runtime_ok()
    captured: dict = {}

    def _capture(**kwargs):
        captured.update(kwargs)
        return runtime

    mock_runtime = MagicMock()
    mock_runtime.handle_action.side_effect = _capture

    with (
        patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
        patch.object(api, "_resolve_profile", return_value=_make_profile()),
        patch.object(api, "_append_chat"),
        patch.object(api, "_get_recent_context", return_value=dict(context)),
        patch.object(api, "_store_recent_context"),
        patch("src.rico_chat_api.agent_runtime", mock_runtime),
    ):
        result = api.process_message(USER, message)
    return result, captured


# ── 1. Search-result card → Save → saved without asking for URL ───────────────


class TestSaveFromSearchCard:

    CONTEXT = {
        "recent_search_matches": [
            {
                "title": "Environmental Advisory Manager — Remote",
                "company": "Careers at UAE",
                "apply_url": "https://example.com/apply/123",
                "source_url": "https://google.com/jobs/123",
                "verification_status": "live",
            }
        ]
    }

    def test_save_card_message_saves_without_asking_for_url(self):
        api = _make_api()
        result, captured = _save_via_chat(
            api,
            "Save — Environmental Advisory Manager — Remote at Careers at UAE",
            self.CONTEXT,
        )
        assert result["type"] == "save_job"
        msg = result["message"].lower()
        for bad in FORBIDDEN:
            assert bad not in msg, f"response must not ask for a URL (found {bad!r})"
        assert "saved —" in msg

    def test_save_routes_through_runtime_with_resolved_job(self):
        api = _make_api()
        _, captured = _save_via_chat(
            api,
            "Save — Environmental Advisory Manager — Remote at Careers at UAE",
            self.CONTEXT,
        )
        assert captured.get("action") == "save"
        job = captured.get("job") or {}
        # Resolved against recent_search_matches → correct title/company boundary.
        assert job.get("title") == "Environmental Advisory Manager — Remote"
        assert job.get("company") == "Careers at UAE"
        assert job.get("apply_url") == "https://example.com/apply/123"
        # Stable job_key must be provided so runtime idempotency is per-job.
        assert captured.get("job_key")

    def test_success_copy_includes_title_and_company(self):
        api = _make_api()
        result, _ = _save_via_chat(
            api,
            "Save — Environmental Advisory Manager — Remote at Careers at UAE",
            self.CONTEXT,
        )
        assert "Environmental Advisory Manager — Remote" in result["message"]
        assert "Careers at UAE" in result["message"]
        assert "tracked jobs" in result["message"].lower()


# ── 2. Resolve from persisted user_job_context (no in-memory matches) ─────────


class TestSaveResolvesFromUserJobContext:

    def test_title_company_resolves_via_find_by_title_company(self):
        api = _make_api()
        row = {
            "title": "Senior Compliance Officer",
            "company": "Emirates NBD",
            "apply_url": "https://nbd.example/apply",
            "source_url": "",
            "alt_url": "",
            "verification_status": "live",
        }
        with patch(
            "src.repositories.user_job_context_repo.find_by_title_company",
            return_value=row,
        ), patch(
            "src.repositories.user_job_context_repo.get_recently_interacted",
            return_value=[],
        ), patch(
            "src.repositories.user_job_context_repo.get_recently_discussed",
            return_value=[],
        ):
            # No recent_search_matches → forces the DB resolution path.
            result, captured = _save_via_chat(
                api, "Save job — Senior Compliance Officer at Emirates NBD", {}
            )
        assert result["type"] == "save_job"
        job = captured.get("job") or {}
        assert job.get("title") == "Senior Compliance Officer"
        assert job.get("company") == "Emirates NBD"
        msg = result["message"].lower()
        for bad in FORBIDDEN:
            assert bad not in msg


# ── 3. Missing apply_url → save with source/alt + verification flag ───────────


class TestSaveWithoutApplyUrl:

    def test_missing_apply_url_uses_source_url_and_flags_verification(self):
        api = _make_api()
        context = {
            "recent_search_matches": [
                {
                    "title": "Data Analyst",
                    "company": "Acme Corp",
                    "apply_url": "",
                    "source_url": "https://google.com/jobs/abc",
                    "verification_status": "lead_needs_verification",
                }
            ]
        }
        result, captured = _save_via_chat(api, "Save — Data Analyst at Acme Corp", context)
        assert result["type"] == "save_job"
        job = captured.get("job") or {}
        # No apply_url, but source_url present → saved with source + flagged.
        assert job.get("apply_url") == ""
        assert job.get("source_url") == "https://google.com/jobs/abc"
        assert result.get("verification_status") == "needs_source_verification"
        msg = result["message"].lower()
        for bad in FORBIDDEN:
            assert bad not in msg
        assert "saved —" in msg

    def test_alt_url_used_when_only_alt_present(self):
        api = _make_api()
        context = {
            "recent_search_matches": [
                {
                    "title": "Project Manager",
                    "company": "BuildCo",
                    "apply_url": "",
                    "source_url": "",
                    "alt_link": "https://alt.example/job",
                    "verification_status": "lead_needs_verification",
                }
            ]
        }
        result, captured = _save_via_chat(api, "Save — Project Manager at BuildCo", context)
        job = captured.get("job") or {}
        assert job.get("source_url") == "https://alt.example/job"
        assert result.get("verification_status") == "needs_source_verification"


# ── 4. Direct unit test of the resolver ───────────────────────────────────────


class TestResolveCardJob:

    def test_resolves_company_containing_at_from_recent_matches(self):
        api = _make_api()
        context = {
            "recent_search_matches": [
                {"title": "Environmental Advisory Manager — Remote", "company": "Careers at UAE",
                 "apply_url": "https://x/apply", "source_url": ""},
            ]
        }
        with patch.object(api, "_get_recent_context", return_value=context):
            # Greedy split the classifier produces: title up to last " at ".
            job = api._resolve_card_job(
                USER, "Environmental Advisory Manager — Remote at Careers", "UAE"
            )
        assert job is not None
        assert job["title"] == "Environmental Advisory Manager — Remote"
        assert job["company"] == "Careers at UAE"

    def test_returns_none_when_nothing_matches(self):
        api = _make_api()
        with patch.object(api, "_get_recent_context", return_value={}), patch(
            "src.repositories.user_job_context_repo.find_by_title_company", return_value=None
        ), patch(
            "src.repositories.user_job_context_repo.get_recently_interacted", return_value=[]
        ), patch(
            "src.repositories.user_job_context_repo.get_recently_discussed", return_value=[]
        ):
            job = api._resolve_card_job(USER, "Nonexistent Role", "Nowhere Inc")
        assert job is None
