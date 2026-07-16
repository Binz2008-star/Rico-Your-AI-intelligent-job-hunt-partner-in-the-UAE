"""
Legacy global Gmail importer is disabled unless explicitly enabled (#1087).

RICO_ENABLE_GMAIL_SYNC gates both the pipeline hook (run_daily._sync_gmail) and
the repo-adapter method (RicoRepoAdapter.sync_gmail). Default off (fail-closed)
so a supposedly-disabled integration cannot silently mutate the shared
applications store or log message metadata. The M0 first-party connector (#1055)
is the supported, per-user, consent-scoped path.

Hermetic: a fake `src.gmail_importer` is injected so the real (heavy) importer is
never imported; the security assertion is that `run_import` is not reached.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest


def _fake_gmail(monkeypatch, classified=0, updated=0, queued=0):
    fake = MagicMock()
    fake.run_import.return_value = MagicMock(
        emails_classified=classified, updates_applied=updated, queued_for_review=queued
    )
    monkeypatch.setitem(sys.modules, "src.gmail_importer", fake)
    return fake


@pytest.fixture(autouse=True)
def _clear_flag(monkeypatch):
    monkeypatch.delenv("RICO_ENABLE_GMAIL_SYNC", raising=False)
    yield


class TestPipelineHookFailClosed:
    def test_skips_when_flag_unset(self, monkeypatch):
        fake = _fake_gmail(monkeypatch)
        from src import run_daily

        run_daily._sync_gmail()
        fake.run_import.assert_not_called()

    def test_skips_when_flag_false(self, monkeypatch):
        monkeypatch.setenv("RICO_ENABLE_GMAIL_SYNC", "false")
        fake = _fake_gmail(monkeypatch)
        from src import run_daily

        run_daily._sync_gmail()
        fake.run_import.assert_not_called()

    def test_runs_when_flag_enabled(self, monkeypatch):
        monkeypatch.setenv("RICO_ENABLE_GMAIL_SYNC", "true")
        fake = _fake_gmail(monkeypatch)
        from src import run_daily

        run_daily._sync_gmail()
        fake.run_import.assert_called_once_with(dry_run=False)


class TestRepoAdapterFailClosed:
    def test_skips_when_flag_unset(self, monkeypatch):
        fake = _fake_gmail(monkeypatch)
        from src.rico_repo_adapter import RicoRepoAdapter

        adapter = RicoRepoAdapter.__new__(RicoRepoAdapter)  # skip heavy __init__
        result = adapter.sync_gmail()
        fake.run_import.assert_not_called()
        assert result.get("skipped") == "disabled"

    def test_runs_when_flag_enabled(self, monkeypatch):
        monkeypatch.setenv("RICO_ENABLE_GMAIL_SYNC", "true")
        fake = _fake_gmail(monkeypatch, classified=2, queued=1)
        from src.rico_repo_adapter import RicoRepoAdapter

        adapter = RicoRepoAdapter.__new__(RicoRepoAdapter)
        result = adapter.sync_gmail()
        fake.run_import.assert_called_once_with(dry_run=False)
        assert result["classified"] == 2
        assert result.get("skipped") is None
