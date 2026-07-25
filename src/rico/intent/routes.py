"""
Explicit routing contract.

Two questions were previously conflated across four predicates checked in a
load-bearing order spread over ``gates.py`` and ``chat_service.py``:

  1. SEMANTIC  — does this request need reasoning, grounded data, or nothing?
  2. TRANSPORT — is its answer safe to stream?

Nothing named either decision, so nothing could assert on it or log it. #1379
made the coupling visible (correcting the semantics silently threatened to
divert new traffic onto the streaming branch) and pinned it with a single
predicate; this module makes both decisions first-class and diagnosable.

``resolve_route`` is PURE: no DB, no provider call, no side effects. It reads
the same predicates, in the same order, that ``should_stream_ai`` and
``send_message`` already applied — this module is a refactor for legibility,
NOT a behaviour change. Every class buffered today stays buffered; every class
streaming today keeps streaming.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SemanticRoute(str, Enum):
    """What kind of work the request actually is."""

    #: Answerable from fixed policy/account state — no model, no search.
    DETERMINISTIC = "deterministic"
    #: Genuine reasoning work; the model must answer it.
    REASONING = "reasoning"
    #: Must be answered from grounded user/provider data (files, jobs,
    #: applications). A model has no access to it and must never guess.
    GROUNDED_TOOL = "grounded_tool"
    #: Rico cannot do this. The only honest answer is to say so.
    UNSUPPORTED = "unsupported"


class TransportRoute(str, Enum):
    """How the answer reaches the client."""

    #: Whole-text response; the post-processing in ``respond()`` applies.
    BUFFERED = "buffered"
    #: Token-streamed over SSE. Bypasses that post-processing — see
    #: ``RouteReason.ADVICE_IMPERATIVE`` for why that matters.
    STREAM = "stream"
    #: Structured payload (job cards, file inventory, policy response).
    STRUCTURED = "structured"


class RouteReason(str, Enum):
    """Fixed reason vocabulary. Never a free-form string."""

    UNSUPPORTED_TOOL = "unsupported_tool"
    ACCOUNT_SERVICE = "account_service"
    DOCUMENT_ACTION = "document_action"
    FILE_INVENTORY = "file_inventory"
    JOB_LISTING_REQUEST = "job_listing_request"
    APPLICATION_STATUS = "application_status"
    #: Imperative advice request. Model-bound but held BUFFERED: the streaming
    #: branch skips ``_preserve_ai_message`` blocked-question filtering and
    #: promise-only detection, so this class must not be diverted onto it as a
    #: side effect of #1379's semantic correction.
    ADVICE_IMPERATIVE = "advice_imperative"
    OPEN_ENDED_QUESTION = "open_ended_question"
    #: Public/guest session with no profile: the legacy classifier loops on the
    #: onboarding welcome forever, so conversational AI answers instead.
    PUBLIC_NO_PROFILE = "public_no_profile"
    LEGACY_CLASSIFIER = "legacy_classifier"


@dataclass(frozen=True, slots=True)
class RouteResolution:
    """The two decisions, their reason category, and the handler they select."""

    semantic_route: SemanticRoute
    transport_route: TransportRoute
    reason: RouteReason
    handler_name: str

    @property
    def uses_reasoning(self) -> bool:
        """True when the model must answer this request."""
        return self.semantic_route is SemanticRoute.REASONING

    @property
    def streams(self) -> bool:
        """True when this request is token-streamed."""
        return self.transport_route is TransportRoute.STREAM

    def to_log_dict(self) -> dict[str, str]:
        """Log-safe view — categories only, never message text."""
        return {
            "semantic_route": self.semantic_route.value,
            "transport_route": self.transport_route.value,
            "reason": self.reason.value,
            "handler_name": self.handler_name,
        }


def resolve_route(
    message: str,
    *,
    profile_present: bool,
    can_persist_profile: bool,
    is_authenticated: bool,
    policy_route: str | None = None,
) -> RouteResolution:
    """Resolve the semantic and transport decisions for one message.

    Predicate order is identical to the order ``should_stream_ai`` and
    ``send_message`` already apply, and each branch is annotated with the call
    site it mirrors. Changing this order changes production routing.

    ``policy_route`` is the ``classify_request`` verdict when the caller has
    already computed it (the preflight does). Omitted, the policy-owned
    branches are simply not claimed here — the preflight still terminates them
    before this function is consulted, so the resolution stays truthful either
    way.
    """
    from src.rico_chat_api import RicoChatAPI
    from .gates import (
        is_advice_imperative_message,
        is_explicit_job_listing_request,
        is_open_ended_question,
        is_file_inventory_question,
    )

    # ── Policy gateway outcomes (chat_service.run_chat_preflight) ────────────
    # Terminal before any AI or legacy routing touches the message.
    if policy_route == "unsupported":
        return RouteResolution(
            SemanticRoute.UNSUPPORTED,
            TransportRoute.STRUCTURED,
            RouteReason.UNSUPPORTED_TOOL,
            "PolicyGateway.unsupported_tool",
        )
    if policy_route == "account_service":
        return RouteResolution(
            SemanticRoute.DETERMINISTIC,
            TransportRoute.STRUCTURED,
            RouteReason.ACCOUNT_SERVICE,
            "PolicyGateway.account_service",
        )

    # ── Document actions (should_stream_ai / send_message, first check) ──────
    if RicoChatAPI.is_document_action_message(message):
        return RouteResolution(
            SemanticRoute.GROUNDED_TOOL,
            TransportRoute.STRUCTURED,
            RouteReason.DOCUMENT_ACTION,
            "RicoChatAPI.handle_document_action",
        )

    # ── Explicit job-listing requests (second check) ─────────────────────────
    # A model has no search tools here and would fabricate companies, salaries
    # and links, so this class can never reach a free-form AI path.
    if is_explicit_job_listing_request(message):
        return RouteResolution(
            SemanticRoute.GROUNDED_TOOL,
            TransportRoute.STRUCTURED,
            RouteReason.JOB_LISTING_REQUEST,
            "PublicJobSearchCTA" if not (profile_present or can_persist_profile)
            else "LegacyClassifier.grounded_search",
        )

    # ── File / CV inventory ──────────────────────────────────────────────────
    # Answered from user_documents. The model cannot enumerate a user's files
    # and must never be given the chance to guess at them.
    if is_file_inventory_question(message):
        return RouteResolution(
            SemanticRoute.GROUNDED_TOOL,
            TransportRoute.STRUCTURED,
            RouteReason.FILE_INVENTORY,
            "RicoChatAPI._handle_file_list_query",
        )

    # ── Intent gate (third check) ────────────────────────────────────────────
    is_open, gate_reason = is_open_ended_question(message)

    if is_open and is_advice_imperative_message(message):
        # Model-bound, transport held buffered. See RouteReason docstring.
        return RouteResolution(
            SemanticRoute.REASONING,
            TransportRoute.BUFFERED,
            RouteReason.ADVICE_IMPERATIVE,
            "ConversationalAIHandler",
        )

    if is_open:
        return RouteResolution(
            SemanticRoute.REASONING,
            TransportRoute.STREAM,
            RouteReason.OPEN_ENDED_QUESTION,
            "ConversationalAIHandler",
        )

    # Public/guest session with no profile — mirrors the `_force_ai` branch in
    # both should_stream_ai and send_message.
    if not profile_present and not can_persist_profile:
        return RouteResolution(
            SemanticRoute.REASONING,
            TransportRoute.STREAM,
            RouteReason.PUBLIC_NO_PROFILE,
            "ConversationalAIHandler",
        )

    if gate_reason == "ok" and _is_application_status(message):
        return RouteResolution(
            SemanticRoute.GROUNDED_TOOL,
            TransportRoute.STRUCTURED,
            RouteReason.APPLICATION_STATUS,
            "RicoChatAPI._handle_application_tracking",
        )

    return RouteResolution(
        SemanticRoute.GROUNDED_TOOL,
        TransportRoute.STRUCTURED,
        RouteReason.LEGACY_CLASSIFIER,
        "LegacyClassifier",
    )


def _is_application_status(message: str) -> bool:
    """Thin wrapper so the application-status carve-out is nameable here."""
    from .gates import _is_application_status_question

    return _is_application_status_question((message or "").lower())
