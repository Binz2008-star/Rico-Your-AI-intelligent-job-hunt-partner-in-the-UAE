"""Durable notification consent + fail-closed senders (#1082).

Locked contracts:

  1. The scheduled Telegram roster selects ONLY rows with an explicit durable
     ``telegram_notifications_enabled IS TRUE`` — NULL/missing is not permission.
  2. Scheduled per-user Telegram alerts are OFF unless
     RICO_ENABLE_USER_TELEGRAM_ALERTS is explicitly enabled (global kill switch,
     distinct from the admin/public bot flags).
  3. /stop durably disables every rico_users row bound to the chat (native and
     web-linked) or fails loudly — "Notifications paused" is never claimed
     without a committed DB write.
  4. /start links with require_db=True — "now linked" is never confirmed from
     the process-local mirror.
  5. The profile-nudge email sweep is OFF behind RICO_ENABLE_EMAIL_ALERTS,
     selects only active+verified users with explicit durable email consent,
     and releases its idempotency stamp when a send fails (retryable).

All DB access is mocked — no real database, no live Telegram/email sends.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# 1. Roster consent filter
# ─────────────────────────────────────────────────────────────────────────────

class TestTelegramRosterFailClosed:
    def test_roster_query_requires_explicit_true_consent(self, monkeypatch):
        from src.repositories import profile_repo

        executed = {}

        cur = MagicMock()
        cur.description = [("external_user_id",), ("name",), ("telegram_chat_id",), ("telegram_username",)]
        cur.fetchall.return_value = []
        cur.execute.side_effect = lambda sql, *a: executed.setdefault("sql", sql)
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        db = MagicMock()
        db.connect.return_value = conn
        monkeypatch.setattr(profile_repo, "_db", lambda: db)

        profile_repo.get_users_with_telegram_alerts()

        assert "telegram_notifications_enabled IS TRUE" in executed["sql"]

    def test_roster_returns_empty_on_db_unavailable(self, monkeypatch):
        from src.repositories import profile_repo

        monkeypatch.setattr(profile_repo, "_db", lambda: None)
        assert profile_repo.get_users_with_telegram_alerts() == []


# ─────────────────────────────────────────────────────────────────────────────
# 2. Global user-alert kill switch in the daily sender
# ─────────────────────────────────────────────────────────────────────────────

class TestDailyTelegramKillSwitch:
    def test_sender_skips_when_switch_unset(self, monkeypatch):
        monkeypatch.delenv("RICO_ENABLE_USER_TELEGRAM_ALERTS", raising=False)
        import src.run_daily as run_daily

        with patch.object(run_daily, "get_users_with_telegram_alerts") as mock_roster:
            run_daily._notify_users_via_telegram([{"title": "HSE Manager"}])
        mock_roster.assert_not_called()

    def test_sender_skips_when_switch_false(self, monkeypatch):
        monkeypatch.setenv("RICO_ENABLE_USER_TELEGRAM_ALERTS", "false")
        import src.run_daily as run_daily

        with patch.object(run_daily, "get_users_with_telegram_alerts") as mock_roster:
            run_daily._notify_users_via_telegram([{"title": "HSE Manager"}])
        mock_roster.assert_not_called()

    def test_sender_proceeds_when_enabled(self, monkeypatch):
        monkeypatch.setenv("RICO_ENABLE_USER_TELEGRAM_ALERTS", "true")
        import src.run_daily as run_daily

        with patch.object(run_daily, "get_users_with_telegram_alerts", return_value=[]) as mock_roster:
            run_daily._notify_users_via_telegram([{"title": "HSE Manager"}])
        mock_roster.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# 3. /stop — durable chat-wide opt-out, no false "paused"
# ─────────────────────────────────────────────────────────────────────────────

def _tg_message(chat_id: str = "12345", username: str = "") -> dict:
    msg: dict = {"chat": {"id": chat_id}, "from": {"id": chat_id}, "text": "/stop"}
    if username:
        msg["from"]["username"] = username
    return msg


class TestStopDurable:
    def test_stop_success_confirms_paused(self):
        import src.rico_telegram_webhook as tw

        with patch(
            "src.repositories.profile_repo.disable_telegram_alerts_for_chat",
            return_value=2,
        ) as mock_disable, patch.object(tw, "send_telegram_to_user") as mock_send:
            result = tw._handle_stop(_tg_message())

        mock_disable.assert_called_once_with("12345")
        assert "paused" in result["reply"].lower()
        mock_send.assert_called_once()

    def test_stop_db_failure_never_claims_paused(self):
        import src.rico_telegram_webhook as tw

        with patch(
            "src.repositories.profile_repo.disable_telegram_alerts_for_chat",
            side_effect=RuntimeError("telegram consent DB unavailable"),
        ), patch.object(tw, "send_telegram_to_user"):
            result = tw._handle_stop(_tg_message())

        assert "paused" not in result["reply"].lower()
        assert "couldn't update" in result["reply"].lower() or "try /stop" in result["reply"].lower()

    def test_stop_unlinked_chat_persists_explicit_opt_out_durably(self):
        import src.rico_telegram_webhook as tw

        with patch(
            "src.repositories.profile_repo.disable_telegram_alerts_for_chat",
            return_value=0,
        ), patch.object(tw, "upsert_profile") as mock_upsert, patch.object(
            tw, "send_telegram_to_user"
        ):
            result = tw._handle_stop(_tg_message("777"))

        assert mock_upsert.call_args.kwargs.get("require_db") is True
        updates = mock_upsert.call_args.args[1]
        assert updates["telegram_notifications_enabled"] is False
        assert "paused" in result["reply"].lower()

    def test_stop_unlinked_chat_write_failure_never_claims_paused(self):
        import src.rico_telegram_webhook as tw

        with patch(
            "src.repositories.profile_repo.disable_telegram_alerts_for_chat",
            return_value=0,
        ), patch.object(
            tw, "upsert_profile",
            side_effect=RuntimeError("profile DB unavailable (require_db)"),
        ), patch.object(tw, "send_telegram_to_user"):
            result = tw._handle_stop(_tg_message("777"))

        assert "paused" not in result["reply"].lower()


class TestStartDurable:
    def test_start_passes_require_db(self):
        import src.rico_telegram_webhook as tw

        with patch.object(tw, "upsert_profile") as mock_upsert, patch.object(
            tw, "send_telegram_to_user"
        ):
            result = tw._handle_start(_tg_message("555"))

        assert mock_upsert.call_args.kwargs.get("require_db") is True
        assert "linked" in result["reply"].lower()

    def test_start_db_failure_never_claims_linked(self):
        import src.rico_telegram_webhook as tw

        with patch.object(
            tw, "upsert_profile",
            side_effect=RuntimeError("profile DB unavailable (require_db)"),
        ), patch.object(tw, "send_telegram_to_user"):
            result = tw._handle_start(_tg_message("555"))

        assert "now linked" not in result["reply"].lower()
        assert "couldn't link" in result["reply"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# disable_telegram_alerts_for_chat — DB-mandatory repo contract
# ─────────────────────────────────────────────────────────────────────────────

class TestDisableForChatRepo:
    def test_raises_when_db_unavailable(self, monkeypatch):
        from src.repositories import profile_repo

        monkeypatch.setattr(profile_repo, "_db", lambda: None)
        with pytest.raises(RuntimeError):
            profile_repo.disable_telegram_alerts_for_chat("123")

    def test_raises_on_empty_chat_id(self):
        from src.repositories import profile_repo

        with pytest.raises(RuntimeError):
            profile_repo.disable_telegram_alerts_for_chat("")

    def test_returns_rowcount_and_targets_chat_id(self, monkeypatch):
        from contextlib import contextmanager

        from src.repositories import profile_repo

        cur = MagicMock()
        cur.rowcount = 2
        executed = {}
        cur.execute.side_effect = lambda sql, params: executed.update(sql=sql, params=params)
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur

        @contextmanager
        def fake_txn():
            yield conn

        monkeypatch.setattr(profile_repo, "_db", lambda: MagicMock())
        monkeypatch.setattr(profile_repo, "_db_transaction", fake_txn)

        assert profile_repo.disable_telegram_alerts_for_chat("999") == 2
        assert "telegram_notifications_enabled = FALSE" in executed["sql"]
        assert executed["params"] == ("999",)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Profile nudge sweep — kill switch, consent roster, retryable stamp
# ─────────────────────────────────────────────────────────────────────────────

class TestNudgeSweepFailClosed:
    def test_sweep_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("RICO_ENABLE_EMAIL_ALERTS", raising=False)
        from src.services.profile_nudge_service import run_profile_nudge_sweep

        with patch("src.rico_db.RicoDB") as mock_db:
            result = run_profile_nudge_sweep()
        assert result["status"] == "disabled"
        mock_db.assert_not_called()

    def test_roster_requires_consent_active_and_verified(self, monkeypatch):
        monkeypatch.setenv("RICO_ENABLE_EMAIL_ALERTS", "true")
        from src.services.profile_nudge_service import run_profile_nudge_sweep

        executed = []

        cur = MagicMock()
        cur.fetchone.return_value = {"?column?": 1}  # migration guard passes
        cur.fetchall.return_value = []
        cur.execute.side_effect = lambda sql, *a: executed.append(sql)
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        db = MagicMock()
        db.available = True
        db.connect.return_value = conn

        with patch("src.rico_db.RicoDB", return_value=db):
            run_profile_nudge_sweep()

        roster_sql = executed[-1]
        assert "can_receive_email_alerts" in roster_sql
        assert "u.is_active IS TRUE" in roster_sql
        assert "u.email_verified IS TRUE" in roster_sql

    def test_failed_send_releases_stamp(self, monkeypatch):
        monkeypatch.setenv("RICO_ENABLE_EMAIL_ALERTS", "true")
        from src.services.profile_nudge_service import run_profile_nudge_sweep

        row = {
            "user_id": 7,
            "email": "real.person@gmail.com",
            "name": "Real Person",
            "cv_filename": None,
            "target_roles": None,
            "preferred_cities": None,
        }

        executed = []

        cur = MagicMock()
        cur.fetchone.return_value = {"?column?": 1}
        cur.fetchall.return_value = [row]
        cur.execute.side_effect = lambda sql, *a: executed.append((sql, a))
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        db = MagicMock()
        db.available = True
        db.connect.return_value = conn

        with patch("src.rico_db.RicoDB", return_value=db), patch(
            "src.services.mailer.send_email", return_value=False
        ):
            result = run_profile_nudge_sweep()

        assert result["nudges_failed"] == 1
        release_calls = [
            sql for sql, _ in executed
            if "profile_nudge_sent_at = NULL" in sql
        ]
        assert release_calls, "failed send must release the idempotency stamp"

    def test_successful_send_keeps_stamp(self, monkeypatch):
        monkeypatch.setenv("RICO_ENABLE_EMAIL_ALERTS", "true")
        from src.services.profile_nudge_service import run_profile_nudge_sweep

        row = {
            "user_id": 8,
            "email": "real.person2@gmail.com",
            "name": "Real Person",
            "cv_filename": None,
            "target_roles": None,
            "preferred_cities": None,
        }

        executed = []

        cur = MagicMock()
        cur.fetchone.return_value = {"?column?": 1}
        cur.fetchall.return_value = [row]
        cur.execute.side_effect = lambda sql, *a: executed.append((sql, a))
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        db = MagicMock()
        db.available = True
        db.connect.return_value = conn

        with patch("src.rico_db.RicoDB", return_value=db), patch(
            "src.services.mailer.send_email", return_value=True
        ):
            result = run_profile_nudge_sweep()

        assert result["nudges_sent"] == 1
        release_calls = [sql for sql, _ in executed if "profile_nudge_sent_at = NULL" in sql]
        assert not release_calls
