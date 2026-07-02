"""
Regression tests for BUG-09: per-user exclude_keywords must not be written to
os.environ["EXCLUDE_KEYWORDS"], which is a process-global var shared across all
users and the legacy scoring pipeline.

Root cause: update_settings() previously mutated os.environ["EXCLUDE_KEYWORDS"]
with the calling user's value. If User A set exclude_keywords=["contract"], the
env var became "contract" and User B's get_settings() (no DB row) would inherit
User A's keywords as the default. The DB already correctly stores per-user rows;
the env-var write was the leak.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _clean_env():
    """Ensure EXCLUDE_KEYWORDS is absent before each test and restored after."""
    orig = os.environ.pop("EXCLUDE_KEYWORDS", None)
    yield
    if orig is None:
        os.environ.pop("EXCLUDE_KEYWORDS", None)
    else:
        os.environ["EXCLUDE_KEYWORDS"] = orig


# ── update_settings must not mutate os.environ ───────────────────────────────

class TestNoEnvVarMutation:
    def _call(self, exclude_keywords, *, db_available=False):
        with patch("src.services.settings_service.is_db_available", return_value=db_available), \
             patch("src.services.settings_service.settings_repo") as mock_repo:
            mock_repo.read.return_value = None
            from src.services.settings_service import update_settings
            return update_settings({"exclude_keywords": exclude_keywords})

    def test_update_settings_does_not_write_env_var_when_db_unavailable(self):
        assert "EXCLUDE_KEYWORDS" not in os.environ
        self._call(["contract"], db_available=False)
        assert "EXCLUDE_KEYWORDS" not in os.environ, (
            "update_settings must not write to os.environ['EXCLUDE_KEYWORDS'] "
            "(env var is process-global and leaks across users)"
        )

    def test_update_settings_does_not_write_env_var_when_db_available(self):
        assert "EXCLUDE_KEYWORDS" not in os.environ
        self._call(["software engineer"], db_available=True)
        assert "EXCLUDE_KEYWORDS" not in os.environ

    def test_clearing_keywords_does_not_write_empty_env_var(self):
        assert "EXCLUDE_KEYWORDS" not in os.environ
        self._call([], db_available=True)
        assert "EXCLUDE_KEYWORDS" not in os.environ


# ── Cross-user isolation: User B must not inherit User A's keywords ───────────

class TestCrossUserIsolation:
    def test_user_b_gets_env_default_not_user_a_keywords(self):
        """User B (no DB row) should get the env-var default, NOT User A's saved keywords."""
        with patch("src.services.settings_service.is_db_available", return_value=True), \
             patch("src.services.settings_service.settings_repo") as mock_repo:

            from src.services.settings_service import update_settings, get_settings

            # User A saves exclude_keywords=["contract"]
            mock_repo.read.return_value = {"exclude_keywords": ["contract"]}
            update_settings({"exclude_keywords": ["contract"]}, user_id="user_a")

            # Env var must NOT have been written
            assert "EXCLUDE_KEYWORDS" not in os.environ

            # User B has no DB row — should get env-var default (empty, nothing set)
            mock_repo.read.return_value = None
            b_settings = get_settings(user_id="user_b")
            assert b_settings["exclude_keywords"] == [], (
                f"User B must not inherit User A's keywords but got {b_settings['exclude_keywords']}"
            )

    def test_user_b_gets_own_db_keywords_not_user_a(self):
        """User B with their own DB row should only see their own keywords."""
        with patch("src.services.settings_service.is_db_available", return_value=True), \
             patch("src.services.settings_service.settings_repo") as mock_repo:

            from src.services.settings_service import update_settings, get_settings

            # User A saves ["linkedin"]
            mock_repo.read.return_value = {"exclude_keywords": ["linkedin"]}
            update_settings({"exclude_keywords": ["linkedin"]}, user_id="user_a")

            # User B has their own row ["remote"]
            mock_repo.read.return_value = {"exclude_keywords": ["remote"]}
            b_settings = get_settings(user_id="user_b")
            assert b_settings["exclude_keywords"] == ["remote"]
            assert "linkedin" not in b_settings["exclude_keywords"]


# ── Env-var default still works as process-level fallback ────────────────────

class TestEnvVarFallback:
    def test_process_level_env_var_used_when_no_db_row(self):
        """The EXCLUDE_KEYWORDS env var remains valid as a process-level default."""
        os.environ["EXCLUDE_KEYWORDS"] = "remote,linkedin"
        with patch("src.services.settings_service.is_db_available", return_value=True), \
             patch("src.services.settings_service.settings_repo") as mock_repo:
            mock_repo.read.return_value = None  # no row → env var is the default
            from src.services.settings_service import get_settings
            settings = get_settings(user_id="user_no_row")
        assert settings["exclude_keywords"] == ["remote", "linkedin"]

    def test_db_row_overrides_env_var_for_that_user(self):
        """A user with a DB row should NOT see the process-level env default."""
        os.environ["EXCLUDE_KEYWORDS"] = "remote"
        with patch("src.services.settings_service.is_db_available", return_value=True), \
             patch("src.services.settings_service.settings_repo") as mock_repo:
            mock_repo.read.return_value = {"exclude_keywords": []}
            from src.services.settings_service import get_settings
            settings = get_settings(user_id="user_with_row")
        assert settings["exclude_keywords"] == []
