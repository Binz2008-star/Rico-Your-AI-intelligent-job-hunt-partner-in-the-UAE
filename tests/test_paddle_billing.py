"""Tests for Paddle Billing: signature verification, webhook idempotency,
subscription lifecycle events, billing status, and customer portal.

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

def _make_sig_header(raw_body: bytes, secret: str, ts: Optional[str] = None) -> str:
    ts = ts or str(int(time.time()))
    signed = f"{ts}:{raw_body.decode('utf-8')}"
    h1 = hmac.new(secret.encode(), signed.encode(), hashlib.sha256).hexdigest()
    return f"ts={ts};h1={h1}"


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


# ---------------------------------------------------------------------------
# Signature verification tests
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

    def test_no_secret_configured_skips_verification(self):
        os.environ.pop("PADDLE_WEBHOOK_SECRET", None)
        body = b'{"event_id":"e6"}'
        # Should return True (dev mode — skip verification)
        self.assertTrue(self._verify(body, None))


# ---------------------------------------------------------------------------
# Webhook service: idempotency
# ---------------------------------------------------------------------------

class TestPaddleWebhookIdempotency(unittest.TestCase):
    def _make_mock_db(self):
        mock_db = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor
        mock_db.get_connection = MagicMock(return_value=mock_conn)
        return mock_db, mock_conn, mock_cursor

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

        with patch("src.repositories.paddle_repo.paddle_event_already_processed", return_value=False), \
             patch("src.repositories.paddle_repo.record_paddle_webhook_event", return_value=True), \
             patch("src.repositories.paddle_repo.mark_paddle_event_processed"), \
             patch("src.repositories.paddle_repo.upsert_paddle_customer"), \
             patch("src.repositories.paddle_repo.upsert_paddle_subscription", return_value={}), \
             patch.dict(os.environ, {
                 "PADDLE_PRO_MONTHLY_PRICE_ID": "pri_pro_monthly",
                 "PADDLE_PRO_YEARLY_PRICE_ID": "",
                 "PADDLE_PREMIUM_MONTHLY_PRICE_ID": "",
                 "PADDLE_PREMIUM_YEARLY_PRICE_ID": "",
             }):
            result = process_paddle_webhook(
                event_id="evt_new",
                event_type="subscription.created",
                payload=_build_sub_payload(),
                db_module=MagicMock(),
            )
        self.assertNotEqual(result["status"], "skipped")


# ---------------------------------------------------------------------------
# Webhook service: subscription lifecycle
# ---------------------------------------------------------------------------

class TestPaddleSubscriptionLifecycle(unittest.TestCase):
    def _run(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        from src.services.paddle_webhook_service import process_paddle_webhook
        import src.services.paddle_webhook_service as pws
        pws._PRICE_TO_PLAN.clear()

        with patch("src.repositories.paddle_repo.paddle_event_already_processed", return_value=False), \
             patch("src.repositories.paddle_repo.record_paddle_webhook_event", return_value=True), \
             patch("src.repositories.paddle_repo.mark_paddle_event_processed"), \
             patch("src.repositories.paddle_repo.upsert_paddle_customer"), \
             patch("src.repositories.paddle_repo.upsert_paddle_subscription", return_value={}), \
             patch("src.repositories.paddle_repo.get_paddle_customer_by_paddle_id", return_value=None), \
             patch.dict(os.environ, {
                 "PADDLE_PRO_MONTHLY_PRICE_ID": "pri_pro_monthly",
                 "PADDLE_PRO_YEARLY_PRICE_ID": "pri_pro_yearly",
                 "PADDLE_PREMIUM_MONTHLY_PRICE_ID": "pri_prem_monthly",
                 "PADDLE_PREMIUM_YEARLY_PRICE_ID": "pri_prem_yearly",
             }):
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

    def test_premium_plan_resolved_correctly(self):
        payload = _build_sub_payload(
            event_id="evt_prem1",
            event_type="subscription.created",
            price_id="pri_prem_monthly",
        )
        result = self._run("subscription.created", payload)
        self.assertEqual(result["status"], "processed")
        self.assertEqual(result.get("plan"), "premium")

    def test_yearly_billing_cycle(self):
        payload = _build_sub_payload(
            event_id="evt_yearly",
            event_type="subscription.created",
            price_id="pri_pro_yearly",
        )
        with patch("src.repositories.paddle_repo.paddle_event_already_processed", return_value=False), \
             patch("src.repositories.paddle_repo.record_paddle_webhook_event", return_value=True), \
             patch("src.repositories.paddle_repo.mark_paddle_event_processed"), \
             patch("src.repositories.paddle_repo.upsert_paddle_customer"), \
             patch("src.repositories.paddle_repo.get_paddle_customer_by_paddle_id", return_value=None):
            captured = {}
            def capture_upsert(**kwargs):
                captured.update(kwargs)
                return {}
            with patch("src.repositories.paddle_repo.upsert_paddle_subscription", side_effect=lambda db, **kw: captured.update(kw) or {}), \
                 patch.dict(os.environ, {
                     "PADDLE_PRO_MONTHLY_PRICE_ID": "pri_pro_monthly",
                     "PADDLE_PRO_YEARLY_PRICE_ID": "pri_pro_yearly",
                     "PADDLE_PREMIUM_MONTHLY_PRICE_ID": "pri_prem_monthly",
                     "PADDLE_PREMIUM_YEARLY_PRICE_ID": "pri_prem_yearly",
                 }):
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
        self.assertIn(result["status"], ("skipped", "processed"))

    def test_no_user_id_in_custom_data_returns_warning(self):
        payload = {
            "event_id": "evt_nouid",
            "event_type": "subscription.created",
            "data": {
                "id": "sub_001",
                "customer_id": "ctm_001",
                "status": "active",
                "custom_data": {},
                "items": [{"price": {"id": "pri_pro_monthly"}}],
                "current_billing_period": {"starts_at": None, "ends_at": None},
            },
        }
        with patch("src.repositories.paddle_repo.paddle_event_already_processed", return_value=False), \
             patch("src.repositories.paddle_repo.record_paddle_webhook_event", return_value=True), \
             patch("src.repositories.paddle_repo.mark_paddle_event_processed"), \
             patch("src.repositories.paddle_repo.get_paddle_customer_by_paddle_id", return_value=None), \
             patch.dict(os.environ, {
                 "PADDLE_PRO_MONTHLY_PRICE_ID": "pri_pro_monthly",
                 "PADDLE_PRO_YEARLY_PRICE_ID": "",
                 "PADDLE_PREMIUM_MONTHLY_PRICE_ID": "",
                 "PADDLE_PREMIUM_YEARLY_PRICE_ID": "",
             }):
            from src.services.paddle_webhook_service import process_paddle_webhook
            result = process_paddle_webhook(
                event_id="evt_nouid",
                event_type="subscription.created",
                payload=payload,
                db_module=MagicMock(),
            )
        self.assertIn("warning", result)


# ---------------------------------------------------------------------------
# billing_mode helper
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


if __name__ == "__main__":
    unittest.main()
