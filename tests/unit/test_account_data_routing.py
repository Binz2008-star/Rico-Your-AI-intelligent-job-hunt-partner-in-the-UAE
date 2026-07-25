"""Account-data questions must reach their deterministic handler; career questions must not.

Two opposite failure modes of one boundary, both live-verified on production at
efcb9ce before this change:

  A. The open-ended gate stole deterministic queries. "show my applications"
     answered from the database with the reconciled total, while "Show me my
     applications" — one interposed word — returned a fabricated "Based on my
     records, I see one application in your history." Same for "list my
     applications", "What are my applications?", "How many applications have I
     sent?" and "What is my application status?".

  B. The file/document carve-out over-matched. "What documents are required for
     a UAE work visa?", "What files does an employer usually ask for?", "What
     documents do UAE employers expect?" and "What files should I bring to an
     interview?" all returned a byte-identical listing of the user's uploaded CV
     filenames with zero guidance content, while "Which certificates do nurses
     need to work in Dubai?" reached the model — proving the trigger was the
     noun "files"/"documents", not the topic.

The negative cases are therefore not defensive padding: they are the other half
of the defect. A fix that only widened the deterministic side would answer "How
many applications should I send per week in the UAE?" with the user's personal
pipeline, which is defect B with the sign flipped.

Entry points are deliberate. Gate-level tests pin the vocabulary; the
IntentRouter tests pin the decision the router actually publishes; the
chat_service tests pin which of the two mutually exclusive handlers the message
reaches. A predicate passing in isolation proves nothing about whether the
message ever arrives.
"""
from __future__ import annotations

import hashlib
from unittest.mock import patch

import pytest

from src.rico.intent.gates import (
    is_application_data_request,
    is_open_ended_question,
    _is_file_list_question,
)
from src.rico.intent.router import IntentRouter
from src.schemas.chat import RicoSessionContext
from src.services import chat_service


# ── The binding acceptance matrix ─────────────────────────────────────────────

APPLICATION_RECORDS = [
    "show my applications",
    "Show me my applications",
    "list my applications",
    "What are my applications?",
    "How many applications have I sent?",
    "What is my application status?",
    "اعرض طلباتي",
    "طلباتي",
    "كم طلب وظيفة قدمت؟",
    "ما حالة طلباتي؟",
]

FILE_INVENTORY = [
    "what files do I have?",
    "which documents are on my account?",
    "Which CV files have I uploaded?",
    "my files",
    "show my documents",
    "ملفاتي",
    "ما الملفات التي رفعتها؟",
]

MUST_REACH_MODEL = [
    # General knowledge about documents — the noun is the only thing these share
    # with an inventory request. The UAE work-visa question is plausibly the most
    # common question this product will ever receive.
    "What documents do UAE employers expect?",
    "What files should I bring to an interview?",
    "What documents are required for Emirates ID?",
    "What files do I need for a visa?",
    "What documents are required for a UAE work visa?",
    "What files does an employer usually ask for?",
    "ما المستندات المطلوبة للتوظيف في الإمارات؟",
    # Career advice that mentions applications. "Why are my applications
    # ignored?" carries the ownership word "my" and still is not a data request,
    # which is why the carve-out is frame-based rather than ownership-based.
    "How many applications should I send per week in the UAE?",
    "Why are my applications ignored?",
    "How do I list applications on LinkedIn?",
    'What does "under review" mean?',
    # Over-correction guard, pinned independently at
    # tests/unit/test_intent_gates.py::test_show_me_routes_to_ai_by_phrase_opener.
    "show me more details",
]


# ── Gate level: the vocabulary itself ─────────────────────────────────────────

class TestGateKeepsAccountDataOffTheAIPath:
    @pytest.mark.parametrize("message", APPLICATION_RECORDS)
    def test_application_records_route_to_legacy(self, message: str) -> None:
        is_open, reason = is_open_ended_question(message)
        assert is_open is False, f"{message!r} was captured by the AI gate ({reason})"

    @pytest.mark.parametrize("message", FILE_INVENTORY)
    def test_file_inventory_routes_to_legacy(self, message: str) -> None:
        is_open, reason = is_open_ended_question(message)
        assert is_open is False, f"{message!r} was captured by the AI gate ({reason})"


class TestGateReleasesCareerQuestions:
    @pytest.mark.parametrize("message", MUST_REACH_MODEL)
    def test_career_questions_reach_the_model(self, message: str) -> None:
        is_open, _ = is_open_ended_question(message)
        assert is_open is True, f"{message!r} was hijacked by a deterministic carve-out"

    @pytest.mark.parametrize("message", MUST_REACH_MODEL)
    def test_career_questions_are_not_claimed_by_the_file_carve_out(self, message: str) -> None:
        assert _is_file_list_question(message.strip()) is False

    @pytest.mark.parametrize("message", MUST_REACH_MODEL)
    def test_career_questions_are_not_claimed_by_the_application_carve_out(
        self, message: str
    ) -> None:
        assert is_application_data_request(message) is False


# ── Router entry point: the decision the router publishes ─────────────────────

class TestIntentRouterDecision:
    """Enters through IntentRouter.route(), the object both transports consume."""

    @pytest.mark.parametrize("message", APPLICATION_RECORDS + FILE_INVENTORY)
    def test_account_data_defers_to_legacy(self, message: str) -> None:
        decision = IntentRouter().route(
            message=message, user_id="u@example.com", profile_context_present=True
        )
        assert decision.should_use_ai is False
        assert decision.handler_name == "LegacyClassifier"

    @pytest.mark.parametrize("message", MUST_REACH_MODEL)
    def test_career_questions_go_to_conversational_ai(self, message: str) -> None:
        decision = IntentRouter().route(
            message=message, user_id="u@example.com", profile_context_present=True
        )
        assert decision.should_use_ai is True
        assert decision.handler_name == "ConversationalAIHandler"


# ── Transport entry point: which handler actually runs ────────────────────────

def _ctx_for(message: str) -> RicoSessionContext:
    """A distinct session per case.

    Every assertion here is about a first turn — what happens when a user opens
    with this message. Sharing one session id across the parametrised cases lets
    conversational state armed by an earlier message (pending intents, lifecycle
    context, last-turn anchors) decide a later one, which would make the suite
    assert something other than what it claims to.
    """
    digest = hashlib.md5(message.encode("utf-8")).hexdigest()[:12]
    return RicoSessionContext.for_authenticated(f"acct-routing-{digest}@example.com")


def _send(message: str):
    """Drive chat_service.send_message and report which branch was taken."""
    with patch(
        "src.repositories.profile_repo.get_profile", return_value={"cv_status": "parsed"}
    ), patch(
        "src.rico_chat_api.RicoChatAPI.answer_conversationally",
        return_value={"message": "AI", "type": "openai_response", "response_source": "openai"},
    ) as ai_path, patch(
        "src.rico_chat_api.RicoChatAPI.process_message",
        return_value={"message": "legacy", "type": "legacy"},
    ) as legacy_path:
        chat_service.send_message(ctx=_ctx_for(message), message=message)
    return ai_path, legacy_path


class TestSendMessageBoundary:
    """Enters through chat_service.send_message — the real transport entry point."""

    @pytest.mark.parametrize("message", APPLICATION_RECORDS + FILE_INVENTORY)
    def test_account_data_reaches_the_deterministic_pipeline(self, message: str) -> None:
        ai_path, legacy_path = _send(message)
        legacy_path.assert_called_once()
        ai_path.assert_not_called()

    @pytest.mark.parametrize(
        "message", [m for m in MUST_REACH_MODEL if m != "show me more details"]
    )
    def test_career_questions_reach_the_conversational_pipeline(self, message: str) -> None:
        ai_path, legacy_path = _send(message)
        ai_path.assert_called_once()
        legacy_path.assert_not_called()

    def test_show_me_more_details_is_diverted_by_the_job_listing_guard(self) -> None:
        """Pins WHY the one excluded phrase is excluded, rather than hiding it.

        "show me more details" is released by both carve-outs (asserted at gate
        and router level above), but `is_explicit_job_listing_request` returns
        True for it, so `chat_service` forces it onto the grounded search path
        at the `_force_real_search` branch — before transport ever consults the
        router's decision. That guard predates this change and this change does
        not touch any job-search predicate; the assertion below fails the moment
        that stops being true.
        """
        from src.rico.intent.gates import is_explicit_job_listing_request

        assert is_explicit_job_listing_request("show me more details") is True
        decision = IntentRouter().route(
            message="show me more details", user_id="u@example.com", profile_context_present=True
        )
        assert decision.should_use_ai is True


# ── One question, one handler ─────────────────────────────────────────────────

class TestSingleApplicationHandler:
    """Every ownership-qualified applications phrasing lands on ONE handler.

    Before this change, `_SHOW_MY_APPLICATIONS_RE` was fully anchored (^...$),
    so "show my applications" reached `_handle_application_tracking` while
    "Show me my applications" and "What is my application status?" fell through
    to a different handler with a different response shape. That difference is
    invisible to the user and defeats the point of a single reconciled answer.
    """

    @pytest.mark.parametrize("message", APPLICATION_RECORDS)
    def test_all_phrasings_reach_application_tracking(self, message: str) -> None:
        from src.rico_chat_api import RicoChatAPI

        with patch(
            "src.repositories.profile_repo.get_profile", return_value={"cv_status": "parsed"}
        ), patch(
            # rico_chat_api binds get_profile at module import, so the repo-level
            # patch above does not reach the handler chain's own lookup.
            "src.rico_chat_api.get_profile",
            return_value={"cv_status": "parsed", "target_roles": ["HSE Manager"]},
        ), patch.object(
            # First turn, no prior conversation state. tests/unit/conftest.py
            # replaces the memory store with a MagicMock whose .get() returns a
            # truthy mock for every key, which arms the context-dependent
            # resolvers that run before the tracking guard. An empty context is
            # what "a user opens with this message" actually looks like.
            RicoChatAPI,
            "_get_recent_context",
            return_value={},
        ), patch.object(
            RicoChatAPI,
            "_handle_application_tracking",
            return_value={"message": "tracking", "type": "application_tracking"},
        ) as tracking, patch.object(
            RicoChatAPI,
            "_handle_app_pipeline_summary",
            return_value={"message": "summary", "type": "application_pipeline_summary"},
        ) as summary, patch.object(
            RicoChatAPI,
            "_handle_applications_list",
            return_value={"message": "list", "type": "applications_list"},
        ) as listing, patch.object(
            RicoChatAPI, "answer_conversationally", return_value={"message": "AI", "type": "ai"}
        ) as ai_path:
            chat_service.send_message(ctx=_ctx_for(message), message=message)

        assert tracking.called, f"{message!r} did not reach _handle_application_tracking"
        assert not summary.called, f"{message!r} was answered by the pipeline-summary handler"
        assert not listing.called, f"{message!r} was answered by the applications-list handler"
        assert not ai_path.called, f"{message!r} reached the AI path"


# ── Regression: the Arabic send-verb substring collision ──────────────────────

class TestArabicSubmitVerbCollision:
    """«كم طلب وظيفة قدمت؟» must not be answered with the send-channel script.

    `_requests_application_send` matches the Arabic send verbs by SUBSTRING, and
    "قدم" ("submit") is a substring of "قدمت" ("I submitted"). So the moment the
    intent gate stopped sending this question to the model, it landed on
    `_handle_application_channel_followup` — which sits earlier in the handler
    chain than the tracking guard — and asked the user which job and which
    recruiter to send to. Widening the gate alone would have swapped one wrong
    answer for another.
    """

    def test_predicate_still_matches_the_send_verb(self) -> None:
        from src.rico_chat_api import RicoChatAPI

        # The collision itself is unchanged — this is what makes the guard necessary.
        assert RicoChatAPI._requests_application_send("كم طلب وظيفة قدمت؟") is True

    def test_channel_followup_declines_an_application_records_request(self) -> None:
        from src.rico_chat_api import RicoChatAPI

        api = RicoChatAPI.__new__(RicoChatAPI)
        assert (
            RicoChatAPI._handle_application_channel_followup(
                api, "u@example.com", "كم طلب وظيفة قدمت؟", None
            )
            is None
        )

    def test_channel_followup_still_handles_a_real_send_request(self) -> None:
        """The guard must not disarm the clarification for genuine send requests."""
        from src.rico_chat_api import RicoChatAPI

        api = RicoChatAPI.__new__(RicoChatAPI)
        result = RicoChatAPI._handle_application_channel_followup(
            api, "u@example.com", "send it to the recruiter", None
        )
        assert result is not None
        assert result["type"] == "application_channel_clarification"
