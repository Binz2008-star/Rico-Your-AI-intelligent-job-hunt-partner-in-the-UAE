"""Regression tests for rico_apply_ai single-call optimization."""

from unittest.mock import MagicMock, patch

import pytest

from src.rico_apply_ai import _parse_tailored_output, tailor_application


class TestParseTailoredOutput:
    """Unit tests for the marked-output parser."""

    def test_extracts_both_sections(self):
        text = (
            "Some preamble\n"
            "[TAILORED_CV]\n"
            "Rewritten CV line one.\n"
            "Rewritten CV line two.\n"
            "[/TAILORED_CV]\n"
            "[COVER_LETTER]\n"
            "Dear Hiring Manager,\n\nCover letter body.\n\nSincerely, Name\n"
            "[/COVER_LETTER]\n"
        )
        result = _parse_tailored_output(text)
        assert result is not None
        assert "Rewritten CV line one" in result["tailored_cv"]
        assert "Dear Hiring Manager" in result["cover_letter"]

    def test_returns_none_when_cv_missing(self):
        text = "[COVER_LETTER]\nLetter\n[/COVER_LETTER]"
        assert _parse_tailored_output(text) is None

    def test_returns_none_when_cover_letter_missing(self):
        text = "[TAILORED_CV]\nCV\n[/TAILORED_CV]"
        assert _parse_tailored_output(text) is None

    def test_returns_none_when_sections_empty(self):
        text = "[TAILORED_CV]  [/TAILORED_CV]\n[COVER_LETTER]  [/COVER_LETTER]"
        assert _parse_tailored_output(text) is None


class TestTailorApplication:
    """Regression tests for tailor_application single-call behavior."""

    def test_single_call_returns_parsed_sections(self):
        job = {
            "title": "HSE Manager",
            "company": "Test Company",
            "description": "Looking for HSE experience.",
            "location": "Dubai",
        }
        profile = {
            "name": "Candidate Name",
            "target_roles": ["HSE Manager"],
        }
        cv_text = "Original CV with safety experience."

        marked_response = (
            "[TAILORED_CV]\nTailored CV content.\n[/TAILORED_CV]\n"
            "[COVER_LETTER]\nDear Hiring Manager,\n\nCover.\n\nSincerely, Candidate\n[/COVER_LETTER]"
        )

        fake_client = MagicMock()
        fake_client.responses.create.return_value = MagicMock(
            output=[
                MagicMock(
                    content=[MagicMock(type="output_text", text=marked_response)]
                )
            ]
        )

        with patch("src.rico_apply_ai._get_ai_client", return_value=(fake_client, "openai", "gpt-4o-mini")):
            with patch("src.rico_apply_ai._call_ai") as mock_call:
                mock_call.return_value = marked_response
                result = tailor_application(cv_text, profile, job)

        assert result["tailored_cv"] == "Tailored CV content."
        assert result["cover_letter"] == "Dear Hiring Manager,\n\nCover.\n\nSincerely, Candidate"
        assert mock_call.call_count == 1

    def test_single_call_passes_max_tokens_for_combined_output(self):
        job = {
            "title": "HSE Manager",
            "company": "Test Company",
            "description": "Looking for HSE experience.",
            "location": "Dubai",
        }
        profile = {"name": "Candidate Name"}
        cv_text = "Original CV."

        with patch("src.rico_apply_ai._get_ai_client", return_value=(MagicMock(), "openai", "gpt-4o-mini")):
            with patch("src.rico_apply_ai._call_ai") as mock_call:
                mock_call.return_value = (
                    "[TAILORED_CV]CV[/TAILORED_CV]\n"
                    "[COVER_LETTER]Letter[/COVER_LETTER]"
                )
                tailor_application(cv_text, profile, job)

        assert mock_call.call_count == 1
        # The combined call should request more output tokens than the old default.
        _, kwargs = mock_call.call_args
        assert kwargs.get("max_tokens") == 3500

    def test_invalid_output_falls_back_to_keyword(self):
        job = {
            "title": "HSE Manager",
            "company": "Test Company",
            "description": "Looking for HSE experience.",
        }
        profile = {"name": "Candidate Name"}
        cv_text = "Original CV."

        with patch("src.rico_apply_ai._get_ai_client", return_value=(MagicMock(), "openai", "gpt-4o-mini")):
            with patch("src.rico_apply_ai._call_ai", return_value="unmarked plain text"):
                result = tailor_application(cv_text, profile, job)

        assert result["tailored_cv"] == cv_text
        assert "HSE Manager" in result["cover_letter"]
