# -*- coding: utf-8 -*-
"""Regression tests: guest/no-profile chat must degrade gracefully on AI failure.

Finding (2026-07-04): `chat_service.send_message` forces every public/guest
message that isn't an explicit job-listing request onto the conversational AI
path (`answer_conversationally`). Its catch-all returned
`build_error_response(...)` — `type=error, success=False,
"Something went wrong processing your message."` — so ANY unexpected exception
in the AI path (e.g. the TypeError raised for non-JSON-serializable context in
`RicoOpenAIAgent.respond`) turned the ENTIRE public chat into an error page:
every greeting, question, and Arabic message failed. Authenticated users with
no profile row hit the same envelope on AI-routed messages
("what is my profile?").

Fix: `answer_conversationally` now logs the exception with full context and
returns a deterministic `provider_degraded` reply (success=True) — a CV/signup
CTA for public sessions, a "deterministic features still work" nudge for
authenticated ones, Arabic when the message is Arabic. Provider internals and
stack traces must never reach the user.

These tests drive the REAL production entry (`chat_service.send_message`) with
all external dependencies stubbed — no DB, no provider, no network.
"""
from __future__ import annotations

from contextlib import ExitStack
from typing import Any
from unittest.mock import PropertyMock, patch

import pytest

from src.schemas.chat import RicoSessionContext
from src.services import chat_service


def _boom(prompt: Any, user_context: Any = None, language: Any = None, **_kw: Any) -> dict:
    raise RuntimeError("simulated AI-path failure")


def _healthy(prompt: Any, user_context: Any = None, language: Any = None, **_kw: Any) -> dict:
    return {"message": "Stubbed AI reply.", "response_source": "test-stub", "provider": "test"}


def _send(ctx: RicoSessionContext, message: str, ai, language: str | None = None) -> dict:
    """chat_service.send_message with every external seam stubbed (offline)."""
    with ExitStack() as stack:
        p = stack.enter_context
        # Both DB layers off (see tests/harness/chat_harness.py for why both).
        p(patch("src.rico_db.RicoDB.available", new_callable=PropertyMock, return_value=False))
        p(patch("src.db.DB_ENABLED", False))
        # No profile rows exist for any user in these tests.
        p(patch("src.repositories.profile_repo.get_profile", return_value=None))
        p(patch("src.rico_chat_api.get_profile", return_value=None))
        p(patch("src.rico_chat_api.is_onboarding_complete", return_value=False))
        p(patch("src.rico_openai_agent.RicoOpenAIAgent.respond", side_effect=ai))
        p(patch("src.llm_scorer._embed", return_value=None))
        p(patch("src.services.subscription_gating.check_ai_message_allowed", return_value=None))
        return chat_service.send_message(ctx=ctx, message=message, language=language)


_PUBLIC = RicoSessionContext.for_public("degraded-test-session")
_AUTH = RicoSessionContext.for_authenticated("no-profile-row@test")

#: strings that must never reach a user from the degraded path
_LEAKS = ("Traceback", "RuntimeError", "simulated AI-path failure",
          "Reference:", "deepseek", "openai", "huggingface")


# ── Public/guest session: AI failure must not brick the chat ───────────────────

def test_public_ai_failure_degrades_gracefully_not_error():
    result = _send(_PUBLIC, "hello", _boom)

    assert result.get("success") is True, result
    assert result.get("type") == "provider_degraded", result
    msg = result.get("message") or ""
    assert "try again" in msg.lower()
    # Public variant: guide toward CV upload / signup, since nothing else works
    # for an anonymous session.
    assert "upload your cv" in msg.lower() or "sign up" in msg.lower()


@pytest.mark.parametrize("message", ["hello", "what can you do?", "yes", "help me please"])
def test_public_ai_failure_never_returns_error_envelope(message):
    result = _send(_PUBLIC, message, _boom)
    assert result.get("type") != "error", result
    assert result.get("success") is True, result


def test_public_ai_failure_leaks_no_internals():
    result = _send(_PUBLIC, "hello", _boom)
    msg = result.get("message") or ""
    for leak in _LEAKS:
        assert leak.lower() not in msg.lower(), f"leaked {leak!r}: {msg!r}"


def test_public_ai_failure_arabic_message_gets_arabic_reply():
    result = _send(_PUBLIC, "مرحبا", _boom, language="ar")

    assert result.get("success") is True, result
    assert result.get("type") == "provider_degraded", result
    msg = result.get("message") or ""
    # Reply must be Arabic (contains Arabic script), not the English fallback.
    assert any("؀" <= ch <= "ۿ" for ch in msg), msg
    # And the signup CTA must be a clickable markdown link, same as English
    # (bare "ricohunt.com" is not autolinked by the chat's markdown renderer).
    assert "https://ricohunt.com" in msg, msg


# ── Authenticated user with no profile row ─────────────────────────────────────

def test_authenticated_no_profile_ai_failure_degrades():
    result = _send(_AUTH, "what is my profile?", _boom)

    assert result.get("type") != "error", result
    assert result.get("success") is True, result
    # Authenticated variant nudges toward the deterministic features.
    if result.get("type") == "provider_degraded":
        assert "try again" in (result.get("message") or "").lower()


# ── Healthy-path regressions: the fix must change ONLY the exception path ──────

def test_public_healthy_ai_reply_passes_through_unchanged():
    result = _send(_PUBLIC, "hello", _healthy)

    assert result.get("success") is True, result
    assert result.get("type") != "provider_degraded", result
    assert result.get("message") == "Stubbed AI reply."


def test_public_job_listing_request_still_gets_cta_not_ai():
    # The deterministic job-listing guard fires before the AI path; a provider
    # outage must not affect it.
    result = _send(_PUBLIC, "find me a job", _boom)

    assert result.get("type") == "onboarding_cta", result
    assert result.get("success") is True
