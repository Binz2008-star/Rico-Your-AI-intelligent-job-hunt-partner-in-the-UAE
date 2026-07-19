"""Analytics retention purge endpoint (POST /api/v1/pipeline/analytics-purge).

Pins the governance contract (DEC-20260719-001):

1. RETENTION IS NEVER CALLER-CONTROLLED — the handler exposes no retention
   parameter, ignores retention-shaped query params, and always invokes the
   repository with its internal constant (no arguments).
2. FAIL-CLOSED KILL SWITCH — RICO_ENABLE_ANALYTICS_PURGE defaults off;
   disabled runs are an explicit 200 no-op that never touches the repository,
   so a scheduled caller never pages on the gate.
3. DRY-RUN NEVER DELETES — ?dry_run=true calls only count_expired() (which
   shares the DELETE's predicate; pinned in test_analytics_events_repo.py).
4. The route stays behind the X-Cron-Secret guard (503 unconfigured / 403 bad).
"""
from __future__ import annotations

import inspect
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.app import app
from src.api.routers import pipeline as pipeline_router
from src.repositories import analytics_events_repo as analytics_repo

client = TestClient(app)
URL = "/api/v1/pipeline/analytics-purge"
_SECRET = "cron-secret-test-only"


def _armed(monkeypatch, flag: str = "true") -> dict:
    """Set the cron secret (and optionally the flag); return valid headers."""
    monkeypatch.setenv("RICO_CRON_SECRET", _SECRET)
    if flag is None:
        monkeypatch.delenv("RICO_ENABLE_ANALYTICS_PURGE", raising=False)
    else:
        monkeypatch.setenv("RICO_ENABLE_ANALYTICS_PURGE", flag)
    return {"X-Cron-Secret": _SECRET}


# ── 1. Retention is never caller-controlled ──────────────────────────────────

def test_handler_signature_exposes_no_retention_parameter():
    params = set(inspect.signature(pipeline_router.run_analytics_purge).parameters)
    assert params == {"request", "_cron"}


def test_real_run_purges_with_internal_constant_only(monkeypatch):
    headers = _armed(monkeypatch)
    with patch.object(analytics_repo, "purge_expired", return_value=3) as purge, \
         patch.object(analytics_repo, "count_expired") as count:
        resp = client.post(URL, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["removed"] == 3
    assert body["would_remove"] is None
    assert body["retention_days"] == analytics_repo.RETENTION_DAYS == 180
    assert body["dry_run"] is False
    purge.assert_called_once_with()  # NO arguments — retention cannot be injected
    assert not count.called


def test_retention_shaped_query_params_are_ignored(monkeypatch):
    headers = _armed(monkeypatch)
    with patch.object(analytics_repo, "purge_expired", return_value=0) as purge:
        resp = client.post(URL + "?retention_days=1&days=1&interval_days=1", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["retention_days"] == analytics_repo.RETENTION_DAYS
    purge.assert_called_once_with()


# ── 2. Fail-closed kill switch ───────────────────────────────────────────────

def test_flag_unset_is_explicit_no_op_that_never_touches_repo(monkeypatch):
    headers = _armed(monkeypatch, flag=None)
    with patch.object(analytics_repo, "purge_expired") as purge, \
         patch.object(analytics_repo, "count_expired") as count:
        resp = client.post(URL, headers=headers)
    assert resp.status_code == 200  # no-op, not a failure — schedulers never page
    body = resp.json()
    assert body["status"] == "disabled"
    assert body["removed"] == 0
    assert not purge.called and not count.called


def test_flag_false_is_disabled(monkeypatch):
    headers = _armed(monkeypatch, flag="false")
    with patch.object(analytics_repo, "purge_expired") as purge:
        resp = client.post(URL, headers=headers)
    assert resp.json()["status"] == "disabled"
    assert not purge.called


# ── 3. Dry-run never deletes ─────────────────────────────────────────────────

def test_dry_run_counts_without_deleting(monkeypatch):
    headers = _armed(monkeypatch)
    with patch.object(analytics_repo, "count_expired", return_value=12) as count, \
         patch.object(analytics_repo, "purge_expired") as purge:
        resp = client.post(URL + "?dry_run=true", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "dry_run"
    assert body["removed"] == 0
    assert body["would_remove"] == 12
    assert body["dry_run"] is True
    count.assert_called_once_with()  # constant only — no caller value
    assert not purge.called


def test_dry_run_while_disabled_stays_disabled(monkeypatch):
    """The kill switch outranks dry-run: flag off means NO repository access,
    not a read-only peek."""
    headers = _armed(monkeypatch, flag="false")
    with patch.object(analytics_repo, "count_expired") as count:
        resp = client.post(URL + "?dry_run=true", headers=headers)
    body = resp.json()
    assert body["status"] == "disabled"
    assert body["dry_run"] is True  # echoed for the caller's log line
    assert not count.called


# ── 4. Cron-secret guard ─────────────────────────────────────────────────────

def test_unconfigured_secret_is_503(monkeypatch):
    monkeypatch.delenv("RICO_CRON_SECRET", raising=False)
    assert client.post(URL).status_code == 503


def test_wrong_secret_is_403(monkeypatch):
    monkeypatch.setenv("RICO_CRON_SECRET", _SECRET)
    assert client.post(URL, headers={"X-Cron-Secret": "wrong"}).status_code == 403
