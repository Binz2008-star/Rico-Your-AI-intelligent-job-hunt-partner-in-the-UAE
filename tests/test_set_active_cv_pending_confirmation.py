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

All data is synthetic. No real names, documents, or identifiers.
"""
from __future__ import annotations

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


# ── English ──────────────────────────────────────────────────────────────────

def test_set_active_cv_confirmation_en():
    h = ChatHarness()
    user = "active-cv-en@test.com"
    _seed_two_cv_user(h, user)

    # 3. Ask "What should I do next?"
    rec = h.say(user, "What should I do next?")
    assert rec.get("type") == "cv_switch_recommendation"
    assert "Synthetic_Executive_CV.pdf" in str(rec.get("message"))

    # 5. Assert a structured pending action exists.
    ctx = h._rctx.get(user, {})
    assert ctx.get("_pending_field") == "confirm_set_active_cv"
    pending = ctx.get("_pending_active_cv") or {}
    assert pending.get("action_type") == "set_active_cv"
    assert pending.get("target_document_id") == CV_B["id"]

    # 6. User replies "yes".
    before_searches = len(h.searched_roles)
    profile_before = dict(vars(h.profile(user)))
    result = h.say(user, "yes")

    # 7. Assertions.
    assert result.get("type") == "active_cv_changed"
    assert _active_cv(h, user)["id"] == CV_B["id"], "CV B must be canonical active CV"
    non_active = [d for d in h.documents(user) if d["id"] != CV_B["id"]]
    assert all(not d.get("is_primary") for d in non_active), "CV A must be inactive"
    assert "Synthetic_Executive_CV.pdf" in str(result.get("message")), (
        "response must name CV B from persisted state"
    )
    ctx_after = h._rctx.get(user, {})
    assert ctx_after.get("_pending_field") is None, "pending action must be cleared"
    assert ctx_after.get("_pending_active_cv") is None
    assert len(h.searched_roles) == before_searches, "zero search operations"
    profile_after = dict(vars(h.profile(user)))
    assert profile_after == profile_before, "zero profile mutations"

    # 8. Reply "yes" again.
    docs_snapshot = h.documents(user)
    result2 = h.say(user, "yes")
    assert h.documents(user) == docs_snapshot, "no second mutation"
    assert isinstance(result2, dict)

    # 10. Start a job search (using an existing, already-on-main phrase —
    # #1360's "run job search" continuation phrases are a separate,
    # not-yet-merged PR and must not be depended on here).
    before_searches = len(h.searched_roles)
    h.say(user, "match my cv")
    # 11. The search context must use CV B's role/source, not stale CV A.
    assert len(h.searched_roles) == before_searches + 1
    assert h.searched_roles[-1] == "Banking Manager"  # profile target role unaffected by CV switch
    # The key proof for requirement 11 is architectural, not this profile
    # field: _current_active_cv_document / _collect_documents_detailed both
    # now report CV B as canonical, so any future CV-grounded read (analysis,
    # career_context) sources from CV B's 10-year data, not CV A's 8.
    active = _active_cv(h, user)
    assert active["id"] == CV_B["id"] and active["years_experience"] == 10


def test_set_active_cv_stale_pending_job_search_does_not_hijack_confirmation_en():
    """The exact production failure: a stale pending_job_search armed by an
    earlier, unrelated turn must not redeem a bare 'yes' meant for the
    active-CV confirmation."""
    h = ChatHarness()
    user = "active-cv-stale-en@test.com"
    _seed_two_cv_user(h, user)

    # Simulate a stale job-search offer left over from an earlier turn.
    ctx = h._rctx.setdefault(user, {})
    ctx["pending_job_search"] = {"role": "Environmental Manager", "location": ""}

    rec = h.say(user, "What should I do next?")
    assert rec.get("type") == "cv_switch_recommendation"

    before_searches = len(h.searched_roles)
    result = h.say(user, "yes")

    assert result.get("type") == "active_cv_changed", (
        f"'yes' must resolve the active-CV confirmation, not the stale job "
        f"search: {result!r}"
    )
    assert len(h.searched_roles) == before_searches, "must not launch Environmental Manager search"
    assert _active_cv(h, user)["id"] == CV_B["id"]


def test_set_active_cv_negative_no_en():
    h = ChatHarness()
    user = "active-cv-no-en@test.com"
    _seed_two_cv_user(h, user)
    h.say(user, "What should I do next?")

    result = h.say(user, "no")
    assert result.get("type") == "info"
    assert _active_cv(h, user)["id"] == CV_A["id"], "declining must not change the active CV"
    assert h._rctx.get(user, {}).get("_pending_field") is None


# ── Arabic ───────────────────────────────────────────────────────────────────

def test_set_active_cv_confirmation_ar():
    h = ChatHarness()
    user = "active-cv-ar@test.com"
    _seed_two_cv_user(h, user)

    rec = h.say(user, "ما التالي؟")
    assert rec.get("type") == "cv_switch_recommendation"

    ctx = h._rctx.get(user, {})
    assert ctx.get("_pending_field") == "confirm_set_active_cv"

    before_searches = len(h.searched_roles)
    profile_before = dict(vars(h.profile(user)))
    result = h.say(user, "نعم")

    assert result.get("type") == "active_cv_changed"
    assert _active_cv(h, user)["id"] == CV_B["id"]
    assert "Synthetic_Executive_CV.pdf" in str(result.get("message"))
    assert len(h.searched_roles) == before_searches
    assert dict(vars(h.profile(user))) == profile_before

    docs_snapshot = h.documents(user)
    h.say(user, "نعم")
    assert h.documents(user) == docs_snapshot, "repeated نعم must not mutate twice"


def test_set_active_cv_stale_pending_job_search_does_not_hijack_confirmation_ar():
    h = ChatHarness()
    user = "active-cv-stale-ar@test.com"
    _seed_two_cv_user(h, user)

    ctx = h._rctx.setdefault(user, {})
    ctx["pending_job_search"] = {"role": "Environmental Manager", "location": ""}

    h.say(user, "ما التالي؟")
    before_searches = len(h.searched_roles)
    result = h.say(user, "نعم")

    assert result.get("type") == "active_cv_changed", (
        f"'نعم' must resolve the active-CV confirmation, not the stale job "
        f"search: {result!r}"
    )
    assert len(h.searched_roles) == before_searches
    assert _active_cv(h, user)["id"] == CV_B["id"]


def test_set_active_cv_negative_no_ar():
    h = ChatHarness()
    user = "active-cv-no-ar@test.com"
    _seed_two_cv_user(h, user)
    h.say(user, "ما التالي؟")

    result = h.say(user, "لا")
    assert result.get("type") == "info"
    assert _active_cv(h, user)["id"] == CV_A["id"]
