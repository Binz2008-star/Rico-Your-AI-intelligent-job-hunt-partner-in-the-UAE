from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


def _profile() -> SimpleNamespace:
    return SimpleNamespace(
        has_cv=True,
        cv_filename="cv.pdf",
        cv_status="parsed",
        years_experience=10.0,
        preferred_cities=["Dubai"],
        skills=["HSE", "ISO 14001"],
        industries=["construction"],
        target_roles=["HSE Manager"],
    )


def _empty_after_filter_reply() -> dict[str, str]:
    return {
        "type": "deepseek_response",
        "message": "Which city do you want to target, and how many years of experience should I optimize for?",
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
    }


@pytest.fixture
def auth_client():
    from fastapi.testclient import TestClient
    from src.api.app import app
    from src.api.auth import create_access_token

    token = create_access_token({"sub": "alice@rico.ai", "role": "user"})
    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.set("access_token", token)
    return client


def test_process_message_converts_filtered_empty_ai_reply_to_error(monkeypatch):
    from src.rico_chat_api import RicoChatAPI

    monkeypatch.setattr("src.rico_chat_api.is_onboarding_complete", lambda _u: True)

    api = RicoChatAPI()
    api.memory = MagicMock()
    api._append_chat = MagicMock()
    api._resolve_profile = lambda _u: _profile()
    api.openai_agent = MagicMock()
    api.openai_agent.respond.return_value = _empty_after_filter_reply()

    response = api.process_message(
        "probe@example.com",
        "Analyze my current career trajectory in one paragraph.",
    )

    assert response["success"] is False
    assert response["type"] == "error"
    assert response["message"].strip()
    assert "Reference:" in response["message"]
    assert response["response_source"] == "deepseek"
    assert response["provider"] == "deepseek"
    assert response["error"] == "empty_message_after_filter"


def test_authenticated_chat_route_never_returns_success_true_with_empty_message(
    monkeypatch, auth_client
):
    monkeypatch.setattr("src.rico_chat_api.is_onboarding_complete", lambda _u: True)
    monkeypatch.setattr(
        "src.rico_chat_api.RicoChatAPI._resolve_profile",
        lambda self, _u: _profile(),
    )
    monkeypatch.setattr(
        "src.rico_chat_api.RicoChatAPI._append_chat",
        lambda self, user_id, role, message: None,
    )

    fake_agent = MagicMock()
    fake_agent.respond.return_value = _empty_after_filter_reply()
    monkeypatch.setattr(
        "src.rico_chat_api.RicoChatAPI._get_openai_agent",
        lambda self: fake_agent,
    )

    response = auth_client.post(
        "/api/v1/rico/chat",
        json={"message": "Analyze my current career trajectory in one paragraph."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["type"] == "error"
    assert body["message"].strip()
    assert "Reference:" in body["message"]
    assert body["response_source"] == "deepseek"
    assert body["provider"] == "deepseek"
    assert body["error"] == "empty_message_after_filter"
