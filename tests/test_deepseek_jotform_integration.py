"""Tests for DeepSeek, Hugging Face, and Jotform onboarding integration."""

import os
import pytest

from src.rico_env import get_ai_provider, _deepseek_key_present, _hf_key_present, _openai_key_present
from src.rico_openai_agent import RicoOpenAIAgent
from src.rico_chat_api import RicoChatAPI


class TestAIProviderSelection:
    """Test AI provider selection logic."""

    def test_deepseek_primary_when_key_present(self, monkeypatch):
        """DeepSeek is primary when DEEPSEEK_API_KEY is present."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test_key")
        monkeypatch.delenv("RICO_AI_KEY", raising=False)
        monkeypatch.delenv("RICO_AI_PROVIDER", raising=False)
        
        provider = get_ai_provider()
        assert provider == "deepseek"

    def test_deepseek_primary_when_explicit_provider(self, monkeypatch):
        """DeepSeek is primary when RICO_AI_PROVIDER=deepseek."""
        monkeypatch.setenv("RICO_AI_PROVIDER", "deepseek")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test_key")
        
        provider = get_ai_provider()
        assert provider == "deepseek"

    def test_hf_fallback_when_deepseek_unavailable(self, monkeypatch):
        """HF is used as fallback when DeepSeek is unavailable."""
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("RICO_AI_PROVIDER", raising=False)
        monkeypatch.setenv("HF_API_KEY", "test_hf_key")
        
        provider = get_ai_provider()
        assert provider == "huggingface"

    def test_none_when_no_keys(self, monkeypatch):
        """Returns 'none' when no AI keys are present."""
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("HF_API_KEY", raising=False)
        monkeypatch.delenv("HF_API_TOKEN", raising=False)
        monkeypatch.delenv("HF_TOKEN", raising=False)
        monkeypatch.delenv("HUGGINGFACE_API_KEY", raising=False)
        monkeypatch.delenv("RICO_AI_PROVIDER", raising=False)
        
        provider = get_ai_provider()
        assert provider == "none"

    def test_openai_never_auto_enabled(self, monkeypatch):
        """OpenAI is never auto-enabled to avoid billing surprises."""
        monkeypatch.setenv("OPENAI_API_KEY", "test_openai_key")
        monkeypatch.delenv("RICO_AI_PROVIDER", raising=False)
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("HF_API_KEY", raising=False)
        
        provider = get_ai_provider()
        assert provider != "openai"

    def test_openai_when_explicitly_set(self, monkeypatch):
        """OpenAI is used when explicitly set via RICO_AI_PROVIDER=openai."""
        monkeypatch.setenv("RICO_AI_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "test_openai_key")
        
        provider = get_ai_provider()
        assert provider == "openai"


class TestRicoOpenAIAgent:
    """Test RicoOpenAIAgent provider availability."""

    def test_deepseek_available_property(self, monkeypatch):
        """Agent reports DeepSeek availability correctly."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test_key")
        agent = RicoOpenAIAgent()
        assert agent.deepseek_available is True

    def test_deepseek_unavailable_without_key(self, monkeypatch):
        """Agent reports DeepSeek unavailable without key."""
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        agent = RicoOpenAIAgent()
        assert agent.deepseek_available is False

    def test_hf_available_property(self, monkeypatch):
        """Agent reports HF availability correctly."""
        monkeypatch.setenv("HF_API_KEY", "test_hf_key")
        agent = RicoOpenAIAgent()
        assert agent.hf_available is True

    def test_hf_available_with_aliases(self, monkeypatch):
        """Agent checks all HF key aliases."""
        monkeypatch.setenv("HF_TOKEN", "test_hf_token")
        agent = RicoOpenAIAgent()
        assert agent.hf_available is True

    def test_use_deepseek_property(self, monkeypatch):
        """Agent uses DeepSeek when provider=deepseek and key present."""
        monkeypatch.setenv("RICO_AI_PROVIDER", "deepseek")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test_key")
        agent = RicoOpenAIAgent()
        assert agent._use_deepseek is True

    def test_provider_available_property(self, monkeypatch):
        """Agent reports provider availability based on current provider."""
        monkeypatch.setenv("RICO_AI_PROVIDER", "deepseek")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test_key")
        agent = RicoOpenAIAgent()
        assert agent.provider_available is True


class TestJotformFormIdMetadata:
    """Test Jotform form ID surfacing in chat metadata."""

    def test_jotform_form_id_in_finalize_metadata(self, monkeypatch):
        """Jotform form ID is surfaced in chat metadata."""
        monkeypatch.setenv("JOTFORM_FORM_ID", "261277705943060")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test_key")
        
        api = RicoChatAPI()
        response = {
            "type": "test",
            "message": "Test message",
        }
        
        finalized = api._finalize(response, "test_source", profile=None)
        assert finalized.get("jotform_form_id") == "261277705943060"

    def test_jotform_rico_form_id_alias(self, monkeypatch):
        """JOTFORM_RICO_FORM_ID alias is recognized."""
        monkeypatch.setenv("JOTFORM_RICO_FORM_ID", "261277622782059")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test_key")
        
        api = RicoChatAPI()
        response = {
            "type": "test",
            "message": "Test message",
        }
        
        finalized = api._finalize(response, "test_source", profile=None)
        assert finalized.get("jotform_form_id") == "261277622782059"

    def test_jotform_form_id_primary_over_alias(self, monkeypatch):
        """JOTFORM_FORM_ID takes precedence over JOTFORM_RICO_FORM_ID."""
        monkeypatch.setenv("JOTFORM_FORM_ID", "261277705943060")
        monkeypatch.setenv("JOTFORM_RICO_FORM_ID", "261277622782059")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test_key")
        
        api = RicoChatAPI()
        response = {
            "type": "test",
            "message": "Test message",
        }
        
        finalized = api._finalize(response, "test_source", profile=None)
        assert finalized.get("jotform_form_id") == "261277705943060"

    def test_jotform_form_id_none_when_not_set(self, monkeypatch):
        """Jotform form ID is None when not configured."""
        monkeypatch.delenv("JOTFORM_FORM_ID", raising=False)
        monkeypatch.delenv("JOTFORM_RICO_FORM_ID", raising=False)
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test_key")
        
        api = RicoChatAPI()
        response = {
            "type": "test",
            "message": "Test message",
        }
        
        finalized = api._finalize(response, "test_source", profile=None)
        assert finalized.get("jotform_form_id") is None


class TestOnboardingCompletenessCheck:
    """Test profile/onboarding completeness checking."""

    def test_onboarding_complete_check_exists(self):
        """is_onboarding_complete function exists and is importable."""
        from src.repositories.onboarding_repo import is_onboarding_complete
        assert callable(is_onboarding_complete)

    def test_onboarding_status_in_profile_context(self):
        """ProfileContext has is_onboarding_complete property."""
        from src.services.profile_context_resolver import ProfileContext
        assert hasattr(ProfileContext, "is_onboarding_complete")
