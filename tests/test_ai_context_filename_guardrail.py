"""
tests/test_ai_context_filename_guardrail.py

Regression test for a production hallucination incident: Rico told a user
"Your CV filename hints at a banking background" — inferring career facts
from a filename.

Root cause: `_build_openai_context` placed the real CV filename into the
model's context under `career_context.active_cv_filename` (no `_untrusted`
suffix), while `get_rico_system_prompt`'s identity-integrity guardrail only
ever named `uploaded_documents[].filename_untrusted`. The model had no
instruction telling it this second filename field was unsafe to infer from.

Coverage:
- `_build_openai_context` never emits the old, unguarded `active_cv_filename`
  key; it emits `active_cv_filename_untrusted` instead.
- The system prompt's identity-integrity rule explicitly names
  `career_context.active_cv_filename_untrusted`, not just the
  uploaded_documents field.
- The system prompt explicitly forbids inferring a background/employer/role
  from a filename (the exact failure mode observed in production).
"""
from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

from src.rico_chat_api import RicoChatAPI
from src.rico_identity import get_rico_system_prompt
from src.services.career_context import CareerContext


PROMPT_LOWER = get_rico_system_prompt().lower()


class _Profile:
    """Minimal stand-in — only attributes _build_openai_context reads."""
    skills = ["Environmental Compliance", "ISO 14001"]
    years_experience = 10
    target_roles = ["Environmental Manager"]
    current_company = "Acme Environmental"
    current_role = "Founder & General Manager"


def _career_context_with_filename(filename: str) -> CareerContext:
    return CareerContext(
        active_cv={"original_filename": filename, "id": "doc-1"},
        active_cv_source="primary",
        profile_years=10,
        cv_years=10,
        display_years=10,
    )


# ---------------------------------------------------------------------------
# _build_openai_context: the filename must only ever appear under the
# _untrusted-suffixed key
# ---------------------------------------------------------------------------

class TestBuildOpenAIContextFilenameGuardrail:
    def test_filename_key_is_suffixed_untrusted(self):
        api = RicoChatAPI(persist=True, can_mutate_applications=True)
        with patch(
            "src.services.career_context.resolve_career_context",
            return_value=_career_context_with_filename("banking_template_v2.pdf"),
        ):
            ctx = api._build_openai_context(_Profile(), user_id="u:test123")

        assert "career_context" in ctx
        assert "active_cv_filename_untrusted" in ctx["career_context"]
        assert ctx["career_context"]["active_cv_filename_untrusted"] == "banking_template_v2.pdf"

    def test_old_unguarded_key_never_emitted(self):
        """Regression pin: the old key name must never reappear — it carried
        no instruction telling the model it was unsafe to infer from."""
        api = RicoChatAPI(persist=True, can_mutate_applications=True)
        with patch(
            "src.services.career_context.resolve_career_context",
            return_value=_career_context_with_filename("banking_template_v2.pdf"),
        ):
            ctx = api._build_openai_context(_Profile(), user_id="u:test123")

        assert "active_cv_filename" not in ctx.get("career_context", {})


# ---------------------------------------------------------------------------
# System prompt: the guardrail must name this exact field and forbid the
# exact inference that happened in production
# ---------------------------------------------------------------------------

class TestSystemPromptCoversCareerContextFilename:
    def test_prompt_names_career_context_filename_field(self):
        assert "career_context.active_cv_filename_untrusted" in PROMPT_LOWER

    def test_prompt_forbids_inferring_background_from_filename(self):
        assert "hints at" in PROMPT_LOWER or "suggests" in PROMPT_LOWER
        assert "never state or infer a person's employer, industry, role, or background from a filename" in PROMPT_LOWER

    def test_prompt_still_covers_uploaded_documents_filename_untrusted(self):
        """Pre-existing guardrail — must not regress while fixing the new one."""
        assert "filename_untrusted" in PROMPT_LOWER
