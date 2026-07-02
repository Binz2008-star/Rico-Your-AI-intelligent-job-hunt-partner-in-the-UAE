"""tests/test_email_notifications.py

Tests for email job-alert opt-in / opt-out and unsubscribe tokens (PR-1).

All DB and profile access is patched — no real database, SMTP, or network.
Invariants verified:
  - opt_in flips can_receive_email_alerts=True and mints an unsubscribe token
  - opt_in validates/normalises frequency; invalid frequency falls back to daily
  - opt_out flips the flag False (token preserved)
  - is_opted_in / get_frequency read from profile.settings, default safely
  - unsubscribe token: mint is idempotent (ON CONFLICT keeps existing)
  - unsubscribe_by_token opts out a known token, no-ops an unknown one
  - opt_in still succeeds (flag written) when the token table is unavailable
  - mailer.send_email attaches an HTML alternative only when html is provided
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.services import email_notifications as en


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _profile(*, email_alerts=False, frequency="daily"):
    settings = MagicMock()
    settings.can_receive_email_alerts = email_alerts
    settings.email_alert_frequency = frequency
    profile = MagicMock()
    profile.settings = settings
    return profile


def _mock_conn(fetch_results):
    """Build a mock connection whose cursor.fetchone() yields fetch_results in order."""
    cur = MagicMock()
    cur.fetchone.side_effect = fetch_results
    cur.__enter__ = MagicMock(return_value=cur)
    cur.__exit__ = MagicMock(return_value=False)
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn, cur


# ---------------------------------------------------------------------------
# Opt-in / opt-out / status
# ---------------------------------------------------------------------------

class TestOptInOut:
    def test_opt_in_sets_flag_and_mints_token(self):
        with patch.object(en, "upsert_profile") as up, \
             patch.object(en, "ensure_unsubscribe_token", return_value="tok") as mint:
            ok = en.opt_in("user@example.com")
        assert ok is True
        up.assert_called_once()
        assert up.call_args.kwargs["updates"]["can_receive_email_alerts"] is True
        mint.assert_called_once_with("user@example.com")

    def test_opt_in_normalises_frequency(self):
        with patch.object(en, "upsert_profile") as up, \
             patch.object(en, "ensure_unsubscribe_token", return_value="tok"):
            en.opt_in("u@x.com", frequency="WEEKLY")
        assert up.call_args.kwargs["updates"]["email_alert_frequency"] == "weekly"

    def test_opt_in_invalid_frequency_falls_back_to_daily(self):
        with patch.object(en, "upsert_profile") as up, \
             patch.object(en, "ensure_unsubscribe_token", return_value="tok"):
            en.opt_in("u@x.com", frequency="hourly")
        assert up.call_args.kwargs["updates"]["email_alert_frequency"] == "daily"

    def test_opt_in_succeeds_when_token_table_unavailable(self):
        # ensure_unsubscribe_token returns None (no DB) — opt-in must still succeed
        with patch.object(en, "upsert_profile") as up, \
             patch.object(en, "ensure_unsubscribe_token", return_value=None):
            ok = en.opt_in("u@x.com")
        assert ok is True
        assert up.call_args.kwargs["updates"]["can_receive_email_alerts"] is True

    def test_opt_out_sets_flag_false(self):
        with patch.object(en, "upsert_profile") as up:
            ok = en.opt_out("u@x.com")
        assert ok is True
        assert up.call_args.kwargs["updates"]["can_receive_email_alerts"] is False

    def test_is_opted_in_reads_settings(self):
        with patch.object(en, "get_profile", return_value=_profile(email_alerts=True)):
            assert en.is_opted_in("u@x.com") is True
        with patch.object(en, "get_profile", return_value=_profile(email_alerts=False)):
            assert en.is_opted_in("u@x.com") is False

    def test_is_opted_in_no_profile_is_false(self):
        with patch.object(en, "get_profile", return_value=None):
            assert en.is_opted_in("u@x.com") is False

    def test_get_frequency_defaults_and_validates(self):
        with patch.object(en, "get_profile", return_value=_profile(frequency="weekly")):
            assert en.get_frequency("u@x.com") == "weekly"
        with patch.object(en, "get_profile", return_value=_profile(frequency="nonsense")):
            assert en.get_frequency("u@x.com") == "daily"


# ---------------------------------------------------------------------------
# Unsubscribe tokens
# ---------------------------------------------------------------------------

class TestUnsubscribeTokens:
    def test_ensure_token_returns_new_token_on_insert(self):
        conn, cur = _mock_conn([("brand-new-token",)])  # RETURNING token
        with patch("src.db.get_db_connection", return_value=conn):
            tok = en.ensure_unsubscribe_token("u@x.com")
        assert tok == "brand-new-token"
        conn.commit.assert_called_once()
        conn.close.assert_called_once()

    def test_ensure_token_idempotent_reads_existing(self):
        # First fetchone (RETURNING) is None → conflict; second reads existing token
        conn, cur = _mock_conn([None, ("existing-token",)])
        with patch("src.db.get_db_connection", return_value=conn):
            tok = en.ensure_unsubscribe_token("u@x.com")
        assert tok == "existing-token"

    def test_ensure_token_no_db_returns_none(self):
        with patch("src.db.get_db_connection", return_value=None):
            assert en.ensure_unsubscribe_token("u@x.com") is None

    def test_resolve_user_by_token(self):
        conn, cur = _mock_conn([("u@x.com",)])
        with patch("src.db.get_db_connection", return_value=conn):
            assert en.resolve_user_by_token("tok") == "u@x.com"

    def test_resolve_unknown_token_returns_none(self):
        conn, cur = _mock_conn([None])
        with patch("src.db.get_db_connection", return_value=conn):
            assert en.resolve_user_by_token("nope") is None

    def test_resolve_empty_token_returns_none(self):
        # No DB call should be made for an empty token
        with patch("src.db.get_db_connection") as gc:
            assert en.resolve_user_by_token("") is None
            gc.assert_not_called()

    def test_unsubscribe_by_token_opts_out_known_user(self):
        with patch.object(en, "resolve_user_by_token", return_value="u@x.com"), \
             patch.object(en, "opt_out", return_value=True) as out:
            assert en.unsubscribe_by_token("tok") is True
            out.assert_called_once_with("u@x.com")

    def test_unsubscribe_by_token_unknown_is_false(self):
        with patch.object(en, "resolve_user_by_token", return_value=None), \
             patch.object(en, "opt_out") as out:
            assert en.unsubscribe_by_token("bad") is False
            out.assert_not_called()


# ---------------------------------------------------------------------------
# Frequency window helper (hours-based; fix #2)
# ---------------------------------------------------------------------------

class TestEmailedWithinHours:
    def test_query_uses_hour_interval_and_passes_window(self):
        conn, cur = _mock_conn([(1,)])  # a row exists → within window
        with patch("src.db.get_db_connection", return_value=conn):
            assert en.emailed_within_hours("u@x.com", 20) is True
        sql, params = cur.execute.call_args.args
        assert "INTERVAL '1 hour'" in sql
        assert "INTERVAL '1 day'" not in sql
        # window value is passed as a bound param (no string interpolation)
        assert 20 in params

    def test_no_recent_row_is_false(self):
        conn, cur = _mock_conn([None])
        with patch("src.db.get_db_connection", return_value=conn):
            assert en.emailed_within_hours("u@x.com", 20) is False

    def test_non_positive_hours_short_circuits(self):
        with patch("src.db.get_db_connection") as gc:
            assert en.emailed_within_hours("u@x.com", 0) is False
            gc.assert_not_called()


# ---------------------------------------------------------------------------
# Mailer HTML support
# ---------------------------------------------------------------------------

class TestMailerHtml:
    def _smtp_env(self, monkeypatch):
        monkeypatch.setenv("SMTP_USER", "sender@ricohunt.com")
        monkeypatch.setenv("SMTP_PASSWORD", "secret")
        monkeypatch.setenv("SMTP_PORT", "465")

    def test_html_alternative_attached_when_provided(self, monkeypatch):
        from src.services import mailer

        self._smtp_env(monkeypatch)
        sent = {}

        class FakeServer:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def login(self, *a): pass
            def send_message(self, msg): sent["msg"] = msg

        with patch("smtplib.SMTP_SSL", return_value=FakeServer()):
            ok = mailer.send_email(
                to_email="to@x.com", subject="Hi", body="text",
                html="<b>hi</b>",
            )
        assert ok is True
        assert sent["msg"].is_multipart() is True
        assert any(p.get_content_type() == "text/html" for p in sent["msg"].walk())

    def test_plain_text_when_no_html(self, monkeypatch):
        from src.services import mailer

        self._smtp_env(monkeypatch)
        sent = {}

        class FakeServer:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def login(self, *a): pass
            def send_message(self, msg): sent["msg"] = msg

        with patch("smtplib.SMTP_SSL", return_value=FakeServer()):
            ok = mailer.send_email(to_email="to@x.com", subject="Hi", body="text")
        assert ok is True
        assert sent["msg"].is_multipart() is False


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
