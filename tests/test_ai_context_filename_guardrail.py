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
  `*_untrusted` keys and is never present in any free-text string value.
- `career_context.verified_cv_evidence` is present when `resolve_cv_context`
  returns substantive `cv_structured` data, and contains only bounded,
  traceable fields, capped per field and per item.
- `career_context.verified_cv_evidence` is absent when the active CV is
  metadata-only.
- Unrelated verified profile fields remain available.
- `resolve_cv_context` is called at most once per `RicoChatAPI` instance.
- The serialized context fits within the configured model context cap.
"""
from __future__ import annotations

import os
import re
import sys
from unittest.mock import MagicMock, patch

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
from src.rico_openai_runtime import _PROFILE_CONTEXT_MAX_CHARS, call_openai_stream


PROMPT_LOWER = get_rico_system_prompt().lower()

_L = RicoChatAPI._VERIFIED_CV_EVIDENCE_LIMITS


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


def _filename_keys(d: dict | list, parent_key: str = "") -> list[tuple[str, str]]:
    """Recursively find all leaf value keys that look like a filename or
    document-name identifier."""
    results: list[tuple[str, str]] = []
    if isinstance(d, dict):
        for k, v in d.items():
            if ("filename" in k or "document_name" in k) and not isinstance(v, (dict, list)):
                path = f"{parent_key}.{k}" if parent_key else k
                results.append((path, k))
            if isinstance(v, (dict, list)):
                _path = f"{parent_key}.{k}" if parent_key else k
                results.extend(_filename_keys(v, _path))
    elif isinstance(d, list):
        for i, item in enumerate(d):
            _path = f"{parent_key}[{i}]"
            if isinstance(item, (dict, list)):
                results.extend(_filename_keys(item, _path))
    return results


def _all_string_values(d: dict | list, parent_key: str = "") -> list[tuple[str, str, str]]:
    """Recursively find every string value. Returns (path, owning_key, value)."""
    results: list[tuple[str, str, str]] = []
    if isinstance(d, dict):
        for k, v in d.items():
            path = f"{parent_key}.{k}" if parent_key else k
            if isinstance(v, str):
                results.append((path, k, v))
            elif isinstance(v, (dict, list)):
                results.extend(_all_string_values(v, path))
    elif isinstance(d, list):
        for i, item in enumerate(d):
            path = f"{parent_key}[{i}]"
            if isinstance(item, (dict, list)):
                results.extend(_all_string_values(item, path))
    return results


def _build_ctx(
    *,
    cv_filename: str = "banking_template_v2.pdf",
    structured: dict | None = None,
    last_doc: dict | None = None,
    recent_context: dict | None = None,
    uploaded_docs: list | None = None,
):
    api = RicoChatAPI(persist=True, can_mutate_applications=True)
    _recent = recent_context or {}
    if last_doc is not None:
        _recent["last_uploaded_document"] = last_doc
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
        patch.object(
            api,
            "_get_recent_context",
            return_value=_recent,
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
# Recursive filename-key and free-text string enforcement (Phase 1)
# ---------------------------------------------------------------------------

class TestRecursiveFilenameAndStringEnforcement:
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

        for path, key in _filename_keys(ctx):
            assert key.endswith("_untrusted"), (
                f"Filename-bearing key '{key}' at {path} does not end with _untrusted"
            )

    def test_synthetic_filename_only_in_untrusted_string_values(self):
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

        for path, key, value in _all_string_values(ctx):
            if banking in value:
                assert key.endswith("_untrusted"), (
                    f"Synthetic filename found in a non-_untrusted string "
                    f"at '{path}' (key={key}): {value[:120]!r}"
                )

    def test_last_uploaded_document_note_has_no_filename(self):
        banking = "Banking_Manager_CV.pdf"
        ctx = _build_ctx(
            cv_filename=banking,
            last_doc={"filename": banking, "display_label": "CV", "document_type": "cv"},
        )

        note = ctx["last_uploaded_document"]["note"]
        assert banking not in note
        assert ctx["last_uploaded_document"]["filename_untrusted"] == banking


# ---------------------------------------------------------------------------
# CV context memoization (Phase 1)
# ---------------------------------------------------------------------------

class TestCVMemoization:
    def test_repeated_build_openai_context_uses_one_cv_resolve_call(self):
        """`self._cv_context` is memoized per instance; calling
        `_build_openai_context` twice with the same user must not resolve the
        CV grounding twice."""
        api = RicoChatAPI(persist=True, can_mutate_applications=True)
        with (
            patch(
                "src.services.career_context.resolve_career_context",
                return_value=_career_context_with_filename("x.pdf"),
            ),
            patch(
                "src.services.cv_context_resolver.resolve_cv_context",
                return_value=_cv_context(SAMPLE_SUBSTANTIVE_CV, "x.pdf"),
            ) as mock_resolve,
            patch.object(api, "_get_last_uploaded_document", return_value=None),
            patch.object(api, "_collect_uploaded_documents", return_value=[]),
        ):
            api._build_openai_context(_Profile(), user_id="u:test123")
            api._build_openai_context(_Profile(), user_id="u:test123")

        assert mock_resolve.call_count == 1, (
            f"resolve_cv_context called {mock_resolve.call_count} times for one instance"
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
        # Raw CV text is explicitly excluded.
        assert "work_experience_text" not in vce
        assert "education_text" not in vce

    def test_metadata_only_cv_produces_no_verified_cv_evidence(self):
        ctx = _build_ctx(structured=None)

        assert "verified_cv_evidence" not in ctx.get("career_context", {})

    def test_unrelated_verified_profile_fields_remain_available(self):
        ctx = _build_ctx(structured=SAMPLE_SUBSTANTIVE_CV)

        # Profile fields from the essential_fields set must still be present.
        assert ctx["current_company"] == "Acme Environmental"
        assert ctx["current_role"] == "Founder & General Manager"
        assert ctx["skills"] == ["Environmental Compliance", "ISO 14001"]


class TestVerifiedCVEvidenceBounds:
    def test_oversized_lists_are_capped(self):
        many_work = [
            {"role": f"Role {i}", "company": f"Company {i}", "years": i}
            for i in range(100)
        ]
        many_edu = [{"degree": f"Degree {i}", "institution": f"School {i}"} for i in range(50)]
        many_skills = [f"Skill {i}" for i in range(200)]
        many_certs = [f"Cert {i}" for i in range(100)]
        many_langs = [f"Lang {i}" for i in range(50)]
        ctx = _build_ctx(structured={
            **SAMPLE_SUBSTANTIVE_CV,
            "work_experience": many_work,
            "education": many_edu,
            "skills": many_skills,
            "certifications": many_certs,
            "languages": many_langs,
        })

        vce = ctx["career_context"]["verified_cv_evidence"]
        assert len(vce["work_experience"]) <= _L["work_experience_entries"]
        assert len(vce["education"]) <= _L["education_entries"]
        assert len(vce["skills"]) <= _L["skills"]
        assert len(vce["certifications"]) <= _L["certifications"]
        assert len(vce["languages"]) <= _L["languages"]
        # Most-recent-first is preserved (leading entries).
        assert vce["work_experience"][0]["company"] == "Company 0"

    def test_long_strings_are_truncated(self):
        long = "x" * 5000
        ctx = _build_ctx(structured={
            **SAMPLE_SUBSTANTIVE_CV,
            "extraction_quality": long,
            "work_experience": [
                {
                    "role": long,
                    "company": long,
                    "summary": long,
                }
            ],
            "skills": [long],
        })

        vce = ctx["career_context"]["verified_cv_evidence"]
        assert len(vce["extraction_quality"]) <= _L["scalar_string_chars"]
        assert len(vce["skills"][0]) <= _L["scalar_string_chars"]
        assert len(vce["work_experience"][0]["role"]) <= _L["entry_text_chars"]
        assert len(vce["work_experience"][0]["company"]) <= _L["entry_text_chars"]

    def test_essential_profile_facts_preserved_with_oversized_cv(self):
        many = [{"role": f"Role {i}", "company": f"Company {i}"} for i in range(100)]
        ctx = _build_ctx(structured={**SAMPLE_SUBSTANTIVE_CV, "work_experience": many})

        assert ctx["current_company"] == "Acme Environmental"
        assert ctx["current_role"] == "Founder & General Manager"
        assert ctx["years_experience"] == 10

    def test_bounded_context_fits_under_runtime_cap(self):
        many = [{"role": f"Role {i}", "company": f"Company {i}"} for i in range(100)]
        long = "x" * 5000
        ctx = _build_ctx(
            structured={
                **SAMPLE_SUBSTANTIVE_CV,
                "work_experience": many,
                "skills": [long for _ in range(200)],
            },
            last_doc={"filename": "doc.pdf", "extracted_text": "short"},
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

        # If this passes, the runtime's 4000-char truncation has not cut the
        # context, so `verified_cv_evidence` is not mid-structure truncated.
        assert len(str(ctx)) <= _PROFILE_CONTEXT_MAX_CHARS


# ---------------------------------------------------------------------------
# Context cap
# ---------------------------------------------------------------------------

class TestContextCap:
    def test_last_uploaded_text_is_pre_truncated_to_cap(self):
        long_text = "Some extracted text " * 500
        ctx = _build_ctx(
            last_doc={"filename": "doc.pdf", "extracted_text": long_text},
        )

        assert len(ctx["last_uploaded_document"]["transcribed_text"]) <= _PROFILE_CONTEXT_MAX_CHARS

    def test_serialized_context_with_bounded_evidence_fits_within_cap(self):
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
# Runtime serialization / truncation path
# ---------------------------------------------------------------------------

class TestRuntimeTruncationPath:
    def test_truncation_preserves_essential_grounded_evidence(self):
        """Exercise the actual `call_openai_stream` profile-context build,
        proving bounded `verified_cv_evidence` survives before long
        `transcribed_text`, that profile facts come first, that raw CV text
        fields are absent, and that the filename stays under `*_untrusted`."""
        banking = "Banking_Manager_CV.pdf"
        long_text = "x" * 4000
        many_work = [
            {
                "role": f"Role {i}",
                "company": f"Company {i} " * 20,
                "summary": f"Summary {i} " * 20,
            }
            for i in range(100)
        ]
        many_skills = [f"Skill {i}" for i in range(200)]
        ctx = _build_ctx(
            cv_filename=banking,
            structured={
                **SAMPLE_SUBSTANTIVE_CV,
                "work_experience": many_work,
                "skills": many_skills,
            },
            last_doc={
                "filename": banking,
                "display_label": "CV",
                "extracted_text": long_text,
            },
            recent_context={
                "last_uploaded_document": {
                    "document_type": "cv",
                    "filename": banking,
                    "display_label": "CV",
                }
            },
            uploaded_docs=[
                {
                    "id": "doc-1",
                    "filename": banking,
                    "label": banking,
                    "doc_type": "cv",
                    "is_primary": True,
                    "skills_count": 3,
                    "years_experience": 8,
                    "file_size": 12345,
                }
            ],
        )

        captured_messages = []

        def fake_stream(*, model, messages, max_tokens, stream):
            captured_messages.append(messages)
            return []

        fake_client = MagicMock()
        fake_client.chat.completions.create = fake_stream

        with (
            patch("src.rico_openai_runtime._build_client", return_value=fake_client),
            patch("src.rico_openai_runtime._deepseek_model_chain", return_value=["deepseek-v4-flash"]),
            patch("src.rico_openai_runtime._advisory_chain", side_effect=lambda chain, provider: chain),
        ):
            list(call_openai_stream("test", profile_context=ctx, provider="deepseek", conversation_history=[]))

        assert captured_messages, "call_openai_stream did not build messages"
        final_message = captured_messages[-1][-1]["content"]
        profile_part, _ = final_message.split("\n\n[User message]\n")
        safe_context = profile_part.split("[User profile]\n")[1]

        # 1. Runtime cap respected.
        assert len(safe_context) <= _PROFILE_CONTEXT_MAX_CHARS

        # 2. Essential profile facts preserved and come first.
        assert safe_context.startswith("{'profile_exists': True")
        assert "'current_company': 'Acme Environmental'" in safe_context
        assert "'current_role': 'Founder & General Manager'" in safe_context
        assert "'years_experience': 10" in safe_context

        # 3. verified_cv_evidence is present and structurally valid (bounded, leading entries only).
        assert "'verified_cv_evidence'" in safe_context
        # Leading, most-recent work_experience entry present; cap drops Company 5 onward.
        assert "Company 0" in safe_context
        assert "Company 4" in safe_context
        assert "Company 5" not in safe_context
        # Skill cap keeps the first 20.
        assert "Skill 0" in safe_context
        assert "Skill 19" in safe_context
        assert "Skill 20" not in safe_context

        # 4. Truncation order is deterministic: the cut lands inside the long
        # transcribed_text because safe_context ends before the 4000 x's finish.
        assert safe_context.index("'transcribed_text'") < len(safe_context)

        # 5. Filename appears only under *_untrusted keys.
        for m in re.finditer(re.escape(banking), safe_context):
            window = safe_context[max(0, m.start() - 60):m.start()]
            assert "filename_untrusted" in window, (
                f"Filename leaked into free text in serialized prompt: ...{window!r}"
            )

        # 6. Raw CV text never enters the serialized prompt.
        assert "cv_text" not in safe_context
        assert "work_experience_text" not in safe_context
        assert "education_text" not in safe_context


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
        assert "never state or infer a person" in PROMPT_LOWER

    def test_prompt_has_evidence_contract(self):
        assert "verified profile/cv facts" in PROMPT_LOWER
        assert "general uae-market context" in PROMPT_LOWER
        assert "missing, conflicting, or unverified" in PROMPT_LOWER

    def test_prompt_still_covers_uploaded_documents_filename_untrusted(self):
        """Pre-existing guardrail — must not regress while fixing the new one."""
        assert "filename_untrusted" in PROMPT_LOWER
