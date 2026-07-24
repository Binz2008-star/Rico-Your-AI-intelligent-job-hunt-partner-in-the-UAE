# -*- coding: utf-8 -*-
"""Task 3 slice 2 — canonical latest-attachment context emission + user
attachment-type clarification.

Every upload write-site emits one consistent `last_uploaded_document` structure
(via build_last_uploaded_context) carrying the provenance/confidence fields the
continuation + provenance layers consume; a newer attachment atomically replaces
the older; a low-confidence classification stays unconfirmed; and a user
clarification ("this is my ID" / "هذه هويتي") updates that attachment's confirmed
type in session context ONLY — never the profile or the active CV.

All PII is synthetic.
"""
from __future__ import annotations

from src.services.attachment_analysis_factory import (
    build_last_uploaded_context,
    normalize_detected_type,
)
from tests.harness.chat_harness import ChatHarness

USER = "canon-attach@test.com"

_CANONICAL_KEYS = {
    "attachment_id", "filename", "detected_type", "classification_confidence",
    "extraction_available", "confirmed_by_user", "requires_confirmation",
    "is_sensitive", "source_turn_id", "created_at",
}


# ── build_last_uploaded_context: shape + truthful defaults ───────────────────

def test_canonical_structure_has_all_fields():
    ctx = build_last_uploaded_context(filename="f.png", document_type="cv", confidence=0.9)
    assert _CANONICAL_KEYS.issubset(ctx.keys()), f"missing canonical fields: {_CANONICAL_KEYS - ctx.keys()}"
    # legacy fields kept for existing consumers (superset, not a break)
    assert {"document_type", "display_label", "confidence", "suggested_actions"}.issubset(ctx.keys())


def test_detected_type_normalization():
    assert normalize_detected_type("cv") == "cv"
    assert normalize_detected_type("resume") == "cv"
    assert normalize_detected_type("identity_document") == "identity_document"
    assert normalize_detected_type("passport") == "identity_document"
    assert normalize_detected_type("job_description") == "job_document"
    assert normalize_detected_type("offer_letter") == "job_document"
    assert normalize_detected_type("invoice") == "unknown"
    assert normalize_detected_type(None) == "unknown"


def test_low_confidence_stays_unconfirmed():
    ctx = build_last_uploaded_context(filename="blurry.png", document_type="cv", confidence=0.2)
    assert ctx["confirmed_by_user"] is False
    assert ctx["requires_confirmation"] is True, "a low-confidence file must require confirmation"


def test_identity_document_is_flagged_sensitive_and_unconfirmed():
    ctx = build_last_uploaded_context(filename="id.png", document_type="identity_document", confidence=0.95)
    assert ctx["detected_type"] == "identity_document"
    assert ctx["is_sensitive"] is True
    assert ctx["confirmed_by_user"] is False
    assert ctx["requires_confirmation"] is True, "an unconfirmed identity doc must require confirmation"


def test_confident_non_sensitive_document_does_not_require_confirmation():
    ctx = build_last_uploaded_context(filename="offer.pdf", document_type="offer_letter", confidence=0.9)
    assert ctx["detected_type"] == "job_document"
    assert ctx["is_sensitive"] is False
    assert ctx["requires_confirmation"] is False


def test_extraction_available_reflects_text():
    with_text = build_last_uploaded_context(filename="a.png", document_type="cv", confidence=0.9, extracted_text="hello")
    without = build_last_uploaded_context(filename="b.png", document_type="cv", confidence=0.9, extracted_text="")
    assert with_text["extraction_available"] is True
    assert without["extraction_available"] is False


def test_newer_context_replaces_older_atomically():
    """The write-site assigns the returned dict wholesale, so a newer attachment
    fully supersedes the older — no stale fields from the previous record."""
    old = build_last_uploaded_context(filename="id.png", document_type="identity_document", confidence=0.9)
    new = build_last_uploaded_context(filename="screenshot.png", document_type="unknown", confidence=0.0)
    # Simulate the write-site's wholesale assignment.
    stored = new
    assert stored["filename"] == "screenshot.png"
    assert stored["detected_type"] == "unknown"
    assert stored["is_sensitive"] is False
    assert stored["attachment_id"] != old["attachment_id"], "each attachment gets a fresh id"


# ── user attachment-type clarification updates the attachment ONLY ───────────

def _seed_with_attachment(h: ChatHarness, user: str, **doc_over):
    h.seed(
        user, cv_status="parsed", cv_filename="Environmental_Manager_CV.pdf",
        target_roles=["Environmental Manager"], years_experience=6,
    )
    doc = build_last_uploaded_context(
        filename="synthetic_upload.png", document_type="cv", confidence=0.3,
    )
    doc.update(doc_over)
    h._rctx.setdefault(user, {})
    h._rctx[user]["last_uploaded_document"] = doc


def test_this_is_my_id_updates_attachment_type_only():
    h = ChatHarness()
    u = USER + ".idclar"
    _seed_with_attachment(h, u)  # misclassified as low-confidence CV
    before_years = h.profile(u).years_experience
    before_cv = h.profile(u).cv_filename

    r = h.say(u, "this is my ID")
    assert r.get("type") == "document_context", f"clarification must be handled deterministically: {r!r}"
    assert not h.searched_roles, "a clarification must not trigger a search"

    doc = h._rctx[u]["last_uploaded_document"]
    assert doc["detected_type"] == "identity_document"
    assert doc["is_sensitive"] is True
    assert doc["confirmed_by_user"] is True
    assert doc["requires_confirmation"] is False
    # Profile / active CV untouched.
    assert h.profile(u).years_experience == before_years
    assert h.profile(u).cv_filename == before_cv


def test_arabic_this_is_my_id_updates_attachment_only():
    h = ChatHarness()
    u = USER + ".idclarar"
    _seed_with_attachment(h, u)
    r = h.say(u, "هذه هويتي")
    assert r.get("type") == "document_context"
    assert not h.searched_roles
    assert h._rctx[u]["last_uploaded_document"]["detected_type"] == "identity_document"
    assert h._rctx[u]["last_uploaded_document"]["confirmed_by_user"] is True


def test_clarification_without_attachment_is_ignored():
    h = ChatHarness()
    u = USER + ".noattach"
    h.seed(u, cv_status="parsed", cv_filename="cv.pdf", target_roles=["Environmental Manager"])
    r = h.say(u, "this is my ID")
    # No attachment on record → not handled here; normal routing proceeds.
    assert not (r.get("type") == "document_context" and "identity document" in (r.get("message") or "").lower())


def test_clarification_reports_failure_when_store_fails():
    """Failure truth: if persisting the clarification fails, Rico must NOT claim
    it was recorded — it returns success=False and an honest message, and does
    not touch the profile/CV."""
    from unittest.mock import patch
    from src.rico_chat_api import RicoChatAPI

    doc = build_last_uploaded_context(filename="synthetic_upload.png", document_type="cv", confidence=0.3)
    ctx = {"last_uploaded_document": doc}
    api = RicoChatAPI()
    with patch.object(api, "_get_recent_context", return_value=ctx), \
         patch.object(api, "_store_recent_context", side_effect=RuntimeError("store down")), \
         patch.object(api, "_append_chat"):
        r = api._handle_attachment_type_clarification("u@test.com", "this is my ID")
    assert isinstance(r, dict)
    assert r.get("success") is False, "a failed store must not be reported as a successful clarification"
    assert "identity document" not in (r.get("message") or "").lower() or "couldn't save" in (r.get("message") or "").lower()


def test_two_consecutive_uploads_latest_wins_at_context_level():
    """Two uploads in a row: the second canonical record fully replaces the
    first in recent-context, so a follow-up resolves against the newest."""
    h = ChatHarness()
    u = USER + ".twoup"
    h.seed(u, cv_status="parsed", cv_filename="cv.pdf", target_roles=["Environmental Manager"])
    h._rctx.setdefault(u, {})
    # First upload: an identity document.
    h._rctx[u]["last_uploaded_document"] = build_last_uploaded_context(
        filename="first_id.png", document_type="identity_document", confidence=0.9,
    )
    # Second upload arrives and replaces it wholesale (as the write-site does).
    h._rctx[u]["last_uploaded_document"] = build_last_uploaded_context(
        filename="second_screenshot.png", document_type="unknown", confidence=0.0,
    )
    doc = h._rctx[u]["last_uploaded_document"]
    assert doc["filename"] == "second_screenshot.png"
    assert doc["detected_type"] == "unknown"
    assert doc["is_sensitive"] is False, "no stale sensitive flag from the older attachment"


def test_this_is_my_cv_clarification_updates_type_not_profile():
    h = ChatHarness()
    u = USER + ".cvclar"
    _seed_with_attachment(h, u, detected_type="identity_document", document_type="identity_document",
                          display_label="Identity Document", is_sensitive=True)
    before_cv = h.profile(u).cv_filename
    r = h.say(u, "this is my CV")
    assert r.get("type") == "document_context"
    doc = h._rctx[u]["last_uploaded_document"]
    assert doc["detected_type"] == "cv"
    assert doc["is_sensitive"] is False
    assert doc["confirmed_by_user"] is True
    # active CV unchanged — clarification never swaps the canonical CV.
    assert h.profile(u).cv_filename == before_cv
