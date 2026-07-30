"""
tests/test_ai_context_filename_guardrail.py

Regression and Phase 1 contract tests for the production hallucination
incident where Rico told a user "Your CV filename hints at a banking
background" — inferring career facts from a filename.

Grounding contract (Phase 1):
- Rico must never infer career facts from filenames or document metadata.
- Rico must ground user-specific claims only in verified evidence present in
the same model payload.

Coverage:
- `_build_openai_context` never emits the old, unguarded `active_cv_filename`
  key; it emits `active_cv_filename_untrusted` instead.
- Every filename/document-name-bearing key exposed to the model ends with
  `_untrusted`.
- A synthetic filename such as `Banking_Manager_CV.pdf` only appears under
  `*_untrusted` keys and is never treated as evidence.
- `career_context.verified_cv_evidence` is present when `resolve_cv_context`
  returns substantive `cv_structured` data, and contains only bounded,
  traceable fields.
- `career_context.verified_cv_evidence` is absent when the active CV is
  metadata-only.
- Unrelated verified profile fields remain in the context.
- The serialized context fits within the configured model context cap.
- The system prompt contains the evidence contract and explicitly names all
  filename-bearing fields.
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
from src.services.cv_context_resolver import CVContext
from src.services.cv_state import STATE_METADATA_ONLY, STATE_STRUCTURED
from src.rico_openai_runtime import _PROFILE_CONTEXT_MAX_CHARS


PROMPT_LOWER = get_rico_system_prompt().lower()


class _Profile:
    """Minimal stand-in — only attributes _build_openai_context reads."""
    skills = ["Environmental Compliance", "ISO 14001"]
    years_experience = 10
    target_roles = ["Environmental Manager"]
    current_company = "Acme Environmental"
    current_role = "Founder & General Manager"


SAMPLE_SUBSTANTIVE_CV = {
    "schema_version": 1,
    "skills": ["Environmental Compliance", "ISO 14001", "ESG Reporting"],
    "certifications": ["ISO 14001 Lead Auditor"],
    "education": [{"degree": "B.Sc. Environmental Science", "institution": "UAE University"}],
    "work_experience": [
        {
            "role": "Environmental Manager",
            "company": "Acme Environmental",
            "years": 5,
        }
    ],
    "languages": ["English", "Arabic"],
    "extraction_quality": "good",
    "years_experience_hint": 10,
}


def _career_context_with_filename(filename: str) -> CareerContext:
    return CareerContext(
        active_cv={"original_filename": filename, "id": "doc-1"},
        active_cv_source="primary",
        profile_years=10,
        cv_years=10,
        display_years=10,
    )


def _cv_context(structured: dict | None, filename: str) -> CVContext:
    return CVContext(
        state=STATE_STRUCTURED if structured else STATE_METADATA_ONLY,
        structured=structured,
        filename=filename,
        availability_reason="structured" if structured else "no_content",
    )


def _filename_keys(d: dict | list, parent_key: str = "") -> list[tuple[str, str | None]]:
    """Recursively find all leaf values with keys that look like a filename or
    document-name identifier. Returns (full_path, value) pairs."""
    results: list[tuple[str, str | None]] = []
    if isinstance(d, dict):
        for k, v in d.items():
            path = f"{parent_key}.{k}" if parent_key else k
            # Any key whose name includes 'filename' or 'document_name'.
            if ("filename" in k or "document_name" in k) and not isinstance(v, (dict, list)):
                results.append((path, v))
            if isinstance(v, (dict, list)):
                results.extend(_filename_keys(v, path))
    elif isinstance(d, list):
        for i, item in enumerate(d):
            path = f"{parent_key}[{i}]"
            if isinstance(item, (dict, list)):
                results.extend(_filename_keys(item, path))
    return results


def _build_ctx(
    *,
    cv_filename: str = "banking_template_v2.pdf",
    structured: dict | None = None,
    last_doc: dict | None = None,
    uploaded_docs: list | None = None,
):
    api = RicoChatAPI(persist=True, can_mutate_applications=True)
    with (
        patch(
            "src.services.career_context.resolve_career_context",
            return_value=_career_context_with_filename(cv_filename),
        ),
        patch(
            "src.services.cv_context_resolver.resolve_cv_context",
            return_value=_cv_context(structured, cv_filename),
        ),
        patch.object(
            api,
            "_get_last_uploaded_document",
            return_value=last_doc,
        ),
        patch.object(
            api,
            "_collect_uploaded_documents",
            return_value=uploaded_docs or [],
        ),
    ):
        return api._build_openai_context(_Profile(), user_id="u:test123")


# ---------------------------------------------------------------------------
# _build_openai_context: the filename must only ever appear under the
# _untrusted-suffixed key
# ---------------------------------------------------------------------------

class TestBuildOpenAIContextFilenameGuardrail:
    def test_filename_key_is_suffixed_untrusted(self):
        ctx = _build_ctx()

        assert "career_context" in ctx
        assert "active_cv_filename_untrusted" in ctx["career_context"]
        assert ctx["career_context"]["active_cv_filename_untrusted"] == "banking_template_v2.pdf"

    def test_old_unguarded_key_never_emitted(self):
        """Regression pin: the old key name must never reappear — it carried
        no instruction telling the model it was unsafe to infer from."""
        ctx = _build_ctx()

        assert "active_cv_filename" not in ctx.get("career_context", {})


# ---------------------------------------------------------------------------
# Recursive filename-key enforcement (Phase 1)
# ---------------------------------------------------------------------------

class TestRecursiveFilenameKeyEnforcement:
    def test_all_filename_keys_are_suffixed_untrusted(self):
        ctx = _build_ctx(
            cv_filename="Banking_Manager_CV.pdf",
            last_doc={
                "filename": "Banking_Manager_CV.pdf",
                "display_label": "CV",
                "extracted_text": "",
            },
            uploaded_docs=[
                {
                    "id": "doc-1",
                    "filename": "Banking_Manager_CV.pdf",
                    "label": "Banking Manager",
                    "doc_type": "cv",
                    "is_primary": True,
                    "skills_count": 3,
                    "years_experience": 8,
                    "file_size": 12345,
                }
            ],
        )

        filename_leaves = _filename_keys(ctx)
        assert filename_leaves, "Expected at least some filename-bearing keys in the context"

        for path, _value in filename_leaves:
            # Get the terminal key name (after the last . or [])
            terminal = path.split(".")[-1]
            terminal = terminal.split("[")[0]  # in case of list indices in path
            assert terminal.endswith("_untrusted"), (
                f"Filename-bearing key '{path}' does not end with _untrusted"
            )

    def test_banking_filename_only_under_untrusted_keys(self):
        banking = "Banking_Manager_CV.pdf"
        ctx = _build_ctx(
            cv_filename=banking,
            last_doc={"filename": banking, "display_label": "CV"},
            uploaded_docs=[
                {
                    "id": "doc-1",
                    "filename": banking,
                    "label": banking,
                    "doc_type": "cv",
                    "is_primary": True,
                    "skills_count": 0,
                    "file_size": 12345,
                }
            ],
        )

        for path, value in _filename_keys(ctx):
            assert value == banking, ("Unexpected filename value in the context: "
                                      f"'{value}' at {path}; the test fixture only supplied {banking}")
            assert path.endswith("_untrusted") or ".filename_untrusted" in path, (
                f"Banking filename found at non-_untrusted path: {path}"
            )


# ---------------------------------------------------------------------------
# Verified CV evidence (Phase 1)
# ---------------------------------------------------------------------------

class TestVerifiedCVEvidence:
    def test_substantive_cv_structured_produces_verified_cv_evidence(self):
        ctx = _build_ctx(structured=SAMPLE_SUBSTANTIVE_CV)

        vce = ctx["career_context"]["verified_cv_evidence"]
        assert vce is not None
        assert "work_experience" in vce
        assert vce["work_experience"][0]["company"] == "Acme Environmental"
        assert vce["skills"] == ["Environmental Compliance", "ISO 14001", "ESG Reporting"]
        assert vce["certifications"] == ["ISO 14001 Lead Auditor"]
        assert "education" in vce
        assert vce["languages"] == ["English", "Arabic"]
        assert vce["extraction_quality"] == "good"

        # These are intentionally excluded from the bounded, traceable set.
        assert "name" not in vce
        assert "current_role" not in vce
        assert "years_experience_hint" not in vce

    def test_metadata_only_cv_produces_no_verified_cv_evidence(self):
        ctx = _build_ctx(structured=None)

        assert "verified_cv_evidence" not in ctx.get("career_context", {})

    def test_unrelated_verified_profile_fields_remain_available(self):
        ctx = _build_ctx(structured=SAMPLE_SUBSTANTIVE_CV)

        # Profile fields from the essential_fields set must still be present.
        assert ctx["current_company"] == "Acme Environmental"
        assert ctx["current_role"] == "Founder & General Manager"
        assert ctx["skills"] == ["Environmental Compliance", "ISO 14001"]


# ---------------------------------------------------------------------------
# Context cap
# ---------------------------------------------------------------------------

class TestContextCap:
    def test_last_uploaded_text_is_pre_truncated_to_cap(self):
        """`_build_openai_context` truncates `transcribed_text` itself before the
        runtime truncation, so last-uploaded images do not blow up the context."""
        long_text = "Some extracted text " * 500
        ctx = _build_ctx(
            last_doc={"filename": "doc.pdf", "extracted_text": long_text},
        )

        assert len(ctx["last_uploaded_document"]["transcribed_text"]) <= _PROFILE_CONTEXT_MAX_CHARS

    def test_serialized_context_with_bounded_evidence_fits_within_cap(self):
        """With bounded `verified_cv_evidence` and truncated `transcribed_text`,
        the raw serialized context stays under the runtime cap."""
        ctx = _build_ctx(
            structured=SAMPLE_SUBSTANTIVE_CV,
            last_doc={"filename": "doc.pdf", "extracted_text": "short text"},
            uploaded_docs=[
                {
                    "id": "doc-1",
                    "filename": "doc.pdf",
                    "doc_type": "cv",
                    "is_primary": True,
                    "skills_count": 3,
                    "years_experience": 8,
                    "file_size": 12345,
                }
            ],
        )

        assert len(str(ctx)) <= _PROFILE_CONTEXT_MAX_CHARS


# ---------------------------------------------------------------------------
# System prompt: the guardrail must name this exact field and forbid the
# exact inference that happened in production
# ---------------------------------------------------------------------------

class TestSystemPromptCoversCareerContextFilename:
    def test_prompt_names_career_context_filename_field(self):
        assert "career_context.active_cv_filename_untrusted" in PROMPT_LOWER

    def test_prompt_names_last_uploaded_document_filename_field(self):
        assert "last_uploaded_document" in PROMPT_LOWER
        assert "filename_untrusted" in PROMPT_LOWER

    def test_prompt_forbids_inferring_background_from_filename(self):
        assert "hints at" in PROMPT_LOWER or "suggests" in PROMPT_LOWER
        assert "never state or infer a person's employer, industry, role, or background from a filename" in PROMPT_LOWER

    def test_prompt_has_evidence_contract(self):
        assert "verified profile/cv facts" in PROMPT_LOWER
        assert "general uae-market context" in PROMPT_LOWER
        assert "missing, conflicting, or unverified" in PROMPT_LOWER

    def test_prompt_still_covers_uploaded_documents_filename_untrusted(self):
        """Pre-existing guardrail — must not regress while fixing the new one."""
        assert "filename_untrusted" in PROMPT_LOWER
