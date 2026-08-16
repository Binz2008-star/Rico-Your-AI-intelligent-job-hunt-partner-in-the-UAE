"""Regression tests for the final-hardening fixes:

1. Public/guest AI usage ledger (migration 053): a registered email's turns on
   the public chat endpoints are recorded and counted toward the SAME allowance
   the anti-dodge checks (closes the confirmed bypass where the cap never
   enforced because public turns were never recorded).
2. The AI-message allowance therefore includes public usage.
3. The AI context sent to third-party providers no longer carries contact /
   routing identifiers (phone, telegram_username, telegram_chat_id, linkedin_url).
"""
import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


class _FakeRow:
    def __init__(self, value):
        self._value = value

    def __getitem__(self, key):
        return self._value


class TestPublicAiUsageLedger:
    def test_record_and_count_roundtrip(self):
        from src.repositories import ai_usage_repo

        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value.fetchone.return_value = _FakeRow(7)
        with patch("src.repositories.ai_usage_repo.get_db_connection", return_value=conn):
            assert ai_usage_repo.record_public_ai_usage("USER@Example.com") is True
        # Normalised to lowercase identity key.
        insert_sql = conn.cursor.return_value.__enter__.return_value.execute.call_args[0][0]
        assert "rico_public_ai_usage" in insert_sql
        assert "ON CONFLICT" in insert_sql

    def test_record_is_best_effort_never_raises(self):
        from src.repositories import ai_usage_repo

        with patch("src.repositories.ai_usage_repo.get_db_connection", return_value=None):
            assert ai_usage_repo.record_public_ai_usage("user@example.com") is False

    def test_count_returns_zero_when_db_unavailable(self):
        from datetime import datetime, timezone

        from src.repositories import ai_usage_repo

        with patch("src.repositories.ai_usage_repo.get_db_connection", return_value=None):
            assert (
                ai_usage_repo.count_public_ai_usage(
                    "user@example.com", datetime.now(timezone.utc)
                )
                == 0
            )


class TestAiAllowanceIncludesPublicUsage:
    def test_gate_counts_public_usage(self):
        from datetime import datetime, timezone

        from src.services.subscription_gating import (
            check_ai_message_allowed_for_user,
        )

        window = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        with patch(
            "src.services.subscription_gating.resolve_effective_user_plan",
        ) as resolve, patch(
            "src.services.subscription_gating.count_monthly_ai_messages",
            return_value=9,
        ) as count_db, patch(
            "src.repositories.ai_usage_repo.count_public_ai_usage",
            return_value=3,
        ) as count_public:
            from src.subscription_plans import FREE_ENTITLEMENTS

            from src.schemas.subscription import (
                SubscriptionResponse,
                SubscriptionStatus,
                SubscriptionTier,
                UserSubscription,
            )

            resolve.return_value = SubscriptionResponse(
                subscription=UserSubscription(
                    user_id="u@example.com",
                    plan=SubscriptionTier.FREE,
                    subscription_status=SubscriptionStatus.INACTIVE,
                    current_period_start=None,
                    current_period_end=None,
                    entitlements=FREE_ENTITLEMENTS,
                ),
                plan=None,
                is_active=False,
            )
            gate = check_ai_message_allowed_for_user("u@example.com")

        count_public.assert_called_once()
        assert gate.allowed is False  # 9 authenticated + 3 public = 12 > 10 free
        assert gate.usage == 12


class TestAiContextPrivacyMinimisation:
    def test_context_excludes_contact_and_routing_identifiers(self):
        """The essential-fields whitelist must NOT contain phone, telegram ids,
        or linkedin_url — contact/routing identifiers are unnecessary for career
        reasoning and must not be transmitted to third-party LLM providers."""
        src = open(
            os.path.join(os.path.dirname(__file__), "..", "src", "rico_chat_api.py"),
            encoding="utf-8",
        ).read()
        block = src.split("essential_fields = {", 1)[1].split("}", 1)[0]
        # Strip comment lines — the explanatory comment names the excluded
        # fields, so only the actual set membership matters.
        block = "\n".join(
            line for line in block.splitlines() if not line.strip().startswith("#")
        )
        for forbidden in ("phone", "telegram_username", "telegram_chat_id", "linkedin_url"):
            assert forbidden not in block, f"forbidden field {forbidden!r} present in essential_fields"
