"""
tests/test_users_auth.py
Tests for DB-backed authentication, role claims, and user registration.

All DB calls are patched — no real database required.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import psycopg2

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _reset_limiter() -> None:
    from src.api.rate_limit import limiter
    try:
        limiter._storage.reset()
    except Exception:
        pass
os.environ.setdefault("ADMIN_EMAIL",    "admin@test.com")
os.environ.setdefault("ADMIN_PASSWORD", "TestPass123")
os.environ.setdefault("JWT_SECRET",     "x" * 32)

from src.repositories.users_repo import User

_DB_USER = User(
    id=1,
    email="alice@rico.ai",
    password_hash="$2b$12$placeholder",   # will be replaced by mock
    role="user",
    is_active=True,
    created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    last_login_at=None,
)

_ADMIN_USER = User(
    id=2,
    email="admin@rico.ai",
    password_hash="$2b$12$placeholder",
    role="admin",
    is_active=True,
    created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    last_login_at=None,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_admin_client():
    from fastapi.testclient import TestClient
    from src.api.app import app
    from src.api.auth import create_access_token
    token = create_access_token({"sub": "admin@test.com", "role": "admin"})
    tc = TestClient(app, raise_server_exceptions=False)
    tc.cookies.set("access_token", token)
    return tc


def _make_user_client():
    from fastapi.testclient import TestClient
    from src.api.app import app
    from src.api.auth import create_access_token
    token = create_access_token({"sub": "user@test.com", "role": "user"})
    tc = TestClient(app, raise_server_exceptions=False)
    tc.cookies.set("access_token", token)
    return tc


def _make_legacy_client():
    """JWT issued before roles were added — no 'role' claim."""
    from fastapi.testclient import TestClient
    from src.api.app import app
    from src.api.auth import create_access_token
    token = create_access_token({"sub": "legacy@test.com"})   # no role key
    tc = TestClient(app, raise_server_exceptions=False)
    tc.cookies.set("access_token", token)
    return tc


@pytest.fixture(scope="module")
def admin_client():
    return _make_admin_client()


@pytest.fixture(scope="module")
def user_client():
    return _make_user_client()


@pytest.fixture(scope="module")
def legacy_client():
    return _make_legacy_client()


# ── verify_credentials ────────────────────────────────────────────────────────

class TestVerifyCredentials:
    def test_db_path_success(self):
        from src.api.auth import verify_credentials
        with patch("src.repositories.users_repo.get_user_by_email", return_value=_DB_USER), \
             patch("src.api.auth._verify_password", return_value=True):
            result = verify_credentials("alice@rico.ai", "correctpass")
        assert result is not None
        assert result["email"] == "alice@rico.ai"
        assert result["role"] == "user"

    def test_db_path_wrong_password(self):
        from src.api.auth import verify_credentials
        with patch("src.repositories.users_repo.get_user_by_email", return_value=_DB_USER), \
             patch("src.api.auth._verify_password", return_value=False):
            result = verify_credentials("alice@rico.ai", "wrongpass")
        assert result is None

    def test_env_fallback_when_db_unavailable(self):
        from src.api.auth import verify_credentials
        env = {"ADMIN_EMAIL": "admin@test.com", "ADMIN_PASSWORD": "TestPass123", "ADMIN_PASSWORD_HASH": ""}
        with patch("src.repositories.users_repo.get_user_by_email", return_value=None), \
             patch.dict(os.environ, env, clear=False):
            result = verify_credentials("admin@test.com", "TestPass123")
        assert result is not None
        assert result["email"] == "admin@test.com"
        assert result["role"] == "admin"

    def test_env_fallback_wrong_password(self):
        from src.api.auth import verify_credentials
        env = {"ADMIN_EMAIL": "admin@test.com", "ADMIN_PASSWORD": "TestPass123", "ADMIN_PASSWORD_HASH": ""}
        with patch("src.repositories.users_repo.get_user_by_email", return_value=None), \
             patch.dict(os.environ, env, clear=False):
            result = verify_credentials("admin@test.com", "wrongpass")
        assert result is None

    def test_unknown_email_returns_none(self):
        from src.api.auth import verify_credentials
        env = {"ADMIN_EMAIL": "admin@test.com", "ADMIN_PASSWORD_HASH": ""}
        with patch("src.repositories.users_repo.get_user_by_email", return_value=None), \
             patch.dict(os.environ, env, clear=False):
            result = verify_credentials("nobody@example.com", "pass")
        assert result is None

    def test_db_error_falls_back_to_env(self):
        from src.api.auth import verify_credentials
        env = {"ADMIN_EMAIL": "admin@test.com", "ADMIN_PASSWORD": "TestPass123", "ADMIN_PASSWORD_HASH": ""}
        with patch("src.repositories.users_repo.get_user_by_email",
                   side_effect=psycopg2.OperationalError("db down")), \
             patch.dict(os.environ, env, clear=False):
            result = verify_credentials("admin@test.com", "TestPass123")
        assert result is not None
        assert result["role"] == "admin"


# ── Role claim in JWT ─────────────────────────────────────────────────────────

class TestJWTRoleClaim:
    def test_login_embeds_role_in_token(self):
        from fastapi.testclient import TestClient
        from src.api.app import app
        from src.api.rate_limit import limiter
        limiter._storage.reset()   # other test files exhaust the 5/min login quota
        tc = TestClient(app, raise_server_exceptions=False)
        with patch("src.api.auth.verify_credentials",
                   return_value={"email": "admin@test.com", "role": "admin"}):
            r = tc.post("/api/v1/auth/login",
                        json={"email": "admin@test.com", "password": "TestPass123"})
        assert r.status_code == 200
        cookie = r.cookies.get("access_token")
        assert cookie is not None
        from src.api.auth import decode_access_token
        payload = decode_access_token(cookie)
        assert payload["role"] == "admin"

    def test_get_current_user_returns_role(self, admin_client):
        r = admin_client.get("/api/v1/auth/me")
        assert r.status_code == 200
        assert r.json()["role"] == "admin"

    def test_legacy_token_without_role_defaults_to_user(self, legacy_client):
        r = legacy_client.get("/api/v1/auth/me")
        assert r.status_code == 200
        assert r.json()["role"] == "user"

    def test_user_role_reflected_correctly(self, user_client):
        r = user_client.get("/api/v1/auth/me")
        assert r.status_code == 200
        assert r.json()["role"] == "user"


class TestCookieSessionSettings:
    def test_login_sets_secure_cross_subdomain_cookie_flags(self):
        from fastapi.testclient import TestClient
        from src.api.app import app
        from src.api.rate_limit import limiter

        limiter._storage.reset()
        tc = TestClient(app, raise_server_exceptions=False)
        env = {
            "COOKIE_SECURE": "true",
            "COOKIE_DOMAIN": ".ricohunt.com",
            "APP_URL": "https://ricohunt.com",
            "RICO_ENV": "production",
        }
        with patch.dict(os.environ, env, clear=False), \
             patch("src.api.auth.verify_credentials", return_value={"email": "admin@test.com", "role": "admin"}):
            r = tc.post(
                "/api/v1/auth/login",
                json={"email": "admin@test.com", "password": "TestPass123"},
            )

        assert r.status_code == 200
        set_cookie = r.headers.get("set-cookie", "")
        set_cookie_lower = set_cookie.lower()
        assert "access_token=" in set_cookie
        assert "httponly" in set_cookie_lower
        assert "secure" in set_cookie_lower
        assert "samesite=lax" in set_cookie_lower
        assert "domain=.ricohunt.com" in set_cookie_lower

    def test_cookie_secure_false_rejected_in_production(self):
        from src.api.auth import _cookie_secure

        env = {
            "COOKIE_SECURE": "false",
            "RICO_ENV": "production",
        }
        with patch.dict(os.environ, env, clear=False):
            with pytest.raises(RuntimeError, match="COOKIE_SECURE must be true"):
                _cookie_secure()


# ── require_admin dependency ──────────────────────────────────────────────────

class TestRequireAdmin:
    def test_any_user_can_register(self, user_client):
        """Register is now public — any caller (even authenticated) can create an account."""
        _reset_limiter()
        with patch("src.repositories.users_repo.get_user_by_email", return_value=None), \
             patch("src.api.auth._hash_password", return_value="$2b$12$fakehash"), \
             patch("src.repositories.users_repo.create_user", return_value=User(
                 id=5, email="new@rico.ai", password_hash="$2b$12$fakehash",
                 role="user", is_active=True,
                 created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                 last_login_at=None,
             )):
            r = user_client.post("/api/v1/auth/register",
                                 json={"email": "new@rico.ai", "password": "SecurePass1"})
        assert r.status_code == 201

    def test_unauthenticated_can_register(self):
        """Register is public — no JWT required."""
        from fastapi.testclient import TestClient
        from src.api.app import app
        _reset_limiter()
        tc = TestClient(app, raise_server_exceptions=False)
        with patch("src.repositories.users_repo.get_user_by_email", return_value=None), \
             patch("src.api.auth._hash_password", return_value="$2b$12$fakehash"), \
             patch("src.repositories.users_repo.create_user", return_value=User(
                 id=6, email="anon@rico.ai", password_hash="$2b$12$fakehash",
                 role="user", is_active=True,
                 created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                 last_login_at=None,
             )):
            r = tc.post("/api/v1/auth/register",
                        json={"email": "anon@rico.ai", "password": "Pass1234xx"})
        assert r.status_code == 201


# ── Register endpoint ─────────────────────────────────────────────────────────

class TestRegisterEndpoint:
    def test_register_returns_201_with_user_fields(self, user_client):
        _reset_limiter()
        created = User(
            id=10, email="newuser@rico.ai", password_hash="$2b$12$fakehash",
            role="user", is_active=True,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_login_at=None,
        )
        with patch("src.repositories.users_repo.get_user_by_email", return_value=None), \
             patch("src.api.auth._hash_password", return_value="$2b$12$fakehash"), \
             patch("src.repositories.users_repo.create_user", return_value=created):
            r = user_client.post("/api/v1/auth/register",
                                  json={"email": "newuser@rico.ai", "password": "SecurePass1"})
        assert r.status_code == 201
        data = r.json()
        assert data["email"] == "newuser@rico.ai"
        assert data["role"] == "user"
        assert data["created"] is True

    def test_register_clears_stale_access_token_cookie(self, user_client):
        _reset_limiter()
        created = User(
            id=16, email="fresh@rico.ai", password_hash="$2b$12$fakehash",
            role="user", is_active=True,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_login_at=None,
        )
        with patch("src.repositories.users_repo.get_user_by_email", return_value=None), \
             patch("src.api.auth._hash_password", return_value="$2b$12$fakehash"), \
             patch("src.repositories.users_repo.create_user", return_value=created):
            r = user_client.post(
                "/api/v1/auth/register",
                json={"email": "fresh@rico.ai", "password": "SecurePass1"},
            )

        assert r.status_code == 201
        set_cookies = r.headers.get_list("set-cookie")
        assert any(
            header.startswith("access_token=") and "Max-Age=0" in header
            for header in set_cookies
        )

    def test_register_attempts_admin_signup_notification(self, user_client):
        _reset_limiter()
        created = User(
            id=12, email="notify@rico.ai", password_hash="$2b$12$fakehash",
            role="user", is_active=True,
            created_at=datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc),
            last_login_at=None,
        )
        env = {
            "ENABLE_SIGNUP_EMAIL_NOTIFICATIONS": "true",
            "ADMIN_SIGNUP_NOTIFICATION_EMAIL": "info@ricohunt.com",
        }
        with patch("src.repositories.users_repo.get_user_by_email", return_value=None), \
             patch("src.api.auth._hash_password", return_value="$2b$12$fakehash"), \
             patch("src.repositories.users_repo.create_user", return_value=created), \
             patch("src.services.signup_notifications.send_email", return_value=True) as send_email, \
             patch.dict(os.environ, env, clear=False):
            r = user_client.post(
                "/api/v1/auth/register",
                json={"email": "notify@rico.ai", "password": "SecurePass1"},
            )

        assert r.status_code == 201
        send_email.assert_called_once()
        kwargs = send_email.call_args.kwargs
        assert kwargs["to_email"] == "info@ricohunt.com"
        assert kwargs["subject"] == "New RicoHunt signup — notify@rico.ai"
        assert "Email: notify@rico.ai" in kwargs["body"]
        assert "User ID: 12" in kwargs["body"]
        assert "Plan: free" in kwargs["body"]
        assert "Signup source: website" in kwargs["body"]

    def test_register_succeeds_when_signup_notification_fails(self, user_client):
        _reset_limiter()
        created = User(
            id=13, email="mailfail@rico.ai", password_hash="$2b$12$fakehash",
            role="user", is_active=True,
            created_at=datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc),
            last_login_at=None,
        )
        with patch("src.repositories.users_repo.get_user_by_email", return_value=None), \
             patch("src.api.auth._hash_password", return_value="$2b$12$fakehash"), \
             patch("src.repositories.users_repo.create_user", return_value=created), \
             patch("src.services.signup_notifications.send_email", side_effect=RuntimeError("provider down")), \
             patch.dict(os.environ, {"ENABLE_SIGNUP_EMAIL_NOTIFICATIONS": "true"}, clear=False):
            r = user_client.post(
                "/api/v1/auth/register",
                json={"email": "mailfail@rico.ai", "password": "SecurePass1"},
            )

        assert r.status_code == 201
        assert r.json()["email"] == "mailfail@rico.ai"

    def test_signup_notification_payload_excludes_sensitive_fields(self, user_client):
        _reset_limiter()
        created = User(
            id=14, email="safe@rico.ai", password_hash="$2b$12$fakehash",
            role="user", is_active=True,
            created_at=datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc),
            last_login_at=None,
        )
        with patch("src.repositories.users_repo.get_user_by_email", return_value=None), \
             patch("src.api.auth._hash_password", return_value="$2b$12$fakehash"), \
             patch("src.repositories.users_repo.create_user", return_value=created), \
             patch("src.services.signup_notifications.send_email", return_value=True) as send_email, \
             patch.dict(os.environ, {"ENABLE_SIGNUP_EMAIL_NOTIFICATIONS": "true"}, clear=False):
            r = user_client.post(
                "/api/v1/auth/register",
                json={
                    "email": "safe@rico.ai",
                    "password": "DoNotLeakPass123",
                    "role": "admin",
                    "public_user_id_to_merge": "public:abc12345",
                },
            )

        assert r.status_code == 201
        body = send_email.call_args.kwargs["body"]
        assert "DoNotLeakPass123" not in body
        assert "password" not in body.lower()
        assert "access_token" not in body
        assert "session" not in body.lower()
        assert "cookie" not in body.lower()
        assert "reset" not in body.lower()
        assert "public:abc12345" not in body

    def test_signup_notification_can_be_disabled(self, user_client):
        _reset_limiter()
        created = User(
            id=15, email="disabled@rico.ai", password_hash="$2b$12$fakehash",
            role="user", is_active=True,
            created_at=datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc),
            last_login_at=None,
        )
        with patch("src.repositories.users_repo.get_user_by_email", return_value=None), \
             patch("src.api.auth._hash_password", return_value="$2b$12$fakehash"), \
             patch("src.repositories.users_repo.create_user", return_value=created), \
             patch("src.services.signup_notifications.send_email", return_value=True) as send_email, \
             patch.dict(os.environ, {"ENABLE_SIGNUP_EMAIL_NOTIFICATIONS": "false"}, clear=False):
            r = user_client.post(
                "/api/v1/auth/register",
                json={"email": "disabled@rico.ai", "password": "SecurePass1"},
            )

        assert r.status_code == 201
        send_email.assert_not_called()

    def test_register_duplicate_returns_409(self, admin_client):
        _reset_limiter()
        with patch("src.repositories.users_repo.get_user_by_email", return_value=_DB_USER):
            r = admin_client.post("/api/v1/auth/register",
                                  json={"email": "alice@rico.ai", "password": "SecurePass1"})
        assert r.status_code == 409

    def test_register_db_unavailable_returns_503(self, admin_client):
        _reset_limiter()
        with patch("src.repositories.users_repo.get_user_by_email", return_value=None), \
             patch("src.api.auth._hash_password", return_value="$2b$12$fakehash"), \
             patch("src.repositories.users_repo.create_user", return_value=None):
            r = admin_client.post("/api/v1/auth/register",
                                  json={"email": "dbdown@rico.ai", "password": "SecurePass1"})
        assert r.status_code == 503

    def test_register_short_password_returns_422(self, admin_client):
        _reset_limiter()
        r = admin_client.post("/api/v1/auth/register",
                              json={"email": "weak@rico.ai", "password": "short"})
        assert r.status_code == 422

    def test_register_role_forced_to_user(self, admin_client):
        """Role in request body is ignored — always forced to user."""
        _reset_limiter()
        created = User(
            id=11, email="newadmin@rico.ai", password_hash="$2b$12$fakehash",
            role="user", is_active=True,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_login_at=None,
        )
        with patch("src.repositories.users_repo.get_user_by_email", return_value=None), \
             patch("src.api.auth._hash_password", return_value="$2b$12$fakehash"), \
             patch("src.repositories.users_repo.create_user", return_value=created):
            r = admin_client.post("/api/v1/auth/register",
                                  json={"email": "newadmin@rico.ai",
                                        "password": "SecurePass1", "role": "admin"})
        assert r.status_code == 201
        assert r.json()["role"] == "user"  # always forced to user, never admin


# ── users_repo unit tests ─────────────────────────────────────────────────────

class TestUsersRepo:
    def test_get_user_by_email_returns_none_when_db_unavailable(self):
        from src.repositories.users_repo import get_user_by_email
        with patch("src.db.is_db_available", return_value=False):
            result = get_user_by_email("any@example.com")
        assert result is None

    def test_get_user_by_email_returns_none_on_no_connection(self):
        from src.repositories.users_repo import get_user_by_email
        with patch("src.db.is_db_available", return_value=True), \
             patch("src.db.get_db_connection", return_value=None):
            result = get_user_by_email("any@example.com")
        assert result is None

    def test_create_user_returns_none_when_db_unavailable(self):
        from src.repositories.users_repo import create_user
        with patch("src.db.is_db_available", return_value=False):
            result = create_user("new@rico.ai", "hash")
        assert result is None

    def test_update_last_login_silently_skips_when_db_unavailable(self):
        from src.repositories.users_repo import update_last_login
        with patch("src.db.is_db_available", return_value=False):
            update_last_login(1)  # must not raise


# ── Login input validation ─────────────────────────────────────────────────────

class TestLoginInputValidation:
    def test_oversized_login_password_returns_422(self):
        """bcrypt DoS guard — passwords over 128 chars must be rejected at schema level."""
        from fastapi.testclient import TestClient
        from src.api.app import app
        from src.api.rate_limit import limiter
        limiter._storage.reset()
        tc = TestClient(app, raise_server_exceptions=False)
        r = tc.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "A" * 129},
        )
        assert r.status_code == 422

    def test_invalid_email_format_returns_422(self):
        from fastapi.testclient import TestClient
        from src.api.app import app
        from src.api.rate_limit import limiter
        limiter._storage.reset()
        tc = TestClient(app, raise_server_exceptions=False)
        r = tc.post(
            "/api/v1/auth/login",
            json={"email": "not-an-email", "password": "TestPass123"},
        )
        assert r.status_code == 422


# ── Production DB-failure fallback guard ───────────────────────────────────────

class TestProductionFallbackGuard:
    def test_production_db_error_rejects_login(self):
        """In production mode, a DB error must not allow env-var admin fallback."""
        from src.api.auth import verify_credentials
        env = {
            "ADMIN_EMAIL": "admin@test.com",
            "ADMIN_PASSWORD": "TestPass123",
            "ADMIN_PASSWORD_HASH": "",
            "RICO_ENV": "production",
            "ALLOW_ENV_AUTH_FALLBACK": "",
        }
        with patch("src.repositories.users_repo.get_user_by_email",
                   side_effect=psycopg2.OperationalError("db down")), \
             patch.dict(os.environ, env, clear=False):
            result = verify_credentials("admin@test.com", "TestPass123")
        assert result is None

    def test_production_fallback_allowed_when_flag_set(self):
        """ALLOW_ENV_AUTH_FALLBACK=true re-enables fallback even in production."""
        from src.api.auth import verify_credentials
        env = {
            "ADMIN_EMAIL": "admin@test.com",
            "ADMIN_PASSWORD": "TestPass123",
            "ADMIN_PASSWORD_HASH": "",
            "RICO_ENV": "production",
            "ALLOW_ENV_AUTH_FALLBACK": "true",
        }
        with patch("src.repositories.users_repo.get_user_by_email",
                   side_effect=psycopg2.OperationalError("db down")), \
             patch.dict(os.environ, env, clear=False):
            result = verify_credentials("admin@test.com", "TestPass123")
        assert result is not None
        assert result["role"] == "admin"

    def test_dev_db_error_still_falls_back(self):
        """Outside production the original fallback behaviour is preserved."""
        from src.api.auth import verify_credentials
        env = {
            "ADMIN_EMAIL": "admin@test.com",
            "ADMIN_PASSWORD": "TestPass123",
            "ADMIN_PASSWORD_HASH": "",
            "RICO_ENV": "development",
            "ALLOW_ENV_AUTH_FALLBACK": "",
        }
        with patch("src.repositories.users_repo.get_user_by_email",
                   side_effect=psycopg2.OperationalError("db down")), \
             patch.dict(os.environ, env, clear=False):
            result = verify_credentials("admin@test.com", "TestPass123")
        assert result is not None
        assert result["role"] == "admin"


# ── Email verification flow ────────────────────────────────────────────────────

class TestEmailVerificationFlow:
    def _verified_user(self) -> "User":
        return User(
            id=20, email="verified@rico.ai", password_hash="$2b$12$hash",
            role="user", is_active=True,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_login_at=None,
            email_verified=True,
        )

    def _unverified_user(self) -> "User":
        return User(
            id=21, email="unverified@rico.ai", password_hash="$2b$12$hash",
            role="user", is_active=True,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_login_at=None,
            email_verified=False,
        )

    def test_register_returns_email_verification_required(self):
        from fastapi.testclient import TestClient
        from src.api.app import app
        _reset_limiter()
        tc = TestClient(app, raise_server_exceptions=False)
        new_user = User(
            id=22, email="newver@rico.ai", password_hash="$2b$12$hash",
            role="user", is_active=True,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_login_at=None,
            email_verified=False,
        )
        with patch("src.repositories.users_repo.get_user_by_email", return_value=None), \
             patch("src.api.auth._hash_password", return_value="$2b$12$hash"), \
             patch("src.repositories.users_repo.create_user", return_value=new_user), \
             patch("src.repositories.email_verification_repo.create_verification_token",
                   return_value="raw-token-abc"), \
             patch("src.services.verification_email.send_email", return_value=True):
            r = tc.post("/api/v1/auth/register",
                        json={"email": "newver@rico.ai", "password": "SecurePass1"})
        assert r.status_code == 201
        data = r.json()
        assert data["email_verification_required"] is True

    def test_register_does_not_set_jwt_cookie(self):
        from fastapi.testclient import TestClient
        from src.api.app import app
        _reset_limiter()
        tc = TestClient(app, raise_server_exceptions=False)
        new_user = User(
            id=23, email="nocookie@rico.ai", password_hash="$2b$12$hash",
            role="user", is_active=True,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_login_at=None,
            email_verified=False,
        )
        with patch("src.repositories.users_repo.get_user_by_email", return_value=None), \
             patch("src.api.auth._hash_password", return_value="$2b$12$hash"), \
             patch("src.repositories.users_repo.create_user", return_value=new_user), \
             patch("src.repositories.email_verification_repo.create_verification_token",
                   return_value="tok"), \
             patch("src.services.verification_email.send_email", return_value=True):
            r = tc.post("/api/v1/auth/register",
                        json={"email": "nocookie@rico.ai", "password": "SecurePass1"})
        assert r.status_code == 201
        assert "access_token" not in r.cookies

    def test_register_schedules_verification_email_to_user(self):
        from fastapi.testclient import TestClient
        from src.api.app import app
        _reset_limiter()
        tc = TestClient(app, raise_server_exceptions=False)
        new_user = User(
            id=24, email="vermail@rico.ai", password_hash="$2b$12$hash",
            role="user", is_active=True,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_login_at=None,
            email_verified=False,
        )
        with patch("src.repositories.users_repo.get_user_by_email", return_value=None), \
             patch("src.api.auth._hash_password", return_value="$2b$12$hash"), \
             patch("src.repositories.users_repo.create_user", return_value=new_user), \
             patch("src.repositories.email_verification_repo.create_verification_token",
                   return_value="raw-abc"), \
             patch("src.services.verification_email.send_email", return_value=True) as mock_send:
            r = tc.post("/api/v1/auth/register",
                        json={"email": "vermail@rico.ai", "password": "SecurePass1"})
        assert r.status_code == 201
        mock_send.assert_called_once()
        assert mock_send.call_args.kwargs["to_email"] == "vermail@rico.ai"
        body = mock_send.call_args.kwargs["body"]
        assert "raw-abc" in body
        assert "24h" in body or "24 hours" in body

    def test_verification_email_subject_does_not_contain_token(self):
        from src.services.verification_email import send_verification_email
        with patch("src.services.verification_email.send_email", return_value=True) as mock_send:
            send_verification_email("user@example.com", "super-secret-tok")
        kwargs = mock_send.call_args.kwargs
        assert "super-secret-tok" not in kwargs["subject"]
        assert "super-secret-tok" in kwargs["body"]

    def test_login_blocked_when_email_not_verified(self):
        from fastapi.testclient import TestClient
        from src.api.app import app
        _reset_limiter()
        tc = TestClient(app, raise_server_exceptions=False)
        with patch("src.api.auth.verify_credentials",
                   return_value={"id": 21, "email": "unverified@rico.ai", "role": "user",
                                 "email_verified": False}), \
             patch("src.repositories.users_repo.update_last_login") as mock_ull:
            r = tc.post("/api/v1/auth/login",
                        json={"email": "unverified@rico.ai", "password": "pass"})
        assert r.status_code == 403
        assert "verify" in r.json()["detail"].lower()
        mock_ull.assert_not_called()

    def test_login_succeeds_when_email_verified(self):
        from fastapi.testclient import TestClient
        from src.api.app import app
        _reset_limiter()
        tc = TestClient(app, raise_server_exceptions=False)
        with patch("src.api.auth.verify_credentials",
                   return_value={"id": 20, "email": "verified@rico.ai", "role": "user",
                                 "email_verified": True}), \
             patch("src.repositories.users_repo.update_last_login") as mock_ull:
            r = tc.post("/api/v1/auth/login",
                        json={"email": "verified@rico.ai", "password": "pass"})
        assert r.status_code == 200
        mock_ull.assert_called_once_with(20)

    def test_verify_email_valid_token_marks_verified_no_cookie(self):
        from fastapi.testclient import TestClient
        from src.api.app import app
        _reset_limiter()
        tc = TestClient(app, raise_server_exceptions=False)
        with patch("src.repositories.email_verification_repo.consume_verification_token",
                   return_value="verified@rico.ai"), \
             patch("src.repositories.users_repo.mark_email_verified", return_value=True):
            r = tc.get("/api/v1/auth/verify-email?token=valid-tok-abc")
        assert r.status_code == 200
        assert r.json()["email"] == "verified@rico.ai"
        # GET /verify-email intentionally does not set a session cookie —
        # user must sign in explicitly after verification.
        assert "access_token" not in r.cookies

    def test_verify_email_invalid_token_returns_400(self):
        from fastapi.testclient import TestClient
        from src.api.app import app
        _reset_limiter()
        tc = TestClient(app, raise_server_exceptions=False)
        with patch("src.repositories.email_verification_repo.consume_verification_token",
                   return_value=None):
            r = tc.get("/api/v1/auth/verify-email?token=bad-token")
        assert r.status_code == 400

    def test_verify_email_reused_token_returns_400(self):
        from fastapi.testclient import TestClient
        from src.api.app import app
        _reset_limiter()
        tc = TestClient(app, raise_server_exceptions=False)
        with patch("src.repositories.email_verification_repo.consume_verification_token",
                   return_value=None):
            r = tc.get("/api/v1/auth/verify-email?token=used-token")
        assert r.status_code == 400

    def test_resend_verification_returns_generic_response(self):
        from fastapi.testclient import TestClient
        from src.api.app import app
        _reset_limiter()
        tc = TestClient(app, raise_server_exceptions=False)
        with patch("src.repositories.users_repo.get_user_by_email",
                   return_value=self._unverified_user()), \
             patch("src.repositories.email_verification_repo.create_verification_token",
                   return_value="tok"), \
             patch("src.services.verification_email.send_email", return_value=True):
            r = tc.post("/api/v1/auth/resend-verification",
                        json={"email": "unverified@rico.ai"})
        assert r.status_code == 200
        assert "message" in r.json()

    def test_resend_verification_unknown_email_returns_generic(self):
        from fastapi.testclient import TestClient
        from src.api.app import app
        _reset_limiter()
        tc = TestClient(app, raise_server_exceptions=False)
        with patch("src.repositories.users_repo.get_user_by_email", return_value=None):
            r = tc.post("/api/v1/auth/resend-verification",
                        json={"email": "ghost@nobody.com"})
        assert r.status_code == 200

    def test_resend_verification_already_verified_returns_generic(self):
        from fastapi.testclient import TestClient
        from src.api.app import app
        _reset_limiter()
        tc = TestClient(app, raise_server_exceptions=False)
        with patch("src.repositories.users_repo.get_user_by_email",
                   return_value=self._verified_user()):
            r = tc.post("/api/v1/auth/resend-verification",
                        json={"email": "verified@rico.ai"})
        assert r.status_code == 200

    def test_verify_credentials_returns_email_verified_field(self):
        from src.api.auth import verify_credentials
        verified = self._verified_user()
        with patch("src.repositories.users_repo.get_user_by_email", return_value=verified), \
             patch("src.api.auth._verify_password", return_value=True):
            result = verify_credentials("verified@rico.ai", "pass")
        assert result is not None
        assert "email_verified" in result
        assert result["email_verified"] is True
        assert "id" in result  # needed by login() to call update_last_login after email check

    def test_existing_user_migration_defaults_to_verified(self):
        u = User(
            id=99, email="legacy@rico.ai", password_hash="$2b$12$hash",
            role="user", is_active=True,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_login_at=None,
            email_verified=True,
        )
        assert u.email_verified is True
