"""
Regression test for Bug 2: jotform_form_id null crashes frontend Zod validation.

When JOTFORM_FORM_ID env var is empty/unset, _finalize() used to include
"jotform_form_id": None (JSON null).  The frontend Zod schema expects
z.string().optional() which rejects null, causing validateShape to throw and
the user sees "Something went wrong. Please try again."

Fix: _finalize() now always emits a string (empty string when env var absent).
"""

import os
from unittest.mock import MagicMock, patch
import pytest


class TestJotformFormIdNeverNull:
    def test_finalize_returns_string_when_env_unset(self, monkeypatch):
        """_finalize() must not include null for jotform_form_id."""
        monkeypatch.delenv("JOTFORM_FORM_ID", raising=False)
        monkeypatch.delenv("JOTFORM_RICO_FORM_ID", raising=False)

        import src.rico_chat_api as mod
        from src.rico_chat_api import RicoChatAPI

        mock_agent = MagicMock()
        mock_agent.openai_available = False
        mock_agent.deepseek_available = False
        mock_agent.hf_available = False
        mock_agent.provider_available = True
        mock_agent.model = "gpt-4o"

        api = RicoChatAPI()
        monkeypatch.setattr(api, "_get_openai_agent", lambda: mock_agent)

        result = api._finalize(
            {"type": "options", "message": "Next, choose what you want me to do."},
            "keyword",
        )

        assert "jotform_form_id" in result
        assert result["jotform_form_id"] is not None, (
            "jotform_form_id must never be None — Zod z.string().optional() rejects null"
        )
        assert isinstance(result["jotform_form_id"], str)

    def test_finalize_returns_form_id_when_env_set(self, monkeypatch):
        """When env var is set, _finalize() must return its value as a string."""
        monkeypatch.setenv("JOTFORM_FORM_ID", "12345678")

        import src.rico_chat_api as mod
        from src.rico_chat_api import RicoChatAPI

        mock_agent = MagicMock()
        mock_agent.openai_available = False
        mock_agent.deepseek_available = False
        mock_agent.hf_available = False
        mock_agent.provider_available = True
        mock_agent.model = "gpt-4o"

        api = RicoChatAPI()
        monkeypatch.setattr(api, "_get_openai_agent", lambda: mock_agent)

        result = api._finalize(
            {"type": "response", "message": "Hello"},
            "keyword",
        )

        assert result["jotform_form_id"] == "12345678"

    def test_finalize_returns_empty_string_when_env_empty(self, monkeypatch):
        """Empty env var must produce empty string, not None."""
        monkeypatch.setenv("JOTFORM_FORM_ID", "")
        monkeypatch.setenv("JOTFORM_RICO_FORM_ID", "")

        import src.rico_chat_api as mod
        from src.rico_chat_api import RicoChatAPI

        mock_agent = MagicMock()
        mock_agent.openai_available = False
        mock_agent.deepseek_available = False
        mock_agent.hf_available = False
        mock_agent.provider_available = True
        mock_agent.model = "gpt-4o"

        api = RicoChatAPI()
        monkeypatch.setattr(api, "_get_openai_agent", lambda: mock_agent)

        result = api._finalize(
            {"type": "response", "message": "Hello"},
            "keyword",
        )

        assert isinstance(result["jotform_form_id"], str)
        assert result["jotform_form_id"] == ""
