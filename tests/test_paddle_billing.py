"""Tests for Paddle Billing: signature verification, webhook idempotency,
subscription lifecycle events, billing status, customer portal, and route registration.

Run: pytest tests/test_paddle_billing.py -v
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
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
}


def _clear_price_cache():
    import src.services.paddle_webhook_service as pws
    pws._PRICE_TO_PLAN.clear()


# ---------------------------------------------------------------------------
# Finding #4 — route existence on real FastAPI app
# ---------------------------------------------------------------------------

class TestPaddleRouteRegistration(unittest.TestCase):
    def test_four_routes_on_router(self):
        """paddle_billing_router must define the four required routes."""
        from fastapi.routing import APIRoute
        from src.api.routers.paddle_billing import paddle_billing_router
        paths = {r.path for r in paddle_billing_router.routes if isinstance(r, APIRoute)}
        self.assertIn("/api/v1/billing/paddle/webhook", paths)
        self.assertIn("/api/v1/billing/status", paths)
        self.assertIn("/api/v1/billing/customer-portal", paths)
        self.assertIn("/api/v1/billing/paddle/checkout-session", paths,
                      "POST /api/v1/billing/paddle/checkout-session missing")

    def test_router_included_in_app(self):
        """paddle_billing_router must be included in the FastAPI app (via openapi schema)."""
        from src.api.app import app
        schema = app.openapi()
        app_paths = set(schema.get("paths", {}).keys())
        self.assertIn("/api/v1/billing/status", app_paths)
        self.assertIn("/api/v1/billing/customer-portal", app_paths)
        self.assertIn("/api/v1/billing/paddle/checkout-session", app_paths,
                      "POST /api/v1/billing/paddle/checkout-session not in app OpenAPI schema")


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
# Webhook replay after failure — regression for the claim/idempotency bug.
#
# In-memory stand-in for the paddle_webhook_events table, faithful enough to run
# the REAL paddle_repo claim/mark functions end-to-end without a live DB. It
# distinguishes ON CONFLICT DO NOTHING (old, buggy) from DO UPDATE ... reclaim
# (new), so the replay test below fails on the old code and passes on the fix.
# ---------------------------------------------------------------------------

class _FakeCursor:
    def __init__(self, events: Dict[str, str]):
        self._events = events
        self._result = None
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    @staticmethod
    def _reclaimable(status: str, sql: str) -> bool:
        # Mirror the claim's WHERE clause: a 'failed' row is reclaimable only
        # when the SQL actually asks to reclaim failed events. (Stale-'pending'
        # timing is not modeled here — not needed for this regression.)
        return status == "failed" and "status = 'failed'" in sql

    def execute(self, sql, params=None):
        params = params or ()
        s = " ".join(sql.split())
        if "INSERT INTO paddle_webhook_events" in s:
            eid = params[0]
            status = self._events.get(eid)
            if status is None:
                self._events[eid] = "pending"
                self._result, self.rowcount = (1,), 1
            elif "DO UPDATE" in s and self._reclaimable(status, s):
                self._events[eid] = "pending"
                self._result, self.rowcount = (1,), 1
            else:
                # ON CONFLICT DO NOTHING, or claim disallowed (processed/in-flight)
                self._result, self.rowcount = None, 0
        elif "SELECT status FROM paddle_webhook_events" in s:
            status = self._events.get(params[0])
            self._result = {"status": status} if status is not None else None
            self.rowcount = 1 if status is not None else 0
        elif "status = 'processed'" in s:
            self._events[params[0]] = "processed"
            self.rowcount = 1
        elif "status = 'failed'" in s:
            # mark_paddle_event_failed params = (error_detail, event_id)
            self._events[params[1]] = "failed"
            self.rowcount = 1
        else:
            self._result, self.rowcount = None, 0

    def fetchone(self):
        return self._result


class _FakeWebhookEventsDB:
    def __init__(self):
        self.events: Dict[str, str] = {}

    def cursor(self):
        return _FakeCursor(self.events)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


class TestPaddleWebhookReplayAfterFailure(unittest.TestCase):
    """A webhook event that FAILS (HTTP 500) must be fully reprocessed — not
    silently skipped as a duplicate — when Paddle retries the same event_id."""

    def _process(self, db, event_id, upsert):
        from src.services.paddle_webhook_service import process_paddle_webhook
        _clear_price_cache()
        with patch("src.repositories.paddle_repo._get_conn", return_value=db), \
             patch("src.repositories.paddle_repo.get_paddle_subscription_by_paddle_id",
                   return_value={"user_id": "user_replay"}), \
             patch("src.repositories.paddle_repo.get_paddle_customer_by_paddle_id", return_value=None), \
             patch("src.repositories.paddle_repo.get_checkout_session", return_value=None), \
             patch("src.repositories.paddle_repo.get_paddle_subscription_by_user", return_value=None), \
             patch("src.repositories.paddle_repo.upsert_paddle_customer"), \
             patch("src.repositories.paddle_repo.upsert_paddle_subscription", upsert), \
             patch.dict(os.environ, _PRO_ENV, clear=False):
            return process_paddle_webhook(
                event_id=event_id,
                event_type="subscription.created",
                payload=_build_sub_payload(event_id=event_id),
                db_module=MagicMock(),
            )

    def test_failed_event_is_reprocessed_on_retry(self):
        db = _FakeWebhookEventsDB()
        # First delivery raises inside the handler; the Paddle retry succeeds.
        upsert = MagicMock(side_effect=[Exception("db down"), {}])
        event_id = "evt_replay_1"

        first = self._process(db, event_id, upsert)
        self.assertEqual(first["status"], "failed")
        self.assertEqual(db.events[event_id], "failed",
                         "first failure must persist as 'failed' for replay")

        second = self._process(db, event_id, upsert)
        self.assertEqual(second["status"], "processed",
                         "failed event must be reprocessed on retry, not skipped as duplicate")
        self.assertEqual(db.events[event_id], "processed")
        self.assertEqual(upsert.call_count, 2,
                         "the subscription upsert must actually run again on the retry")

    def test_processed_event_is_not_reprocessed(self):
        db = _FakeWebhookEventsDB()
        upsert = MagicMock(return_value={})
        event_id = "evt_replay_2"

        first = self._process(db, event_id, upsert)
        self.assertEqual(first["status"], "processed")

        # A duplicate delivery of an already-processed event must be skipped.
        second = self._process(db, event_id, upsert)
        self.assertEqual(second["status"], "skipped")
        self.assertEqual(second["reason"], "duplicate")
        self.assertEqual(upsert.call_count, 1,
                         "an already-processed event must not run the handler again")

    def test_claim_sql_reclaims_failed_and_returns_by_row(self):
        """record_paddle_webhook_event must be an atomic claim: it returns True
        iff the DB returns a claimed row, and its SQL reclaims failed events."""
        from src.repositories import paddle_repo
        cur = MagicMock()
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur

        cur.fetchone.return_value = (42,)  # RETURNING id -> a row -> claimed
        with patch("src.repositories.paddle_repo._get_conn", return_value=conn):
            claimed = paddle_repo.record_paddle_webhook_event(
                MagicMock(), "evt_wire", "subscription.created")
        self.assertTrue(claimed)

        sql = " ".join(cur.execute.call_args[0][0].split())
        self.assertIn("ON CONFLICT", sql)
        self.assertIn("DO UPDATE", sql)
        self.assertIn("RETURNING", sql)
        self.assertIn("status = 'failed'", sql, "claim must reclaim previously-failed events")

        cur.fetchone.return_value = None  # no row -> not claimed
        with patch("src.repositories.paddle_repo._get_conn", return_value=conn):
            not_claimed = paddle_repo.record_paddle_webhook_event(
                MagicMock(), "evt_wire", "subscription.created")
        self.assertFalse(not_claimed)


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
             patch("src.repositories.paddle_repo.get_paddle_customer_by_paddle_id",
                   return_value={"user_id": "user@example.com"}), \
             patch("src.repositories.paddle_repo.get_checkout_session", return_value=None), \
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

    def test_billing_cycle_is_always_monthly(self):
        """Single-plan scope: no yearly SKU exists, billing_cycle is always 'monthly'."""
        payload = _build_sub_payload(
            event_id="evt_cycle",
            event_type="subscription.created",
            price_id="pri_pro_monthly",
        )
        _clear_price_cache()
        captured = {}
        with patch("src.repositories.paddle_repo.paddle_event_already_processed", return_value=False), \
             patch("src.repositories.paddle_repo.record_paddle_webhook_event", return_value=True), \
             patch("src.repositories.paddle_repo.mark_paddle_event_processed"), \
             patch("src.repositories.paddle_repo.upsert_paddle_customer"), \
             patch("src.repositories.paddle_repo.get_paddle_subscription_by_paddle_id", return_value=None), \
             patch("src.repositories.paddle_repo.get_paddle_customer_by_paddle_id",
                   return_value={"user_id": "user@example.com"}), \
             patch("src.repositories.paddle_repo.get_checkout_session", return_value=None), \
             patch("src.repositories.paddle_repo.upsert_paddle_subscription",
                   side_effect=lambda db, **kw: captured.update(kw) or {}), \
             patch.dict(os.environ, _PRO_ENV, clear=False):
            from src.services.paddle_webhook_service import process_paddle_webhook
            process_paddle_webhook(
                event_id="evt_cycle",
                event_type="subscription.created",
                payload=payload,
                db_module=MagicMock(),
            )
        self.assertEqual(captured.get("billing_cycle"), "monthly")

    def test_unhandled_event_type_skipped_gracefully(self):
        payload = {"event_id": "evt_unk", "event_type": "customer.created", "data": {}}
        result = self._run("customer.created", payload)
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "unhandled_event_type")

    def test_no_user_id_returns_warning(self):
        """When DB lookup + checkout_session both find no user, emit warning.
        custom_data.user_id is NOT used as identity."""
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
             patch("src.repositories.paddle_repo.get_checkout_session", return_value=None), \
             patch.dict(os.environ, _PRO_ENV, clear=False):
            from src.services.paddle_webhook_service import process_paddle_webhook
            result = process_paddle_webhook(
                event_id="evt_nouid",
                event_type="subscription.created",
                payload=payload,
                db_module=MagicMock(),
            )
        self.assertIn("warning", result)

    def test_custom_data_user_id_not_used_as_identity(self):
        """custom_data.user_id must NOT be used as identity fallback.
        Only DB records and server-owned checkout_session_id are trusted."""
        payload = _build_sub_payload(
            event_id="evt_cuid_reject",
            event_type="subscription.created",
            user_id="untrusted_browser_user",  # custom_data.user_id
        )
        # No checkout_session_id in custom_data — only user_id (untrusted)
        _clear_price_cache()
        with patch("src.repositories.paddle_repo.paddle_event_already_processed", return_value=False), \
             patch("src.repositories.paddle_repo.record_paddle_webhook_event", return_value=True), \
             patch("src.repositories.paddle_repo.mark_paddle_event_processed"), \
             patch("src.repositories.paddle_repo.get_paddle_subscription_by_paddle_id", return_value=None), \
             patch("src.repositories.paddle_repo.get_paddle_customer_by_paddle_id", return_value=None), \
             patch("src.repositories.paddle_repo.get_checkout_session", return_value=None), \
             patch.dict(os.environ, _PRO_ENV, clear=False):
            from src.services.paddle_webhook_service import process_paddle_webhook
            result = process_paddle_webhook(
                event_id="evt_cuid_reject",
                event_type="subscription.created",
                payload=payload,
                db_module=MagicMock(),
            )
        # Must not resolve user from browser-supplied custom_data.user_id
        self.assertIn("warning", result,
                      "Must warn (no_user_id) when only custom_data.user_id exists — not use it")

    def test_db_identity_takes_priority_over_checkout_session(self):
        """DB lookup by customer_id must win over checkout_session_id."""
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
                         "DB-resolved user_id must be used")

    def test_checkout_session_resolves_user(self):
        """Identity via server-owned checkout_session_id must be accepted."""
        session_token = "tok_abc123"
        payload = {
            "event_id": "evt_sess1",
            "event_type": "subscription.created",
            "data": {
                "id": "sub_sess1",
                "customer_id": "ctm_sess1",
                "status": "active",
                "custom_data": {"checkout_session_id": session_token},
                "items": [{"price": {"id": "pri_pro_monthly"}}],
                "current_billing_period": {
                    "starts_at": "2026-07-01T00:00:00Z",
                    "ends_at": "2026-08-01T00:00:00Z",
                },
            },
        }
        session_user = "session_resolved_user"
        captured_upsert = {}
        _clear_price_cache()

        with patch("src.repositories.paddle_repo.paddle_event_already_processed", return_value=False), \
             patch("src.repositories.paddle_repo.record_paddle_webhook_event", return_value=True), \
             patch("src.repositories.paddle_repo.mark_paddle_event_processed"), \
             patch("src.repositories.paddle_repo.upsert_paddle_customer"), \
             patch("src.repositories.paddle_repo.get_paddle_subscription_by_paddle_id", return_value=None), \
             patch("src.repositories.paddle_repo.get_paddle_customer_by_paddle_id", return_value=None), \
             patch("src.repositories.paddle_repo.get_checkout_session",
                   return_value={"user_id": session_user, "session_token": session_token}), \
             patch("src.repositories.paddle_repo.mark_checkout_session_used"), \
             patch("src.repositories.paddle_repo.upsert_paddle_subscription",
                   side_effect=lambda db, **kw: captured_upsert.update(kw) or {}), \
             patch.dict(os.environ, _PRO_ENV, clear=False):
            from src.services.paddle_webhook_service import process_paddle_webhook
            result = process_paddle_webhook(
                event_id="evt_sess1",
                event_type="subscription.created",
                payload=payload,
                db_module=MagicMock(),
            )
        self.assertEqual(result["status"], "processed")
        self.assertEqual(captured_upsert.get("user_id"), session_user,
                         "checkout_session_id must resolve to server-owned user_id")


# ---------------------------------------------------------------------------
# Non-2xx failure semantics + stale-event guard
# ---------------------------------------------------------------------------

class TestPaddleWebhookFailureSemantics(unittest.TestCase):
    def test_failed_processing_returns_500(self):
        """process_paddle_webhook returning 'failed' must trigger a 500 from the router."""
        import asyncio
        from fastapi import HTTPException
        from src.api.routers.paddle_billing import paddle_webhook

        mock_request = MagicMock()
        body = json.dumps({"event_id": "evt_fail", "event_type": "subscription.created"}).encode()

        async def _fake_body():
            return body

        async def _fake_stream():
            yield body

        mock_request.body = _fake_body
        mock_request.stream = _fake_stream
        mock_request.headers = {"Paddle-Signature": "ts=1;h1=x"}

        import asyncio as _asyncio
        with patch("src.api.routers.paddle_billing._verify_paddle_signature", return_value=True), \
             patch("src.repositories.paddle_repo.paddle_event_already_processed", return_value=False), \
             patch("src.repositories.paddle_repo.record_paddle_webhook_event", return_value=True), \
             patch("src.repositories.paddle_repo.mark_paddle_event_failed"), \
             patch("src.repositories.paddle_repo.get_paddle_subscription_by_paddle_id", return_value=None), \
             patch("src.repositories.paddle_repo.get_paddle_customer_by_paddle_id", return_value=None), \
             patch("src.repositories.paddle_repo.get_checkout_session", return_value=None), \
             patch("src.repositories.paddle_repo.upsert_paddle_subscription",
                   side_effect=Exception("db down")), \
             patch("src.repositories.paddle_repo.upsert_paddle_customer"), \
             patch.dict(os.environ, {**_PRO_ENV, "PADDLE_WEBHOOK_SECRET": "",
                                     "ENVIRONMENT": "test"}):
            _clear_price_cache()
            with self.assertRaises(HTTPException) as ctx:
                _asyncio.run(paddle_webhook(mock_request))
        self.assertEqual(ctx.exception.status_code, 500,
                         "failed processing must return HTTP 500 so Paddle retries")

    def test_stale_event_guard_passes_occurred_at(self):
        """upsert_paddle_subscription must receive occurred_at from _parse_occurred_at."""
        from datetime import datetime, timezone
        occurred_str = "2026-07-01T10:00:00Z"
        payload = {
            "event_id": "evt_occ1",
            "event_type": "subscription.updated",
            "occurred_at": occurred_str,
            "data": {
                "id": "sub_occ1",
                "customer_id": "ctm_occ1",
                "status": "active",
                "custom_data": {},
                "items": [{"price": {"id": "pri_pro_monthly"}}],
                "current_billing_period": {
                    "starts_at": "2026-07-01T00:00:00Z",
                    "ends_at": "2026-08-01T00:00:00Z",
                },
            },
        }
        captured = {}
        _clear_price_cache()
        with patch("src.repositories.paddle_repo.paddle_event_already_processed", return_value=False), \
             patch("src.repositories.paddle_repo.record_paddle_webhook_event", return_value=True), \
             patch("src.repositories.paddle_repo.mark_paddle_event_processed"), \
             patch("src.repositories.paddle_repo.upsert_paddle_customer"), \
             patch("src.repositories.paddle_repo.get_paddle_subscription_by_paddle_id",
                   return_value={"user_id": "user_occ1"}), \
             patch("src.repositories.paddle_repo.get_paddle_customer_by_paddle_id", return_value=None), \
             patch("src.repositories.paddle_repo.upsert_paddle_subscription",
                   side_effect=lambda db, **kw: captured.update(kw) or {}), \
             patch.dict(os.environ, _PRO_ENV, clear=False):
            from src.services.paddle_webhook_service import process_paddle_webhook
            process_paddle_webhook(
                event_id="evt_occ1",
                event_type="subscription.updated",
                payload=payload,
                db_module=MagicMock(),
            )
        expected_dt = datetime(2026, 7, 1, 10, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(captured.get("occurred_at"), expected_dt,
                         "occurred_at must be passed to upsert for stale-event guard")

    def test_failed_events_recorded_in_db_for_retry(self):
        """Failed events must be recorded in DB (status=failed) so they can be replayed."""
        from src.services.paddle_webhook_service import process_paddle_webhook
        mark_failed = MagicMock()

        with patch("src.repositories.paddle_repo.paddle_event_already_processed", return_value=False), \
             patch("src.repositories.paddle_repo.record_paddle_webhook_event", return_value=True), \
             patch("src.repositories.paddle_repo.mark_paddle_event_processed"), \
             patch("src.repositories.paddle_repo.mark_paddle_event_failed", mark_failed), \
             patch("src.repositories.paddle_repo.get_paddle_subscription_by_paddle_id",
                   return_value={"user_id": "user_retry"}), \
             patch("src.repositories.paddle_repo.get_paddle_customer_by_paddle_id", return_value=None), \
             patch("src.repositories.paddle_repo.upsert_paddle_customer"), \
             patch("src.repositories.paddle_repo.upsert_paddle_subscription",
                   side_effect=Exception("db exploded on upsert")), \
             patch.dict(os.environ, _PRO_ENV, clear=False):
            _clear_price_cache()
            result = process_paddle_webhook(
                event_id="evt_retry1",
                event_type="subscription.created",
                payload=_build_sub_payload(event_id="evt_retry1"),
                db_module=MagicMock(),
            )
        self.assertEqual(result["status"], "failed",
                         "unhandled exception during processing must return failed status")
        self.assertTrue(mark_failed.called,
                        "mark_paddle_event_failed must be called so the event can be replayed")

    def test_checkout_session_endpoint_returns_token_and_price_id(self):
        """POST /billing/paddle/checkout-session must return session_token + price_id."""
        import asyncio
        from src.api.routers.paddle_billing import create_checkout_session

        mock_request = MagicMock()

        async def _fake_json():
            return {"plan": "pro", "billing_cycle": "monthly"}

        mock_request.json = _fake_json

        active_env = {
            "BILLING_MODE": "paddle",
            "PADDLE_API_KEY": "test_api_key",
            "PADDLE_WEBHOOK_SECRET": "test_webhook_secret",
            "PADDLE_PRO_MONTHLY_PRICE_ID": "pri_pro_monthly",
        }
        with patch("src.repositories.paddle_repo.create_checkout_session"), \
             patch("sys.modules", {**__import__('sys').modules, "src.db": MagicMock()}), \
             patch.dict(os.environ, active_env):
            import asyncio as _asyncio
            resp = _asyncio.run(
                create_checkout_session(mock_request, user_id="user_cs1")
            )
        self.assertIn("session_token", resp)
        self.assertNotEqual(resp["session_token"], "",
                            "session_token must be non-empty")
        self.assertEqual(resp["plan"], "pro")
        self.assertEqual(resp["price_id"], "pri_pro_monthly")

    def test_checkout_session_rejects_invalid_plan(self):
        """POST /billing/paddle/checkout-session must reject unknown plans."""
        import asyncio
        from fastapi import HTTPException
        from src.api.routers.paddle_billing import create_checkout_session

        mock_request = MagicMock()

        async def _fake_json():
            return {"plan": "premium", "billing_cycle": "monthly"}

        mock_request.json = _fake_json

        active_env = {
            "BILLING_MODE": "paddle",
            "PADDLE_API_KEY": "test_api_key",
            "PADDLE_WEBHOOK_SECRET": "test_webhook_secret",
            "PADDLE_PRO_MONTHLY_PRICE_ID": "pri_pro_monthly",
        }
        with patch.dict(os.environ, active_env):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(
                    create_checkout_session(mock_request, user_id="user_bad")
                )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_checkout_session_fails_closed_when_paddle_inactive(self):
        """No checkout session is issued when Paddle billing is not fully active.

        Covers both BILLING_MODE != paddle and an incomplete server credential
        set — a stale client bundle must never start a checkout the backend
        cannot complete end-to-end (payment → webhook → entitlement).
        """
        import asyncio
        from fastapi import HTTPException
        from src.api.routers.paddle_billing import create_checkout_session

        mock_request = MagicMock()

        async def _fake_json():
            return {"plan": "pro", "billing_cycle": "monthly"}

        mock_request.json = _fake_json

        inactive_envs = [
            {"BILLING_MODE": "manual",
             "PADDLE_API_KEY": "k", "PADDLE_WEBHOOK_SECRET": "s",
             "PADDLE_PRO_MONTHLY_PRICE_ID": "pri_x"},
            {"BILLING_MODE": "paddle",
             "PADDLE_API_KEY": "k", "PADDLE_PRO_MONTHLY_PRICE_ID": "pri_x"},  # no webhook secret
        ]
        for env in inactive_envs:
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaises(HTTPException) as ctx:
                    asyncio.run(
                        create_checkout_session(mock_request, user_id="user_blocked")
                    )
            self.assertEqual(ctx.exception.status_code, 503,
                             f"checkout-session must 503 for env {env}")


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


# ---------------------------------------------------------------------------
# Regression: paddle_repo must use a real, dict-cursor-capable connection
# ---------------------------------------------------------------------------
#
# src.db.get_db_connection() returns a plain-tuple-cursor psycopg2 connection
# with no get_connection() method at all — every paddle_repo.* call that
# doesn't inject conn= explicitly would previously raise AttributeError (or,
# if patched to the right method name, break on dict(row) access against a
# tuple cursor). This is masked by every other test in this file because
# they patch the paddle_repo functions themselves. Guard the fix directly.

class TestPaddleRepoConnection(unittest.TestCase):
    def test_get_conn_uses_ricodb_not_db_module(self):
        from src.repositories import paddle_repo

        fake_conn = MagicMock()
        fake_ricodb = MagicMock()
        fake_ricodb.connect.return_value = fake_conn

        broken_db_module = MagicMock(spec=[])  # no get_connection/get_db_connection attrs at all

        with patch("src.repositories.paddle_repo._rico_db", return_value=fake_ricodb):
            conn = paddle_repo._get_conn(broken_db_module)

        fake_ricodb.connect.assert_called_once()
        self.assertIs(conn, fake_conn)


class TestBillingConfigEndpoint(unittest.TestCase):
    """GET /api/v1/billing/config — unauthenticated, no secrets exposed."""

    def _get_client(self, billing_mode: str = "paddle", sandbox: str = "true"):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from src.api.routers.paddle_billing import router
        app = FastAPI()
        app.include_router(router)
        env = {"BILLING_MODE": billing_mode, "PADDLE_SANDBOX": sandbox}
        with patch.dict(os.environ, env):
            return TestClient(app)

    def test_returns_200_no_auth(self):
        client = self._get_client("paddle", "true")
        with patch.dict(os.environ, {"BILLING_MODE": "paddle", "PADDLE_SANDBOX": "true"}):
            r = client.get("/api/v1/billing/config")
        self.assertEqual(r.status_code, 200)

    # Full server credential set — paddle_active requires ALL of these
    # (fail-closed: a checkout the webhook can't complete is never offered).
    _FULL_PADDLE_ENV = {
        "BILLING_MODE": "paddle",
        "PADDLE_SANDBOX": "true",
        "PADDLE_API_KEY": "test_api_key",
        "PADDLE_WEBHOOK_SECRET": "test_webhook_secret",
        "PADDLE_PRO_MONTHLY_PRICE_ID": "pri_test",
    }

    def test_paddle_mode_fields(self):
        with patch.dict(os.environ, self._FULL_PADDLE_ENV, clear=True):
            from fastapi.testclient import TestClient
            from fastapi import FastAPI
            from src.api.routers.paddle_billing import router
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)
            r = client.get("/api/v1/billing/config")
        data = r.json()
        self.assertEqual(data["billing_mode"], "paddle")
        self.assertTrue(data["paddle_active"])
        self.assertTrue(data["sandbox"])

    def test_paddle_mode_incomplete_credentials_fails_closed(self):
        """BILLING_MODE=paddle with ANY missing server credential → paddle_active=false."""
        for missing in ("PADDLE_API_KEY", "PADDLE_WEBHOOK_SECRET", "PADDLE_PRO_MONTHLY_PRICE_ID"):
            env = {k: v for k, v in self._FULL_PADDLE_ENV.items() if k != missing}
            with patch.dict(os.environ, env, clear=True):
                from fastapi.testclient import TestClient
                from fastapi import FastAPI
                from src.api.routers.paddle_billing import router
                app = FastAPI()
                app.include_router(router)
                client = TestClient(app)
                r = client.get("/api/v1/billing/config")
            data = r.json()
            self.assertEqual(data["billing_mode"], "paddle",
                             f"billing_mode must still report paddle without {missing}")
            self.assertFalse(data["paddle_active"],
                             f"paddle_active must fail closed without {missing}")

    def test_paddle_mode_live_sandbox_false(self):
        """PADDLE_SANDBOX=false is reported so the client can cross-check environments."""
        env = {**self._FULL_PADDLE_ENV, "PADDLE_SANDBOX": "false"}
        with patch.dict(os.environ, env, clear=True):
            from fastapi.testclient import TestClient
            from fastapi import FastAPI
            from src.api.routers.paddle_billing import router
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)
            r = client.get("/api/v1/billing/config")
        data = r.json()
        self.assertTrue(data["paddle_active"])
        self.assertFalse(data["sandbox"])

    def test_manual_mode_fields(self):
        with patch.dict(os.environ, {"BILLING_MODE": "manual", "PADDLE_SANDBOX": "true"}):
            from fastapi.testclient import TestClient
            from fastapi import FastAPI
            from src.api.routers.paddle_billing import router
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)
            r = client.get("/api/v1/billing/config")
        data = r.json()
        self.assertEqual(data["billing_mode"], "manual")
        self.assertFalse(data["paddle_active"])

    def test_webhook_keeps_processing_under_manual_rollback(self):
        """Rollback continuity: BILLING_MODE=manual must NOT stop webhook processing.

        The rollback path (set BILLING_MODE=manual on Render) disables NEW
        checkouts only. Signed webhooks for existing subscriptions must keep
        processing so renewals/cancellations still update entitlements —
        the webhook route gates on the signature, never on billing mode.
        """
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from src.api.routers.paddle_billing import router

        app = FastAPI()
        app.include_router(router)

        body = json.dumps(
            {"event_id": "evt_rollback_1", "event_type": "subscription.updated"}
        ).encode("utf-8")
        secret = "rollback_secret"
        header = _make_sig_header(body, secret)

        rollback_env = {
            "BILLING_MODE": "manual",  # checkout disabled…
            "PADDLE_WEBHOOK_SECRET": secret,  # …but webhook credentials intact
        }
        with patch.dict(os.environ, rollback_env, clear=True), \
             patch("sys.modules", {**sys.modules, "src.db": MagicMock()}), \
             patch(
                 "src.services.paddle_webhook_service.process_paddle_webhook",
                 return_value={"status": "processed"},
             ) as processor:
            client = TestClient(app)
            r = client.post(
                "/api/v1/billing/paddle/webhook",
                content=body,
                headers={"Paddle-Signature": header, "Content-Type": "application/json"},
            )

        self.assertEqual(r.status_code, 200,
                         "signed webhook must be accepted under BILLING_MODE=manual")
        self.assertTrue(processor.called,
                        "webhook processing must run under BILLING_MODE=manual")

    def test_no_secrets_in_response(self):
        with patch.dict(os.environ, {"BILLING_MODE": "paddle", "PADDLE_SANDBOX": "true",
                                      "PADDLE_API_KEY": "secret_key",
                                      "PADDLE_WEBHOOK_SECRET": "secret_webhook"}):
            from fastapi.testclient import TestClient
            from fastapi import FastAPI
            from src.api.routers.paddle_billing import router
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)
            r = client.get("/api/v1/billing/config")
        body = r.text
        self.assertNotIn("secret_key", body)
        self.assertNotIn("secret_webhook", body)
        self.assertNotIn("PADDLE_API_KEY", body)


if __name__ == "__main__":
    unittest.main()
