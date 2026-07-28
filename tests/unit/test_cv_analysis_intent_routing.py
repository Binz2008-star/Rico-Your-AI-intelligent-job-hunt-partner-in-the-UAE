"""CV-analysis asks must reach grounded CV analysis, never a job search.

WHY THIS FILE EXISTS
--------------------
``tests/unit/test_journey1_cv_routing_characterization.py`` recorded — neutrally,
as a mechanism and explicitly *not* as an endorsement — that "analyse my cv
please" reaches ``_target_role_search_response`` and never touches the CV
grounding read. That characterization was written before an owner decision
existed, so it deliberately stopped at describing the behaviour.

The decision now exists, and it is a product contract:

    analyse / analyze / review / critique my CV
        -> ``cv_analysis``
        -> authoritative CV context is read
        -> zero job-search calls

This file is that contract, in English and Arabic. Everything here is a
``test_contract_*``: a failure is a user-visible regression, not a note about
internals.

WHAT THE DEFECT ACTUALLY IS
---------------------------
Three independent surfaces disagree about what an analysis ask is, and a message
only reaches grounded analysis if it satisfies the *narrowest* of them:

1. ``_CV_ANALYSIS_RE`` (the intent classifier) recognises ``review my cv`` and
   ``rate my cv``, but carries no ``analyse``/``analyze``/``critique`` verb, no
   ``curriculum vitae`` noun, and no Arabic at all. So "analyse my cv please"
   classifies as ``unknown``.
2. An ``unknown`` intent falls through the entire legacy cascade to the bare-role
   gate, where ``_looks_like_bare_target_role`` accepts the short CV phrase as a
   job title and runs a search.
3. Arabic never even reaches classification: the upload-announce gate matches
   "سيرتي الذاتية" and answers with upload guidance first.

``RicoChatAPI._CV_ANALYZE_ASK_RE`` already knows the analysis verbs in both
languages — it is simply not consulted anywhere on these paths.

This is a global routing defect. It affects every user whose phrasing is not the
one blessed literal, and every Arabic user regardless of phrasing; it is not
specific to any account, profile state, or saved-role list.

HOW ROUTING IS OBSERVED
-----------------------
Through ``Dispatch``, the harness that drives the real production entry point
``RicoChatAPI._handle_active_user_inner`` and counts what it did. It is imported
rather than re-created so both files observe the same dispatcher; the cascade is
never re-implemented here. ``ProfileWriteSpy`` adds the one observation
``Dispatch`` does not make: whether the turn wrote to the profile store.

Hermetic only — no database, no network, no provider, no account.
"""
from __future__ import annotations

from contextlib import ExitStack
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest

from tests.unit.test_journey1_cv_routing_characterization import (
    AR_CV_QUESTION,
    AR_JOB_SEARCH_MENTIONING_CV,
    AR_UPLOAD_ANNOUNCE,
    EN_JOB_SEARCH_MENTIONING_CV,
    EN_STORED_FILENAME,
    EN_UPLOAD_ANNOUNCE,
    Dispatch,
    ctx_genuinely_absent,
    ctx_readable,
    ctx_store_unavailable_no_metadata,
)


# ── The asks under contract ──────────────────────────────────────────────────

#: English analysis asks. Every one of these is the same request in a different
#: register; a user is entitled to the same answer from all four.
EN_ANALYSIS_ASKS = [
    pytest.param("analyse my cv please", id="en-analyse"),
    pytest.param("analyze my CV", id="en-analyze"),
    pytest.param("review my resume", id="en-review-resume"),
    pytest.param("critique my curriculum vitae", id="en-critique-cv"),
]

#: Arabic analysis asks. Same contract, and the surface with no coverage at all
#: today — the announce gate claims them before intent routing runs.
AR_ANALYSIS_ASKS = [
    pytest.param("حلل سيرتي الذاتية", id="ar-analyse"),
    pytest.param("راجع سيرتي الذاتية", id="ar-review"),
]

ALL_ANALYSIS_ASKS = EN_ANALYSIS_ASKS + AR_ANALYSIS_ASKS

#: English near-misses. Each pairs an analysis verb with a noun that is NOT a
#: CV. The first draft of this fix accepted "profile" as a CV noun, which made
#: all three of these ``cv_analysis`` — answering a question about a LinkedIn
#: page or a career profile with a CV review.
EN_NOT_CV_ASKS = [
    pytest.param("assess my profile", id="en-bare-profile"),
    pytest.param("review my LinkedIn profile", id="en-linkedin-profile"),
    pytest.param("evaluate my career profile", id="en-career-profile"),
]

#: Arabic near-misses. "سيرة" alone is just *biography*; only "سيرة ذاتية" is a
#: curriculum vitae. The first draft keyed on the bare noun, so a request to
#: analyse a company's history or a candidate's background became a review of
#: the user's own CV.
AR_NOT_CV_ASKS = [
    pytest.param("حلل سيرة الشركة", id="ar-company-history"),
    pytest.param("راجع سيرة المرشح", id="ar-candidate-background"),
    pytest.param("تحليل سيرة شخصية", id="ar-personal-biography"),
]

ALL_NOT_CV_ASKS = EN_NOT_CV_ASKS + AR_NOT_CV_ASKS

#: Response types that mean "the user was told to upload a CV, or told about
#: one, instead of being given the analysis they asked for".
CV_GUIDANCE_TYPES = frozenset({"cv_upload_guidance", "cv_already_exists"})

#: The two profile-store writers. A read-only question must reach neither.
_PROFILE_WRITERS = ("upsert_profile", "save_preferences")


class ProfileWriteSpy:
    """Counts writes to the profile store for the duration of one turn.

    Patched at ``src.repositories.profile_repo`` — the module every write on
    this path resolves through — so a write anywhere in the dispatcher is
    counted, not only one made by the handler under test.
    """

    def __init__(self) -> None:
        self.writes: list[str] = []

    def __enter__(self) -> "ProfileWriteSpy":
        self._stack = ExitStack()
        for name in _PROFILE_WRITERS:
            self._stack.enter_context(patch(
                f"src.repositories.profile_repo.{name}",
                side_effect=lambda *a, _n=name, **k: self.writes.append(_n),
            ))
        return self

    def __exit__(self, *exc: Any) -> None:
        self._stack.close()

    @property
    def count(self) -> int:
        return len(self.writes)


def run_analysis_ask(
    message: str,
    cv_ctx: Optional[Any] = None,
    has_cv: bool = True,
    target_roles: Optional[list] = None,
) -> tuple[Dispatch, dict[str, Any], ProfileWriteSpy]:
    """Drive one turn through the real dispatcher and return everything observed."""
    d = Dispatch(
        cv_ctx=cv_ctx if cv_ctx is not None else ctx_readable(),
        has_cv=has_cv,
        target_roles=target_roles,
    )
    with ProfileWriteSpy() as spy:
        result = d.run(message)
    return d, result, spy


# ══════════════════════════════════════════════════════════════════════════
# 1. The binding contract — analysis asks reach grounded CV analysis
# ══════════════════════════════════════════════════════════════════════════

class TestAnalysisAskReachesCvAnalysis:
    """The four clauses of the contract, asserted separately so a failure names
    which one broke rather than only that something did."""

    @pytest.mark.parametrize("message", ALL_ANALYSIS_ASKS)
    def test_contract_analysis_ask_answers_with_cv_analysis(self, message):
        """Clause 1. The user asked for an analysis and gets one — not a job
        list, not upload guidance, not a generated answer."""
        _d, result, _spy = run_analysis_ask(message)
        assert result.get("type") == "cv_analysis"

    @pytest.mark.parametrize("message", ALL_ANALYSIS_ASKS)
    def test_contract_analysis_ask_reads_the_cv_grounding(self, message):
        """Clause 2. An analysis that never read the CV state is not grounded,
        whatever it says. The read is counted, not assumed."""
        d, _result, _spy = run_analysis_ask(message)
        assert d.cv_context_reads >= 1

    @pytest.mark.parametrize("message", ALL_ANALYSIS_ASKS)
    def test_contract_analysis_ask_starts_no_job_search(self, message):
        """Clause 3, and the defect's headline symptom. Both the call count and
        the terminal list are asserted: the count proves no search ran, the
        list names which one did if the count is wrong."""
        d, _result, _spy = run_analysis_ask(message)
        assert d.job_search_calls == 0
        assert d.job_search_terminals == []

    @pytest.mark.parametrize("message", ALL_ANALYSIS_ASKS)
    def test_contract_analysis_ask_writes_nothing_to_the_profile(self, message):
        """Clause 4. Asking about a CV is a read-only question. A routing path
        that mutates saved roles or preferences on the way is a side effect the
        user did not ask for."""
        _d, _result, spy = run_analysis_ask(message)
        assert spy.writes == []

    @pytest.mark.parametrize("message", ALL_ANALYSIS_ASKS)
    def test_contract_analysis_ask_is_not_answered_by_the_llm(self, message):
        """The answer must be the deterministic grounded one. Reaching the LLM
        fallback means no gate claimed the turn — the same failure mode as the
        job search, with a friendlier face."""
        d, _result, _spy = run_analysis_ask(message)
        assert d.llm_fallback_calls == 0

    @pytest.mark.parametrize("message", ALL_ANALYSIS_ASKS)
    def test_contract_user_with_a_cv_is_never_told_to_upload_one(self, message):
        """A user who has a CV asked what is wrong with it. Answering with
        upload guidance is both wrong and a dead end."""
        _d, result, _spy = run_analysis_ask(message)
        assert result.get("type") not in CV_GUIDANCE_TYPES
        assert result.get("next_action") != "upload_cv"

    @pytest.mark.parametrize("message", ALL_ANALYSIS_ASKS)
    @pytest.mark.parametrize("target_roles", [[], ["Compliance Manager"],
                                              ["Warehouse Supervisor", "Chef"]])
    def test_contract_saved_target_roles_do_not_change_the_answer(
        self, message, target_roles
    ):
        """The routing must key on what the user asked, not on what happens to
        be saved. Empty, single and multiple unrelated roles all answer the
        same — otherwise the fix would only hold for one profile shape."""
        d, result, _spy = run_analysis_ask(message, target_roles=target_roles)
        assert result.get("type") == "cv_analysis"
        assert d.job_search_calls == 0


# ══════════════════════════════════════════════════════════════════════════
# 2. Truthfulness — the answer must match what was actually established
# ══════════════════════════════════════════════════════════════════════════

class TestAnalysisAskStaysTruthfulAboutCvState:
    """Routing to ``cv_analysis`` must not cost the Journey-1 D3 guarantees.
    Reaching the right handler with the wrong claim is not a fix."""

    @pytest.mark.parametrize("message", ALL_ANALYSIS_ASKS)
    def test_contract_unavailable_store_stays_unknown_not_absent(self, message):
        """The grounding read did not complete. The honest answer is that the
        state is unverified — never "you haven't uploaded one", and never an
        instruction to upload, which would imply the first upload vanished."""
        _d, result, _spy = run_analysis_ask(
            message, cv_ctx=ctx_store_unavailable_no_metadata()
        )
        assert result.get("type") == "cv_state_unverified"
        assert result.get("next_action") is None
        assert result.get("type") not in CV_GUIDANCE_TYPES

    @pytest.mark.parametrize("message", ALL_ANALYSIS_ASKS)
    def test_contract_unavailable_store_still_starts_no_job_search(self, message):
        """An outage must not be a back door to the very search this fix
        removes."""
        d, _result, _spy = run_analysis_ask(
            message, cv_ctx=ctx_store_unavailable_no_metadata()
        )
        assert d.job_search_calls == 0

    @pytest.mark.parametrize("message", ALL_ANALYSIS_ASKS)
    def test_contract_genuine_absence_is_still_stated_plainly(self, message):
        """A COMPLETED read proving no CV, in BOTH languages.

        This is the case where upload guidance is *earned*, and the two failure
        modes sit on either side of it: suppressing it (leaving the user with no
        way forward) and reaching it without evidence (the D3 violation). Both
        are asserted, together with the absence of any search.

        Arabic is covered here because it is the surface that previously never
        reached this branch at all — the announce gate answered first, so a
        genuinely CV-less Arabic user and a store outage were indistinguishable.
        """
        d, result, _spy = run_analysis_ask(
            message, cv_ctx=ctx_genuinely_absent(), has_cv=False
        )
        # Verified absence is evidence, so the unverified answer is WRONG here.
        assert result.get("type") != "cv_state_unverified"
        # ...and the answer must still be grounded in an authoritative read.
        assert d.cv_context_reads >= 1
        # Truthful: it says there is no CV, and points at the upload.
        assert "haven't uploaded one" in result["message"]
        assert "Upload your CV" in result["message"]
        # No search, no provider terminal, no generated answer.
        assert d.job_search_calls == 0
        assert d.job_search_terminals == []
        assert d.llm_fallback_calls == 0


# ══════════════════════════════════════════════════════════════════════════
# 2b. Negative fences — what an analysis VERB alone must not capture
# ══════════════════════════════════════════════════════════════════════════

class TestAnalysisVerbDoesNotCaptureNonCvNouns:
    """The widened predicate keys on a verb bound to a noun. These prove the
    noun half is doing real work: the same verbs, attached to something that is
    not a CV, must not be answered as a CV review.

    Both lists are regressions from the first draft of this fix, not
    hypotheticals — "profile" was an accepted English noun, and the Arabic arm
    accepted a bare "سيرة" (biography).
    """

    @pytest.mark.parametrize("message", ALL_NOT_CV_ASKS)
    def test_contract_non_cv_noun_is_not_cv_analysis(self, message):
        """The contract. Where these DO go is pre-existing routing this change
        does not touch, so only the CV-analysis outcome is fenced here."""
        _d, result, _spy = run_analysis_ask(message)
        assert result.get("type") != "cv_analysis"

    @pytest.mark.parametrize("message", ALL_NOT_CV_ASKS)
    def test_contract_non_cv_noun_does_not_read_the_cv_grounding(self, message):
        """The stronger form: not merely a different answer, but no CV work at
        all. A grounding read here would mean the message was routed as a CV ask
        and then rendered differently — the fence must hold at the routing
        decision, not at the response."""
        d, _result, _spy = run_analysis_ask(message)
        assert d.cv_context_reads == 0
        assert d.document_reads == 0

    @pytest.mark.parametrize(
        "message", [p.values[0] for p in ALL_NOT_CV_ASKS]
    )
    def test_contract_non_cv_noun_does_not_classify_as_cv_analysis(self, message):
        """Predicate level, so a regression names the exact phrase."""
        from src.agent.intelligence.intent_classifier import classify_intent

        assert classify_intent(message).intent != "cv_analysis"

    @pytest.mark.parametrize(
        "message",
        ["مراجعة السيرة الذاتية", "تحليل سيرة ذاتية"],
    )
    def test_contract_arabic_cv_phrase_variants_are_still_recognised(self, message):
        """The other side of the Arabic tightening: requiring the "ذاتية"
        qualifier must not cost the definite and indefinite CV phrasings."""
        from src.agent.intelligence.intent_classifier import classify_intent

        assert classify_intent(message).intent == "cv_analysis"


# ══════════════════════════════════════════════════════════════════════════
# 3. Regression fence — what must NOT move
# ══════════════════════════════════════════════════════════════════════════

class TestNeighbouringRoutingIsUnchanged:
    """The fix widens one predicate. These are the turns adjacent to it, pinned
    so the widening cannot swallow them."""

    def test_contract_english_job_search_mentioning_cv_remains_job_search(self):
        """The clearest way to get this fix wrong: a user asking for jobs that
        match their CV wants jobs. "my CV" appearing in the sentence must not
        redirect them to a CV review."""
        d, result, _spy = run_analysis_ask(EN_JOB_SEARCH_MENTIONING_CV)
        assert d.job_search_calls == 1
        assert result.get("type") == "job_matches"

    def test_contract_arabic_job_search_mentioning_cv_remains_job_search(self):
        """The same fence in Arabic, where the CV noun that trips every gate is
        the one this fix newly keys on."""
        d, result, _spy = run_analysis_ask(AR_JOB_SEARCH_MENTIONING_CV)
        assert d.job_search_calls == 1
        assert result.get("type") == "job_matches"

    def test_contract_filename_specific_request_still_reads_the_document(self):
        """Naming a stored file must still get the document-grounded answer —
        the strictly better path, which the intent-level fix must not divert."""
        d, result, _spy = run_analysis_ask(EN_STORED_FILENAME)
        assert result.get("type") == "cv_analysis"
        assert d.stored_cv_handler_calls == 1
        assert d.document_reads == 1
        assert d.job_search_calls == 0

    @pytest.mark.parametrize(
        "message", [EN_UPLOAD_ANNOUNCE, AR_UPLOAD_ANNOUNCE, AR_CV_QUESTION]
    )
    def test_contract_upload_announcements_are_still_answered_by_the_gate(
        self, message
    ):
        """Announcing or asking about the existence of a CV is not an analysis
        ask. These keep the upload-announce gate, and the Arabic exemption this
        fix adds must be narrow enough to leave them alone."""
        d, _result, _spy = run_analysis_ask(message)
        assert d.gate2_calls == 1
        assert d.job_search_calls == 0
        assert d.llm_fallback_calls == 0


# ══════════════════════════════════════════════════════════════════════════
# 4. Harness controls — so the zeros above are not vacuous
# ══════════════════════════════════════════════════════════════════════════

class TestHarnessControls:
    """Every assertion above is an ``== 0``. These prove each spy can fire, so a
    zero means the path was not taken rather than the spy was not wired."""

    def test_control_job_search_spy_fires_on_a_real_search(self):
        d, _result, _spy = run_analysis_ask(EN_JOB_SEARCH_MENTIONING_CV)
        assert d.job_search_calls == 1

    def test_control_llm_spy_fires_when_no_gate_claims_the_turn(self):
        d, _result, _spy = run_analysis_ask(
            "what do you think about my career prospects in general?"
        )
        assert d.llm_fallback_calls == 1

    def test_control_profile_write_spy_counts_a_write(self):
        """The profile-write spy patches real module attributes, so it is proved
        by calling through the patched module rather than by a routing turn."""
        import src.repositories.profile_repo as profile_repo

        with ProfileWriteSpy() as spy:
            profile_repo.upsert_profile("u@test", {})
            profile_repo.save_preferences("u@test", {})
        assert spy.writes == ["upsert_profile", "save_preferences"]
        assert spy.count == 2

    def test_control_cv_context_read_counter_moves(self):
        """And the grounding-read counter, proved on a turn already known to
        read it."""
        d, _result, _spy = run_analysis_ask("review my resume")
        assert d.cv_context_reads >= 1


# ══════════════════════════════════════════════════════════════════════════
# 5. The predicate itself — recognition is language- and verb-symmetric
# ══════════════════════════════════════════════════════════════════════════

class TestAnalysisAskRecognition:
    """Unit-level cover for the widened predicate. The behavioural contract is
    owned by the dispatcher tests above; this exists so a recognition gap names
    the exact phrase that regressed instead of failing eight scenarios at once.
    """

    @pytest.mark.parametrize("message", [p.values[0] for p in ALL_ANALYSIS_ASKS])
    def test_contract_every_analysis_ask_classifies_as_cv_analysis(self, message):
        from src.agent.intelligence.intent_classifier import classify_intent

        assert classify_intent(message).intent == "cv_analysis"

    @pytest.mark.parametrize(
        "message",
        [
            EN_JOB_SEARCH_MENTIONING_CV,
            AR_JOB_SEARCH_MENTIONING_CV,
            EN_UPLOAD_ANNOUNCE,
            AR_UPLOAD_ANNOUNCE,
            AR_CV_QUESTION,
        ],
    )
    def test_contract_non_analysis_messages_do_not_classify_as_cv_analysis(
        self, message
    ):
        """The other half of the predicate: widening must not annex job
        searches, upload announcements, or existence questions."""
        from src.agent.intelligence.intent_classifier import classify_intent

        assert classify_intent(message).intent != "cv_analysis"
