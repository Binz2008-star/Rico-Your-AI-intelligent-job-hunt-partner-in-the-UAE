"""WhatsApp-assisted subscription channel (DEC-20260719-003).

Pins the security contract:
  - authenticated-only request creation; identity from JWT, never the body
  - server-resolved plan/price/currency; client fields ignored
  - fail-closed configuration (flag + E.164 number both required)
  - idempotent repeated clicks (single pending request per user)
  - creating a request NEVER touches entitlement
  - no JWT/secret/PII in the response
  - admin manual activation marks a matching request approved (best-effort)
  - Paddle endpoints remain untouched by this router

Run: pytest tests/test_whatsapp_subscription.py -v
"""
from __future__ import annotations

import os
import unittest
from typing import Any, Dict
from unittest.mock import MagicMock, patch
from urllib.parse import unquote

from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

from src.api.deps import get_current_user_id
from src.api.routers.billing_whatsapp import router as whatsapp_router

_TEST_USER = "user@rico.ai"

_ACTIVE_ENV = {
    "WHATSAPP_SUBSCRIPTIONS_ENABLED": "true",
    "WHATSAPP_SUBSCRIPTION_NUMBER": "971585989080",
}

_FAKE_ROW: Dict[str, Any] = {
    "reference": "RICO-ABCDEF1234",
    "user_id": _TEST_USER,
    "plan": "pro",
    "price_usd": 21.50,
    "currency": "USD",
    "status": "pending",
    "requested_language": "en",
    "created_at": None,
}


def _make_client(authenticated: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(whatsapp_router)
    if authenticated:
        app.dependency_overrides[get_current_user_id] = lambda: _TEST_USER
    return TestClient(app, raise_server_exceptions=False)


class TestWhatsAppConfigEndpoint(unittest.TestCase):
    """GET /api/v1/billing/whatsapp/config — public boolean, fail-closed."""

    def _config(self, env: Dict[str, str]) -> Dict[str, Any]:
        client = _make_client(authenticated=False)
        with patch.dict(os.environ, env, clear=True):
            r = client.get("/api/v1/billing/whatsapp/config")
        self.assertEqual(r.status_code, 200)
        return r.json()

    def test_default_is_inactive(self):
        self.assertFalse(self._config({})["whatsapp_active"])

    def test_enabled_without_number_is_inactive(self):
        self.assertFalse(
            self._config({"WHATSAPP_SUBSCRIPTIONS_ENABLED": "true"})["whatsapp_active"]
        )

    def test_number_without_enable_flag_is_inactive(self):
        self.assertFalse(
            self._config({"WHATSAPP_SUBSCRIPTION_NUMBER": "971585989080"})["whatsapp_active"]
        )

    def test_invalid_number_is_inactive(self):
        for bad in ("abc", "0123456789", "+0", "12345", "97158598908012345678"):
            env = {"WHATSAPP_SUBSCRIPTIONS_ENABLED": "true", "WHATSAPP_SUBSCRIPTION_NUMBER": bad}
            self.assertFalse(self._config(env)["whatsapp_active"], f"{bad!r} must fail closed")

    def test_valid_config_is_active(self):
        self.assertTrue(self._config(dict(_ACTIVE_ENV))["whatsapp_active"])

    def test_plus_prefixed_e164_accepted(self):
        env = {"WHATSAPP_SUBSCRIPTIONS_ENABLED": "true", "WHATSAPP_SUBSCRIPTION_NUMBER": "+971585989080"}
        self.assertTrue(self._config(env)["whatsapp_active"])

    def test_config_exposes_no_number_or_secrets(self):
        client = _make_client(authenticated=False)
        with patch.dict(os.environ, dict(_ACTIVE_ENV), clear=True):
            r = client.get("/api/v1/billing/whatsapp/config")
        self.assertEqual(set(r.json().keys()), {"whatsapp_active"})
        self.assertNotIn("971585989080", r.text)


class TestWhatsAppSubscriptionRequest(unittest.TestCase):
    """POST /api/v1/billing/whatsapp-subscription-request."""

    def test_unauthenticated_rejected(self):
        client = _make_client(authenticated=False)
        with patch.dict(os.environ, dict(_ACTIVE_ENV), clear=True):
            r = client.post("/api/v1/billing/whatsapp-subscription-request", json={})
        self.assertEqual(r.status_code, 401)

    def test_fails_closed_when_disabled(self):
        client = _make_client()
        for env in ({}, {"WHATSAPP_SUBSCRIPTIONS_ENABLED": "true"},
                    {"WHATSAPP_SUBSCRIPTION_NUMBER": "971585989080"}):
            with patch.dict(os.environ, env, clear=True):
                r = client.post("/api/v1/billing/whatsapp-subscription-request", json={})
            self.assertEqual(r.status_code, 503, f"env {env} must fail closed")

    def test_happy_path_returns_reference_and_sanitized_url(self):
        client = _make_client()
        with patch.dict(os.environ, dict(_ACTIVE_ENV), clear=True), \
             patch("src.repositories.whatsapp_requests_repo.get_or_create_pending_request",
                   return_value=dict(_FAKE_ROW)) as create:
            r = client.post("/api/v1/billing/whatsapp-subscription-request", json={"language": "en"})

        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["reference"], "RICO-ABCDEF1234")
        self.assertEqual(data["status"], "pending")
        self.assertTrue(data["whatsapp_url"].startswith("https://wa.me/971585989080?text="))

        message = unquote(data["whatsapp_url"].split("text=", 1)[1])
        self.assertIn("RICO-ABCDEF1234", message)
        self.assertIn("Rico Monthly", message)
        self.assertIn("21.50 USD", message)
        self.assertIn("payment instructions", message)

        # Identity comes from the JWT dependency, not the body.
        self.assertEqual(create.call_args.args[0], _TEST_USER)

    def test_arabic_language_selects_arabic_template(self):
        client = _make_client()
        with patch.dict(os.environ, dict(_ACTIVE_ENV), clear=True), \
             patch("src.repositories.whatsapp_requests_repo.get_or_create_pending_request",
                   return_value=dict(_FAKE_ROW)):
            r = client.post("/api/v1/billing/whatsapp-subscription-request", json={"language": "ar"})
        message = unquote(r.json()["whatsapp_url"].split("text=", 1)[1])
        self.assertIn("مرجع الطلب", message)
        self.assertIn("RICO-ABCDEF1234", message)

    def test_client_cannot_alter_plan_price_currency_or_user(self):
        """Forged body fields must be ignored — server snapshot wins."""
        client = _make_client()
        forged = {
            "language": "en",
            "plan": "premium",
            "price": "0.01",
            "currency": "AED",
            "user_id": "attacker@evil.com",
            "reference": "RICO-FORGED",
        }
        with patch.dict(os.environ, dict(_ACTIVE_ENV), clear=True), \
             patch("src.repositories.whatsapp_requests_repo.get_or_create_pending_request",
                   return_value=dict(_FAKE_ROW)) as create:
            r = client.post("/api/v1/billing/whatsapp-subscription-request", json=forged)

        self.assertEqual(r.status_code, 200)
        create.assert_called_once()
        self.assertEqual(create.call_args.args[0], _TEST_USER)  # not attacker
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["plan"], "pro")
        self.assertEqual(kwargs["price_usd"], 21.50)
        self.assertEqual(kwargs["currency"], "USD")
        self.assertNotIn("RICO-FORGED", r.text)
        self.assertNotIn("attacker@evil.com", r.text)

    def test_repeated_click_reuses_pending_request(self):
        """Endpoint idempotency is delegated to get_or_create — both calls
        must return the SAME reference (the repo returns the pending row)."""
        client = _make_client()
        with patch.dict(os.environ, dict(_ACTIVE_ENV), clear=True), \
             patch("src.repositories.whatsapp_requests_repo.get_or_create_pending_request",
                   return_value=dict(_FAKE_ROW)):
            r1 = client.post("/api/v1/billing/whatsapp-subscription-request", json={})
            r2 = client.post("/api/v1/billing/whatsapp-subscription-request", json={})
        self.assertEqual(r1.json()["reference"], r2.json()["reference"])

    def test_repo_failure_fails_closed(self):
        client = _make_client()
        with patch.dict(os.environ, dict(_ACTIVE_ENV), clear=True), \
             patch("src.repositories.whatsapp_requests_repo.get_or_create_pending_request",
                   return_value=None):
            r = client.post("/api/v1/billing/whatsapp-subscription-request", json={})
        self.assertEqual(r.status_code, 503)

    def test_request_creation_never_touches_entitlement(self):
        """The assisted request path must not call the entitlement writer."""
        client = _make_client()
        with patch.dict(os.environ, dict(_ACTIVE_ENV), clear=True), \
             patch("src.repositories.whatsapp_requests_repo.get_or_create_pending_request",
                   return_value=dict(_FAKE_ROW)), \
             patch("src.repositories.paddle_repo.upsert_paddle_subscription") as upsert:
            r = client.post("/api/v1/billing/whatsapp-subscription-request", json={})
        self.assertEqual(r.status_code, 200)
        upsert.assert_not_called()

    def test_no_jwt_or_pii_in_response(self):
        client = _make_client()
        with patch.dict(os.environ, dict(_ACTIVE_ENV), clear=True), \
             patch("src.repositories.whatsapp_requests_repo.get_or_create_pending_request",
                   return_value=dict(_FAKE_ROW)):
            r = client.post(
                "/api/v1/billing/whatsapp-subscription-request",
                json={},
                headers={"Cookie": "access_token=eyJfaketoken.signature.parts"},
            )
        body = r.text
        self.assertNotIn("eyJfaketoken", body)
        self.assertNotIn(_TEST_USER, body)  # user email never echoed
        self.assertNotIn('"id"', body)  # no raw DB ids
        data = r.json()
        self.assertEqual(
            set(data.keys()),
            {"reference", "status", "plan", "price", "currency", "whatsapp_url", "note_en", "note_ar"},
        )


class TestRepoIdempotency(unittest.TestCase):
    """get_or_create_pending_request reuses an existing pending row."""

    def _fake_conn(self, select_row):
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        cur.fetchone.return_value = select_row
        return conn, cur

    def test_existing_pending_row_short_circuits_insert(self):
        from src.repositories import whatsapp_requests_repo as repo

        row = ("RICO-EXISTING1", _TEST_USER, "pro", 21.50, "USD", "pending", "en", None)
        conn, cur = self._fake_conn(row)
        with patch("src.repositories.whatsapp_requests_repo.get_db_connection", return_value=conn):
            out = repo.get_or_create_pending_request(
                _TEST_USER, plan="pro", price_usd=21.50, currency="USD", language="en"
            )
        self.assertEqual(out["reference"], "RICO-EXISTING1")
        executed_sql = " ".join(str(c.args[0]) for c in cur.execute.call_args_list)
        self.assertNotIn("INSERT", executed_sql)

    def test_db_unavailable_returns_none(self):
        from src.repositories import whatsapp_requests_repo as repo
        with patch("src.repositories.whatsapp_requests_repo.get_db_connection", return_value=None):
            self.assertIsNone(
                repo.get_or_create_pending_request(
                    _TEST_USER, plan="pro", price_usd=21.50, currency="USD"
                )
            )


class TestAdminApprovalLinkage(unittest.TestCase):
    """Admin manual activation marks a matching RICO- reference approved."""

    def _admin_client(self):
        os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)
        from fastapi.testclient import TestClient as TC
        from src.api.app import app
        from src.api.auth import create_access_token
        token = create_access_token({"sub": "admin@rico.ai", "role": "admin"})
        tc = TC(app, raise_server_exceptions=False)
        tc.cookies.set("access_token", token)
        return tc

    def _mock_user(self, monkey_target="src.repositories.users_repo.get_user_by_email"):
        from datetime import datetime, timezone
        from src.repositories.users_repo import User
        return User(
            id=7, email="target@rico.ai", password_hash="x", role="user",
            is_active=True, created_at=datetime.now(timezone.utc), last_login_at=None,
        )

    def test_activation_with_rico_reference_marks_request_approved(self):
        client = self._admin_client()
        fake_user = self._mock_user()
        with patch("src.db.is_db_available", return_value=True), \
             patch("src.repositories.users_repo.get_user_by_email",
                   return_value=fake_user), \
             patch("src.repositories.paddle_repo.upsert_paddle_subscription",
                   return_value={"user_id": "target@rico.ai"}), \
             patch("src.repositories.whatsapp_requests_repo.mark_request_status",
                   return_value=True) as mark:
            r = client.post(
                "/api/v1/admin/subscriptions/activate",
                json={"email": "target@rico.ai", "plan": "pro", "duration_days": 30,
                      "payment_reference": "rico-abcdef1234"},
            )
        self.assertEqual(r.status_code, 200)
        mark.assert_called_once()
        self.assertEqual(mark.call_args.args[0], "RICO-ABCDEF1234")
        self.assertEqual(mark.call_args.args[1], "approved")

    def test_marking_failure_never_blocks_activation(self):
        client = self._admin_client()
        fake_user = self._mock_user()
        with patch("src.db.is_db_available", return_value=True), \
             patch("src.repositories.users_repo.get_user_by_email",
                   return_value=fake_user), \
             patch("src.repositories.paddle_repo.upsert_paddle_subscription",
                   return_value={"user_id": "target@rico.ai"}), \
             patch("src.repositories.whatsapp_requests_repo.mark_request_status",
                   side_effect=RuntimeError("db down")):
            r = client.post(
                "/api/v1/admin/subscriptions/activate",
                json={"email": "target@rico.ai", "plan": "pro", "duration_days": 30,
                      "payment_reference": "RICO-ABCDEF1234"},
            )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["success"])

    def test_non_rico_reference_does_not_touch_requests(self):
        client = self._admin_client()
        fake_user = self._mock_user()
        with patch("src.db.is_db_available", return_value=True), \
             patch("src.repositories.users_repo.get_user_by_email",
                   return_value=fake_user), \
             patch("src.repositories.paddle_repo.upsert_paddle_subscription",
                   return_value={"user_id": "target@rico.ai"}), \
             patch("src.repositories.whatsapp_requests_repo.mark_request_status") as mark:
            r = client.post(
                "/api/v1/admin/subscriptions/activate",
                json={"email": "target@rico.ai", "plan": "pro", "duration_days": 30,
                      "payment_reference": "bank-transfer-991"},
            )
        self.assertEqual(r.status_code, 200)
        mark.assert_not_called()


class TestPaddleRouterUntouched(unittest.TestCase):
    """The assisted channel must not alter the Paddle billing surface."""

    def test_whatsapp_router_defines_only_its_two_routes(self):
        from fastapi.routing import APIRoute
        paths = {r.path for r in whatsapp_router.routes if isinstance(r, APIRoute)}
        self.assertEqual(paths, {
            "/api/v1/billing/whatsapp/config",
            "/api/v1/billing/whatsapp-subscription-request",
        })

    def test_app_still_exposes_paddle_routes(self):
        from src.api.app import app
        schema = app.openapi()
        app_paths = set(schema.get("paths", {}).keys())
        for p in ("/api/v1/billing/config", "/api/v1/billing/status",
                  "/api/v1/billing/customer-portal",
                  "/api/v1/billing/paddle/checkout-session",
                  "/api/v1/billing/whatsapp/config",
                  "/api/v1/billing/whatsapp-subscription-request"):
            self.assertIn(p, app_paths)


if __name__ == "__main__":
    unittest.main()
