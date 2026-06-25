"""
Document-action routing: "Summarize this document" and "Extract key information"
must BOTH stay on the deterministic document-read path when a fresh uploaded
document is on record — for public sessions too.

Production bug (#741 re-test): a public user uploaded a job screenshot; OCR read
it; "Summarize" worked (legacy document path) but "Extract the most important
information from this document." was routed down the AI path with no transcript
and paraphrased the public job-listing CTA ("I can only show you verified UAE job
listings…"). The fix routes any document action to the document-read path before
the AI/legacy intent split whenever a fresh transcript exists.

No AI/provider/DB calls — the document handler and store are mocked.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.rico_chat_api import RicoChatAPI
from src.schemas.chat import RicoSessionContext
from src.services import chat_service


def _api() -> RicoChatAPI:
    return RicoChatAPI(persist=False)


# ── RicoChatAPI public entry points ───────────────────────────────────────────

def test_is_document_action_message_matches_buttons():
    assert RicoChatAPI.is_document_action_message("Extract the most important information from this document.")
    assert RicoChatAPI.is_document_action_message("Summarize this document for me.")
    assert RicoChatAPI.is_document_action_message("Describe what's in this image.")
    assert not RicoChatAPI.is_document_action_message("Find me Developer jobs in Dubai")
    assert not RicoChatAPI.is_document_action_message("")


def test_handle_document_action_none_without_fresh_doc():
    """No fresh transcript on record → None, so normal routing proceeds."""
    api = _api()
    with patch.object(api, "_get_last_uploaded_document", return_value=None):
        assert api.handle_document_action("public:web-1", "Extract key information") is None


def test_handle_document_action_none_for_non_document_message():
    api = _api()
    with patch.object(api, "_get_last_uploaded_document", return_value={"extracted_text": "x"}) as g:
        assert api.handle_document_action("public:web-1", "Find me jobs") is None
    g.assert_not_called()  # regex gate short-circuits before any store read


def test_handle_document_action_extract_uses_transcript():
    """Fresh transcript present → AI answers from it (the transcript is in the prompt)."""
    api = _api()
    durable = {"extracted_text": "Regional GM at Yalla Pizza, Ajman.", "display_label": "Job Description"}
    captured = {}

    def _fake_ai(uid, msg, profile, *, save_user_message, language=None, prompt_override=None):
        captured["override"] = prompt_override
        return {"type": "ai", "message": "Key info: Regional GM, Ajman.", "success": True}

    with (
        patch.object(api, "_get_last_uploaded_document", return_value=durable),
        patch.object(api, "_resolve_profile", return_value=None),
        patch.object(api, "_answer_with_ai_fallback", side_effect=_fake_ai),
        patch.object(api, "_append_chat", lambda *a, **k: None),
    ):
        res = api.handle_document_action(
            "public:web-1", "Extract the most important information from this document."
        )
    assert "Yalla Pizza" in captured["override"]
    assert res["message"] == "Key info: Regional GM, Ajman."


# ── chat_service.send_message routing ─────────────────────────────────────────

def _public_ctx() -> RicoSessionContext:
    return RicoSessionContext.for_public("web-abc12345")


def _send_with_doc_handler(message, doc_reply):
    """Drive send_message with policy/gate/profile stubbed and the document
    handler returning *doc_reply*. Returns (result, intent_router_called)."""
    fake_api = MagicMock()
    fake_api.handle_document_action.return_value = doc_reply

    fake_policy = MagicMock()
    fake_policy.route = "ai"

    router_called = {"v": False}

    def _route(*a, **k):
        router_called["v"] = True
        d = MagicMock()
        d.should_use_ai = True
        return d

    with (
        patch("src.rico.policy.classify_request", return_value=fake_policy),
        patch("src.services.operation_state.is_status_followup", return_value=False),
        patch("src.services.subscription_gating.check_ai_message_allowed", return_value=None),
        patch("src.repositories.profile_repo.get_profile", return_value=None),
        patch("src.rico_chat_api.RicoChatAPI", return_value=fake_api),
        patch.object(chat_service._intent_router, "route", side_effect=_route),
    ):
        result = chat_service.send_message(
            _public_ctx(), message, operation_id=None, language=None
        )
    return result, router_called["v"]


def test_extract_routes_to_document_path_not_job_cta():
    """The exact failing case: public session, fresh doc, 'Extract…' returns the
    document reply and never reaches the intent router / public job CTA."""
    doc_reply = {"type": "document_context", "message": "Role: Regional GM. Location: Ajman.", "success": True}
    result, router_called = _send_with_doc_handler(
        "Extract the most important information from this document.", doc_reply
    )
    assert result["message"] == "Role: Regional GM. Location: Ajman."
    assert result["intent"] == "document_action"
    assert "verified" not in result["message"].lower()
    assert router_called is False  # intercepted before the AI/legacy split


def test_summarize_routes_to_document_path():
    doc_reply = {"type": "document_context", "message": "This is a Regional GM job posting.", "success": True}
    result, router_called = _send_with_doc_handler("Summarize this document for me.", doc_reply)
    assert result["message"] == "This is a Regional GM job posting."
    assert router_called is False


def test_non_document_message_falls_through_to_router():
    """When the document handler returns None, flow continues to the intent
    router (neutral message, not a job-listing request that the public guard
    would short-circuit)."""
    result, router_called = _send_with_doc_handler("hello there, how are you?", None)
    assert router_called is True
