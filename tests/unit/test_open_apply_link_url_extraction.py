"""tests/unit/test_open_apply_link_url_extraction.py

Tests for the open_apply_link URL extraction fix.

Before the fix, the handler only checked rec.get("link"), missing
job_apply_link / apply_link / apply_url in top-level fields and any URL
stored in a nested job_data / job sub-dict (for records that were not
fully flattened by get_recommendations).

After the fix:
  - RicoChatAPI._extract_rec_url checks all known URL field variants
  - rico_db.get_recommendations exposes apply_url alongside link, so the
    flattened record already carries alternative-field URLs
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.rico_chat_api import RicoChatAPI


# ---------------------------------------------------------------------------
# 1. _extract_rec_url — static helper
# ---------------------------------------------------------------------------

class TestExtractRecUrl:

    def test_top_level_link(self):
        rec = {"link": "https://example.com/apply", "title": "HSE Officer", "company": "Acme"}
        assert RicoChatAPI._extract_rec_url(rec) == "https://example.com/apply"

    def test_top_level_apply_url(self):
        rec = {"apply_url": "https://example.com/apply", "link": ""}
        assert RicoChatAPI._extract_rec_url(rec) == "https://example.com/apply"

    def test_top_level_job_apply_link(self):
        rec = {"job_apply_link": "https://jobs.example.com/123", "link": "", "apply_url": ""}
        assert RicoChatAPI._extract_rec_url(rec) == "https://jobs.example.com/123"

    def test_top_level_apply_link(self):
        rec = {"apply_link": "https://jobs.example.com/456"}
        assert RicoChatAPI._extract_rec_url(rec) == "https://jobs.example.com/456"

    def test_top_level_source_url(self):
        rec = {"source_url": "https://google.com/jobs/123"}
        assert RicoChatAPI._extract_rec_url(rec) == "https://google.com/jobs/123"

    def test_nested_job_data_link(self):
        rec = {
            "link": "",
            "apply_url": "",
            "job_data": {"link": "https://nested.example.com/apply"},
        }
        assert RicoChatAPI._extract_rec_url(rec) == "https://nested.example.com/apply"

    def test_nested_job_data_job_apply_link(self):
        rec = {
            "link": "",
            "job_data": {"job_apply_link": "https://nested.example.com/jal"},
        }
        assert RicoChatAPI._extract_rec_url(rec) == "https://nested.example.com/jal"

    def test_nested_job_sub_dict(self):
        # Some records use "job" as the key name for raw job_data
        rec = {
            "link": "",
            "job": {"apply_url": "https://nested.example.com/au"},
        }
        assert RicoChatAPI._extract_rec_url(rec) == "https://nested.example.com/au"

    def test_top_level_takes_precedence_over_nested(self):
        rec = {
            "link": "https://top.example.com",
            "job_data": {"link": "https://nested.example.com"},
        }
        assert RicoChatAPI._extract_rec_url(rec) == "https://top.example.com"

    def test_empty_record_returns_empty_string(self):
        assert RicoChatAPI._extract_rec_url({}) == ""

    def test_all_empty_returns_empty_string(self):
        rec = {"link": "", "apply_url": "", "job_apply_link": "", "job_data": {}}
        assert RicoChatAPI._extract_rec_url(rec) == ""

    def test_strips_whitespace(self):
        rec = {"link": "  https://example.com/apply  "}
        assert RicoChatAPI._extract_rec_url(rec) == "https://example.com/apply"

    def test_non_dict_nested_does_not_raise(self):
        rec = {"link": "", "job_data": "not-a-dict"}
        assert RicoChatAPI._extract_rec_url(rec) == ""


# ---------------------------------------------------------------------------
# 2. get_recommendations — link field extraction in rico_db
# ---------------------------------------------------------------------------

class TestGetRecommendationsLinkExtraction:

    def _make_db_row(self, job_dict: dict, job_key: str = "key-1") -> dict:
        """Simulate a psycopg2 RealDictRow returned by cursor.fetchall()."""
        from datetime import datetime
        row = {
            "job_key": job_key,
            "job": job_dict,
            "repo_score": None,
            "rico_score": 75,
            "explanation": None,
            "status": "found",
            "created_at": datetime(2026, 1, 1),
            "updated_at": datetime(2026, 1, 2),
        }
        return row

    def _run_get_recommendations(self, job_dict: dict) -> dict:
        from src.rico_db import RicoDB
        db = RicoDB.__new__(RicoDB)
        row = self._make_db_row(job_dict)

        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [row]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        with patch.object(db, "_transaction") as mock_tx:
            mock_tx.return_value.__enter__.return_value = mock_conn
            result = db.get_recommendations("user-uuid-123")

        return result[0]

    def test_plain_link_field(self):
        rec = self._run_get_recommendations({"title": "HSE Officer", "company": "Acme", "link": "https://example.com"})
        assert rec["link"] == "https://example.com"
        assert rec["apply_url"] == "https://example.com"

    def test_job_apply_link_field(self):
        """JSearch-format job stored with job_apply_link not link."""
        rec = self._run_get_recommendations({
            "title": "HSE Officer", "company": "Acme",
            "link": "",
            "job_apply_link": "https://jsearch.example.com/apply",
        })
        assert rec["link"] == "https://jsearch.example.com/apply"
        assert rec["apply_url"] == "https://jsearch.example.com/apply"

    def test_apply_url_field(self):
        rec = self._run_get_recommendations({
            "title": "HSE Officer", "company": "Acme",
            "apply_url": "https://apply.example.com",
        })
        assert rec["link"] == "https://apply.example.com"
        assert rec["apply_url"] == "https://apply.example.com"

    def test_apply_link_field(self):
        rec = self._run_get_recommendations({
            "title": "HSE Officer", "company": "Acme",
            "apply_link": "https://alt.example.com",
        })
        assert rec["link"] == "https://alt.example.com"

    def test_no_url_returns_empty(self):
        rec = self._run_get_recommendations({"title": "HSE Officer", "company": "Acme"})
        assert rec["link"] == ""
        assert rec["apply_url"] == ""


# ---------------------------------------------------------------------------
# 3. open_apply_link handler — end-to-end via process_message
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
    p.target_roles = ["HSE Officer"]  # must pass evaluate_minimum_profile gate
    p.skills = []
    p.name = "Test User"
    p.email = USER
    return p


def _call_open_link(api: RicoChatAPI, message: str, apps: list) -> dict:
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
        patch.object(api, "_get_recent_context", return_value={}),
        patch.object(api, "_store_recent_context", side_effect=lambda uid, ctx: stored.append(ctx)),
        patch("src.rico_chat_api.classify_intent", return_value=intent),
        patch("src.repositories.applications_repo.get_all", return_value=apps),
        patch.object(api, "_verify_link_sync", return_value=None),
    ):
        result = api.process_message(USER, message)
    return result, stored


class TestOpenApplyLinkHandler:

    def setup_method(self):
        self.api = _make_api()

    def test_finds_top_level_link(self):
        apps = [{"title": "HSE Officer", "company": "Acme Corp", "link": "https://example.com/apply", "apply_url": ""}]
        result, stored = _call_open_link(self.api, "open apply link for HSE Officer at Acme Corp", apps)
        assert result["apply_url"] == "https://example.com/apply"
        assert "https://example.com/apply" in result["message"]
        assert any(ctx.get("recent_application", {}).get("link") for ctx in stored)

    def test_finds_job_apply_link_field(self):
        """JSearch-format record where link is empty but job_apply_link has the URL."""
        apps = [{
            "title": "HSE Officer", "company": "Acme Corp",
            "link": "",
            "apply_url": "",
            "job_apply_link": "https://jsearch.example.com/apply",
        }]
        result, stored = _call_open_link(self.api, "open apply link for HSE Officer at Acme Corp", apps)
        assert result["apply_url"] == "https://jsearch.example.com/apply"
        assert "https://jsearch.example.com/apply" in result["message"]

    def test_finds_nested_job_data_link(self):
        """Record where URL is nested under job_data (not fully flattened)."""
        apps = [{
            "title": "HSE Officer", "company": "Acme Corp",
            "link": "",
            "job_data": {"link": "https://nested.example.com/apply"},
        }]
        result, stored = _call_open_link(self.api, "open apply link for HSE Officer at Acme Corp", apps)
        assert result["apply_url"] == "https://nested.example.com/apply"

    def test_no_url_returns_no_link_message(self):
        apps = [{"title": "HSE Officer", "company": "Acme Corp", "link": "", "apply_url": ""}]
        result, stored = _call_open_link(self.api, "open apply link for HSE Officer at Acme Corp", apps)
        assert result["apply_url"] in (None, "")
        assert "don't have" in result["message"].lower() or "no saved" in result["message"].lower()
        assert not any(ctx.get("recent_application", {}).get("link") for ctx in stored)

    def test_no_matching_app_returns_no_link_message(self):
        apps = [{"title": "Different Role", "company": "Other Corp", "link": "https://example.com"}]
        result, stored = _call_open_link(self.api, "open apply link for HSE Officer at Acme Corp", apps)
        assert result["apply_url"] in (None, "")

    def test_stores_url_evidence_when_found(self):
        """After open_apply_link with URL, context must hold link for _has_apply_evidence."""
        apps = [{"title": "HSE Officer", "company": "Acme Corp", "link": "https://example.com/apply"}]
        result, stored = _call_open_link(self.api, "open apply link for HSE Officer at Acme Corp", apps)
        recent_app = next(
            (ctx.get("recent_application") for ctx in stored if ctx.get("recent_application")),
            None,
        )
        assert recent_app is not None
        assert recent_app["link"] == "https://example.com/apply"
