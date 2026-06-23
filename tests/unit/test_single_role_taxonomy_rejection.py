# -*- coding: utf-8 -*-
"""
Single-role taxonomy-rejection parity fix.

Live RECHECK (prod commit ab170e2) found a contradiction:

  * Multi-role "… Technical Product Owner, Product Owner, Technical Project
    Manager …" → searched all three directly (works).
  * Single-role "Search UAE jobs for Technical Product Owner only" → the 3-tier
    CV taxonomy returns "unknown" for "Technical Product Owner", so the handler
    replied "I do not recognize 'Technical Product Owner' as a job role. Based on
    your CV, I can search for: Developer." — a clarification + a STALE fallback to
    the leftover CV role, instead of searching what the user explicitly asked for.

Fix: in ``_classified_role_search`` an explicit, well-formed title the taxonomy
doesn't happen to know is searched directly (same as multi-role), never bounced
back as "I do not recognize" and never replaced by a stale CV role.

Mocks/fixtures only — 0 external provider calls.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from src.agent.intelligence.intent_classifier import classify_intent
from src.agent.intelligence.role_classifier import classify_role_candidate
from src.rico_chat_api import RicoChatAPI, _looks_like_valid_role_title


# Developer/SE CV — "Technical Product Owner" is NOT in this profile's taxonomy.
_DEV_PROFILE = {
    "target_roles": ["Developer"], "current_role": "Software Engineer",
    "cv_status": "parsed", "cv_filename": "cv.pdf",
    "skills": ["python", "react"], "certifications": [], "industries": [],
    "years_experience": 6, "preferred_cities": ["Dubai"],
}


def _api() -> RicoChatAPI:
    return RicoChatAPI(persist=False)


def _run_classified_search(role_text: str, profile: dict):
    """Drive ``_classified_role_search`` with all side effects mocked, capturing
    whether (and with what role) a real search would have been issued."""
    api = _api()
    captured: dict = {}

    def _fake_search(user_id, role, profile, **kw):
        captured["role"] = role
        return {"type": "job_matches", "message": f"Searching {role}", "matches": [], "success": True}

    with (
        patch.object(api, "_target_role_search_response", side_effect=_fake_search),
        patch.object(api, "_get_recent_context", return_value={}),
        patch.object(api, "_append_chat", lambda *a, **k: None),
        patch.object(api, "_generate_role_suggestions", return_value=[]),
        patch.object(api, "_store_pending_job_search", lambda *a, **k: None),
    ):
        result = api._classified_role_search("u-tpo", role_text, profile)
    return result, captured


# ── 0. the head-noun heuristic ────────────────────────────────────────────────

@pytest.mark.parametrize("title", [
    "Technical Product Owner", "Product Owner", "Technical Project Manager",
    "QHSE Manager", "Solutions Architect", "Digital Transformation Manager",
])
def test_valid_titles_accepted(title):
    assert _looks_like_valid_role_title(title) is True


@pytest.mark.parametrize("junk", [
    "XYZNonsenseRole", "asdf", "Developer", "UAE", "",
    "the best job ever in dubai please now",
])
def test_non_titles_rejected(junk):
    assert _looks_like_valid_role_title(junk) is False


# ── 1. single Technical Product Owner is searched, not rejected ───────────────

def test_single_tpo_searches_instead_of_rejecting():
    # Precondition: the taxonomy genuinely does NOT know this title for a dev CV.
    classification, _canonical = classify_role_candidate("Technical Product Owner", _DEV_PROFILE)
    assert classification == "unknown"

    result, captured = _run_classified_search("Technical Product Owner", _DEV_PROFILE)

    # It searched the exact requested role …
    assert result.get("type") == "job_matches"
    assert captured.get("role") == "Technical Product Owner"
    # … and never produced the rejection or any stale-CV fallback.
    msg = (result.get("message") or "").lower()
    assert "i do not recognize" not in msg
    assert "developer" not in msg


def test_single_tpo_no_stale_developer_fallback():
    """The explicit role must never be replaced by the leftover CV role."""
    _result, captured = _run_classified_search("Technical Product Owner", _DEV_PROFILE)
    assert captured.get("role") == "Technical Product Owner"
    assert captured.get("role") != "Developer"


# ── 2. single-role parses to an explicit search intent (parity with multi) ────

def test_single_tpo_only_parses_to_explicit_search():
    r = classify_intent("Search UAE jobs for Technical Product Owner only", has_cv_profile=True)
    assert r.legacy_intent == "job_search_explicit"
    assert r.extracted_role == "Technical Product Owner"


# ── 3. multi-role parity guard (must keep working) ────────────────────────────

def test_multi_role_tpo_po_tpm_all_recognised():
    r = classify_intent(
        "Search for Technical Product Owner, Product Owner, and Technical Project Manager roles in UAE",
        has_cv_profile=True,
    )
    assert r.legacy_intent == "job_search_multi_role"
    assert (r.entities or {}).get("roles") == [
        "Technical Product Owner", "Product Owner", "Technical Project Manager",
    ]


# ── 4. genuine gibberish is still correctly rejected ──────────────────────────

def test_single_token_nonsense_still_rejected():
    result, captured = _run_classified_search("XYZNonsenseRole", _DEV_PROFILE)
    assert captured == {}  # never searched
    assert result.get("type") == "clarification"
    assert "i do not recognize" in (result.get("message") or "").lower()
