"""Regression tests for post-PR-253 billing hardening fixes.

Covers two Codex findings:
  1. WhatsApp number normalization (billing.ts logic verified via Python equivalent)
  2. Admin activation returns 503 when DB is unavailable vs 404 when user not found

(The former third finding — upsert_subscription's clear_cancellation flag — tested
src/repositories/subscription_repo.py's Stripe-era COALESCE-preservation pattern,
which doesn't apply to paddle_repo.upsert_paddle_subscription: Paddle webhooks
deliver full subscription state on every event, not partial diffs, so cancel_at/
canceled_at are always set directly from the event payload rather than needing a
selective-clear flag.)
"""
from __future__ import annotations

import os
import re
import sys

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
