"""
Uploaded image/document transcript must reach the AI context.

Bug: after the upload route reads an image (vision/OCR) it stores the transcript
in ``recent_context.last_uploaded_document.extracted_text``, but the AI context
builder never surfaced it — so follow-up actions ("Summarize this document",
"Extract key information") answered with no document text and were inaccurate.

Fix: ``_build_openai_context`` injects the recent transcript so the AI answers
from the actual document text.

Mocks/fixtures only — no AI/provider calls.
"""
from __future__ import annotations

from unittest.mock import patch

from src.rico_chat_api import RicoChatAPI


def _api() -> RicoChatAPI:
    return RicoChatAPI(persist=False)


def _ctx_with(api, recent_context):
    """Build the AI context with everything but recent_context stubbed out."""
    with (
        patch.object(api, "_collect_uploaded_documents", return_value=[]),
        patch.object(api, "_get_recent_messages", return_value=[]),
        patch.object(api, "_recent_jobs_summary", return_value=None),
        patch.object(api, "_get_recent_context", return_value=recent_context),
    ):
        return api._build_openai_context(None, user_id="u-img")


def test_transcript_injected_into_ai_context():
    api = _api()
    ctx = _ctx_with(api, {
        "last_uploaded_document": {
            "filename": "crypto-job.png",
            "display_label": "Job Description",
            "document_type": "job_description",
            "extracted_text": "Product Design Manager at Crypto.com. Location: Dubai.",
        }
    })
    doc = ctx.get("last_uploaded_document")
    assert doc is not None
    assert doc["transcribed_text"] == "Product Design Manager at Crypto.com. Location: Dubai."
    assert doc["type"] == "Job Description"
    assert doc["filename"] == "crypto-job.png"


def test_no_transcript_when_absent():
    api = _api()
    ctx = _ctx_with(api, {})
    assert "last_uploaded_document" not in ctx


def test_no_transcript_when_text_empty():
    api = _api()
    ctx = _ctx_with(api, {"last_uploaded_document": {"filename": "x.png", "extracted_text": ""}})
    assert "last_uploaded_document" not in ctx


def test_transcript_truncated_to_4000_chars():
    api = _api()
    ctx = _ctx_with(api, {"last_uploaded_document": {"extracted_text": "x" * 9000}})
    assert len(ctx["last_uploaded_document"]["transcribed_text"]) == 4000


def test_type_falls_back_to_document_type():
    api = _api()
    ctx = _ctx_with(api, {"last_uploaded_document": {"document_type": "contract", "extracted_text": "This agreement..."}})
    assert ctx["last_uploaded_document"]["type"] == "contract"
