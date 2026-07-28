# -*- coding: utf-8 -*-
"""Saying thank you must not spend a provider call (global, all users).

After any successful search that had adjacent roles to offer, Rico arms a
pending job search for the first of them. Every redemption site then redeems an
armed search on a bare acknowledgement — and ``thanks`` / ``شكراً`` are
acknowledgements. So the single most common way a satisfied user ends a turn
burned a real JSearch call and answered with a search for a role they never
asked for.

The fix is one guard shared by all four redemption sites
(``_pending_search_redemption_blocked``), because a per-site fix is three
chances to miss one.

The fence in the other direction matters just as much and is asserted here: the
words that genuinely DO accept an offer — ``ok`` / ``تمام`` / ``yes`` /
``sounds good`` — must still redeem. Blocking those would resurrect the
"hollow promise" loop those call sites exist to close.

Hermetic: no DB, no provider, no network, no credentials, no user-specific data.
"""
from __future__ import annotations

from contextlib import ExitStack
from typing import Any
from unittest.mock import PropertyMock, patch

import pytest

USER = "synthetic@test"
ARMED = {"role": "Quality Manager", "location": "", "query_type": "adjacent_broaden"}


def _api_and_calls(stack: ExitStack) -> tuple[Any, list[str]]:
    """A RicoChatAPI with a pending search armed and the search call recorded."""
    p = stack.enter_context
    p(patch("src.rico_db.RicoDB.available", new_callable=PropertyMock, return_value=False))
    p(patch("src.db.DB_ENABLED", False))

    from src.rico_chat_api import RicoChatAPI

    calls: list[str] = []

    def _search(_self: Any, user_id: str, role: str, *_a: Any, **_kw: Any) -> dict[str, Any]:
        calls.append(role)
        return {"type": "job_matches", "matches": [], "message": "searched"}

    p(patch.object(RicoChatAPI, "_get_pending_job_search", lambda _s, _u: dict(ARMED)))
    p(patch.object(RicoChatAPI, "_clear_pending_job_search", lambda _s, _u: None))
    p(patch.object(RicoChatAPI, "_discard_pending_role_confirmation", lambda _s, _u: None))
    p(patch.object(RicoChatAPI, "_get_recent_context", lambda _s, _u: {}))
    p(patch.object(RicoChatAPI, "_store_recent_context", lambda _s, _u, _c: None))
    p(patch.object(RicoChatAPI, "_get_last_assistant_message", lambda _s, _u: ""))
    p(patch.object(RicoChatAPI, "_target_role_search_response", _search))
    return RicoChatAPI(), calls


# ── The guard itself ──────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "message",
    [
        "thanks", "Thanks!", "  THANK YOU  ", "thank you so much",
        "thanks a lot", "much appreciated", "appreciate it", "cheers",
        "ok thanks", "okay thank you",
        "شكرا", "شكراً", "شكراً جزيلاً", "شكرا!",
    ],
)
def test_gratitude_blocks_pending_search_redemption(message: str):
    with ExitStack() as stack:
        api, _ = _api_and_calls(stack)
        assert api._pending_search_redemption_blocked(USER, message) is True


@pytest.mark.parametrize(
    "message",
    [
        # These genuinely accept an offer and MUST keep redeeming.
        "ok", "okay", "yes", "sure", "go ahead", "sounds good", "got it",
        "تمام", "نعم", "ماشي", "حسنا", "كمل",
        # A real instruction that merely contains a courtesy word.
        "thanks, now search Quality Manager jobs in Dubai",
        "find me quality manager jobs please, thank you",
    ],
)
def test_genuine_confirmations_and_instructions_still_redeem(message: str):
    with ExitStack() as stack:
        api, _ = _api_and_calls(stack)
        assert api._pending_search_redemption_blocked(USER, message) is False


# ── A real redemption site ────────────────────────────────────────────────────

def test_thanks_does_not_dispatch_a_search_at_the_redemption_site():
    """`_resolve_pending_intent` Priority-0 redeems before any intent check."""
    with ExitStack() as stack:
        api, calls = _api_and_calls(stack)
        result = api._resolve_pending_intent(USER, "thanks", profile=object())

    assert calls == [], f"gratitude dispatched a provider search: {calls}"
    assert result is None, "the turn must fall through to a normal acknowledgement"


def test_arabic_thanks_does_not_dispatch_a_search():
    with ExitStack() as stack:
        api, calls = _api_and_calls(stack)
        result = api._resolve_pending_intent(USER, "شكراً", profile=object())

    assert calls == []
    assert result is None


def test_ok_still_dispatches_the_armed_search():
    """The regression fence: blocking gratitude must not block acceptance."""
    with ExitStack() as stack:
        api, calls = _api_and_calls(stack)
        result = api._resolve_pending_intent(USER, "ok", profile=object())

    assert calls == ["Quality Manager"], "an accepted offer must still execute"
    assert result is not None


def test_pending_search_survives_a_thank_you():
    """Gratitude declines to redeem; it does not CLEAR the armed search, so a
    later 'yes' still works inside the 15-minute TTL."""
    cleared: list[str] = []
    with ExitStack() as stack:
        p = stack.enter_context
        p(patch("src.rico_db.RicoDB.available", new_callable=PropertyMock, return_value=False))
        p(patch("src.db.DB_ENABLED", False))
        from src.rico_chat_api import RicoChatAPI

        p(patch.object(RicoChatAPI, "_get_pending_job_search", lambda _s, _u: dict(ARMED)))
        p(patch.object(RicoChatAPI, "_clear_pending_job_search", lambda _s, u: cleared.append(u)))
        p(patch.object(RicoChatAPI, "_discard_pending_role_confirmation", lambda _s, _u: None))
        p(patch.object(RicoChatAPI, "_get_recent_context", lambda _s, _u: {}))
        p(patch.object(RicoChatAPI, "_get_last_assistant_message", lambda _s, _u: ""))
        p(patch.object(
            RicoChatAPI, "_target_role_search_response",
            lambda *_a, **_k: {"type": "job_matches", "matches": []},
        ))
        api = RicoChatAPI()
        api._resolve_pending_intent(USER, "thanks", profile=object())

    assert cleared == [], "a thank-you must not consume the armed offer"


# ── The acknowledgement reply itself is unchanged ─────────────────────────────

def test_gratitude_still_gets_its_warm_reply():
    from src.rico_chat_api import _acknowledgement_reply

    assert _acknowledgement_reply("thanks") == "You're welcome!"
    assert _acknowledgement_reply("شكرا") == "عفواً!"
    # Trailing punctuation now resolves to the same reply instead of the generic one.
    assert _acknowledgement_reply("thanks!") == "You're welcome!"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
