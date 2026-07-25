"""Rate-limiter storage selection from the environment.

`REDIS_URL` and `RICO_REDIS_URL` are both documented as the rate-limiting
backend, but `_storage_uri()` used to read only `REDIS_URL`. An environment
configured with `RICO_REDIS_URL` alone therefore fell back to per-process
memory storage while appearing configured: counters stop being shared between
workers, so every declared limit is effectively multiplied by the worker count
and resets on restart.

The fallback is deliberately narrow: only a genuinely UNSET `REDIS_URL` defers
to `RICO_REDIS_URL`. A `REDIS_URL` that is present but empty is an explicit
opt-out meaning "force in-memory" — the CI workflow relies on exactly that — so
it must never fall through. All four combinations are pinned below.

These tests cover both halves of the fix: which variable selects the backend,
and that the memory fallback is loud in production rather than silent.
"""
from __future__ import annotations

import logging

import pytest

from src.api.rate_limit import _storage_uri

_ENV_VARS = ("REDIS_URL", "RICO_REDIS_URL", "RICO_ENV", "APP_ENV", "ENV", "ENVIRONMENT")


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Remove every variable that influences storage selection."""
    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


class TestStorageSelection:
    def test_redis_url_selects_redis(self, clean_env: pytest.MonkeyPatch) -> None:
        clean_env.setenv("REDIS_URL", "redis://redis-a:6379/0")
        assert _storage_uri() == "redis://redis-a:6379/0"

    def test_rico_redis_url_alone_selects_redis(self, clean_env: pytest.MonkeyPatch) -> None:
        """The regression: this returned 'memory://' before the fallback existed."""
        clean_env.setenv("RICO_REDIS_URL", "redis://redis-b:6379/1")
        assert _storage_uri() == "redis://redis-b:6379/1"

    def test_redis_url_takes_precedence_over_rico_redis_url(
        self, clean_env: pytest.MonkeyPatch
    ) -> None:
        clean_env.setenv("REDIS_URL", "redis://primary:6379/0")
        clean_env.setenv("RICO_REDIS_URL", "redis://fallback:6379/1")
        assert _storage_uri() == "redis://primary:6379/0"

    def test_both_absent_falls_back_to_memory(self, clean_env: pytest.MonkeyPatch) -> None:
        assert _storage_uri() == "memory://"

    @pytest.mark.parametrize("blank", ["", "   "])
    def test_empty_redis_url_forces_memory_despite_rico_redis_url(
        self, clean_env: pytest.MonkeyPatch, blank: str
    ) -> None:
        """DO NOT DELETE: an explicitly empty REDIS_URL is an opt-out, not "unset".

        `.github/workflows/qa-tests.yml:33` sets ``REDIS_URL: ""`` on purpose so
        slowapi falls back to ``memory://`` — CI has no Redis, and without that
        fallback every rate-limited route returns HTTP 500. If an empty
        REDIS_URL were allowed to fall through to RICO_REDIS_URL, any
        environment that also defines RICO_REDIS_URL would start dialling a real
        Redis inside a CI or test run. This test pins that it does not.
        """
        clean_env.setenv("REDIS_URL", blank)
        clean_env.setenv("RICO_REDIS_URL", "redis://should-never-be-used:6379/0")
        assert _storage_uri() == "memory://"

    @pytest.mark.parametrize("blank", ["", "   "])
    def test_empty_rico_redis_url_counts_as_absent(
        self, clean_env: pytest.MonkeyPatch, blank: str
    ) -> None:
        clean_env.setenv("RICO_REDIS_URL", blank)
        assert _storage_uri() == "memory://"


class TestMemoryFallbackVisibility:
    """The silent degradation is the defect — production must not whisper it."""

    @pytest.mark.parametrize("marker", ["RICO_ENV", "APP_ENV", "ENV", "ENVIRONMENT"])
    @pytest.mark.parametrize("value", ["production", "prod"])
    def test_memory_fallback_warns_in_production(
        self,
        clean_env: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
        marker: str,
        value: str,
    ) -> None:
        clean_env.setenv(marker, value)
        with caplog.at_level(logging.INFO, logger="src.api.rate_limit"):
            assert _storage_uri() == "memory://"
        records = [r for r in caplog.records if "in-memory storage" in r.message]
        assert len(records) == 1
        assert records[0].levelno == logging.WARNING

    def test_memory_fallback_stays_info_outside_production(
        self, clean_env: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        clean_env.setenv("ENVIRONMENT", "test")
        with caplog.at_level(logging.INFO, logger="src.api.rate_limit"):
            assert _storage_uri() == "memory://"
        records = [r for r in caplog.records if "in-memory storage" in r.message]
        assert len(records) == 1
        assert records[0].levelno == logging.INFO

    def test_configured_redis_does_not_warn(
        self, clean_env: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        clean_env.setenv("ENVIRONMENT", "production")
        clean_env.setenv("RICO_REDIS_URL", "redis://redis-d:6379/0")
        with caplog.at_level(logging.INFO, logger="src.api.rate_limit"):
            assert _storage_uri() == "redis://redis-d:6379/0"
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
