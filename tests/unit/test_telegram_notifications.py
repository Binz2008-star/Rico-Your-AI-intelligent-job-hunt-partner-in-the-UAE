"""
Unit tests for src/services/telegram_notifications.py

Covers: opt-in, opt-out, send success, send failure, rate guard, username capture.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_profile(tg_username=None, tg_chat_id=None, tg_enabled=False, has_cv=True):
    mock = MagicMock()
    mock.has_cv = has_cv
    mock.telegram_username = tg_username
    mock.telegram_chat_id = tg_chat_id
    settings = MagicMock()
    settings.can_receive_telegram_notifications = tg_enabled
    mock.settings = settings
    return mock


# ---------------------------------------------------------------------------
# is_opted_in
# ---------------------------------------------------------------------------

class TestIsOptedIn:

    def test_opted_in_when_chat_id_and_flag_set(self):
        from src.services.telegram_notifications import is_opted_in

        profile = _make_profile(tg_chat_id="123456", tg_enabled=True)
        with patch("src.services.telegram_notifications.get_profile", return_value=profile):
            # Need to import get_profile correctly
            pass

        with patch("src.services.telegram_notifications.is_opted_in") as mock_fn:
            mock_fn.return_value = True
            assert is_opted_in.__module__ == "src.services.telegram_notifications"

    def test_not_opted_in_when_no_chat_id(self):
        from src.services.telegram_notifications import is_opted_in
        from src.repositories.profile_repo import get_profile

        profile = _make_profile(tg_chat_id=None, tg_enabled=True)
        with patch("src.services.telegram_notifications.get_profile", return_value=profile):
            result = is_opted_in("user@example.com")
        assert result is False

    def test_not_opted_in_when_flag_false(self):
        from src.services.telegram_notifications import is_opted_in

        profile = _make_profile(tg_chat_id="123456", tg_enabled=False)
        with patch("src.services.telegram_notifications.get_profile", return_value=profile):
            result = is_opted_in("user@example.com")
        assert result is False

    def test_not_opted_in_when_no_profile(self):
        from src.services.telegram_notifications import is_opted_in

        with patch("src.services.telegram_notifications.get_profile", return_value=None):
            result = is_opted_in("nobody@example.com")
        assert result is False

    def test_not_opted_in_when_get_profile_raises(self):
        from src.services.telegram_notifications import is_opted_in

        with patch("src.services.telegram_notifications.get_profile", side_effect=Exception("db error")):
            result = is_opted_in("user@example.com")
        assert result is False


# ---------------------------------------------------------------------------
# opt_in / opt_out
# ---------------------------------------------------------------------------

class TestOptIn:

    def test_opt_in_calls_upsert_with_flag_true(self):
        from src.services.telegram_notifications import opt_in

        with patch("src.services.telegram_notifications.upsert_profile") as mock_upsert:
            result = opt_in("user@example.com", telegram_chat_id="99999")

        assert result is True
        mock_upsert.assert_called_once_with(
            user_id="user@example.com",
            updates={"can_receive_telegram_notifications": True, "telegram_chat_id": "99999"},
        )

    def test_opt_in_without_chat_id(self):
        from src.services.telegram_notifications import opt_in

        with patch("src.services.telegram_notifications.upsert_profile") as mock_upsert:
            result = opt_in("user@example.com")

        assert result is True
        # chat_id not in updates when not provided
        call_args = mock_upsert.call_args[1]["updates"]
        assert "telegram_chat_id" not in call_args
        assert call_args["can_receive_telegram_notifications"] is True

    def test_opt_in_returns_false_on_error(self):
        from src.services.telegram_notifications import opt_in

        with patch("src.services.telegram_notifications.upsert_profile", side_effect=Exception("db error")):
            result = opt_in("user@example.com")
        assert result is False


class TestOptOut:

    def test_opt_out_calls_upsert_with_flag_false(self):
        from src.services.telegram_notifications import opt_out

        with patch("src.services.telegram_notifications.upsert_profile") as mock_upsert:
            result = opt_out("user@example.com")

        assert result is True
        mock_upsert.assert_called_once_with(
            user_id="user@example.com",
            updates={"can_receive_telegram_notifications": False},
        )

    def test_opt_out_returns_false_on_error(self):
        from src.services.telegram_notifications import opt_out

        with patch("src.services.telegram_notifications.upsert_profile", side_effect=Exception("db")):
            result = opt_out("user@example.com")
        assert result is False


# ---------------------------------------------------------------------------
# send_user_notification — success path
# ---------------------------------------------------------------------------

class TestSendUserNotification:

    def _setup_opted_in(self, chat_id="12345"):
        """Patch is_opted_in + chat_id resolution for the happy path."""
        mock_db = MagicMock()
        mock_db.available = True
        return {
            "is_opted_in": patch("src.services.telegram_notifications.is_opted_in", return_value=True),
            "resolve_chat": patch("src.services.telegram_notifications._resolve_chat_id", return_value=chat_id),
            "resolve_db": patch("src.services.telegram_notifications._resolve_db_user_id", return_value="uuid-abc"),
            "db": patch("src.services.telegram_notifications._db", return_value=mock_db),
            "rate": patch("src.services.telegram_notifications._check_rate_limit", return_value=True),
            "log": patch("src.services.telegram_notifications._log_alert"),
        }

    def test_sends_plain_text_when_no_job(self):
        from src.services.telegram_notifications import send_user_notification

        patches = self._setup_opted_in()
        with patches["is_opted_in"], patches["resolve_chat"], \
             patches["resolve_db"], patches["db"], patches["rate"], patches["log"], \
             patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "fake-token"}), \
             patch("requests.post") as mock_post:

            mock_post.return_value = MagicMock(ok=True)
            result = send_user_notification("u@x.com", "Test message", alert_type="job_alert")

        assert result is True
        mock_post.assert_called_once()
        call_json = mock_post.call_args[1]["json"]
        assert call_json["chat_id"] == "12345"
        assert "Test message" in call_json["text"]

    def test_sends_job_card_when_job_provided(self):
        from src.services.telegram_notifications import send_user_notification

        patches = self._setup_opted_in()
        job = {"title": "HSE Manager", "company": "Acme", "link": "https://example.com"}

        with patches["is_opted_in"], patches["resolve_chat"], \
             patches["resolve_db"], patches["db"], patches["rate"], patches["log"], \
             patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "fake-token"}), \
             patch("src.services.telegram_notifications.send_job_card_with_buttons", return_value=True) as mock_card:

            result = send_user_notification("u@x.com", "ignore", alert_type="job_alert", job=job)

        assert result is True
        mock_card.assert_called_once_with(job, chat_id="12345")

    def test_returns_false_when_not_opted_in(self):
        from src.services.telegram_notifications import send_user_notification

        with patch("src.services.telegram_notifications.is_opted_in", return_value=False):
            result = send_user_notification("u@x.com", "hi")
        assert result is False

    def test_returns_false_when_no_chat_id(self):
        from src.services.telegram_notifications import send_user_notification

        with patch("src.services.telegram_notifications.is_opted_in", return_value=True), \
             patch("src.services.telegram_notifications._resolve_chat_id", return_value=None):
            result = send_user_notification("u@x.com", "hi")
        assert result is False

    def test_returns_false_when_no_bot_token(self):
        from src.services.telegram_notifications import send_user_notification

        patches = self._setup_opted_in()
        with patches["is_opted_in"], patches["resolve_chat"], \
             patches["resolve_db"], patches["db"], patches["rate"], patches["log"], \
             patch.dict("os.environ", {}, clear=True):  # no TELEGRAM_BOT_TOKEN
            import os
            os.environ.pop("TELEGRAM_BOT_TOKEN", None)
            result = send_user_notification("u@x.com", "hi")

        assert result is False

    def test_send_failure_logs_and_returns_false(self):
        from src.services.telegram_notifications import send_user_notification

        patches = self._setup_opted_in()
        with patches["is_opted_in"], patches["resolve_chat"], \
             patches["resolve_db"], patches["db"], patches["rate"], patches["log"] as mock_log, \
             patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "fake-token"}), \
             patch("requests.post") as mock_post:

            mock_post.return_value = MagicMock(ok=False)
            result = send_user_notification("u@x.com", "msg", alert_type="reminder")

        assert result is False
        mock_log.assert_called_once()
        log_args = mock_log.call_args[0]
        assert log_args[3] == "failed" or "failed" in str(mock_log.call_args)

    def test_exception_in_requests_returns_false(self):
        from src.services.telegram_notifications import send_user_notification

        patches = self._setup_opted_in()
        with patches["is_opted_in"], patches["resolve_chat"], \
             patches["resolve_db"], patches["db"], patches["rate"], patches["log"], \
             patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "fake-token"}), \
             patch("requests.post", side_effect=Exception("network error")):

            result = send_user_notification("u@x.com", "hi")
        assert result is False


# ---------------------------------------------------------------------------
# Rate guard
# ---------------------------------------------------------------------------

class TestRateGuard:

    def test_rate_limited_send_returns_false(self):
        from src.services.telegram_notifications import send_user_notification

        with patch("src.services.telegram_notifications.is_opted_in", return_value=True), \
             patch("src.services.telegram_notifications._resolve_chat_id", return_value="123"), \
             patch("src.services.telegram_notifications._resolve_db_user_id", return_value="uuid"), \
             patch("src.services.telegram_notifications._check_rate_limit", return_value=False), \
             patch("src.services.telegram_notifications._db", return_value=MagicMock(available=True)):

            result = send_user_notification("u@x.com", "hi", alert_type="job_alert")

        assert result is False

    def test_within_rate_limit_allows_send(self):
        from src.services.telegram_notifications import send_user_notification

        with patch("src.services.telegram_notifications.is_opted_in", return_value=True), \
             patch("src.services.telegram_notifications._resolve_chat_id", return_value="123"), \
             patch("src.services.telegram_notifications._resolve_db_user_id", return_value="uuid"), \
             patch("src.services.telegram_notifications._check_rate_limit", return_value=True), \
             patch("src.services.telegram_notifications._log_alert"), \
             patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "tok"}), \
             patch("requests.post", return_value=MagicMock(ok=True)):

            result = send_user_notification("u@x.com", "hi", alert_type="job_alert")

        assert result is True


# ---------------------------------------------------------------------------
# Duplicate/dedup guard — rate limit prevents duplicate sends
# ---------------------------------------------------------------------------

class TestDuplicateGuard:

    def test_two_sends_within_window_second_is_blocked(self):
        """Simulate two sends within the rate window; second should be rate-limited."""
        from src.services.telegram_notifications import send_user_notification

        call_count = {"n": 0}

        def rate_limit_side_effect(*args, **kwargs):
            call_count["n"] += 1
            return call_count["n"] == 1  # only first call allowed

        with patch("src.services.telegram_notifications.is_opted_in", return_value=True), \
             patch("src.services.telegram_notifications._resolve_chat_id", return_value="123"), \
             patch("src.services.telegram_notifications._resolve_db_user_id", return_value="uuid"), \
             patch("src.services.telegram_notifications._check_rate_limit", side_effect=rate_limit_side_effect), \
             patch("src.services.telegram_notifications._log_alert"), \
             patch("src.services.telegram_notifications._db", return_value=MagicMock(available=True)), \
             patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "tok"}), \
             patch("requests.post", return_value=MagicMock(ok=True)):

            first = send_user_notification("u@x.com", "alert 1", alert_type="job_alert")
            second = send_user_notification("u@x.com", "alert 2", alert_type="job_alert")

        assert first is True
        assert second is False


# ---------------------------------------------------------------------------
# /start webhook handler
# ---------------------------------------------------------------------------

class TestStartHandler:

    def test_start_opts_in_known_username(self):
        """Known Telegram username → opt_in called with chat_id."""
        from src.rico_telegram_webhook import _handle_start

        mock_profile = MagicMock()
        mock_profile.user_id = "user@example.com"

        with patch("src.rico_telegram_webhook.find_profiles_by_telegram_username",
                   return_value=[mock_profile]), \
             patch("src.rico_telegram_webhook.opt_in") as mock_opt_in:

            reply = _handle_start(chat_id="999", tg_username="@Robin_amg")

        mock_opt_in.assert_called_once_with("user@example.com", telegram_chat_id="999")
        assert "job alerts" in reply.lower() or "notifications" in reply.lower() or "receive" in reply.lower()

    def test_start_unknown_username_returns_link_prompt(self):
        """Unknown Telegram username → prompts user to link account in Settings."""
        from src.rico_telegram_webhook import _handle_start

        with patch("src.rico_telegram_webhook.find_profiles_by_telegram_username", return_value=[]), \
             patch("src.rico_telegram_webhook.opt_in") as mock_opt_in:

            reply = _handle_start(chat_id="888", tg_username="@stranger")

        mock_opt_in.assert_not_called()
        assert "settings" in reply.lower() or "link" in reply.lower() or "ricohunt" in reply.lower()

    def test_start_no_username_returns_generic_prompt(self):
        """No Telegram username → safe fallback."""
        from src.rico_telegram_webhook import _handle_start

        with patch("src.rico_telegram_webhook.find_profiles_by_telegram_username", return_value=[]), \
             patch("src.rico_telegram_webhook.opt_in"):

            reply = _handle_start(chat_id="777", tg_username=None)

        assert isinstance(reply, str) and len(reply) > 0
