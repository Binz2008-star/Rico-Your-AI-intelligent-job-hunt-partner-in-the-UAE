"""
tests/test_chat_uploaded_documents_context.py

Tests for fix(chat): preserve uploaded document metadata in Rico context.

Covers:
- uploaded_documents is inserted into the AI context BEFORE conversation_history
  so it survives the profile-context truncation in rico_openai_runtime.
- Truncation at _PROFILE_CONTEXT_MAX_CHARS preserves uploaded_documents.
- Legacy profile-CV fallback (same as GET /api/v1/user/files) when
  user_documents is empty.
- System prompt instructs Rico to answer file-list questions from
  uploaded_documents and not to claim raw PDFs are openable.
- A file-list style message reaches the provider call with filenames,
  doc types, and the active CV present in the prompt.

All DB and provider calls are mocked — no real database or AI provider.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


def _docs_fixture():
    return [
        {
            "id": "doc-cv-1",
            "file_size": 90000,
            "filename": "Roben_Finance_CV.pdf",
            "doc_type": "cv",
            "label": "Finance CV",
            "is_primary": True,
            "skills_count": 12,
            "years_experience": 7.0,
        },
        {
            "id": "doc-cl-1",
            "file_size": 45000,
            "filename": "cover_letter_emaar.pdf",
            "doc_type": "cover_letter",
            "label": None,
            "is_primary": False,
            "skills_count": 0,
            "years_experience": None,
        },
    ]


def _history_fixture(turns: int = 8):
    return [
        {
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"turn {i}: " + ("finance manager roles in dubai with IFRS and SAP " * 4),
        }
        for i in range(turns)
    ]


def _build_ctx(docs, *, profile=None, history=None, db_available=True):
    from src.rico_chat_api import RicoChatAPI

    api = RicoChatAPI.__new__(RicoChatAPI)
    api._memory = MagicMock()
    api._memory.load_chat_history.return_value = []

    mock_db = MagicMock()
    mock_db.available = db_available
    mock_db.list_user_documents.return_value = docs

    with patch("src.rico_db.RicoDB", return_value=mock_db):
        with patch.object(api, "_get_recent_messages", return_value=history or []):
            with patch.object(api, "_recent_jobs_summary", return_value=""):
                ctx = api._build_openai_context(profile, user_id="user@x.com")
    return ctx


# ── Ordering: documents must precede conversation history ─────────────────────

class TestContextOrdering:
    def test_uploaded_documents_before_conversation_history(self):
        ctx = _build_ctx(_docs_fixture(), history=_history_fixture())
        keys = list(ctx.keys())
        assert "uploaded_documents" in keys
        assert "conversation_history" in keys
        assert keys.index("uploaded_documents") < keys.index("conversation_history")

    def test_documents_payload_fields(self):
        # #P0 identity guard: filenames are kept as an UNTRUSTED identifier
        # (filename_untrusted) beside safe structured fields; the bare
        # 'filename'/'label' keys never reach the model.
        ctx = _build_ctx(_docs_fixture())
        docs = ctx["uploaded_documents"]
        assert len(docs) == 2
        primary = [d for d in docs if d["is_primary"]]
        assert len(primary) == 1
        assert primary[0]["document_id"] == "doc-cv-1"
        assert primary[0]["doc_type"] == "cv"
        assert primary[0]["parse_status"] == "parsed"
        # `content_available` describes THIS payload, not the stored document.
        # These fixtures carry no cv_structured, so no verified evidence block
        # is assembled and the flag is correctly False even though the document
        # was parsed. Deriving it from skills_count is the defect fixed in
        # tests/test_ai_grounding_contract.py.
        assert primary[0]["content_available"] is False
        assert primary[0]["filename_untrusted"] == "Roben_Finance_CV.pdf"
        # a metadata-only file (cover letter) is kept but flagged unavailable
        other = [d for d in docs if not d["is_primary"]][0]
        assert other["content_available"] is False
        assert other["parse_status"] == "metadata_only"
        assert all("filename" not in d and "label" not in d for d in docs)

    def test_no_documents_and_no_profile_means_no_key(self):
        ctx = _build_ctx([])
        assert "uploaded_documents" not in ctx

    def test_db_unavailable_does_not_raise(self):
        ctx = _build_ctx([], db_available=False)
        assert "uploaded_documents" not in ctx


# ── Legacy profile-CV fallback ─────────────────────────────────────────────────

class TestLegacyProfileCvFallback:
    def test_profile_cv_synthesised_when_no_documents(self):
        profile = {"cv_filename": "old_profile_cv.pdf", "skills": ["excel"]}
        ctx = _build_ctx([], profile=profile)
        docs = ctx["uploaded_documents"]
        assert len(docs) == 1
        assert docs[0]["doc_type"] == "cv"
        assert docs[0]["is_primary"] is True
        assert docs[0]["is_legacy"] is True
        assert docs[0]["parse_status"] == "parsed"  # legacy profile CV was parsed
        # …but its content is not in this payload (no cv_structured resolved),
        # so the model is told metadata only. See test_ai_grounding_contract.py.
        assert docs[0]["content_available"] is False
        assert docs[0]["filename_untrusted"] == "old_profile_cv.pdf"
        assert "filename" not in docs[0]

    def test_real_documents_take_precedence_over_fallback(self):
        profile = {"cv_filename": "old_profile_cv.pdf"}
        ctx = _build_ctx(_docs_fixture(), profile=profile)
        docs = ctx["uploaded_documents"]
        assert not any(d.get("is_legacy") for d in docs)
        names = [d["filename_untrusted"] for d in docs]
        assert "old_profile_cv.pdf" not in names

    def test_profile_without_cv_filename_adds_no_key(self):
        ctx = _build_ctx([], profile={"skills": ["excel"]})
        assert "uploaded_documents" not in ctx


# ── Truncation: documents survive _PROFILE_CONTEXT_MAX_CHARS ──────────────────

class TestTruncationPreservesDocuments:
    def test_documents_survive_truncation_with_full_history(self):
        from src.rico_openai_runtime import _PROFILE_CONTEXT_MAX_CHARS

        ctx = _build_ctx(_docs_fixture(), history=_history_fixture(8))
        serialized = json.dumps(ctx, ensure_ascii=False)
        truncated = serialized[:_PROFILE_CONTEXT_MAX_CHARS]
        # The full documents payload — not just the key — must survive.
        assert "uploaded_documents" in truncated
        assert "Roben_Finance_CV.pdf" in truncated
        assert "cover_letter_emaar.pdf" in truncated
        assert '"is_primary": true' in truncated

    def test_limit_is_at_least_4000(self):
        from src.rico_openai_runtime import _PROFILE_CONTEXT_MAX_CHARS

        assert _PROFILE_CONTEXT_MAX_CHARS >= 4000


# ── System prompt guidance ─────────────────────────────────────────────────────

class TestSystemPromptGuidance:
    def test_prompt_instructs_file_list_from_uploaded_documents(self):
        from src.rico_identity import get_rico_system_prompt

        prompt = get_rico_system_prompt()
        assert "uploaded_documents" in prompt
        assert "is_primary" in prompt
        assert "filename" in prompt
        assert "doc_type" in prompt

    def test_prompt_has_raw_pdf_honesty_guardrail(self):
        from src.rico_identity import get_rico_system_prompt

        prompt = get_rico_system_prompt()
        assert "Do NOT claim you can open or read the raw contents" in prompt
        assert "metadata" in prompt


# ── End to end: file-list question reaches the provider with metadata ──────────

class TestFileListMessageReachesProvider:
    def test_provider_prompt_contains_filenames_and_active_cv(self):
        """call_openai_minimal embeds the context with uploaded_documents into
        the [User profile] section of the final provider message."""
        from src.rico_openai_runtime import call_openai_minimal

        ctx = _build_ctx(_docs_fixture(), history=_history_fixture(8))
        captured = {}

        def _fake_responses(client, model, system_prompt, final_user_message, **kwargs):
            captured["system_prompt"] = system_prompt
            captured["final_user_message"] = final_user_message
            return (
                "You have 2 uploaded files: Roben_Finance_CV.pdf (CV, active) "
                "and cover_letter_emaar.pdf (cover letter). I can only see "
                "metadata for the cover letter — its raw PDF contents are not "
                "readable unless parsed."
            )

        with patch("src.rico_openai_runtime._build_client", return_value=MagicMock()):
            with patch("src.rico_openai_runtime._call_openai_responses", side_effect=_fake_responses):
                result = call_openai_minimal(
                    "check my uploaded files",
                    profile_context=json.dumps(ctx, ensure_ascii=False),
                    provider="openai",
                )

        assert result["success"] is True
        msg = captured["final_user_message"]
        assert "[User profile]" in msg
        assert "Roben_Finance_CV.pdf" in msg
        assert "cover_letter_emaar.pdf" in msg
        assert '"is_primary": true' in msg
        # The system prompt carries the file-list behavior rules
        assert "uploaded_documents" in captured["system_prompt"]
