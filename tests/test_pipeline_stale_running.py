"""Regression tests for the scheduler stale-'running' recovery (audit CB-4).

The pipeline_runs table is the FIFO-style trigger gate: a row stuck in 'running'
with no lease/heartbeat/timeout permanently blocked every future admin trigger
(head-of-line failure mode). A stale row must be recovered (marked failed with an
explicit reason) so the trigger can never be bricked by an unprocessable unit.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest


def _run(**overrides):
    run = {
        "run_id": 1,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "status": "running",
        "jobs_found": 0,
        "error": None,
    }
    run.update(overrides)
    return run


def _stale_started() -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()


class FakeRepo:
    def __init__(self, latest):
        self._latest = latest
        self.updates = []
        self.inserted = 0

    def get_latest(self):
        return self._latest

    def insert_run(self):
        self.inserted += 1
        return 42

    def update_run(self, run_id, status, error=None):
        self.updates.append((run_id, status, error))


class TestTriggerStaleRunningRecovery:
    @pytest.fixture(autouse=True)
    def _noop_bg(self):
        # trigger() starts a daemon thread that would call run_pipeline — never let
        # the test actually run the pipeline. Scoped to this class so the _run_bg
        # outcome tests exercise the real function.
        with patch("src.services.pipeline_service._run_bg") as mock_bg:
            mock_bg.side_effect = lambda run_id: None
            yield mock_bg

    def test_running_row_is_stale_recovered_and_new_run_inserted(self):
        repo = FakeRepo(_run(started_at=_stale_started()))

        with patch("src.services.pipeline_service.is_db_available", return_value=True), \
             patch("src.services.pipeline_service.pipeline_repo", repo):
            from src.services.pipeline_service import trigger

            trigger()

        assert repo.updates == [(1, "failed", "abandoned_stale_running")]
        assert repo.inserted == 1

    def test_recent_running_row_blocks_trigger(self):
        repo = FakeRepo(_run())

        with patch("src.services.pipeline_service.is_db_available", return_value=True), \
             patch("src.services.pipeline_service.pipeline_repo", repo):
            from src.services.pipeline_service import trigger

            with pytest.raises(RuntimeError, match="already in progress"):
                trigger()

        assert repo.updates == []
        assert repo.inserted == 0

    def test_unparseable_started_at_treated_as_stale(self):
        repo = FakeRepo(_run(started_at="not-a-timestamp"))

        with patch("src.services.pipeline_service.is_db_available", return_value=True), \
             patch("src.services.pipeline_service.pipeline_repo", repo):
            from src.services.pipeline_service import trigger

            trigger()

        assert repo.updates == [(1, "failed", "abandoned_stale_running")]
        assert repo.inserted == 1

    def test_missing_started_at_treated_as_stale(self):
        repo = FakeRepo(_run(started_at=None))

        with patch("src.services.pipeline_service.is_db_available", return_value=True), \
             patch("src.services.pipeline_service.pipeline_repo", repo):
            from src.services.pipeline_service import trigger

            trigger()

        assert repo.updates == [(1, "failed", "abandoned_stale_running")]

    def test_no_running_row_triggers_normally(self):
        repo = FakeRepo(_run(status="done"))

        with patch("src.services.pipeline_service.is_db_available", return_value=True), \
             patch("src.services.pipeline_service.pipeline_repo", repo):
            from src.services.pipeline_service import trigger

            trigger()

        assert repo.updates == []
        assert repo.inserted == 1


class TestRunBgOutcomePropagation:
    def test_nonzero_return_marks_failed(self):
        repo = FakeRepo(None)
        with patch("src.run_daily.run_pipeline", return_value=1), \
             patch("src.services.pipeline_service.pipeline_repo", repo):
            from src.services.pipeline_service import _run_bg

            _run_bg(7)

        assert repo.updates == [(7, "failed", "run_pipeline_returned_1")]

    def test_zero_return_marks_done(self):
        repo = FakeRepo(None)
        with patch("src.run_daily.run_pipeline", return_value=0), \
             patch("src.services.pipeline_service.pipeline_repo", repo):
            from src.services.pipeline_service import _run_bg

            _run_bg(7)

        assert repo.updates == [(7, "done", None)]

    def test_exception_marks_failed_with_message(self):
        repo = FakeRepo(None)
        with patch("src.run_daily.run_pipeline", side_effect=RuntimeError("boom")), \
             patch("src.services.pipeline_service.pipeline_repo", repo):
            from src.services.pipeline_service import _run_bg

            _run_bg(7)

        assert repo.updates[0][0] == 7
        assert repo.updates[0][1] == "failed"
        assert "boom" in (repo.updates[0][2] or "")


class _FakeRedis:
    """Minimal fake of the redis client interface used by distributed_lock."""

    def __init__(self):
        self.store = {}
        self.eval_calls = []

    def from_url(self, url):
        return self

    def set(self, key, val, nx=True, ex=0):
        if key in self.store:
            return None
        self.store[key] = val
        self.store[key + ":ttl"] = ex
        return True

    def get(self, key):
        return self.store.get(key)

    def eval(self, script, num_keys, key, *args):
        self.eval_calls.append(script)
        if "del" in script:  # unlock
            if self.store.get(key) == args[0]:
                self.store.pop(key, None)
        elif "expire" in script:  # renew
            if self.store.get(key) == args[0]:
                self.store[key + ":ttl"] = int(args[1])
                return 1
        return 0


class TestDistributedLock:
    """The distributed lock is the cross-process heartbeat: while a pipeline is
    running its TTL is renewed, so a long run cannot lose ownership; when the
    lock cannot be established the pipeline must NOT run (fail closed)."""

    @pytest.fixture
    def lock_env(self, monkeypatch):
        fake = _FakeRedis()
        redis_module = type("redis", (), {"from_url": fake.from_url})
        monkeypatch.setattr("src.run_daily.redis", redis_module)
        monkeypatch.setattr("src.run_daily.REDIS_AVAILABLE", True)
        monkeypatch.setattr("src.run_daily._LOCK_RENEW_INTERVAL_S", 0.02)
        return fake

    def test_renews_ttl_while_held(self, lock_env):
        import time

        from src.run_daily import distributed_lock

        with distributed_lock("rico:pipeline:running", timeout=3600) as state:
            time.sleep(0.08)
            assert state == "acquired"
            renews = [s for s in lock_env.eval_calls if "expire" in s]
            assert len(renews) >= 1, "lock TTL must be renewed while the pipeline runs"
        # Unlock script ran on exit and released the lock.
        assert any("del" in s for s in lock_env.eval_calls)
        assert lock_env.store.get("rico:pipeline:running") is None

    def test_already_running_when_lock_held(self, lock_env):
        lock_env.store["rico:pipeline:running"] = "other-owner"

        from src.run_daily import distributed_lock

        with distributed_lock("rico:pipeline:running", timeout=3600) as state:
            assert state == "already_running"

    def test_fails_closed_when_redis_unavailable(self, monkeypatch):
        redis_module = type("redis", (), {
            "from_url": lambda url: (_ for _ in ()).throw(RuntimeError("redis down"))
        })
        monkeypatch.setattr("src.run_daily.redis", redis_module)
        monkeypatch.setattr("src.run_daily.REDIS_AVAILABLE", True)

        from src.run_daily import distributed_lock

        with distributed_lock("rico:pipeline:running", timeout=3600) as state:
            assert state == "unavailable"

    def test_fails_closed_when_redis_lib_missing(self, monkeypatch):
        monkeypatch.setattr("src.run_daily.REDIS_AVAILABLE", False)

        from src.run_daily import distributed_lock

        with distributed_lock("rico:pipeline:running", timeout=3600) as state:
            assert state == "unavailable"


class TestRunPipelineLockDispatch:
    def test_returns_zero_when_another_run_in_progress(self, monkeypatch):
        from contextlib import contextmanager

        @contextmanager
        def _locked(key, timeout=3600):
            yield "already_running"

        monkeypatch.setattr("src.run_daily.distributed_lock", _locked)
        from src.run_daily import run_pipeline

        assert run_pipeline() == 0

    def test_returns_one_when_lock_unavailable(self, monkeypatch):
        from contextlib import contextmanager

        @contextmanager
        def _locked(key, timeout=3600):
            yield "unavailable"

        monkeypatch.setattr("src.run_daily.distributed_lock", _locked)
        from src.run_daily import run_pipeline

        assert run_pipeline() == 1
