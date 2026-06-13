"""
Hardening tests (Fix-5): H3 proxy-aware rate limiting, H4 forgot-password timing oracle,
H7 admin-only pipeline trigger.
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

os.environ.setdefault("ADMIN_EMAIL", "rico-admin@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Forgot-password is limited to 3/min and all TestClient calls share one key, so
    reset the limiter between tests to keep them independent."""
    from src.api.rate_limit import limiter
    try:
        limiter._storage.reset()
    except Exception:
        pass


# ── H3: rate-limit key resolves the real client behind a proxy ────────────────

def _request(headers: dict, client_host: str = "10.0.0.1"):
    from starlette.requests import Request
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": (client_host, 12345),
    }
    return Request(scope)


class TestRateLimitClientKey:
    def test_uses_first_forwarded_for_entry(self):
        from src.api.rate_limit import client_ip_key
        # Proxy IP is the TCP peer; the real client is in X-Forwarded-For.
        req = _request({"x-forwarded-for": "203.0.113.7"}, client_host="10.0.0.1")
        assert client_ip_key(req) == "203.0.113.7"

    def test_takes_leftmost_of_a_chain(self):
        from src.api.rate_limit import client_ip_key
        req = _request({"x-forwarded-for": "203.0.113.7, 10.0.0.1, 10.0.0.2"})
        assert client_ip_key(req) == "203.0.113.7"

    def test_falls_back_to_peer_without_header(self):
        from src.api.rate_limit import client_ip_key
        req = _request({}, client_host="198.51.100.5")
        assert client_ip_key(req) == "198.51.100.5"

    def test_blank_header_falls_back_to_peer(self):
        from src.api.rate_limit import client_ip_key
        req = _request({"x-forwarded-for": "   "}, client_host="198.51.100.5")
        assert client_ip_key(req) == "198.51.100.5"

    def test_distinct_clients_get_distinct_keys(self):
        """The core bug: behind a proxy every user must NOT collapse to one bucket."""
        from src.api.rate_limit import client_ip_key
        a = _request({"x-forwarded-for": "1.1.1.1"}, client_host="10.0.0.1")
        b = _request({"x-forwarded-for": "2.2.2.2"}, client_host="10.0.0.1")
        assert client_ip_key(a) != client_ip_key(b)


# ── H4: forgot-password defers work to a background task (no timing oracle) ───

class TestForgotPasswordTiming:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from src.api.app import app
        return TestClient(app, raise_server_exceptions=False)

    def test_registered_email_dispatches_in_background(self, client):
        from src.repositories.users_repo import User
        from datetime import datetime
        user = User(id=1, email="real@x.com", password_hash="x", role="user",
                    is_active=True, created_at=datetime.now(), last_login_at=None)
        with patch("src.repositories.users_repo.get_user_by_email", return_value=user), \
             patch("src.api.auth._dispatch_password_reset_email") as dispatch:
            r = client.post("/api/v1/auth/forgot-password", json={"email": "real@x.com"})
        assert r.status_code == 200
        # TestClient runs background tasks after the response — so dispatch must have fired.
        dispatch.assert_called_once_with("real@x.com")

    def test_unregistered_email_does_not_dispatch(self, client):
        # The endpoint always schedules the helper (to keep response timing constant);
        # the no-send guarantee for unknown emails now lives inside the helper, which
        # returns early before creating a token or sending an email.
        with patch("src.repositories.users_repo.get_user_by_email", return_value=None), \
             patch("src.repositories.password_reset_repo.create_reset_token") as create_tok, \
             patch("src.services.password_reset_email.send_password_reset_email") as send:
            r = client.post("/api/v1/auth/forgot-password", json={"email": "ghost@x.com"})
        assert r.status_code == 200
        create_tok.assert_not_called()
        send.assert_not_called()

    def test_response_body_identical_for_both(self, client):
        from src.repositories.users_repo import User
        from datetime import datetime
        user = User(id=1, email="real@x.com", password_hash="x", role="user",
                    is_active=True, created_at=datetime.now(), last_login_at=None)
        with patch("src.repositories.users_repo.get_user_by_email", return_value=user), \
             patch("src.api.auth._dispatch_password_reset_email"):
            r1 = client.post("/api/v1/auth/forgot-password", json={"email": "real@x.com"})
        with patch("src.repositories.users_repo.get_user_by_email", return_value=None):
            r2 = client.post("/api/v1/auth/forgot-password", json={"email": "ghost@x.com"})
        # No enumeration via response content either.
        assert r1.json() == r2.json()

    def test_dispatch_helper_creates_token_and_sends(self):
        from src.api import auth as auth_mod
        from src.repositories.users_repo import User
        from datetime import datetime
        user = User(id=1, email="real@x.com", password_hash="x", role="user",
                    is_active=True, created_at=datetime.now(), last_login_at=None)
        # The helper now resolves the user before creating a token — patch the lookup
        # so it proceeds to token creation and email delivery.
        with patch("src.repositories.users_repo.get_user_by_email", return_value=user), \
             patch("src.repositories.password_reset_repo.create_reset_token", return_value="tok123"), \
             patch("src.services.password_reset_email.send_password_reset_email", return_value=True) as send:
            auth_mod._dispatch_password_reset_email("real@x.com")
        send.assert_called_once_with("real@x.com", "tok123")


# ── H7: pipeline trigger is admin-only ────────────────────────────────────────

class TestPipelineTriggerAdminOnly:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from src.api.app import app
        return TestClient(app, raise_server_exceptions=False)

    @staticmethod
    def _token(role: str):
        from src.api.auth import create_access_token
        return create_access_token({"sub": f"{role}@rico.ai", "role": role})

    def test_non_admin_cannot_trigger(self, client):
        client.cookies.set("access_token", self._token("user"))
        r = client.post("/api/v1/pipeline/trigger")
        assert r.status_code == 403, r.text

    def test_unauthenticated_cannot_trigger(self, client):
        r = client.post("/api/v1/pipeline/trigger")
        assert r.status_code == 401, r.text

    def test_admin_can_trigger(self, client):
        client.cookies.set("access_token", self._token("admin"))
        with patch("src.api.routers.pipeline.trigger") as svc:
            r = client.post("/api/v1/pipeline/trigger")
        assert r.status_code == 200, r.text
        svc.assert_called_once()

    def test_status_still_allowed_for_regular_user(self, client):
        """Read-only status stays available to authenticated non-admins (no regression)."""
        client.cookies.set("access_token", self._token("user"))
        with patch("src.api.routers.pipeline.get_status", return_value={"status": "idle"}):
            r = client.get("/api/v1/pipeline/status")
        assert r.status_code == 200, r.text
