# -*- coding: utf-8 -*-
"""Fail-closed job-search routing and buffered verified delivery (PR2).

Two independent guarantees are pinned here, both about the *one* search path
adopted by PR1 (``RicoChatAPI._target_role_search_response`` → the verified
bundle built by ``src.services.verified_job_search.build_bundle``).

**Routing must positively prove search intent.** A turn that contains no
search request must not become a search. Absence of proof is not permission:
Rico may not infer a role, infer a location, or start a lifecycle operation
from prose it cannot classify.

**Delivery is buffered until the bundle is terminal-and-COMPLETED.** Listings
may be released only from a verified bundle whose execution reached
``SearchStatus.COMPLETED``. ``EMPTY``, ``PROVIDER_UNAVAILABLE`` and
``CANCELLED`` are terminal states that deliver nothing at all — no named job,
no card, no partial shortlist, no "completed" wording — because each of them
means something different to the user and none of them means "here are your
jobs".

Fail-first record — what these assertions found on ``main@4f1af6b``:

* ``test_unclassified_prose_does_not_start_a_job_search`` — the prose turns
  "Answer", "أجب", "؟" and "؟؟" each executed a full provider search. The chain
  was: a completed search response is persisted to chat history as its
  *serialised dict*; that JSON blob contains the literal text
  ``preferred cities``; ``_resolve_pending_field`` scans the last assistant turn
  for field-ask signals, matches its own machine payload, and concludes Rico had
  asked "which city?" — which it never had. The next message, whatever it was,
  was then taken as the city answer and re-dispatched as the invented intent
  ``"find matching jobs"``. Observed reply: *"I will target Operations Manager
  roles in Answer"* — a guessed role and a guessed location, with real job cards
  attached.
* ``test_provider_unavailable_terminal_delivers_no_completed_search`` — a
  bundle whose execution status was ``provider_unavailable`` was still delivered
  as ``type="job_matches"`` with ``operation_status="completed"``. The response
  contradicted the evidence it carried on the same surface.
* ``test_cancellation_after_the_cascade_leaks_no_listing`` — ownership lost
  after the cascade returned still delivered every listing, marked the operation
  completed, and wrote the results into the search context.

Hermetic: no DB, no provider, no network, no credentials. Synthetic data only.
"""
from __future__ import annotations

import os
from contextlib import ExitStack
from typing import Any
from unittest.mock import PropertyMock, patch

import pytest

from src.domain.job_search import SearchStatus
from src.jsearch_client import FetchResult
from src.rico_agent import RicoProfile
from tests.harness.chat_harness import ChatHarness


# ---------------------------------------------------------------------------
# Synthetic provider payloads
# ---------------------------------------------------------------------------

def _job(title: str, company: str = "SynthCo") -> dict[str, Any]:
    url = f"https://synthco.example/jobs/{abs(hash(title)) % 10000}"
    return {
        "title": title,
        "company": company,
        "apply_url": url,
        "job_apply_link": url,
        "location": "Dubai, UAE",
        "description": f"{title} position based in Dubai, UAE.",
    }


#: Titles that the integrity gate rejects against a "Compliance Manager"
#: request — the provider answered, nothing it returned is deliverable.
_OFF_DOMAIN_TITLES = ["Pastry Chef", "Sous Chef"]
_ON_DOMAIN_TITLES = ["Compliance Manager", "Compliance Officer"]


class _SearchRun:
    """Drive the real adopted search handler with a controllable provider.

    Records every observable side effect the delivery contract cares about:
    how many provider cascades ran, how many lifecycle operations were started,
    and what the lifecycle store was told about the outcome.
    """

    def __init__(
        self,
        titles: list[str],
        *,
        provider: str = "jsearch",
        quota_exhausted: bool = False,
        rate_limited: bool = False,
        cancel_after_cascade: bool = False,
    ) -> None:
        self._items = [_job(t) for t in titles]
        self._provider = provider
        self._quota_exhausted = quota_exhausted
        self._rate_limited = rate_limited
        self._cancel_after_cascade = cancel_after_cascade

        self.cascades: list[str] = []
        self.operations_started: list[str] = []
        self.completed_calls: list[tuple[str, int]] = []
        self.failed_calls: list[tuple[str, str]] = []
        self.legacy_fallback_calls: int = 0
        self.stored_operation: dict[str, Any] | None = None
        self._ownership_lost = False

    # -- stubs ---------------------------------------------------------------

    def _search(self, role: str, location: str = "", **_kw: Any) -> FetchResult:
        self.cascades.append(role)
        result = FetchResult(
            items=[dict(j) for j in self._items],
            provider=self._provider if self._items else "none",
            rate_limited=self._rate_limited,
            quota_exhausted=self._quota_exhausted,
        )
        if self._cancel_after_cascade:
            # Ownership is lost *after* the cascade handed back results: the
            # cascade itself never saw a cancelled token, so nothing downstream
            # is warned unless the delivery boundary re-checks.
            self._ownership_lost = True
        return result

    def _run_for_profile(self, _profile: Any, limit: Any = None) -> dict[str, Any]:
        self.legacy_fallback_calls += 1
        return {"status": "completed", "matches": []}

    def _ownership_lost_check(self, _op: str, _attempt: int) -> bool:
        return self._ownership_lost

    # -- driver --------------------------------------------------------------

    def run(self, requested_role: str, *, location: str = "") -> dict[str, Any]:
        profile = RicoProfile(user_id="synthetic@test")
        profile.target_roles = []
        profile.skills = []

        rctx: dict[str, Any] = {}

        from src import rico_chat_api as _mod
        from src.rico_chat_api import RicoChatAPI

        real_start = _mod.start_job_search_operation
        real_completed = _mod.mark_completed
        real_failed = _mod.mark_failed

        def _recording_start(*, user_id: str, role_or_query: str, operation_id: Any = None):
            result = real_start(
                user_id=user_id, role_or_query=role_or_query, operation_id=operation_id
            )
            self.operations_started.append(str(result.get("operation_id") or ""))
            return result

        def _recording_completed(user_id: str, operation_id: str, count: int, **kw: Any):
            self.completed_calls.append((str(operation_id), int(count)))
            return real_completed(user_id, operation_id, count, **kw)

        def _recording_failed(user_id: str, operation_id: str, error: str, **kw: Any):
            self.failed_calls.append((str(operation_id), str(error)))
            return real_failed(user_id, operation_id, error, **kw)

        with ExitStack() as stack:
            p = stack.enter_context
            p(patch("src.rico_db.RicoDB.available", new_callable=PropertyMock, return_value=False))
            p(patch("src.db.DB_ENABLED", False))
            os.environ.pop("REDIS_URL", None)
            p(patch("src.rico_chat_api.RicoChatAPI._search_jsearch_meta", side_effect=self._search))
            p(patch("src.rico_repo_adapter.RicoSystem.run_for_profile", side_effect=self._run_for_profile))
            p(patch("src.services.operation_state.ownership_lost", self._ownership_lost_check))
            p(patch("src.rico_chat_api.start_job_search_operation", _recording_start))
            p(patch("src.rico_chat_api.mark_completed", _recording_completed))
            p(patch("src.rico_chat_api.mark_failed", _recording_failed))
            p(patch("src.rico_chat_api.RicoChatAPI._get_recent_context", lambda _s, _u: dict(rctx)))
            p(patch("src.rico_chat_api.RicoChatAPI._store_recent_context",
                    lambda _s, _u, c: (rctx.clear(), rctx.update(c or {}))))
            p(patch("src.llm_scorer._embed", return_value=None))
            api = RicoChatAPI()
            resp = api._target_role_search_response(
                profile.user_id, requested_role, profile, location=location
            )
            # Read the lifecycle row back through the same in-memory store the
            # production code wrote it to, so the assertion is about persisted
            # state and not merely about which helper was called.
            from src.services.operation_state import get_operation

            self.stored_operation = (
                get_operation(profile.user_id, self.operations_started[0])
                if self.operations_started else None
            )
        self.recent_context = dict(rctx)
        return resp


# ---------------------------------------------------------------------------
# Shared assertions
# ---------------------------------------------------------------------------

_TERMINAL_STATES_WITH_NOTHING_TO_DELIVER = {
    SearchStatus.EMPTY.value,
    SearchStatus.PROVIDER_UNAVAILABLE.value,
    SearchStatus.CANCELLED.value,
}

#: Wording that asserts a finished, fruitful search. None of it may appear in a
#: reply whose bundle never reached COMPLETED.
_COMPLETED_SEARCH_WORDING = ("i found", "وجدت", "match(es)")


def _assert_names_no_job(resp: dict[str, Any]) -> None:
    """No named job, no card, no partial shortlist — on any surface."""
    matches = resp.get("matches") or []
    assert matches == [], f"a non-COMPLETED bundle delivered {len(matches)} listing(s)"
    assert not resp.get("result_count"), "result_count must be zero when nothing is deliverable"
    blob = repr(resp).lower()
    assert "synthco" not in blob, "a company name leaked from a bundle that never completed"
    assert "synthco.example" not in blob, "an apply link leaked from a bundle that never completed"


def _assert_no_completed_search_claim(resp: dict[str, Any]) -> None:
    assert resp.get("operation_status") != "completed", (
        "the response claimed a completed operation while its own evidence "
        f"reported {(resp.get('search_evidence') or {}).get('status')!r}"
    )
    message = str(resp.get("message") or "").lower()
    for phrase in _COMPLETED_SEARCH_WORDING:
        assert phrase not in message, f"completed-search wording {phrase!r} in a non-completed reply"


# ===========================================================================
# A. Unknown prose must not become a job search
# ===========================================================================

_UNCLASSIFIED_PROSE = ["Answer", "answer", "أجب", "؟", "؟؟", "ما هذا؟"]


def _seeded_harness(user_id: str) -> ChatHarness:
    h = ChatHarness()
    h.seed(
        user_id,
        target_roles=["Operations Manager"],
        skills=["operations", "logistics"],
        years_experience=6,
        current_role="Operations Manager",
        preferred_cities=["Dubai"],
        cv_status="parsed",
        cv_filename="cv.pdf",
    )
    return h


@pytest.mark.parametrize("prose", _UNCLASSIFIED_PROSE)
def test_unclassified_prose_does_not_start_a_job_search(prose: str) -> None:
    """Contract A — absence of proof of search intent means no search.

    The preceding turn is a normal, successful search. Nothing about it grants
    the *next* turn permission to search again, whatever that turn says.
    """
    user_id = f"prose-{abs(hash(prose))}@test"
    h = _seeded_harness(user_id)
    h.say(user_id, "Regional Compliance Manager")
    searches_before = len(h.searched_roles)
    cities_before = list(h.profile(user_id).preferred_cities or [])

    resp = h.say(user_id, prose)

    assert h.searched_roles[searches_before:] == [], (
        f"{prose!r} triggered a provider search for "
        f"{h.searched_roles[searches_before:]!r} — the turn proved no search intent"
    )
    assert not resp.get("operation_id"), f"{prose!r} started a lifecycle search operation"
    assert resp.get("type") != "job_matches", f"{prose!r} produced job cards"
    assert not (resp.get("matches") or []), f"{prose!r} named jobs"
    assert list(h.profile(user_id).preferred_cities or []) == cities_before, (
        f"{prose!r} was guessed to be a location and written to the profile"
    )


def test_a_persisted_structured_reply_is_not_a_question_rico_asked() -> None:
    """The proven root cause, pinned directly.

    A ``job_matches`` reply is persisted to chat history as its serialised dict.
    That payload contains the literal text ``preferred cities``. Reading it as
    though it were a question Rico asked makes the resolver claim a pending city
    prompt that never existed — and the request then guesses its route from
    Rico's own output.
    """
    user_id = "selfsignal@test"
    h = _seeded_harness(user_id)
    h.say(user_id, "Regional Compliance Manager")

    from src.rico_chat_api import RicoChatAPI

    api = RicoChatAPI()
    last_assistant = api._get_last_assistant_message(user_id)
    assert "preferred cities" in last_assistant.lower(), (
        "fixture drift: the persisted structured reply no longer contains the "
        "signal text this regression is about"
    )

    profile = h.profile(user_id)
    with ExitStack() as stack:
        p = stack.enter_context
        p(patch("src.rico_db.RicoDB.available", new_callable=PropertyMock, return_value=False))
        p(patch("src.db.DB_ENABLED", False))
        p(patch("src.rico_chat_api.RicoChatAPI._get_recent_context", lambda _s, _u: {}))
        p(patch("src.rico_chat_api.RicoChatAPI._store_recent_context", lambda _s, _u, _c: None))
        p(patch("src.rico_chat_api.upsert_profile", lambda **kw: profile))
        resolved = api._resolve_pending_field(user_id, "Answer", profile)

    assert resolved is None, (
        "a serialised response payload was read as a field-ask question — the "
        f"resolver claimed a pending prompt Rico never issued and returned {resolved!r}"
    )


# ===========================================================================
# B. An explicit search executes exactly once
# ===========================================================================

def test_explicit_search_runs_one_cascade_under_one_operation_id() -> None:
    run = _SearchRun(_ON_DOMAIN_TITLES)
    resp = run.run("Compliance Manager")

    assert resp.get("type") == "job_matches", resp.get("type")
    assert len(run.cascades) == 1, f"expected one provider cascade, got {run.cascades!r}"
    assert run.legacy_fallback_calls == 0, "the legacy fallback dispatched on a successful cascade"
    assert len(run.operations_started) == 1, (
        f"expected one lifecycle operation, got {run.operations_started!r}"
    )

    operation_id = run.operations_started[0]
    assert operation_id.strip()
    assert resp["operation_id"] == operation_id
    assert resp["search_evidence"]["operation_id"] == operation_id, (
        "the response and its evidence reported two identities for one search"
    )
    assert [op for op, _ in run.completed_calls] == [operation_id]


# ===========================================================================
# C. Partial provider output followed by a provider-unavailable terminal
# ===========================================================================

def test_provider_unavailable_terminal_delivers_no_completed_search() -> None:
    """Contract C — records arrived internally; the operation still ended unable.

    The provider answered with records *and* reported its quota exhausted. None
    of the records survived the integrity gate, so the verified bundle is
    terminal ``PROVIDER_UNAVAILABLE``: we could not properly ask, which is not
    the same fact as an empty market and must never be delivered as one.
    """
    run = _SearchRun(_OFF_DOMAIN_TITLES, quota_exhausted=True)
    resp = run.run("Compliance Manager")

    evidence = resp.get("search_evidence") or {}
    assert evidence.get("status") == SearchStatus.PROVIDER_UNAVAILABLE.value, (
        f"fixture drift: expected a provider_unavailable bundle, got {evidence.get('status')!r}"
    )
    assert evidence.get("raw_result_count", 0) > 0, "fixture drift: no records arrived internally"
    assert evidence.get("accepted_result_count") == 0

    _assert_names_no_job(resp)
    _assert_no_completed_search_claim(resp)
    assert resp.get("type") != "job_matches", (
        "a provider-unavailable outcome was delivered in the shape that names jobs"
    )
    assert len(run.cascades) == 1, (
        f"a degraded provider was re-queried — {run.cascades!r}; no automatic retry is permitted"
    )


def test_provider_unavailable_records_a_failed_not_completed_lifecycle_state() -> None:
    """The lifecycle row must say the execution errored, not that it finished.

    ``operation_state`` gives the two statuses different meanings and different
    consequences: ``completed`` is a finished execution, and
    ``_duplicate_operation_guard`` answers a repeat of that operation id with a
    status reply instead of re-executing; ``failed`` is terminal in the sense
    that a retry is legitimate and returns ``None`` from that guard so the
    search runs again. Writing ``completed`` for an execution that never
    reached a provider therefore does more than mislabel it — it tells the
    guard to refuse the retry the user is entitled to once quota recovers.

    ``mark_failed`` also refuses to downgrade a row that is already
    ``completed``, so this cannot be repaired by a later call: the first write
    has to be the right one.
    """
    run = _SearchRun(_OFF_DOMAIN_TITLES, quota_exhausted=True)
    run.run("Compliance Manager")

    operation_id = run.operations_started[0]

    assert run.completed_calls == [], (
        "an execution that could not reach a provider was marked completed: "
        f"{run.completed_calls!r}"
    )
    assert [op for op, _ in run.failed_calls] == [operation_id], (
        f"expected exactly one failed write for {operation_id!r}, got {run.failed_calls!r}"
    )

    stored = run.stored_operation
    assert stored is not None, "fixture drift: the lifecycle row could not be read back"
    assert stored.get("status") == "failed", (
        f"the persisted lifecycle status is {stored.get('status')!r}; a retry after "
        "quota recovery would be refused as a duplicate of a finished search"
    )

    # A machine-safe code only: no provider payload, query, user data or
    # exception text may be persisted on the lifecycle row.
    error = str(stored.get("error") or "")
    assert error == "provider_unavailable", f"unexpected lifecycle error value {error!r}"
    for leak in ("synthco", "compliance manager", "pastry", "chef", "synthetic@test"):
        assert leak not in error.lower(), f"lifecycle error leaked {leak!r}"


def test_provider_unavailable_is_never_phrased_as_an_empty_market() -> None:
    run = _SearchRun(_OFF_DOMAIN_TITLES, quota_exhausted=True)
    resp = run.run("Compliance Manager")

    assert resp.get("degraded") is True, (
        "a quota-exhausted execution must be reported as degraded, not as a market with no jobs"
    )
    assert resp.get("provider_state") in {"quota_exhausted", "rate_limited", "unavailable"}


# ===========================================================================
# D. Cancellation after partial internal work
# ===========================================================================

def test_cancellation_after_the_cascade_leaks_no_listing() -> None:
    """Contract D — a de-owned execution delivers nothing it already fetched."""
    run = _SearchRun(_ON_DOMAIN_TITLES, cancel_after_cascade=True)
    resp = run.run("Compliance Manager")

    _assert_names_no_job(resp)
    assert resp.get("operation_status") == "superseded", (
        f"expected a terminal cancelled/superseded reply, got {resp.get('operation_status')!r}"
    )
    assert resp.get("type") == "search_superseded", resp.get("type")


def test_a_cancelled_execution_emits_no_late_completion() -> None:
    run = _SearchRun(_ON_DOMAIN_TITLES, cancel_after_cascade=True)
    resp = run.run("Compliance Manager")

    assert [c for c in run.completed_calls if c[1] > 0] == [], (
        f"a cancelled execution reported a completion with results: {run.completed_calls!r}"
    )
    assert not run.recent_context.get("recent_search_matches"), (
        "a cancelled execution wrote its results into the search context"
    )
    assert "search_evidence" not in resp or not (resp.get("matches") or [])


# ===========================================================================
# E. Empty verified bundle
# ===========================================================================

def test_empty_bundle_delivers_an_honest_zero() -> None:
    run = _SearchRun([])
    resp = run.run("Compliance Manager")

    evidence = resp.get("search_evidence") or {}
    if evidence:
        assert evidence.get("status") in _TERMINAL_STATES_WITH_NOTHING_TO_DELIVER
        assert evidence.get("accepted_result_count") == 0
    _assert_names_no_job(resp)
    assert len(run.cascades) == 1


# ===========================================================================
# F. Completed verified bundle
# ===========================================================================

def test_completed_bundle_releases_its_listings_exactly_once() -> None:
    run = _SearchRun(_ON_DOMAIN_TITLES)
    resp = run.run("Compliance Manager")

    evidence = resp["search_evidence"]
    assert evidence["status"] == SearchStatus.COMPLETED.value
    matches = resp.get("matches") or []
    assert matches, "a completed bundle must deliver its verified listings"
    assert len(matches) <= evidence["accepted_result_count"], (
        "more jobs were shown than the execution accepted"
    )
    assert resp["result_count"] == len(matches)
    assert resp.get("operation_status") == "completed"

    # Released once: one completion write, and no duplicate titles in the payload.
    assert len(run.completed_calls) == 1, run.completed_calls
    titles = [str(m.get("title") or "") for m in matches]
    assert len(titles) == len(set(titles)), f"a listing was released twice: {titles!r}"

    # Only listings from the verified bundle — every shown company is synthetic
    # and every shown title came from the provider payload.
    provider_titles = {t for t in _ON_DOMAIN_TITLES}
    assert set(titles) <= provider_titles, (
        f"a title appeared that no verified listing stands behind: {set(titles) - provider_titles!r}"
    )


def test_completed_bundle_preserves_pr1_provenance() -> None:
    """PR1's guarantees remain intact — this slice adds to them, it does not relax them."""
    run = _SearchRun(_ON_DOMAIN_TITLES)
    resp = run.run("Compliance Manager")

    evidence = resp["search_evidence"]
    for field in (
        "operation_id", "provider", "status", "requested_role", "requested_location",
        "started_at", "duration_ms", "raw_result_count", "accepted_result_count",
    ):
        assert field in evidence, f"search_evidence lost {field!r}"
    serialised = repr(evidence).lower()
    assert "synthco" not in serialised, "evidence must carry no listing content"


# ===========================================================================
# G. JSON / SSE behavioural parity
# ===========================================================================

def test_an_explicit_search_is_transport_held_off_the_token_stream() -> None:
    """Neither surface may bypass buffering.

    An explicit job-listing request is never token-streamed: the SSE route
    resolves it through the same ``chat_service.send_message`` the JSON route
    uses and emits the result as one terminal ``done`` event. That is what makes
    buffering transport-independent rather than a JSON-only property.
    """
    from src.schemas.chat import RicoSessionContext
    from src.services import chat_service

    ctx = RicoSessionContext.for_public("web-failclosed01")
    assert chat_service.should_stream_ai(ctx, "find Compliance Manager jobs in Dubai", None) is False


def test_both_surfaces_report_one_status_for_one_terminal_outcome() -> None:
    """The same terminal outcome must read the same on JSON and on SSE."""
    import json as _json

    run_json = _SearchRun(_OFF_DOMAIN_TITLES, quota_exhausted=True)
    json_resp = run_json.run("Compliance Manager")

    sse_payload = _terminal_sse_payload(json_resp)
    assert sse_payload["type"] == json_resp["type"], (
        "SSE and JSON disagreed about the terminal type for one outcome"
    )
    assert sse_payload.get("operation_status") == json_resp.get("operation_status")
    assert (sse_payload.get("matches") or []) == (json_resp.get("matches") or []) == []
    # One terminal event, and no listing-bearing event before it.
    assert _json.dumps(sse_payload).count("synthco") == 0


def _terminal_sse_payload(response: dict[str, Any]) -> dict[str, Any]:
    """Round-trip a response through the SSE terminal encoder the route uses."""
    import json as _json

    from src.api.routers.rico_chat import _sse_done

    frame = _sse_done(response)
    assert frame.startswith("data: ") and frame.endswith("\n\n")
    assert frame.count("data: ") == 1, "a terminal outcome must be one SSE event"
    envelope = _json.loads(frame[len("data: "):].strip())
    assert envelope["type"] == "done"
    return envelope["response"]
