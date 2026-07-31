"""Provider-agnostic guard for identity/contact details in external drafts.

Production incident: Rico inserted an unconfirmed candidate name and phone
number into an Arabic HR follow-up message, then claimed the name came from
registered account data without a source it could prove. This suite pins the
shared prompt contract on both the premium and HuggingFace provider paths.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from src.rico_identity import (
    EXTERNAL_DRAFT_IDENTITY_RULE,
    get_grounding_contract,
    get_rico_system_prompt,
)
from src.rico_openai_agent import RicoOpenAIAgent
from src.rico_openai_runtime import call_openai_minimal


def test_external_draft_rule_is_shared_by_primary_and_fallback_prompts():
    assert EXTERNAL_DRAFT_IDENTITY_RULE in get_rico_system_prompt()
    assert EXTERNAL_DRAFT_IDENTITY_RULE in get_grounding_contract()


def test_external_draft_rule_pins_confirmation_conflict_and_source_behavior():
    low = EXTERNAL_DRAFT_IDENTITY_RULE.lower()
    for field in ("name", "email", "phone", "linkedin_url"):
        assert f"`{field}`" in EXTERNAL_DRAFT_IDENTITY_RULE
    assert "not automatically approved" in low
    assert "explicitly confirmed" in low
    assert "neutral placeholder" in low
    assert "omit the signature/contact block" in low
    assert "do not choose one" in low
    assert "one concise confirmation question" in low
    assert "source cannot be verified" in low
    assert "registered account data" in low
    assert "unless the current context proves that source" in low


def test_primary_provider_receives_external_draft_rule(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dsk-test")
    captured: dict[str, object] = {}

    class _Completions:
        @staticmethod
        def create(**kwargs):
            captured.update(kwargs)
            message = SimpleNamespace(content="OK")
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))
    with patch("src.rico_openai_runtime._build_client", return_value=client):
        result = call_openai_minimal(
            "Draft an HR follow-up email.",
            profile_context='{"name":"Unconfirmed Name","phone":"+971500000000"}',
            provider="deepseek",
        )

    assert result["success"] is True
    messages = captured["messages"]
    assert EXTERNAL_DRAFT_IDENTITY_RULE in messages[0]["content"]


def test_huggingface_fallback_receives_the_same_external_draft_rule(monkeypatch):
    monkeypatch.setenv("HF_API_TOKEN", "hf-test")
    captured: dict[str, object] = {}

    def _generate(prompt, **kwargs):
        captured["prompt"] = prompt
        captured.update(kwargs)
        return "OK"

    with patch("src.rico_hf_client.is_available", return_value=True), patch(
        "src.rico_hf_client.generate_text", side_effect=_generate
    ):
        result = RicoOpenAIAgent()._call_hf_free(
            "اكتب رسالة متابعة للموارد البشرية",
            {"name": "اسم غير مؤكد", "phone": "+971500000000"},
            language="ar",
        )

    assert result and result["message"] == "OK"
    assert EXTERNAL_DRAFT_IDENTITY_RULE in captured["system"]
