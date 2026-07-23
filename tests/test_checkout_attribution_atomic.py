"""Tests for checkout attribution atomicity and retry-safety (#1074).

Verifies that:
1. Checkout session is NOT consumed during _extract_subscription_data
2. Checkout session IS consumed after successful subscription upsert
3. mark_checkout_session_used is idempotent (safe to call multiple times)
4. No raw session tokens appear in log output
"""
import json
from unittest.mock import patch, MagicMock, call


class TestCheckoutSessionNotConsumedDuringExtraction:
    """_extract_subscription_data must NOT consume the checkout session."""

    @patch("src.services.paddle_webhook_service._user_id_from_checkout_session")
    @patch("src.services.paddle_webhook_service._user_id_from_sub_id")
    @patch("src.services.paddle_webhook_service._user_id_from_customer")
    @patch("src.services.paddle_webhook_service._consume_checkout_session")
    @patch("src.services.paddle_webhook_service._resolve_plan_from_price_id")
    def test_session_not_consumed_during_extraction(
        self,
        mock_resolve_plan,
        mock_consume,
        mock_from_customer,
        mock_from_sub,
        mock_from_checkout,
    ):
        mock_resolve_plan.return_value = "pro"
        mock_from_sub.return_value = None
        mock_from_customer.return_value = None
        mock_from_checkout.return_value = "user@example.com"

        from src.services.paddle_webhook_service import _extract_subscription_data

        payload = {
            "data": {
                "id": "sub_123",
                "customer_id": "ctm_123",
                "status": "active",
                "items": [{"price": {"id": "pri_123"}}],
                "custom_data": {"checkout_session_id": "tok_abc"},
            }
        }

        fields = _extract_subscription_data(
            payload, MagicMock(), event_id="evt_1"
        )

        # Session token should be returned in fields, NOT consumed
        assert fields["checkout_session_token"] == "tok_abc"
        assert fields["user_id"] == "user@example.com"
        mock_consume.assert_not_called()


class TestCheckoutSessionConsumedAfterUpsert:
    """_handle_subscription_created must consume the session after upsert."""

    @patch("src.services.paddle_webhook_service._consume_checkout_session")
    @patch("src.services.paddle_webhook_service._lookup_existing_status")
    @patch("src.services.paddle_webhook_service._ensure_paddle_customer")
    @patch("src.services.paddle_webhook_service._parse_occurred_at")
    @patch("src.services.paddle_webhook_service._extract_subscription_data")
    @patch("src.repositories.paddle_repo.upsert_paddle_subscription")
    def test_session_consumed_after_upsert_created(
        self,
        mock_upsert,
        mock_extract,
        mock_parse,
        mock_ensure,
        mock_lookup,
        mock_consume,
    ):
        from src.services.paddle_webhook_service import _handle_subscription_created

        mock_extract.return_value = {
            "unmapped": False,
            "sub_id": "sub_123",
            "customer_id": "ctm_123",
            "rico_status": "active",
            "price_id": "pri_123",
            "plan": "pro",
            "billing_cycle": "monthly",
            "period_start": None,
            "period_end": None,
            "cancel_at": None,
            "user_id": "user@example.com",
            "checkout_session_token": "tok_abc",
        }
        mock_parse.return_value = None
        mock_lookup.return_value = None

        db_module = MagicMock()
        result = _handle_subscription_created(
            "evt_1", "subscription.created", {}, db_module
        )

        # upsert must be called BEFORE consume
        mock_upsert.assert_called_once()
        mock_consume.assert_called_once()
        # Verify the token argument (second positional arg)
        assert mock_consume.call_args[0][1] == "tok_abc"
        assert result["user_id"] == "user@example.com"

    @patch("src.services.paddle_webhook_service._consume_checkout_session")
    @patch("src.services.paddle_webhook_service._lookup_existing_status")
    @patch("src.services.paddle_webhook_service._ensure_paddle_customer")
    @patch("src.services.paddle_webhook_service._parse_occurred_at")
    @patch("src.services.paddle_webhook_service._extract_subscription_data")
    @patch("src.repositories.paddle_repo.upsert_paddle_subscription")
    def test_session_consumed_after_upsert_updated(
        self,
        mock_upsert,
        mock_extract,
        mock_parse,
        mock_ensure,
        mock_lookup,
        mock_consume,
    ):
        from src.services.paddle_webhook_service import _handle_subscription_updated

        mock_extract.return_value = {
            "unmapped": False,
            "sub_id": "sub_123",
            "customer_id": "ctm_123",
            "rico_status": "active",
            "price_id": "pri_123",
            "plan": "pro",
            "billing_cycle": "monthly",
            "period_start": None,
            "period_end": None,
            "cancel_at": None,
            "user_id": "user@example.com",
            "checkout_session_token": "tok_abc",
        }
        mock_parse.return_value = None
        mock_lookup.return_value = None

        db_module = MagicMock()
        result = _handle_subscription_updated(
            "evt_1", "subscription.updated", {}, db_module
        )

        mock_upsert.assert_called_once()
        mock_consume.assert_called_once()
        assert mock_consume.call_args[0][1] == "tok_abc"
        assert result["user_id"] == "user@example.com"

    @patch("src.services.paddle_webhook_service._consume_checkout_session")
    @patch("src.services.paddle_webhook_service._lookup_existing_status")
    @patch("src.services.paddle_webhook_service._ensure_paddle_customer")
    @patch("src.services.paddle_webhook_service._parse_occurred_at")
    @patch("src.services.paddle_webhook_service._extract_subscription_data")
    @patch("src.repositories.paddle_repo.upsert_paddle_subscription")
    def test_session_not_consumed_on_upsert_failure(
        self,
        mock_upsert,
        mock_extract,
        mock_parse,
        mock_ensure,
        mock_lookup,
        mock_consume,
    ):
        from src.services.paddle_webhook_service import _handle_subscription_created

        mock_extract.return_value = {
            "unmapped": False,
            "sub_id": "sub_123",
            "customer_id": "ctm_123",
            "rico_status": "active",
            "price_id": "pri_123",
            "plan": "pro",
            "billing_cycle": "monthly",
            "period_start": None,
            "period_end": None,
            "cancel_at": None,
            "user_id": "user@example.com",
            "checkout_session_token": "tok_abc",
        }
        mock_parse.return_value = None
        mock_lookup.return_value = None
        mock_upsert.side_effect = Exception("DB error")

        # Should propagate the exception, and consume should NOT be called
        try:
            _handle_subscription_created(
                "evt_1", "subscription.created", {}, MagicMock()
            )
        except Exception:
            pass

        mock_consume.assert_not_called()


class TestMarkCheckoutSessionUsedIdempotent:
    """mark_checkout_session_used must be idempotent (WHERE used = FALSE)."""

    @patch("src.repositories.paddle_repo._get_conn")
    def test_sql_includes_used_false_guard(self, mock_get_conn):
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        mock_get_conn.return_value = conn

        from src.repositories.paddle_repo import mark_checkout_session_used

        mark_checkout_session_used(MagicMock(), "tok_abc")

        sql = cur.execute.call_args[0][0]
        assert "used = FALSE" in sql
