"""Tests for profile import CLI command."""

import json
import pytest
from pathlib import Path
from typing import Optional
from unittest.mock import patch, MagicMock

from src.cli.import_profile import (
    _load_json,
    _resolve_user_id,
    _clean_profile,
    import_profile_file,
)


class TestLoadJson:
    """Test JSON file loading and validation."""

    def test_loads_valid_json_file(self, tmp_path):
        """Should load valid JSON object from file."""
        file_path = tmp_path / "profile.json"
        file_path.write_text('{"email": "test@example.com"}', encoding="utf-8")

        result = _load_json(str(file_path))
        assert result == {"email": "test@example.com"}

    def test_raises_FileNotFoundError_for_missing_file(self):
        """Should raise error when file does not exist."""
        with pytest.raises(FileNotFoundError, match="Profile file not found"):
            _load_json("nonexistent.json")

    def test_raises_ValueError_for_non_object_json(self, tmp_path):
        """Should raise error when JSON is not an object."""
        file_path = tmp_path / "array.json"
        file_path.write_text('["item1", "item2"]', encoding="utf-8")

        with pytest.raises(ValueError, match="must contain a JSON object"):
            _load_json(str(file_path))


class TestResolveUserId:
    """Test user_id resolution logic."""

    def test_uses_explicit_user_id_override(self):
        """--user-id flag should override file data."""
        data = {"email": "file@example.com"}
        result = _resolve_user_id(data, "override@example.com")
        assert result == "override@example.com"

    def test_falls_back_to_external_user_id(self):
        """Should use external_user_id when no override."""
        data = {"external_user_id": "ext-123"}
        result = _resolve_user_id(data, None)
        assert result == "ext-123"

    def test_falls_back_to_email(self):
        """Should use email when no override or external_user_id."""
        data = {"email": "test@example.com"}
        result = _resolve_user_id(data, None)
        assert result == "test@example.com"

    def test_falls_back_to_user_id_field(self):
        """Should use user_id field when other options missing."""
        data = {"user_id": "user-456"}
        result = _resolve_user_id(data, None)
        assert result == "user-456"

    def test_raises_error_when_no_user_id_source(self):
        """Should raise error when no user_id can be resolved."""
        data = {"name": "Test User"}
        with pytest.raises(ValueError, match="Missing user_id"):
            _resolve_user_id(data, None)

    def test_normalizes_to_lowercase(self):
        """Should normalize user_id to lowercase."""
        data = {"email": "TEST@EXAMPLE.COM"}
        result = _resolve_user_id(data, None)
        assert result == "test@example.com"

    def test_strips_whitespace(self):
        """Should strip whitespace from user_id."""
        data = {"email": "  test@example.com  "}
        result = _resolve_user_id(data, None)
        assert result == "test@example.com"


class TestCleanProfile:
    """Test profile data cleaning."""

    def test_keeps_only_allowed_fields(self):
        """Should filter to only allowed fields."""
        data = {
            "email": "test@example.com",
            "name": "Test",
            "disallowed_field": "should be removed",
        }
        result = _clean_profile(data)
        assert "email" in result
        assert "name" in result
        assert "disallowed_field" not in result

    def test_removes_none_values(self):
        """Should remove fields with None values."""
        data = {
            "email": "test@example.com",
            "phone": None,
        }
        result = _clean_profile(data)
        assert "email" in result
        assert "phone" not in result

    def test_removes_empty_strings(self):
        """Should remove fields with empty string values."""
        data = {
            "email": "test@example.com",
            "name": "",
        }
        result = _clean_profile(data)
        assert "email" in result
        assert "name" not in result

    def test_removes_empty_lists(self):
        """Should remove fields with empty list values."""
        data = {
            "email": "test@example.com",
            "skills": [],
        }
        result = _clean_profile(data)
        assert "email" in result
        assert "skills" not in result

    def test_adds_profile_creation_mode(self, tmp_path):
        """import_profile_file should stamp profile_creation_mode=file_import on the upsert."""
        file_path = tmp_path / "profile.json"
        file_path.write_text(
            json.dumps({"email": "test@example.com"}),
            encoding="utf-8",
        )

        mock_upsert = MagicMock()
        with patch("src.cli.import_profile.upsert_profile", mock_upsert), \
             patch("src.cli.import_profile.mark_onboarding_complete"), \
             patch("src.cli.import_profile.resolve_profile_context", return_value=MagicMock()):
            import_profile_file(file_path=str(file_path))

        # profile_creation_mode is stamped by import_profile_file (not _clean_profile).
        _, kwargs = mock_upsert.call_args
        assert kwargs["updates"]["profile_creation_mode"] == "file_import"


class TestImportProfileFile:
    """End-to-end profile import function tests."""

    def test_imports_valid_complete_profile(self, tmp_path, monkeypatch):
        """Should import valid profile and call repository functions."""
        file_path = tmp_path / "profile.json"
        file_path.write_text(
            json.dumps({
                "email": "test@example.com",
                "name": "Test User",
                "target_roles": ["HSE Manager"],
                "skills": ["ISO 9001"],
            }),
            encoding="utf-8"
        )

        mock_upsert = MagicMock()
        mock_mark_complete = MagicMock()
        mock_resolve_context = MagicMock()
        mock_context = MagicMock()
        mock_context.completeness_score = 0.8
        mock_context.target_roles = ["HSE Manager"]
        mock_context.preferred_cities = ["Dubai"]
        mock_resolve_context.return_value = mock_context

        with patch("src.cli.import_profile.upsert_profile", mock_upsert), \
             patch("src.cli.import_profile.mark_onboarding_complete", mock_mark_complete), \
             patch("src.cli.import_profile.resolve_profile_context", mock_resolve_context):

            result = import_profile_file(file_path=str(file_path))

        assert result["ok"] is True
        assert result["user_id"] == "test@example.com"
        assert result["completeness_score"] == 0.8
        mock_upsert.assert_called_once()
        mock_mark_complete.assert_called_once_with("test@example.com")
        mock_resolve_context.assert_called_once_with("test@example.com")

    def test_does_not_trigger_jobs_without_flag(self, tmp_path, monkeypatch):
        """Should not trigger jobs when --run-jobs is False."""
        file_path = tmp_path / "profile.json"
        file_path.write_text(
            json.dumps({"email": "test@example.com"}),
            encoding="utf-8"
        )

        with patch("src.cli.import_profile.upsert_profile"), \
             patch("src.cli.import_profile.mark_onboarding_complete"), \
             patch("src.cli.import_profile.resolve_profile_context") as mock_resolve:
            mock_resolve.return_value = MagicMock()

            result = import_profile_file(file_path=str(file_path), run_jobs=False)

        assert result.get("jobs") is None

    def test_does_not_trigger_telegram_without_flag(self, tmp_path, monkeypatch):
        """Should not send Telegram alert when --send-telegram is False."""
        file_path = tmp_path / "profile.json"
        file_path.write_text(
            json.dumps({"email": "test@example.com"}),
            encoding="utf-8"
        )

        with patch("src.cli.import_profile.upsert_profile"), \
             patch("src.cli.import_profile.mark_onboarding_complete"), \
             patch("src.cli.import_profile.resolve_profile_context") as mock_resolve:
            mock_resolve.return_value = MagicMock()

            result = import_profile_file(file_path=str(file_path), send_telegram=False)

        assert result.get("telegram") is None

    def test_runs_job_pipeline_when_jobs_flag(self, tmp_path, monkeypatch):
        """Should run the scoring pipeline and summarise results when --run-jobs is True."""
        file_path = tmp_path / "profile.json"
        file_path.write_text(
            json.dumps({"email": "test@example.com"}),
            encoding="utf-8"
        )

        mock_adapter = MagicMock()
        mock_adapter.fetch_jobs.return_value = [
            {"title": "HSE Manager", "company": "Acme"},
        ]
        mock_adapter.score_jobs.return_value = [
            ({"title": "HSE Manager", "company": "Acme"}, 0.91),
        ]

        with patch("src.cli.import_profile.upsert_profile"), \
             patch("src.cli.import_profile.mark_onboarding_complete"), \
             patch("src.cli.import_profile.resolve_profile_context", return_value=MagicMock()), \
             patch("src.rico_repo_adapter.RicoRepoAdapter", return_value=mock_adapter), \
             patch("src.profile.get_candidate_profile", return_value={"target_roles": []}):

            result = import_profile_file(file_path=str(file_path), run_jobs=True)

        assert result["jobs"]["fetched"] == 1
        assert result["jobs"]["scored"] == 1
        assert result["jobs"]["top_matches"][0]["title"] == "HSE Manager"

    def test_sends_telegram_when_telegram_flag(self, tmp_path, monkeypatch):
        """Should send a Telegram alert and mark it sent when --send-telegram is True."""
        file_path = tmp_path / "profile.json"
        file_path.write_text(
            json.dumps({"email": "test@example.com"}),
            encoding="utf-8"
        )

        mock_send = MagicMock()
        with patch("src.cli.import_profile.upsert_profile"), \
             patch("src.cli.import_profile.mark_onboarding_complete"), \
             patch("src.cli.import_profile.resolve_profile_context", return_value=MagicMock()), \
             patch("src.telegram_bot.send_telegram_message", mock_send):

            result = import_profile_file(file_path=str(file_path), send_telegram=True)

        assert result["telegram"] == "sent"
        mock_send.assert_called_once()
