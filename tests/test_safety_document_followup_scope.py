"""Regression tests for the "racebook" discrimination false-positive bug.

Production transcript: a user uploaded a screenshot; OCR produced malformed
text containing the substring "racebook" (not the word "race"). The user then
asked "Extract the most important information from this document." — a
completely benign request — and Rico refused with the discrimination-guard
message ("I cannot filter or recommend jobs using protected characteristics.").

Root cause (verified by direct code tracing, not assumed):

1. `RicoSafetyGuard.DISCRIMINATION_PATTERNS` used bare substrings (`r"race"`,
   `r"religion"`) with `re.search` — no word boundaries — so "racebook"
   matched "race".
2. `_handle_uploaded_document_followup` embeds the raw OCR transcript into an
   augmented prompt and sends it to `_answer_with_ai_fallback(...,
   prompt_override=augmented)`, which called `.respond(prompt_override or
   message, ...)` — meaning safety evaluated the AUGMENTED prompt (with the
   embedded OCR garbage), not the user's actual request.

This file proves: (A) safety now evaluates only the user's original message,
never OCR/document content smuggled in via `prompt_override`; (B) the
discrimination patterns no longer match benign substrings but still catch
genuine discriminatory requests; (C) the attachment-followup gate recognizes
EN+AR extract/summarize/describe/what-was-that phrasing; (D) an
OCR-extracted-but-unclassifiable document is never mislabeled as a confirmed
"Document" and never emits duplicate uncertainty warnings.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from src.rico_chat_api import RicoChatAPI
from src.rico_openai_agent import RicoOpenAIAgent
from src.rico_safety import RicoSafetyGuard
from src.services.attachment_analysis_factory import build_attachment_analysis
from src.services.document_classifier import DocumentClassifier


# ── B: regex correctness — benign tokens vs. genuine requests ───────────────

@pytest.mark.parametrize("benign_text", [
    "racebook",
    "The candidate mentioned racebook.com in their portfolio.",
    "He enjoys racecourse visits on weekends.",
    "Please embrace this opportunity.",
    "I need to trace the shipment.",
    "racing enthusiast, embraces new challenges, traces bugs for a living",
])
def test_discrimination_guard_does_not_flag_benign_substrings(benign_text):
    result = RicoSafetyGuard().check_message(benign_text)
    assert result.allowed is True


@pytest.mark.parametrize("genuine_text", [
    "Only show me jobs from candidates of a specific race.",
    "Please reject applicants based on their race.",
    "I want to filter out people by religion.",
    "I want only men for this position.",
    "Avoid candidates of a certain nationality.",
])
def test_discrimination_guard_still_blocks_genuine_requests(genuine_text):
    result = RicoSafetyGuard().check_message(genuine_text)
    assert result.allowed is False
    assert result.category == "discrimination_risk"


# ── A: safety scope separation — original message only, never OCR/prompt_override ──

def _agent_forced_to_fallback() -> RicoOpenAIAgent:
    """A RicoOpenAIAgent guaranteed to reach the deterministic, offline
    `_fallback_response` path once safety allows the message (no network
    calls) — isolates the safety-scope behavior under test."""
    agent = RicoOpenAIAgent()
    agent.openai_api_key = None
    agent.api_key = None
    agent.deepseek_api_key = None
    return agent


def test_respond_checks_original_message_not_augmented_prompt_override():
    """The exact defect: an augmented prompt embedding OCR text containing
    "racebook" must NOT trigger a safety refusal when the real user request
    (passed separately as safety_check_message) is benign."""
    agent = _agent_forced_to_fallback()
    with patch.object(type(agent), "hf_available", False):
        augmented_prompt_with_ocr_garbage = (
            "Extract the most important information from this document.\n\n"
            '[Transcribed text of the document the user just uploaded]\n'
            '"""\nracebook - Senior Analyst - Dubai\n"""\n'
        )
        result = agent.respond(
            augmented_prompt_with_ocr_garbage,
            safety_check_message="Extract the most important information from this document.",
        )
    assert result.get("type") != "safety_refusal"


def test_respond_still_refuses_genuine_discrimination_in_original_message():
    """Safety scope separation must not weaken real protections: if the
    user's OWN message (not document content) is genuinely discriminatory,
    it is still refused even when passed as safety_check_message."""
    agent = _agent_forced_to_fallback()
    with patch.object(type(agent), "hf_available", False):
        result = agent.respond(
            "some augmented prompt text",
            safety_check_message="Only show me candidates of a specific race.",
        )
    assert result["type"] == "safety_refusal"
    assert result["category"] == "discrimination_risk"


def test_respond_defaults_to_checking_user_message_when_no_override_given():
    """Backward compatible: callers that don't pass safety_check_message
    still get the original (only) message checked, unchanged behavior."""
    agent = _agent_forced_to_fallback()
    with patch.object(type(agent), "hf_available", False):
        result = agent.respond("I want only men for this position.")
    assert result["type"] == "safety_refusal"


# ── A (integration): _answer_with_ai_fallback wires safety_check_message=message ──

def test_answer_with_ai_fallback_passes_original_message_as_safety_check():
    api = RicoChatAPI(persist=False)
    captured = {}

    class _FakeAgent:
        def respond(self, prompt, user_context=None, language=None, safety_check_message=None):
            captured["prompt"] = prompt
            captured["safety_check_message"] = safety_check_message
            return {"type": "ai", "message": "ok", "success": True}

    augmented = (
        "Extract the most important information from this document.\n\n"
        '"""\nracebook - Senior Analyst - Dubai\n"""\n'
    )
    with (
        patch.object(api, "_get_openai_agent", return_value=_FakeAgent()),
        patch.object(api, "_build_openai_context", return_value={}),
        patch.object(api, "_get_blocked_questions", return_value=[]),
        patch.object(api, "_append_chat", lambda *a, **k: None),
    ):
        api._answer_with_ai_fallback(
            "u@test",
            "Extract the most important information from this document.",
            profile=None,
            save_user_message=True,
            prompt_override=augmented,
        )

    assert captured["prompt"] == augmented
    assert captured["safety_check_message"] == (
        "Extract the most important information from this document."
    )
    assert "racebook" not in captured["safety_check_message"]


# ── C: attachment follow-up gate — EN + AR extract/summarize/describe phrasing ──

@pytest.mark.parametrize("message", [
    "استخرج المعلومات المهمة من هذا المستند",
    "لخص هذا الملف",
    "لخص المستند",
    "صف هذه الصورة",
    "اقرأ هذا الملف",
    "ماذا يقول هذا المستند",
    "ماذا تقول هذه الصورة",
])
def test_document_action_message_matches_arabic_phrasing(message):
    assert RicoChatAPI.is_document_action_message(message)


@pytest.mark.parametrize("message", [
    "استخرج راتبي من العقد",  # "extract my salary from the contract" — no doc noun; must not over-match
    "ابحث عن وظائف في دبي",  # "search for jobs in Dubai" — unrelated
])
def test_document_action_message_does_not_over_match_arabic(message):
    assert not RicoChatAPI.is_document_action_message(message)


def test_document_action_message_still_matches_english_extract_phrase():
    assert RicoChatAPI.is_document_action_message(
        "Extract the most important information from this document."
    )


# ── D: truthful low-confidence / unknown-document labeling ──────────────────

def test_ocr_unmatched_text_is_not_labeled_as_confirmed_document():
    """OCR-extracted-but-unclassifiable text (confidence 0.0) must not be
    displayed as a confirmed "Document" — that reads as a classification
    when none was made."""
    classifier = DocumentClassifier()
    result = classifier._classify_text("racebook xyz123 qwerty", file_format="png")
    assert result.document_type == "unknown"
    assert result.confidence == 0.0
    assert result.display_label != "Document"
    assert "Unrecognized" in result.display_label or "Unknown" in result.display_label


def test_unknown_document_analysis_does_not_duplicate_uncertainty_warnings():
    """build_attachment_analysis must not stack the 'not sure what this is'
    warning together with a separate 'low classification confidence'
    warning for the same 0%-confidence unknown-document case."""
    classifier = DocumentClassifier()
    classification = classifier._classify_text("racebook xyz123 qwerty", file_format="png")
    analysis = build_attachment_analysis(classification, filename="upload.png")
    uncertainty_warnings = [
        w for w in analysis.warnings
        if "not sure" in w.lower() or "low classification confidence" in w.lower()
    ]
    assert len(uncertainty_warnings) == 1


# ── Full before/after transcript reproduction ────────────────────────────────

def test_full_transcript_racebook_upload_then_extract_request_not_refused():
    """Reproduces the exact reported transcript end-to-end through the real
    _handle_uploaded_document_followup path: a screenshot with malformed OCR
    text containing "racebook" is on record; the user asks to extract the
    most important information; the reply must not be a safety refusal."""
    api = RicoChatAPI(persist=False)
    durable = {
        "extracted_text": "racebook - Senior Analyst - Dubai - 5+ years exp",
        "display_label": "Unrecognized Document",
        "filename": "screenshot.png",
    }

    class _FakeAgent:
        def respond(self, prompt, user_context=None, language=None, safety_check_message=None):
            # The real RicoSafetyGuard, exercised against the ORIGINAL
            # message only — proves the end-to-end wiring, not just the unit.
            safety_result = RicoSafetyGuard().check_message(
                safety_check_message or prompt
            )
            if not safety_result.allowed:
                return {
                    "type": "safety_refusal",
                    "message": safety_result.safe_response,
                    "category": safety_result.category,
                }
            return {"type": "ai", "message": "Senior Analyst role in Dubai.", "success": True}

    with (
        patch.object(api, "_get_last_uploaded_document", return_value=durable),
        patch.object(api, "_resolve_profile", return_value=None),
        patch.object(api, "_get_openai_agent", return_value=_FakeAgent()),
        patch.object(api, "_build_openai_context", return_value={}),
        patch.object(api, "_get_blocked_questions", return_value=[]),
        patch.object(api, "_append_chat", lambda *a, **k: None),
    ):
        result = api.handle_document_action(
            "u@test", "Extract the most important information from this document."
        )

    assert result is not None
    assert result.get("type") != "safety_refusal"
    assert "cannot filter or recommend jobs using protected characteristics" not in (
        result.get("message") or ""
    )
