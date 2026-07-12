"""Tests for Paddle Billing: signature verification, webhook idempotency,
subscription lifecycle events, billing status, customer portal, and route registration.

Run: pytest tests/test_paddle_billing.py -v
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import unittest
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sig_header(raw_body: bytes, secret: str, ts: Optional[int] = None) -> str:
    """Build a valid Paddle-Signature header using the same bytes-based HMAC
    that the production router uses: ts_bytes + b':' + raw_body."""
    ts_int = ts if ts is not None else int(time.time())
    ts_str = str(ts_int)
    signed = ts_str.encode("utf-8") + b":" + raw_body
    h1 = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"ts={ts_str};h1={h1}"


def _build_sub_payload(
    event_id: str = "evt_001",
    event_type: str = "subscription.created",
    sub_id: str = "sub_001",
    customer_id: str = "ctm_001",
    status: str = "active",
    price_id: str = "pri_pro_monthly",
    user_id: str = "user@example.com",
) -> Dict[str, Any]:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "data": {
            "id": sub_id,
            "customer_id": customer_id,
            "status": status,
            "custom_data": {"user_id": user_id},
            "items": [{"price": {"id": price_id}}],
            "current_billing_period": {
                "starts_at": "2026-07-01T00:00:00Z",
                "ends_at": "2026-08-01T00:00:00Z",
            },
        },
    }


_PRO_ENV = {
    "PADDLE_PRO_MONTHLY_PRICE_ID": "pri_pro_monthly",
    "PADDLE_PRO_YEARLY_PRICE_ID": "pri_pro_yearly",
}


def _clear_price_cache():
    import src.services.paddle_webhook_service as pws
    pws._PRICE_TO_PLAN.clear()


# ---------------------------------------------------------------------------
# Finding #4 — route existence on real FastAPI app
# ---------------------------------------------------------------------------

class TestPaddleRouteRegistration(unittest.TestCase):
    def test_three_routes_on_router(self):
        """paddle_billing_router must define exactly the three required routes."""
        from fastapi.routing import APIRoute
        from src.api.routers.paddle_billing import paddle_billing_router
        paths = {r.path for r in paddle_billing_router.routes if isinstance(r, APIRoute)}
        self.assertIn("/api/v1/billing/paddle/webhook", paths,
                      "POST /api/v1/billing/paddle/webhook missing from paddle_billing_router")
        self.assertIn("/api/v1/billing/status", paths,
                      "GET /api/v1/billing/status missing from paddle_billing_router")
        self.assertIn("/api/v1/billing/customer-portal", paths,
                      "POST /api/v1/billing/customer-portal missing from paddle_billing_router")

    def test_router_included_in_app(self):
        """paddle_billing_router must be included in the FastAPI app (via openapi schema)."""
        from src.api.app import app
        schema = app.openapi()
        app_paths = set(schema.get("paths", {}).keys())
        # These two are in-schema; webhook has include_in_schema=False but still routes correctly
        self.assertIn("/api/v1/billing/status", app_paths,
                      "GET /api/v1/billing/status not in app OpenAPI schema")
        self.assertIn("/api/v1/billing/customer-portal", app_paths,
                      "POST /api/v1/billing/customer-portal not in app OpenAPI schema")


# ---------------------------------------------------------------------------
# Finding #6 — signature verification (fail-closed + timestamp)
# ---------------------------------------------------------------------------

class TestPaddleSignatureVerification(unittest.TestCase):
    def setUp(self):
        os.environ["PADDLE_WEBHOOK_SECRET"] = "test_secret_key"

    def tearDown(self):
        os.environ.pop("PADDLE_WEBHOOK_SECRET", None)

    def _verify(self, raw_body: bytes, sig_header: Optional[str]) -> bool:
        from src.api.routers.paddle_billing import _verify_paddle_signature
        return _verify_paddle_signature(raw_body, sig_header)

    def test_valid_signature_accepted(self):
        body = b'{"event_id":"e1","event_type":"subscription.created"}'
        header = _make_sig_header(body, "test_secret_key")
        self.assertTrue(self._verify(body, header))

    def test_wrong_secret_rejected(self):
        body = b'{"event_id":"e2","event_type":"subscription.created"}'
        header = _make_sig_header(body, "wrong_secret")
        self.assertFalse(self._verify(body, header))

    def test_missing_header_rejected(self):
        body = b'{"event_id":"e3"}'
        self.assertFalse(self._verify(body, None))

    def test_malformed_header_rejected(self):
        body = b'{"event_id":"e4"}'
        self.assertFalse(self._verify(body, "invalid-header-format"))

    def test_tampered_body_rejected(self):
        original = b'{"event_id":"e5","event_type":"subscription.created"}'
        tampered = b'{"event_id":"e5","event_type":"subscription.canceled"}'
        header = _make_sig_header(original, "test_secret_key")
        self.assertFalse(self._verify(tampered, header))

    def test_no_secret_configured_fails_closed(self):
        """Missing PADDLE_WEBHOOK_SECRET must FAIL CLOSED, not skip (finding #6)."""
        os.environ.pop("PADDLE_WEBHOOK_SECRET", None)
        body = b'{"event_id":"e6"}'
        # No secret → reject the request (fail closed)
        self.assertFalse(self._verify(body, None))

    def test_no_secret_test_mode_skips(self):
        """_test_mode=True allows bypassing secret check in unit tests only."""
        os.environ.pop("PADDLE_WEBHOOK_SECRET", None)
        from src.api.routers.paddle_billing import _verify_paddle_signature
        body = b'{"event_id":"e7"}'
        self.assertTrue(_verify_paddle_signature(body, None, _test_mode=True))

    def test_stale_timestamp_rejected(self):
        """Timestamps older than 5 minutes must be rejected (finding #6)."""
        body = b'{"event_id":"e8"}'
        old_ts = int(time.time()) - 400  # 400s ago > 300s tolerance
        header = _make_sig_header(body, "test_secret_key", ts=old_ts)
        self.assertFalse(self._verify(body, header))

    def test_fresh_timestamp_accepted(self):
        body = b'{"event_id":"e9"}'
        fresh_ts = int(time.time()) - 10  # 10s ago — well within tolerance
        header = _make_sig_header(body, "test_secret_key", ts=fresh_ts)
        self.assertTrue(self._verify(body, header))


# ---------------------------------------------------------------------------
# Webhook service: idempotency (finding #7)
# ---------------------------------------------------------------------------

class TestPaddleWebhookIdempotency(unittest.TestCase):
    def test_duplicate_event_returns_skipped(self):
        from src.services.paddle_webhook_service import process_paddle_webhook

        with patch("src.repositories.paddle_repo.paddle_event_already_processed", return_value=True):
            result = process_paddle_webhook(
                event_id="evt_dup",
                event_type="subscription.created",
                payload=_build_sub_payload(),
                db_module=MagicMock(),
            )
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "duplicate")

    def test_new_event_not_skipped(self):
        from src.services.paddle_webhook_service import process_paddle_webhook
        _clear_price_cache()

        with patch("src.repositories.paddle_repo.paddle_event_already_processed", return_value=False), \
             patch("src.repositories.paddle_repo.record_paddle_webhook_event", return_value=True), \
             patch("src.repositories.paddle_repo.mark_paddle_event_processed"), \
             patch("src.repositories.paddle_repo.upsert_paddle_customer"), \
             patch("src.repositories.paddle_repo.upsert_paddle_subscription", return_value={}), \
             patch("src.repositories.paddle_repo.get_paddle_subscription_by_paddle_id", return_value=None), \
             patch("src.repositories.paddle_repo.get_paddle_customer_by_paddle_id", return_value=None), \
             patch.dict(os.environ, _PRO_ENV):
            result = process_paddle_webhook(
                event_id="evt_new",
                event_type="subscription.created",
                payload=_build_sub_payload(),
                db_module=MagicMock(),
            )
        self.assertNotEqual(result["status"], "skipped")


# ---------------------------------------------------------------------------
# Webhook service: subscription lifecycle (findings #8, #9, #10)
# ---------------------------------------------------------------------------

class TestPaddleSubscriptionLifecycle(unittest.TestCase):
    def _run(self, event_type: str, payload: Dict[str, Any],
             extra_env: Optional[Dict] = None) -> Dict[str, Any]:
        from src.services.paddle_webhook_service import process_paddle_webhook
        _clear_price_cache()

        env = dict(_PRO_ENV)
        if extra_env:
            env.update(extra_env)

        with patch("src.repositories.paddle_repo.paddle_event_already_processed", return_value=False), \
             patch("src.repositories.paddle_repo.record_paddle_webhook_event", return_value=True), \
             patch("src.repositories.paddle_repo.mark_paddle_event_processed"), \
             patch("src.repositories.paddle_repo.upsert_paddle_customer"), \
             patch("src.repositories.paddle_repo.upsert_paddle_subscription", return_value={}), \
             patch("src.repositories.paddle_repo.get_paddle_subscription_by_paddle_id", return_value=None), \
             patch("src.repositories.paddle_repo.get_paddle_customer_by_paddle_id", return_value=None), \
             patch.dict(os.environ, env, clear=False):
            return process_paddle_webhook(
                event_id=payload["event_id"],
                event_type=event_type,
                payload=payload,
                db_module=MagicMock(),
            )

    def test_subscription_created_processed(self):
        payload = _build_sub_payload(event_type="subscription.created")
        result = self._run("subscription.created", payload)
        self.assertEqual(result["status"], "processed")
        self.assertEqual(result.get("plan"), "pro")

    def test_subscription_updated_processed(self):
        payload = _build_sub_payload(event_id="evt_u1", event_type="subscription.updated")
        result = self._run("subscription.updated", payload)
        self.assertEqual(result["status"], "processed")

    def test_subscription_canceled_processed(self):
        payload = _build_sub_payload(event_id="evt_c1", event_type="subscription.canceled")
        result = self._run("subscription.canceled", payload)
        self.assertEqual(result["status"], "processed")

    def test_subscription_activated_processed(self):
        """subscription.activated must be handled (finding #10)."""
        payload = _build_sub_payload(event_id="evt_act", event_type="subscription.activated",
                                     status="active")
        result = self._run("subscription.activated", payload)
        self.assertEqual(result["status"], "processed")

    def test_subscription_past_due_processed(self):
        """subscription.past_due must be handled (finding #10)."""
        payload = _build_sub_payload(event_id="evt_pd", event_type="subscription.past_due",
                                     status="past_due")
        result = self._run("subscription.past_due", payload)
        self.assertEqual(result["status"], "processed")

    def test_subscription_paused_processed(self):
        """subscription.paused must be handled (finding #10)."""
        payload = _build_sub_payload(event_id="evt_paus", event_type="subscription.paused",
                                     status="paused")
        result = self._run("subscription.paused", payload)
        self.assertEqual(result["status"], "processed")

    def test_subscription_resumed_processed(self):
        """subscription.resumed must be handled (finding #10)."""
        payload = _build_sub_payload(event_id="evt_res", event_type="subscription.resumed",
                                     status="active")
        result = self._run("subscription.resumed", payload)
        self.assertEqual(result["status"], "processed")

    def test_transaction_payment_failed_processed(self):
        """transaction.payment_failed must be handled (finding #10)."""
        payload = {
            "event_id": "evt_pf1", "event_type": "transaction.payment_failed",
            "data": {"customer_id": "ctm_001"},
        }
        result = self._run("transaction.payment_failed", payload)
        self.assertEqual(result["status"], "processed")

    def test_unknown_price_id_no_entitlement(self):
        """Unknown/unconfigured price IDs must NEVER grant paid entitlement (finding #8)."""
        payload = _build_sub_payload(
            event_id="evt_unk_price",
            event_type="subscription.created",
            price_id="pri_unknown_xyz",
        )
        _clear_price_cache()
        result = self._run("subscription.created", payload,
                           extra_env={"PADDLE_PRO_MONTHLY_PRICE_ID": "pri_pro_monthly",
                                      "PADDLE_PRO_YEARLY_PRICE_ID": "pri_pro_yearly"})
        # Must NOT grant 'pro' or any paid plan — result is processed but with unmapped warning
        if result["status"] == "processed":
            self.assertNotEqual(result.get("plan"), "pro",
                                "Unknown price ID must not grant pro entitlement")
            self.assertIn("unmapped", result.get("warning", ""),
                          "Unknown price ID must produce unmapped_price warning")

    def test_yearly_billing_cycle(self):
        payload = _build_sub_payload(
            event_id="evt_yearly",
            event_type="subscription.created",
            price_id="pri_pro_yearly",
        )
        _clear_price_cache()
        captured = {}
        with patch("src.repositories.paddle_repo.paddle_event_already_processed", return_value=False), \
             patch("src.repositories.paddle_repo.record_paddle_webhook_event", return_value=True), \
             patch("src.repositories.paddle_repo.mark_paddle_event_processed"), \
             patch("src.repositories.paddle_repo.upsert_paddle_customer"), \
             patch("src.repositories.paddle_repo.get_paddle_subscription_by_paddle_id", return_value=None), \
             patch("src.repositories.paddle_repo.get_paddle_customer_by_paddle_id", return_value=None), \
             patch("src.repositories.paddle_repo.upsert_paddle_subscription",
                   side_effect=lambda db, **kw: captured.update(kw) or {}), \
             patch.dict(os.environ, _PRO_ENV, clear=False):
            from src.services.paddle_webhook_service import process_paddle_webhook
            process_paddle_webhook(
                event_id="evt_yearly",
                event_type="subscription.created",
                payload=payload,
                db_module=MagicMock(),
            )
        self.assertEqual(captured.get("billing_cycle"), "yearly")

    def test_unhandled_event_type_skipped_gracefully(self):
        payload = {"event_id": "evt_unk", "event_type": "customer.created", "data": {}}
        result = self._run("customer.created", payload)
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "unhandled_event_type")

    def test_no_user_id_returns_warning(self):
        """Finding #9: when DB lookup finds no user and custom_data is empty, warn."""
        payload = {
            "event_id": "evt_nouid",
            "event_type": "subscription.created",
            "data": {
                "id": "sub_nouid",
                "customer_id": "ctm_nouid",
                "status": "active",
                "custom_data": {},
                "items": [{"price": {"id": "pri_pro_monthly"}}],
                "current_billing_period": {"starts_at": None, "ends_at": None},
            },
        }
        _clear_price_cache()
        with patch("src.repositories.paddle_repo.paddle_event_already_processed", return_value=False), \
             patch("src.repositories.paddle_repo.record_paddle_webhook_event", return_value=True), \
             patch("src.repositories.paddle_repo.mark_paddle_event_processed"), \
             patch("src.repositories.paddle_repo.get_paddle_subscription_by_paddle_id", return_value=None), \
             patch("src.repositories.paddle_repo.get_paddle_customer_by_paddle_id", return_value=None), \
             patch.dict(os.environ, _PRO_ENV, clear=False):
            from src.services.paddle_webhook_service import process_paddle_webhook
            result = process_paddle_webhook(
                event_id="evt_nouid",
                event_type="subscription.created",
                payload=payload,
                db_module=MagicMock(),
            )
        self.assertIn("warning", result)

    def test_db_identity_takes_priority_over_custom_data(self):
        """Finding #9: DB lookup by customer_id must override custom_data.user_id."""
        payload = _build_sub_payload(
            event_id="evt_id9",
            event_type="subscription.created",
            user_id="untrusted_from_browser",
        )
        _clear_price_cache()
        captured_upsert = {}
        db_user = "db_resolved_user_id"

        with patch("src.repositories.paddle_repo.paddle_event_already_processed", return_value=False), \
             patch("src.repositories.paddle_repo.record_paddle_webhook_event", return_value=True), \
             patch("src.repositories.paddle_repo.mark_paddle_event_processed"), \
             patch("src.repositories.paddle_repo.upsert_paddle_customer"), \
             patch("src.repositories.paddle_repo.get_paddle_subscription_by_paddle_id", return_value=None), \
             patch("src.repositories.paddle_repo.get_paddle_customer_by_paddle_id",
                   return_value={"user_id": db_user}), \
             patch("src.repositories.paddle_repo.upsert_paddle_subscription",
                   side_effect=lambda db, **kw: captured_upsert.update(kw) or {}), \
             patch.dict(os.environ, _PRO_ENV, clear=False):
            from src.services.paddle_webhook_service import process_paddle_webhook
            result = process_paddle_webhook(
                event_id="evt_id9",
                event_type="subscription.created",
                payload=payload,
                db_module=MagicMock(),
            )
        self.assertEqual(result["status"], "processed")
        self.assertEqual(captured_upsert.get("user_id"), db_user,
                         "DB-resolved user_id must be used, not untrusted custom_data")


# ---------------------------------------------------------------------------
# billing_mode helpers
# ---------------------------------------------------------------------------

class TestBillingMode(unittest.TestCase):
    def test_paddle_mode(self):
        with patch.dict(os.environ, {"BILLING_MODE": "paddle"}):
            from importlib import reload
            import src.billing_mode as bm
            reload(bm)
            self.assertTrue(bm.is_paddle_billing_mode())
            self.assertFalse(bm.is_stripe_billing_mode())
            self.assertFalse(bm.is_manual_billing_mode())

    def test_manual_mode_default(self):
        env = {k: v for k, v in os.environ.items() if k != "BILLING_MODE"}
        with patch.dict(os.environ, env, clear=True):
            from importlib import reload
            import src.billing_mode as bm
            reload(bm)
            self.assertFalse(bm.is_paddle_billing_mode())
            self.assertTrue(bm.is_manual_billing_mode())

    def test_api_key_not_exposed(self):
        """PADDLE_API_KEY must never appear in NEXT_PUBLIC_* or client code paths."""
        import src.api.routers.paddle_billing as pb_router
        import inspect
        source = inspect.getsource(pb_router)
        self.assertNotIn("NEXT_PUBLIC_PADDLE", source)
        self.assertNotIn("NEXT_PUBLIC_API_KEY", source)

    def test_premium_env_vars_not_in_server_scope(self):
        """Finding #11: Premium price env vars must not be referenced server-side."""
        import src.services.paddle_webhook_service as pws
        import inspect
        source = inspect.getsource(pws)
        self.assertNotIn("PADDLE_PREMIUM_MONTHLY_PRICE_ID", source)
        self.assertNotIn("PADDLE_PREMIUM_YEARLY_PRICE_ID", source)


if __name__ == "__main__":
    unittest.main()
