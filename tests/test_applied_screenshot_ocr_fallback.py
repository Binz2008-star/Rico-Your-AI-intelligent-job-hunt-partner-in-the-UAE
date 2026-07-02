# -*- coding: utf-8 -*-
"""
Applied-from-screenshot OCR fallback — 2026-07-02 owner smoke failure.

Reproduced scenario: the user uploaded a job-listings screenshot (two roles),
the document classifier returned `unknown @ 0%`, and the Arabic report
"لقد قمت بالتقديم عليها ارجوك احفظها" fell back to "which job do you mean?" —
the successfully-extracted OCR text was discarded because its use was coupled
to the classifier verdict.

Two fixes under test:
1. Arabic applied-report phrasing "قمت بالتقديم عليها" now classifies as
   application_status_update (it was `unknown`).
2. When an applied report can't be resolved to a job, the OCR text of the last
   uploaded transcript is mined for job entities regardless of classification
   confidence — one entity → one-click confirm; several → disambiguation
   buttons; none → the previous clarification, unchanged.

All DB/AI access is mocked — no live Neon / providers.
"""
from __future__ import annotations

from unittest.mock import patch

from src.rico_chat_api import RicoChatAPI


# The owner's actual smoke transcript shape (two board cards, single-line style).
OWNER_SMOKE_TRANSCRIPT = (
    "Jess Talent.com — Assistant Business Development Manager — "
    "Environmental & Geotechnical Services — Abu Dhabi, UAE\n"
    "SGS Global Marine Environmental — Biz Dev Leader — Abu Dhabi, UAE"
)

ARABIC_SMOKE_PHRASE = "لقد قمت بالتقديم عليها ارجوك احفظها"


def _api():
    return RicoChatAPI(persist=False)


def _doc(text: str, doc_type: str = "unknown") -> dict:
    return {"document_type": doc_type, "extracted_text": text, "filename": "shot.png"}


# ── Fix 1: Arabic applied-report routing ─────────────────────────────────────

def test_arabic_smoke_phrase_classifies_as_application_status_update():
    from src.agent.intelligence.intent_classifier import classify_intent, _map_intent_to_legacy
    result = classify_intent(ARABIC_SMOKE_PHRASE, has_cv_profile=True)
    assert _map_intent_to_legacy(result.intent) == "application_status_update"


def test_arabic_applied_variants_route():
    from src.agent.intelligence.intent_classifier import classify_intent, _map_intent_to_legacy
    for phrase in (
        "قمت بالتقديم على الوظيفة احفظها",
        "تقدمت عليها بالفعل",
        "لقد قمت بالتقديم",
    ):
        result = classify_intent(phrase, has_cv_profile=True)
        assert _map_intent_to_legacy(result.intent) == "application_status_update", phrase


# ── Entity extraction ─────────────────────────────────────────────────────────

def test_extract_two_jobs_from_owner_smoke_transcript():
    entities = RicoChatAPI._extract_job_entities_from_transcript(OWNER_SMOKE_TRANSCRIPT)
    assert len(entities) == 2
    assert entities[0] == {
        "title": "Assistant Business Development Manager",
        "company": "Jess Talent.com",
    }
    assert entities[1] == {
        "title": "Biz Dev Leader",
        "company": "SGS Global Marine Environmental",
    }


def test_extract_stacked_card_title_then_company():
    text = (
        "Assistant Business Development Manager\n"
        "Jess Talent.com\n"
        "Abu Dhabi, United Arab Emirates\n"
        "Easy Apply"
    )
    entities = RicoChatAPI._extract_job_entities_from_transcript(text)
    assert entities == [
        {"title": "Assistant Business Development Manager", "company": "Jess Talent.com"}
    ]


def test_extract_stacked_card_company_then_title():
    text = "SGS Global Marine Environmental\nBiz Dev Leader\nAbu Dhabi, UAE"
    entities = RicoChatAPI._extract_job_entities_from_transcript(text)
    assert entities == [
        {"title": "Biz Dev Leader", "company": "SGS Global Marine Environmental"}
    ]


def test_ui_chrome_and_locations_never_become_company():
    text = "Senior Sales Manager\n3 days ago\nEasy Apply"
    assert RicoChatAPI._extract_job_entities_from_transcript(text) == []
    text2 = "Operations Manager\nDubai, United Arab Emirates"
    assert RicoChatAPI._extract_job_entities_from_transcript(text2) == []


def test_no_entities_from_plain_prose():
    text = "This is a paragraph about the weather in the mountains. Nothing else."
    assert RicoChatAPI._extract_job_entities_from_transcript(text) == []


def test_labelled_fields_extracted():
    text = "Application received.\nPosition: QHSE Manager\nCompany: Acme Contracting"
    entities = RicoChatAPI._extract_job_entities_from_transcript(text)
    assert {"title": "QHSE Manager", "company": "Acme Contracting"} in entities


# ── Fallback handler ──────────────────────────────────────────────────────────

def test_fallback_multi_job_returns_disambiguation_options():
    api = _api()
    stored = {}
    ctx = {"last_uploaded_document": _doc(OWNER_SMOKE_TRANSCRIPT)}
    with (
        patch.object(api, "_get_recent_context", return_value=ctx),
        patch.object(api, "_store_recent_context", side_effect=lambda uid, c: stored.update(c)),
    ):
        res = api._applied_from_screenshot_fallback("u@test", arabic=True)

    assert res["type"] == "clarification"
    assert res["next_action"] == "confirm_application_from_upload"
    assert len(res["options"]) == 2
    assert res["options"][0]["message"] == (
        "Mark as applied — Assistant Business Development Manager at Jess Talent.com"
    )
    assert res["options"][1]["message"] == (
        "Mark as applied — Biz Dev Leader at SGS Global Marine Environmental"
    )
    # Both offered jobs are pre-armed so ONE click persists (no double-confirm).
    offered = stored["_pending_confirm_apply_options"]
    assert {"title": "Biz Dev Leader", "company": "SGS Global Marine Environmental"} in offered


def test_fallback_single_job_asks_one_click_confirm():
    api = _api()
    stored = {}
    text = "Assistant Business Development Manager\nJess Talent.com\nAbu Dhabi, UAE"
    ctx = {"last_uploaded_document": _doc(text)}
    with (
        patch.object(api, "_get_recent_context", return_value=ctx),
        patch.object(api, "_store_recent_context", side_effect=lambda uid, c: stored.update(c)),
    ):
        res = api._applied_from_screenshot_fallback("u@test", arabic=False)

    assert len(res["options"]) == 1
    assert res["options"][0]["message"] == (
        "Mark as applied — Assistant Business Development Manager at Jess Talent.com"
    )
    assert stored["_pending_confirm_apply"] == {
        "title": "Assistant Business Development Manager",
        "company": "Jess Talent.com",
    }
    assert "Is this the job you applied to?" in res["message"]


def test_fallback_ignores_cv_transcripts():
    api = _api()
    ctx = {"last_uploaded_document": _doc("Operations Manager\nAcme Corp", doc_type="cv")}
    with patch.object(api, "_get_recent_context", return_value=ctx):
        assert api._applied_from_screenshot_fallback("u@test", arabic=False) is None


def test_fallback_none_without_upload():
    api = _api()
    with (
        patch.object(api, "_get_recent_context", return_value={}),
        patch("src.repositories.uploaded_document_repo.get_last_uploaded_document",
              return_value=None),
    ):
        assert api._applied_from_screenshot_fallback("u@test", arabic=True) is None


# ── End-to-end: the exact owner smoke turn ────────────────────────────────────

def test_owner_smoke_turn_offers_extracted_jobs_not_no_details():
    """Arabic 'I applied, save it' + unrecognized screenshot → disambiguation
    from OCR text, NOT the 'which job do you mean?' dead end."""
    api = _api()
    ctx = {"last_uploaded_document": _doc(OWNER_SMOKE_TRANSCRIPT)}
    with (
        patch.object(api, "_get_recent_context", return_value=ctx),
        patch.object(api, "_store_recent_context"),
    ):
        res = api._handle_application_status_update("u@test", ARABIC_SMOKE_PHRASE, None)

    assert res["type"] == "clarification"
    assert res["next_action"] == "confirm_application_from_upload"
    assert len(res["options"]) == 2
    assert "Jess Talent.com" in res["message"]
    assert "SGS Global Marine Environmental" in res["message"]


def test_no_upload_still_gets_previous_clarification():
    """Non-regression: with no uploaded doc, behavior is unchanged."""
    api = _api()
    with (
        patch.object(api, "_get_recent_context", return_value={}),
        patch("src.repositories.uploaded_document_repo.get_last_uploaded_document",
              return_value=None),
    ):
        res = api._handle_application_status_update("u@test", ARABIC_SMOKE_PHRASE, None)
    assert res["type"] == "clarification"
    assert res["next_action"] == "choose_job_to_mark_applied"


# ── One-click persistence wiring ──────────────────────────────────────────────

def test_offered_option_counts_as_apply_evidence():
    """A job offered via disambiguation passes _has_apply_evidence, so the
    button's 'Mark as applied — T at C' persists without a second confirm."""
    api = _api()
    ctx = {
        "_pending_confirm_apply_options": [
            {"title": "Biz Dev Leader", "company": "SGS Global Marine Environmental"},
        ]
    }
    with patch.object(api, "_get_recent_context", return_value=ctx):
        assert api._has_apply_evidence(
            "u@test", "Biz Dev Leader", "SGS Global Marine Environmental"
        ) is True
        assert api._has_apply_evidence("u@test", "Other Job", "Other Co") is False


def test_mark_applied_button_message_matches_card_action_regex():
    """The emitted button payload must route through the existing job-card
    mark-applied interceptor, not the manual applied-status flow."""
    from src.rico_chat_api import _MARK_APPLIED_CARD_ACTION_RE
    assert _MARK_APPLIED_CARD_ACTION_RE.search(
        "Mark as applied — Assistant Business Development Manager at Jess Talent.com"
    )
