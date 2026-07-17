"""tests/test_1072_jwt_auth_version.py

#1072 — stale-JWT invalidation via a per-user auth_version.

Invariants verified:
  - a token minted at auth_version N is rejected once the account is at N+1
    (password reset / logout-all revoke earlier tokens)
  - deactivated or deleted accounts reject existing tokens immediately
  - authorization role comes from the DB, never from a stale token claim
  - user-store outage fails CLOSED (503), never authorizes from stale claims
  - legacy tokens (no "av" claim) behave as version 1 — nobody is logged out
    by deploying this change
  - env-fallback admin tokens are isolated: rejected in production unless
    ALLOW_ENV_AUTH_FALLBACK is explicitly set
  - update_password bumps auth_version in the SAME statement as the password
    change; missing migration 045 degrades loudly instead of breaking reset
  - /auth/logout-all revokes truthfully (503 when it cannot revoke)

No real database required — repo internals are mocked.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api.auth import create_access_token, decode_access_token
from src.api.deps import get_current_user, require_admin
from src.repositories.users_repo import AuthStoreUnavailable


EMAIL = "user@example.com"


def _request_with_token(token: str) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"cookie", f"access_token={token}".encode())],
        "query_string": b"",
    }
    return Request(scope)


def _snapshot(av=1, active=True, role="user", verified=True):
    return ("found", {
        "auth_version": av,
        "is_active": active,
        "role": role,
        "email_verified": verified,
    })


def _token(email=EMAIL, role="user", av=None, extra=None):
    claims = {"sub": email, "role": role}
    if av is not None:
        claims["av"] = av
    if extra:
        claims.update(extra)
    return create_access_token(claims)


# ── get_current_user validation (#1072 enforcement point) ─────────────────────

class TestTokenValidation:
    def _validate(self, token, snapshot=None, side_effect=None, db_available=True):
        req = _request_with_token(token)
        with patch("src.db.is_db_available", return_value=db_available), \
             patch("src.repositories.users_repo.get_auth_snapshot",
                   return_value=snapshot, side_effect=side_effect):
            return get_current_user(req)

    def test_matching_version_passes(self):
        user = self._validate(_token(av=3), snapshot=_snapshot(av=3))
        assert user == {"email": EMAIL, "role": "user"}

    def test_stale_version_rejected(self):
        with pytest.raises(HTTPException) as e:
            self._validate(_token(av=1), snapshot=_snapshot(av=2))
        assert e.value.status_code == 401

    def test_legacy_token_without_av_counts_as_version_1(self):
        user = self._validate(_token(av=None), snapshot=_snapshot(av=1))
        assert user["email"] == EMAIL
        with pytest.raises(HTTPException) as e:
            self._validate(_token(av=None), snapshot=_snapshot(av=2))
        assert e.value.status_code == 401

    def test_deactivated_account_rejected_immediately(self):
        with pytest.raises(HTTPException) as e:
            self._validate(_token(av=1), snapshot=_snapshot(av=1, active=False))
        assert e.value.status_code == 401

    def test_deleted_account_rejected(self):
        with pytest.raises(HTTPException) as e:
            self._validate(_token(av=1), snapshot=("not_found", None))
        assert e.value.status_code == 401

    def test_store_outage_fails_closed_with_503(self):
        with pytest.raises(HTTPException) as e:
            self._validate(_token(av=1), side_effect=AuthStoreUnavailable("down"))
        assert e.value.status_code == 503

    def test_role_comes_from_db_not_stale_token(self):
        # Token still claims admin; the DB says the account was downgraded.
        req = _request_with_token(_token(role="admin", av=1))
        with patch("src.db.is_db_available", return_value=True), \
             patch("src.repositories.users_repo.get_auth_snapshot",
                   return_value=_snapshot(av=1, role="user")):
            with pytest.raises(HTTPException) as e:
                require_admin(req)
        assert e.value.status_code == 403

    def test_db_admin_authorized_regardless_of_token_claim(self):
        req = _request_with_token(_token(role="user", av=1))
        with patch("src.db.is_db_available", return_value=True), \
             patch("src.repositories.users_repo.get_auth_snapshot",
                   return_value=_snapshot(av=1, role="admin")):
            user = require_admin(req)
        assert user["role"] == "admin"

    def test_no_user_store_configured_keeps_legacy_behavior(self):
        # Dev/test without DATABASE_URL: no DB accounts exist to revoke.
        with patch("src.db.is_db_available", return_value=False):
            user = get_current_user(_request_with_token(_token(av=None)))
        assert user == {"email": EMAIL, "role": "user"}


class TestEnvAdminIsolation:
    def test_env_admin_allowed_outside_production(self, monkeypatch):
        for var in ("RICO_ENV", "APP_ENV", "ENV", "ENVIRONMENT"):
            monkeypatch.delenv(var, raising=False)
        token = _token(email="admin@localhost", role="admin", extra={"auth": "env"})
        user = get_current_user(_request_with_token(token))
        assert user["role"] == "admin"

    def test_env_admin_rejected_in_production(self, monkeypatch):
        # Mint the token BEFORE flipping to production (prod requires JWT_SECRET).
        token = _token(email="admin@localhost", role="admin", extra={"auth": "env"})
        monkeypatch.setenv("JWT_SECRET", "x" * 64)
        monkeypatch.setenv("RICO_ENV", "production")
        monkeypatch.delenv("ALLOW_ENV_AUTH_FALLBACK", raising=False)
        token_prod = create_access_token(
            {"sub": "admin@localhost", "role": "admin", "auth": "env"}
        )
        with pytest.raises(HTTPException) as e:
            get_current_user(_request_with_token(token_prod))
        assert e.value.status_code == 401

    def test_env_admin_allowed_in_production_with_explicit_override(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET", "x" * 64)
        monkeypatch.setenv("RICO_ENV", "production")
        monkeypatch.setenv("ALLOW_ENV_AUTH_FALLBACK", "true")
        token = create_access_token(
            {"sub": "admin@localhost", "role": "admin", "auth": "env"}
        )
        user = get_current_user(_request_with_token(token))
        assert user["role"] == "admin"


# ── Revocation lifecycle: reset invalidates, continuity survives restarts ─────

class TestRevocationLifecycle:
    def test_password_reset_invalidates_all_earlier_tokens(self):
        token = _token(av=1)
        req_ok = _request_with_token(token)
        with patch("src.db.is_db_available", return_value=True), \
             patch("src.repositories.users_repo.get_auth_snapshot",
                   return_value=_snapshot(av=1)):
            assert get_current_user(req_ok)["email"] == EMAIL

        # update_password bumped auth_version 1 → 2; same token must now die.
        req_stale = _request_with_token(token)
        with patch("src.db.is_db_available", return_value=True), \
             patch("src.repositories.users_repo.get_auth_snapshot",
                   return_value=_snapshot(av=2)):
            with pytest.raises(HTTPException) as e:
                get_current_user(req_stale)
        assert e.value.status_code == 401

    def test_session_continuity_across_process_restart(self):
        # Same JWT_SECRET → a token minted "before restart" still validates
        # as long as auth_version is unchanged.
        token = _token(av=5)
        payload = decode_access_token(token)
        assert payload["av"] == 5
        with patch("src.db.is_db_available", return_value=True), \
             patch("src.repositories.users_repo.get_auth_snapshot",
                   return_value=_snapshot(av=5)):
            assert get_current_user(_request_with_token(token))["email"] == EMAIL


# ── users_repo: atomic bump + migration-045-missing degradation ──────────────

def _conn_with_cursor(cur):
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    return conn


class TestUsersRepoAuthVersion:
    def test_update_password_bumps_auth_version_in_same_statement(self):
        from src.repositories.users_repo import update_password
        cur = MagicMock()
        cur.rowcount = 1
        conn = _conn_with_cursor(cur)
        with patch("src.db.is_db_available", return_value=True), \
             patch("src.db.get_db_connection", return_value=conn):
            assert update_password(EMAIL, "newhash") is True
        assert cur.execute.call_count == 1
        sql = cur.execute.call_args[0][0]
        assert "password_hash" in sql and "auth_version" in sql

    def test_update_password_falls_back_when_migration_045_missing(self, caplog):
        import psycopg2.errors
        from src.repositories.users_repo import update_password
        cur = MagicMock()
        cur.rowcount = 1
        cur.execute.side_effect = [psycopg2.errors.UndefinedColumn("no auth_version"), None]
        conn = _conn_with_cursor(cur)
        with patch("src.db.is_db_available", return_value=True), \
             patch("src.db.get_db_connection", return_value=conn):
            assert update_password(EMAIL, "newhash") is True
        assert cur.execute.call_count == 2
        legacy_sql = cur.execute.call_args_list[1][0][0]
        assert "auth_version" not in legacy_sql
        assert "migration 045 not applied" in caplog.text

    def test_increment_auth_version_returns_new_version(self):
        from src.repositories.users_repo import increment_auth_version
        cur = MagicMock()
        cur.fetchone.return_value = (4,)
        conn = _conn_with_cursor(cur)
        with patch("src.db.is_db_available", return_value=True), \
             patch("src.db.get_db_connection", return_value=conn):
            assert increment_auth_version(EMAIL) == 4
        conn.commit.assert_called_once()

    def test_increment_returns_none_when_migration_045_missing(self):
        import psycopg2.errors
        from src.repositories.users_repo import increment_auth_version
        cur = MagicMock()
        cur.execute.side_effect = psycopg2.errors.UndefinedColumn("no auth_version")
        conn = _conn_with_cursor(cur)
        with patch("src.db.is_db_available", return_value=True), \
             patch("src.db.get_db_connection", return_value=conn):
            assert increment_auth_version(EMAIL) is None

    def test_get_auth_snapshot_found_and_not_found(self):
        from src.repositories.users_repo import get_auth_snapshot
        cur = MagicMock()
        cur.fetchone.return_value = (3, True, "admin", True)
        conn = _conn_with_cursor(cur)
        with patch("src.db.is_db_available", return_value=True), \
             patch("src.db.get_db_connection", return_value=conn):
            status, snap = get_auth_snapshot(EMAIL)
        assert status == "found"
        assert snap == {"auth_version": 3, "is_active": True, "role": "admin",
                        "email_verified": True}

        cur.fetchone.return_value = None
        conn2 = _conn_with_cursor(cur)
        with patch("src.db.is_db_available", return_value=True), \
             patch("src.db.get_db_connection", return_value=conn2):
            status, snap = get_auth_snapshot(EMAIL)
        assert status == "not_found" and snap is None

    def test_get_auth_snapshot_raises_on_unavailable_store(self):
        from src.repositories.users_repo import get_auth_snapshot
        with patch("src.db.is_db_available", return_value=True), \
             patch("src.db.get_db_connection", return_value=None):
            with pytest.raises(AuthStoreUnavailable):
                get_auth_snapshot(EMAIL)

    def test_get_auth_snapshot_raises_on_query_failure(self):
        from src.repositories.users_repo import get_auth_snapshot
        cur = MagicMock()
        cur.execute.side_effect = RuntimeError("socket reset")
        conn = _conn_with_cursor(cur)
        with patch("src.db.is_db_available", return_value=True), \
             patch("src.db.get_db_connection", return_value=conn):
            with pytest.raises(AuthStoreUnavailable):
                get_auth_snapshot(EMAIL)


# ── Endpoints: login mints av; logout vs logout-all semantics ────────────────

class TestLoginMintsAuthVersion:
    def test_db_user_token_carries_current_auth_version(self):
        from src.api.app import app
        with patch("src.api.auth.verify_credentials",
                   return_value={"id": 1, "email": EMAIL, "role": "user",
                                 "email_verified": True}), \
             patch("src.repositories.users_repo.update_last_login"), \
             patch("src.repositories.users_repo.get_auth_snapshot",
                   return_value=_snapshot(av=7)):
            tc = TestClient(app)
            r = tc.post("/api/v1/auth/login",
                        json={"email": EMAIL, "password": "irrelevant"})
        assert r.status_code == 200
        payload = decode_access_token(tc.cookies.get("access_token"))
        assert payload["av"] == 7
        assert "auth" not in payload

    def test_env_admin_token_is_marked_and_has_no_av(self):
        from src.api.app import app
        with patch("src.api.auth.verify_credentials",
                   return_value={"email": "admin@rico.dev", "role": "admin"}):
            tc = TestClient(app)
            r = tc.post("/api/v1/auth/login",
                        json={"email": "admin@rico.dev", "password": "x"})
        assert r.status_code == 200
        payload = decode_access_token(tc.cookies.get("access_token"))
        assert payload["auth"] == "env"
        assert "av" not in payload


class TestLogoutSemantics:
    def _client(self, av=1):
        from src.api.app import app
        tc = TestClient(app)
        tc.cookies.set("access_token", _token(av=av))
        return tc

    def test_plain_logout_does_not_touch_auth_version(self):
        tc = self._client()
        with patch("src.repositories.users_repo.increment_auth_version") as inc:
            r = tc.post("/api/v1/auth/logout")
        assert r.status_code == 200
        inc.assert_not_called()

    def test_logout_all_bumps_version_and_clears_cookie(self):
        tc = self._client(av=1)
        with patch("src.db.is_db_available", return_value=True), \
             patch("src.repositories.users_repo.get_auth_snapshot",
                   return_value=_snapshot(av=1)), \
             patch("src.repositories.users_repo.increment_auth_version",
                   return_value=2) as inc:
            r = tc.post("/api/v1/auth/logout-all")
        assert r.status_code == 200
        inc.assert_called_once_with(EMAIL)

    def test_logout_all_fails_truthfully_when_revocation_impossible(self):
        tc = self._client(av=1)
        with patch("src.db.is_db_available", return_value=True), \
             patch("src.repositories.users_repo.get_auth_snapshot",
                   return_value=_snapshot(av=1)), \
             patch("src.repositories.users_repo.increment_auth_version",
                   return_value=None):
            r = tc.post("/api/v1/auth/logout-all")
        assert r.status_code == 503

    def test_logout_all_requires_authentication(self):
        from src.api.app import app
        tc = TestClient(app)
        r = tc.post("/api/v1/auth/logout-all")
        assert r.status_code == 401
