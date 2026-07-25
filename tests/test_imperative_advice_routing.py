"""
tests/test_imperative_advice_routing.py

Imperative advice requests must reach the model (PR-A, router semantics).

Live-verified defect (production, 2026-07-25, commit bcc71e9): genuine advice
requests phrased as IMPERATIVES carry no question mark and no interrogative
opening token, so `is_open_ended_question` returned (False, "ok") and they fell
through to the legacy classifier, which answered them with a canned template:

  * "Give me one short tip to improve my CV for UAE employers"
      -> "Your CV on file is **X**. Ask me to analyze or review it and I will."
         (src/rico_chat_api.py:13981) — a deflection, not an answer.
  * "List exactly four interview questions a Dubai bank would ask a compliance
     officer, numbered one to four"
      -> "## Interview Preparation Guide{role_line}" (src/rico_chat_api.py:19968)
         — injected a role the user never mentioned and ignored the count.

The interrogative form of the same request ("Why does a UAE employer prefer GCC
banking experience") already worked, which is what isolated the gate as the
cause rather than the doc-action or job-listing predicates.

Deterministic and provider-free: every assertion is made at the routing layer
(`is_open_ended_question` / `IntentRouter.route` / `should_stream_ai`). No AI
provider, no DB, no network.

TRANSPORT: this change corrects the SEMANTIC decision only. `should_stream_ai`
derives eligibility from the same gate, so the newly model-bound classes are
explicitly held BUFFERED — the streaming branch bypasses the whole-text
post-processing in `respond()` (`_preserve_ai_message` blocked-question
filtering at rico_chat_api.py:8013 and promise-only detection at :8023), so
diverting new traffic onto it as a side effect would silently skip the safety
pass for exactly the prompts we just started sending to the model. Enabling
streaming for these classes is a separate, deliberate change. These tests pin
that hold, and pin that previously-eligible prompts are untouched.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("JWT_SECRET", "x" * 32)

from src.rico.intent.gates import (
    ADVICE_IMPERATIVE_REASON,
    is_advice_imperative_message,
    is_explicit_job_listing_request,
    is_open_ended_question,
)
from src.rico.intent.router import IntentRouter
from src.rico_chat_api import RicoChatAPI

# The owner's exact live prompts.
CV_TIP_PROMPT = "Give me one short tip to improve my CV for UAE employers"
INTERVIEW_PROMPT = (
    "List exactly four interview questions a Dubai bank would ask a "
    "compliance officer, numbered one to four"
)
WORKING_PROMPT = "Why does a UAE employer prefer GCC banking experience"


def _model_bound(message: str, *, profile_present: bool = True) -> bool:
    """Would the router send this to the conversational-AI (reasoning) path?"""
    decision = IntentRouter().route(
        message=message, user_id="u@example.com", profile_context_present=profile_present
    )
    return decision.should_use_ai


def _streams(message: str):
    """should_stream_ai for an authenticated user WITH a profile.

    A real profile is required: with profile=None on a non-persisting session the
    `_force_ai` branch masks the gate's own verdict.
    """
    from src.schemas.chat import RicoSessionContext
    from src.services.chat_service import should_stream_ai

    ctx = RicoSessionContext.for_authenticated("u@example.com")
    return should_stream_ai(ctx, message, object())


# ── Mandatory regression tests: the owner's exact live prompts ────────────────

class TestLiveDefectPrompts:
    def test_cv_tip_request_is_model_bound_not_the_cv_deflection(self):
        """(1) Must NOT route to the CV-on-file deflection at rico_chat_api.py:13981.

        That deflection is only reachable via the legacy classifier, so proving
        the router chooses the reasoning path proves the deflection is bypassed
        — without invoking a provider.
        """
        is_open, reason = is_open_ended_question(CV_TIP_PROMPT)
        assert is_open is True, "CV advice request must reach the model"
        assert reason == ADVICE_IMPERATIVE_REASON
        assert _model_bound(CV_TIP_PROMPT) is True
        # The predicates that run BEFORE the router must not claim it either,
        # or it would be short-circuited to a deterministic handler.
        assert is_explicit_job_listing_request(CV_TIP_PROMPT) is False
        assert RicoChatAPI.is_document_action_message(CV_TIP_PROMPT) is False

    def test_interview_questions_request_is_model_bound_not_the_template(self):
        """(2) Must NOT route to the Interview Preparation Guide at :19968."""
        is_open, reason = is_open_ended_question(INTERVIEW_PROMPT)
        assert is_open is True, "interview-questions request must reach the model"
        assert reason == ADVICE_IMPERATIVE_REASON
        assert _model_bound(INTERVIEW_PROMPT) is True
        assert is_explicit_job_listing_request(INTERVIEW_PROMPT) is False
        assert RicoChatAPI.is_document_action_message(INTERVIEW_PROMPT) is False

    def test_interrogative_form_still_works_no_regression(self):
        """(3) The one prompt that already worked must keep working, unchanged."""
        is_open, reason = is_open_ended_question(WORKING_PROMPT)
        assert is_open is True
        # Still classified by its ORIGINAL reason, not the new branch.
        assert reason == "token:why"
        assert _model_bound(WORKING_PROMPT) is True


# ── (4) Structured carve-outs must still reach deterministic handlers ─────────

class TestStructuredCarveOutsPreserved:
    @pytest.mark.parametrize("message", [
        "show my files",
        "list my files",
        "show me my uploaded documents",
        "which cv is the active one",
    ])
    def test_file_listing_never_goes_to_the_model(self, message):
        assert is_open_ended_question(message)[0] is False, message

    @pytest.mark.parametrize("message", [
        "find me jobs in Dubai",
        "give me jobs in Dubai",
        "search for HSE roles in Abu Dhabi",
        "show me accounting roles in Sharjah",
    ])
    def test_job_search_stays_on_the_grounded_search_path(self, message):
        """Job listings must never be answered by a model with no search tools."""
        assert not (
            is_open_ended_question(message)[0]
            and not is_explicit_job_listing_request(message)
        ), f"{message!r} could reach the AI path and fabricate listings"

    @pytest.mark.parametrize("message", [
        "what jobs have I applied to?",
        "what did i apply to",
    ])
    def test_application_status_stays_deterministic(self, message):
        assert is_open_ended_question(message)[0] is False, message

    @pytest.mark.parametrize("message", ["مرحبا", "ابحث عن وظائف"])
    def test_arabic_carve_outs_unchanged(self, message):
        assert is_open_ended_question(message)[0] is False, message

    @pytest.mark.parametrize("message", [
        "what is my visa status",
    ])
    def test_what_is_my_x_status_is_unchanged_by_this_pr(self, message):
        """Pinned as UNCHANGED, and deliberately not "fixed" here.

        These already routed to the model on `main` before this PR (reason
        "token:what" — `_APPLICATION_STATUS_RE` does not match this phrasing).
        This PR must not alter them in either direction.

        "what is my application status" used to be pinned here too, with the
        note that whether it *should* be a deterministic lookup was "a separate
        scope with its own evidence". That evidence now exists — a production
        read of the status column across all users, plus live verification that
        the phrasing returned a fabricated count — and the owner has ruled it a
        data request. It moved to the test below rather than being deleted, and
        the half of this test's intent that was about THIS branch (that the
        advice-imperative rule must not be what reclassifies it) is asserted
        there unchanged. A visa-status question stays model-bound: it is not a
        question about the user's stored records at all.
        """
        is_open, reason = is_open_ended_question(message)
        assert is_open is True
        assert reason == "token:what"
        # NOT reclassified by the new branch.
        assert reason != ADVICE_IMPERATIVE_REASON

    @pytest.mark.parametrize("message", [
        "what is my application status",
        "What is my application status?",
    ])
    def test_application_status_is_now_a_deterministic_lookup(self, message):
        """Reclassified deliberately, by the account-data carve-out — not by this branch.

        Live-verified on production: this phrasing reached the model, which has
        no database access, and answered a question about the user's own records
        by inventing a number. It is now routed to the deterministic tracking
        handler alongside every other ownership-qualified applications phrasing.
        """
        is_open, reason = is_open_ended_question(message)
        assert is_open is False
        assert reason == "ok"
        # The original intent of the pin above, preserved verbatim: whatever
        # reclassifies this message, it must not be the advice-imperative rule.
        assert reason != ADVICE_IMPERATIVE_REASON


# ── Newly eligible classes (input to the bounded-streaming PR) ────────────────

class TestNewlyEligibleAdviceClasses:
    @pytest.mark.parametrize("message", [
        "Give me one short tip to improve my CV for UAE employers",
        "List exactly four interview questions for a compliance officer",
        "Suggest three ways to strengthen my CV summary",
        "Compare working in Dubai versus Abu Dhabi for banking",
        "Rewrite my CV summary to be more concise",
        "Draft a short professional bio for a compliance officer",
        "Recommend a certification for AML work in the UAE",
        "Review my approach to salary negotiation in the Gulf",
        "Please summarize the key differences between DIFC and ADGM",
    ])
    def test_advice_imperatives_reach_the_model(self, message):
        assert is_open_ended_question(message)[0] is True, message
        assert _model_bound(message) is True, message


# ── Transport: newly eligible classes must stay BUFFERED ─────────────────────

class TestTransportHeldBuffered:
    @pytest.mark.parametrize("message", [CV_TIP_PROMPT, INTERVIEW_PROMPT])
    def test_newly_model_bound_prompts_do_not_stream(self, message):
        """Semantic fix without a transport change: reasoning yes, streaming no.

        Streaming would bypass `_preserve_ai_message` and promise-only
        detection, so these must remain on the buffered path until streaming is
        enabled deliberately.
        """
        assert _model_bound(message) is True, "must reach the model"
        assert _streams(message) is False, "must remain BUFFERED"

    @pytest.mark.parametrize("message", [
        WORKING_PROMPT,
        "How do I improve my CV?",
        "Can you give me a tip?",
    ])
    def test_previously_eligible_prompts_still_stream_unchanged(self, message):
        """The hold must be surgical: anything already stream-eligible is untouched.

        "Can you give me a tip?" is advice-shaped but question-marked, so it
        qualified before this PR and must keep streaming — proving the guard
        keys on the new branch only, not on advice phrasing generally.
        """
        assert _streams(message) is True, message

    def test_predicate_matches_exactly_the_newly_eligible_set(self):
        assert is_advice_imperative_message(CV_TIP_PROMPT) is True
        assert is_advice_imperative_message(INTERVIEW_PROMPT) is True
        # Pre-existing reasons are never claimed by the predicate.
        assert is_advice_imperative_message(WORKING_PROMPT) is False
        assert is_advice_imperative_message("Can you give me a tip?") is False
        assert is_advice_imperative_message("show my files") is False
        assert is_advice_imperative_message("find me jobs in Dubai") is False
