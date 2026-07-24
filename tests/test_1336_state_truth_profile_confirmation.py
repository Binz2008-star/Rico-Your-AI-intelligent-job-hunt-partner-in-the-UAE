# -*- coding: utf-8 -*-
"""State-truth regression for the profile-update consent gate (governing
invariant: never claim a mutation succeeded unless the response is composed
from the resulting canonical persisted state, not the pre-write intent).

Concrete, reproducible failure mode this guards against: the BUG-04
profile-update consent flow (``confirm_profile_update`` in
``RicoChatAPI._resolve_pending_field``) used to build its "Saved: ..."
confirmation text directly from the pre-write ``pending`` dict. If a field
is silently sanitized/dropped at the write boundary without raising — e.g.
``preferred_cities`` under #1336's fail-closed sanitizer, which omits an
invalid-only update entirely rather than overwriting a valid existing value
— the confirmation would falsely claim that field was saved.
"""
from __future__ import annotations

from tests.harness.chat_harness import ChatHarness

USER = "state-truth-confirm@test.com"


class _RejectingHarness(ChatHarness):
    """Mirrors profile_repo.upsert_profile's real fail-closed contract for
    preferred_cities: an invalid-looking value (the exact #1336 corruption
    shape) is silently dropped from the write, preserving whatever was
    already stored, instead of being written verbatim like the base
    harness's ``_upsert_profile`` does."""

    _REJECTED_CITY_VALUE = ["ابحث عن وظيفه"]

    def _upsert_profile(self, user_id: str, updates: dict):
        filtered = dict(updates)
        if filtered.get("preferred_cities") == self._REJECTED_CITY_VALUE:
            del filtered["preferred_cities"]
        return super()._upsert_profile(user_id, filtered)


def test_confirmation_never_claims_a_silently_rejected_field_was_saved():
    h = _RejectingHarness()
    h.seed(
        USER, cv_status="parsed", cv_filename="cv.pdf",
        target_roles=["Environmental Manager"], years_experience=6,
        preferred_cities=["Dubai"],
    )
    ctx = h._rctx.setdefault(USER, {})
    ctx["_pending_field"] = "confirm_profile_update"
    ctx["_pending_profile_update"] = {
        "preferred_cities": _RejectingHarness._REJECTED_CITY_VALUE,  # will be rejected
        "years_experience": 8,  # will genuinely persist
    }

    result = h.say(USER, "yes")
    assert isinstance(result, dict)
    reply = str(result.get("message") or "")

    profile = h.profile(USER)
    assert profile.preferred_cities == ["Dubai"], (
        "the rejected field must keep its existing valid value, not the "
        f"invalid pending one: {profile.preferred_cities!r}"
    )
    assert profile.years_experience == 8, "the genuinely-valid field must persist"

    assert "preferred cit" not in reply.lower() or "not saved" in reply.lower(), (
        f"reply must not claim the rejected field was saved: {reply!r}"
    )
    assert "8" in reply or "years of experience" in reply.lower(), (
        f"reply must confirm the field that actually changed: {reply!r}"
    )

    assert result.get("updated") == {"years_experience": 8}, (
        f"'updated' must reflect only what was actually persisted: {result.get('updated')!r}"
    )
    assert result.get("rejected") == ["preferred_cities"], (
        f"'rejected' must name the field that did not take: {result.get('rejected')!r}"
    )


def test_confirmation_still_reports_normally_when_everything_persists():
    """Non-regression: when nothing is rejected, behavior is unchanged —
    all intended fields are reported saved."""
    h = ChatHarness()
    h.seed(
        USER + ".ok", cv_status="parsed", cv_filename="cv.pdf",
        target_roles=["Environmental Manager"], years_experience=6,
        preferred_cities=["Dubai"],
    )
    ctx = h._rctx.setdefault(USER + ".ok", {})
    ctx["_pending_field"] = "confirm_profile_update"
    ctx["_pending_profile_update"] = {"years_experience": 9}

    result = h.say(USER + ".ok", "yes")
    assert result.get("updated") == {"years_experience": 9}
    assert result.get("rejected") == []
    assert h.profile(USER + ".ok").years_experience == 9


def test_repeated_confirmation_does_not_mutate_twice():
    """The pending state is cleared one-shot regardless of outcome, so a
    second 'yes' with nothing newly pending must not re-apply the mutation."""
    h = ChatHarness()
    h.seed(
        USER + ".repeat", cv_status="parsed", cv_filename="cv.pdf",
        target_roles=["Environmental Manager"], years_experience=6,
    )
    ctx = h._rctx.setdefault(USER + ".repeat", {})
    ctx["_pending_field"] = "confirm_profile_update"
    ctx["_pending_profile_update"] = {"years_experience": 10}

    first = h.say(USER + ".repeat", "yes")
    assert first.get("type") == "preferences_updated"
    assert h.profile(USER + ".repeat").years_experience == 10

    # Nothing pending anymore — a second "yes" must not silently redo a
    # mutation or crash.
    second = h.say(USER + ".repeat", "yes")
    assert isinstance(second, dict)
    assert h.profile(USER + ".repeat").years_experience == 10
