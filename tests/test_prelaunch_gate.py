"""Focused tests for the opt-in pre-launch gate and waitlist intake.

No test touches a real database or external service.
"""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.app import app
from src.repositories.waitlist_repo import WaitlistUnavailable
from src.services.launch_mode import (
    get_launch_mode,
    is_public_during_waitlist,
    is_request_allowed,
)


WAITLIST_ENV = {
    "RICO_LAUNCH_MODE": "waitlist",
    "INTERNAL_ALLOWLIST_EMAILS": "internal@example.com",
    "ADMIN_EMAIL": "owner@example.com",
    "JWT_SECRET": "x" * 32,
    "COOKIE_SECURE": "false",
    "RICO_ENV": "test",
}


def _request(path: str, *, email: str | None = None, method: str = "GET"):
    current_user = {"email": email, "role": "user"} if email else None
    return SimpleNamespace(
        url=SimpleNamespace(path=path),
        method=method,
        state=SimpleNamespace(current_user=current_user),
    )


def _reset_limiter() -> None:
    from src.api.rate_limit import limiter

    try:
        limiter._storage.reset()
    except Exception:
        pass


class TestLaunchModePolicy:
    def test_missing_mode_preserves_live_product(self):
        with patch.dict(os.environ, {}, clear=True):
            assert get_launch_mode() == "live"

    def test_invalid_mode_fails_open_to_current_live_behavior(self):
        with patch.dict(os.environ, {"RICO_LAUNCH_MODE": "unexpected"}, clear=True):
            assert get_launch_mode() == "live"

    def test_waitlist_public_contract_is_explicit(self):
        assert is_public_during_waitlist("/api/v1/auth/login", "POST") is True
        assert is_public_during_waitlist("/api/v1/waitlist/register", "POST") is True
        assert is_public_during_waitlist("/health", "GET") is True
        assert is_public_during_waitlist("/api/v1/rico/chat/public", "POST") is False
        assert is_public_during_waitlist("/api/v1/auth/register", "POST") is False

    def test_non_internal_product_api_request_is_blocked(self):
        with patch.dict(os.environ, WAITLIST_ENV, clear=False):
            assert is_request_allowed(_request("/api/v1/rico/profile")) is False
            assert (
                is_request_allowed(
                    _request("/api/v1/rico/profile", email="external@example.com")
                )
                is False
            )

    def test_internal_and_owner_emails_are_allowed(self):
        with patch.dict(os.environ, WAITLIST_ENV, clear=False):
            assert (
                is_request_allowed(
                    _request("/api/v1/rico/profile", email="INTERNAL@example.com")
                )
                is True
            )
            assert (
                is_request_allowed(
                    _request("/api/v1/rico/profile", email="owner@example.com")
                )
                is True
            )

    def test_live_mode_does_not_change_existing_api_access(self):
        with patch.dict(os.environ, {"RICO_LAUNCH_MODE": "live"}, clear=False):
            assert is_request_allowed(_request("/api/v1/rico/profile")) is True


class TestPrelaunchHTTPGate:
    def setup_method(self):
        _reset_limiter()

    def test_non_allowlisted_login_is_rejected_before_credentials_or_cookie(self):
        client = TestClient(app, raise_server_exceptions=False)
        with patch.dict(os.environ, WAITLIST_ENV, clear=False), patch(
            "src.api.auth.verify_credentials"
        ) as verify:
            response = client.post(
                "/api/v1/auth/login",
                json={"email": "external@example.com", "password": "ValidPass1"},
            )

        assert response.status_code == 403
        assert response.json()["code"] == "prelaunch_access_required"
        assert response.cookies.get("access_token") is None
        verify.assert_not_called()

    def test_allowlisted_login_uses_existing_auth_contract(self):
        client = TestClient(app, raise_server_exceptions=False)
        with patch.dict(os.environ, WAITLIST_ENV, clear=False), patch(
            "src.api.auth.verify_credentials",
            return_value={
                "email": "internal@example.com",
                "role": "user",
                "email_verified": True,
            },
        ):
            response = client.post(
                "/api/v1/auth/login",
                json={"email": "internal@example.com", "password": "ValidPass1"},
            )

        assert response.status_code == 200
        assert response.cookies.get("access_token") is not None

    def test_signup_and_public_chat_are_blocked_in_waitlist_mode(self):
        client = TestClient(app, raise_server_exceptions=False)
        with patch.dict(os.environ, WAITLIST_ENV, clear=False):
            signup = client.post(
                "/api/v1/auth/register",
                json={"email": "new@example.com", "password": "ValidPass1"},
            )
            chat = client.post(
                "/api/v1/rico/chat/public",
                json={"message": "hello", "user_id": "public:testuser1"},
            )

        assert signup.status_code == 403
        assert chat.status_code == 403
        assert signup.json()["code"] == "prelaunch_access_required"
        assert chat.json()["code"] == "prelaunch_access_required"

    def test_prelaunch_access_decision_reflects_authenticated_allowlist(self):
        from src.api.auth import create_access_token

        client = TestClient(app, raise_server_exceptions=False)
        token = create_access_token({"sub": "internal@example.com", "role": "user"})
        client.cookies.set("access_token", token)
        with patch.dict(os.environ, WAITLIST_ENV, clear=False):
            response = client.get("/api/v1/prelaunch/access")

        assert response.status_code == 200
        assert response.json() == {"mode": "waitlist", "allowed": True}


class TestWaitlistIntake:
    def setup_method(self):
        _reset_limiter()

    def test_endpoint_is_hidden_while_product_is_live(self):
        client = TestClient(app, raise_server_exceptions=False)
        with patch.dict(os.environ, {"RICO_LAUNCH_MODE": "live"}, clear=False), patch(
            "src.api.routers.waitlist.upsert_waitlist_entry"
        ) as upsert:
            response = client.post(
                "/api/v1/waitlist/register",
                json={"email": "person@example.com", "consent": True},
            )

        assert response.status_code == 404
        upsert.assert_not_called()

    def test_waitlist_submission_is_consent_gated_and_persisted_once_by_repository(self):
        client = TestClient(app, raise_server_exceptions=False)
        with patch.dict(os.environ, WAITLIST_ENV, clear=False), patch(
            "src.api.routers.waitlist.upsert_waitlist_entry"
        ) as upsert:
            response = client.post(
                "/api/v1/waitlist/register",
                json={
                    "email": " Person@Example.com ",
                    "first_name": " Person ",
                    "target_role": " Product Manager ",
                    "location": "Dubai",
                    "consent": True,
                    "source": {"utm_source": "qa", "unknown": "ignored"},
                },
            )

        assert response.status_code == 200
        assert response.json()["success"] is True
        upsert.assert_called_once_with(
            email="person@example.com",
            first_name="Person",
            target_role="Product Manager",
            location="Dubai",
            consent=True,
            source={"utm_source": "qa"},
        )

    def test_waitlist_persistence_failure_is_sanitized(self):
        client = TestClient(app, raise_server_exceptions=False)
        with patch.dict(os.environ, WAITLIST_ENV, clear=False), patch(
            "src.api.routers.waitlist.upsert_waitlist_entry",
            side_effect=WaitlistUnavailable("database details must not leak"),
        ):
            response = client.post(
                "/api/v1/waitlist/register",
                json={"email": "person@example.com", "consent": True},
            )

        assert response.status_code == 503
        detail = response.json()["detail"].lower()
        assert "database" not in detail
        assert "details" not in detail

    def test_missing_consent_is_rejected_before_repository_write(self):
        client = TestClient(app, raise_server_exceptions=False)
        with patch.dict(os.environ, WAITLIST_ENV, clear=False), patch(
            "src.api.routers.waitlist.upsert_waitlist_entry"
        ) as upsert:
            response = client.post(
                "/api/v1/waitlist/register",
                json={"email": "person@example.com", "consent": False},
            )

        assert response.status_code == 422
        upsert.assert_not_called()
