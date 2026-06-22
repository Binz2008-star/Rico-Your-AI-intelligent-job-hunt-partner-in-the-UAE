"""
tests/unit/test_single_role_title_recognition.py

Production recheck follow-up — single-role parsing must accept explicit job
titles the same way multi-role parsing already does.

Live bug: "Search UAE jobs for Technical Product Owner only" returned
`clarification` — "I do not recognize 'Technical Product Owner' as a job role.
Based on your CV, I can search for: Developer." — even though the identical
title is accepted in a multi-role list. Rico bounced the explicit role and fell
back to the stale saved target_role "Developer".

Fix: a single explicit title (multi-word, ending in a known occupational noun)
is searched directly. Backend-only; mocks/fixtures only — no provider calls.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.agent.intelligence.intent_classifier import extract_role_list
from src.rico_chat_api import RicoChatAPI


def _api() -> RicoChatAPI:
    return RicoChatAPI()


def _stale_developer_profile() -> dict:
    """Product-management CV, but a stale 'Developer' left in target_roles."""
    return {
        "target_roles": ["Developer"],
        "cv_status": "parsed", "cv_filename": "cv.pdf",
        "skills": ["product", "agile", "stakeholder management", "roadmap"],
        "years_experience": 8, "preferred_cities": ["Dubai"],
    }


# ── 1. title detector ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("title", [
    "Technical Product Owner", "Product Owner", "Technical Project Manager",
    "Digital Transformation Manager", "Operations Technology Manager",
    "HSE Manager", "Senior Data Scientist",
])
def test_explicit_job_titles_are_accepted(title):
    assert _api()._is_explicit_job_title(title) is True


@pytest.mark.parametrize("not_title", [
    "software", "developer", "my cv", "based on my profile", "check my files",
    "jobs", "anything", "the best role for me",
])
def test_non_titles_are_rejected(not_title):
    assert _api()._is_explicit_job_title(not_title) is False


# ── 2. single-role / multi-role parity (the contradiction) ────────────────────

def test_single_and_multi_role_both_accept_technical_product_owner():
    # multi-role path
    roles, _excl = extract_role_list(
        "Search for Technical Product Owner, Product Owner, and Technical Project Manager roles in UAE"
    )
    assert "Technical Product Owner" in roles
    # single-role path
    assert _api()._is_explicit_job_title("Technical Product Owner") is True


# ── 3. end-to-end chat ────────────────────────────────────────────────────────

def _run_chat(message: str, profile: dict):
    api = _api()
    captured: dict = {}

    def fake_search(user_id, role, profile, **kw):
        captured["role"] = role
        return {"type": "job_matches", "message": f"Searching {role}.", "matches": [], "success": True}

    with (
        patch("src.rico_chat_api.get_profile", return_value=profile),
        patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
        patch.object(api, "_get_recent_context", return_value={}),
        patch.object(api, "_target_role_search_response", side_effect=fake_search),
    ):
        api.system = MagicMock()
        api.system.run_for_profile = MagicMock(return_value={"matches": []})
        result = api._handle_active_user("u-title", message)
    return result, captured


@pytest.mark.parametrize("phrase", [
    "Search UAE jobs for Technical Product Owner only",
    "Search UAE jobs for Technical Product Owner",
])
def test_single_technical_product_owner_searches_not_rejected(phrase):
    result, captured = _run_chat(phrase, _stale_developer_profile())
    assert result.get("type") == "job_matches"
    assert captured.get("role") == "Technical Product Owner"
    msg = (result.get("message") or "").lower()
    assert "do not recognize" not in msg


def test_stale_developer_does_not_override_explicit_title():
    # An explicit title must be searched as-is — the stale saved "Developer" must
    # never be substituted in, nor surfaced as a fallback suggestion.
    result, captured = _run_chat(
        "Search UAE jobs for Technical Product Owner only", _stale_developer_profile()
    )
    assert captured.get("role") == "Technical Product Owner"
    assert "Developer" not in (result.get("message") or "")


def test_bare_domain_word_still_rejected_via_detector():
    # Guard against over-acceptance: a bare domain word is not an explicit title.
    assert _api()._is_explicit_job_title("software") is False
