"""Tests for subscription_webhook_service — Paddle event processing.

All DB calls are mocked. No live Paddle, Render, or Neon required.
Idempotency gate (record_subscription_event) is patched at the service level.

Fixture payloads mirror real Paddle Billing webhook "data" object shapes
(simplified but structurally correct) so handlers exercise realistic code paths.
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
_GET_CUS       = f"{_SVC}.get_subscription_by_paddle_customer"
_GET_EVENT_STATUS = f"{_SVC}.get_subscription_event_status"


# ── Autouse: silence update_subscription_event_status in all tests ────────────
# process_paddle_event now calls update_subscription_event_status after every
# handler. Tests that don't explicitly care about the status update get a no-op
# via this autouse fixture so they don't need to patch it individually.

@pytest.fixture(autouse=True)
def _noop_update_status(monkeypatch):
    import src.services.subscription_webhook_service as svc
    monkeypatch.setattr(svc, "update_subscription_event_status", lambda *a, **kw: True)


# ── Paddle event payload builders ─────────────────────────────────────────────
# Paddle's webhook envelope is {event_id, event_type, data}; "data" is the
# object directly (no nested "object" wrapper like Stripe).

def _transaction_completed_event(
    user_id="alice@rico.ai",
    plan="pro",
    customer="ctm_test",
    subscription="sub_test",
):
    return {
        "data": {
            "customer_id": customer,
            "subscription_id": subscription,
            "custom_data": {"user_id": user_id, "plan": plan},
        }
    }


def _subscription_event(
    user_id="alice@rico.ai",
    plan="pro",
    status="active",
    customer="ctm_test",
    sub_id="sub_test",
    period_start="2024-05-18T00:00:00Z",
    period_end="2024-06-17T00:00:00Z",
    price_id=None,
):
    items = []
    if price_id:
        items = [{"price": {"id": price_id}}]
    return {
        "data": {
            "id": sub_id,
            "customer_id": customer,
            "status": status,
            "custom_data": {"user_id": user_id, "plan": plan},
            "items": items,
            "current_billing_period": {"starts_at": period_start, "ends_at": period_end},
        }
    }


def _canceled_event(user_id="alice@rico.ai", customer="ctm_test", sub_id="sub_test"):
    return {
        "data": {
            "id": sub_id,
            "customer_id": customer,
            "status": "canceled",
            "custom_data": {"user_id": user_id},
        }
    }


def _payment_failed_event(customer="ctm_test", subscription="sub_test"):
    return {
        "data": {
            "customer_id": customer,
            "subscription_id": subscription,
        }
    }


def _existing_row(user_id="alice@rico.ai", plan="pro", status="active"):
    return {
        "user_id": user_id, "plan": plan, "status": status,
        "paddle_customer_id": "ctm_test", "paddle_subscription_id": "sub_test",
        "current_period_start": None, "current_period_end": None,
    }


# ── Idempotency ───────────────────────────────────────────────────────────────

class TestIdempotency:
    def test_processed_duplicate_skips_all_processing(self):
        from src.services.subscription_webhook_service import process_paddle_event
        with patch(_RECORD, return_value=False) as mock_record, \
             patch(_GET_EVENT_STATUS, return_value="processed"), \
             patch(_UPSERT) as mock_upsert:
            result = process_paddle_event(
                "evt_dup", "transaction.completed", _transaction_completed_event()
            )
        assert result is True
        mock_upsert.assert_not_called()

    def test_unhandled_event_type_is_claimed_and_acknowledged(self):
        from src.services.subscription_webhook_service import process_paddle_event
        with patch(_RECORD, return_value=True), patch(_UPSERT) as mock_upsert:
            result = process_paddle_event("evt_x", "adjustment.created", {"data": {}})
        assert result is True
        mock_upsert.assert_not_called()

    def test_record_called_with_correct_args(self):
        from src.services.subscription_webhook_service import process_paddle_event
        with patch(_RECORD, return_value=True) as mock_record, \
             patch(_UPSERT, return_value=_existing_row()):
            process_paddle_event("evt_1", "transaction.completed", _transaction_completed_event())
        mock_record.assert_called_once_with(
            "evt_1",
            "transaction.completed",
            user_id="alice@rico.ai",
            payload=_transaction_completed_event(),
        )


# ── transaction.completed ─────────────────────────────────────────────────────

class TestTransactionCompleted:
    def test_creates_active_pro_subscription(self):
        from src.services.subscription_webhook_service import process_paddle_event
        with patch(_RECORD, return_value=True), \
             patch(_UPSERT, return_value=_existing_row()) as mock_upsert:
            result = process_paddle_event(
                "evt_tx_1", "transaction.completed", _transaction_completed_event(plan="pro")
            )
        assert result is True
        mock_upsert.assert_called_once()
        kw = mock_upsert.call_args
        assert kw.args[0] == "alice@rico.ai"
        assert kw.kwargs["plan"] == "pro"
        assert kw.kwargs["status"] == "active"
        assert kw.kwargs["paddle_customer_id"] == "ctm_test"
        assert kw.kwargs["paddle_subscription_id"] == "sub_test"
        assert "monthly_ai_message_limit" not in kw.kwargs
        assert "saved_jobs_limit" not in kw.kwargs
        assert "premium_recommendations_enabled" not in kw.kwargs

    def test_creates_active_premium_subscription(self):
        from src.services.subscription_webhook_service import process_paddle_event
        with patch(_RECORD, return_value=True), \
             patch(_UPSERT, return_value=_existing_row(plan="premium")) as mock_upsert:
            result = process_paddle_event(
                "evt_tx_2", "transaction.completed", _transaction_completed_event(plan="premium")
            )
        assert result is True
        args = mock_upsert.call_args
        assert args.kwargs["plan"] == "premium"
        assert args.kwargs["status"] == "active"

    def test_skips_when_user_id_missing(self):
        from src.services.subscription_webhook_service import process_paddle_event
        data = {"data": {"customer_id": "ctm_x", "custom_data": {}}}
        with patch(_RECORD, return_value=True), \
             patch(_GET_CUS, return_value=None), \
             patch(_UPSERT) as mock_upsert:
            result = process_paddle_event("evt_tx_3", "transaction.completed", data)
        assert result is False
        mock_upsert.assert_not_called()

    def test_skips_when_plan_unknown(self):
        from src.services.subscription_webhook_service import process_paddle_event
        data = _transaction_completed_event(plan="enterprise")
        with patch(_RECORD, return_value=True), \
             patch(_GET_CUS, return_value=None), \
             patch(_UPSERT) as mock_upsert:
            result = process_paddle_event("evt_tx_4", "transaction.completed", data)
        assert result is False
        mock_upsert.assert_not_called()

    def test_falls_back_to_price_id_when_custom_data_plan_missing(self, monkeypatch):
        from src.services.subscription_webhook_service import process_paddle_event
        monkeypatch.setenv("PADDLE_PRO_PRICE_ID", "pri_pro_live")
        data = {
            "data": {
                "customer_id": "ctm_test",
                "subscription_id": "sub_test",
                "custom_data": {"user_id": "alice@rico.ai"},
                "items": [{"price": {"id": "pri_pro_live"}}],
            }
        }
        with patch(_RECORD, return_value=True), \
             patch(_UPSERT, return_value=_existing_row()) as mock_upsert:
            result = process_paddle_event("evt_tx_5", "transaction.completed", data)
        assert result is True
        assert mock_upsert.call_args.kwargs["plan"] == "pro"

    def test_falls_back_to_existing_customer_and_plan_on_renewal_without_custom_data(self):
        """Recurring renewal transactions may arrive with empty custom_data; the
        handler must still resolve the user via the customer lookup and reuse
        the plan already on file rather than dropping the event."""
        from src.services.subscription_webhook_service import process_paddle_event
        data = {
            "data": {
                "customer_id": "ctm_test",
                "subscription_id": "sub_test",
                "custom_data": {},
            }
        }
        with patch(_RECORD, return_value=True), \
             patch(_GET_CUS, return_value=_existing_row(plan="premium")), \
             patch(_UPSERT, return_value=_existing_row(plan="premium")) as mock_upsert:
            result = process_paddle_event("evt_tx_renewal", "transaction.completed", data)
        assert result is True
        kwargs = mock_upsert.call_args.kwargs
        assert kwargs["plan"] == "premium"
        assert kwargs["status"] == "active"

    def test_skips_renewal_when_customer_unresolvable(self):
        from src.services.subscription_webhook_service import process_paddle_event
        data = {
            "data": {
                "customer_id": "ctm_unknown",
                "subscription_id": "sub_test",
                "custom_data": {},
            }
        }
        with patch(_RECORD, return_value=True), \
             patch(_GET_CUS, return_value=None), \
             patch(_UPSERT) as mock_upsert:
            result = process_paddle_event("evt_tx_renewal_2", "transaction.completed", data)
        assert result is False
        mock_upsert.assert_not_called()


# ── subscription.created / .updated ──────────────────────────────────────────

class TestSubscriptionUpsert:
    def test_subscription_created_active(self):
        from src.services.subscription_webhook_service import process_paddle_event
        with patch(_RECORD, return_value=True), \
             patch(_UPSERT, return_value=_existing_row()) as mock_upsert:
            result = process_paddle_event(
                "evt_su_1", "subscription.created",
                _subscription_event(plan="pro", status="active"),
            )
        assert result is True
        kwargs = mock_upsert.call_args.kwargs
        assert kwargs["plan"] == "pro"
        assert kwargs["status"] == "active"
        assert kwargs["paddle_customer_id"] == "ctm_test"

    def test_subscription_updated_to_past_due(self):
        from src.services.subscription_webhook_service import process_paddle_event
        with patch(_RECORD, return_value=True), \
             patch(_UPSERT, return_value=_existing_row(status="past_due")) as mock_upsert:
            result = process_paddle_event(
                "evt_su_2", "subscription.updated",
                _subscription_event(status="past_due"),
            )
        assert result is True
        assert mock_upsert.call_args.kwargs["status"] == "past_due"

    def test_trialing_maps_to_active(self):
        from src.services.subscription_webhook_service import process_paddle_event
        with patch(_RECORD, return_value=True), \
             patch(_UPSERT, return_value=_existing_row()) as mock_upsert:
            process_paddle_event(
                "evt_su_3", "subscription.updated",
                _subscription_event(status="trialing"),
            )
        assert mock_upsert.call_args.kwargs["status"] == "active"

    def test_period_timestamps_converted(self):
        from src.services.subscription_webhook_service import process_paddle_event
        from datetime import datetime, timezone
        with patch(_RECORD, return_value=True), \
             patch(_UPSERT, return_value=_existing_row()) as mock_upsert:
            process_paddle_event(
                "evt_su_4", "subscription.updated",
                _subscription_event(
                    period_start="2024-05-18T00:00:00Z",
                    period_end="2024-06-17T00:00:00Z",
                ),
            )
        kwargs = mock_upsert.call_args.kwargs
        assert kwargs["current_period_start"] == datetime(2024, 5, 18, tzinfo=timezone.utc)
        assert kwargs["current_period_end"] == datetime(2024, 6, 17, tzinfo=timezone.utc)

    def test_falls_back_to_price_id_when_custom_data_plan_missing(self, monkeypatch):
        from src.services.subscription_webhook_service import process_paddle_event
        monkeypatch.setenv("PADDLE_PRO_PRICE_ID", "pri_pro_live")
        data = {
            "data": {
                "id": "sub_test",
                "customer_id": "ctm_test",
                "status": "active",
                "custom_data": {"user_id": "alice@rico.ai"},
                "items": [{"price": {"id": "pri_pro_live"}}],
                "current_billing_period": None,
            }
        }
        with patch(_RECORD, return_value=True), \
             patch(_UPSERT, return_value=_existing_row()) as mock_upsert:
            result = process_paddle_event("evt_su_5", "subscription.updated", data)
        assert result is True
        assert mock_upsert.call_args.kwargs["plan"] == "pro"

    def test_prefers_price_id_over_stale_custom_data_plan(self, monkeypatch):
        from src.services.subscription_webhook_service import process_paddle_event
        monkeypatch.setenv("PADDLE_PREMIUM_PRICE_ID", "pri_premium_live")
        data = _subscription_event(plan="pro", price_id="pri_premium_live")
        with patch(_RECORD, return_value=True), \
             patch(_UPSERT, return_value=_existing_row(plan="premium")) as mock_upsert:
            result = process_paddle_event("evt_su_price", "subscription.updated", data)
        assert result is True
        assert mock_upsert.call_args.kwargs["plan"] == "premium"

    def test_falls_back_to_customer_lookup_when_custom_data_user_id_missing(self):
        from src.services.subscription_webhook_service import process_paddle_event
        data = {
            "data": {
                "id": "sub_test",
                "customer_id": "ctm_test",
                "status": "active",
                "custom_data": {"plan": "pro"},
                "items": [],
                "current_billing_period": None,
            }
        }
        with patch(_RECORD, return_value=True), \
             patch(_GET_CUS, return_value=_existing_row()), \
             patch(_UPSERT, return_value=_existing_row()) as mock_upsert:
            result = process_paddle_event("evt_su_6", "subscription.updated", data)
        assert result is True
        assert mock_upsert.call_args.args[0] == "alice@rico.ai"

    def test_skips_when_user_id_unresolvable(self):
        from src.services.subscription_webhook_service import process_paddle_event
        data = {
            "data": {
                "id": "sub_test",
                "customer_id": "ctm_unknown",
                "status": "active",
                "custom_data": {},
                "items": [],
                "current_billing_period": None,
            }
        }
        with patch(_RECORD, return_value=True), \
             patch(_GET_CUS, return_value=None), \
             patch(_UPSERT) as mock_upsert:
            result = process_paddle_event("evt_su_7", "subscription.updated", data)
        assert result is False
        mock_upsert.assert_not_called()


# ── subscription.canceled ─────────────────────────────────────────────────────

class TestSubscriptionCanceled:
    def test_sets_canceled_preserving_plan(self):
        from src.services.subscription_webhook_service import process_paddle_event
        with patch(_RECORD, return_value=True), \
             patch(_GET_SUB, return_value=_existing_row(plan="premium")), \
             patch(_UPSERT, return_value=_existing_row(status="canceled")) as mock_upsert:
            result = process_paddle_event(
                "evt_del_1", "subscription.canceled", _canceled_event()
            )
        assert result is True
        kwargs = mock_upsert.call_args.kwargs
        assert kwargs["status"] == "canceled"
        assert kwargs["plan"] == "premium"
        assert "monthly_ai_message_limit" not in kwargs
        assert "premium_recommendations_enabled" not in kwargs

    def test_uses_free_plan_when_no_existing_subscription(self):
        from src.services.subscription_webhook_service import process_paddle_event
        with patch(_RECORD, return_value=True), \
             patch(_GET_SUB, return_value=None), \
             patch(_UPSERT) as mock_upsert:
            process_paddle_event("evt_del_2", "subscription.canceled", _canceled_event())
        assert mock_upsert.call_args.kwargs["plan"] == "free"

    def test_skips_when_user_id_unresolvable(self):
        from src.services.subscription_webhook_service import process_paddle_event
        data = {"data": {"customer_id": "ctm_unknown", "custom_data": {}}}
        with patch(_RECORD, return_value=True), \
             patch(_GET_CUS, return_value=None), \
             patch(_UPSERT) as mock_upsert:
            result = process_paddle_event("evt_del_3", "subscription.canceled", data)
        assert result is False
        mock_upsert.assert_not_called()


# ── transaction.payment_failed ────────────────────────────────────────────────

class TestTransactionPaymentFailed:
    def test_sets_past_due(self):
        from src.services.subscription_webhook_service import process_paddle_event
        with patch(_RECORD, return_value=True), \
             patch(_GET_CUS, return_value=_existing_row(plan="premium")), \
             patch(_UPSERT, return_value=_existing_row(status="past_due")) as mock_upsert:
            result = process_paddle_event(
                "evt_fail_1", "transaction.payment_failed", _payment_failed_event()
            )
        assert result is True
        kwargs = mock_upsert.call_args.kwargs
        assert kwargs["status"] == "past_due"
        assert kwargs["plan"] == "premium"

    def test_skips_when_no_subscription_found(self):
        from src.services.subscription_webhook_service import process_paddle_event
        with patch(_RECORD, return_value=True), \
             patch(_GET_CUS, return_value=None), \
             patch(_UPSERT) as mock_upsert:
            result = process_paddle_event("evt_fail_2", "transaction.payment_failed", _payment_failed_event())
        assert result is True  # permanent skip returns True to prevent Paddle retry storm
        mock_upsert.assert_not_called()

    def test_ignores_failure_for_different_subscription(self):
        from src.services.subscription_webhook_service import process_paddle_event
        with patch(_RECORD, return_value=True), \
             patch(_GET_CUS, return_value=_existing_row()), \
             patch(_UPSERT) as mock_upsert:
            result = process_paddle_event(
                "evt_fail_other", "transaction.payment_failed",
                _payment_failed_event(subscription="sub_other"),
            )
        assert result is True
        mock_upsert.assert_not_called()

    def test_skips_when_customer_missing(self):
        from src.services.subscription_webhook_service import process_paddle_event
        with patch(_RECORD, return_value=True), patch(_UPSERT) as mock_upsert:
            result = process_paddle_event("evt_fail_3", "transaction.payment_failed", {"data": {}})
        assert result is False
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

        result = svc.process_paddle_event(
            "evt_crash", "transaction.completed",
            {"data": {"custom_data": {"user_id": "u@t.com", "plan": "pro"},
                      "customer_id": "ctm_1", "subscription_id": "sub_1"}},
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

        result = svc.process_paddle_event(
            "evt_ok", "transaction.completed",
            {"data": {"custom_data": {"user_id": "u@t.com", "plan": "pro"},
                      "customer_id": "ctm_1", "subscription_id": "sub_1"}},
        )

        assert result is True
        assert status_updates == [("evt_ok", "processed", {})]

    def test_handler_success_returns_false_when_processed_status_update_fails(self, monkeypatch):
        import src.services.subscription_webhook_service as svc
        monkeypatch.setattr(svc, "record_subscription_event", lambda *a, **kw: True)
        monkeypatch.setattr(svc, "update_subscription_event_status", lambda *a, **kw: False)
        monkeypatch.setattr(svc, "upsert_subscription", lambda *a, **kw: _existing_row())
        monkeypatch.setattr(svc, "get_subscription_by_paddle_customer", lambda *a, **kw: None)

        result = svc.process_paddle_event(
            "evt_status_fail", "transaction.completed",
            {"data": {"custom_data": {"user_id": "u@t.com", "plan": "pro"},
                      "customer_id": "ctm_1", "subscription_id": "sub_1"}},
        )

        assert result is False

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

        result = svc.process_paddle_event(
            "evt_write_fail", "transaction.completed",
            {"data": {"custom_data": {"user_id": "u@t.com", "plan": "pro"},
                      "customer_id": "ctm_1", "subscription_id": "sub_1"}},
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

        result = svc.process_paddle_event("evt_unk", "adjustment.created", {"data": {}})

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

        result = svc.process_paddle_event("evt_dup", "transaction.completed", _transaction_completed_event())

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

        result = svc.process_paddle_event("evt_pending", "transaction.completed", _transaction_completed_event())

        assert result is True
        assert status_updates == []
        svc.upsert_subscription.assert_not_called()

    def test_failed_unclaimed_event_remains_retryable(self, monkeypatch):
        import src.services.subscription_webhook_service as svc
        monkeypatch.setattr(svc, "record_subscription_event", lambda *a, **kw: False)
        monkeypatch.setattr(svc, "get_subscription_event_status", lambda *a, **kw: "failed")
        monkeypatch.setattr(svc, "upsert_subscription", MagicMock())

        result = svc.process_paddle_event("evt_failed", "transaction.completed", _transaction_completed_event())

        assert result is False
        svc.upsert_subscription.assert_not_called()

    def test_missing_or_db_error_unclaimed_event_returns_false(self, monkeypatch):
        import src.services.subscription_webhook_service as svc
        monkeypatch.setattr(svc, "record_subscription_event", lambda *a, **kw: False)
        monkeypatch.setattr(svc, "get_subscription_event_status", lambda *a, **kw: None)
        monkeypatch.setattr(svc, "upsert_subscription", MagicMock())

        result = svc.process_paddle_event("evt_missing", "transaction.completed", _transaction_completed_event())

        assert result is False
        svc.upsert_subscription.assert_not_called()


# ── _price_id_to_plan unit tests ──────────────────────────────────────────────

class TestPriceIdMapping:
    def test_maps_pro_env(self, monkeypatch):
        from src.services.subscription_webhook_service import _price_id_to_plan
        monkeypatch.setenv("PADDLE_PRO_PRICE_ID", "pri_pro_123")
        assert _price_id_to_plan("pri_pro_123") == "pro"

    def test_maps_premium_env(self, monkeypatch):
        from src.services.subscription_webhook_service import _price_id_to_plan
        monkeypatch.setenv("PADDLE_PREMIUM_PRICE_ID", "pri_prem_123")
        assert _price_id_to_plan("pri_prem_123") == "premium"

    def test_unknown_price_id_returns_none(self, monkeypatch):
        from src.services.subscription_webhook_service import _price_id_to_plan
        monkeypatch.delenv("PADDLE_PRO_PRICE_ID", raising=False)
        monkeypatch.delenv("PADDLE_PREMIUM_PRICE_ID", raising=False)
        assert _price_id_to_plan("pri_unknown") is None

    def test_empty_price_id_returns_none(self):
        from src.services.subscription_webhook_service import _price_id_to_plan
        assert _price_id_to_plan("") is None


# ── Paddle status mapping ─────────────────────────────────────────────────────

class TestPaddleStatusMapping:
    @pytest.mark.parametrize("paddle_status,expected", [
        ("active",         "active"),
        ("trialing",       "active"),
        ("past_due",       "past_due"),
        ("paused",         "inactive"),
        ("canceled",       "canceled"),
        ("unknown_future", "inactive"),
    ])
    def test_status_mapping(self, paddle_status, expected):
        from src.services.subscription_webhook_service import _paddle_status
        assert _paddle_status(paddle_status) == expected
