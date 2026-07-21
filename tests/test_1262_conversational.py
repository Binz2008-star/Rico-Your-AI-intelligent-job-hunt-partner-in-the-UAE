"""
tests/test_1262_conversational.py

Issue #1262 phase 3 — suggestion cards retired; save-search becomes a real
conversational flow.

Three layers are pinned here:

1. Classification: "save this search( for X)" / «احفظ هذا البحث» must route to
   the deterministic ``save_search_create`` intent. REGRESSION PIN: the generic
   save_job regex used to swallow these phrases (including the retired card's
   own payload) and try to save a JOB instead of the search.
2. The spoken offer: results messages carry the opt-in sentence in the user's
   language, and the exact phrase Rico suggests must parse back into
   ``save_search_create`` (transcript parity — what Rico says must work).
3. Dispatch: the ``save_search_create`` handler in _handle_active_user_inner —
   sign-in guard for public identities, named-role extraction, recent-search
   context fallback, honest no-context / persist-failure replies.

Pure unit tests — no HTTP, no database, no external services.
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("JWT_SECRET", "x" * 32)

from src.agent.intelligence.intent_classifier import (  # noqa: E402
    _map_intent_to_legacy,
    classify_intent,
)


def _legacy(text: str) -> str:
    return _map_intent_to_legacy(classify_intent(text).intent)


# ---------------------------------------------------------------------------
# 1. Classification — save_search_create beats the save_job regex
# ---------------------------------------------------------------------------

class TestSaveSearchClassification:

    def test_save_this_search_for_role_is_not_save_job(self):
        """THE fix pin: this exact phrase (the retired card's payload shape)
        previously classified as save_job and tried to save a job."""
        assert _legacy("save this search for Senior HSE Manager") == "save_search_create"

    def test_bare_save_this_search(self):
        assert _legacy("save this search") == "save_search_create"

    def test_save_search_short_form(self):
        assert _legacy("Save search") == "save_search_create"

    def test_save_my_search(self):
        assert _legacy("save my search") == "save_search_create"

    def test_arabic_save_this_search(self):
        assert _legacy("احفظ هذا البحث") == "save_search_create"

    def test_arabic_save_search_short_form(self):
        assert _legacy("احفظ البحث") == "save_search_create"

    def test_save_this_job_still_routes_to_save_job(self):
        """Saving a JOB is untouched — only the search phrasing was rescued."""
        assert _legacy("save this job") == "save_job"

    def test_save_it_still_routes_to_save_job(self):
        assert _legacy("save it") == "save_job"

    def test_daily_phrase_still_routes_to_scheduled_search(self):
        """Section 1c (scheduled) keeps priority over 1d (save)."""
        assert _legacy("search these jobs daily") == "scheduled_search_create"


# ---------------------------------------------------------------------------
# 2. The spoken offer in _build_role_search_message
# ---------------------------------------------------------------------------

class TestSaveSearchOfferSentence:
    """The retired Save-search card, spoken (adjacent-roles idiom): present
    only for signed-in users with results, and the suggested phrase must
    round-trip through the deterministic intent."""

    _EN_PHRASE = "save this search"
    _AR_PHRASE = "احفظ هذا البحث"

    def _build(self, *, offer: bool, arabic: bool = False, matches=None):
        from src.rico_chat_api import RicoChatAPI

        if matches is None:
            matches = [{"title": "A", "company": "B", "link": "https://j.example/1"}]
        return RicoChatAPI._build_role_search_message(
            None, "HSE Manager", "", "", matches, None,
            arabic=arabic, offer_save_search=offer,
        )

    def test_offer_appends_english_sentence(self):
        assert f'"{self._EN_PHRASE}"' in self._build(offer=True)

    def test_offer_appends_arabic_sentence(self):
        assert f"«{self._AR_PHRASE}»" in self._build(offer=True, arabic=True)

    def test_no_offer_message_unchanged(self):
        assert self._EN_PHRASE not in self._build(offer=False)
        assert self._AR_PHRASE not in self._build(offer=False, arabic=True)

    def test_no_matches_never_offers(self):
        assert self._EN_PHRASE not in self._build(offer=True, matches=[])

    def test_suggested_phrases_parse_as_save_search_create(self):
        """Cross-pin: what Rico tells the user to say MUST reach the
        save-search flow — never the save_job regex."""
        assert _legacy(self._EN_PHRASE) == "save_search_create"
        assert _legacy(self._AR_PHRASE) == "save_search_create"


# ---------------------------------------------------------------------------
# 3. Dispatch — the save_search_create handler
# ---------------------------------------------------------------------------

class TestSaveSearchDispatch:

    def _call_inner(self, message: str, *, user_id: str = "user@test.com",
                    recent_context: dict | None = None):
        """Run _handle_active_user_inner with the standard routing-test mocks
        (same idiom as tests/test_acknowledgement_intent.py)."""
        from src.rico_chat_api import RicoChatAPI

        api = RicoChatAPI.__new__(RicoChatAPI)
        api.memory = MagicMock()

        mock_profile = MagicMock()
        mock_profile.has_cv = True
        mock_profile.name = "Test User"

        with (
            patch.object(api, "_resolve_profile", return_value=mock_profile),
            patch.object(api, "_get_recent_messages", return_value=[]),
            patch.object(api, "_get_recent_context", return_value=recent_context or {}),
            patch.object(api, "_append_chat"),
            patch.object(api, "_finalize", side_effect=lambda r, *a, **kw: r),
            patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
        ):
            return api._handle_active_user_inner(user_id, message)

    def test_public_identity_gets_signin_prompt_and_never_persists(self):
        with patch("src.repositories.profile_repo.save_search") as save:
            result = self._call_inner("save this search", user_id="public_abc123")
        assert result.get("type") == "save_search"
        assert result.get("action") == "signin_required"
        save.assert_not_called()

    def test_named_role_is_saved_verbatim(self):
        with patch("src.repositories.profile_repo.save_search", return_value="id-1") as save:
            result = self._call_inner("save this search for Senior HSE Manager")
        save.assert_called_once_with(
            "user@test.com", "Senior HSE Manager", {"source": "chat"}
        )
        assert result.get("action") == "created"
        assert "[your saved searches](/saved-searches)" in result.get("message", "")

    def test_bare_phrase_falls_back_to_recent_search_context(self):
        ctx = {"recent_search_role": "HSE Manager", "recent_search_location": "Dubai"}
        with patch("src.repositories.profile_repo.save_search", return_value="id-2") as save:
            result = self._call_inner("save this search", recent_context=ctx)
        save.assert_called_once_with(
            "user@test.com", "HSE Manager in Dubai", {"source": "chat"}
        )
        assert result.get("action") == "created"

    def test_no_recent_search_gets_honest_reply_without_persisting(self):
        with patch("src.repositories.profile_repo.save_search") as save:
            result = self._call_inner("save this search", recent_context={})
        assert result.get("action") == "no_recent_search"
        save.assert_not_called()

    def test_persist_failure_never_claims_success(self):
        with patch("src.repositories.profile_repo.save_search", return_value=None):
            result = self._call_inner("save this search for HSE Manager")
        assert result.get("action") == "failed"
        msg = result.get("message", "")
        assert "Saved!" not in msg and "saved searches" not in msg

    def test_arabic_phrase_gets_arabic_reply(self):
        ctx = {"recent_search_role": "مدير سلامة"}
        with patch("src.repositories.profile_repo.save_search", return_value="id-3"):
            result = self._call_inner("احفظ هذا البحث", recent_context=ctx)
        assert result.get("action") == "created"
        assert "[بحوثك المحفوظة](/saved-searches)" in result.get("message", "")


# ---------------------------------------------------------------------------
# 4. Phase 4 — strict spoken confirm for the destructive delete
# ---------------------------------------------------------------------------

class TestStrictDeleteConfirmPhrases:
    """The Yes/No buttons are retired; execution is gated by
    _is_delete_confirmation — literal phrases only, carrying the delete verb.
    The full pending-flow behavior is pinned in test_delete_saved_jobs_chat.py;
    here we pin the gate itself and its transcript parity with the prompts."""

    def _gate(self, text: str) -> bool:
        from src.rico_chat_api import RicoChatAPI
        return RicoChatAPI._is_delete_confirmation(text)

    def test_instructed_phrases_pass(self):
        assert self._gate("yes, delete")
        assert self._gate("Yes delete")
        assert self._gate("نعم احذف")
        assert self._gate("نعم أحذف")

    def test_legacy_card_payload_passes(self):
        assert self._gate("yes delete all my saved jobs")

    def test_loose_affirmatives_fail(self):
        for phrase in ("yes", "ok", "okay", "sure", "go ahead", "do it",
                       "please", "نعم", "يلا", "اه", "طبعا", "اكيد"):
            assert not self._gate(phrase), (
                f"{phrase!r} must NOT confirm an irreversible delete"
            )

    def test_sentences_containing_the_phrase_fail(self):
        # Exact-set membership, not substring: no smart interpretation.
        assert not self._gate("yes delete my account")
        assert not self._gate("I think yes, delete maybe?")

    def test_prompts_instruct_exactly_what_the_gate_accepts(self):
        """Transcript parity: the ask prompt (EN and AR) must contain a phrase
        that passes the gate verbatim."""
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI

        api = RicoChatAPI.__new__(RicoChatAPI)
        api.memory = MagicMock()
        api._append_chat = MagicMock()

        api._is_arabic_text = MagicMock(return_value=False)
        en = api._intercept_unsupported_delete_mutation("u1", "delete all my saved jobs")
        assert en["type"] == "delete_saved_jobs_confirm"
        assert "yes, delete" in en["message"] and self._gate("yes, delete")

        api._is_arabic_text = MagicMock(return_value=True)
        ar = api._intercept_unsupported_delete_mutation("u1", "احذف جميع الوظائف المحفوظة")
        assert ar["type"] == "delete_saved_jobs_confirm"
        assert "نعم احذف" in ar["message"] and self._gate("نعم احذف")


# ---------------------------------------------------------------------------
# 5. Phase 5 — Save/Skip buttons retired; ordinal skip + spoken how-to
# ---------------------------------------------------------------------------

class TestOrdinalSkipRegex:
    """Position-based skip ("skip the first one") previously fell into the
    AI fallback — now it has the same deterministic route as ordinal save."""

    def _en(self, text: str):
        from src.rico_chat_api import _SKIP_ORDINAL_RE
        return _SKIP_ORDINAL_RE.match(text)

    def _ar(self, text: str):
        from src.rico_chat_api import _SKIP_ORDINAL_AR_RE
        return _SKIP_ORDINAL_AR_RE.match(text)

    def test_english_variants_match(self):
        for text in ("skip the first one", "skip the second job", "Skip job 2",
                     "skip 3", "skip the 2nd", "please skip the last one"):
            assert self._en(text), f"{text!r} must match the ordinal-skip route"

    def test_arabic_variants_match(self):
        for text in ("تجاهل الوظيفة الأولى", "تجاهل الأولى", "تخطى الثانية",
                     "تجاهل ثاني وظيفة", "تجاهل الوظيفة الأخيرة"):
            assert self._ar(text), f"{text!r} must match the ordinal-skip route"

    def test_non_ordinal_skip_phrases_do_not_match(self):
        # Onboarding "skip", question skip, search-filter phrasing, and the
        # named title-at-company form all keep their existing routes.
        for text in ("skip", "skip this question", "skip coding jobs",
                     "Skip HSE Manager at ACME Gulf"):
            assert not self._en(text), f"{text!r} must NOT match ordinal skip"

    def test_named_skip_still_routes_to_card_action(self):
        from src.rico_chat_api import _SKIP_CARD_ACTION_RE
        assert _SKIP_CARD_ACTION_RE.match("Skip HSE Manager at ACME Gulf")


class TestOrdinalSkipDispatch:
    """End-to-end: the ordinal resolves against the recent results list and the
    suppression goes through agent_runtime.handle_action(action='skip')."""

    def _call(self, message: str, *, matches, ok: bool = True):
        from src.rico_chat_api import RicoChatAPI

        api = RicoChatAPI.__new__(RicoChatAPI)
        api.memory = MagicMock()
        mock_profile = MagicMock()
        mock_profile.has_cv = True
        rt_result = MagicMock()
        rt_result.ok = ok
        rt_result.error = None if ok else "db down"

        with (
            patch.object(api, "_resolve_profile", return_value=mock_profile),
            patch.object(api, "_get_recent_messages", return_value=[]),
            patch.object(api, "_get_recent_context", return_value={}),
            patch.object(api, "_append_chat"),
            patch.object(api, "_finalize", side_effect=lambda r, *a, **kw: r),
            patch.object(api, "_recent_search_matches", return_value=matches),
            patch.object(api, "_resolve_card_job", return_value=None),
            patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
            patch("src.rico_chat_api.agent_runtime") as rt,
        ):
            rt.handle_action.return_value = rt_result
            result = api._handle_active_user_inner("user@test.com", message)
        return result, rt

    _TWO = [{"title": "A", "company": "X"}, {"title": "B", "company": "Y"}]

    def test_skip_second_targets_the_second_match(self):
        result, rt = self._call("skip the second one", matches=self._TWO)
        assert result["type"] == "skip_job"
        kwargs = rt.handle_action.call_args.kwargs
        assert kwargs["action"] == "skip"
        assert kwargs["job"]["title"] == "B" and kwargs["job"]["company"] == "Y"

    def test_arabic_last_targets_the_last_match(self):
        result, rt = self._call("تجاهل الوظيفة الأخيرة", matches=self._TWO)
        assert result["type"] == "skip_job"
        assert rt.handle_action.call_args.kwargs["job"]["title"] == "B"

    def test_no_recent_list_gets_honest_reply_without_action(self):
        result, rt = self._call("skip the first one", matches=[])
        assert result["type"] == "clarification"
        rt.handle_action.assert_not_called()

    def test_out_of_range_asks_which_without_action(self):
        result, rt = self._call("skip job 5", matches=[{"title": "A", "company": "X"}])
        assert result["type"] == "clarification"
        rt.handle_action.assert_not_called()

    def test_runtime_failure_never_claims_success(self):
        result, _ = self._call("skip the first one", matches=self._TWO, ok=False)
        assert result["type"] == "skip_job"
        assert "couldn't skip" in result["message"]


class TestSpokenActionHowTo:
    """The retired Save/Skip buttons, spoken: the results message says how to
    act, and each suggested phrase routes deterministically (cross-pins)."""

    _EN_SAVE = "save the first job"
    _EN_SKIP = "skip the second one"
    _AR_SAVE = "احفظ أول وظيفة"
    _AR_SKIP = "تجاهل الوظيفة الثانية"

    def _build(self, *, arabic: bool = False, matches=None):
        from src.rico_chat_api import RicoChatAPI

        if matches is None:
            matches = [{"title": "A", "company": "B", "link": "https://j.example/1"}]
        return RicoChatAPI._build_role_search_message(
            None, "HSE Manager", "", "", matches, None, arabic=arabic,
        )

    def test_howto_present_with_matches(self):
        msg = self._build()
        assert f'"{self._EN_SAVE}"' in msg
        assert f'"{self._EN_SKIP}"' in msg

    def test_arabic_howto_present(self):
        msg = self._build(arabic=True)
        assert f"«{self._AR_SAVE}»" in msg
        assert f"«{self._AR_SKIP}»" in msg

    def test_absent_without_matches(self):
        assert self._EN_SAVE not in self._build(matches=[])

    def test_suggested_phrases_route_deterministically(self):
        from src.rico_chat_api import _SKIP_ORDINAL_AR_RE, _SKIP_ORDINAL_RE

        assert _legacy(self._EN_SAVE) == "save_job"
        assert _legacy(self._AR_SAVE) == "save_job"
        assert _SKIP_ORDINAL_RE.match(self._EN_SKIP)
        assert _SKIP_ORDINAL_AR_RE.match(self._AR_SKIP)


# ---------------------------------------------------------------------------
# 6. Steps-to-apply (owner directive 2026-07-21 «كي أضغط وأقدم»)
# ---------------------------------------------------------------------------

class TestSearchTopTrackWithAlternatives:
    """A generic "find me jobs" with a multi-track profile searches the most
    relevant track immediately and SPEAKS the alternatives — never blocks on
    a which-track menu. Track choice is per-user data at request time."""

    _CANDIDATES = ["Environmental Manager", "Compliance Manager", "ESG Manager"]

    def _api(self, recent_context=None):
        from src.rico_chat_api import RicoChatAPI

        api = RicoChatAPI.__new__(RicoChatAPI)
        api.memory = MagicMock()
        api._append_chat = MagicMock()
        api._get_recent_context = MagicMock(return_value=recent_context or {})
        api._target_role_search_response = MagicMock(
            return_value={"message": "RESULTS", "matches": [{"title": "x"}]}
        )
        return api

    def test_searches_first_track_and_speaks_alternatives(self):
        api = self._api()
        resp = api._search_top_track_with_alternatives(
            "u@test.com", list(self._CANDIDATES), SimpleNamespace(), "find me jobs"
        )
        chosen = api._target_role_search_response.call_args.args[1]
        assert chosen == "Environmental Manager"
        assert "Compliance Manager" in resp["message"]
        assert "ESG Manager" in resp["message"]
        assert resp["track_alternatives"] == ["Compliance Manager", "ESG Manager"]

    def test_recent_track_preferred_case_insensitive(self):
        api = self._api(recent_context={"recent_search_role": "esg manager"})
        api._search_top_track_with_alternatives(
            "u@test.com", list(self._CANDIDATES), SimpleNamespace(), "find me jobs"
        )
        assert api._target_role_search_response.call_args.args[1] == "ESG Manager"

    def test_arabic_ask_gets_arabic_note(self):
        api = self._api()
        resp = api._search_top_track_with_alternatives(
            "u@test.com", list(self._CANDIDATES), SimpleNamespace(), "ابحثلي عن وظائف"
        )
        assert "بدأت بمسارك" in resp["message"]

    def test_single_candidate_adds_no_note(self):
        api = self._api()
        resp = api._search_top_track_with_alternatives(
            "u@test.com", ["Environmental Manager"], SimpleNamespace(), "find me jobs"
        )
        assert resp["message"] == "RESULTS"
        assert "track_alternatives" not in resp


class TestAdjacentRoleAutoHop:
    """When live results exist but the title floor drops them ALL, the search
    takes exactly ONE hop to the closest adjacent role and returns its real
    matches with an honest relabel — never a dead-end zero when the taxonomy
    knows a near neighbour."""

    def _profile(self):
        return SimpleNamespace(
            user_id="u@test.com", has_cv=True, name="Test",
            target_roles=["ESG Manager"], skills=["iso 14001"],
            certifications=[], years_experience=8, industries=[],
            preferred_cities=["Dubai"], current_role="Manager",
            nationality="", citizenship="", deal_breakers=[],
        )

    def _api(self, monkeypatch, fetch_side_effects):
        from src.jsearch_client import FetchResult
        from src.rico_chat_api import RicoChatAPI

        api = RicoChatAPI.__new__(RicoChatAPI)
        api.memory = MagicMock()
        api._persist = False
        api._append_chat = MagicMock()
        api._get_recent_messages = MagicMock(return_value=[])
        api._get_recent_context = MagicMock(return_value={})
        api._store_recent_context = MagicMock()
        api._current_operation_id = None

        monkeypatch.setattr(
            api, "_search_jsearch_meta",
            MagicMock(side_effect=[FetchResult(items=it) for it in fetch_side_effects]),
        )
        monkeypatch.setattr(api, "_enrich_with_role_intelligence", lambda *a, **k: None)
        monkeypatch.setattr(
            api, "_begin_job_search_operation",
            lambda _u, _r: {"operation_id": f"op-{_r}", "attempt": 1},
        )
        monkeypatch.setattr("src.rico_chat_api.mark_completed", lambda *a, **k: None)
        monkeypatch.setattr("src.rico_chat_api.mark_failed", lambda *a, **k: None)
        monkeypatch.setattr(api, "_closest_adjacent_role", lambda _u, _r, _p: "HSE Manager")
        return api

    # Passes the coarse integrity gate (weak single "environment") but fails
    # the strict 3-layer title floor for "ESG Manager" — the exact production
    # shape that used to end in an honest-but-dead-end zero.
    _OFF_TITLE = [{"title": "Environment Officer", "company": "ACME", "location": "Dubai, AE",
                   "link": "https://j.example/1", "job_apply_link": "https://j.example/1"}]
    _HSE = [{"title": "HSE Manager", "company": "Gulf Co", "location": "Dubai, AE",
             "link": "https://j.example/2", "job_apply_link": "https://j.example/2"}]

    def test_floored_zero_hops_once_and_relabels_honestly(self, monkeypatch):
        api = self._api(monkeypatch, [self._OFF_TITLE, self._HSE])
        resp = api._target_role_search_response("u@test.com", "ESG Manager", self._profile())
        assert resp.get("adjacent_hop_from") == "ESG Manager"
        assert resp.get("matches"), "hop results must be presented"
        assert "HSE Manager" in resp.get("message", "")
        assert "closest role" in resp.get("message", "") or "الأقرب" in resp.get("message", "")
        # Exactly two searches: the floored original + ONE hop.
        assert api._search_jsearch_meta.call_count == 2

    def test_hop_never_recurses(self, monkeypatch):
        # Both searches floor out — the guard stops after one hop.
        api = self._api(monkeypatch, [self._OFF_TITLE, self._OFF_TITLE])
        resp = api._target_role_search_response("u@test.com", "ESG Manager", self._profile())
        assert api._search_jsearch_meta.call_count == 2
        assert not resp.get("matches")
        assert "adjacent_hop_from" not in resp
