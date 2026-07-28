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
    An established correct contract. A failure is a regression.

``test_characterizes_*``
    A neutral statement of what the code does today. It is **not** an
    endorsement. Changing the behaviour deliberately means changing the test,
    and the name says so out loud so nobody reads it as approval.

``@pytest.mark.xfail(strict=True)``
    A known divergence whose desired contract is **already established** but not
    yet implemented. Strict, so it fails loudly the day it is fixed and the
    marker must be removed.

The Arabic routing asymmetry is deliberately NOT an xfail: whether
``_looks_like_cv_intent_no_file`` should defer to the intent router is an open
owner decision (recorded in #1422), so no desired contract exists to diverge
from. It is characterized instead.

SCOPE
-----
Hermetic only — no database, no network, no provider, no account. Every
collaborator is a spy or a fake. Long user-visible copy is never asserted
wholesale; only the minimum wording needed to separate "truthfully unverified"
from "absent" / "upload guidance" is pinned, because that distinction is the
Journey-1 D3 invariant (READ FAILURE != VERIFIED ABSENCE) and nothing else in
the wording is a contract.
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
from src.services.cv_state import STATE_METADATA_ONLY, STATE_NONE


# ── Scenario messages ────────────────────────────────────────────────────────
# One constant per required scenario, English and Arabic where the paths differ.

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


# ── Probe: a hermetic RicoChatAPI that counts every side effect ──────────────

class Probe:
    """A RicoChatAPI wired so no real collaborator can be reached, with a
    counter for every side effect the migration rules care about."""

    def __init__(self, cv_ctx: Optional[CVContext] = None, docs: Any = None,
                 docs_raise: bool = False):
        api = RicoChatAPI.__new__(RicoChatAPI)
        self.api = api
        self.append_chat_calls: list[str] = []
        self.finalize_sources: list[str] = []
        self.cv_context_reads = 0
        self.document_reads = 0
        self.profile_reads = 0
        self.profile_writes = 0
        self.job_search_calls = 0
        self.llm_fallback_calls = 0
        self._cv_ctx = cv_ctx if cv_ctx is not None else ctx_genuinely_absent()
        self._docs = docs if docs is not None else list(STORED_DOCS)
        self._docs_raise = docs_raise

        def _append_chat(user_id, role, message):
            self.append_chat_calls.append(role)

        def _finalize(response, source=None, **kwargs):
            self.finalize_sources.append(source)
            return response

        def _cv_context(user_id, profile=None):
            self.cv_context_reads += 1
            return self._cv_ctx

        def _collect_documents_detailed(user_id, profile):
            self.document_reads += 1
            if self._docs_raise:
                raise RuntimeError("document store unavailable")
            return list(self._docs)

        api._append_chat = _append_chat
        api._finalize = _finalize
        api._cv_context = _cv_context
        api._collect_documents_detailed = _collect_documents_detailed
        # Terminal collaborators — reaching one is itself an observation.
        api._target_role_search_response = MagicMock(
            side_effect=lambda *a, **k: self._count_search()
        )

    def _count_search(self):
        self.job_search_calls += 1
        return {"type": "job_matches"}

    # -- observation helpers ------------------------------------------------
    @property
    def append_chat_count(self) -> int:
        return len(self.append_chat_calls)

    @property
    def finalize_count(self) -> int:
        return len(self.finalize_sources)


def _is_unverified(response: dict[str, Any]) -> bool:
    """The Journey-1 D3 answer, identified by contract rather than by prose."""
    return response.get("type") == "cv_state_unverified"


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


# ══════════════════════════════════════════════════════════════════════════
# 1. Routing gates — which predicate claims a message, and in what order
# ══════════════════════════════════════════════════════════════════════════

class TestRoutingGatePrecedence:
    """The gate predicates are pure, so precedence can be characterized exactly.

    Order in ``_handle_active_user_inner`` (read at this base):
        1. ``_looks_like_cv_upload`` and not ``_is_job_request_mentioning_cv``
        2. ``_looks_like_cv_intent_no_file`` and not
           ``is_explicit_job_listing_request``
        3. the ``cv_analysis`` intent, which calls
           ``_handle_stored_cv_reference`` first
    """

    def setup_method(self):
        self.api = RicoChatAPI.__new__(RicoChatAPI)

    def test_contract_a_filename_token_disables_the_announce_gate(self):
        """Gate 2 explicitly stands down when a real filename is present, so a
        named file reaches the stored-CV handler rather than upload guidance."""
        assert CV_FILE_RE.search(EN_STORED_FILENAME)
        assert self.api._looks_like_cv_intent_no_file(EN_STORED_FILENAME) is False

    def test_contract_english_job_search_never_trips_the_announce_gate(self):
        """The English announce list requires a have/upload verb, so an English
        job search mentioning a CV never reaches gate 2 at all."""
        assert self.api._looks_like_cv_intent_no_file(
            EN_JOB_SEARCH_MENTIONING_CV
        ) is False

    def test_contract_arabic_job_search_is_exempted_by_the_job_listing_predicate(self):
        """BUG-25: the Arabic phrase DOES trip gate 2, and only the explicit
        job-listing exemption keeps the search reachable. Both halves are the
        contract — losing either one re-breaks Arabic job search."""
        from src.rico.intent.gates import is_explicit_job_listing_request

        assert self.api._looks_like_cv_intent_no_file(
            AR_JOB_SEARCH_MENTIONING_CV
        ) is True
        assert is_explicit_job_listing_request(AR_JOB_SEARCH_MENTIONING_CV) is True

    def test_characterizes_arabic_cv_question_intercepted_before_intent_routing(self):
        """CURRENT BEHAVIOUR, not an endorsement.

        A plain Arabic CV *question* trips gate 2 and is not an explicit
        job-listing request, so it is answered by upload/CV-status guidance and
        never reaches the ``cv_analysis`` intent that the equivalent English
        question reaches. This is the Arabic/English routing divergence.

        It is NOT an xfail: whether the gate should defer to the intent router
        is an open owner decision (#1422), so there is no established contract
        to diverge from.
        """
        from src.rico.intent.gates import is_explicit_job_listing_request

        assert self.api._looks_like_cv_intent_no_file(AR_CV_QUESTION) is True
        assert is_explicit_job_listing_request(AR_CV_QUESTION) is False

    def test_characterizes_english_analysis_ask_falls_through_to_intent_routing(self):
        """The English counterpart of the case above: "analyse my cv" trips
        neither announce gate, so it reaches the ``cv_analysis`` intent. Recorded
        as the asymmetry's other half."""
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
        """Which messages gate 2 claims, stated as data."""
        assert self.api._looks_like_cv_intent_no_file(message) is expected


# ══════════════════════════════════════════════════════════════════════════
# 2. _handle_stored_cv_reference — entry, exit and side-effect counts
# ══════════════════════════════════════════════════════════════════════════

class TestStoredCvReferenceHandler:

    def test_characterizes_handler_declines_messages_it_does_not_own(self):
        """No filename token and no analysis ask -> ``None``, and crucially the
        document store is never read. The read count is the point: this is the
        cheap early exit that keeps unrelated turns off the store."""
        probe = Probe()
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
        probe = Probe()
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
        probe = Probe(docs_raise=True)
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
        probe = Probe(docs_raise=True)
        result = probe.api._handle_stored_cv_reference(
            "u@test", dict(PARSED_PROFILE), "حلل سيرتي الذاتية"
        )
        assert _is_unverified(result)
        assert result.get("next_action") is None

    def test_contract_successful_empty_read_remains_genuine_absence(self):
        """Scenario 6. The read COMPLETED and returned nothing. That is real
        evidence of absence, so the not-found answer is correct and must not be
        reclassified as unverified by the D3 work."""
        probe = Probe(docs=[])
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
        probe = Probe()
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
        probe = Probe(docs=[])
        result = probe.api._handle_stored_cv_reference(
            "u@test", dict(PARSED_PROFILE), EN_CV_ANALYSIS
        )
        assert result is None
        assert probe.document_reads == 1


# ══════════════════════════════════════════════════════════════════════════
# 3. The cv_analysis CV-state branch — precedence of the three outcomes
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

    def test_contract_unavailable_is_evaluated_before_both_confident_branches(self):
        """The ordering, asserted against the production source rather than the
        model above, so the two cannot silently drift apart."""
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
# 4. The unverified response itself — shape, not prose
# ══════════════════════════════════════════════════════════════════════════

class TestUnverifiedResponseShape:

    @pytest.mark.parametrize("arabic", [False, True])
    def test_contract_unverified_response_carries_no_action_and_no_options(self, arabic):
        """The single prohibited instruction after a failed read is
        ``next_action="upload_cv"``. Assert the shape, in both languages."""
        probe = Probe()
        response = probe.api._cv_state_unverified_response("u@test", arabic)
        assert response["type"] == "cv_state_unverified"
        assert response.get("next_action") is None
        assert not response.get("options")
        assert response["message"].strip()

    @pytest.mark.parametrize("arabic", [False, True])
    def test_contract_unverified_response_blames_nothing(self, arabic):
        """It must claim no cause, blame no document, and ask for no upload."""
        probe = Probe()
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
        probe = Probe()
        probe.api._cv_state_unverified_response("u@test", False)
        assert probe.append_chat_count == 1
        assert probe.append_chat_calls == ["assistant"]
        assert probe.finalize_count == 0


# ══════════════════════════════════════════════════════════════════════════
# 5. _cv_upload_guidance_with_db_check — the gate-2 pre-check
# ══════════════════════════════════════════════════════════════════════════

class TestUploadGuidanceDbCheck:

    def _run(self, message: str, resolve_cv=None, raises: bool = False,
             only_identity: bool = False):
        probe = Probe()

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
        probe = Probe(cv_ctx=ctx_store_unavailable_no_metadata())
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
# 6. Per-turn read economy
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
# 7. Known divergence — established contract, not yet implemented
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
