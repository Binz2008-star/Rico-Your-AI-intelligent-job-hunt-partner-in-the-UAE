# -*- coding: utf-8 -*-
"""The adopted consumer may not name a job without evidence behind it.

Fail-first record. On ``main`` before this change, the assertion in
``test_job_matches_response_carries_execution_evidence`` failed: the real
``RicoChatAPI._target_role_search_response`` returned a ``job_matches`` response
whose ``matches`` carried titles, companies and apply links, while the response
itself said nothing about which provider produced them, when, how many raw
records arrived, or how many were rejected on the way. The job structure was
real and the provenance was absent — a reply could name a company that no
evidence object stood behind.

This file pins the invariant for the one consumer adopted in this slice:
a ``job_matches`` response from that path always carries ``search_evidence``,
and its accepted count always equals the number of matches shown.

Hermetic: no DB, no provider, no network, no credentials. Synthetic data only.
"""
from __future__ import annotations

import os
from contextlib import ExitStack
from typing import Any
from unittest.mock import PropertyMock, patch

import pytest

from src.jsearch_client import FetchResult
from src.rico_agent import RicoProfile


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


class _Driver:
    """Controllable provider payload → the real search handler."""

    def __init__(self, titles: list[str], *, provider: str = "jsearch") -> None:
        self._items = [_job(t) for t in titles]
        self._provider = provider

    def _search(self, role: str, location: str = "", **_kw: Any) -> FetchResult:
        return FetchResult(items=[dict(j) for j in self._items], provider=self._provider)

    def run(self, requested_role: str, *, drop_operation_id: bool = False) -> dict[str, Any]:
        profile = RicoProfile(user_id="synthetic@test")
        if hasattr(profile, "target_roles"):
            profile.target_roles = []
        if hasattr(profile, "skills"):
            profile.skills = []

        rctx: dict[str, Any] = {}

        def _get_rctx(_self: Any, uid: str) -> dict[str, Any]:
            return dict(rctx)

        def _store_rctx(_self: Any, uid: str, ctx: dict[str, Any]) -> None:
            rctx.clear()
            rctx.update(ctx or {})

        from src.rico_chat_api import RicoChatAPI

        with ExitStack() as stack:
            p = stack.enter_context
            p(patch("src.rico_db.RicoDB.available", new_callable=PropertyMock, return_value=False))
            p(patch("src.db.DB_ENABLED", False))
            os.environ.pop("REDIS_URL", None)
            p(patch("src.rico_chat_api.RicoChatAPI._search_jsearch_meta", side_effect=self._search))
            p(patch("src.rico_chat_api.RicoChatAPI._get_recent_context", _get_rctx))
            p(patch("src.rico_chat_api.RicoChatAPI._store_recent_context", _store_rctx))
            p(patch("src.llm_scorer._embed", return_value=None))
            api = RicoChatAPI()
            if drop_operation_id:
                # The audited case: a client-supplied identity that is
                # whitespace-only. It must be normalised to None *before* the
                # lifecycle write so the store generates the one real id —
                # not persisted blank and then papered over downstream.
                api._current_operation_id = "        "
            return api._target_role_search_response(profile.user_id, requested_role, profile)


# ---------------------------------------------------------------------------
# The defect this slice closes
# ---------------------------------------------------------------------------


def test_job_matches_response_carries_execution_evidence():
    """The assertion that had nothing to bind to before the contract existed."""
    resp = _Driver([
        "Compliance Manager",
        "Compliance Officer",
        "Senior Compliance Manager",
    ]).run("Compliance Manager")

    if resp.get("type") != "job_matches":
        # The path legitimately has other outcomes; this test only constrains
        # the one that names jobs.
        assert not resp.get("matches"), "a non-job_matches reply must name no job"
        return

    evidence = resp.get("search_evidence")
    assert evidence, (
        "a job_matches response must carry the evidence of the execution that "
        "produced it — without it, a named company has no provenance"
    )

    for field in (
        "operation_id",
        "provider",
        "status",
        "requested_role",
        "started_at",
        "duration_ms",
        "raw_result_count",
        "accepted_result_count",
    ):
        assert field in evidence, f"search_evidence is missing {field!r}"

    assert evidence["provider"], "evidence must name the provider that answered"
    assert evidence["status"] in {
        "completed",
        "empty",
        "provider_unavailable",
        "cancelled",
    }, f"unexpected status {evidence['status']!r}"


def test_shown_matches_never_exceed_the_accepted_count():
    """Every card shown is one the gate accepted — not one the model invented."""
    resp = _Driver([
        "Compliance Manager",
        "Compliance Officer",
    ]).run("Compliance Manager")

    if resp.get("type") != "job_matches":
        return

    evidence = resp["search_evidence"]
    matches = resp.get("matches") or []
    assert len(matches) <= evidence["accepted_result_count"], (
        "more jobs were shown than the execution accepted — the surplus has no "
        "verified listing behind it"
    )
    assert evidence["accepted_result_count"] <= evidence["raw_result_count"]


def test_request_without_an_operation_id_gets_one_server_side():
    """The client is never the source of truth for operation identity.

    A request carrying no operation id must still produce a traceable bundle,
    and the id the response reports must be the *same* value the evidence
    carries — two generated ids would look like provenance while pointing
    apart.
    """
    resp = _Driver(["Compliance Manager"]).run(
        "Compliance Manager", drop_operation_id=True
    )

    evidence = resp.get("search_evidence")
    if resp.get("type") != "job_matches":
        # Other outcomes are permitted, but must still name no job.
        assert not resp.get("matches")
        return

    assert evidence, "a job_matches response must carry evidence"
    assert evidence["operation_id"].strip(), (
        "the server must mint an operation id when the request carries none"
    )
    assert resp.get("operation_id") == evidence["operation_id"], (
        "the response and its evidence must report one operation id, not two"
    )


def test_whitespace_incoming_id_is_normalised_before_the_lifecycle_write():
    """The store must never persist a blank identity.

    A whitespace-only id is truthy, so passing it through would key the
    lifecycle row on the blank value and force a second id downstream — one
    search with two identities. Normalisation happens *before* the write, and
    the store stays the single generator.
    """
    from src.rico_chat_api import RicoChatAPI

    seen: dict[str, Any] = {}

    def _fake_start(*, user_id: str, role_or_query: str, operation_id: Any = None):
        seen["operation_id_passed_to_store"] = operation_id
        return {"operation_id": "op-generated-by-store", "attempt": 1, "claimed": True}

    api = RicoChatAPI()
    api._current_operation_id = "        "  # eight spaces, the audited value

    with patch("src.rico_chat_api.start_job_search_operation", _fake_start):
        operation = api._begin_job_search_operation("synthetic@test", "Compliance Manager")

    assert seen["operation_id_passed_to_store"] is None, (
        "a whitespace-only id must be normalised to None before the lifecycle "
        "write, so the store generates instead of persisting a blank identity"
    )
    assert operation["operation_id"] == "op-generated-by-store"
    assert api._current_operation_id == "op-generated-by-store"


def test_a_valid_supplied_id_is_preserved_unchanged():
    from src.rico_chat_api import RicoChatAPI

    seen: dict[str, Any] = {}

    def _fake_start(*, user_id: str, role_or_query: str, operation_id: Any = None):
        seen["operation_id_passed_to_store"] = operation_id
        return {"operation_id": operation_id, "attempt": 1, "claimed": True}

    api = RicoChatAPI()
    api._current_operation_id = "op-client-supplied-123"

    with patch("src.rico_chat_api.start_job_search_operation", _fake_start):
        operation = api._begin_job_search_operation("synthetic@test", "Compliance Manager")

    assert seen["operation_id_passed_to_store"] == "op-client-supplied-123"
    assert operation["operation_id"] == "op-client-supplied-123"


def test_a_store_returning_no_id_fails_closed():
    """No identity, no search — and therefore no named job and no bundle."""
    from src.rico_chat_api import RicoChatAPI

    def _fake_start(*, user_id: str, role_or_query: str, operation_id: Any = None):
        return {"operation_id": "   ", "attempt": 1, "claimed": True}

    api = RicoChatAPI()
    api._current_operation_id = None

    with patch("src.rico_chat_api.start_job_search_operation", _fake_start):
        with pytest.raises(RuntimeError, match="operation_id"):
            api._begin_job_search_operation("synthetic@test", "Compliance Manager")


def test_no_downstream_second_id_fallback_remains():
    """The handler must not mint an identity of its own, anywhere."""
    import inspect

    from src.rico_chat_api import RicoChatAPI

    source = inspect.getsource(RicoChatAPI._target_role_search_response)
    assert "uuid" not in source, (
        "the search handler must not generate an operation id — the lifecycle "
        "store is the single generator and owner"
    )


def test_one_identity_from_storage_through_evidence_to_response():
    """Trace one operation id end to end: stored == response == evidence."""
    stored: dict[str, Any] = {}
    real_start = None

    from src import rico_chat_api as _mod

    real_start = _mod.start_job_search_operation

    def _recording_start(*, user_id: str, role_or_query: str, operation_id: Any = None):
        result = real_start(
            user_id=user_id, role_or_query=role_or_query, operation_id=operation_id
        )
        stored["persisted"] = str(result.get("operation_id") or "")
        return result

    with patch("src.rico_chat_api.start_job_search_operation", _recording_start):
        resp = _Driver(["Compliance Manager"]).run(
            "Compliance Manager", drop_operation_id=False
        )

    if resp.get("type") != "job_matches":
        assert not resp.get("matches")
        return

    persisted = stored["persisted"]
    assert persisted.strip(), "the lifecycle store must persist a non-empty id"
    assert resp["operation_id"] == persisted, "response id diverged from storage"
    assert resp["search_evidence"]["operation_id"] == persisted, (
        "evidence id diverged from storage — one search would carry two identities"
    )


def test_evidence_is_execution_metadata_and_leaks_no_listing_content():
    """Provenance must not become a second, unfiltered copy of the results."""
    resp = _Driver(["Compliance Manager"]).run("Compliance Manager")
    if resp.get("type") != "job_matches":
        return

    serialised = repr(resp["search_evidence"]).lower()
    assert "synthco" not in serialised, "evidence must not carry company names"
    assert "synthco.example" not in serialised, "evidence must not carry apply links"
