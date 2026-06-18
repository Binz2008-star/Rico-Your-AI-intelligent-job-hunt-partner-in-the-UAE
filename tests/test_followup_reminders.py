"""Tests for follow-up reminders Phase 1 (Issue #355).

Covers the cron-secret guard, the due-scan service summary/safety, and the
idempotent sweep SQL. No live DB or network.
"""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from fastapi import HTTPException


class _FakeHeaders:
    def __init__(self, data):
        self._data = data

    def get(self, key, default=None):
        return self._data.get(key, default)


def _req(headers):
    return SimpleNamespace(headers=_FakeHeaders(headers))


# ── require_cron_secret ──────────────────────────────────────────────────────


def test_cron_secret_unset_is_503(monkeypatch):
    from src.api.deps import require_cron_secret

    monkeypatch.delenv("RICO_CRON_SECRET", raising=False)
    with pytest.raises(HTTPException) as exc:
        require_cron_secret(_req({"X-Cron-Secret": "anything"}))
    assert exc.value.status_code == 503  # fails closed when not configured


def test_cron_secret_wrong_is_403(monkeypatch):
    from src.api.deps import require_cron_secret

    monkeypatch.setenv("RICO_CRON_SECRET", "right-secret")
    with pytest.raises(HTTPException) as exc:
        require_cron_secret(_req({"X-Cron-Secret": "wrong-secret"}))
    assert exc.value.status_code == 403


def test_cron_secret_missing_header_is_403(monkeypatch):
    from src.api.deps import require_cron_secret

    monkeypatch.setenv("RICO_CRON_SECRET", "right-secret")
    with pytest.raises(HTTPException) as exc:
        require_cron_secret(_req({}))
    assert exc.value.status_code == 403


def test_cron_secret_correct_passes(monkeypatch):
    from src.api.deps import require_cron_secret

    monkeypatch.setenv("RICO_CRON_SECRET", "right-secret")
    assert require_cron_secret(_req({"X-Cron-Secret": "right-secret"})) is None


# ── run_due_scan service ─────────────────────────────────────────────────────


def _fake_db(available=True, marked=0, raises=False):
    db = MagicMock()
    db.available = available
    if raises:
        db.mark_followups_due.side_effect = Exception("no such column: applied_at")
    else:
        db.mark_followups_due.return_value = marked
    return db


def test_run_due_scan_ok():
    from src.services import followup_service

    db = _fake_db(available=True, marked=3)
    with patch("src.rico_db.RicoDB", return_value=db):
        out = followup_service.run_due_scan(7)
    assert out == {"status": "ok", "interval_days": 7, "marked_due": 3}
    db.mark_followups_due.assert_called_once_with(7)


def test_run_due_scan_db_unavailable():
    from src.services import followup_service

    db = _fake_db(available=False)
    with patch("src.rico_db.RicoDB", return_value=db):
        out = followup_service.run_due_scan(7)
    assert out["status"] == "unavailable"
    assert out["marked_due"] == 0
    db.mark_followups_due.assert_not_called()


def test_run_due_scan_swallows_db_error():
    from src.services import followup_service

    db = _fake_db(available=True, raises=True)
    with patch("src.rico_db.RicoDB", return_value=db):
        out = followup_service.run_due_scan(7)
    assert out["status"] == "error"
    assert out["marked_due"] == 0  # never raises (e.g. pre-migration 027)


def test_run_due_scan_interval_defaults_on_bad_input():
    from src.services import followup_service

    db = _fake_db(available=True, marked=0)
    with patch("src.rico_db.RicoDB", return_value=db):
        out_zero = followup_service.run_due_scan(0)
        out_bad = followup_service.run_due_scan("nonsense")
    assert out_zero["interval_days"] == followup_service.DEFAULT_FOLLOWUP_INTERVAL_DAYS
    assert out_bad["interval_days"] == followup_service.DEFAULT_FOLLOWUP_INTERVAL_DAYS


# ── mark_followups_due sweep (idempotent SQL) ────────────────────────────────


def test_mark_followups_due_targets_applied_only_and_returns_rowcount():
    from src.rico_db import RicoDB

    cur = MagicMock()
    cur.rowcount = 2
    conn = MagicMock()
    conn.cursor.return_value.__enter__ = lambda *_: cur
    conn.cursor.return_value.__exit__ = lambda *a: False

    @contextmanager
    def fake_tx():
        yield conn

    db = RicoDB.__new__(RicoDB)  # bypass __init__/connection
    with patch.object(db, "_transaction", fake_tx):
        result = db.mark_followups_due(7)

    assert result == 2
    sql = cur.execute.call_args[0][0]
    # Idempotency: only applied rows are transitioned, to follow_up_due.
    assert "status = 'applied'" in sql
    assert "follow_up_due" in sql
    assert cur.execute.call_args[0][1] == (7,)


def test_mark_followups_due_clamps_interval_to_min_one():
    from src.rico_db import RicoDB

    cur = MagicMock()
    cur.rowcount = 0
    conn = MagicMock()
    conn.cursor.return_value.__enter__ = lambda *_: cur
    conn.cursor.return_value.__exit__ = lambda *a: False

    @contextmanager
    def fake_tx():
        yield conn

    db = RicoDB.__new__(RicoDB)
    with patch.object(db, "_transaction", fake_tx):
        db.mark_followups_due(0)

    assert cur.execute.call_args[0][1] == (1,)  # clamped to >= 1 day
