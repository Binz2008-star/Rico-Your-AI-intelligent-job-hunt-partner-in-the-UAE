# -*- coding: utf-8 -*-
"""Regression for the production-proven failure: Rico asked whether to
change the active CV, the user answered ``نعم``, and no active-CV mutation
was executed or truthfully confirmed — instead a stale pending job search
was redeemed and an unrelated search launched.

Root cause: the "should I change the active CV?" offer was never backed by
a structured pending action, so a bare "yes"/"نعم" had nothing specific to
resolve against and fell through to whatever OTHER pending state happened
to exist (a stale ``pending_job_search`` armed by an earlier, unrelated
turn) — via ``_resolve_pending_intent``'s Priority-0 job-search redemption,
which fires unconditionally whenever ``pending_job_search`` is set.

Fix: a new structured pending-action contract (``_pending_field ==
"confirm_set_active_cv"`` + ``_pending_active_cv``), resolved inside
``_resolve_pending_field`` — which already runs before pending job-search
continuation, bare-role classification, generic intent classification, and
the starter-action fallback (see ``_handle_active_user_inner``'s call
order) — so the priority requirement falls out of the existing dispatch
order, no new priority plumbing required.

Review corrections applied in this revision:
  - The pending action is armed ONLY by an explicit user selection of a
    named stored CV ("activate Synthetic_Executive_CV.pdf") — never an
    automatic "more years of experience = better CV" recommendation.
  - The success reply no longer claims the new CV will power future job
    searches or CV analysis — only that the activation itself succeeded
    (no regression proves the search/analysis path consumes it yet).
  - A failed write or an unverified read-back never names ANY document
    (target or otherwise) as "current" — it reports verification failure
    plainly instead of guessing.
  - The pending action carries source_turn_id / created_at / expires_at;
    an expired confirmation is cleared and does not execute.

All data is synthetic. No real names, documents, or identifiers.
"""
from __future__ import annotations

import time

from tests.harness.chat_harness import ChatHarness

CV_A = {
    "id": "synthetic-cv-a",
    "doc_type": "cv",
    "is_primary": True,
    "filename": "Synthetic_Banking_CV.pdf",
    "years_experience": 8,
}
CV_B = {
    "id": "synthetic-cv-b",
    "doc_type": "cv",
    "is_primary": False,
    "filename": "Synthetic_Executive_CV.pdf",
    "years_experience": 10,
}


def _seed_two_cv_user(h: ChatHarness, user_id: str) -> None:
    h.seed(
        user_id, cv_status="parsed", cv_filename=CV_A["filename"],
        target_roles=["Banking Manager"], current_role="Banking Manager",
        years_experience=CV_A["years_experience"], preferred_cities=["Dubai"],
    )
    h.seed_documents(user_id, [dict(CV_A), dict(CV_B)])


def _active_cv(h: ChatHarness, user_id: str) -> "dict | None":
    return next((d for d in h.documents(user_id) if d.get("is_primary")), None)


def _pending(h: ChatHarness, user_id: str) -> "dict":
    return (h._rctx.get(user_id, {}) or {}).get("_pending_active_cv") or {}


# ── Explicit selection arms the pending action (no auto-recommendation) ─────

def test_explicit_selection_arms_pending_action_en():
    h = ChatHarness()
    user = "cv-explicit-en@test.com"
    _seed_two_cv_user(h, user)

    result = h.say(user, "Activate Synthetic_Executive_CV.pdf")
    assert result.get("type") == "cv_switch_confirmation_prompt"
    assert "Synthetic_Executive_CV.pdf" in str(result.get("message"))

    ctx = h._rctx.get(user, {})
    assert ctx.get("_pending_field") == "confirm_set_active_cv"
    pending = _pending(h, user)
    assert pending.get("action_type") == "set_active_cv"
    assert pending.get("target_document_id") == CV_B["id"]
    # Metadata completeness (review requirement).
    assert pending.get("source_turn_id"), "source_turn_id must be set"
    assert isinstance(pending.get("created_at"), float)
    assert isinstance(pending.get("expires_at"), float)
    assert pending["expires_at"] > pending["created_at"]


def test_explicit_selection_arms_pending_action_ar():
    h = ChatHarness()
    user = "cv-explicit-ar@test.com"
    _seed_two_cv_user(h, user)

    result = h.say(user, "فعّل Synthetic_Executive_CV.pdf")
    assert result.get("type") == "cv_switch_confirmation_prompt"
    ctx = h._rctx.get(user, {})
    assert ctx.get("_pending_field") == "confirm_set_active_cv"
    assert _pending(h, user).get("target_document_id") == CV_B["id"]


def test_no_automatic_years_only_recommendation():
    """A generic 'what should I do next?' — with NO explicit CV named —
    must NOT auto-recommend switching, even though CV B has more years."""
    h = ChatHarness()
    user = "cv-no-auto-rec@test.com"
    _seed_two_cv_user(h, user)

    result = h.say(user, "What should I do next?")
    assert result.get("type") != "cv_switch_confirmation_prompt", (
        f"a generic 'what next' must not auto-arm a CV switch: {result!r}"
    )
    assert h._rctx.get(user, {}).get("_pending_field") != "confirm_set_active_cv"
    assert _active_cv(h, user)["id"] == CV_A["id"], "active CV must be unchanged"


def test_naming_the_already_active_cv_does_not_arm_anything():
    h = ChatHarness()
    user = "cv-already-active@test.com"
    _seed_two_cv_user(h, user)

    result = h.say(user, "Activate Synthetic_Banking_CV.pdf")
    assert result.get("type") != "cv_switch_confirmation_prompt"
    assert h._rctx.get(user, {}).get("_pending_field") != "confirm_set_active_cv"


# ── Confirmation: success, no unsupported claims, zero search/profile mutation ─

def test_confirmation_success_en_no_unsupported_search_claim():
    h = ChatHarness()
    user = "cv-confirm-en@test.com"
    _seed_two_cv_user(h, user)
    h.say(user, "Activate Synthetic_Executive_CV.pdf")

    before_searches = len(h.searched_roles)
    profile_before = dict(vars(h.profile(user)))
    result = h.say(user, "yes")

    assert result.get("type") == "active_cv_changed"
    assert _active_cv(h, user)["id"] == CV_B["id"], "CV B must be canonical active CV"
    non_active = [d for d in h.documents(user) if d["id"] != CV_B["id"]]
    assert all(not d.get("is_primary") for d in non_active), "CV A must be inactive"
    reply = str(result.get("message"))
    assert "Synthetic_Executive_CV.pdf" in reply
    # Review requirement: no unsupported claim that search/analysis will use
    # the new CV — no regression proves that consumption path yet.
    assert "search" not in reply.lower(), f"reply must not claim future search use: {reply!r}"
    assert "analysis" not in reply.lower(), f"reply must not claim future analysis use: {reply!r}"

    ctx_after = h._rctx.get(user, {})
    assert ctx_after.get("_pending_field") is None, "pending action must be cleared"
    assert ctx_after.get("_pending_active_cv") is None
    assert len(h.searched_roles) == before_searches, "zero search operations"
    assert dict(vars(h.profile(user))) == profile_before, "zero profile mutations"


def test_confirmation_success_ar():
    h = ChatHarness()
    user = "cv-confirm-ar@test.com"
    _seed_two_cv_user(h, user)
    h.say(user, "فعّل Synthetic_Executive_CV.pdf")

    before_searches = len(h.searched_roles)
    profile_before = dict(vars(h.profile(user)))
    result = h.say(user, "نعم")

    assert result.get("type") == "active_cv_changed"
    assert _active_cv(h, user)["id"] == CV_B["id"]
    assert "Synthetic_Executive_CV.pdf" in str(result.get("message"))
    assert len(h.searched_roles) == before_searches
    assert dict(vars(h.profile(user))) == profile_before


# ── Repeated confirmation is idempotent ───────────────────────────────────────

def test_repeated_confirmation_idempotent_en():
    h = ChatHarness()
    user = "cv-repeat-en@test.com"
    _seed_two_cv_user(h, user)
    h.say(user, "Activate Synthetic_Executive_CV.pdf")
    h.say(user, "yes")

    docs_snapshot = h.documents(user)
    result2 = h.say(user, "yes")
    assert h.documents(user) == docs_snapshot, "no second mutation"
    assert isinstance(result2, dict)


def test_repeated_confirmation_idempotent_ar():
    h = ChatHarness()
    user = "cv-repeat-ar@test.com"
    _seed_two_cv_user(h, user)
    h.say(user, "فعّل Synthetic_Executive_CV.pdf")
    h.say(user, "نعم")

    docs_snapshot = h.documents(user)
    result2 = h.say(user, "نعم")
    assert h.documents(user) == docs_snapshot, "repeated نعم must not mutate twice"


# ── Stale pending job search cannot hijack yes/نعم ───────────────────────────

def test_stale_pending_job_search_does_not_hijack_confirmation_en():
    """The exact production failure: a stale pending_job_search armed by an
    earlier, unrelated turn must not redeem a bare 'yes' meant for the
    active-CV confirmation."""
    h = ChatHarness()
    user = "cv-stale-en@test.com"
    _seed_two_cv_user(h, user)
    ctx = h._rctx.setdefault(user, {})
    ctx["pending_job_search"] = {"role": "Environmental Manager", "location": ""}

    h.say(user, "Activate Synthetic_Executive_CV.pdf")
    before_searches = len(h.searched_roles)
    result = h.say(user, "yes")

    assert result.get("type") == "active_cv_changed", (
        f"'yes' must resolve the active-CV confirmation, not the stale job "
        f"search: {result!r}"
    )
    assert len(h.searched_roles) == before_searches, "must not launch Environmental Manager search"
    assert _active_cv(h, user)["id"] == CV_B["id"]


def test_stale_pending_job_search_does_not_hijack_confirmation_ar():
    h = ChatHarness()
    user = "cv-stale-ar@test.com"
    _seed_two_cv_user(h, user)
    ctx = h._rctx.setdefault(user, {})
    ctx["pending_job_search"] = {"role": "Environmental Manager", "location": ""}

    h.say(user, "فعّل Synthetic_Executive_CV.pdf")
    before_searches = len(h.searched_roles)
    result = h.say(user, "نعم")

    assert result.get("type") == "active_cv_changed", (
        f"'نعم' must resolve the active-CV confirmation, not the stale job "
        f"search: {result!r}"
    )
    assert len(h.searched_roles) == before_searches
    assert _active_cv(h, user)["id"] == CV_B["id"]


# ── Negative: "no" declines without changing anything ────────────────────────

def test_negative_no_en():
    h = ChatHarness()
    user = "cv-no-en@test.com"
    _seed_two_cv_user(h, user)
    h.say(user, "Activate Synthetic_Executive_CV.pdf")

    result = h.say(user, "no")
    assert result.get("type") == "info"
    assert _active_cv(h, user)["id"] == CV_A["id"], "declining must not change the active CV"
    assert h._rctx.get(user, {}).get("_pending_field") is None


def test_negative_no_ar():
    h = ChatHarness()
    user = "cv-no-ar@test.com"
    _seed_two_cv_user(h, user)
    h.say(user, "فعّل Synthetic_Executive_CV.pdf")

    result = h.say(user, "لا")
    assert result.get("type") == "info"
    assert _active_cv(h, user)["id"] == CV_A["id"]


# ── Failed write/read-back never mislabels the target as current ────────────

class _FailingActivationHarness(ChatHarness):
    """Simulates set_primary_document succeeding at the DB layer but the
    canonical read-back failing to confirm it (or the write itself failing)
    — the exact scenario the review flagged: no document, verified or not,
    may be named as "current" from unverified data."""

    def _activate_cv(self, user_id: str, doc_id: str):
        return None  # write/read-back verification failed


def test_failed_activation_never_names_any_document_as_current_en():
    h = _FailingActivationHarness()
    user = "cv-fail-en@test.com"
    _seed_two_cv_user(h, user)
    h.say(user, "Activate Synthetic_Executive_CV.pdf")

    result = h.say(user, "yes")
    assert result.get("type") == "info"
    reply = str(result.get("message"))
    assert "Synthetic_Executive_CV.pdf" not in reply, (
        f"must not name the failed target as current: {reply!r}"
    )
    assert "Synthetic_Banking_CV.pdf" not in reply, (
        f"must not guess/name any document as current from unverified data: {reply!r}"
    )
    # The in-memory store's own state is untouched since the (stubbed)
    # activation never actually flipped is_primary.
    assert _active_cv(h, user)["id"] == CV_A["id"]


def test_failed_activation_never_names_any_document_as_current_ar():
    h = _FailingActivationHarness()
    user = "cv-fail-ar@test.com"
    _seed_two_cv_user(h, user)
    h.say(user, "فعّل Synthetic_Executive_CV.pdf")

    result = h.say(user, "نعم")
    assert result.get("type") == "info"
    reply = str(result.get("message"))
    assert "Synthetic_Executive_CV.pdf" not in reply
    assert "Synthetic_Banking_CV.pdf" not in reply


# ── Expired confirmation does not execute ────────────────────────────────────

def test_expired_confirmation_does_not_execute_en():
    h = ChatHarness()
    user = "cv-expired-en@test.com"
    _seed_two_cv_user(h, user)
    h.say(user, "Activate Synthetic_Executive_CV.pdf")

    # Force the armed pending action into the past.
    ctx = h._rctx.get(user, {})
    ctx["_pending_active_cv"]["created_at"] = time.time() - 1000
    ctx["_pending_active_cv"]["expires_at"] = time.time() - 700
    h._rctx[user] = ctx

    result = h.say(user, "yes")
    assert result.get("type") == "info"
    assert "expire" in str(result.get("message")).lower()
    assert _active_cv(h, user)["id"] == CV_A["id"], "expired confirmation must not execute"
    assert h._rctx.get(user, {}).get("_pending_field") is None, "expired action must be cleared"


def test_expired_confirmation_does_not_execute_ar():
    h = ChatHarness()
    user = "cv-expired-ar@test.com"
    _seed_two_cv_user(h, user)
    h.say(user, "فعّل Synthetic_Executive_CV.pdf")

    ctx = h._rctx.get(user, {})
    ctx["_pending_active_cv"]["created_at"] = time.time() - 1000
    ctx["_pending_active_cv"]["expires_at"] = time.time() - 700
    h._rctx[user] = ctx

    result = h.say(user, "نعم")
    assert result.get("type") == "info"
    assert _active_cv(h, user)["id"] == CV_A["id"]
    assert h._rctx.get(user, {}).get("_pending_field") is None
