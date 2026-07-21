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
