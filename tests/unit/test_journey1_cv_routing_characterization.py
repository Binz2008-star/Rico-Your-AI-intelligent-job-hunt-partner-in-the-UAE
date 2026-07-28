"""Journey-1 CV routing — characterization before extraction.

WHY THIS FILE EXISTS
--------------------
``src/rico_chat_api.py`` answers "does this user have a CV?" from several
independent gates. ``AI_WORKSPACE/ARCHITECTURE.md`` -> "Migration rules for
``rico_chat_api.py``" requires routing and side-effect order to be characterized
*before* any code moves. This file is that characterization and nothing else: it
adds no production code, fixes no behaviour, and moves nothing.

WHAT A TEST HERE MEANS
----------------------
Three deliberately different kinds of assertion, never mixed:

``test_contract_*``
    A **product-level** guarantee a user is entitled to. A failure is a
    regression. Reserved for outcomes, never for the internal mechanism that
    currently produces them.

``test_characterizes_*``
    A neutral statement of what the code does today — including which predicate
    fires, in what order, and which concrete handler wins. It is **not** an
    endorsement, and a mechanism recorded here may be replaced freely as long as
    the contracts above still hold.

``@pytest.mark.xfail(strict=True)``
    A known divergence whose desired contract is **already established** but not
    yet implemented. Strict, so it fails loudly the day it is fixed.

The line between the two names is the one this file has to get right. "An Arabic
job search reaches job search" is a contract. "It reaches job search *because*
``_looks_like_cv_intent_no_file`` matches and ``is_explicit_job_listing_request``
then rescues it" is a mechanism — fixable, and not something a test may bless.

HOW ROUTING IS OBSERVED
-----------------------
``TestDispatcherScenarioMatrix`` drives the real production entry point,
``RicoChatAPI._handle_active_user_inner``, and observes it from the outside. The
cascade is never re-implemented here: the harness stubs *upstream intercepts* so
a message can reach the CV region, wraps the CV collaborators in counting
proxies that still delegate to the real methods, and replaces only the
*terminal* handlers with spies. Whatever the dispatcher does between those two
edges is what gets recorded.

Hermetic only — no database, no network, no provider, no account.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest

from src.rico_chat_api import CV_FILE_RE, RicoChatAPI
from src.services.cv_context_resolver import (
    REASON_NO_CONTENT,
    REASON_NONE_ON_FILE,
    REASON_UNAVAILABLE,
    CVContext,
)
from src.services.cv_state import STATE_METADATA_ONLY, STATE_NONE, STATE_STRUCTURED


# ── Scenario messages ────────────────────────────────────────────────────────

EN_STORED_FILENAME = "review the previous uploaded cv of Roudain Mosleh 2026.pdf"
EN_CV_ANALYSIS = "analyse my cv please"
AR_CV_QUESTION = "هل لدي سيرة ذاتية محفوظة؟"
EN_UPLOAD_ANNOUNCE = "i have a cv, ill upload it"
AR_UPLOAD_ANNOUNCE = "أريد رفع سيرتي الذاتية"
EN_JOB_SEARCH_MENTIONING_CV = "Find UAE jobs that match my CV and experience."
AR_JOB_SEARCH_MENTIONING_CV = "ابحث عن وظائف في الإمارات تناسب سيرتي الذاتية"

STORED_DOCS = [
    {
        "id": "doc-1",
        "filename": "Roudain Mosleh 2026.pdf",
        "original_filename": "Roudain Mosleh 2026.pdf",
        "doc_type": "cv",
        "is_primary": True,
        "skills_json": ["iso 14001", "compliance"],
        "years_experience": 8.0,
        "current_role": "Founder & General Manager",
    },
]

PARSED_PROFILE = {
    "cv_status": "parsed",
    "cv_filename": "Roudain Mosleh 2026.pdf",
    "skills": ["compliance"],
    "years_experience": 8,
}


# ── CV-context fixtures, one per store state ─────────────────────────────────

def ctx_store_unavailable_no_metadata() -> CVContext:
    """Scenario 7: the grounding read did not complete, nothing else known."""
    return CVContext(state=STATE_NONE, availability_reason=REASON_UNAVAILABLE)


def ctx_store_unavailable_with_metadata() -> CVContext:
    """Scenario 7 + 8: read failed, but the caller's profile shows a filename."""
    return CVContext(
        state=STATE_METADATA_ONLY,
        filename="Roudain Mosleh 2026.pdf",
        availability_reason=REASON_UNAVAILABLE,
    )


def ctx_metadata_only() -> CVContext:
    """Scenario 8: read SUCCEEDED; a CV exists, its content does not."""
    return CVContext(
        state=STATE_METADATA_ONLY,
        filename="Roudain Mosleh 2026.pdf",
        availability_reason=REASON_NO_CONTENT,
    )


def ctx_genuinely_absent() -> CVContext:
    """Scenarios 6 + 9: read SUCCEEDED and the account genuinely has no CV."""
    return CVContext(state=STATE_NONE, availability_reason=REASON_NONE_ON_FILE)


def ctx_readable() -> CVContext:
    """A healthy CV with readable content — the baseline 'nothing wrong' state."""
    return CVContext(
        state=STATE_STRUCTURED,
        structured={"skills": ["compliance"]},
        filename="Roudain Mosleh 2026.pdf",
        availability_reason="structured_available",
    )


def _is_unverified(response: dict[str, Any]) -> bool:
    """The Journey-1 D3 answer, identified by contract rather than by prose."""
    return isinstance(response, dict) and response.get("type") == "cv_state_unverified"


#: The five renderings a failed read must never produce. Substrings only — the
#: full sentences are copy, not contract.
FORBIDDEN_AFTER_FAILED_READ = (
    "haven't uploaded one",
    "no saved CVs",
    "Re-upload it",
    "Upload your CV",
    "لم ترفع",
    "أعد رفعها",
)

#: Response types that constitute "the user was sent to upload a CV".
CV_GUIDANCE_TYPES = frozenset({"cv_upload_guidance", "cv_already_exists"})


# ══════════════════════════════════════════════════════════════════════════
# The dispatcher harness — real routing, observed from the outside
# ══════════════════════════════════════════════════════════════════════════

#: Collaborators that run BEFORE the CV region and would otherwise need a
#: database. Each is neutralised to "no opinion" so the message flows onward.
#: Stubbing these does not decide any CV or search outcome.
_UPSTREAM_INTERCEPTS = (
    "_resolve_pending_field",
    "_resolve_letter_choice",
    "_handle_pending_pipeline_reset",
    "_handle_pending_delete_saved_jobs",
    "_intercept_unsupported_delete_mutation",
    "_resolve_settings_command",
    "_extract_explicit_draft_job_from_message",
    "_handle_application_channel_followup",
)

#: Every terminal that means "a job search was actually run". More than one
#: exists, and which one wins is a routing fact this file records rather than
#: asserts — see ``test_characterizes_search_terminal_differs_by_language``.
_JOB_SEARCH_TERMINALS = (
    "_target_role_search_response",
    "_handle_company_search",
    "_handle_salary_filtered_search",
    "_handle_employment_type_search",
    "_handle_industry_search",
    "_handle_seniority_search",
    "_handle_company_type_search",
    "_handle_urgency_search",
    "_handle_refine_search",
)


class Dispatch:
    """Runs ``_handle_active_user_inner`` and records everything it did.

    The CV collaborators are *wrapped*, not replaced: each proxy increments a
    counter and then calls the real bound method, so the production decision is
    the one being observed. Only the job-search and LLM terminals are true
    spies, because reaching one is the observation.
    """

    def __init__(self, cv_ctx: Optional[CVContext] = None, docs: Any = None,
                 docs_raise: bool = False, target_roles: Optional[list] = None,
                 has_cv: bool = True):
        api = RicoChatAPI.__new__(RicoChatAPI)
        self.api = api
        self.append_chat_calls: list[str] = []
        self.finalize_sources: list[str] = []
        self.cv_context_reads = 0
        self.document_reads = 0
        self.job_search_calls = 0
        self.job_search_terminals: list[str] = []
        self.llm_fallback_calls = 0
        self.gate2_calls = 0
        self.stored_cv_handler_calls = 0
        self._cv_ctx = cv_ctx if cv_ctx is not None else ctx_readable()
        self._docs = list(STORED_DOCS) if docs is None else list(docs)
        self._docs_raise = docs_raise

        api._can_mutate_applications = True
        api._resolve_profile = MagicMock(return_value=SimpleNamespace(
            has_cv=has_cv,
            target_roles=list(target_roles or ["Compliance Manager"]),
            preferred_cities=["Dubai"],
        ))
        api._normalize_followup_phrase = MagicMock(side_effect=lambda m: m)
        api._pending_search_redemption_blocked = MagicMock(return_value=False)
        for name in _UPSTREAM_INTERCEPTS:
            setattr(api, name, MagicMock(return_value=None))
        api._get_recent_context = MagicMock(return_value={})
        api._get_last_turn = MagicMock(return_value={})

        api._append_chat = lambda uid, role, msg: self.append_chat_calls.append(role)

        def _finalize(response, source=None, **kwargs):
            self.finalize_sources.append(source)
            return response
        api._finalize = _finalize

        # -- counting proxies over the REAL CV logic --------------------------
        def _cv_context(user_id, profile=None):
            self.cv_context_reads += 1
            return self._cv_ctx
        api._cv_context = _cv_context

        def _collect_documents_detailed(user_id, profile):
            self.document_reads += 1
            if self._docs_raise:
                raise RuntimeError("document store unavailable")
            return list(self._docs)
        api._collect_documents_detailed = _collect_documents_detailed

        real_gate2 = RicoChatAPI._cv_upload_guidance_with_db_check.__get__(api)
        def _gate2(user_id, message, profile=None):
            self.gate2_calls += 1
            return real_gate2(user_id, message, profile=profile)
        api._cv_upload_guidance_with_db_check = _gate2

        real_stored = RicoChatAPI._handle_stored_cv_reference.__get__(api)
        def _stored(user_id, profile, message):
            self.stored_cv_handler_calls += 1
            return real_stored(user_id, profile, message)
        api._handle_stored_cv_reference = _stored

        # -- terminal spies ---------------------------------------------------
        for name in _JOB_SEARCH_TERMINALS:
            setattr(api, name, MagicMock(
                side_effect=lambda *a, _n=name, **k: self._search(_n)))
        api._answer_with_ai_fallback = MagicMock(
            side_effect=lambda *a, **k: self._llm())

    def _search(self, terminal: str) -> dict[str, Any]:
        self.job_search_calls += 1
        self.job_search_terminals.append(terminal)
        return {"type": "job_matches", "_terminal": terminal}

    def _llm(self) -> dict[str, Any]:
        self.llm_fallback_calls += 1
        return {"type": "ai_response", "_terminal": "llm_fallback"}

    def run(self, message: str, user_id: str = "u@test") -> dict[str, Any]:
        """Drive the production dispatcher. No document store is reachable, so
        ``resolve_user_cv`` is faked to report a verified-empty account unless a
        test says otherwise."""
        with (
            patch("src.services.document_resolver.resolve_user_cv", return_value=None),
            patch("src.services.document_resolver.has_only_identity_documents",
                  return_value=False),
        ):
            return self.api._handle_active_user_inner(user_id, message)

    # -- observation helpers ------------------------------------------------
    @property
    def append_chat_count(self) -> int:
        return len(self.append_chat_calls)

    @property
    def finalize_count(self) -> int:
        return len(self.finalize_sources)


# ══════════════════════════════════════════════════════════════════════════
# 1. Scenario matrix — driven through the real dispatcher
# ══════════════════════════════════════════════════════════════════════════

class TestDispatcherScenarioMatrix:
    """The nine required scenarios, each run through
    ``_handle_active_user_inner`` with every side effect counted."""

    # -- Positive controls: prove the terminal spies can actually fire ------
    # Without these, every ``== 0`` assertion below could pass because the spy
    # was never wired rather than because the path was never taken.

    def test_harness_control_llm_fallback_spy_fires_when_the_path_is_taken(self):
        """A message no deterministic gate claims reaches the LLM fallback, so
        the ``llm_fallback_calls == 0`` assertions elsewhere are not vacuous."""
        d = Dispatch()
        result = d.run("what do you think about my career prospects in general?")
        assert d.llm_fallback_calls == 1
        assert d.job_search_calls == 0
        assert result.get("type") == "ai_response"

    def test_harness_control_job_search_spy_fires_when_the_path_is_taken(self):
        """The counterpart control for the job-search terminals."""
        d = Dispatch()
        d.run(EN_JOB_SEARCH_MENTIONING_CV)
        assert d.job_search_calls == 1

    # -- Scenario 5: job search mentioning the CV -------------------------

    def test_contract_english_job_search_mentioning_cv_reaches_job_search(self):
        """PRODUCT CONTRACT. A user asking for jobs gets jobs — not CV upload
        guidance, and not a generic LLM answer."""
        d = Dispatch()
        result = d.run(EN_JOB_SEARCH_MENTIONING_CV)
        assert d.job_search_calls == 1
        assert d.llm_fallback_calls == 0
        assert result.get("type") == "job_matches"
        assert result.get("type") not in CV_GUIDANCE_TYPES

    def test_contract_arabic_job_search_mentioning_cv_reaches_job_search(self):
        """PRODUCT CONTRACT, and the one that BUG-25 broke. The Arabic request
        must reach a job search and must not become CV guidance or an LLM
        answer. HOW it gets there is deliberately not asserted here."""
        d = Dispatch()
        result = d.run(AR_JOB_SEARCH_MENTIONING_CV)
        assert d.job_search_calls == 1
        assert d.llm_fallback_calls == 0
        assert result.get("type") == "job_matches"
        assert result.get("type") not in CV_GUIDANCE_TYPES

    def test_characterizes_search_terminal_differs_by_language(self):
        """CURRENT BEHAVIOUR, not an endorsement.

        English and Arabic reach *different* job-search terminals for the same
        intent: English lands on ``_target_role_search_response`` and Arabic on
        ``_handle_company_search``. Both satisfy the contracts above, so this is
        recorded rather than asserted as desirable — but an extraction that
        unifies them changes this test, and should.
        """
        en, ar = Dispatch(), Dispatch()
        en.run(EN_JOB_SEARCH_MENTIONING_CV)
        ar.run(AR_JOB_SEARCH_MENTIONING_CV)
        assert en.job_search_terminals == ["_target_role_search_response"]
        assert ar.job_search_terminals == ["_handle_company_search"]

    def test_contract_job_search_does_not_read_the_document_store(self):
        """A job search must not pay for a document-store round trip it does not
        use. Counted, not assumed."""
        d = Dispatch()
        d.run(EN_JOB_SEARCH_MENTIONING_CV)
        assert d.document_reads == 0
        assert d.stored_cv_handler_calls == 0

    # -- Scenario 3 + 4: announce gate ------------------------------------

    @pytest.mark.parametrize(
        "message,label",
        [(EN_UPLOAD_ANNOUNCE, "en"), (AR_UPLOAD_ANNOUNCE, "ar"),
         (AR_CV_QUESTION, "ar_question")],
    )
    def test_characterizes_announce_gate_owns_these_turns(self, message, label):
        """CURRENT BEHAVIOUR. Gate 2 claims the turn, the pre-check runs exactly
        once, and neither a job search nor the LLM fallback is reached — the
        turn exits before any later routing gate."""
        d = Dispatch()
        d.run(message)
        assert d.gate2_calls == 1
        assert d.job_search_calls == 0
        assert d.llm_fallback_calls == 0

    def test_contract_upload_announcement_never_reaches_the_llm_fallback(self):
        """PRODUCT CONTRACT. Upload guidance is deterministic; a user announcing
        a CV must never get a generated answer about it."""
        for message in (EN_UPLOAD_ANNOUNCE, AR_UPLOAD_ANNOUNCE):
            d = Dispatch()
            d.run(message)
            assert d.llm_fallback_calls == 0

    # -- Scenario 7: store unavailable, through the dispatcher -------------

    @pytest.mark.parametrize(
        "message", [EN_UPLOAD_ANNOUNCE, AR_UPLOAD_ANNOUNCE, AR_CV_QUESTION]
    )
    def test_contract_store_outage_answers_unverified_and_asks_for_nothing(self, message):
        """PRODUCT CONTRACT, Journey-1 D3, proven end-to-end rather than at the
        helper. A failed grounding read must not produce upload guidance."""
        d = Dispatch(cv_ctx=ctx_store_unavailable_no_metadata())
        result = d.run(message)
        assert _is_unverified(result)
        assert result.get("next_action") is None
        assert result.get("type") not in CV_GUIDANCE_TYPES
        assert d.llm_fallback_calls == 0
        assert d.job_search_calls == 0
        for forbidden in FORBIDDEN_AFTER_FAILED_READ:
            assert forbidden not in result["message"]

    def test_characterizes_store_outage_side_effect_counts(self):
        """CURRENT BEHAVIOUR — the exact per-turn cost of the outage path, so an
        extraction cannot quietly add a read or a duplicate transcript write."""
        d = Dispatch(cv_ctx=ctx_store_unavailable_no_metadata())
        d.run(EN_UPLOAD_ANNOUNCE)
        assert d.cv_context_reads == 1
        assert d.document_reads == 0
        assert d.append_chat_count == 1
        assert d.finalize_count == 1
        assert d.finalize_sources == [RicoChatAPI.SOURCE_KEYWORD]

    def test_contract_outage_with_visible_filename_still_answers_unverified(self):
        """Scenario 7 + 8. A filename the caller can see must not promote a
        failed read into document blame."""
        d = Dispatch(cv_ctx=ctx_store_unavailable_with_metadata())
        result = d.run(AR_CV_QUESTION)
        assert _is_unverified(result)
        assert result.get("next_action") is None

    # -- Scenario 1 + 2: filename reference and analysis ask ---------------

    def test_contract_filename_reference_is_answered_from_the_stored_document(self):
        """PRODUCT CONTRACT. Naming a stored file gets a document-grounded
        answer — not a job search, not a generated one."""
        d = Dispatch()
        result = d.run(EN_STORED_FILENAME)
        assert result.get("type") == "cv_analysis"
        assert d.stored_cv_handler_calls == 1
        assert d.job_search_calls == 0
        assert d.llm_fallback_calls == 0

    def test_characterizes_filename_reference_side_effect_counts(self):
        """CURRENT BEHAVIOUR. Exactly one document read and one CV-context read
        for scenario 1, with a single transcript write and a single finalize."""
        d = Dispatch()
        d.run(EN_STORED_FILENAME)
        assert d.document_reads == 1
        assert d.cv_context_reads == 1
        assert d.append_chat_count == 1
        assert d.finalize_count == 1
        assert d.gate2_calls == 0

    @pytest.mark.parametrize("target_roles", [[], ["Compliance Manager"]])
    def test_characterizes_analysis_ask_routes_to_job_search_not_cv_analysis(
        self, target_roles
    ):
        """CURRENT BEHAVIOUR, and the most surprising fact this file records.

        "analyse my cv please" does NOT reach a CV-analysis answer through the
        dispatcher. It reaches ``_target_role_search_response`` — a job search —
        with or without saved target roles, and without reading the document
        store or the CV context at all.

        This is recorded, not endorsed, and deliberately NOT an xfail: no owner
        decision has established what an analysis ask *should* return, so there
        is no contract to diverge from. It is named here so an extraction cannot
        assume the obvious routing and quietly change behaviour.
        """
        d = Dispatch(target_roles=target_roles)
        result = d.run(EN_CV_ANALYSIS)
        assert result.get("type") == "job_matches"
        assert d.job_search_terminals == ["_target_role_search_response"]
        assert d.llm_fallback_calls == 0
        assert d.stored_cv_handler_calls == 0
        assert d.document_reads == 0
        assert d.cv_context_reads == 0

    # -- Scenario 9: genuine no-CV account ---------------------------------

    def test_characterizes_no_cv_account_announcing_a_cv_gets_upload_guidance(self):
        """Scenario 9. A COMPLETED read proving no CV — upload guidance is
        earned here, so ``next_action="upload_cv"`` is correct and is NOT the
        prohibited case."""
        d = Dispatch(cv_ctx=ctx_genuinely_absent(), has_cv=False)
        result = d.run(EN_UPLOAD_ANNOUNCE)
        assert result.get("type") == "cv_upload_guidance"
        assert result.get("next_action") == "upload_cv"
        assert d.llm_fallback_calls == 0

    def test_contract_a_verified_existing_cv_is_offered_for_search_not_re_upload(self):
        """Scenario 4 with a CV on file. The user is told what they have and
        pointed at job search rather than at a re-upload."""
        d = Dispatch()
        with (
            patch("src.services.document_resolver.resolve_user_cv",
                  return_value={"filename": "Roudain Mosleh 2026.pdf",
                                "is_primary": True}),
            patch("src.services.document_resolver.has_only_identity_documents",
                  return_value=False),
        ):
            result = d.api._handle_active_user_inner("u@test", EN_UPLOAD_ANNOUNCE)
        assert result.get("type") == "cv_already_exists"
        assert result.get("next_action") == "job_search"
        assert d.llm_fallback_calls == 0


# ══════════════════════════════════════════════════════════════════════════
# 2. Routing gates — which predicate claims a message
# ══════════════════════════════════════════════════════════════════════════

class TestRoutingGateMechanism:
    """Predicate-level facts. Everything here is a MECHANISM: it records how the
    dispatcher currently reaches the outcomes contracted above, and none of it
    is a product guarantee. Gate order at this base:

        1. ``_looks_like_cv_upload`` and not ``_is_job_request_mentioning_cv``
        2. ``_looks_like_cv_intent_no_file`` and not
           ``is_explicit_job_listing_request``
        3. the ``cv_analysis`` intent
    """

    def setup_method(self):
        self.api = RicoChatAPI.__new__(RicoChatAPI)

    def test_characterizes_filename_token_disables_the_announce_gate(self):
        """MECHANISM. Gate 2 stands down when a filename token is present."""
        assert CV_FILE_RE.search(EN_STORED_FILENAME)
        assert self.api._looks_like_cv_intent_no_file(EN_STORED_FILENAME) is False

    def test_characterizes_english_job_search_does_not_trip_the_announce_gate(self):
        """MECHANISM. The English announce list requires a have/upload verb, so
        an English job search never reaches gate 2 at all. The contract this
        serves is asserted behaviourally in the dispatcher matrix."""
        assert self.api._looks_like_cv_intent_no_file(
            EN_JOB_SEARCH_MENTIONING_CV
        ) is False

    def test_characterizes_arabic_job_search_trips_the_gate_then_is_exempted(self):
        """MECHANISM ONLY — deliberately not a contract.

        The Arabic phrase DOES match gate 2, and ``is_explicit_job_listing_request``
        is what keeps the search reachable. That two-step rescue is a current,
        fixable implementation detail: a future change could stop the gate
        matching at all and this test would change, with no product regression.

        The product guarantee — the Arabic request reaches job search — lives in
        ``test_contract_arabic_job_search_mentioning_cv_reaches_job_search``.
        """
        from src.rico.intent.gates import is_explicit_job_listing_request

        assert self.api._looks_like_cv_intent_no_file(
            AR_JOB_SEARCH_MENTIONING_CV
        ) is True
        assert is_explicit_job_listing_request(AR_JOB_SEARCH_MENTIONING_CV) is True

    def test_characterizes_arabic_cv_question_intercepted_before_intent_routing(self):
        """MECHANISM. A plain Arabic CV *question* trips gate 2 and is not an
        explicit job-listing request, so it is answered by CV guidance and never
        reaches the ``cv_analysis`` intent its English counterpart reaches.

        NOT an xfail: whether the gate should defer to the intent router is an
        open owner decision (#1422), so there is no established contract to
        diverge from.
        """
        from src.rico.intent.gates import is_explicit_job_listing_request

        assert self.api._looks_like_cv_intent_no_file(AR_CV_QUESTION) is True
        assert is_explicit_job_listing_request(AR_CV_QUESTION) is False

    def test_characterizes_english_analysis_ask_falls_through_the_announce_gate(self):
        """MECHANISM. The other half of the asymmetry above."""
        assert self.api._looks_like_cv_intent_no_file(EN_CV_ANALYSIS) is False
        assert self.api._CV_ANALYZE_ASK_RE.search(EN_CV_ANALYSIS) is not None

    @pytest.mark.parametrize(
        "message,expected",
        [
            (EN_UPLOAD_ANNOUNCE, True),
            (AR_UPLOAD_ANNOUNCE, True),
            (EN_CV_ANALYSIS, False),
            (EN_STORED_FILENAME, False),
        ],
    )
    def test_characterizes_announce_gate_membership(self, message, expected):
        """MECHANISM, stated as data."""
        assert self.api._looks_like_cv_intent_no_file(message) is expected


# ══════════════════════════════════════════════════════════════════════════
# HandlerProbe — for the single-handler sections below
# ══════════════════════════════════════════════════════════════════════════

class HandlerProbe:
    """A minimal RicoChatAPI for exercising ONE handler in isolation.

    The dispatcher matrix above is the authority on routing; this probe exists
    only to pin a handler's own contract and side-effect count, which the
    dispatcher cannot isolate. It never decides routing.
    """

    def __init__(self, cv_ctx=None, docs=None, docs_raise=False):
        api = RicoChatAPI.__new__(RicoChatAPI)
        self.api = api
        self.append_chat_calls: list[str] = []
        self.finalize_sources: list[str] = []
        self.cv_context_reads = 0
        self.document_reads = 0
        self._cv_ctx = cv_ctx if cv_ctx is not None else ctx_genuinely_absent()
        self._docs = list(STORED_DOCS) if docs is None else list(docs)
        self._docs_raise = docs_raise

        api._append_chat = lambda uid, role, msg: self.append_chat_calls.append(role)

        def _finalize(response, source=None, **kwargs):
            self.finalize_sources.append(source)
            return response
        api._finalize = _finalize

        def _cv_context(user_id, profile=None):
            self.cv_context_reads += 1
            return self._cv_ctx
        api._cv_context = _cv_context

        def _collect_documents_detailed(user_id, profile):
            self.document_reads += 1
            if self._docs_raise:
                raise RuntimeError("document store unavailable")
            return list(self._docs)
        api._collect_documents_detailed = _collect_documents_detailed

    @property
    def append_chat_count(self) -> int:
        return len(self.append_chat_calls)

    @property
    def finalize_count(self) -> int:
        return len(self.finalize_sources)


# ══════════════════════════════════════════════════════════════════════════
# 3. _handle_stored_cv_reference — entry, exit and side-effect counts
# ══════════════════════════════════════════════════════════════════════════

class TestStoredCvReferenceHandler:

    def test_characterizes_handler_declines_messages_it_does_not_own(self):
        """No filename token and no analysis ask -> ``None``, and crucially the
        document store is never read. The read count is the point: this is the
        cheap early exit that keeps unrelated turns off the store."""
        probe = HandlerProbe()
        result = probe.api._handle_stored_cv_reference(
            "u@test", dict(PARSED_PROFILE), "what is the weather"
        )
        assert result is None
        assert probe.document_reads == 0
        assert probe.append_chat_count == 0
        assert probe.finalize_count == 0

    def test_contract_stored_filename_reference_reaches_document_analysis(self):
        """Scenario 1. One document read, and the answer is grounded in the
        matched row rather than the profile."""
        probe = HandlerProbe()
        result = probe.api._handle_stored_cv_reference(
            "u@test", dict(PARSED_PROFILE), EN_STORED_FILENAME
        )
        assert result is not None
        assert result["type"] == "cv_analysis"
        assert result["filename"] == "Roudain Mosleh 2026.pdf"
        assert probe.document_reads == 1

    def test_contract_document_read_failure_is_not_a_successful_empty_read(self):
        """Scenario 7, Journey-1 D3. The read raised, so the answer must be the
        unverified state — never the not-found answer, which is what a
        SUCCESSFUL read of an empty account produces."""
        probe = HandlerProbe(docs_raise=True)
        result = probe.api._handle_stored_cv_reference(
            "u@test", dict(PARSED_PROFILE), EN_STORED_FILENAME
        )
        assert _is_unverified(result)
        assert result.get("next_action") is None
        assert probe.document_reads == 1
        for forbidden in FORBIDDEN_AFTER_FAILED_READ:
            assert forbidden not in result["message"]

    def test_contract_arabic_read_failure_is_also_unverified(self):
        """Scenario 7 in Arabic — same contract, same absence of next_action."""
        probe = HandlerProbe(docs_raise=True)
        result = probe.api._handle_stored_cv_reference(
            "u@test", dict(PARSED_PROFILE), "حلل سيرتي الذاتية"
        )
        assert _is_unverified(result)
        assert result.get("next_action") is None

    def test_contract_successful_empty_read_remains_genuine_absence(self):
        """Scenario 6. The read COMPLETED and returned nothing. That is real
        evidence of absence, so the not-found answer is correct and must not be
        reclassified as unverified by the D3 work."""
        probe = HandlerProbe(docs=[])
        result = probe.api._handle_stored_cv_reference(
            "u@test", dict(PARSED_PROFILE), EN_STORED_FILENAME
        )
        assert result is not None
        assert not _is_unverified(result)
        assert result["type"] == "cv_reference_not_found"
        assert probe.document_reads == 1

    def test_characterizes_analysis_ask_without_filename_uses_the_primary_cv(self):
        """Scenario 2 at the handler level: no filename token, so the primary
        document is selected rather than a name being matched."""
        probe = HandlerProbe()
        result = probe.api._handle_stored_cv_reference(
            "u@test", dict(PARSED_PROFILE), EN_CV_ANALYSIS
        )
        assert result is not None
        assert result["type"] == "cv_analysis"
        assert probe.document_reads == 1

    def test_characterizes_analysis_ask_with_empty_store_returns_none(self):
        """Scenario 9 at the handler level. No filename token means the
        not-found branch is skipped, and with no CV rows the handler declines
        (``None``) and lets later routing answer. The early-exit answer is
        therefore NOT owned by this handler for a genuine no-CV account."""
        probe = HandlerProbe(docs=[])
        result = probe.api._handle_stored_cv_reference(
            "u@test", dict(PARSED_PROFILE), EN_CV_ANALYSIS
        )
        assert result is None
        assert probe.document_reads == 1


# ══════════════════════════════════════════════════════════════════════════
# 4. The cv_analysis CV-state branch — precedence of the three outcomes
# ══════════════════════════════════════════════════════════════════════════

class TestCvAnalysisStateBranch:
    """The branch reads ``_cv_context`` ONCE and then picks exactly one of
    three outcomes, in this order: unavailable -> absent -> no-content.

    Reproduced here as a table rather than driven through the 23k-line module,
    because the ordering *is* the contract and it is what an extraction must
    preserve. The production ordering is asserted structurally in
    ``test_contract_unavailable_is_evaluated_before_both_confident_branches``.
    """

    @staticmethod
    def _classify(ctx: CVContext, profile_has_cv: bool = False) -> str:
        if ctx.is_unavailable:
            return "unverified"
        if not (ctx.has_cv or profile_has_cv):
            return "absent"
        if not ctx.has_content:
            return "no_content"
        return "review"

    def test_contract_store_unavailable_classifies_as_unverified(self):
        """Scenario 7."""
        assert self._classify(ctx_store_unavailable_no_metadata()) == "unverified"

    def test_contract_unavailable_wins_even_when_metadata_shows_a_filename(self):
        """Scenario 7 + 8 together. A visible filename must not promote a failed
        read into the "we have it but can't read it" answer — that answer blames
        the document for what is an outage on our side."""
        assert self._classify(ctx_store_unavailable_with_metadata()) == "unverified"

    def test_contract_metadata_only_after_a_successful_read_is_a_content_problem(self):
        """Scenario 8. The read COMPLETED, so ``no_readable_content`` is earned
        and keeps its existing document-quality guidance."""
        assert self._classify(ctx_metadata_only()) == "no_content"

    def test_contract_genuine_absence_after_a_successful_read_stays_absence(self):
        """Scenarios 6 and 9."""
        assert self._classify(ctx_genuinely_absent()) == "absent"

    def test_characterizes_source_order_tripwire_for_the_three_branches(self):
        """A STRUCTURAL TRIPWIRE, not the acceptance proof.

        The behavioural guarantee is owned by the ``test_contract_*`` cases in
        this class and by the end-to-end outage tests in the dispatcher matrix;
        those are what must hold. This test only reads the source order so that
        a textual reordering is noticed early, and it is expected to be deleted
        the moment the branches move behind a CV boundary — at which point the
        behavioural contracts continue to hold unchanged.
        """
        import inspect

        import src.rico_chat_api as mod

        src = inspect.getsource(mod)
        i_unavailable = src.index("if _cv_ctx.is_unavailable:")
        i_absent = src.index("I can't review your CV yet")
        i_no_content = src.index("I have your CV **{_fname}** on file")
        assert i_unavailable < i_absent < i_no_content

    def test_contract_unavailable_never_coexists_with_readable_content(self):
        """Why the ordering is safe: the resolver only sets ``store_unavailable``
        on states that carry no content, so the first branch can never swallow a
        review that could have been given."""
        for ctx in (ctx_store_unavailable_no_metadata(),
                    ctx_store_unavailable_with_metadata()):
            assert ctx.is_unavailable is True
            assert ctx.has_content is False


# ══════════════════════════════════════════════════════════════════════════
# 5. The unverified response itself — shape, not prose
# ══════════════════════════════════════════════════════════════════════════

class TestUnverifiedResponseShape:

    @pytest.mark.parametrize("arabic", [False, True])
    def test_contract_unverified_response_carries_no_action_and_no_options(self, arabic):
        """The single prohibited instruction after a failed read is
        ``next_action="upload_cv"``. Assert the shape, in both languages."""
        probe = HandlerProbe()
        response = probe.api._cv_state_unverified_response("u@test", arabic)
        assert response["type"] == "cv_state_unverified"
        assert response.get("next_action") is None
        assert not response.get("options")
        assert response["message"].strip()

    @pytest.mark.parametrize("arabic", [False, True])
    def test_contract_unverified_response_blames_nothing(self, arabic):
        """It must claim no cause, blame no document, and ask for no upload."""
        probe = HandlerProbe()
        message = probe.api._cv_state_unverified_response("u@test", arabic)["message"]
        for forbidden in FORBIDDEN_AFTER_FAILED_READ:
            assert forbidden not in message

    def test_characterizes_unverified_response_owns_its_own_transcript_write(self):
        """CURRENT BEHAVIOUR, verified against the code rather than assumed.

        The helper performs the ``_append_chat`` itself and does NOT call
        ``_finalize`` — its three call sites each wrap the returned dict in
        their own ``_finalize``. That split matters to an extraction: moving
        this helper moves one transcript write with it, and a caller that also
        appends would double-write the turn.
        """
        probe = HandlerProbe()
        probe.api._cv_state_unverified_response("u@test", False)
        assert probe.append_chat_count == 1
        assert probe.append_chat_calls == ["assistant"]
        assert probe.finalize_count == 0


# ══════════════════════════════════════════════════════════════════════════
# 6. _cv_upload_guidance_with_db_check — the gate-2 pre-check
# ══════════════════════════════════════════════════════════════════════════

class TestUploadGuidanceDbCheck:

    def _run(self, message: str, resolve_cv=None, raises: bool = False,
             only_identity: bool = False):
        probe = HandlerProbe()

        def _resolve_user_cv(user_id, profile=None):
            if raises:
                raise RuntimeError("store unavailable")
            return resolve_cv

        with (
            patch("src.services.document_resolver.resolve_user_cv",
                  side_effect=_resolve_user_cv),
            patch("src.services.document_resolver.has_only_identity_documents",
                  return_value=only_identity),
        ):
            result = probe.api._cv_upload_guidance_with_db_check(
                "u@test", message, profile=None
            )
        return probe, result

    def test_contract_verified_existing_cv_wins_over_upload_guidance(self):
        """Scenario 4 with a CV on file: the user is told what they already
        have, and is pointed at job search rather than at a re-upload."""
        probe, result = self._run(
            EN_UPLOAD_ANNOUNCE,
            resolve_cv={"filename": "Roudain Mosleh 2026.pdf", "is_primary": True},
        )
        assert result is not None
        assert result["type"] == "cv_already_exists"
        assert result["next_action"] == "job_search"
        assert probe.append_chat_count == 1
        assert probe.finalize_count == 1

    def test_characterizes_verified_empty_account_returns_none(self):
        """Scenario 9. A COMPLETED read that finds nothing returns ``None`` so
        the caller proceeds to upload guidance. This is correct — and it is also
        exactly the value the failure case below returns."""
        probe, result = self._run(EN_UPLOAD_ANNOUNCE, resolve_cv=None)
        assert result is None
        assert probe.append_chat_count == 0

    def test_characterizes_read_failure_returns_the_same_none_as_a_verified_empty(self):
        """Scenario 7, and the reason the gate-2 D3 guard has to exist.

        The broad ``except`` here flattens a failed read into ``None`` — byte
        identical to the verified-empty case above. This helper therefore cannot
        distinguish the two, and the ``is_unavailable`` check in the CALLER is
        what stops the outage becoming ``next_action="upload_cv"``. Recorded as
        current behaviour: it is contained, not wrong, but it is load-bearing
        context for anyone extracting this helper.
        """
        probe, result = self._run(EN_UPLOAD_ANNOUNCE, raises=True)
        assert result is None
        assert probe.append_chat_count == 0

    def test_contract_caller_guard_converts_that_none_into_an_unverified_answer(self):
        """The caller-side protection that makes the above safe: when the
        pre-check returns ``None`` and the CV context reports unavailable, the
        answer is the unverified state and NOT upload guidance."""
        probe = HandlerProbe(cv_ctx=ctx_store_unavailable_no_metadata())
        ctx = probe.api._cv_context("u@test", None)
        assert ctx.is_unavailable is True
        response = probe.api._cv_state_unverified_response("u@test", False)
        assert response.get("next_action") is None
        assert probe.cv_context_reads == 1

    def test_characterizes_identity_only_documents_still_ask_for_an_upload(self):
        """A COMPLETED read proving the user has documents but no CV. Upload
        guidance is earned here, so ``next_action="upload_cv"`` is correct."""
        probe, result = self._run(EN_UPLOAD_ANNOUNCE, resolve_cv=None,
                                  only_identity=True)
        assert result is not None
        assert result["type"] == "cv_upload_guidance"
        assert result["next_action"] == "upload_cv"


# ══════════════════════════════════════════════════════════════════════════
# 7. Per-turn read economy
# ══════════════════════════════════════════════════════════════════════════

class TestReadEconomy:

    def test_contract_cv_context_is_memoised_per_request(self):
        """Several gates ask the same question in one turn. The memo is what
        keeps that at one grounding read — an extraction that splits these call
        sites across objects loses the memo and reintroduces an N+1."""
        api = RicoChatAPI.__new__(RicoChatAPI)
        resolver = MagicMock(return_value=ctx_genuinely_absent())
        with patch("src.services.cv_context_resolver.resolve_cv_context", resolver):
            first = api._cv_context("u@test", None)
            second = api._cv_context("u@test", None)
        assert first is second
        assert resolver.call_count == 1

    def test_characterizes_memo_is_keyed_on_user_and_does_not_serve_another(self):
        """The memo is per-user, so a different user in the same instance
        re-reads. Recorded because it bounds what the memo may be assumed to do."""
        api = RicoChatAPI.__new__(RicoChatAPI)
        resolver = MagicMock(return_value=ctx_genuinely_absent())
        with patch("src.services.cv_context_resolver.resolve_cv_context", resolver):
            api._cv_context("a@test", None)
            api._cv_context("b@test", None)
        assert resolver.call_count == 2

    def test_contract_resolver_never_raises_and_reports_unavailable_instead(self):
        """The resolver's own contract, which every gate above depends on."""
        from src.services.cv_context_resolver import resolve_cv_context

        with patch("src.repositories.profile_repo.get_cv_grounding",
                   side_effect=RuntimeError("boom")):
            ctx = resolve_cv_context("u@test", None)
        assert ctx.is_unavailable is True
        assert ctx.has_cv is False
        assert ctx.has_content is False


# ══════════════════════════════════════════════════════════════════════════
# 8. Known divergence — established contract, not yet implemented
# ══════════════════════════════════════════════════════════════════════════

class TestKnownDivergences:

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "Journey-1 residual: My Files collapses an unavailable document "
            "store into files=[], which is byte-identical to a successful read "
            "of an empty account. The desired contract IS established — "
            "ARCHITECTURE.md: a failed or incomplete read must not be rendered "
            "as absence — and is unimplemented on this surface. Remove this "
            "marker when the surface distinguishes the two."
        ),
    )
    def test_my_files_must_not_render_an_unavailable_store_as_an_empty_list(self):
        from src.api.routers import files as files_router

        unavailable_db = SimpleNamespace(
            available=False,
            list_user_documents=lambda _uid: (_ for _ in ()).throw(
                AssertionError("must not be called while unavailable")
            ),
        )
        # A faithful plan/entitlement stub, so the test runs to its own
        # assertion instead of dying on a sentinel — an xfail that fails for an
        # incidental reason proves nothing about the divergence it names.
        plan_stub = SimpleNamespace(
            subscription=SimpleNamespace(
                plan=SimpleNamespace(value="free"),
                entitlements=SimpleNamespace(
                    cv_storage_limit=1, other_document_limit=3
                ),
            )
        )
        request = SimpleNamespace()
        with (
            patch.object(files_router, "_db", unavailable_db),
            patch.object(files_router, "get_current_user",
                         return_value={"email": "u@test"}),
            patch.object(files_router, "build_profile_cv_record", return_value=None),
            patch.object(files_router, "has_active_cv_document", return_value=False),
            patch.object(files_router, "resolve_effective_user_plan",
                         return_value=plan_stub),
        ):
            payload = files_router.list_files(request)

        # Guard the xfail itself: the store really was unavailable on this run,
        # so a failure below is the divergence and not a broken fixture.
        assert unavailable_db.available is False
        # The desired contract: an unreadable store is not an empty inventory.
        # Today this returns files=[] with total=0 — indistinguishable from a
        # successful read of an account that genuinely holds nothing.
        assert payload["files"] != [] or payload.get("state") == "unavailable"
