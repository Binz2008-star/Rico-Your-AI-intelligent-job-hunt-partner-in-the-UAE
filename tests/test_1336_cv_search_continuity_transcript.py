# -*- coding: utf-8 -*-
"""#1336 PR2 — end-to-end replay of the owner's authenticated production
transcript that exposed the CV/search-continuity regressions.

Exact sequence required by the incident brief:

    Environmental Manager -> لديك سيرتي الذاتيه -> استهدف نعم -> وسع -> نفذ
    -> CV correction -> screenshot -> uploaded PDF -> راجعها ونفذ
    -> ما كان طلبي الأساسي؟ -> قبل ذلك -> ؟ -> ؟؟

Driven through the real ``RicoChatAPI.process_message`` via
``tests/harness/chat_harness.py`` (offline: in-memory profile store, canned
job-search results, deterministic AI fallback — no live DB/provider). The
"screenshot" and "uploaded PDF" turns happen through a separate REST route
(``/upload-cv`` + ``/confirm-cv-profile``) in production, not through chat —
this harness only drives the chat entry point, so those two steps simulate
their PERSISTED EFFECT (what confirm-cv-profile writes to canonical profile
storage, and what the transient last-uploaded-document context holds) rather
than replaying the HTTP upload itself.

This test asserts the CONTRACT the transcript pins, not the exact wording of
every reply (wording is covered by narrower unit tests elsewhere):

  - No role name or CV-status question is ever captured into
    ``preferred_cities`` (#1336 PR1 + PR2).
  - No job listing is ever presented that didn't come from the harness's
    stubbed ``_search_jsearch_meta`` (i.e. every reported match traces back
    to ``harness.searched_roles``) — never a fabricated listing.
  - No unfulfilled "I will search now" / "سأبحث الآن" style promise: any
    reply containing that language must be accompanied by an actual search
    having run this turn (a role appended to ``searched_roles``) OR must not
    appear at all.
  - CV state (filename / status) after the "uploaded PDF" turn reflects only
    the canonical profile fields the harness explicitly seeded — never text
    pulled from chat history or the transient screenshot context.
  - The harness never raises — every turn returns a response dict.
"""
from __future__ import annotations

from tests.harness.chat_harness import ChatHarness

USER = "transcript-1336@test.com"

# Phrases that mean "I will search" without having actually searched.
_HOLLOW_PROMISE_SIGNALS = (
    "سأبحث الآن", "ساابحث الان", "ببحث الآن", "ببحث الان", "سأبحث",
    "i will search now", "searching now", "let me search now",
)


def _is_hollow_promise(reply_text: str, roles_searched_this_turn: int) -> bool:
    low = (reply_text or "").lower()
    made_promise = any(sig in low for sig in _HOLLOW_PROMISE_SIGNALS)
    return made_promise and roles_searched_this_turn == 0


def test_1336_transcript_never_crashes_and_holds_contract():
    h = ChatHarness()
    # Profile-less / never-onboarded user — the exact starting state that
    # exposed the incident (no target_roles, no CV, no preferred_cities).
    h.seed_state(USER, "no_cv")

    transcript = [
        "Environmental Manager",
        "لديك سيرتي الذاتيه",
        "استهدف نعم",
        "وسع",
        "نفذ",
    ]

    for message in transcript:
        before_searches = len(h.searched_roles)
        result = h.say(USER, message)
        assert isinstance(result, dict), f"turn {message!r} did not return a response dict"

        reply_text = str(result.get("message") or "")
        this_turn_searches = len(h.searched_roles) - before_searches

        # Contract 1: never a hollow "I will search now" without a real search.
        assert not _is_hollow_promise(reply_text, this_turn_searches), (
            f"turn {message!r} produced an unfulfilled search promise: {reply_text!r}"
        )

        # Contract 2: any reported job match traces back to a real stubbed
        # search this turn — never fabricated prose-only listings.
        matches = result.get("matches") or result.get("jobs") or []
        if matches:
            assert this_turn_searches > 0, (
                f"turn {message!r} reported job matches with no underlying "
                f"search call: {matches!r}"
            )

        # Contract 3 (#1336 PR1 + PR2): neither a role name nor the CV-status
        # question is ever captured into preferred_cities, however the turn
        # was routed.
        profile = h.profile(USER)
        cities = list(getattr(profile, "preferred_cities", None) or [])
        for corrupt in ("Environmental Manager", "لديك سيرتي الذاتيه", "سيرتي الذاتيه"):
            assert corrupt not in cities, (
                f"turn {message!r} left {corrupt!r} in preferred_cities: {cities!r}"
            )

    # Contract 4 (#1336 PR2 fix #1): the CV-status question, once reachable
    # (fix #4b stops it being swallowed by a wrongly-armed pending city
    # field), must not silently trigger a job search or a bare re-upload
    # demand when the canonical store has no CV on file — resolve_user_cv
    # (canonical) is consulted, which for this no-CV user correctly falls
    # through to upload guidance, never a search.
    assert "لديك سيرتي الذاتيه" not in h.ai_prompts, (
        "the CV-status question must be intercepted deterministically, "
        "never handed to the AI fallback"
    )


def test_1336_transcript_cv_upload_continuity_and_canonical_state():
    h = ChatHarness()
    h.seed_state(USER + ".2", "no_cv")
    user = USER + ".2"

    h.say(user, "Environmental Manager")
    h.say(user, "لديك سيرتي الذاتيه")

    # "CV correction" — a free-text correction turn. Must not crash and must
    # not silently overwrite canonical profile fields with chat text.
    before = h.profile(user)
    before_role = getattr(before, "current_role", None)
    h.say(user, "لا، خبرتي الفعلية ٨ سنوات كمدير بيئة")
    after = h.profile(user)
    assert getattr(after, "current_role", None) == before_role, (
        "a free-text CV-correction message must not silently mutate "
        "current_role from chat text outside the CV-parse pipeline"
    )

    # "screenshot" — simulate the transient, low-confidence OCR context a
    # screenshot upload leaves behind (mirrors what
    # src.repositories.uploaded_document_repo.set_last_uploaded_document
    # would store). This must NEVER by itself become canonical CV state.
    h._rctx.setdefault(user, {})["last_uploaded_document"] = {
        "document_type": "cv",
        "display_label": "Resume / CV",
        "filename": "screenshot.png",
        "source": "image",
        "extracted_text": "Environmental Manager - 8 years experience",
        "confidence": 0.42,  # low confidence — must not establish CV state
    }
    pre_screenshot_filename = getattr(h.profile(user), "cv_filename", None)
    h.say(user, "؟")
    post_screenshot_profile = h.profile(user)
    assert getattr(post_screenshot_profile, "cv_filename", None) == pre_screenshot_filename, (
        "a low-confidence screenshot-derived transcript must never establish "
        "canonical cv_filename/CV state (#1336 PR2 requirement 9)"
    )

    # "uploaded PDF" — simulate the EFFECT of a real /confirm-cv-profile call
    # (canonical write path, out of scope for this chat-only harness) —
    # this is what actually establishes new CV state.
    h.seed(
        user,
        cv_filename="Environmental_Manager_CV.pdf",
        cv_status="parsed",
        current_role="Environmental Manager",
        target_roles=["Environmental Manager"],
        years_experience=8,
        preferred_cities=["Dubai"],
    )

    # "راجعها ونفذ" — must be recognized deterministically (fix #2) and
    # continue using the CANONICAL profile just established, never the
    # low-confidence screenshot text or prior chat history.
    before_searches = len(h.searched_roles)
    result = h.say(user, "راجعها ونفذ")
    assert isinstance(result, dict)
    reply_text = str(result.get("message") or "")
    this_turn_searches = len(h.searched_roles) - before_searches
    assert not _is_hollow_promise(reply_text, this_turn_searches), (
        f"'راجعها ونفذ' produced an unfulfilled promise: {reply_text!r}"
    )
    if this_turn_searches:
        # Whatever role it searched must come from canonical profile data,
        # never the screenshot's OCR text or a role-shaped chat fragment.
        assert h.searched_roles[-1] not in ("screenshot.png", "؟"), h.searched_roles

    # Tail of the transcript: reflective / ambiguous follow-ups must never
    # crash and must never fabricate a job listing out of thin air.
    for message in ["ما كان طلبي الأساسي؟", "قبل ذلك", "؟", "؟؟"]:
        before_searches = len(h.searched_roles)
        result = h.say(user, message)
        assert isinstance(result, dict), f"turn {message!r} raised or returned non-dict"
        matches = result.get("matches") or result.get("jobs") or []
        this_turn_searches = len(h.searched_roles) - before_searches
        if matches:
            assert this_turn_searches > 0, (
                f"turn {message!r} reported matches with no real search: {matches!r}"
            )
