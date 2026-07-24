# -*- coding: utf-8 -*-
"""Regression tests for the review corrections applied to #1364 after the
correctness review found reproducible blockers against real execution paths
(not merely the PR's own helper-seeded tests).

Each test here maps to one numbered finding from that review:

  1. `_LATEST_ATTACHMENT_CONTINUATION_RE` over-matched ordinary job-search
     follow-ups ("what did you find/get") whenever ANY document was on record.
  2. An explicit ID/passport-source question fell through toward the
     unredacted generic-AI path instead of a deterministic, privacy-safe
     handler; a CV-source question never reached a real CV-specific answer.
  3. The "structured confirmations always outrank stale searches" guarantee
     was false on at least one real dispatch path (`answer_conversationally`,
     which never resolved the confirmation at all) — and two MORE reachable
     redemption sites inside `_handle_active_user_inner` were completely
     unguarded (one of them self-documented as a known gap in its own
     comment).
  4. #1364 alone did not fix its own headline motivating transcript ("a later
     0%-confidence screenshot answered from an older context") — the OCR-
     failure upload branch only wrote the durable store, never
     `recent_context`, so a stale older attachment stayed "latest".
  5. Combined with #1365's canonical context fields, `_describe_latest_attachment`
     ignored `confirmed_by_user`/`requires_confirmation`, re-asking a question
     the user had just answered.
  6. `_EXPLICIT_DOC_SOURCE_RE` matched bare "id"/"identity"/"cv" as standalone
     words with no possessive marker, false-matching ordinary prose.

All PII in this file is synthetic.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.rico_chat_api import RicoChatAPI
from src.rico_memory import RicoMemoryStore
from tests.harness.chat_harness import ChatHarness

_SYNTH_ID_NUMBER = "784-0000-SYNTHONLY-0"
_SYNTH_NAME = "Synthetic Test-Person"
_SYNTH_DOB = "01/01/1990"


def _no_sensitive_leak(text: str) -> bool:
    return all(v not in (text or "") for v in (_SYNTH_ID_NUMBER, _SYNTH_NAME, _SYNTH_DOB))


# ── Finding 1: continuation regex must not hijack job-search follow-ups ──────

@pytest.mark.parametrize("message", [
    "what did you find in the search results",
    "what did you get for the job search",
    "I wonder what did you find about the company",
    "what did you find in the job listings",
])
def test_continuation_regex_does_not_hijack_job_search_followups(message):
    assert not RicoChatAPI._LATEST_ATTACHMENT_CONTINUATION_RE.search(message)


@pytest.mark.parametrize("message", [
    "what was that?", "what did you extract", "what did you extract?",
    "what did you read from it", "what did you get from that",
    "what did you find in it", "what did I upload", "what is this file",
])
def test_continuation_regex_still_matches_genuine_attachment_questions(message):
    assert RicoChatAPI._LATEST_ATTACHMENT_CONTINUATION_RE.search(message)


def test_job_search_followup_routes_normally_even_with_stale_document_on_record():
    """End-to-end: a stale (unrelated) document on record must not hijack a
    genuine job-search follow-up question."""
    h = ChatHarness()
    user = "finding1@test.com"
    h.seed(user, cv_status="parsed", cv_filename="cv.pdf", target_roles=["Environmental Manager"],
           current_role="Environmental Manager", preferred_cities=["Dubai"],
           skills=["hse"], years_experience=6)
    h._rctx.setdefault(user, {})
    h._rctx[user]["last_uploaded_document"] = {
        "filename": "old_screenshot.png", "detected_type": "unknown",
        "document_type": "unknown", "display_label": "Unrecognized Document",
        "classification_confidence": 0.0, "confidence": 0.0, "is_sensitive": False,
    }
    r = h.say(user, "what did you find in the search results")
    assert r.get("type") != "document_context", f"must not be hijacked into an attachment reply: {r!r}"


# ── Finding 6: narrowed source regexes must not over-match ordinary prose ───

@pytest.mark.parametrize("message", [
    "id like to know more about this role",
    "id rather not say",
    "identity theft is a concern in job scams",
    "what is a valid id format for jobs in uae",
])
def test_id_source_regex_does_not_over_match_casual_prose(message):
    assert not RicoChatAPI._EXPLICIT_ID_SOURCE_RE.search(message)


@pytest.mark.parametrize("message", [
    "what did you extract from my ID?", "what's on my passport", "from my ID",
    "my Emirates ID", "tell me about my passport", "من هويتي",
])
def test_id_source_regex_matches_genuine_ownership_questions(message):
    assert RicoChatAPI._EXPLICIT_ID_SOURCE_RE.search(message)


@pytest.mark.parametrize("message", [
    "can you help me profile this job market",
    "what is a resume format used in the UAE",
    "I want to build my career",
])
def test_cv_source_regex_does_not_over_match_casual_prose(message):
    assert not RicoChatAPI._EXPLICIT_CV_SOURCE_RE.search(message)


@pytest.mark.parametrize("message", [
    "what did you extract from my CV?", "what's on my resume", "from my CV",
    "tell me about my résumé", "من سيرتي الذاتية",
])
def test_cv_source_regex_matches_genuine_ownership_questions(message):
    assert RicoChatAPI._EXPLICIT_CV_SOURCE_RE.search(message)


# ── Finding 2: explicit ID-source question never reaches unredacted AI ──────

def _sensitive_doc(**over):
    doc = {
        "filename": "synthetic_identity.png", "detected_type": "identity_document",
        "document_type": "identity_document", "display_label": "Identity Document",
        "classification_confidence": 0.95, "confidence": 0.95, "is_sensitive": True,
        "extracted_text": f"NAME: {_SYNTH_NAME}\nID: {_SYNTH_ID_NUMBER}\nDOB: {_SYNTH_DOB}",
    }
    doc.update(over)
    return doc


def test_explicit_id_source_question_never_reaches_ai_fallback():
    """The deterministic ID-source handler must answer BEFORE any AI call —
    verified by asserting _answer_with_ai_fallback / respond() is never
    invoked, not merely that the reply text happens to be clean."""
    api = RicoChatAPI(persist=False)
    doc = _sensitive_doc()
    with (
        patch.object(RicoChatAPI, "_get_recent_context", return_value={"last_uploaded_document": doc}),
        patch.object(RicoChatAPI, "_get_last_uploaded_document", return_value=doc),
        patch.object(RicoChatAPI, "_append_chat"),
        patch.object(RicoChatAPI, "_answer_with_ai_fallback") as mock_ai,
    ):
        r = api._get_recent_upload_document_reply("u@test", "what did you extract from my ID?")
    mock_ai.assert_not_called()
    assert r is not None and r["type"] == "document_context"
    assert _no_sensitive_leak(r["message"])


def test_explicit_id_source_question_honest_when_no_id_on_record():
    api = RicoChatAPI(persist=False)
    cv_doc = {"filename": "cv.pdf", "detected_type": "cv", "document_type": "cv",
              "display_label": "Resume / CV", "classification_confidence": 0.9,
              "confidence": 0.9, "is_sensitive": False}
    with (
        patch.object(RicoChatAPI, "_get_recent_context", return_value={"last_uploaded_document": cv_doc}),
        patch.object(RicoChatAPI, "_get_last_uploaded_document", return_value=cv_doc),
        patch.object(RicoChatAPI, "_append_chat"),
    ):
        r = api._get_recent_upload_document_reply("u@test", "what did you extract from my ID?")
    assert r is not None
    assert "don't have an identity document" in r["message"].lower()


def test_explicit_id_source_question_arabic_no_leak():
    api = RicoChatAPI(persist=False)
    doc = _sensitive_doc()
    with (
        patch.object(RicoChatAPI, "_get_recent_context", return_value={"last_uploaded_document": doc}),
        patch.object(RicoChatAPI, "_get_last_uploaded_document", return_value=doc),
        patch.object(RicoChatAPI, "_append_chat"),
        patch.object(RicoChatAPI, "_answer_with_ai_fallback") as mock_ai,
    ):
        r = api._get_recent_upload_document_reply("u@test", "من هويتي؟")
    mock_ai.assert_not_called()
    assert _no_sensitive_leak(r["message"])


# ── Finding 2: explicit CV-source question reaches a REAL CV handler ────────

def test_explicit_cv_source_question_reaches_real_cv_record_not_identity_doc():
    """The latest attachment is an IDENTITY document, but the user explicitly
    asks about their CV — the reply must come from the real CV record
    (_collect_uploaded_documents), never the identity document, and never
    generic AI."""
    api = RicoChatAPI(persist=False)
    identity_doc = _sensitive_doc()
    with (
        patch.object(RicoChatAPI, "_get_recent_context", return_value={"last_uploaded_document": identity_doc}),
        patch.object(RicoChatAPI, "_resolve_profile", return_value=None),
        patch.object(RicoChatAPI, "_collect_uploaded_documents", return_value=[
            {"filename": "Environmental_Manager_CV.pdf", "doc_type": "cv", "is_primary": True},
        ]),
        patch.object(RicoChatAPI, "_append_chat"),
        patch.object(RicoChatAPI, "_answer_with_ai_fallback") as mock_ai,
    ):
        r = api._get_recent_upload_document_reply("u@test", "what did you extract from my CV?")
    mock_ai.assert_not_called()
    assert r is not None
    assert "Environmental_Manager_CV.pdf" in r["message"]
    assert "synthetic_identity" not in r["message"]
    assert _no_sensitive_leak(r["message"])


def test_explicit_cv_source_question_honest_when_no_cv_on_record():
    api = RicoChatAPI(persist=False)
    with (
        patch.object(RicoChatAPI, "_get_recent_context", return_value={}),
        patch.object(RicoChatAPI, "_resolve_profile", return_value=None),
        patch.object(RicoChatAPI, "_collect_uploaded_documents", return_value=[]),
        patch.object(RicoChatAPI, "_append_chat"),
    ):
        r = api._get_recent_upload_document_reply("u@test", "what did you extract from my CV?")
    assert r is not None
    assert "don't have a cv" in r["message"].lower()


# ── Finding 3: both structured confirmations outrank stale search on every
#    reachable dispatch path ───────────────────────────────────────────────

def _seeded_harness(user: str) -> ChatHarness:
    h = ChatHarness()
    h.seed(user, cv_status="parsed", cv_filename="cv.pdf", target_roles=["Environmental Manager"],
           current_role="Environmental Manager", preferred_cities=["Dubai"],
           skills=["hse"], years_experience=6)
    return h


@pytest.mark.parametrize("message", ["نعم", "yes", "ok", "okay"])
def test_confirm_profile_update_outranks_stale_search_via_process_message(message):
    """Dispatch path: RicoChatAPI.process_message -> _handle_active_user_inner
    -> _resolve_pending_field (the primary, correctly-ordered site)."""
    user = f"f3-a-{message}@test.com"
    h = _seeded_harness(user)
    h._rctx.setdefault(user, {})
    h._rctx[user]["_pending_field"] = "confirm_profile_update"
    h._rctx[user]["_pending_profile_update"] = {"years_experience": 8}
    pending_js = {"role": "Environmental Manager"}
    before = len(h.searched_roles)
    with patch.object(RicoChatAPI, "_get_pending_job_search", return_value=pending_js):
        r = h.say(user, message)
    assert len(h.searched_roles) == before, "the stale search must not run"
    assert r.get("type") == "preferences_updated"
    assert h.profile(user).years_experience == 8


@pytest.mark.parametrize("message", ["تمام", "confirm", "continue"])
def test_ambiguous_acknowledgement_never_redeems_stale_search_when_confirmation_armed(message):
    """The two previously-unguarded sites inside _handle_active_user_inner
    (the _ACKNOWLEDGEMENT_REPLIES block and the 'Priority 1.5' block) —
    reproduced directly: before the fix, "تمام" and "confirm" redeemed the
    stale search here while the real confirmation was silently dropped. The
    profile mutation is NOT expected to apply for these ambiguous replies
    (pre-existing, intentional "neither yes nor no" behavior) — what must
    never happen is the stale search firing in its place."""
    user = f"f3-b-{message}@test.com"
    h = _seeded_harness(user)
    h._rctx.setdefault(user, {})
    h._rctx[user]["_pending_field"] = "confirm_profile_update"
    h._rctx[user]["_pending_profile_update"] = {"years_experience": 8}
    pending_js = {"role": "Environmental Manager"}
    before = len(h.searched_roles)
    with patch.object(RicoChatAPI, "_get_pending_job_search", return_value=pending_js):
        h.say(user, message)
    assert len(h.searched_roles) == before, (
        f"{message!r} must not redeem the stale search while a structured "
        "confirmation was armed"
    )


@pytest.mark.parametrize("message", ["نعم", "yes"])
def test_confirm_set_active_cv_outranks_stale_search_via_process_message(message):
    user = f"f3-c-{message}@test.com"
    h = _seeded_harness(user)
    h.seed_documents(user, [{"id": "doc-123", "doc_type": "cv", "filename": "new_cv.pdf"}])
    h._rctx.setdefault(user, {})
    h._rctx[user]["_pending_field"] = "confirm_set_active_cv"
    h._rctx[user]["_pending_active_cv"] = {"target_document_id": "doc-123"}
    pending_js = {"role": "Environmental Manager"}
    before = len(h.searched_roles)
    with patch.object(RicoChatAPI, "_get_pending_job_search", return_value=pending_js):
        r = h.say(user, message)
    assert len(h.searched_roles) == before, "the stale search must not run"
    assert r.get("type") == "active_cv_changed"


@pytest.mark.parametrize("message", ["نعم", "yes"])
def test_confirm_profile_update_outranks_stale_search_via_answer_conversationally(message):
    """Dispatch path: chat_service._conversational_ai_reply ->
    RicoChatAPI.answer_conversationally — the path with NO call to
    _resolve_pending_field before this fix, reproduced directly: the guard
    stopped the stale search but the real confirmation was never resolved,
    falling through to a generic AI reply instead."""
    api = RicoChatAPI(persist=False)
    ctx = {
        "_pending_field": "confirm_profile_update",
        "_pending_profile_update": {"years_experience": 8},
    }
    from types import SimpleNamespace
    with (
        patch.object(RicoChatAPI, "_get_recent_context", return_value=ctx),
        patch.object(RicoChatAPI, "_store_recent_context"),
        patch.object(RicoChatAPI, "_append_chat"),
        patch.object(RicoChatAPI, "_get_pending_job_search", return_value={"role": "Environmental Manager"}),
        patch("src.rico_chat_api.upsert_profile") as mock_upsert,
        patch.object(RicoChatAPI, "_answer_with_ai_fallback") as mock_ai,
    ):
        mock_upsert.return_value = SimpleNamespace(years_experience=8)
        r = api.answer_conversationally("u@test", message, profile=SimpleNamespace(years_experience=6))
    mock_ai.assert_not_called()
    assert r["type"] == "preferences_updated"
    mock_upsert.assert_called_once()


def test_no_duplicate_mutation_path_added():
    """The guard and the answer_conversationally wiring must not introduce a
    second write path — upsert_profile is called at most once per turn."""
    api = RicoChatAPI(persist=False)
    ctx = {
        "_pending_field": "confirm_profile_update",
        "_pending_profile_update": {"years_experience": 8},
    }
    from types import SimpleNamespace
    with (
        patch.object(RicoChatAPI, "_get_recent_context", return_value=ctx),
        patch.object(RicoChatAPI, "_store_recent_context"),
        patch.object(RicoChatAPI, "_append_chat"),
        patch.object(RicoChatAPI, "_get_pending_job_search", return_value={"role": "Environmental Manager"}),
        patch("src.rico_chat_api.upsert_profile") as mock_upsert,
    ):
        mock_upsert.return_value = SimpleNamespace(years_experience=8)
        api.answer_conversationally("u@test", "yes", profile=SimpleNamespace(years_experience=6))
    assert mock_upsert.call_count == 1


# ── Finding 4: end-to-end, real-store regression for the OCR-failure
#    "answered from an older context" transcript — #1364 ALONE ──────────────

@pytest.fixture()
def real_memory_store(tmp_path, monkeypatch):
    """Route RicoMemoryStore's context file to an isolated temp directory —
    exercises the REAL JSON-backed read/write round-trip (not a synthetic
    dict seeded directly into a test double), closing the exact gap the
    review found: #1364's own test bypassed this store entirely."""
    def _context_path(self, user_id):
        return tmp_path / f"context_{user_id}.json"
    monkeypatch.setattr(RicoMemoryStore, "_context_path", _context_path)
    monkeypatch.setattr("src.rico_memory._JSON_WRITE_ENABLED", True)
    return RicoMemoryStore()


def test_ocr_failed_upload_supersedes_older_attachment_end_to_end(real_memory_store):
    """Reproduces the PR's own headline transcript with #1364 ALONE (no
    #1365 code involved): an identity document is uploaded successfully
    (writes recent_context, mirroring rico_upload_cv's success branch), then
    a later screenshot fails OCR (writes recent_context via THIS fix's new
    write block, mirroring rico_upload_cv's OCR-failure branch). A real
    RicoChatAPI, reading through the real RicoMemoryStore, must describe the
    NEWEST (OCR-failed) attachment — not the stale identity document."""
    user_id = "finding4@test.com"
    mem = real_memory_store

    # Mirrors rico_upload_cv's successful-image-classification write block.
    rctx = mem.get_context(user_id, "recent_context") or {}
    rctx["last_uploaded_document"] = {
        "document_type": "identity_document",
        "display_label": "Identity Document",
        "filename": "synthetic_identity.png",
        "source": "image",
        "is_sensitive": True,
        "confidence": 0.95,
        "extracted_text": f"NAME: {_SYNTH_NAME}\nID: {_SYNTH_ID_NUMBER}",
        "suggested_actions": [],
    }
    mem.set_context(user_id, "recent_context", rctx)

    # Mirrors rico_upload_cv's OCR-failure write block — THIS fix.
    rctx = mem.get_context(user_id, "recent_context") or {}
    rctx["last_uploaded_document"] = {
        "document_type": "image",
        "display_label": "Image",
        "filename": "later_screenshot.png",
        "source": "image",
        "confidence": 0.0,
        "is_sensitive": False,
        "extracted_text": "",
        "suggested_actions": [],
    }
    mem.set_context(user_id, "recent_context", rctx)

    # api.memory is a fresh RicoMemoryStore() instance (set in __init__), but
    # the fixture patched RicoMemoryStore._context_path at the CLASS level, so
    # it transparently reads/writes the same temp-dir files as `mem` above —
    # no instance-level patch needed.
    api = RicoChatAPI(persist=False)
    doc = api._get_last_uploaded_document(user_id)
    assert doc is not None
    assert doc["filename"] == "later_screenshot.png", (
        f"must read the NEWEST attachment, got {doc!r}"
    )
    assert doc["filename"] != "synthetic_identity.png"

    reply = api._describe_latest_attachment(doc, is_ar=False)
    assert "later_screenshot.png" in reply
    assert "synthetic_identity" not in reply
    assert _no_sensitive_leak(reply)


# ── Finding 5: consuming #1365's confirmed_by_user / requires_confirmation ──

def test_confirmed_attachment_is_not_reconfirmed():
    api = RicoChatAPI(persist=False)
    doc = {
        "filename": "maybe_cv.png", "detected_type": "cv", "document_type": "cv",
        "display_label": "Resume / CV", "classification_confidence": 0.2, "confidence": 0.2,
        "is_sensitive": False, "confirmed_by_user": True, "requires_confirmation": False,
    }
    reply = api._describe_latest_attachment(doc, is_ar=False)
    assert "confirm" not in reply.lower() or "confirmed" in reply.lower()
    assert "not fully sure" not in reply.lower()
    assert "you confirmed" in reply.lower()


def test_unconfirmed_low_confidence_attachment_is_still_reconfirmed():
    api = RicoChatAPI(persist=False)
    doc = {
        "filename": "blurry.png", "detected_type": "unknown", "document_type": "unknown",
        "display_label": "Unrecognized Document", "classification_confidence": 0.1,
        "confidence": 0.1, "is_sensitive": False, "confirmed_by_user": False,
        "requires_confirmation": True,
    }
    reply = api._describe_latest_attachment(doc, is_ar=False)
    assert "not fully sure" in reply.lower() and "confirm" in reply.lower()


def test_sensitive_confirmed_attachment_still_redacts_values():
    api = RicoChatAPI(persist=False)
    doc = {
        "filename": "id.png", "detected_type": "identity_document",
        "document_type": "identity_document", "display_label": "Identity Document",
        "classification_confidence": 0.95, "confidence": 0.95, "is_sensitive": True,
        "confirmed_by_user": True, "requires_confirmation": False,
        "extracted_text": f"NAME: {_SYNTH_NAME}\nID: {_SYNTH_ID_NUMBER}",
    }
    reply = api._describe_latest_attachment(doc, is_ar=False)
    assert _no_sensitive_leak(reply)
    assert "identity document" in reply.lower()


def test_confirmation_does_not_imply_profile_or_cv_mutation():
    """_describe_latest_attachment is read-only — it must never call any
    profile/CV-mutating function, confirmed or not."""
    api = RicoChatAPI(persist=False)
    doc = {
        "filename": "maybe_cv.png", "detected_type": "cv", "document_type": "cv",
        "display_label": "Resume / CV", "classification_confidence": 0.2, "confidence": 0.2,
        "is_sensitive": False, "confirmed_by_user": True, "requires_confirmation": False,
    }
    with (
        patch("src.rico_chat_api.upsert_profile") as mock_upsert,
        patch.object(RicoChatAPI, "_activate_cv_document") as mock_activate,
    ):
        api._describe_latest_attachment(doc, is_ar=False)
    mock_upsert.assert_not_called()
    mock_activate.assert_not_called()


# ── EN + AR sanity across the fixed handlers ─────────────────────────────────

def test_confirmed_attachment_description_arabic():
    api = RicoChatAPI(persist=False)
    doc = {
        "filename": "maybe_cv.png", "detected_type": "cv", "document_type": "cv",
        "display_label": "السيرة الذاتية", "classification_confidence": 0.2, "confidence": 0.2,
        "is_sensitive": False, "confirmed_by_user": True, "requires_confirmation": False,
    }
    reply = api._describe_latest_attachment(doc, is_ar=True)
    assert "أكّدت" in reply
    assert "لست متأكّداً" not in reply
