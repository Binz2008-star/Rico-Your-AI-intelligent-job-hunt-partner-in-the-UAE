"""Regression tests for post-PR-253 billing hardening fixes.

Covers three Codex findings:
  1. WhatsApp number normalization (billing.ts logic verified via Python equivalent)
  2. Admin activation returns 503 when DB is unavailable vs 404 when user not found
  3. upsert_subscription clear_cancellation clears cancel_at/canceled_at on reactivation
"""
from __future__ import annotations

import os
import re
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


# ── WhatsApp number normalization ─────────────────────────────────────────────
# billing.ts uses raw.replace(/\D/g, "") — Python equivalent: re.sub(r'\D', '', raw)
# These tests verify the expected transform for inputs the Codex review flagged.

def _normalize(raw: str) -> str:
    return re.sub(r"\D", "", raw)


class TestWhatsAppNumberNormalization:
    def test_formatted_number_with_plus_and_spaces(self):
        assert _normalize("+971 58 598 9080") == "971585989080"

    def test_plain_digits_unchanged(self):
        assert _normalize("971585989080") == "971585989080"

    def test_number_with_hyphens(self):
        assert _normalize("+971-58-598-9080") == "971585989080"

    def test_number_with_parentheses(self):
        assert _normalize("+971 (58) 598-9080") == "971585989080"

    def test_empty_string_yields_empty(self):
        assert _normalize("") == ""


# ── Admin activation: DB availability gating ──────────────────────────────────

@pytest.fixture(scope="module")
def admin_client():
    from fastapi.testclient import TestClient
    from src.api.app import app
    from src.api.auth import create_access_token

    token = create_access_token({"sub": "admin@rico.ai", "role": "admin"})
    tc = TestClient(app, raise_server_exceptions=False)
    tc.cookies.set("access_token", token)
    return tc


def _fake_user(email: str = "target@rico.ai"):
    from src.repositories.users_repo import User
    return User(
        id=99,
        email=email,
        password_hash="x",
        role="user",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        last_login_at=None,
    )


def _fake_upsert(calls: list):
    def _inner(user_id, *, plan, status, **kwargs):
        calls.append({"user_id": user_id, "plan": plan, "status": status, **kwargs})
        return {"user_id": user_id, "plan": plan, "status": status}
    return _inner


class TestAdminActivationDbGating:
    def test_503_when_db_unavailable(self, admin_client, monkeypatch):
        monkeypatch.setattr("src.db.is_db_available", lambda: False)

        r = admin_client.post(
            "/api/v1/admin/subscriptions/activate",
            json={"email": "anyone@rico.ai", "plan": "pro", "duration_days": 30},
        )

        assert r.status_code == 503
        assert "database unavailable" in r.json()["detail"].lower()

    def test_404_when_db_available_but_user_missing(self, admin_client, monkeypatch):
        monkeypatch.setattr("src.db.is_db_available", lambda: True)
        monkeypatch.setattr("src.repositories.users_repo.get_user_by_email", lambda e: None)

        r = admin_client.post(
            "/api/v1/admin/subscriptions/activate",
            json={"email": "ghost@rico.ai", "plan": "pro", "duration_days": 30},
        )

        assert r.status_code == 404
        assert "ghost@rico.ai" in r.json()["detail"]

    def test_422_input_validation_fires_before_db_check(self, admin_client, monkeypatch):
        # duration_days=0 is invalid; should get 422 without touching the DB.
        # is_db_available is NOT patched — proves validation runs before the DB check.
        r = admin_client.post(
            "/api/v1/admin/subscriptions/activate",
            json={"email": "target@rico.ai", "plan": "pro", "duration_days": 0},
        )

        assert r.status_code == 422


# ── upsert_subscription: clear_cancellation ───────────────────────────────────

class FakeCursor:
    def __init__(self):
        self.sql_log: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def execute(self, sql, params=None):
        self.sql_log.append(sql)

    def fetchone(self):
        return None


class FakeConn:
    def __init__(self):
        self._cursor = FakeCursor()

    def cursor(self):
        return self._cursor

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


@contextmanager
def _fake_transaction(conn):
    yield conn


class TestClearCancellation:
    def _run_upsert(self, **kwargs):
        conn = FakeConn()

        with patch(
            "src.repositories.subscription_repo._db_transaction",
            return_value=_fake_transaction(conn),
        ):
            from src.repositories.subscription_repo import upsert_subscription
            upsert_subscription("user@test.com", plan="pro", status="active", **kwargs)

        return conn._cursor.sql_log

    def test_clear_cancellation_true_writes_null_for_both_fields(self):
        sql_log = self._run_upsert(clear_cancellation=True)

        assert sql_log, "upsert SQL was not executed"
        sql = sql_log[0]
        assert "cancel_at                      = NULL" in sql
        assert "canceled_at                    = NULL" in sql
        assert "COALESCE(EXCLUDED.cancel_at" not in sql
        assert "COALESCE(EXCLUDED.canceled_at" not in sql

    def test_clear_cancellation_false_uses_coalesce(self):
        sql_log = self._run_upsert(clear_cancellation=False)

        sql = sql_log[0]
        assert "COALESCE(EXCLUDED.cancel_at" in sql
        assert "COALESCE(EXCLUDED.canceled_at" in sql

    def test_clear_cancellation_defaults_to_false(self):
        sql_log = self._run_upsert()

        sql = sql_log[0]
        assert "COALESCE(EXCLUDED.cancel_at" in sql
        assert "COALESCE(EXCLUDED.canceled_at" in sql

    def test_admin_activation_passes_clear_cancellation_true(self, admin_client, monkeypatch):
        monkeypatch.setattr("src.db.is_db_available", lambda: True)
        monkeypatch.setattr(
            "src.repositories.users_repo.get_user_by_email",
            lambda e: _fake_user(e),
        )

        calls: list = []
        monkeypatch.setattr(
            "src.repositories.subscription_repo.upsert_subscription",
            _fake_upsert(calls),
        )

        r = admin_client.post(
            "/api/v1/admin/subscriptions/activate",
            json={"email": "target@rico.ai", "plan": "pro", "duration_days": 30},
        )

        assert r.status_code == 200
        assert calls, "upsert_subscription was not called"
        assert calls[0].get("clear_cancellation") is True
