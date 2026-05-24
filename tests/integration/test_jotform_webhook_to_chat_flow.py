"""Integration test for public chat with email-based user identification.

This test verifies that:
1. Public chat endpoint accepts email as an alternative to session_id
2. Email-based user_id is passed to the chat service correctly
3. Session-based user_id still works for anonymous users
"""
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def client():
    """Test client for API endpoints."""
    from fastapi.testclient import TestClient
    from src.api.app import app
    return TestClient(app, raise_server_exceptions=False)


class TestPublicChatWithEmail:
    """Test public chat endpoint with email-based user identification."""

    def test_public_chat_accepts_email_instead_of_session_id(self, client):
        """Verify that public chat accepts email for user identification."""
        with patch("src.services.chat_service.send_message") as mock_send_message:
            mock_send_message.return_value = {
                "type": "assistant",
                "message": "Hello!",
                "matches": [],
            }

            response = client.post(
                "/api/v1/rico/chat/public",
                json={
                    "message": "Find me jobs",
                    "email": "test@example.com",
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["type"] == "assistant"
            assert data["message"] == "Hello!"

            # Verify the chat service received the email as user_id via SessionContext
            mock_send_message.assert_called_once()
            call_kwargs = mock_send_message.call_args[1]
            assert call_kwargs["ctx"].user_id == "test@example.com"

    def test_public_chat_uses_session_id_when_no_email_provided(self, client):
        """Verify that public chat still works with session_id for anonymous users."""
        with patch("src.services.chat_service.send_message") as mock_send_message:
            mock_send_message.return_value = {
                "type": "assistant",
                "message": "Hello anonymous user",
                "matches": [],
            }

            response = client.post(
                "/api/v1/rico/chat/public",
                json={
                    "message": "Hello",
                    "session_id": "public-session-123",
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Hello anonymous user"

            # Verify the chat service received the session-based user_id via SessionContext
            mock_send_message.assert_called_once()
            call_kwargs = mock_send_message.call_args[1]
            assert call_kwargs["ctx"].user_id == "public:public-session-123"

    def test_public_chat_requires_either_session_id_or_email(self, client):
        """Verify that public chat rejects requests without session_id or email."""
        response = client.post(
            "/api/v1/rico/chat/public",
            json={
                "message": "Hello",
            }
        )
        assert response.status_code == 422

    def test_public_chat_email_validation(self, client):
        """Verify that public chat validates email format."""
        invalid_emails = [
            "invalid-email",
            "no-at-symbol",
            "",
        ]

        for invalid_email in invalid_emails:
            response = client.post(
                "/api/v1/rico/chat/public",
                json={
                    "message": "Hello",
                    "email": invalid_email,
                }
            )
            assert response.status_code == 422

    def test_public_chat_email_is_normalized_to_lowercase(self, client):
        """Verify that email is normalized to lowercase."""
        with patch("src.services.chat_service.send_message") as mock_send_message:
            mock_send_message.return_value = {
                "type": "assistant",
                "message": "Hello",
                "matches": [],
            }

            response = client.post(
                "/api/v1/rico/chat/public",
                json={
                    "message": "Hello",
                    "email": "Test@Example.COM",
                }
            )
            assert response.status_code == 200

            # Verify the chat service received lowercase email via SessionContext
            mock_send_message.assert_called_once()
            call_kwargs = mock_send_message.call_args[1]
            assert call_kwargs["ctx"].user_id == "test@example.com"

    def test_public_chat_email_takes_precedence_over_session_id(self, client):
        """Verify that email takes precedence when both are provided."""
        with patch("src.services.chat_service.send_message") as mock_send_message:
            mock_send_message.return_value = {
                "type": "assistant",
                "message": "Hello",
                "matches": [],
            }

            response = client.post(
                "/api/v1/rico/chat/public",
                json={
                    "message": "Hello",
                    "email": "user@example.com",
                    "session_id": "ignored-session",
                }
            )
            assert response.status_code == 200

            # Verify email was used, not session_id
            mock_send_message.assert_called_once()
            call_kwargs = mock_send_message.call_args[1]
            assert call_kwargs["ctx"].user_id == "user@example.com"
            assert call_kwargs["ctx"].user_id != "public:ignored-session"

    def test_public_chat_returns_safe_provider_metadata_only(self, client):
        """Public chat may expose provider metadata, but must not leak internal diagnostics."""
        with patch("src.services.chat_service.send_message") as mock_send_message:
            mock_send_message.return_value = {
                "type": "deepseek_response",
                "message": "Hello!",
                "matches": [],
                "response_source": "deepseek",
                "provider": "deepseek",
                "provider_state": "available",
                "internal_debug": {"secret": "should-not-leak"},
                "raw_prompt": "should-not-leak",
            }

            response = client.post(
                "/api/v1/rico/chat/public",
                json={
                    "message": "Hello",
                    "session_id": "public-session-123",
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Hello!"
            assert data["response_source"] == "deepseek"
            assert data["provider"] == "deepseek"
            assert data["provider_state"] == "available"
            assert "internal_debug" not in data
            assert "raw_prompt" not in data
