"""tests/test_telegram_notifications.py

Tests for the Telegram notifications workflow (JOB-55):
  - /start command binds chat_id and enables notifications
  - /start with unknown @username creates a record under the chat_id user_id
  - /stop command disables notifications
  - send_job_alerts sends cards, records to log, returns count
  - Duplicate guard: already-logged job is skipped
  - Daily rate cap: stops after MAX_ALERTS_PER_DAY
  - send_followup_reminder sends correctly-formatted reminder
  - broadcast_job_alerts_to_subscribed_users iterates subscribed users
  - Safe failure: Telegram API error → logged, returns 0, does not raise
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, call, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_telegram_update(text: str, chat_id: int = 111, username: str = "Robin_amg") -> dict:
    return {
        "message": {
            "chat": {"id": chat_id},
            "from": {"id": chat_id, "username": username},
            "text": text,
        }
    }


def _sample_jobs(n: int = 3) -> list[dict]:
    return [
        {
            "title": f"HSE Manager {i}",
            "company": f"AcmeCorp {i}",
            "location": "Dubai, UAE",
            "salary": "AED 20,000",
            "score": 85 - i,
            "apply_url": f"https://example.com/job/{i}",
        }
        for i in range(1, n + 1)
    ]


# ---------------------------------------------------------------------------
# /start command
# ---------------------------------------------------------------------------

class TestStartCommand:
    def test_start_binds_chat_id_for_known_username(self):
        """If @username matches an existing user, bind chat_id to that user."""
        from src.rico_telegram_webhook import _handle_start

        profile = MagicMock()
        profile.user_id = "user-abc"

        with patch("src.rico_telegram_webhook.find_profiles_by_telegram_username", return_value=[profile]) as mock_find, \
             patch("src.rico_telegram_webhook.upsert_profile") as mock_upsert:
            result = _handle_start(
                {"chat": {"id": 12345}, "from": {"id": 12345, "username": "Robin_amg"}}
            )

        mock_find.assert_called_once_with("robin_amg")
        mock_upsert.assert_called_once()
        call_kwargs = mock_upsert.call_args
        assert call_kwargs[0][0] == "user-abc"
        updates = call_kwargs[0][1]
        assert updates["telegram_chat_id"] == "12345"
        assert updates["telegram_notifications_enabled"] is True
        assert result["chat_id"] == "12345"
        assert "/stop" in result["reply"]

    def test_start_uses_chat_id_as_user_id_when_no_match(self):
        """Unknown @username → fall back to chat_id as Rico user_id."""
        from src.rico_telegram_webhook import _handle_start

        with patch("src.rico_telegram_webhook.find_profiles_by_telegram_username", return_value=[]), \
             patch("src.rico_telegram_webhook.upsert_profile") as mock_upsert:
            result = _handle_start(
                {"chat": {"id": 99999}, "from": {"id": 99999, "username": "unknown_user"}}
            )

        call_kwargs = mock_upsert.call_args
        # user_id should be the chat_id string
        assert call_kwargs[0][0] == "99999"
        assert call_kwargs[0][1]["telegram_chat_id"] == "99999"
        assert result["chat_id"] == "99999"

    def test_start_without_username(self):
        """Message without username still binds chat_id to the chat_id user."""
        from src.rico_telegram_webhook import _handle_start

        with patch("src.rico_telegram_webhook.find_profiles_by_telegram_username", return_value=[]), \
             patch("src.rico_telegram_webhook.upsert_profile") as mock_upsert:
            result = _handle_start({"chat": {"id": 55555}, "from": {}})

        mock_upsert.assert_called_once()
        assert result["chat_id"] == "55555"

    def test_start_upsert_failure_does_not_raise(self):
        """DB failure on /start is logged but not raised."""
        from src.rico_telegram_webhook import _handle_start

        with patch("src.rico_telegram_webhook.find_profiles_by_telegram_username", return_value=[]), \
             patch("src.rico_telegram_webhook.upsert_profile", side_effect=Exception("DB down")):
            result = _handle_start({"chat": {"id": 77777}, "from": {"username": "testuser"}})

        # Should still return a response dict
        assert "chat_id" in result


# ---------------------------------------------------------------------------
# /stop command
# ---------------------------------------------------------------------------

class TestStopCommand:
    def test_stop_disables_notifications(self):
        """Sending /stop durably disables every row bound to the chat (#1082)."""
        from src.rico_telegram_webhook import _handle_stop

        with patch(
            "src.repositories.profile_repo.disable_telegram_alerts_for_chat",
            return_value=1,
        ) as mock_disable:
            result = _handle_stop({"chat": {"id": 12345}, "from": {"id": 12345}})

        mock_disable.assert_called_once_with("12345")
        assert "/start" in result["reply"]
        assert result["chat_id"] == "12345"

    def test_stop_failure_does_not_raise(self):
        from src.rico_telegram_webhook import _handle_stop

        with patch(
            "src.repositories.profile_repo.disable_telegram_alerts_for_chat",
            side_effect=Exception("DB down"),
        ):
            result = _handle_stop({"chat": {"id": 12345}, "from": {}})

        assert "chat_id" in result
        assert "paused" not in result["reply"].lower()


# ---------------------------------------------------------------------------
# Webhook routing
# ---------------------------------------------------------------------------

class TestWebhookRouting:
    def test_start_command_routed_before_chat(self):
        """process_telegram_update must call _handle_start for /start."""
        from src.rico_telegram_webhook import process_telegram_update

        with patch("src.rico_telegram_webhook._handle_start") as mock_start:
            mock_start.return_value = {"chat_id": "1", "reply": "ok"}
            process_telegram_update(_make_telegram_update("/start"))

        mock_start.assert_called_once()

    def test_stop_command_routed_before_chat(self):
        from src.rico_telegram_webhook import process_telegram_update

        with patch("src.rico_telegram_webhook._handle_stop") as mock_stop:
            mock_stop.return_value = {"chat_id": "1", "reply": "ok"}
            process_telegram_update(_make_telegram_update("/stop"))

        mock_stop.assert_called_once()

    def test_regular_message_goes_to_chat_api(self):
        from src.rico_telegram_webhook import process_telegram_update

        with patch("src.rico_telegram_webhook.chat_api") as mock_api:
            mock_api.process_message.return_value = {"message": "hi"}
            process_telegram_update(_make_telegram_update("find me jobs in Dubai"))

        mock_api.process_message.assert_called_once()


# ---------------------------------------------------------------------------
# send_job_alerts
# ---------------------------------------------------------------------------

class TestSendJobAlerts:
    def _mock_db(self, *, sent_today: int = 0, already_sent: bool = False):
        db = MagicMock()
        db.available = True
        db.count_alerts_today.return_value = sent_today
        db.was_alert_sent.return_value = already_sent
        db.log_telegram_alert.return_value = True
        return db

    def test_sends_jobs_and_returns_count(self):
        from src.services.telegram_alert_service import send_job_alerts

        db = self._mock_db()
        jobs = _sample_jobs(3)

        with patch("src.services.telegram_alert_service.RicoDB", return_value=db), \
             patch("src.services.telegram_alert_service._send_message", return_value=True) as mock_send:
            count = send_job_alerts("user1", "chat123", jobs)

        assert count == 3
        assert mock_send.call_count == 3
        assert db.log_telegram_alert.call_count == 3

    def test_duplicate_guard_skips_already_sent(self):
        """Jobs already logged in telegram_alert_log are skipped."""
        from src.services.telegram_alert_service import send_job_alerts

        db = self._mock_db(already_sent=True)
        jobs = _sample_jobs(2)

        with patch("src.services.telegram_alert_service.RicoDB", return_value=db), \
             patch("src.services.telegram_alert_service._send_message", return_value=True) as mock_send:
            count = send_job_alerts("user1", "chat123", jobs)

        assert count == 0
        mock_send.assert_not_called()

    def test_daily_rate_cap_stops_early(self):
        """Stops after MAX_ALERTS_PER_DAY regardless of job list length."""
        from src.services.telegram_alert_service import MAX_ALERTS_PER_DAY, send_job_alerts

        db = self._mock_db(sent_today=MAX_ALERTS_PER_DAY)
        jobs = _sample_jobs(5)

        with patch("src.services.telegram_alert_service.RicoDB", return_value=db), \
             patch("src.services.telegram_alert_service._send_message") as mock_send:
            count = send_job_alerts("user1", "chat123", jobs)

        assert count == 0
        mock_send.assert_not_called()

    def test_dry_run_counts_eligibles_without_sending(self):
        from src.services.telegram_alert_service import send_job_alerts

        db = self._mock_db()
        jobs = _sample_jobs(3)

        with patch("src.services.telegram_alert_service.RicoDB", return_value=db), \
             patch("src.services.telegram_alert_service._send_message") as mock_send:
            count = send_job_alerts("user1", "chat123", jobs, dry_run=True)

        assert count == 3
        mock_send.assert_not_called()
        db.log_telegram_alert.assert_not_called()

    def test_telegram_api_error_returns_zero_does_not_raise(self):
        from src.services.telegram_alert_service import send_job_alerts

        db = self._mock_db()
        jobs = _sample_jobs(2)

        with patch("src.services.telegram_alert_service.RicoDB", return_value=db), \
             patch("src.services.telegram_alert_service._send_message", return_value=False):
            count = send_job_alerts("user1", "chat123", jobs)

        assert count == 0  # sends failed → nothing counted

    def test_empty_job_list_returns_zero(self):
        from src.services.telegram_alert_service import send_job_alerts

        with patch("src.services.telegram_alert_service.RicoDB"):
            count = send_job_alerts("user1", "chat123", [])

        assert count == 0

    def test_missing_chat_id_returns_zero(self):
        from src.services.telegram_alert_service import send_job_alerts

        with patch("src.services.telegram_alert_service.RicoDB"):
            count = send_job_alerts("user1", "", _sample_jobs(2))

        assert count == 0


# ---------------------------------------------------------------------------
# send_followup_reminder
# ---------------------------------------------------------------------------

class TestFollowupReminder:
    def test_sends_formatted_reminder(self):
        from src.services.telegram_alert_service import send_followup_reminder

        with patch("src.services.telegram_alert_service._send_message", return_value=True) as mock_send:
            result = send_followup_reminder("chat123", "HSE Manager", "AcmeCorp", days_ago=3)

        assert result is True
        text = mock_send.call_args[0][1]
        assert "HSE Manager" in text
        assert "AcmeCorp" in text
        assert "3 days ago" in text

    def test_followup_api_failure_returns_false(self):
        from src.services.telegram_alert_service import send_followup_reminder

        with patch("src.services.telegram_alert_service._send_message", return_value=False):
            result = send_followup_reminder("chat123", "Developer", "Corp")

        assert result is False


# ---------------------------------------------------------------------------
# broadcast_job_alerts_to_subscribed_users
# ---------------------------------------------------------------------------

class TestBroadcast:
    def test_iterates_subscribed_users(self):
        from src.services.telegram_alert_service import broadcast_job_alerts_to_subscribed_users

        mock_db = MagicMock()
        mock_db.available = True
        mock_db.get_users_with_active_telegram_notifications.return_value = [
            {"external_user_id": "user1", "telegram_chat_id": "chat1"},
            {"external_user_id": "user2", "telegram_chat_id": "chat2"},
        ]

        jobs = _sample_jobs(2)

        with patch("src.services.telegram_alert_service.RicoDB", return_value=mock_db), \
             patch("src.services.telegram_alert_service.send_job_alerts", return_value=2) as mock_alerts:
            result = broadcast_job_alerts_to_subscribed_users(jobs)

        assert result["users"] == 2
        assert result["total_sent"] == 4  # 2 users × 2 each
        assert mock_alerts.call_count == 2

    def test_db_unavailable_returns_empty(self):
        from src.services.telegram_alert_service import broadcast_job_alerts_to_subscribed_users

        mock_db = MagicMock()
        mock_db.available = False

        with patch("src.services.telegram_alert_service.RicoDB", return_value=mock_db):
            result = broadcast_job_alerts_to_subscribed_users(_sample_jobs(2))

        assert result == {"users": 0, "total_sent": 0}
