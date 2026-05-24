"""Tests for subscription_webhook_service — Phase 2 event processing.

All DB calls are mocked. No live Stripe, Render, or Neon required.
Idempotency gate (record_subscription_event) is patched at the service level.

Fixture payloads mirror real Stripe event shapes (simplified but structurally
correct) so handlers exercise realistic code paths.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, call, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

# ── Patch targets (module-level imports in the service) ───────────────────────
_SVC = "src.services.subscription_webhook_service"
_RECORD        = f"{_SVC}.record_subscription_event"
_UPDATE_STATUS = f"{_SVC}.update_subscription_event_status"
_UPSERT        = f"{_SVC}.upsert_subscription"
_GET_SUB       = f"{_SVC}.get_subscription"
_GET_CUS       = f"{_SVC}.get_subscription_by_stripe_customer"
_GET_EVENT_STATUS = f"{_SVC}.get_subscription_event_status"


# ── Autouse: silence update_subscription_event_status in all tests ────────────
# process_stripe_event now calls update_subscription_event_status after every
# handler. Tests that don't explicitly care about the status update get a no-op
# via this autouse fixture so they don't need to patch it individually.

@pytest.fixture(autouse=True)
def _noop_update_status(monkeypatch):
    import src.services.subscription_webhook_service as svc
    monkeypatch.setattr(svc, "update_subscription_event_status", lambda *a, **kw: True)


# ── Stripe event payload builders ─────────────────────────────────────────────

def _checkout_event(
    user_id="alice@rico.ai",
    plan="pro",
    customer="cus_test",
    subscription="sub_test",
):
    return {
        "object": {
            "customer": customer,
            "subscription": subscription,
            "metadata": {"user_id": user_id, "plan": plan},
        }
    }


def _subscription_event(
    user_id="alice@rico.ai",
    plan="pro",
    status="active",
    customer="cus_test",
    sub_id="sub_test",
    period_start=1_716_000_000,
    period_end=1_718_592_000,
    price_id=None,
):
    items = {}
    if price_id:
        items = {"data": [{"price": {"id": price_id}}]}
    return {
        "object": {
            "id": sub_id,
            "customer": customer,
            "status": status,
            "metadata": {"user_id": user_id, "plan": plan},
            "items": items,
            "current_period_start": period_start,
            "current_period_end": period_end,
        }
    }


def _deleted_event(user_id="alice@rico.ai", customer="cus_test", sub_id="sub_test"):
    return {
        "object": {
            "id": sub_id,
            "customer": customer,
            "status": "canceled",
            "metadata": {"user_id": user_id},
        }
    }


def _invoice_event(
    customer="cus_test",
    subscription="sub_test",
    period_start=1_716_000_000,
    period_end=1_718_592_000,
):
    return {
        "object": {
            "customer": customer,
            "subscription": subscription,
            "lines": {
                "data": [{"period": {"start": period_start, "end": period_end}}]
            },
        }
    }


def _existing_row(user_id="alice@rico.ai", plan="pro", status="active"):
    return {
        "user_id": user_id, "plan": plan, "status": status,
        "stripe_customer_id": "cus_test", "stripe_subscription_id": "sub_test",
        "current_period_start": None, "current_period_end": None,
    }


# ── Idempotency ───────────────────────────────────────────────────────────────

class TestIdempotency:
    def test_processed_duplicate_skips_all_processing(self):
        from src.services.subscription_webhook_service import process_stripe_event
        with patch(_RECORD, return_value=False) as mock_record, \
             patch(_GET_EVENT_STATUS, return_value="processed"), \
             patch(_UPSERT) as mock_upsert:
            result = process_stripe_event(
                "evt_dup", "checkout.session.completed", _checkout_event()
            )
        assert result is True
        mock_upsert.assert_not_called()

    def test_unhandled_event_type_is_claimed_and_acknowledged(self):
        from src.services.subscription_webhook_service import process_stripe_event
        with patch(_RECORD, return_value=True), patch(_UPSERT) as mock_upsert:
            result = process_stripe_event("evt_x", "payment_intent.created", {"object": {}})
        assert result is True
        mock_upsert.assert_not_called()

    def test_record_called_with_correct_args(self):
        from src.services.subscription_webhook_service import process_stripe_event
        with patch(_RECORD, return_value=True) as mock_record, \
             patch(_UPSERT, return_value=_existing_row()):
            process_stripe_event("evt_1", "checkout.session.completed", _checkout_event())
        mock_record.assert_called_once_with(
            "evt_1",
            "checkout.session.completed",
            user_id="alice@rico.ai",
            payload=_checkout_event(),
        )


# ── checkout.session.completed ────────────────────────────────────────────────

class TestCheckoutCompleted:
    def test_creates_active_pro_subscription(self):
        from src.services.subscription_webhook_service import process_stripe_event
        with patch(_RECORD, return_value=True), \
             patch(_UPSERT, return_value=_existing_row()) as mock_upsert:
            result = process_stripe_event(
                "evt_co_1", "checkout.session.completed", _checkout_event(plan="pro")
            )
        assert result is True
        mock_upsert.assert_called_once()
        kw = mock_upsert.call_args
        assert kw.args[0] == "alice@rico.ai"
        assert kw.kwargs["plan"] == "pro"
        assert kw.kwargs["status"] == "active"
        assert kw.kwargs["stripe_customer_id"] == "cus_test"
        assert kw.kwargs["stripe_subscription_id"] == "sub_test"
        assert "monthly_ai_message_limit" not in kw.kwargs
        assert "saved_jobs_limit" not in kw.kwargs
        assert "premium_recommendations_enabled" not in kw.kwargs

    def test_creates_active_premium_subscription(self):
        from src.services.subscription_webhook_service import process_stripe_event
        with patch(_RECORD, return_value=True), \
             patch(_UPSERT, return_value=_existing_row(plan="premium")) as mock_upsert:
            result = process_stripe_event(
                "evt_co_2", "checkout.session.completed", _checkout_event(plan="premium")
            )
        assert result is True
        args = mock_upsert.call_args
        assert args.kwargs["plan"] == "premium"
        assert args.kwargs["status"] == "active"

    def test_skips_when_user_id_missing(self):
        from src.services.subscription_webhook_service import process_stripe_event
        data = {"object": {"customer": "cus_x", "metadata": {}}}
        with patch(_RECORD, return_value=True), patch(_UPSERT) as mock_upsert:
            result = process_stripe_event("evt_co_3", "checkout.session.completed", data)
        assert result is False
        mock_upsert.assert_not_called()

    def test_skips_when_plan_unknown(self):
        from src.services.subscription_webhook_service import process_stripe_event
        data = _checkout_event(plan="enterprise")
        with patch(_RECORD, return_value=True), patch(_UPSERT) as mock_upsert:
            result = process_stripe_event("evt_co_4", "checkout.session.completed", data)
        assert result is False
        mock_upsert.assert_not_called()


# ── customer.subscription.created / .updated ─────────────────────────────────

class TestSubscriptionUpsert:
    def test_subscription_created_active(self):
        from src.services.subscription_webhook_service import process_stripe_event
        with patch(_RECORD, return_value=True), \
             patch(_UPSERT, return_value=_existing_row()) as mock_upsert:
            result = process_stripe_event(
                "evt_su_1", "customer.subscription.created",
                _subscription_event(plan="pro", status="active"),
            )
        assert result is True
        kwargs = mock_upsert.call_args.kwargs
        assert kwargs["plan"] == "pro"
        assert kwargs["status"] == "active"
        assert kwargs["stripe_customer_id"] == "cus_test"

    def test_subscription_updated_to_past_due(self):
        from src.services.subscription_webhook_service import process_stripe_event
        with patch(_RECORD, return_value=True), \
             patch(_UPSERT, return_value=_existing_row(status="past_due")) as mock_upsert:
            result = process_stripe_event(
                "evt_su_2", "customer.subscription.updated",
                _subscription_event(status="past_due"),
            )
        assert result is True
        assert mock_upsert.call_args.kwargs["status"] == "past_due"

    def test_trialing_maps_to_active(self):
        from src.services.subscription_webhook_service import process_stripe_event
        with patch(_RECORD, return_value=True), \
             patch(_UPSERT, return_value=_existing_row()) as mock_upsert:
            process_stripe_event(
                "evt_su_3", "customer.subscription.updated",
                _subscription_event(status="trialing"),
            )
        assert mock_upsert.call_args.kwargs["status"] == "active"

    def test_period_timestamps_converted(self):
        from src.services.subscription_webhook_service import process_stripe_event
        from datetime import datetime, timezone
        with patch(_RECORD, return_value=True), \
             patch(_UPSERT, return_value=_existing_row()) as mock_upsert:
            process_stripe_event(
                "evt_su_4", "customer.subscription.updated",
                _subscription_event(period_start=1_716_000_000, period_end=1_718_592_000),
            )
        kwargs = mock_upsert.call_args.kwargs
        assert kwargs["current_period_start"] == datetime.fromtimestamp(1_716_000_000, tz=timezone.utc)
        assert kwargs["current_period_end"] == datetime.fromtimestamp(1_718_592_000, tz=timezone.utc)

    def test_falls_back_to_price_id_when_metadata_plan_missing(self, monkeypatch):
        from src.services.subscription_webhook_service import process_stripe_event
        monkeypatch.setenv("STRIPE_PRO_PRICE_ID", "price_pro_live")
        data = {
            "object": {
                "id": "sub_test",
                "customer": "cus_test",
                "status": "active",
                "metadata": {"user_id": "alice@rico.ai"},
                "items": {"data": [{"price": {"id": "price_pro_live"}}]},
                "current_period_start": None,
                "current_period_end": None,
            }
        }
        with patch(_RECORD, return_value=True), \
             patch(_UPSERT, return_value=_existing_row()) as mock_upsert:
            result = process_stripe_event("evt_su_5", "customer.subscription.updated", data)
        assert result is True
        assert mock_upsert.call_args.kwargs["plan"] == "pro"

    def test_prefers_price_id_over_stale_metadata_plan(self, monkeypatch):
        from src.services.subscription_webhook_service import process_stripe_event
        monkeypatch.setenv("STRIPE_PREMIUM_PRICE_ID", "price_premium_live")
        data = _subscription_event(plan="pro", price_id="price_premium_live")
        with patch(_RECORD, return_value=True), \
             patch(_UPSERT, return_value=_existing_row(plan="premium")) as mock_upsert:
            result = process_stripe_event("evt_su_price", "customer.subscription.updated", data)
        assert result is True
        assert mock_upsert.call_args.kwargs["plan"] == "premium"

    def test_falls_back_to_customer_lookup_when_metadata_user_id_missing(self):
        from src.services.subscription_webhook_service import process_stripe_event
        data = {
            "object": {
                "id": "sub_test",
                "customer": "cus_test",
                "status": "active",
                "metadata": {"plan": "pro"},
                "items": {},
                "current_period_start": None,
                "current_period_end": None,
            }
        }
        with patch(_RECORD, return_value=True), \
             patch(_GET_CUS, return_value=_existing_row()), \
             patch(_UPSERT, return_value=_existing_row()) as mock_upsert:
            result = process_stripe_event("evt_su_6", "customer.subscription.updated", data)
        assert result is True
        assert mock_upsert.call_args.args[0] == "alice@rico.ai"

    def test_skips_when_user_id_unresolvable(self):
        from src.services.subscription_webhook_service import process_stripe_event
        data = {
            "object": {
                "id": "sub_test",
                "customer": "cus_unknown",
                "status": "active",
                "metadata": {},
                "items": {},
                "current_period_start": None,
                "current_period_end": None,
            }
        }
        with patch(_RECORD, return_value=True), \
             patch(_GET_CUS, return_value=None), \
             patch(_UPSERT) as mock_upsert:
            result = process_stripe_event("evt_su_7", "customer.subscription.updated", data)
        assert result is False
        mock_upsert.assert_not_called()


# ── customer.subscription.deleted ────────────────────────────────────────────

class TestSubscriptionDeleted:
    def test_sets_canceled_preserving_plan(self):
        from src.services.subscription_webhook_service import process_stripe_event
        with patch(_RECORD, return_value=True), \
             patch(_GET_SUB, return_value=_existing_row(plan="premium")), \
             patch(_UPSERT, return_value=_existing_row(status="canceled")) as mock_upsert:
            result = process_stripe_event(
                "evt_del_1", "customer.subscription.deleted", _deleted_event()
            )
        assert result is True
        kwargs = mock_upsert.call_args.kwargs
        assert kwargs["status"] == "canceled"
        assert kwargs["plan"] == "premium"
        assert "monthly_ai_message_limit" not in kwargs
        assert "premium_recommendations_enabled" not in kwargs

    def test_uses_free_plan_when_no_existing_subscription(self):
        from src.services.subscription_webhook_service import process_stripe_event
        with patch(_RECORD, return_value=True), \
             patch(_GET_SUB, return_value=None), \
             patch(_UPSERT) as mock_upsert:
            process_stripe_event("evt_del_2", "customer.subscription.deleted", _deleted_event())
        assert mock_upsert.call_args.kwargs["plan"] == "free"

    def test_skips_when_user_id_unresolvable(self):
        from src.services.subscription_webhook_service import process_stripe_event
        data = {"object": {"customer": "cus_unknown", "metadata": {}}}
        with patch(_RECORD, return_value=True), \
             patch(_GET_CUS, return_value=None), \
             patch(_UPSERT) as mock_upsert:
            result = process_stripe_event("evt_del_3", "customer.subscription.deleted", data)
        assert result is False
        mock_upsert.assert_not_called()


# ── invoice.paid ──────────────────────────────────────────────────────────────

class TestInvoicePaid:
    def test_activates_subscription_and_updates_period(self):
        from src.services.subscription_webhook_service import process_stripe_event
        from datetime import datetime, timezone
        with patch(_RECORD, return_value=True), \
             patch(_GET_CUS, return_value=_existing_row()), \
             patch(_UPSERT, return_value=_existing_row()) as mock_upsert:
            result = process_stripe_event("evt_inv_1", "invoice.paid", _invoice_event())
        assert result is True
        kwargs = mock_upsert.call_args.kwargs
        assert kwargs["status"] == "active"
        assert kwargs["current_period_start"] == datetime.fromtimestamp(1_716_000_000, tz=timezone.utc)
        assert kwargs["current_period_end"] == datetime.fromtimestamp(1_718_592_000, tz=timezone.utc)

    def test_skips_when_no_subscription_found(self):
        from src.services.subscription_webhook_service import process_stripe_event
        with patch(_RECORD, return_value=True), \
             patch(_GET_CUS, return_value=None), \
             patch(_UPSERT) as mock_upsert:
            result = process_stripe_event("evt_inv_2", "invoice.paid", _invoice_event())
        assert result is False
        mock_upsert.assert_not_called()

    def test_skips_when_customer_missing(self):
        from src.services.subscription_webhook_service import process_stripe_event
        with patch(_RECORD, return_value=True), patch(_UPSERT) as mock_upsert:
            result = process_stripe_event("evt_inv_3", "invoice.paid", {"object": {}})
        assert result is False
        mock_upsert.assert_not_called()

    def test_ignores_invoice_for_different_subscription(self):
        from src.services.subscription_webhook_service import process_stripe_event
        with patch(_RECORD, return_value=True), \
             patch(_GET_CUS, return_value=_existing_row()), \
             patch(_UPSERT) as mock_upsert:
            result = process_stripe_event(
                "evt_inv_other", "invoice.paid", _invoice_event(subscription="sub_other")
            )
        assert result is True
        mock_upsert.assert_not_called()


# ── invoice.payment_failed ────────────────────────────────────────────────────

class TestInvoicePaymentFailed:
    def test_sets_past_due(self):
        from src.services.subscription_webhook_service import process_stripe_event
        with patch(_RECORD, return_value=True), \
             patch(_GET_CUS, return_value=_existing_row(plan="premium")), \
             patch(_UPSERT, return_value=_existing_row(status="past_due")) as mock_upsert:
            result = process_stripe_event(
                "evt_fail_1", "invoice.payment_failed", _invoice_event()
            )
        assert result is True
        kwargs = mock_upsert.call_args.kwargs
        assert kwargs["status"] == "past_due"
        assert kwargs["plan"] == "premium"

    def test_skips_when_no_subscription_found(self):
        from src.services.subscription_webhook_service import process_stripe_event
        with patch(_RECORD, return_value=True), \
             patch(_GET_CUS, return_value=None), \
             patch(_UPSERT) as mock_upsert:
            result = process_stripe_event("evt_fail_2", "invoice.payment_failed", _invoice_event())
        assert result is False
        mock_upsert.assert_not_called()

    def test_ignores_failure_for_different_subscription(self):
        from src.services.subscription_webhook_service import process_stripe_event
        with patch(_RECORD, return_value=True), \
             patch(_GET_CUS, return_value=_existing_row()), \
             patch(_UPSERT) as mock_upsert:
            result = process_stripe_event(
                "evt_fail_other", "invoice.payment_failed", _invoice_event(subscription="sub_other")
            )
        assert result is True
        mock_upsert.assert_not_called()


# ── Retry / failure status tracking ──────────────────────────────────────────
#
# Core invariant: a claimed event must transition out of 'pending' regardless
# of handler outcome. 'failed' events are re-claimable; 'processed' are not.

class TestRetryOnFailure:
    def test_handler_failure_marks_event_as_failed(self, monkeypatch):
        import src.services.subscription_webhook_service as svc
        status_updates: list = []
        monkeypatch.setattr(svc, "record_subscription_event", lambda *a, **kw: True)
        monkeypatch.setattr(
            svc,
            "update_subscription_event_status",
            lambda event_id, status, **kw: status_updates.append((event_id, status, kw)) or True,
        )
        monkeypatch.setattr(svc, "upsert_subscription",
                            MagicMock(side_effect=RuntimeError("DB crash")))

        result = svc.process_stripe_event(
            "evt_crash", "checkout.session.completed",
            {"object": {"metadata": {"user_id": "u@t.com", "plan": "pro"},
                        "customer": "cus_1", "subscription": "sub_1"}},
        )

        assert result is False
        assert len(status_updates) == 1
        event_id, status, kw = status_updates[0]
        assert event_id == "evt_crash"
        assert status == "failed"
        assert kw.get("error_detail") == "DB crash"

    def test_handler_success_marks_event_as_processed(self, monkeypatch):
        import src.services.subscription_webhook_service as svc
        status_updates: list = []
        monkeypatch.setattr(svc, "record_subscription_event", lambda *a, **kw: True)
        monkeypatch.setattr(
            svc,
            "update_subscription_event_status",
            lambda event_id, status, **kw: status_updates.append((event_id, status, kw)) or True,
        )
        monkeypatch.setattr(svc, "upsert_subscription", lambda *a, **kw: _existing_row())

        result = svc.process_stripe_event(
            "evt_ok", "checkout.session.completed",
            {"object": {"metadata": {"user_id": "u@t.com", "plan": "pro"},
                        "customer": "cus_1", "subscription": "sub_1"}},
        )

        assert result is True
        assert status_updates == [("evt_ok", "processed", {})]

    def test_handler_false_marks_event_as_failed(self, monkeypatch):
        import src.services.subscription_webhook_service as svc
        status_updates: list = []
        monkeypatch.setattr(svc, "record_subscription_event", lambda *a, **kw: True)
        monkeypatch.setattr(
            svc,
            "update_subscription_event_status",
            lambda event_id, status, **kw: status_updates.append((event_id, status, kw)) or True,
        )
        monkeypatch.setattr(svc, "upsert_subscription", lambda *a, **kw: None)

        result = svc.process_stripe_event(
            "evt_write_fail", "checkout.session.completed",
            {"object": {"metadata": {"user_id": "u@t.com", "plan": "pro"},
                        "customer": "cus_1", "subscription": "sub_1"}},
        )

        assert result is False
        assert status_updates == [
            ("evt_write_fail", "failed", {"error_detail": "handler returned false"})
        ]

    def test_unhandled_event_marks_as_processed_and_acknowledged(self, monkeypatch):
        import src.services.subscription_webhook_service as svc
        status_updates: list = []
        monkeypatch.setattr(svc, "record_subscription_event", lambda *a, **kw: True)
        monkeypatch.setattr(
            svc,
            "update_subscription_event_status",
            lambda event_id, status, **kw: status_updates.append((event_id, status, kw)) or True,
        )

        result = svc.process_stripe_event("evt_unk", "payment.intent.created", {"object": {}})

        assert result is True
        assert status_updates == [("evt_unk", "processed", {})]

    def test_processed_duplicate_returns_true_and_skips_status_update(self, monkeypatch):
        import src.services.subscription_webhook_service as svc
        status_updates: list = []
        monkeypatch.setattr(svc, "record_subscription_event", lambda *a, **kw: False)
        monkeypatch.setattr(svc, "get_subscription_event_status", lambda *a, **kw: "processed")
        monkeypatch.setattr(
            svc,
            "update_subscription_event_status",
            lambda event_id, status, **kw: status_updates.append((event_id, status, kw)) or True,
        )

        result = svc.process_stripe_event("evt_dup", "checkout.session.completed", _checkout_event())

        assert result is True
        assert status_updates == []

    def test_pending_in_flight_returns_true_and_skips_status_update(self, monkeypatch):
        import src.services.subscription_webhook_service as svc
        status_updates: list = []
        monkeypatch.setattr(svc, "record_subscription_event", lambda *a, **kw: False)
        monkeypatch.setattr(svc, "get_subscription_event_status", lambda *a, **kw: "pending")
        monkeypatch.setattr(
            svc,
            "update_subscription_event_status",
            lambda event_id, status, **kw: status_updates.append((event_id, status, kw)) or True,
        )
        monkeypatch.setattr(svc, "upsert_subscription", MagicMock())

        result = svc.process_stripe_event("evt_pending", "checkout.session.completed", _checkout_event())

        assert result is True
        assert status_updates == []
        svc.upsert_subscription.assert_not_called()

    def test_failed_unclaimed_event_remains_retryable(self, monkeypatch):
        import src.services.subscription_webhook_service as svc
        monkeypatch.setattr(svc, "record_subscription_event", lambda *a, **kw: False)
        monkeypatch.setattr(svc, "get_subscription_event_status", lambda *a, **kw: "failed")
        monkeypatch.setattr(svc, "upsert_subscription", MagicMock())

        result = svc.process_stripe_event("evt_failed", "checkout.session.completed", _checkout_event())

        assert result is False
        svc.upsert_subscription.assert_not_called()

    def test_missing_or_db_error_unclaimed_event_returns_false(self, monkeypatch):
        import src.services.subscription_webhook_service as svc
        monkeypatch.setattr(svc, "record_subscription_event", lambda *a, **kw: False)
        monkeypatch.setattr(svc, "get_subscription_event_status", lambda *a, **kw: None)
        monkeypatch.setattr(svc, "upsert_subscription", MagicMock())

        result = svc.process_stripe_event("evt_missing", "checkout.session.completed", _checkout_event())

        assert result is False
        svc.upsert_subscription.assert_not_called()


# ── _price_id_to_plan unit tests ──────────────────────────────────────────────

class TestPriceIdMapping:
    def test_maps_primary_pro_env(self, monkeypatch):
        from src.services.subscription_webhook_service import _price_id_to_plan
        monkeypatch.setenv("STRIPE_PRO_PRICE_ID", "price_pro_123")
        assert _price_id_to_plan("price_pro_123") == "pro"

    def test_maps_legacy_pro_env(self, monkeypatch):
        from src.services.subscription_webhook_service import _price_id_to_plan
        monkeypatch.delenv("STRIPE_PRO_PRICE_ID", raising=False)
        monkeypatch.setenv("STRIPE_PRICE_PRO", "price_pro_legacy")
        assert _price_id_to_plan("price_pro_legacy") == "pro"

    def test_maps_primary_premium_env(self, monkeypatch):
        from src.services.subscription_webhook_service import _price_id_to_plan
        monkeypatch.setenv("STRIPE_PREMIUM_PRICE_ID", "price_prem_123")
        assert _price_id_to_plan("price_prem_123") == "premium"

    def test_unknown_price_id_returns_none(self, monkeypatch):
        from src.services.subscription_webhook_service import _price_id_to_plan
        monkeypatch.delenv("STRIPE_PRO_PRICE_ID", raising=False)
        monkeypatch.delenv("STRIPE_PRICE_PRO", raising=False)
        monkeypatch.delenv("STRIPE_PREMIUM_PRICE_ID", raising=False)
        monkeypatch.delenv("STRIPE_PRICE_PREMIUM", raising=False)
        assert _price_id_to_plan("price_unknown") is None

    def test_empty_price_id_returns_none(self):
        from src.services.subscription_webhook_service import _price_id_to_plan
        assert _price_id_to_plan("") is None


# ── Stripe status mapping ─────────────────────────────────────────────────────

class TestStripeStatusMapping:
    @pytest.mark.parametrize("stripe_status,expected", [
        ("active",             "active"),
        ("trialing",           "active"),
        ("past_due",           "past_due"),
        ("canceled",           "canceled"),
        ("cancelled",          "canceled"),
        ("incomplete",         "inactive"),
        ("incomplete_expired", "inactive"),
        ("unpaid",             "past_due"),
        ("paused",             "inactive"),
        ("unknown_future",     "inactive"),
    ])
    def test_status_mapping(self, stripe_status, expected):
        from src.services.subscription_webhook_service import _stripe_status
        assert _stripe_status(stripe_status) == expected
