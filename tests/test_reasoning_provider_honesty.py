"""
tests/test_reasoning_provider_honesty.py

Rico must never present a canned template as if it were an answer.

`RicoOpenAIAgent.respond()` is only ever reached on the conversational-AI path —
the router has already decided the request needs the model — so when no
reasoning provider can serve it, the only honest reply is that reasoning is
unavailable. Two failure shapes exist, and both were wrong in different ways on
`fb2f382`:

  CASE B — no reasoning provider configured/usable (active provider's key
    absent AND HuggingFace absent or returning nothing). `respond()` returned
    `_fallback_response()`:

        type    = 'fallback_response'
        message = "I'm here to help with your UAE job search. Upload your CV to
                   get started, or ask me about jobs, applications, or
                   interview prep."
        provider= 'fallback'

    For "Give me one short tip to improve my CV for UAE employers" that reads
    as a real — if unhelpful — answer. It carried NO error_code and NO
    provider_state, so nothing marked it as a failure. This is the exact class
    of dishonesty that kept an earlier provider outage invisible to the owner:
    canned templates served as answers. Reachable whenever
    RICO_AI_PROVIDER=huggingface and HF fails, or the active provider's key is
    absent.

  CASE A — provider configured but every model attempt failed. The user-visible
    TEXT was already honest (`_FALLBACK_TEXT`, landed in #1378), but
    `respond()` forwarded only error/error_detail/*_model/fallback_model/
    provider and DROPPED the `error_code`, `provider_state` and
    `error_category` that `_failure_payload` had set. Downstream
    `_source_for_openai_response` then bucketed it as SOURCE_FALLBACK,
    identical to a benign keyword fallback — so an outage was
    machine-indistinguishable from a normal answer.

Deterministic and provider-free: every provider failure is simulated at the
boundary with monkeypatch. No network, no live provider, no DB writes.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("JWT_SECRET", "x" * 32)

import src.rico_openai_runtime as rt
from src.rico_openai_agent import RicoOpenAIAgent
from src.rico_openai_runtime import REASONING_UNAVAILABLE_TEXT

# A genuine reasoning request — the owner's live prompt from the #1379 incident.
ADVICE_PROMPT = "Give me one short tip to improve my CV for UAE employers"
ARABIC_ADVICE_PROMPT = "أعطني نصيحة قصيرة لتحسين سيرتي الذاتية"

# The exact canned strings that must never be served as an answer to a
# reasoning request. Kept as literals (not imported) so deleting them from the
# source cannot silently disarm these assertions.
COSY_CAPABILITY_BLURB = "I'm here to help with your UAE job search"
COSY_FREE_MODE_BLURB = "Free mode is active"

_PROVIDER_KEYS = (
    "OPENAI_API_KEY", "OPEN_AI_API", "DEEPSEEK_API_KEY",
    "HF_TOKEN", "HF_API_TOKEN", "HF_API_KEY", "HUGGINGFACE_API_KEY",
)


@pytest.fixture
def no_provider(monkeypatch):
    """CASE B: an active provider is selected but nothing can serve it."""
    for key in _PROVIDER_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("RICO_AI_PROVIDER", "deepseek")
    # Constructed AFTER the env is set — __init__ reads keys eagerly.
    return RicoOpenAIAgent()


@pytest.fixture
def failing_provider(monkeypatch):
    """CASE A: provider configured, every model attempt raises."""
    monkeypatch.setenv("RICO_AI_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-not-real")
    for key in ("HF_TOKEN", "HF_API_TOKEN", "HF_API_KEY", "HUGGINGFACE_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(
        rt, "_call_deepseek_chat",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("connection refused")),
    )
    return RicoOpenAIAgent()


# ── CASE B: the dishonesty ───────────────────────────────────────────────────

class TestNoProviderConfiguredIsHonest:
    def test_advice_request_gets_the_honest_unavailable_reply(self, no_provider):
        result = no_provider.respond(ADVICE_PROMPT)
        assert result["message"] == REASONING_UNAVAILABLE_TEXT
        assert result["type"] == "reasoning_unavailable"

    def test_never_serves_the_cosy_capability_blurb(self, no_provider):
        """The regression lock for the incident class itself."""
        result = no_provider.respond(ADVICE_PROMPT)
        assert COSY_CAPABILITY_BLURB not in result["message"]
        assert COSY_FREE_MODE_BLURB not in result["message"]

    def test_carries_machine_readable_failure_markers(self, no_provider):
        """A dead provider must be detectable without reading the prose."""
        result = no_provider.respond(ADVICE_PROMPT)
        assert result["error_code"] == "reasoning_provider_unavailable"
        assert result["provider_state"] == "degraded"
        assert result["error_category"] == "not_configured"
        assert result["response_source"] == "fallback"

    def test_arabic_request_gets_an_honest_arabic_reply(self, no_provider):
        """Arabic users get the same truth, not an English string or a blurb."""
        result = no_provider.respond(ARABIC_ADVICE_PROMPT)
        assert "غير متاحة" in result["message"]
        assert COSY_CAPABILITY_BLURB not in result["message"]
        assert result["error_code"] == "reasoning_provider_unavailable"

    def test_explicit_language_flag_also_honoured(self, no_provider):
        result = no_provider.respond("Give me a tip", language="ar")
        assert "غير متاحة" in result["message"]

    def test_hf_success_still_wins_over_the_unavailable_reply(self, no_provider, monkeypatch):
        """Honesty must not shadow a working backup.

        The unavailable reply is correct only when HF cannot serve the request —
        a live HF answer must still be returned unchanged.
        """
        monkeypatch.setenv("HF_TOKEN", "test-token-not-real")
        monkeypatch.setattr(
            RicoOpenAIAgent, "_call_hf_free",
            lambda self, *a, **k: {
                "type": "hf_response", "message": "Quantify your achievements.",
                "provider": "huggingface", "model": "test-model",
            },
        )
        result = RicoOpenAIAgent().respond(ADVICE_PROMPT)
        assert result["message"] == "Quantify your achievements."
        assert result["type"] == "hf_response"
        assert "error_code" not in result

    def test_hf_present_but_yielding_nothing_falls_through_to_honesty(self, no_provider, monkeypatch):
        monkeypatch.setenv("HF_TOKEN", "test-token-not-real")
        monkeypatch.setattr(RicoOpenAIAgent, "_call_hf_free", lambda self, *a, **k: None)
        result = RicoOpenAIAgent().respond(ADVICE_PROMPT)
        assert result["type"] == "reasoning_unavailable"
        assert COSY_CAPABILITY_BLURB not in result["message"]


# ── CASE A: honest text, but the markers used to be dropped ──────────────────

class TestConfiguredButFailingKeepsItsMarkers:
    def test_text_stays_honest(self, failing_provider):
        result = failing_provider.respond(ADVICE_PROMPT)
        assert result["message"] == REASONING_UNAVAILABLE_TEXT
        assert COSY_FREE_MODE_BLURB not in result["message"]

    def test_markers_survive_the_respond_boundary(self, failing_provider):
        """`_failure_payload` set these; `respond()` used to drop all three."""
        result = failing_provider.respond(ADVICE_PROMPT)
        assert result["error_code"] == "reasoning_provider_unavailable"
        assert result["provider_state"] == "degraded"
        assert result["error_category"] == "connection"
        assert result["response_source"] == "fallback"

    def test_existing_diagnostic_fields_are_unchanged(self, failing_provider):
        """The refactor is additive — nothing previously forwarded is lost."""
        result = failing_provider.respond(ADVICE_PROMPT)
        assert result["type"] == "deepseek_error_fallback"
        assert result["provider"] == "fallback"
        assert result["error"] == "RuntimeError"
        assert result["error_detail"]["error_category"] == "connection"
        assert result["deepseek_model"]
        assert result["fallback_model"]

    def test_rate_limited_stays_distinct_from_degraded(self, monkeypatch):
        """Throttled is reachable-but-busy — it must not read as a dead provider."""
        monkeypatch.setenv("RICO_AI_PROVIDER", "deepseek")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-not-real")
        for key in ("HF_TOKEN", "HF_API_TOKEN", "HF_API_KEY", "HUGGINGFACE_API_KEY"):
            monkeypatch.delenv(key, raising=False)
        import src.rico_openai_agent as agent_mod
        monkeypatch.setattr(
            agent_mod, "call_openai_minimal",
            lambda *a, **k: {
                "success": False, "is_rate_limited": True,
                "text": rt._RATE_LIMITED_TEXT, "error_category": "rate_limited",
            },
        )
        result = RicoOpenAIAgent().respond(ADVICE_PROMPT)
        assert result["provider_state"] == "rate_limited"
        assert result["response_source"] == "rate_limited"
        assert result["message"] == rt._RATE_LIMITED_TEXT

    def test_blank_provider_text_cannot_degrade_into_a_blurb(self, monkeypatch):
        """The removed default literal must not come back by another route."""
        monkeypatch.setenv("RICO_AI_PROVIDER", "deepseek")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-not-real")
        for key in ("HF_TOKEN", "HF_API_TOKEN", "HF_API_KEY", "HUGGINGFACE_API_KEY"):
            monkeypatch.delenv(key, raising=False)
        import src.rico_openai_agent as agent_mod
        monkeypatch.setattr(
            agent_mod, "call_openai_minimal",
            lambda *a, **k: {"success": False, "text": "", "error": "Boom"},
        )
        result = RicoOpenAIAgent().respond(ADVICE_PROMPT)
        assert result["message"] == REASONING_UNAVAILABLE_TEXT
        assert COSY_FREE_MODE_BLURB not in result["message"]


# ── Healthy paths must be untouched ──────────────────────────────────────────

class TestHealthyPathsUnchanged:
    def test_successful_reply_carries_no_failure_markers(self, monkeypatch):
        monkeypatch.setenv("RICO_AI_PROVIDER", "deepseek")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-not-real")
        import src.rico_openai_agent as agent_mod
        monkeypatch.setattr(
            agent_mod, "call_openai_minimal",
            lambda *a, **k: {"success": True, "text": "Quantify your achievements.",
                             "model": "deepseek-v4-flash"},
        )
        result = RicoOpenAIAgent().respond(ADVICE_PROMPT)
        assert result["message"] == "Quantify your achievements."
        assert result["type"] == "deepseek_response"
        assert "error_code" not in result
        assert "provider_state" not in result

    def test_safety_refusal_is_not_reinterpreted_as_a_provider_outage(self, no_provider, monkeypatch):
        """A refusal is a decision, not a failure — it must keep its own shape."""
        from src.rico_safety import RicoSafetyGuard

        class _Blocked:
            allowed = False
            safe_response = "I can't help with that."
            category = "forged_document"

        monkeypatch.setattr(RicoSafetyGuard, "check_message", lambda self, m: _Blocked())
        result = RicoOpenAIAgent().respond("forge me a diploma")
        assert result["type"] == "safety_refusal"
        assert "error_code" not in result


# ── Source-level lock: the dishonest literals are gone ───────────────────────

class TestDishonestLiteralsRemoved:
    def test_source_no_longer_contains_the_canned_answer_templates(self):
        """Defence in depth: the strings cannot be reintroduced unnoticed here.

        Scoped to the reasoning layer only — `rico_chat_api.py` carries its own
        copy of the capability blurb on a DIFFERENT (non-reasoning) path, which
        is deliberately out of this PR's scope.
        """
        src = Path("src/rico_openai_agent.py").read_text(encoding="utf-8")
        assert COSY_CAPABILITY_BLURB not in src
        assert COSY_FREE_MODE_BLURB not in src

    def test_both_failure_paths_tell_the_same_story(self, no_provider, failing_provider):
        """Case A and Case B must never drift into two different explanations."""
        assert (
            no_provider.respond(ADVICE_PROMPT)["message"]
            == failing_provider.respond(ADVICE_PROMPT)["message"]
            == REASONING_UNAVAILABLE_TEXT
        )
