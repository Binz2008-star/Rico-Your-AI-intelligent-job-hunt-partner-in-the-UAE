# -*- coding: utf-8 -*-
"""
Higher-fidelity integration tests for the LIVE chat path (production-equivalent).

Investigation context (fix/live-role-parsing-path-regressions): a live RECHECK
reported T2–T6 still failing ("Technical Product Owner not recognized", multi-role
→ "Something went wrong", exclusions ignored, category crash) even though the
#723/#730/#731 UNIT tests pass.

Those unit tests called ``RicoChatAPI._handle_active_user`` DIRECTLY, skipping the
real production entry path:

    /api/v1/rico/chat
      → chat_service.send_message
          → Policy Gateway (classify_request)
          → IntentRouter (is_open_ended_question)  [open-ended → AI, bypasses classifier]
          → _legacy_send_message → RicoChatAPI.process_message
              → _handle_active_user → _handle_active_user_inner
                  → classify_intent + dispatch

These tests drive the SAME ``chat_service.send_message`` path the HTTP handler uses
(authenticated session, mocked profile, mocked provider — 0 external calls) for the
five exact RECHECK prompts, in BOTH a healthy-provider and a quota-exhausted
(degraded) provider state, and assert:

  * the message is recognised (no generic safe-fallback, no empty-message error,
    and NEVER the "Something went wrong processing your message." string from
    process_message's outer except);
  * ``success`` is True so the frontend (``api.ts`` gates on ``!result.success``)
    does not render a generic error;
  * roles / exclusions parse correctly;
  * under a degraded provider, the user still gets a recognised, actionable
    response (provider_degraded CTA with role recognition, or CV suggestions) —
    not an error.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from src.jsearch_client import FetchResult
from src.schemas.chat import RicoSessionContext
from src.services import chat_service


_PROFILE = {
    "user_id": "u@test", "has_cv": True, "cv_status": "parsed", "cv_filename": "cv.pdf",
    "target_roles": ["Technical Product Owner"], "skills": ["product", "delivery"],
    "years_experience": 8, "preferred_cities": ["Dubai"], "current_role": "Product Owner",
}

# The five exact prompts from the live RECHECK.
P2 = "Search UAE jobs for Technical Product Owner only"
P3 = "Search UAE jobs for HSE Manager and QHSE Manager"
P4 = "Search for Technical Product Owner, Product Owner, and Technical Project Manager roles in UAE"
P5 = "Find jobs based on my CV, but do not search Software Engineer, Full Stack, Backend, Golang, or Machine Learning roles"
P6 = "I want product and technical management jobs, not coding jobs"
ALL_PROMPTS = [P2, P3, P4, P5, P6]

# Phrases that mean the message was NOT understood / errored — must never appear.
_FAILURE_MARKERS = (
    "something went wrong",
    "could not produce a usable reply",
    "i do not recognize",
    "i'm here to help with your uae job search",  # generic safe-fallback
)


def _healthy_search(role, location="", **kw):
    return FetchResult(
        items=[{"title": role or "Role", "company": "ACME",
                "apply_url": "https://acme.com/jobs/1", "location": "Dubai, UAE"}],
        provider="jsearch",
    )


def _degraded_search(role, location="", **kw):
    # Live condition: JSearch quota exhausted, no Jooble/Adzuna fallback hit.
    return FetchResult(items=[], provider="none", quota_exhausted=True,
                       error="all_providers_unavailable")


def _send(message: str, search_fn) -> dict:
    ctx = RicoSessionContext.for_authenticated("u@test")
    with (
        patch("src.repositories.profile_repo.get_profile", return_value=_PROFILE),
        patch("src.rico_chat_api.get_profile", return_value=_PROFILE),
        patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
        patch("src.rico_chat_api.upsert_profile", side_effect=lambda u, up: {**_PROFILE, **up}),
        patch("src.rico_chat_api.RicoChatAPI._search_jsearch_meta", side_effect=search_fn),
        # Legacy scraper fallback is unavailable in CI/sandbox; force it empty so the
        # degraded path is deterministic (in prod it's a no-op when providers return).
        patch("src.rico_chat_api.RicoChatAPI.system", create=True),
        patch("src.services.subscription_gating.check_ai_message_allowed", return_value=None),
    ):
        return chat_service.send_message(ctx=ctx, message=message)


def _assert_no_error_escape(res: dict):
    assert res.get("success") is True, f"frontend would error: success={res.get('success')} res={res.get('type')}"
    msg = (res.get("message") or "").strip()
    assert msg, "empty message → frontend empty-reply error"
    low = msg.lower()
    for marker in _FAILURE_MARKERS:
        assert marker not in low, f"failure marker {marker!r} in: {msg[:120]!r}"


# ── Healthy provider — the parse must reach the handler and search ────────────

@pytest.mark.parametrize("prompt", ALL_PROMPTS)
def test_live_path_no_error_escape_healthy(prompt):
    _assert_no_error_escape(_send(prompt, _healthy_search))


def test_t2_only_qualifier_searches_clean_role_live():
    res = _send(P2, _healthy_search)
    _assert_no_error_escape(res)
    assert res.get("type") == "job_matches"
    assert "Technical Product Owner" in (res.get("message") or "")
    assert "only" not in (res.get("search_query") or "Technical Product Owner")


def test_t3_two_roles_recognised_live():
    res = _send(P3, _healthy_search)
    _assert_no_error_escape(res)
    assert res.get("recognized_roles") == ["HSE Manager", "QHSE Manager"]


def test_t4_three_roles_recognised_live():
    res = _send(P4, _healthy_search)
    _assert_no_error_escape(res)
    assert res.get("recognized_roles") == [
        "Technical Product Owner", "Product Owner", "Technical Project Manager",
    ]


def test_t5_exclusions_never_suggest_excluded_live():
    res = _send(P5, _healthy_search)
    _assert_no_error_escape(res)
    blob = (res.get("message") or "") + " " + " ".join(
        str(o.get("label", "")) + str(o.get("action", "")) for o in (res.get("options") or [])
    )
    low = blob.lower()
    for banned in ("software engineer", "full stack", "backend", "golang", "machine learning"):
        assert banned not in low, f"excluded role surfaced: {banned}"


def test_t6_category_maps_and_excludes_coding_live():
    res = _send(P6, _healthy_search)
    _assert_no_error_escape(res)
    assert res.get("recognized_roles") == [
        "Technical Product Owner", "Product Owner", "Technical Project Manager",
        "Digital Transformation Manager", "Operations Technology Manager",
    ]
    assert res.get("excluded_roles") == [
        "Software Engineer", "Full Stack", "Backend", "Golang", "Machine Learning",
    ]


# ── Degraded provider (live quota-exhausted) — recognised, never an error ─────

@pytest.mark.parametrize("prompt", ALL_PROMPTS)
def test_live_path_no_error_escape_degraded(prompt):
    """Under quota-exhausted providers the user must still get a recognised,
    actionable response — never 'Something went wrong'."""
    _assert_no_error_escape(_send(prompt, _degraded_search))


def test_t6_degraded_still_recognises_roles():
    res = _send(P6, _degraded_search)
    _assert_no_error_escape(res)
    # Role recognition survives a degraded provider (preamble lists the roles).
    assert "recognised 5 target roles" in (res.get("message") or "").lower() \
        or res.get("recognized_roles")
