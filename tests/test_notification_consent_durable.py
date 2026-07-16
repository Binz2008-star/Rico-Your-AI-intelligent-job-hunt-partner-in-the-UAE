"""
Notification consent writes are DB-mandatory (#1082 P0).

opt_in/opt_out for Telegram and email must persist consent durably: they pass
require_db=True to upsert_profile, so a swallowed DB failure surfaces as a False
return (→ HTTP 500 at the settings router) instead of a false success that would
leave the persisted roster opted-in and the user still reachable by a later
worker. All DB calls are mocked — no real database.
"""
from __future__ import annotations

from unittest.mock import patch


class TestTelegramConsentDurable:
    def test_opt_in_passes_require_db(self):
        from src.services import telegram_notifications as tn

        with patch.object(tn, "upsert_profile") as mock_upsert:
            assert tn.opt_in("u@example.com", telegram_chat_id="123") is True
        assert mock_upsert.call_args.kwargs.get("require_db") is True

    def test_opt_out_passes_require_db(self):
        from src.services import telegram_notifications as tn

        with patch.object(tn, "upsert_profile") as mock_upsert:
            assert tn.opt_out("u@example.com") is True
        assert mock_upsert.call_args.kwargs.get("require_db") is True

    def test_opt_out_returns_false_when_persistence_fails(self):
        from src.services import telegram_notifications as tn

        with patch.object(
            tn, "upsert_profile", side_effect=RuntimeError("profile DB unavailable (require_db)")
        ):
            assert tn.opt_out("u@example.com") is False


class TestEmailConsentDurable:
    def test_opt_in_passes_require_db(self):
        from src.services import email_notifications as en

        with patch.object(en, "upsert_profile") as mock_upsert, patch.object(
            en, "ensure_unsubscribe_token", return_value=None
        ):
            assert en.opt_in("u@example.com", frequency="daily") is True
        assert mock_upsert.call_args.kwargs.get("require_db") is True

    def test_opt_out_passes_require_db(self):
        from src.services import email_notifications as en

        with patch.object(en, "upsert_profile") as mock_upsert:
            assert en.opt_out("u@example.com") is True
        assert mock_upsert.call_args.kwargs.get("require_db") is True

    def test_opt_out_returns_false_when_persistence_fails(self):
        from src.services import email_notifications as en

        with patch.object(
            en, "upsert_profile", side_effect=RuntimeError("profile DB unavailable (require_db)")
        ):
            assert en.opt_out("u@example.com") is False
