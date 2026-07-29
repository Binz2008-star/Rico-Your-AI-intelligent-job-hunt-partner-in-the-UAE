"""Regression coverage for Rico application-tailoring AI client wiring."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src import rico_apply_ai


@pytest.mark.parametrize(
    ("provider", "primary_model"),
    (("openai", "gpt-test"), ("deepseek", "deepseek-test")),
)
def test_get_ai_client_uses_current_runtime_helpers(
    provider: str,
    primary_model: str,
) -> None:
    """Supported providers resolve without the removed _primary_model_for symbol."""
    client = object()

    with (
        patch("src.rico_env.get_ai_provider", return_value=provider),
        patch(
            "src.rico_openai_runtime._provider_key_present",
            return_value=True,
        ) as key_present,
        patch(
            "src.rico_openai_runtime._provider_models",
            return_value=(primary_model, "fallback-model"),
        ) as provider_models,
        patch(
            "src.rico_openai_runtime._build_client",
            return_value=client,
        ) as build_client,
    ):
        resolved = rico_apply_ai._get_ai_client()

    assert resolved == (client, provider, primary_model)
    key_present.assert_called_once_with(provider)
    provider_models.assert_called_once_with(provider)
    build_client.assert_called_once_with(provider)


def test_removed_primary_model_symbol_no_longer_causes_silent_degradation() -> None:
    """The previous missing import must not force the generic fallback path."""
    import src.rico_openai_runtime as runtime

    assert not hasattr(runtime, "_primary_model_for")

    client = object()
    with (
        patch("src.rico_env.get_ai_provider", return_value="openai"),
        patch.object(runtime, "_provider_key_present", return_value=True),
        patch.object(
            runtime,
            "_provider_models",
            return_value=("gpt-test", "gpt-fallback"),
        ),
        patch.object(runtime, "_build_client", return_value=client),
    ):
        resolved = rico_apply_ai._get_ai_client()

    assert resolved == (client, "openai", "gpt-test")


def test_missing_provider_key_returns_unavailable_without_building_client() -> None:
    with (
        patch("src.rico_env.get_ai_provider", return_value="openai"),
        patch(
            "src.rico_openai_runtime._provider_key_present",
            return_value=False,
        ),
        patch("src.rico_openai_runtime._provider_models") as provider_models,
        patch("src.rico_openai_runtime._build_client") as build_client,
    ):
        resolved = rico_apply_ai._get_ai_client()

    assert resolved == (None, None, None)
    provider_models.assert_not_called()
    build_client.assert_not_called()


@pytest.mark.parametrize("provider", ("none", "huggingface"))
def test_unsupported_provider_returns_unavailable_without_client(
    provider: str,
) -> None:
    with (
        patch("src.rico_env.get_ai_provider", return_value=provider),
        patch(
            "src.rico_openai_runtime._provider_key_present"
        ) as key_present,
        patch("src.rico_openai_runtime._provider_models") as provider_models,
        patch("src.rico_openai_runtime._build_client") as build_client,
    ):
        resolved = rico_apply_ai._get_ai_client()

    assert resolved == (None, None, None)
    key_present.assert_not_called()
    provider_models.assert_not_called()
    build_client.assert_not_called()


def test_call_ai_extracts_openai_responses_text() -> None:
    response = SimpleNamespace(output_text="  Tailored CV  ", output=[])
    create = MagicMock(return_value=response)
    client = SimpleNamespace(responses=SimpleNamespace(create=create))

    text = rico_apply_ai._call_ai(
        client,
        "openai",
        "gpt-test",
        "system prompt",
        "user prompt",
    )

    assert text == "Tailored CV"
    create.assert_called_once()


def test_call_ai_extracts_deepseek_chat_completion_text() -> None:
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="  Cover letter  ")
            )
        ]
    )
    create = MagicMock(return_value=response)
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )

    text = rico_apply_ai._call_ai(
        client,
        "deepseek",
        "deepseek-test",
        "system prompt",
        "user prompt",
    )

    assert text == "Cover letter"
    create.assert_called_once()


@pytest.mark.parametrize("provider", ("openai", "deepseek"))
def test_call_ai_rejects_empty_provider_output(provider: str) -> None:
    if provider == "openai":
        response = SimpleNamespace(output_text="", output=[])
        client = SimpleNamespace(
            responses=SimpleNamespace(create=MagicMock(return_value=response))
        )
    else:
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=""))]
        )
        client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=MagicMock(return_value=response))
            )
        )

    with pytest.raises(ValueError, match="no usable text"):
        rico_apply_ai._call_ai(
            client,
            provider,
            "test-model",
            "system prompt",
            "user prompt",
        )


def test_empty_ai_output_falls_back_without_raising() -> None:
    response = SimpleNamespace(output_text="", output=[])
    client = SimpleNamespace(
        responses=SimpleNamespace(create=MagicMock(return_value=response))
    )
    job = {
        "title": "HSE Manager",
        "company": "Example Company",
        "description": "Safety leadership role",
        "location": "Dubai",
    }

    with patch(
        "src.rico_apply_ai._get_ai_client",
        return_value=(client, "openai", "gpt-test"),
    ):
        result = rico_apply_ai.tailor_application(
            "Original CV text",
            {"name": "Candidate"},
            job,
        )

    assert result["tailored_cv"] == "Original CV text"
    assert "HSE Manager" in result["cover_letter"]
    assert "Example Company" in result["cover_letter"]
