#!/usr/bin/env python3
"""Test Rico free AI provider mode functionality."""

import os
import pytest
from unittest.mock import patch, Mock
from starlette.requests import Request

from src.rico_env import get_ai_provider
from src.services.chat_service import send_message

_AI_ENV_VARS = [
    "OPENAI_API_KEY",
    "OPEN_AI_API",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_BASE_URL",
    "DEEPSEEK_MODEL",
    "DEEPSEEK_FALLBACK_MODEL",
    "HF_API_TOKEN",
    "HF_TOKEN",
    "HF_API_KEY",
    "HUGGINGFACE_API_KEY",
    "RICO_AI_PROVIDER",
]


@pytest.fixture(autouse=True)
def clear_ai_env():
    saved = {name: os.environ.get(name) for name in _AI_ENV_VARS}
    for name in _AI_ENV_VARS:
        os.environ.pop(name, None)
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


class TestFreeProviderMode:
    """Test free AI provider mode functionality."""

    def test_get_ai_provider_default(self):
        """Test that default provider is 'none' when env var is not set."""
        with patch.dict(os.environ, {}, clear=True):
            assert get_ai_provider() == "none"

    def test_get_ai_provider_none(self):
        """Test that provider='none' is respected."""
        with patch.dict(os.environ, {"RICO_AI_PROVIDER": "none"}):
            assert get_ai_provider() == "none"

    def test_get_ai_provider_openai(self):
        """Test that provider='openai' is respected."""
        with patch.dict(os.environ, {"RICO_AI_PROVIDER": "openai"}):
            assert get_ai_provider() == "openai"

    def test_get_ai_provider_huggingface(self):
        """Test that provider='huggingface' is respected."""
        with patch.dict(os.environ, {"RICO_AI_PROVIDER": "huggingface"}):
            assert get_ai_provider() == "huggingface"

    def test_get_ai_provider_deepseek(self):
        """Test that provider='deepseek' is respected."""
        with patch.dict(os.environ, {"RICO_AI_PROVIDER": "deepseek"}):
            assert get_ai_provider() == "deepseek"

    def test_get_ai_provider_invalid(self):
        """Test that invalid provider defaults to auto-detect (none when no keys)."""
        with patch.dict(os.environ, {"RICO_AI_PROVIDER": "invalid"}, clear=True):
            assert get_ai_provider() == "none"

    def test_get_ai_provider_auto_detects_hf(self):
        """Test that HF key auto-detects huggingface provider."""
        with patch.dict(os.environ, {"HF_TOKEN": "hf_test_token"}, clear=True):
            assert get_ai_provider() == "huggingface"

    def test_get_ai_provider_auto_detects_hf_api_token_alias(self):
        """Test that HF_API_TOKEN is treated as a valid HF key alias."""
        with patch.dict(os.environ, {"HF_API_TOKEN": "hf_test_token"}, clear=True):
            assert get_ai_provider() == "huggingface"

    def test_get_ai_provider_deepseek_priority_over_hf(self):
        """Test that DeepSeek wins auto-detect when both DeepSeek and HF keys are present."""
        with patch.dict(
            os.environ,
            {"HF_TOKEN": "hf_test", "DEEPSEEK_API_KEY": "dsk-test"},
            clear=True,
        ):
            assert get_ai_provider() == "deepseek"

    def test_get_ai_provider_auto_detects_deepseek(self):
        """Test that a DeepSeek key auto-detects DeepSeek."""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "dsk-test-token"}, clear=True):
            assert get_ai_provider() == "deepseek"

    def test_get_ai_provider_case_insensitive(self):
        """Test that provider is case insensitive."""
        with patch.dict(os.environ, {"RICO_AI_PROVIDER": "none"}):
            assert get_ai_provider() == "none"
        with patch.dict(os.environ, {"RICO_AI_PROVIDER": "openai"}):
            assert get_ai_provider() == "openai"
        with patch.dict(os.environ, {"RICO_AI_PROVIDER": "DeepSeek"}):
            assert get_ai_provider() == "deepseek"

    def test_get_ai_provider_hf_alias(self):
        """Test that 'hf' shorthand resolves to 'huggingface'."""
        with patch.dict(os.environ, {"RICO_AI_PROVIDER": "hf"}):
            assert get_ai_provider() == "huggingface"
        with patch.dict(os.environ, {"RICO_AI_PROVIDER": "HF"}):
            assert get_ai_provider() == "huggingface"

    def test_send_message_returns_dict_with_message_key(self):
        """send_message always returns a dict containing at least a 'message' key."""
        from src.schemas.chat import RicoSessionContext
        from unittest.mock import patch as _patch
        ctx = RicoSessionContext.for_authenticated("test@example.com")
        ai_reply = {"type": "smalltalk", "message": "Hello!", "response_source": "keyword"}
        with _patch("src.services.chat_service._legacy_send_message", return_value=ai_reply), \
             _patch("src.services.subscription_gating.check_ai_message_allowed", return_value=None):
            result = send_message(ctx=ctx, message="Hello")
        assert isinstance(result, dict)
        assert "message" in result

    def test_openai_smoke_route_removed(self):
        """#1077: rico_openai_smoke no longer exists in the router module —
        the user-callable paid probe was removed, not just gated."""
        import src.api.routers.rico_chat as _chat_mod
        assert not hasattr(_chat_mod, "rico_openai_smoke")
        assert not hasattr(_chat_mod, "call_openai_minimal")
