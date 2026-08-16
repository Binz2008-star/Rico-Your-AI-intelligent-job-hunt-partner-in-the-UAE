"""Unit regression tests for launch-blocker closure items that need no DB.

Covers: API-docs production gating, the native-Telegram bounded AI allowance,
Telegram bind-code detection, and the Jotform merge → confirmation interception
(the write-into-existing-account path must be closed).
"""
import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


class TestApiDocsGating:
    def test_docs_disabled_in_production_by_default(self, monkeypatch):
        from src.api import app as app_module

        monkeypatch.setattr(app_module, "_is_production_deploy", lambda: True)
        monkeypatch.delenv("RICO_ENABLE_API_DOCS", raising=False)
        assert app_module._docs_enabled() is False

    def test_docs_enabled_in_non_production(self, monkeypatch):
        from src.api import app as app_module

        monkeypatch.setattr(app_module, "_is_production_deploy", lambda: False)
        assert app_module._docs_enabled() is True

    def test_docs_explicitly_enabled_in_production(self, monkeypatch):
        from src.api import app as app_module

        monkeypatch.setattr(app_module, "_is_production_deploy", lambda: True)
        monkeypatch.setenv("RICO_ENABLE_API_DOCS", "true")
        assert app_module._docs_enabled() is True

    def test_dev_app_serves_openapi(self):
        # In the current (non-production) test environment the docs are on.
        from src.api.app import app

        assert app.openapi_url == "/api/openapi.json"


class TestNativeTelegramGate:
    def test_below_limit_allowed_and_recorded(self):
        from src.rico_telegram_webhook import _gate_native_telegram

        with patch(
            "src.repositories.ai_usage_repo.count_public_ai_usage_strict",
            return_value=9,
        ) as count, patch(
            "src.repositories.ai_usage_repo.record_public_ai_usage"
        ) as record:
            reply = _gate_native_telegram("chat-123")
        assert reply is None  # allowed
        count.assert_called_once()
        record.assert_called_once()

    def test_at_limit_denied(self):
        from src.rico_telegram_webhook import _gate_native_telegram

        with patch(
            "src.repositories.ai_usage_repo.count_public_ai_usage_strict",
            return_value=10,
        ):
            reply = _gate_native_telegram("chat-123")
        assert reply is not None
        assert "limit" in reply

    def test_db_failure_fails_closed(self):
        from src.rico_telegram_webhook import _gate_native_telegram

        with patch(
            "src.repositories.ai_usage_repo.count_public_ai_usage_strict",
            side_effect=RuntimeError("db down"),
        ):
            reply = _gate_native_telegram("chat-123")
        assert reply is not None
        assert "unavailable" in reply


class TestTelegramBindCode:
    def test_code_shape_detected(self):
        from src.rico_telegram_webhook import _looks_like_bind_code

        assert _looks_like_bind_code("A" * 43) is True
        assert _looks_like_bind_code("abcDEF_-" * 5 + "abc") is True
        assert _looks_like_bind_code("hello") is False
        assert _looks_like_bind_code("A" * 42) is False

    def test_code_reply_binds_account_and_verifies_chat(self):
        from src.rico_telegram_webhook import _handle_bind_code_reply

        code = "A" * 43
        with patch(
            "src.services.account_confirmation_service.resolve_telegram_bind_code",
            return_value="owner@example.com",
        ) as resolve, patch(
            "src.rico_telegram_webhook.upsert_profile"
        ) as upsert, patch(
            "src.rico_telegram_webhook.send_telegram_to_user"
        ) as send:
            result = _handle_bind_code_reply(code, "chat-123")
        resolve.assert_called_once_with(code, "chat-123")
        upsert.assert_called_once()
        send.assert_called_once()
        assert result is not None

    def test_wrong_chat_code_does_not_bind(self):
        from src.rico_telegram_webhook import _handle_bind_code_reply

        code = "A" * 43
        with patch(
            "src.services.account_confirmation_service.resolve_telegram_bind_code",
            return_value=None,
        ) as resolve, patch("src.rico_telegram_webhook.upsert_profile") as upsert:
            assert _handle_bind_code_reply(code, "chat-123") is None
        upsert.assert_not_called()


class TestJotformMergeRequiresConfirmation:
    def _payload(self, email="test@example.com"):
        return {
            "formID": "261278237812056",
            "submissionID": "sub_conf_1",
            "pretty": {
                "email": email,
                "full_name": "Test User",
                "target_roles": "HSE Manager",
                "preferred_cities": "Dubai",
                "consent": "true",
            },
        }

    def test_merge_returns_confirmation_required_and_never_writes(self):
        from src.rico_jotform_webhook import handle_jotform_submission

        candidate = MagicMock()
        candidate.user_id = "test@example.com"
        resolution = MagicMock()
        resolution.action = "merge"
        resolution.matched_user_id = "test@example.com"
        resolution.confidence = 0.95
        resolution.reasons = ["email"]
        resolution.conflicts = {}
        resolution.missing_fields = []

        with patch(
            "src.rico_jotform_webhook._active_form_ids", return_value=frozenset({"261278237812056"})
        ), patch(
            "src.rico_jotform_webhook._validate_webhook_secret", return_value=True
        ), patch(
            "src.rico_jotform_webhook.find_identity_candidates",
            return_value=[candidate],
        ), patch(
            "src.rico_jotform_webhook.map_identity_flow",
            return_value=resolution,
        ), patch(
            "src.rico_jotform_webhook.RicoDB",
        ) as MockDB, patch(
            "src.services.account_confirmation_service.create_jotform_merge_confirmation",
            return_value=True,
        ) as create_confirm:
            db = MockDB.return_value
            db._transaction.return_value.__enter__.return_value = MagicMock()
            db.register_webhook_event.return_value = True

            result = handle_jotform_submission(self._payload())

        assert result["reason"] == "confirmation_required"
        create_confirm.assert_called_once()
        # The merge payload must NOT include a write: upsert_user/upsert_profile
        # are never invoked on the matched account.
        MockDB.return_value.upsert_user.assert_not_called()
        MockDB.return_value.upsert_profile.assert_not_called()

    def test_confirmation_dispatch_failure_fails_closed(self):
        from fastapi import HTTPException

        from src.rico_jotform_webhook import handle_jotform_submission

        candidate = MagicMock()
        candidate.user_id = "test@example.com"
        resolution = MagicMock()
        resolution.action = "merge"
        resolution.matched_user_id = "test@example.com"
        resolution.confidence = 0.95
        resolution.reasons = ["email"]
        resolution.conflicts = {}
        resolution.missing_fields = []

        with patch(
            "src.rico_jotform_webhook._active_form_ids", return_value=frozenset({"261278237812056"})
        ), patch(
            "src.rico_jotform_webhook._validate_webhook_secret", return_value=True
        ), patch(
            "src.rico_jotform_webhook.find_identity_candidates",
            return_value=[candidate],
        ), patch(
            "src.rico_jotform_webhook.map_identity_flow",
            return_value=resolution,
        ), patch(
            "src.rico_jotform_webhook.RicoDB",
        ), patch(
            "src.services.account_confirmation_service.create_jotform_merge_confirmation",
            return_value=False,
        ):
            with pytest.raises(RuntimeError, match="dispatch_failed"):
                handle_jotform_submission(self._payload())
