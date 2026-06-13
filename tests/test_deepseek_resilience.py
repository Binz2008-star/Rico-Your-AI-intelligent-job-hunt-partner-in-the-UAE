"""Regression tests for DeepSeek provider resilience.

These tests verify:
- Invalid model names → next model in chain is tried, no hard failure
- Empty response text → safe fallback returned
- 400/401/403/500 errors → safe structured fallback, never "Something went wrong"
- Timeout → safe fallback
- 429 → rate_limited structured response
- No API key appears in any returned payload
- Deterministic intents (update profile, CV analysis, salary) do NOT call DeepSeek
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeAPIError(Exception):
    """Minimal stand-in for openai.APIError."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code
        self.request_id = None


class _FakeRateLimitError(_FakeAPIError):
    def __init__(self):
        super().__init__("Rate limit exceeded", status_code=429)


class _FakeTimeoutError(Exception):
    """Simulates a network timeout."""


def _make_chat_response(text: str):
    """Build a minimal chat completions response object."""
    content = SimpleNamespace(text=text, content=text)
    message = SimpleNamespace(content=text)
    choice = SimpleNamespace(message=message, delta=None)
    return SimpleNamespace(choices=[choice])


# ---------------------------------------------------------------------------
# _deepseek_model_chain
# ---------------------------------------------------------------------------

class TestDeepseekModelChain:
    def test_default_chain_starts_with_deepseek_chat(self, monkeypatch):
        monkeypatch.delenv("RICO_DEEPSEEK_MODEL", raising=False)
        monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
        monkeypatch.delenv("DEEPSEEK_FALLBACK_MODEL", raising=False)
        monkeypatch.delenv("DEEPSEEK_MODEL_CHAIN", raising=False)
        # Re-import with cleared env
        import importlib
        import src.rico_openai_runtime as m
        importlib.reload(m)
        chain = m._deepseek_model_chain()
        assert chain[0] == "deepseek-chat", f"Primary must be deepseek-chat, got {chain[0]}"
        assert "deepseek-chat" in chain

    def test_deepseek_chat_always_in_chain(self, monkeypatch):
        monkeypatch.setenv("RICO_DEEPSEEK_MODEL", "deepseek-reasoner")
        monkeypatch.setenv("DEEPSEEK_FALLBACK_MODEL", "deepseek-reasoner")
        monkeypatch.delenv("DEEPSEEK_MODEL_CHAIN", raising=False)
        import importlib, src.rico_openai_runtime as m
        importlib.reload(m)
        chain = m._deepseek_model_chain()
        # deepseek-chat must be appended as safe anchor even when not in env config
        assert "deepseek-chat" in chain

    def test_env_chain_override(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_MODEL_CHAIN", "model-a, model-b, model-c")
        import importlib, src.rico_openai_runtime as m
        importlib.reload(m)
        chain = m._deepseek_model_chain()
        assert chain == ["model-a", "model-b", "model-c"]


# ---------------------------------------------------------------------------
# call_openai_minimal — DeepSeek error scenarios
# ---------------------------------------------------------------------------

def _make_client_mock(side_effects):
    """Create a mock client whose chat.completions.create raises/returns in sequence."""
    client = MagicMock()
    client.chat.completions.create.side_effect = side_effects
    return client


@pytest.fixture(autouse=True)
def _reload_runtime(monkeypatch):
    """Ensure a clean module state with deepseek as active provider."""
    monkeypatch.setenv("RICO_AI_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-1234")
    monkeypatch.delenv("DEEPSEEK_MODEL_CHAIN", raising=False)
    monkeypatch.delenv("RICO_DEEPSEEK_MODEL", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.delenv("DEEPSEEK_FALLBACK_MODEL", raising=False)
    import importlib, src.rico_openai_runtime as m
    importlib.reload(m)


class TestDeepSeekInvalidModel:
    def test_invalid_model_400_tries_next_model(self, monkeypatch):
        """400 on first model must cause the next model in chain to be attempted."""
        import src.rico_openai_runtime as m

        calls = []

        def fake_create(model, messages, max_tokens, **kwargs):
            calls.append(model)
            if model != "deepseek-chat":
                raise _FakeAPIError("Model not found", status_code=400)
            return _make_chat_response("Hello from deepseek-chat!")

        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = fake_create

        with patch.object(m, "_build_client", return_value=fake_client):
            result = m.call_openai_minimal("Hello", provider="deepseek")

        assert result["success"] is True
        assert "deepseek-chat" in calls
        assert result["text"] == "Hello from deepseek-chat!"

    def test_all_models_fail_returns_structured_fallback(self, monkeypatch):
        """When all models fail, result must be a safe structured dict with no exception."""
        import src.rico_openai_runtime as m

        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = _FakeAPIError(
            "Model not found", status_code=400
        )

        with patch.object(m, "_build_client", return_value=fake_client):
            result = m.call_openai_minimal("Hello", provider="deepseek")

        assert result["success"] is False
        assert result.get("type") == "deepseek_error_fallback"
        assert result.get("provider_state") == "degraded"
        assert isinstance(result.get("text"), str)
        assert result["text"]  # non-empty
        assert "Something went wrong" not in result["text"]

    def test_all_models_fail_message_is_user_friendly(self, monkeypatch):
        import src.rico_openai_runtime as m

        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = _FakeAPIError(
            "Model not found", status_code=400
        )

        with patch.object(m, "_build_client", return_value=fake_client):
            result = m.call_openai_minimal("Hello", provider="deepseek")

        msg = result.get("text", "")
        assert "job search" in msg.lower() or "help" in msg.lower(), (
            f"Fallback message must be user-friendly, got: {msg!r}"
        )


class TestDeepSeekEmptyResponse:
    def test_empty_text_tries_next_model(self, monkeypatch):
        """Empty response text must trigger fallback to next model."""
        import src.rico_openai_runtime as m

        attempts = []

        def fake_create(model, messages, max_tokens, **kwargs):
            attempts.append(model)
            if model != "deepseek-chat":
                return _make_chat_response("")  # empty text
            return _make_chat_response("Useful reply")

        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = fake_create

        with patch.object(m, "_build_client", return_value=fake_client):
            result = m.call_openai_minimal("Hello", provider="deepseek")

        assert result["success"] is True
        assert result["text"] == "Useful reply"


class TestDeepSeekAuthErrors:
    @pytest.mark.parametrize("status_code", [401, 403, 500])
    def test_non_429_error_returns_safe_fallback(self, status_code, monkeypatch):
        """401/403/500 must return structured fallback, never crash."""
        import src.rico_openai_runtime as m

        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = _FakeAPIError(
            "Auth error", status_code=status_code
        )

        with patch.object(m, "_build_client", return_value=fake_client):
            result = m.call_openai_minimal("Hello", provider="deepseek")

        assert result["success"] is False
        assert isinstance(result.get("text"), str)
        assert result["text"]
        assert "Something went wrong" not in result["text"]

    def test_no_api_key_in_response(self, monkeypatch):
        """API key must never appear in the returned payload."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "dsk-supersecretkey1234")
        import src.rico_openai_runtime as m

        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = _FakeAPIError(
            "Auth error with key dsk-supersecretkey1234 in body", status_code=401
        )

        with patch.object(m, "_build_client", return_value=fake_client):
            result = m.call_openai_minimal("Hello", provider="deepseek")

        result_str = str(result)
        assert "supersecretkey" not in result_str, "Raw API key must not appear in response"


class TestDeepSeekTimeout:
    def test_timeout_returns_safe_fallback(self, monkeypatch):
        """Network timeout must return structured fallback, not raise."""
        import src.rico_openai_runtime as m

        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = _FakeTimeoutError("Connection timed out")

        with patch.object(m, "_build_client", return_value=fake_client):
            result = m.call_openai_minimal("Hello", provider="deepseek")

        assert result["success"] is False
        assert isinstance(result.get("text"), str)
        assert result["text"]


class TestDeepSeekRateLimit:
    def test_429_returns_structured_rate_limited_payload(self, monkeypatch):
        """429 must return a rate_limited structured dict immediately."""
        import src.rico_openai_runtime as m

        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = _FakeRateLimitError()

        with patch.object(m, "_build_client", return_value=fake_client):
            result = m.call_openai_minimal("Hello", provider="deepseek")

        assert result["success"] is False
        assert result.get("is_rate_limited") is True
        assert result.get("provider_state") == "rate_limited"
        assert isinstance(result.get("text"), str)
        assert result["text"]


# ---------------------------------------------------------------------------
# Deterministic intent paths must NOT call DeepSeek
# ---------------------------------------------------------------------------

class TestDeterministicIntentsSkipProvider:
    """Verify that known deterministic intents are routed before the AI provider."""

    def _make_profile(self):
        return SimpleNamespace(
            user_id="test@example.com",
            has_cv=True,
            target_roles=["Compliance Manager"],
            skills=["ISO 14001", "Risk Management"],
            certifications=[],
            years_experience=8,
            industries=[],
            preferred_cities=["Dubai"],
            current_role="Senior Compliance Officer",
            name="Test User",
            email="test@example.com",
            phone=None,
            telegram_username=None,
            nationality=None,
            languages=[],
            education=None,
            cv_text="Sample CV text",
            pasted_cv_text=None,
            uploaded_documents=[],
            onboarding_state="completed",
            subscription_tier="free",
            visa_status=None,
            job_search_status=None,
            profile_strength=None,
        )

    def _make_api(self, monkeypatch):
        from src.rico_chat_api import RicoChatAPI
        api = RicoChatAPI(persist=False)
        api.memory = MagicMock()
        api.memory.get.return_value = None
        api.openai_agent = MagicMock()
        api.openai_agent.respond.side_effect = AssertionError(
            "DeepSeek/AI provider must NOT be called for this deterministic intent"
        )
        monkeypatch.setattr(api, "_resolve_profile", lambda _uid: self._make_profile())
        monkeypatch.setattr(api, "_resolve_pending_field", lambda *_a, **_kw: None)
        return api

    def test_update_profile_does_not_call_ai(self, monkeypatch):
        api = self._make_api(monkeypatch)
        response = api._handle_active_user(
            "test@example.com",
            "Update my profile",
        )
        # Must return a response without hitting the AI provider
        assert isinstance(response, dict)
        assert response.get("type") != "error"

    def test_salary_enquiry_does_not_call_ai(self, monkeypatch):
        api = self._make_api(monkeypatch)
        response = api._handle_active_user(
            "test@example.com",
            "What salary should I expect as a Compliance Manager in Dubai?",
        )
        assert isinstance(response, dict)
        assert response.get("type") != "error"

    def test_cv_analysis_does_not_call_ai(self, monkeypatch):
        api = self._make_api(monkeypatch)
        response = api._handle_active_user(
            "test@example.com",
            "What are the weak points in my CV?",
        )
        assert isinstance(response, dict)
        assert response.get("type") != "error"
