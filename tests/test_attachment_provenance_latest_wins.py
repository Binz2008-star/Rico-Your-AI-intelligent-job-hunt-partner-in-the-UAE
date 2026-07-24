# -*- coding: utf-8 -*-
"""Attachment provenance + latest-attachment-wins continuation (sanitized
transcript regression).

Governing invariant: attachments must be classified, remembered, described, and
handled truthfully and privately. A low-confidence classification never becomes
canonical document identity; identity-document values never contaminate a CV
summary and are never repeated in a general reply; a "what was that?"-style
follow-up resolves against the LATEST attachment, not an older
subscription/search/CV context; and a bare ``yes``/``نعم`` never redeems a
pending job search when an explicit profile-mutation confirmation is armed.

All PII here is synthetic. No real name, DOB, nationality, employer, email,
phone, ID number, card number, document image, or expiry date appears.

The production transcript this pins showed, in order: an Emirates-ID image
uploaded while multiple CVs + a career profile existed; Rico first mis-describing
it; identity fields bleeding into later CV/profile summaries; sensitive ID values
echoed back and needlessly repeated; a later 0%-confidence screenshot answered
from an older context; and a ``نعم`` (meant to confirm a name change) triggering a
job search. These tests seed the attachment context the upload path produces and
drive the real chat handler over it.
"""
from __future__ import annotations

from tests.harness.chat_harness import ChatHarness

USER = "attach-prov@test.com"

# Synthetic identity-document extraction — every value is fake.
_SYNTH_ID_NUMBER = "784-0000-SYNTHONLY-0"
_SYNTH_NAME = "Synthetic Test-Person"
_SYNTH_DOB = "01/01/1990"


def _seed_profile(h: ChatHarness, user: str) -> None:
    h.seed(
        user, cv_status="parsed", cv_filename="Environmental_Manager_CV.pdf",
        target_roles=["Environmental Manager"], current_role="Environmental Manager",
        current_company="Eco Co", preferred_cities=["Dubai"],
        skills=["hse", "environment"], years_experience=6,
    )


def _put_attachment(h: ChatHarness, user: str, **over) -> None:
    doc = {
        "filename": "synthetic_identity.png",
        "detected_type": "identity_document",
        "document_type": "identity_document",
        "display_label": "Identity Document",
        "classification_confidence": 0.04,
        "confidence": 0.04,
        "is_sensitive": True,
        "extraction_available": True,
        "confirmed_by_user": False,
        "requires_confirmation": True,
        "extracted_text": f"NAME: {_SYNTH_NAME}\nID: {_SYNTH_ID_NUMBER}\nDOB: {_SYNTH_DOB}",
    }
    doc.update(over)
    h._rctx.setdefault(user, {})
    h._rctx[user]["last_uploaded_document"] = doc


def _no_sensitive_leak(text: str) -> bool:
    return all(v not in (text or "") for v in (_SYNTH_ID_NUMBER, _SYNTH_NAME, _SYNTH_DOB))


# ── D — latest attachment wins (EN + AR) ─────────────────────────────────────

def test_latest_attachment_wins_en():
    h = ChatHarness()
    _seed_profile(h, USER)
    _put_attachment(h, USER)
    before = len(h.searched_roles)
    r = h.say(USER, "what was that?")
    assert r.get("type") == "document_context", f"must answer from the latest attachment: {r!r}"
    assert len(h.searched_roles) == before, "attachment clarification must not trigger a search"
    msg = r.get("message") or ""
    assert "synthetic_identity.png" in msg, f"must reference the latest attachment: {msg!r}"
    assert _no_sensitive_leak(msg), f"must not repeat sensitive identity values: {msg!r}"


def test_latest_attachment_wins_ar():
    h = ChatHarness()
    _seed_profile(h, USER + ".ar")
    _put_attachment(h, USER + ".ar")
    before = len(h.searched_roles)
    r = h.say(USER + ".ar", "شو هاد؟")
    assert r.get("type") == "document_context", f"Arabic continuation must answer from the latest attachment: {r!r}"
    assert len(h.searched_roles) == before, "attachment clarification must not trigger a search"
    assert _no_sensitive_leak(r.get("message") or "")


def test_newer_attachment_replaces_older_context():
    h = ChatHarness()
    _seed_profile(h, USER + ".newer")
    _put_attachment(h, USER + ".newer")  # the ID, first
    # A newer 0%-confidence screenshot arrives and becomes the latest attachment.
    _put_attachment(
        h, USER + ".newer", filename="later_screenshot.png",
        detected_type="unknown", document_type="unknown", display_label="Document",
        classification_confidence=0.0, confidence=0.0, is_sensitive=False,
        extracted_text="",
    )
    r = h.say(USER + ".newer", "what was that?")
    msg = r.get("message") or ""
    assert "later_screenshot.png" in msg, f"must reference the NEWEST attachment: {msg!r}"
    assert "synthetic_identity.png" not in msg, "must not answer from the older attachment"


# ── B — low-confidence classification is never canonical ─────────────────────

def test_low_confidence_document_not_asserted_as_canonical():
    h = ChatHarness()
    _seed_profile(h, USER + ".lowconf")
    _put_attachment(
        h, USER + ".lowconf", filename="blurry.png",
        detected_type="unknown", document_type="unknown", display_label="Document",
        classification_confidence=0.0, confidence=0.0, is_sensitive=False,
        extracted_text="",
    )
    r = h.say(USER + ".lowconf", "what was that?")
    msg = (r.get("message") or "").lower()
    assert any(w in msg for w in ("not fully sure", "best guess", "confirm")), (
        f"a 0%-confidence file must be described as uncertain, not asserted: {msg!r}"
    )


def test_low_confidence_cv_guess_asks_confirmation_not_canonical():
    h = ChatHarness()
    _seed_profile(h, USER + ".lowcv")
    _put_attachment(
        h, USER + ".lowcv", filename="maybe_cv.png",
        detected_type="cv", document_type="cv", display_label="Resume / CV",
        classification_confidence=0.2, confidence=0.2, is_sensitive=False,
        extracted_text="some text",
    )
    r = h.say(USER + ".lowcv", "what was that?")
    msg = (r.get("message") or "").lower()
    assert "confirm" in msg or "not fully sure" in msg or "best guess" in msg, (
        f"a low-confidence CV guess must not be asserted as canonical: {msg!r}"
    )


# ── C — provenance boundaries (no cross-contamination) ───────────────────────

def test_cv_source_question_not_answered_from_identity_attachment():
    h = ChatHarness()
    _seed_profile(h, USER + ".cvsrc")
    _put_attachment(h, USER + ".cvsrc", classification_confidence=0.95, confidence=0.95)
    r = h.say(USER + ".cvsrc", "what did you extract from my CV?")
    # Must NOT be answered by the latest-attachment (identity) reply.
    is_identity_reply = (
        r.get("type") == "document_context"
        and "identity document" in (r.get("message") or "").lower()
    )
    assert not is_identity_reply, (
        f"a CV-source question must not be answered from the identity attachment: {r!r}"
    )
    assert _no_sensitive_leak(r.get("message") or "")


# ── E — sensitive values never repeated in a general follow-up ───────────────

def test_general_followup_does_not_repeat_sensitive_values():
    h = ChatHarness()
    _seed_profile(h, USER + ".sens")
    _put_attachment(h, USER + ".sens", classification_confidence=0.95, confidence=0.95)
    r = h.say(USER + ".sens", "what was that?")
    assert _no_sensitive_leak(r.get("message") or ""), "general summary must not echo the ID number/name/DOB"


# ── F — no auto profile mutation; نعم does not redeem a search when a ─────────
# ── mutation confirmation is armed ───────────────────────────────────────────

def test_nam_confirms_pending_mutation_not_job_search():
    h = ChatHarness()
    _seed_profile(h, USER + ".confirm")
    h._rctx.setdefault(USER + ".confirm", {})
    # A pending job search is armed AND Rico has asked for an explicit profile
    # update confirmation (the #1361 persisted-state flow).
    h._rctx[USER + ".confirm"]["_pending_job_search"] = {"role": "Environmental Manager"}
    h._rctx[USER + ".confirm"]["_pending_field"] = "confirm_profile_update"
    h._rctx[USER + ".confirm"]["_pending_profile_update"] = {"years_experience": 8}
    before = len(h.searched_roles)
    r = h.say(USER + ".confirm", "نعم")
    assert len(h.searched_roles) == before, (
        f"نعم must resolve the pending confirmation, not redeem a job search: searched {len(h.searched_roles) - before}"
    )
    assert r.get("type") == "preferences_updated", f"نعم must confirm the pending mutation: {r!r}"
    assert h.profile(USER + ".confirm").years_experience == 8


def _guard_with_ctx(ctx: dict):
    """Build a RicoChatAPI with _get_recent_context stubbed to `ctx` and return
    its _pending_search_redemption_blocked bound method."""
    from unittest.mock import patch
    from src.rico_chat_api import RicoChatAPI

    api = RicoChatAPI()
    patcher = patch.object(api, "_get_recent_context", return_value=ctx)
    patcher.start()
    return api._pending_search_redemption_blocked


# (2) supported structured action (the profile-mutation confirmation) + stale
# pending search + affirmative → the confirmation outranks the search.
def test_guard_blocks_on_confirm_profile_update():
    blocked = _guard_with_ctx({"_pending_field": "confirm_profile_update"})
    assert blocked("u@test.com", "نعم") is True
    assert blocked("u@test.com", "yes") is True


# (2b) the #1363 active-CV switch confirmation is also a structured yes/no that
# a bare affirmative belongs to — it must likewise outrank a stale pending
# search (kept in sync with _resolve_pending_field's affirmative branches).
def test_guard_blocks_on_confirm_set_active_cv():
    blocked = _guard_with_ctx({"_pending_field": "confirm_set_active_cv"})
    assert blocked("u@test.com", "نعم") is True
    assert blocked("u@test.com", "yes") is True


# (4) explicit CV-analysis intent + pending search → CV analysis outranks.
def test_guard_blocks_on_cv_analysis_intent():
    blocked = _guard_with_ctx({})
    assert blocked("u@test.com", "analyze my CV") is True


# (5) only a pending search armed (no confirmation, no higher intent) → NOT
# blocked, so a plain "yes" still redeems the search exactly once.
def test_guard_allows_plain_affirmative_with_only_pending_search():
    blocked = _guard_with_ctx({})
    assert blocked("u@test.com", "yes") is False
    assert blocked("u@test.com", "نعم") is False


# (3) THE narrowing that this correction is about: an unrelated / stale /
# unknown / non-confirmation _pending_field must NOT suppress a valid
# "yes, run the search" — otherwise the turn silently dead-ends. Value-prompt
# fields expect a value, not a bare "yes", so they never own the affirmative.
def test_guard_does_not_block_on_unrelated_or_stale_pending_field():
    for stale in ("preferred_cities", "telegram_username", "phone", "email",
                  "some_unknown_legacy_field", ""):
        blocked = _guard_with_ctx({"_pending_field": stale})
        assert blocked("u@test.com", "yes") is False, (
            f"a non-confirmation pending field ({stale!r}) must not block a valid search 'yes'"
        )
        # …but an explicit CV-analysis intent still outranks, regardless of the field.
        assert _guard_with_ctx({"_pending_field": stale})("u@test.com", "analyze my CV") is True
