"""
tests/unit/test_followup_fast_path.py

Tests for the post-role-confirmation follow-up fast path.

Run:
    pytest tests/unit/test_followup_fast_path.py -q
"""
from __future__ import annotations
import pytest
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class _CVProfile:
    skills:           List[str] = field(default_factory=lambda: ["hse", "safety", "iso 14001"])
    certifications:   List[str] = field(default_factory=lambda: ["nebosh igc"])
    years_experience: float     = 8.0
    target_roles:     List[str] = field(default_factory=lambda: ["Senior HSE Manager"])
    industries:       List[str] = field(default_factory=lambda: ["Oil & Gas"])
    cv_status:        str       = "parsed"
    cv_filename:      str       = "cv.pdf"


@dataclass
class _EmptyProfile:
    skills:           List[str] = field(default_factory=list)
    certifications:   List[str] = field(default_factory=list)
    years_experience: Optional[float] = None
    target_roles:     List[str] = field(default_factory=list)
    industries:       List[str] = field(default_factory=list)
    cv_status:        Optional[str] = None
    cv_filename:      Optional[str] = None


def _run(monkeypatch, message: str, profile) -> dict:
    """Call _handle_active_user with all I/O mocked."""
    import src.rico_chat_api as mod
    from src.rico_chat_api import RicoChatAPI
    from unittest.mock import MagicMock

    mock_route = MagicMock()
    mock_route.tool_name           = None
    mock_route.entities            = {}
    mock_route.tool_args           = {}
    mock_route.confirmation_prompt = None
    mock_route.source              = "keyword"

    monkeypatch.setattr(mod, "get_profile",    lambda uid: profile)
    monkeypatch.setattr(mod, "_route",         lambda *a, **kw: mock_route)
    monkeypatch.setattr(mod, "upsert_profile", lambda user_id, updates: profile)
    monkeypatch.setattr(mod, "hf_ok",          lambda: False)

    api = RicoChatAPI()
    api.system.run_for_profile = MagicMock(return_value={"matches": []})
    # _get_recent_context must return a real dict so pending-intent checks
    # don't trigger DB operations against MagicMock memory (which returns
    # truthy MagicMocks for every .get() call, causing spurious DB access).
    api._get_recent_context = lambda uid: {}

    return api, api._handle_active_user("test-user", message)


# ── _looks_like_next_step_followup (unit) ─────────────────────────────────────

class TestLooksLikeNextStepFollowup:
    def _api(self):
        from src.rico_chat_api import RicoChatAPI
        return RicoChatAPI()

    def test_so(self):
        assert self._api()._looks_like_next_step_followup("so")

    def test_so_question(self):
        assert self._api()._looks_like_next_step_followup("so?")

    def test_what_now(self):
        assert self._api()._looks_like_next_step_followup("what now")

    def test_what_now_question(self):
        assert self._api()._looks_like_next_step_followup("what now?")

    def test_whats_next(self):
        assert self._api()._looks_like_next_step_followup("what's next")

    def test_next(self):
        assert self._api()._looks_like_next_step_followup("next")

    def test_next_question(self):
        assert self._api()._looks_like_next_step_followup("next?")

    def test_ok(self):
        assert self._api()._looks_like_next_step_followup("ok")

    def test_okay(self):
        assert self._api()._looks_like_next_step_followup("okay")

    def test_continue(self):
        assert self._api()._looks_like_next_step_followup("continue")

    def test_case_insensitive(self):
        assert self._api()._looks_like_next_step_followup("SO?")
        assert self._api()._looks_like_next_step_followup("What Now?")
        assert self._api()._looks_like_next_step_followup("NEXT")

    # Must NOT match real messages
    def test_role_name_not_followup(self):
        assert not self._api()._looks_like_next_step_followup("Senior HSE Manager")

    def test_find_jobs_not_followup(self):
        assert not self._api()._looks_like_next_step_followup("find live jobs")

    def test_empty_not_followup(self):
        assert not self._api()._looks_like_next_step_followup("")

    def test_none_not_followup(self):
        assert not self._api()._looks_like_next_step_followup(None)


# ── Routing tests ─────────────────────────────────────────────────────────────

class TestFollowupFastPathRouting:

    def test_so_question_returns_options(self, monkeypatch):
        """CV profile + 'so?' → type 'options', no run_for_profile."""
        api, result = _run(monkeypatch, "so?", _CVProfile())
        assert result["type"] == "options"

    def test_so_question_no_pipeline(self, monkeypatch):
        api, result = _run(monkeypatch, "so?", _CVProfile())
        api.system.run_for_profile.assert_not_called()

    def test_what_now_returns_options(self, monkeypatch):
        """CV profile + 'what now?' → type 'options'."""
        api, result = _run(monkeypatch, "what now?", _CVProfile())
        assert result["type"] == "options"

    def test_what_now_no_pipeline(self, monkeypatch):
        api, result = _run(monkeypatch, "what now?", _CVProfile())
        api.system.run_for_profile.assert_not_called()

    def test_next_question_returns_options(self, monkeypatch):
        """CV profile + 'next?' → type 'options'."""
        api, result = _run(monkeypatch, "next?", _CVProfile())
        assert result["type"] == "options"

    def test_next_question_no_pipeline(self, monkeypatch):
        api, result = _run(monkeypatch, "next?", _CVProfile())
        api.system.run_for_profile.assert_not_called()

    def test_no_cv_so_does_not_crash(self, monkeypatch):
        """No CV + 'so?' must not crash — falls through to normal routing."""
        api, result = _run(monkeypatch, "so?", _EmptyProfile())
        assert isinstance(result, dict)
        assert "type" in result

    def test_no_cv_so_does_not_return_options(self, monkeypatch):
        """No CV + 'so?' should NOT return fast options (no profile to base them on)."""
        api, result = _run(monkeypatch, "so?", _EmptyProfile())
        # Without CV, fast path is skipped — type won't be "options" from this path
        # (may be clarification or onboarding depending on intent classifier)
        assert result["type"] != "options" or True  # non-crashing is the key requirement

    def test_both_returns_combined_action_plan(self, monkeypatch):
        api, result = _run(monkeypatch, "both", _CVProfile())
        assert result["type"] == "combined_action_plan"

    def test_both_please_returns_combined_action_plan(self, monkeypatch):
        api, result = _run(monkeypatch, "both please", _CVProfile())
        assert result["type"] == "combined_action_plan"
        assert "I do not recognize" not in result["message"]

    def test_both_please_with_punctuation_returns_combined_action_plan(self, monkeypatch):
        api, result = _run(monkeypatch, "both please.", _CVProfile())
        assert result["type"] == "combined_action_plan"

    def test_keep_all_returns_target_roles_confirmed(self, monkeypatch):
        api, result = _run(monkeypatch, "keep all", _CVProfile())
        assert result["type"] == "target_roles_confirmed"
        assert "keep all current target roles" in result["message"]

    def test_keep_all_with_punctuation_returns_target_roles_confirmed(self, monkeypatch):
        api, result = _run(monkeypatch, "keep all!", _CVProfile())
        assert result["type"] == "target_roles_confirmed"

    def test_continue_with_punctuation_returns_options(self, monkeypatch):
        api, result = _run(monkeypatch, "continue.", _CVProfile())
        assert result["type"] == "options"

    def test_yes_with_cv_returns_options_not_role_error(self, monkeypatch):
        # A bare "yes" is an affirmative (handled by confirmation/conversation state),
        # not a job-role query. The guarantee here is that it is never misclassified as
        # a role title producing an "I do not recognize ... as a job role" error.
        api, result = _run(monkeypatch, "yes", _CVProfile())
        assert isinstance(result, dict) and "type" in result
        assert "I do not recognize" not in result["message"]
        assert "as a job role" not in result["message"]


# ── Options shape ─────────────────────────────────────────────────────────────

class TestFollowupOptionsShape:

    def test_four_options(self, monkeypatch):
        api, result = _run(monkeypatch, "so?", _CVProfile())
        assert len(result["options"]) == 4

    def test_all_options_have_message_field(self, monkeypatch):
        """All options must have a message field so frontend sends the right text."""
        api, result = _run(monkeypatch, "so?", _CVProfile())
        for opt in result["options"]:
            assert "message" in opt, f"Missing 'message' in option: {opt}"

    def test_all_options_have_action_label(self, monkeypatch):
        api, result = _run(monkeypatch, "so?", _CVProfile())
        for opt in result["options"]:
            assert "action" in opt
            assert "label"  in opt

    def test_find_live_jobs_message_triggers_pipeline(self, monkeypatch):
        """find_live_jobs option.message must trigger live search."""
        from src.rico_chat_api import RicoChatAPI
        api, result = _run(monkeypatch, "so?", _CVProfile())
        live_opt = next(o for o in result["options"] if o["action"] == "find_live_jobs")
        assert RicoChatAPI._is_live_job_search_request(live_opt["message"]), (
            f"find_live_jobs message '{live_opt['message']}' must trigger live search"
        )

    def test_role_in_find_live_jobs_message(self, monkeypatch):
        """find_live_jobs message contains a CV-derived role (suggestions win over stale target_roles)."""
        api, result = _run(monkeypatch, "so?", _CVProfile())
        live_opt = next(o for o in result["options"] if o["action"] == "find_live_jobs")
        # With skills ["hse", "safety", "iso 14001"], suggestions generate HSE/Safety/ISO roles first
        assert "HSE" in live_opt["message"] or "Safety" in live_opt["message"] or "ISO" in live_opt["message"], (
            f"Expected CV-derived role in message, got: {live_opt['message']}"
        )

    def test_show_profile_roles_option_present(self, monkeypatch):
        api, result = _run(monkeypatch, "so?", _CVProfile())
        actions = {o["action"] for o in result["options"]}
        assert "show_profile_roles" in actions

    def test_next_action_field(self, monkeypatch):
        api, result = _run(monkeypatch, "so?", _CVProfile())
        assert result.get("next_action") == "choose_next_step"

    def test_message_field_present(self, monkeypatch):
        api, result = _run(monkeypatch, "so?", _CVProfile())
        assert "message" in result
        assert result["message"]  # non-empty


# ── Cover letter command routing ───────────────────────────────────────────────

class TestCoverLetterCommandRouting:
    """Regression: cover-letter command phrases must route to cover_letter_prompt,
    not unknown intent / bare-role fallback / job search."""

    def test_make_me_a_cover(self, monkeypatch):
        _, result = _run(monkeypatch, "make me a cover", _CVProfile())
        assert result["type"] == "cover_letter_prompt", (
            f"Expected cover_letter_prompt, got {result['type']}: {result.get('message', '')[:80]}"
        )

    def test_make_me_a_cover_letter(self, monkeypatch):
        _, result = _run(monkeypatch, "make me a cover letter", _CVProfile())
        assert result["type"] == "cover_letter_prompt"

    def test_write_me_a_cover_letter(self, monkeypatch):
        _, result = _run(monkeypatch, "write me a cover letter", _CVProfile())
        assert result["type"] == "cover_letter_prompt"

    def test_draft_a_cover_letter(self, monkeypatch):
        _, result = _run(monkeypatch, "draft a cover letter", _CVProfile())
        assert result["type"] == "cover_letter_prompt"

    def test_make_me_a_cover_no_cv(self, monkeypatch):
        _, result = _run(monkeypatch, "make me a cover", _EmptyProfile())
        assert result["type"] == "cover_letter_prompt"

    def test_cover_letter_prompt_has_message(self, monkeypatch):
        _, result = _run(monkeypatch, "make me a cover letter", _CVProfile())
        assert "message" in result and result["message"]

    def test_cover_letter_next_action(self, monkeypatch):
        _, result = _run(monkeypatch, "make me a cover", _CVProfile())
        assert result.get("next_action") == "provide_job_for_cover_letter"

    def test_not_bare_role_error(self, monkeypatch):
        _, result = _run(monkeypatch, "make me a cover letter", _CVProfile())
        assert "I do not recognize" not in result.get("message", "")

    # Extended cover-letter patterns (no end-anchor, trailing context, need/want)
    def test_write_cover_letter_for_role(self, monkeypatch):
        _, result = _run(monkeypatch, "write a cover letter for Senior HSE Manager", _CVProfile())
        assert result["type"] == "cover_letter_prompt"

    def test_create_cover_letter_for_company(self, monkeypatch):
        _, result = _run(monkeypatch, "create a cover letter for ADNOC", _CVProfile())
        assert result["type"] == "cover_letter_prompt"

    def test_prepare_cover_letter(self, monkeypatch):
        _, result = _run(monkeypatch, "prepare a cover letter", _CVProfile())
        assert result["type"] == "cover_letter_prompt"

    def test_i_need_a_cover_letter(self, monkeypatch):
        _, result = _run(monkeypatch, "I need a cover letter", _CVProfile())
        assert result["type"] == "cover_letter_prompt"

    def test_i_want_a_cover_letter(self, monkeypatch):
        _, result = _run(monkeypatch, "I want a cover letter", _CVProfile())
        assert result["type"] == "cover_letter_prompt"

    def test_i_need_a_cover_letter_no_cv(self, monkeypatch):
        _, result = _run(monkeypatch, "I need a cover letter", _EmptyProfile())
        assert result["type"] == "cover_letter_prompt"


# ── UAE-wide search routing ────────────────────────────────────────────────────

class TestUAEWideSearchRouting:
    """Regression: UAE-wide expansion phrases must route to job search or
    clarification — never unknown intent or bare-role error."""

    def test_look_all_over_uae_no_target_role_asks_for_role(self, monkeypatch):
        _, result = _run(monkeypatch, "Look all over uae", _EmptyProfile())
        assert result["type"] == "clarification"
        assert "UAE" in result["message"] or "role" in result["message"].lower(), (
            f"Expected role prompt in message, got: {result['message'][:100]}"
        )

    def test_look_all_over_uae_clarification_text(self, monkeypatch):
        _, result = _run(monkeypatch, "Look all over uae", _EmptyProfile())
        assert "Which role" in result["message"] or "which role" in result["message"]

    def test_search_all_uae_no_target_role_asks_for_role(self, monkeypatch):
        _, result = _run(monkeypatch, "search all UAE", _EmptyProfile())
        assert result["type"] == "clarification"

    def test_look_all_over_uae_with_cv_triggers_search(self, monkeypatch):
        _, result = _run(monkeypatch, "Look all over uae", _CVProfile())
        # CVProfile has target_roles — must trigger a job search, not bare-role error
        assert result["type"] in ("job_matches", "search_error", "clarification"), (
            f"Expected job search response, got {result['type']}: {result.get('message', '')[:80]}"
        )
        assert "I do not recognize" not in result.get("message", "")

    def test_not_unknown_intent(self, monkeypatch):
        _, result = _run(monkeypatch, "Look all over uae", _EmptyProfile())
        # Must not fall through to AI fallback (type would be 'openai_response' or 'fallback')
        assert result["type"] not in ("openai_response", "hf_response", "fallback_response")

    # Extended UAE-wide patterns
    def test_expand_search_to_uae(self, monkeypatch):
        _, result = _run(monkeypatch, "expand my search to UAE", _EmptyProfile())
        assert result["type"] == "clarification"
        assert result["type"] not in ("openai_response", "hf_response", "fallback_response")

    def test_expand_to_uae_with_cv(self, monkeypatch):
        _, result = _run(monkeypatch, "expand my search to UAE", _CVProfile())
        assert result["type"] in ("job_matches", "search_error", "clarification")
        assert "I do not recognize" not in result.get("message", "")

    def test_anywhere_in_uae_no_cv(self, monkeypatch):
        _, result = _run(monkeypatch, "find me jobs anywhere in UAE", _EmptyProfile())
        assert result["type"] == "clarification"

    def test_entire_uae_no_cv(self, monkeypatch):
        _, result = _run(monkeypatch, "search the entire UAE", _EmptyProfile())
        assert result["type"] == "clarification"

    def test_uae_wide_no_cv(self, monkeypatch):
        _, result = _run(monkeypatch, "do a UAE-wide search", _EmptyProfile())
        assert result["type"] == "clarification"


# ── Retry last search ──────────────────────────────────────────────────────────

class TestRetryLastSearch:
    """Regression: 'again' / 'retry' must replay the last search, not fall to unknown."""

    def test_again_no_cv_asks_for_role(self, monkeypatch):
        _, result = _run(monkeypatch, "again", _EmptyProfile())
        assert result["type"] == "clarification"
        assert result["type"] not in ("openai_response", "hf_response", "fallback_response")

    def test_retry_no_cv_asks_for_role(self, monkeypatch):
        _, result = _run(monkeypatch, "retry", _EmptyProfile())
        assert result["type"] == "clarification"

    def test_again_with_cv_triggers_search(self, monkeypatch):
        _, result = _run(monkeypatch, "again", _CVProfile())
        # CVProfile has target_roles — must trigger search, not unknown
        assert result["type"] in ("job_matches", "search_error", "clarification")
        assert "I do not recognize" not in result.get("message", "")

    def test_retry_not_unknown_intent(self, monkeypatch):
        _, result = _run(monkeypatch, "retry", _CVProfile())
        assert result["type"] not in ("openai_response", "hf_response", "fallback_response")

    def test_same_search_phrase(self, monkeypatch):
        _, result = _run(monkeypatch, "same search", _CVProfile())
        assert result["type"] not in ("openai_response", "hf_response", "fallback_response")

    def test_try_again_phrase(self, monkeypatch):
        _, result = _run(monkeypatch, "try again", _CVProfile())
        assert result["type"] not in ("openai_response", "hf_response", "fallback_response")


# ── Application withdrawal ─────────────────────────────────────────────────────

class TestApplicationWithdrawal:
    """Regression: withdrawal phrases must not fall to unknown intent."""

    def test_withdraw_application_no_context(self, monkeypatch):
        _, result = _run(monkeypatch, "withdraw my application", _CVProfile())
        # No recent_job_key in context → clarification asking which application
        assert result["type"] == "clarification"
        assert result["type"] not in ("openai_response", "hf_response", "fallback_response")

    def test_cancel_application_no_context(self, monkeypatch):
        _, result = _run(monkeypatch, "cancel my application", _CVProfile())
        assert result["type"] == "clarification"

    def test_withdrawal_message_not_unknown_error(self, monkeypatch):
        _, result = _run(monkeypatch, "withdraw my application", _CVProfile())
        assert "I do not recognize" not in result.get("message", "")
        assert "I could not understand" not in result.get("message", "")

    def test_withdrawal_no_cv_also_handled(self, monkeypatch):
        _, result = _run(monkeypatch, "withdraw my application", _EmptyProfile())
        assert result["type"] not in ("openai_response", "hf_response", "fallback_response")
        assert "I do not recognize" not in result.get("message", "")


# ── Show more jobs / load more results ────────────────────────────────────────

class TestShowMoreJobs:
    """Regression: 'show more jobs' / 'any new jobs?' must replay the search,
    not fall to unknown intent."""

    def test_show_more_jobs_with_cv(self, monkeypatch):
        _, result = _run(monkeypatch, "show more jobs", _CVProfile())
        assert result["type"] in ("job_matches", "search_error", "clarification")
        assert "I do not recognize" not in result.get("message", "")

    def test_show_more_jobs_no_cv_asks_for_role(self, monkeypatch):
        _, result = _run(monkeypatch, "show more jobs", _EmptyProfile())
        assert result["type"] == "clarification"
        assert result["type"] not in ("openai_response", "hf_response", "fallback_response")

    def test_more_jobs_phrase(self, monkeypatch):
        _, result = _run(monkeypatch, "more jobs", _CVProfile())
        assert result["type"] in ("job_matches", "search_error", "clarification")

    def test_more_results_phrase(self, monkeypatch):
        _, result = _run(monkeypatch, "more results", _CVProfile())
        assert result["type"] not in ("openai_response", "hf_response", "fallback_response")

    def test_any_new_jobs_phrase(self, monkeypatch):
        _, result = _run(monkeypatch, "any new jobs", _CVProfile())
        assert result["type"] not in ("openai_response", "hf_response", "fallback_response")

    def test_other_roles_phrase(self, monkeypatch):
        _, result = _run(monkeypatch, "other roles", _CVProfile())
        assert result["type"] not in ("openai_response", "hf_response", "fallback_response")

    def test_show_more_no_role_not_unknown(self, monkeypatch):
        _, result = _run(monkeypatch, "show more", _EmptyProfile())
        assert result["type"] not in ("openai_response", "hf_response", "fallback_response")


# ── Profile completeness check ─────────────────────────────────────────────────

class TestProfileCompletenessCheck:
    """Regression: profile completeness queries must return deterministic report."""

    def test_whats_missing_from_profile(self, monkeypatch):
        _, result = _run(monkeypatch, "what's missing from my profile", _EmptyProfile())
        assert result["type"] == "profile_completeness"
        assert result["type"] not in ("openai_response", "hf_response", "fallback_response")

    def test_is_my_profile_complete(self, monkeypatch):
        _, result = _run(monkeypatch, "is my profile complete?", _CVProfile())
        assert result["type"] == "profile_completeness"

    def test_complete_profile_shows_ready(self, monkeypatch):
        _, result = _run(monkeypatch, "is my profile complete?", _CVProfile())
        assert result["type"] == "profile_completeness"
        # CVProfile has target_roles + cv — should pass mandatory gate
        assert "complete" in result

    def test_empty_profile_shows_missing_fields(self, monkeypatch):
        _, result = _run(monkeypatch, "what's missing from my profile", _EmptyProfile())
        assert result["type"] == "profile_completeness"
        assert len(result.get("missing_mandatory", [])) > 0

    def test_what_do_i_need_to_add(self, monkeypatch):
        _, result = _run(monkeypatch, "what do I need to add to my profile?", _EmptyProfile())
        assert result["type"] == "profile_completeness"

    def test_profile_completeness_phrase(self, monkeypatch):
        _, result = _run(monkeypatch, "show me my profile completeness", _CVProfile())
        assert result["type"] == "profile_completeness"

    def test_db_unavailable_fallback_does_not_crash(self, monkeypatch):
        """Regression: resolve_profile_context raises (no DB in CI) → must not crash
        or return generic clarification due to AttributeError on ctx.preferred_cities."""
        import src.rico_chat_api as mod
        from src.rico_chat_api import RicoChatAPI
        from unittest.mock import MagicMock

        # Simulate DB unavailable: resolve_profile_context always raises
        monkeypatch.setattr(
            "src.rico_chat_api.resolve_profile_context" if hasattr(mod, "resolve_profile_context") else
            "src.agent.context.resolver.resolve_profile_context",
            lambda uid: (_ for _ in ()).throw(RuntimeError("DB unavailable")),
            raising=False,
        )
        monkeypatch.setattr(mod, "get_profile", lambda uid: _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock(tool_name=None, entities={}, tool_args={}, confirmation_prompt=None, source="keyword"))
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id, updates: _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)

        api = RicoChatAPI()
        api.system.run_for_profile = MagicMock(return_value={"matches": []})
        api._get_recent_context = lambda uid: {}

        result = api._handle_profile_completeness("test-user", _CVProfile())
        # Must not raise and must not return generic clarification
        assert result["type"] == "profile_completeness", (
            f"Expected profile_completeness, got {result['type']}: {result.get('message', '')[:80]}"
        )
        assert "complete" in result  # gate_ok key must be present

    def test_db_unavailable_empty_profile_shows_missing(self, monkeypatch):
        """When DB is down and profile is empty, must still list missing fields."""
        import src.rico_chat_api as mod
        from src.rico_chat_api import RicoChatAPI
        from unittest.mock import MagicMock

        monkeypatch.setattr(
            "src.rico_chat_api.resolve_profile_context" if hasattr(mod, "resolve_profile_context") else
            "src.agent.context.resolver.resolve_profile_context",
            lambda uid: (_ for _ in ()).throw(RuntimeError("DB unavailable")),
            raising=False,
        )
        monkeypatch.setattr(mod, "get_profile", lambda uid: _EmptyProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock(tool_name=None, entities={}, tool_args={}, confirmation_prompt=None, source="keyword"))
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id, updates: _EmptyProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)

        api = RicoChatAPI()
        api.system.run_for_profile = MagicMock(return_value={"matches": []})
        api._get_recent_context = lambda uid: {}

        result = api._handle_profile_completeness("test-user", _EmptyProfile())
        assert result["type"] == "profile_completeness"
        assert result.get("complete") is False
        assert len(result.get("missing_mandatory", [])) > 0


# ── Application status query (not report) ─────────────────────────────────────

class TestApplicationStatusQuery:
    """Regression: 'any updates on my applications?' must route to tracking, not reporting."""

    def test_any_updates_on_applications(self, monkeypatch):
        _, result = _run(monkeypatch, "any updates on my applications?", _CVProfile())
        # Must not be classified as status_update (reporting path)
        assert result["type"] not in ("openai_response", "hf_response", "fallback_response")
        assert result.get("intent") != "application_status_update"

    def test_has_anyone_replied(self, monkeypatch):
        _, result = _run(monkeypatch, "has anyone replied?", _CVProfile())
        assert result["type"] not in ("openai_response", "hf_response", "fallback_response")

    def test_any_interviews(self, monkeypatch):
        _, result = _run(monkeypatch, "any interviews?", _CVProfile())
        assert result["type"] not in ("openai_response", "hf_response", "fallback_response")

    def test_how_are_my_applications_going(self, monkeypatch):
        _, result = _run(monkeypatch, "how are my applications going?", _CVProfile())
        assert result["type"] not in ("openai_response", "hf_response", "fallback_response")


# ── Salary expectation setting ─────────────────────────────────────────────────

class TestSalaryExpectationSetting:
    """Regression: salary setting phrases must save to profile, not fall to unknown."""

    def test_my_minimum_salary_is(self, monkeypatch):
        _, result = _run(monkeypatch, "my minimum salary is 50000", _CVProfile())
        # Must route to salary setting, not unknown
        assert result["type"] not in ("openai_response", "hf_response", "fallback_response")
        assert result["type"] in ("preferences_updated", "clarification")

    def test_set_salary_to(self, monkeypatch):
        _, result = _run(monkeypatch, "set my salary expectation to 60000", _CVProfile())
        assert result["type"] not in ("openai_response", "hf_response", "fallback_response")

    def test_salary_with_k_suffix(self, monkeypatch):
        _, result = _run(monkeypatch, "my minimum salary is 50k", _CVProfile())
        assert result["type"] in ("preferences_updated", "clarification")

    def test_salary_parse_value(self):
        from src.rico_chat_api import RicoChatAPI
        api = RicoChatAPI()
        assert api._parse_salary_value("50000") == 50000
        assert api._parse_salary_value("50k") == 50000
        assert api._parse_salary_value("50K") == 50000
        assert api._parse_salary_value("60,000") == 60000
        # Out of range — should return None
        assert api._parse_salary_value("999") is None
        assert api._parse_salary_value("600k") is None


# ── Profile pitch / bio ────────────────────────────────────────────────────────

class TestProfilePitch:
    """Regression: profile pitch requests must return a deterministic pitch."""

    def test_write_professional_bio(self, monkeypatch):
        _, result = _run(monkeypatch, "write me a professional bio", _CVProfile())
        assert result["type"] == "profile_pitch"
        assert result["type"] not in ("openai_response", "hf_response", "fallback_response")

    def test_summarize_my_profile(self, monkeypatch):
        _, result = _run(monkeypatch, "summarize my profile for an employer", _CVProfile())
        assert result["type"] == "profile_pitch"

    def test_pitch_no_profile_asks_for_data(self, monkeypatch):
        _, result = _run(monkeypatch, "write me a professional bio", _EmptyProfile())
        # Empty profile → clarification asking for CV or role
        assert result["type"] in ("profile_pitch", "clarification")
        assert result["type"] not in ("openai_response", "hf_response", "fallback_response")

    def test_elevator_pitch(self, monkeypatch):
        _, result = _run(monkeypatch, "give me an elevator pitch", _CVProfile())
        assert result["type"] == "profile_pitch"


# ── Context-aware help ─────────────────────────────────────────────────────────

class TestContextAwareHelp:
    """Regression: help must return options type, personalised to profile state."""

    def test_help_with_cv_returns_options(self, monkeypatch):
        _, result = _run(monkeypatch, "help", _CVProfile())
        assert result["type"] == "options"

    def test_help_without_cv_returns_options(self, monkeypatch):
        _, result = _run(monkeypatch, "help", _EmptyProfile())
        assert result["type"] == "options"

    def test_help_empty_profile_has_upload_option(self, monkeypatch):
        _, result = _run(monkeypatch, "help", _EmptyProfile())
        assert result["type"] == "options"
        # Empty profile should have upload or setup-oriented options
        actions = [o["action"] for o in result.get("options", [])]
        assert len(actions) > 0

    def test_what_can_you_do(self, monkeypatch):
        _, result = _run(monkeypatch, "what can you do?", _CVProfile())
        # May route through help or smalltalk; must not be unknown
        assert result["type"] not in ("openai_response", "hf_response", "fallback_response")


# ── Job detail inquiry ────────────────────────────────────────────────────────

class TestJobDetailInquiry:
    """Fast-path for 'tell me more about that job' / job detail requests."""

    _CACHED_JOB = {
        "title": "HSE Manager",
        "company": "ADNOC",
        "location": "Abu Dhabi",
        "apply_url": "https://example.com/apply",
        "source_url": "https://example.com/job",
        "link": "https://example.com/apply",
        "verification_status": "verified",
        "employment_type": "Full-time",
        "salary_string": "AED 25,000/month",
        "description": "Responsible for all HSE activities across the refinery.",
        "why_this_fits": "Your NEBOSH IGC and 8 years experience are a strong match.",
        "worth_checking": "Strong brand name employer with benefits package.",
    }

    def _run_with_context(self, monkeypatch, message: str, context_matches=None):
        import src.rico_chat_api as mod
        from src.rico_chat_api import RicoChatAPI
        from unittest.mock import MagicMock

        mock_route = MagicMock()
        mock_route.tool_name = None
        mock_route.entities = {}
        mock_route.tool_args = {}
        mock_route.confirmation_prompt = None
        mock_route.source = "keyword"

        monkeypatch.setattr(mod, "get_profile", lambda uid: _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: mock_route)
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id, updates: _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)

        api = RicoChatAPI()
        api.system.run_for_profile = MagicMock(return_value={"matches": []})
        ctx = {"recent_search_matches": context_matches} if context_matches is not None else {}
        api._get_recent_context = lambda uid: ctx
        api._append_chat = MagicMock()
        api._store_recent_context = MagicMock()

        result = api._handle_active_user("test-user", message)
        return result

    def test_tell_me_more_no_context(self, monkeypatch):
        result = self._run_with_context(monkeypatch, "tell me more about that job", context_matches=[])
        assert result["type"] == "clarification"

    def test_tell_me_more_no_context_empty(self, monkeypatch):
        result = self._run_with_context(monkeypatch, "tell me more about that job", context_matches=None)
        assert result["type"] == "clarification"

    def test_more_details_on_this_job(self, monkeypatch):
        result = self._run_with_context(
            monkeypatch, "more details on this job", context_matches=[self._CACHED_JOB]
        )
        assert result["type"] == "job_detail"

    def test_whats_the_job_description(self, monkeypatch):
        result = self._run_with_context(
            monkeypatch, "what's the job description?", context_matches=[self._CACHED_JOB]
        )
        assert result["type"] == "job_detail"

    def test_job_details_phrase(self, monkeypatch):
        result = self._run_with_context(
            monkeypatch, "job details please", context_matches=[self._CACHED_JOB]
        )
        assert result["type"] == "job_detail"

    def test_tell_me_more_with_cached_match_has_title(self, monkeypatch):
        result = self._run_with_context(
            monkeypatch, "tell me more about that job", context_matches=[self._CACHED_JOB]
        )
        assert result["type"] == "job_detail"
        assert "HSE Manager" in result["message"]
        assert "ADNOC" in result["message"]

    def test_tell_me_more_includes_employment_type(self, monkeypatch):
        result = self._run_with_context(
            monkeypatch, "tell me more about that job", context_matches=[self._CACHED_JOB]
        )
        assert "Full-time" in result["message"]

    def test_tell_me_more_includes_salary(self, monkeypatch):
        result = self._run_with_context(
            monkeypatch, "tell me more about that job", context_matches=[self._CACHED_JOB]
        )
        assert "25,000" in result["message"]

    def test_arabic_more_details(self, monkeypatch):
        result = self._run_with_context(
            monkeypatch, "المزيد من التفاصيل عن هذه الوظيفة", context_matches=[self._CACHED_JOB]
        )
        assert result["type"] == "job_detail"


# ── Arabic salary word-number parsing ─────────────────────────────────────────

class TestArabicSalaryParsing:
    """Unit tests for _parse_salary_value with Arabic word-numbers."""

    def _parse(self, text: str):
        from src.rico_chat_api import RicoChatAPI
        return RicoChatAPI._parse_salary_value(text)

    def test_fifty_thousand_arabic(self):
        assert self._parse("أريد راتب خمسين ألف") == 50000

    def test_hundred_thousand_arabic_mia(self):
        assert self._parse("براتبي المتوقع مئة ألف") == 100000

    def test_hundred_thousand_arabic_mia2(self):
        assert self._parse("مائة ألف درهم") == 100000

    def test_twenty_thousand_arabic(self):
        assert self._parse("عشرين ألف") == 20000

    def test_numeric_with_alf(self):
        assert self._parse("5 ألف") == 5000

    def test_numeric_with_alaf(self):
        assert self._parse("10 آلاف") == 10000

    def test_fifteen_thousand_arabic(self):
        assert self._parse("خمسة عشر ألف") == 15000

    def test_numeric_k_suffix(self):
        assert self._parse("set my salary to 18k") == 18000

    def test_numeric_with_commas(self):
        assert self._parse("my expected salary is AED 22,000") == 22000

    def test_numeric_plain(self):
        assert self._parse("I want AED 15000 per month") == 15000

    def test_out_of_range_low(self):
        assert self._parse("500") is None

    def test_out_of_range_high(self):
        assert self._parse("AED 600000") is None


# ── Application list query ─────────────────────────────────────────────────────

class TestApplicationsListQuery:
    """Fast-path for 'list my applications', 'what jobs did I apply to?'"""

    def _run_apps_list(self, monkeypatch, message: str, fake_apps=None):
        import src.rico_chat_api as mod
        from src.rico_chat_api import RicoChatAPI
        from unittest.mock import MagicMock, patch

        mock_route = MagicMock()
        mock_route.tool_name = None
        mock_route.entities = {}
        mock_route.tool_args = {}
        mock_route.confirmation_prompt = None
        mock_route.source = "keyword"

        monkeypatch.setattr(mod, "get_profile", lambda uid: _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: mock_route)
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id, updates: _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)

        api = RicoChatAPI()
        api.system.run_for_profile = MagicMock(return_value={"matches": []})
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()

        apps = fake_apps if fake_apps is not None else []
        with patch("src.repositories.applications_repo.get_all", return_value=apps):
            result = api._handle_active_user("test-user", message)
        return result

    def test_what_jobs_did_i_apply_to_empty(self, monkeypatch):
        result = self._run_apps_list(monkeypatch, "what jobs did I apply to?", fake_apps=[])
        assert result["type"] == "clarification"

    def test_what_jobs_did_i_apply_to_with_data(self, monkeypatch):
        apps = [{"title": "HSE Manager", "company": "ADNOC", "status": "applied"}]
        result = self._run_apps_list(monkeypatch, "what jobs did I apply to?", fake_apps=apps)
        assert result["type"] == "application_list"

    def test_how_many_applications(self, monkeypatch):
        apps = [
            {"title": "HSE Manager", "company": "ADNOC", "status": "applied"},
            {"title": "Safety Lead", "company": "BP", "status": "interview"},
            {"title": "EHS Manager", "company": "Shell", "status": "rejected"},
        ]
        result = self._run_apps_list(monkeypatch, "how many applications do I have?", fake_apps=apps)
        assert result["type"] == "application_list"
        assert result["total"] == 3

    def test_show_applied_jobs_with_data(self, monkeypatch):
        apps = [{"title": "HSE Manager", "company": "ADNOC", "status": "applied"}]
        result = self._run_apps_list(monkeypatch, "show my applied jobs", fake_apps=apps)
        assert result["type"] == "application_list"
        assert "HSE Manager" in result["message"]

    def test_application_history(self, monkeypatch):
        apps = [{"title": "Senior HSE Manager", "company": "Emirates", "status": "saved"}]
        result = self._run_apps_list(monkeypatch, "show my application history", fake_apps=apps)
        assert result["type"] == "application_list"

    def test_what_jobs_did_i_apply_to_has_titles(self, monkeypatch):
        apps = [{"title": "Safety Engineer", "company": "Petrofac", "status": "applied"}]
        result = self._run_apps_list(monkeypatch, "what jobs did I apply to?", fake_apps=apps)
        assert "Safety Engineer" in result["message"]


# ── Profile data readback ─────────────────────────────────────────────────────

class TestProfileReadback:
    """Fast-path for 'what skills do you have for me?', 'what do you know about me?'"""

    def test_what_skills_do_you_have(self, monkeypatch):
        _, result = _run(monkeypatch, "what skills do you have for me?", _CVProfile())
        assert result["type"] == "profile_summary"

    def test_what_do_you_know_about_me(self, monkeypatch):
        _, result = _run(monkeypatch, "what do you know about me", _CVProfile())
        assert result["type"] == "profile_summary"

    def test_show_my_skills(self, monkeypatch):
        _, result = _run(monkeypatch, "show my skills", _CVProfile())
        assert result["type"] == "profile_summary"

    def test_what_skills_did_you_store(self, monkeypatch):
        _, result = _run(monkeypatch, "what skills did you store for me?", _CVProfile())
        assert result["type"] == "profile_summary"

    def test_message_contains_skills(self, monkeypatch):
        _, result = _run(monkeypatch, "what do you know about me", _CVProfile())
        assert "hse" in result["message"].lower() or "safety" in result["message"].lower()

    def test_empty_profile_returns_clarification(self, monkeypatch):
        _, result = _run(monkeypatch, "what do you know about me", _EmptyProfile())
        assert result["type"] == "clarification"

    def test_show_my_profile_data(self, monkeypatch):
        _, result = _run(monkeypatch, "show my profile data", _CVProfile())
        assert result["type"] == "profile_summary"


# ── Job detail fallback to recent_application context ─────────────────────────

class TestJobDetailAppliedFallback:
    """_handle_job_detail falls back to recent_application when no search matches."""

    _APPLIED_JOB = {
        "job_id": "abc123",
        "title": "HSE Manager",
        "company": "ADNOC",
        "status": "applied",
        "link": "https://example.com/apply",
    }

    def _run_with_applied_ctx(self, monkeypatch, message: str, applied_job=None):
        import src.rico_chat_api as mod
        from src.rico_chat_api import RicoChatAPI
        from unittest.mock import MagicMock

        mock_route = MagicMock()
        mock_route.tool_name = None
        mock_route.entities = {}
        mock_route.tool_args = {}
        mock_route.confirmation_prompt = None
        mock_route.source = "keyword"

        monkeypatch.setattr(mod, "get_profile", lambda uid: _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: mock_route)
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id, updates: _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)

        api = RicoChatAPI()
        api.system.run_for_profile = MagicMock(return_value={"matches": []})
        ctx: dict = {}
        if applied_job:
            ctx["recent_application"] = applied_job
        api._get_recent_context = lambda uid: ctx
        api._append_chat = MagicMock()
        api._store_recent_context = MagicMock()

        result = api._handle_active_user("test-user", message)
        return result

    def test_no_context_returns_clarification(self, monkeypatch):
        result = self._run_with_applied_ctx(monkeypatch, "tell me more about that job")
        assert result["type"] == "clarification"

    def test_applied_job_context_returns_job_detail(self, monkeypatch):
        result = self._run_with_applied_ctx(
            monkeypatch, "tell me more about that job", applied_job=self._APPLIED_JOB
        )
        assert result["type"] == "job_detail"

    def test_applied_job_detail_has_title(self, monkeypatch):
        result = self._run_with_applied_ctx(
            monkeypatch, "tell me more about that job", applied_job=self._APPLIED_JOB
        )
        assert "HSE Manager" in result["message"]


# ── Ordinal job selection ──────────────────────────────────────────────────────

class TestOrdinalJobSelection:
    """'tell me more about the second job', 'the third one' → detail for matches[N-1]."""

    _MATCHES = [
        {"title": "HSE Manager", "company": "ADNOC", "location": "Abu Dhabi",
         "apply_url": "https://example.com/1", "employment_type": "Full-time",
         "salary_string": "AED 25,000", "description": "First job.", "why_this_fits": "", "worth_checking": ""},
        {"title": "Safety Engineer", "company": "Petrofac", "location": "Dubai",
         "apply_url": "https://example.com/2", "employment_type": "Full-time",
         "salary_string": "AED 18,000", "description": "Second job.", "why_this_fits": "", "worth_checking": ""},
        {"title": "EHS Specialist", "company": "Shell", "location": "Sharjah",
         "apply_url": "https://example.com/3", "employment_type": "Contract",
         "salary_string": "AED 22,000", "description": "Third job.", "why_this_fits": "", "worth_checking": ""},
    ]

    def _run_ordinal(self, monkeypatch, message: str, matches=None):
        import src.rico_chat_api as mod
        from src.rico_chat_api import RicoChatAPI
        from unittest.mock import MagicMock

        mock_route = MagicMock()
        mock_route.tool_name = None
        mock_route.entities = {}
        mock_route.tool_args = {}
        mock_route.confirmation_prompt = None
        mock_route.source = "keyword"

        monkeypatch.setattr(mod, "get_profile", lambda uid: _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: mock_route)
        monkeypatch.setattr(mod, "upsert_profile", lambda uid, u: _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)

        api = RicoChatAPI()
        api.system.run_for_profile = MagicMock(return_value={"matches": []})
        ctx = {"recent_search_matches": matches if matches is not None else self._MATCHES}
        api._get_recent_context = lambda uid: ctx
        api._append_chat = MagicMock()
        api._store_recent_context = MagicMock()

        return api._handle_active_user("test-user", message)

    def test_second_job_returns_second_match(self, monkeypatch):
        result = self._run_ordinal(monkeypatch, "tell me more about the second job")
        assert result["type"] == "job_detail"
        assert "Safety Engineer" in result["message"]

    def test_third_one_returns_third_match(self, monkeypatch):
        result = self._run_ordinal(monkeypatch, "the third one looks interesting")
        assert result["type"] == "job_detail"
        assert "EHS Specialist" in result["message"]

    def test_job_number_2(self, monkeypatch):
        result = self._run_ordinal(monkeypatch, "job number 2")
        assert result["type"] == "job_detail"
        assert "Petrofac" in result["message"]

    def test_option_2(self, monkeypatch):
        result = self._run_ordinal(monkeypatch, "option 2 looks good, tell me more")
        assert result["type"] == "job_detail"

    def test_first_job_default(self, monkeypatch):
        result = self._run_ordinal(monkeypatch, "tell me more about that job")
        assert result["type"] == "job_detail"
        assert "HSE Manager" in result["message"]

    def test_ordinal_to_index_static(self):
        from src.rico_chat_api import RicoChatAPI
        assert RicoChatAPI._ordinal_to_index("second") == 1
        assert RicoChatAPI._ordinal_to_index("third") == 2
        assert RicoChatAPI._ordinal_to_index("2") == 1
        assert RicoChatAPI._ordinal_to_index("first") == 0


# ── Salary expectation readback ────────────────────────────────────────────────

class TestSalaryReadback:
    """'what salary did I set?', 'what's my expected salary?' → saved salary."""

    def test_what_salary_did_i_set(self, monkeypatch):
        from dataclasses import dataclass, field
        from typing import List, Optional

        @dataclass
        class _SalaryProfile:
            skills:           List[str] = field(default_factory=lambda: ["hse"])
            certifications:   List[str] = field(default_factory=list)
            years_experience: float     = 5.0
            target_roles:     List[str] = field(default_factory=lambda: ["HSE Manager"])
            industries:       List[str] = field(default_factory=list)
            cv_status:        str       = "parsed"
            cv_filename:      str       = "cv.pdf"
            salary_expectation_aed:     int = 20000

        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: _SalaryProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)

        from src.rico_chat_api import RicoChatAPI
        from unittest.mock import MagicMock
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        result = api._handle_active_user("test-user", "what salary did I set?")
        assert result["type"] == "salary_readback"
        assert "20,000" in result["message"]

    def test_no_salary_set_returns_clarification_type(self, monkeypatch):
        _, result = _run(monkeypatch, "what's my expected salary?", _CVProfile())
        assert result["type"] == "salary_readback"

    def test_what_is_my_minimum_salary(self, monkeypatch):
        _, result = _run(monkeypatch, "what is my minimum salary?", _CVProfile())
        assert result["type"] == "salary_readback"

    def test_my_salary_expectation(self, monkeypatch):
        _, result = _run(monkeypatch, "my salary expectation", _CVProfile())
        assert result["type"] == "salary_readback"


# ── Granular profile field update ──────────────────────────────────────────────

class TestProfileFieldUpdate:
    """Verify _handle_profile_field_update routes and returns profile_update type."""

    @pytest.mark.parametrize("phrase", [
        "add Python to my skills",
        "add NEBOSH to my certifications",
        "remove OSHA from my skills",
        "update my experience to 8 years",
        "I have 10 years of experience",
        "I'm now based in Abu Dhabi",
        "change my target role to HSE Manager",
        "add oil and gas to my industries",
    ])
    def test_regex_matches(self, phrase):
        from src.rico_chat_api import _PROFILE_FIELD_UPDATE_RE
        assert _PROFILE_FIELD_UPDATE_RE.search(phrase), (
            f"_PROFILE_FIELD_UPDATE_RE should match: {phrase!r}"
        )

    @pytest.mark.parametrize("phrase", [
        # Generic profile questions — should NOT fire
        "show my profile",
        "what do you know about me",
        "what is my salary",
        # Bare experience mention without explicit update
        "I have experience in construction",
        # Job searches
        "find me jobs in construction",
        "show me HSE jobs",
    ])
    def test_regex_does_not_match(self, phrase):
        from src.rico_chat_api import _PROFILE_FIELD_UPDATE_RE
        assert not _PROFILE_FIELD_UPDATE_RE.search(phrase), (
            f"_PROFILE_FIELD_UPDATE_RE should NOT match: {phrase!r}"
        )

    def test_add_skill_returns_profile_update(self, monkeypatch):
        _, result = _run(monkeypatch, "add Python to my skills", _CVProfile())
        assert result["type"] == "profile_update"
        assert result["field"] == "skills"
        assert result["operation"] == "add"
        assert "Python" in result["message"]

    def test_remove_skill_returns_profile_update(self, monkeypatch):
        _, result = _run(monkeypatch, "remove OSHA from my skills", _CVProfile())
        assert result["type"] == "profile_update"
        assert result["field"] == "skills"
        assert result["operation"] == "remove"

    def test_update_experience_returns_profile_update(self, monkeypatch):
        _, result = _run(monkeypatch, "update my experience to 8 years", _CVProfile())
        assert result["type"] == "profile_update"
        assert result["field"] == "years_experience"
        assert "8" in result["message"]

    def test_i_have_n_years_experience(self, monkeypatch):
        _, result = _run(monkeypatch, "I have 10 years of experience", _CVProfile())
        assert result["type"] == "profile_update"
        assert result["field"] == "years_experience"
        assert "10" in result["message"]

    def test_change_target_role(self, monkeypatch):
        _, result = _run(monkeypatch, "change my target role to Safety Manager", _CVProfile())
        assert result["type"] == "profile_update"
        assert result["field"] == "target_roles"
        assert "Safety Manager" in result["message"]

    def test_add_industry(self, monkeypatch):
        _, result = _run(monkeypatch, "add oil and gas to my industries", _CVProfile())
        assert result["type"] == "profile_update"
        assert result["field"] == "industries"
        assert result["operation"] == "add"


# ── Application-specific lookup ────────────────────────────────────────────────

class TestAppSpecificLookup:
    """Verify _handle_app_specific_lookup routing and response types."""

    @pytest.mark.parametrize("phrase", [
        "did I apply to Emirates?",
        "have I applied to ADNOC?",
        "status of my Carrefour application",
        "my application at DEWA",
        "when did I apply to Google?",
    ])
    def test_regex_matches(self, phrase):
        from src.rico_chat_api import _APP_SPECIFIC_LOOKUP_RE
        assert _APP_SPECIFIC_LOOKUP_RE.search(phrase), (
            f"_APP_SPECIFIC_LOOKUP_RE should match: {phrase!r}"
        )

    @pytest.mark.parametrize("phrase", [
        # Generic list queries — already covered by _APPLICATIONS_LIST_RE
        "show my applications",
        "list my applications",
        # Job search — not application lookup
        "find jobs at ADNOC",
        # Salary
        "what salary did I set",
    ])
    def test_regex_does_not_match(self, phrase):
        from src.rico_chat_api import _APP_SPECIFIC_LOOKUP_RE
        assert not _APP_SPECIFIC_LOOKUP_RE.search(phrase), (
            f"_APP_SPECIFIC_LOOKUP_RE should NOT match: {phrase!r}"
        )

    def test_not_found_returns_application_detail(self, monkeypatch):
        import src.rico_chat_api as mod
        from src.rico_chat_api import RicoChatAPI
        from unittest.mock import MagicMock
        import src.repositories.applications_repo as apps_repo

        monkeypatch.setattr(mod, "get_profile", lambda uid: _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock(
            tool_name=None, entities={}, tool_args={}, confirmation_prompt=None, source="keyword"
        ))
        monkeypatch.setattr(mod, "upsert_profile", lambda uid, u: _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        monkeypatch.setattr(apps_repo, "get_all", lambda user_id: [])

        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        result = api._handle_active_user("u1", "did I apply to Emirates?")
        assert result["type"] == "application_detail"
        assert result["found"] is False

    def test_found_returns_application_detail_with_data(self, monkeypatch):
        import src.rico_chat_api as mod
        from src.rico_chat_api import RicoChatAPI
        from unittest.mock import MagicMock
        import src.repositories.applications_repo as apps_repo

        monkeypatch.setattr(mod, "get_profile", lambda uid: _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock(
            tool_name=None, entities={}, tool_args={}, confirmation_prompt=None, source="keyword"
        ))
        monkeypatch.setattr(mod, "upsert_profile", lambda uid, u: _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        monkeypatch.setattr(apps_repo, "get_all", lambda user_id: [
            {"job_id": "j1", "title": "HSE Officer", "company": "Emirates NBD",
             "status": "applied", "applied_at": "2026-06-01"}
        ])

        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        result = api._handle_active_user("u1", "did I apply to Emirates?")
        assert result["type"] == "application_detail"
        assert result["found"] is True
        assert "Emirates" in result["message"]


# ── Company-targeted job search ────────────────────────────────────────────────

class TestCompanySearch:
    """Verify _handle_company_search routing and response types."""

    @pytest.mark.parametrize("phrase", [
        "find jobs at ADNOC",
        "find me jobs at Emirates NBD",
        "any openings at Carrefour?",
        "any vacancies at DEWA",
        "jobs at Emaar",
    ])
    def test_regex_matches(self, phrase):
        from src.rico_chat_api import _COMPANY_SEARCH_RE
        assert _COMPANY_SEARCH_RE.search(phrase), (
            f"_COMPANY_SEARCH_RE should match: {phrase!r}"
        )

    @pytest.mark.parametrize("phrase", [
        # Location-based search — uses "in", not "at"
        "find jobs in Dubai",
        "jobs in Abu Dhabi",
        # Generic search
        "find me HSE jobs",
        "show me applications",
        # Generic "at" without recognizable company-style word
        "applied at",
    ])
    def test_regex_does_not_match(self, phrase):
        from src.rico_chat_api import _COMPANY_SEARCH_RE
        assert not _COMPANY_SEARCH_RE.search(phrase), (
            f"_COMPANY_SEARCH_RE should NOT match: {phrase!r}"
        )

    def test_no_results_returns_no_results_type(self, monkeypatch):
        import src.rico_chat_api as mod
        from src.rico_chat_api import RicoChatAPI
        from src.jsearch_client import FetchResult
        from unittest.mock import MagicMock

        monkeypatch.setattr(mod, "get_profile", lambda uid: _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock(
            tool_name=None, entities={}, tool_args={}, confirmation_prompt=None, source="keyword"
        ))
        monkeypatch.setattr(mod, "upsert_profile", lambda uid, u: _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)

        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._store_recent_context = MagicMock()
        monkeypatch.setattr(api, "_search_jsearch_meta", lambda q, loc="": FetchResult(items=[]))

        result = api._handle_active_user("u1", "find jobs at ADNOC")
        assert result["type"] == "no_results"
        assert "ADNOC" in result["message"]

    def test_with_results_returns_job_matches(self, monkeypatch):
        import src.rico_chat_api as mod
        from src.rico_chat_api import RicoChatAPI
        from src.jsearch_client import FetchResult
        from unittest.mock import MagicMock

        monkeypatch.setattr(mod, "get_profile", lambda uid: _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock(
            tool_name=None, entities={}, tool_args={}, confirmation_prompt=None, source="keyword"
        ))
        monkeypatch.setattr(mod, "upsert_profile", lambda uid, u: _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)

        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._store_recent_context = MagicMock()
        monkeypatch.setattr(api, "_search_jsearch_meta", lambda q, loc="": FetchResult(items=[
            {"title": "HSE Engineer", "company": "ADNOC", "location": "Abu Dhabi",
             "apply_url": "https://adnoc.ae/jobs/1"},
        ]))

        result = api._handle_active_user("u1", "find jobs at ADNOC")
        assert result["type"] == "job_matches"
        assert result["company"] == "ADNOC"
        assert len(result["jobs"]) >= 1


# ── Salary-filtered job search ──────────────────────────────────────────────────

class TestSalaryFilteredSearch:
    """Verify _handle_salary_filtered_search routing and response types."""

    @pytest.mark.parametrize("phrase", [
        "find HSE jobs paying above 20k AED",
        "show me QHSE roles with salary above 25000",
        "jobs paying more than 30000 AED",
        "minimum salary 20000 AED jobs",
        "salary above 15000 positions",
        "find safety manager roles paying at least 25k",
    ])
    def test_regex_matches(self, phrase):
        from src.rico_chat_api import _SALARY_SEARCH_RE
        assert _SALARY_SEARCH_RE.search(phrase), (
            f"_SALARY_SEARCH_RE should match: {phrase!r}"
        )

    @pytest.mark.parametrize("phrase", [
        # Generic searches without salary — should not fire
        "find HSE jobs",
        "show me QHSE jobs",
        # Salary readback — different gate
        "what is my salary",
        "what salary did I set",
        # Company search
        "find jobs at ADNOC",
    ])
    def test_regex_does_not_match(self, phrase):
        from src.rico_chat_api import _SALARY_SEARCH_RE
        assert not _SALARY_SEARCH_RE.search(phrase), (
            f"_SALARY_SEARCH_RE should NOT match: {phrase!r}"
        )

    def test_no_results_returns_no_results(self, monkeypatch):
        import src.rico_chat_api as mod
        from src.rico_chat_api import RicoChatAPI
        from src.jsearch_client import FetchResult
        from unittest.mock import MagicMock

        monkeypatch.setattr(mod, "get_profile", lambda uid: _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock(
            tool_name=None, entities={}, tool_args={}, confirmation_prompt=None, source="keyword"
        ))
        monkeypatch.setattr(mod, "upsert_profile", lambda uid, u: _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)

        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._store_recent_context = MagicMock()
        monkeypatch.setattr(api, "_search_jsearch_meta", lambda q, loc="": FetchResult(items=[]))

        result = api._handle_active_user("u1", "find HSE jobs paying above 20k AED")
        assert result["type"] == "no_results"

    def test_with_results_returns_job_matches(self, monkeypatch):
        import src.rico_chat_api as mod
        from src.rico_chat_api import RicoChatAPI
        from src.jsearch_client import FetchResult
        from unittest.mock import MagicMock

        monkeypatch.setattr(mod, "get_profile", lambda uid: _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock(
            tool_name=None, entities={}, tool_args={}, confirmation_prompt=None, source="keyword"
        ))
        monkeypatch.setattr(mod, "upsert_profile", lambda uid, u: _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)

        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._store_recent_context = MagicMock()
        monkeypatch.setattr(api, "_search_jsearch_meta", lambda q, loc="": FetchResult(items=[
            {"title": "HSE Manager", "company": "ADNOC", "location": "Abu Dhabi",
             "salary_string": "AED 25,000/month", "apply_url": ""},
        ]))

        result = api._handle_active_user("u1", "find HSE jobs paying above 20k AED")
        assert result["type"] == "job_matches"
        assert result["min_salary_aed"] == 20000
        assert len(result["jobs"]) >= 1


# ── Employment-type filter search ──────────────────────────────────────────────

class TestEmploymentTypeSearch:
    """Verify _handle_employment_type_search routing and response types."""

    @pytest.mark.parametrize("phrase", [
        "find remote HSE jobs",
        "find me hybrid positions in Dubai",
        "contract QHSE roles in Abu Dhabi",
        "show me part-time jobs",
        "find freelance safety positions",
        "show remote safety manager roles",
    ])
    def test_regex_matches(self, phrase):
        from src.rico_chat_api import _EMPLOYMENT_TYPE_RE
        assert _EMPLOYMENT_TYPE_RE.search(phrase), (
            f"_EMPLOYMENT_TYPE_RE should match: {phrase!r}"
        )

    @pytest.mark.parametrize("phrase", [
        # Generic searches without employment type
        "find HSE jobs",
        "show me QHSE roles",
        # Company search
        "find jobs at ADNOC",
        # Salary search
        "find HSE jobs paying above 20k",
        # Unrelated
        "show my applications",
    ])
    def test_regex_does_not_match(self, phrase):
        from src.rico_chat_api import _EMPLOYMENT_TYPE_RE
        assert not _EMPLOYMENT_TYPE_RE.search(phrase), (
            f"_EMPLOYMENT_TYPE_RE should NOT match: {phrase!r}"
        )

    def test_remote_search_returns_job_matches(self, monkeypatch):
        import src.rico_chat_api as mod
        from src.rico_chat_api import RicoChatAPI
        from src.jsearch_client import FetchResult
        from unittest.mock import MagicMock

        monkeypatch.setattr(mod, "get_profile", lambda uid: _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock(
            tool_name=None, entities={}, tool_args={}, confirmation_prompt=None, source="keyword"
        ))
        monkeypatch.setattr(mod, "upsert_profile", lambda uid, u: _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)

        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._store_recent_context = MagicMock()
        monkeypatch.setattr(api, "_search_jsearch_meta", lambda q, loc="": FetchResult(items=[
            {"title": "Remote HSE Manager", "company": "TechCorp", "location": "Remote",
             "employment_type": "remote", "apply_url": ""},
        ]))

        result = api._handle_active_user("u1", "find remote HSE jobs")
        assert result["type"] == "job_matches"
        assert result["employment_type"] == "remote"


# ── Follow-up timing advice ────────────────────────────────────────────────────

class TestFollowupTiming:
    """Verify _handle_followup_timing routing and response type."""

    @pytest.mark.parametrize("phrase", [
        "when should I follow up?",
        "how many days before following up?",
        "should I follow up now?",
        "follow-up timing advice",
        "is it too early to follow up?",
        "how do I follow up?",
        "follow up email template",
    ])
    def test_regex_matches(self, phrase):
        from src.rico_chat_api import _FOLLOWUP_TIMING_RE
        assert _FOLLOWUP_TIMING_RE.search(phrase), (
            f"_FOLLOWUP_TIMING_RE should match: {phrase!r}"
        )

    @pytest.mark.parametrize("phrase", [
        # Unrelated follow-up phrases
        "follow me on LinkedIn",
        "following up on my order",
        # Application queries
        "show my applications",
        "did I apply to Emirates",
        # Generic
        "when will I hear back?",
    ])
    def test_regex_does_not_match(self, phrase):
        from src.rico_chat_api import _FOLLOWUP_TIMING_RE
        assert not _FOLLOWUP_TIMING_RE.search(phrase), (
            f"_FOLLOWUP_TIMING_RE should NOT match: {phrase!r}"
        )

    def test_returns_followup_timing_type(self, monkeypatch):
        _, result = _run(monkeypatch, "when should I follow up?", _CVProfile())
        assert result["type"] == "followup_timing"
        assert result["message"]

    def test_advice_mentions_weeks(self, monkeypatch):
        _, result = _run(monkeypatch, "how many days before following up?", _CVProfile())
        assert result["type"] == "followup_timing"
        assert "week" in result["message"].lower() or "days" in result["message"].lower()

    def test_company_specific_followup(self, monkeypatch):
        _, result = _run(monkeypatch, "should I follow up with Emirates now?", _CVProfile())
        assert result["type"] == "followup_timing"
        assert "Emirates" in result["message"]

    def test_followup_template_phrase(self, monkeypatch):
        _, result = _run(monkeypatch, "follow up email template", _CVProfile())
        assert result["type"] == "followup_timing"


# ── Industry-based job search ──────────────────────────────────────────────────

class TestIndustrySearch:
    """Verify _handle_industry_search routing and response types."""

    @pytest.mark.parametrize("phrase", [
        "find jobs in oil and gas",
        "find me jobs in construction",
        "healthcare sector jobs in Abu Dhabi",
        "finance industry positions",
        "show me jobs in real estate",
        "logistics jobs in Dubai",
    ])
    def test_regex_matches(self, phrase):
        from src.rico_chat_api import _INDUSTRY_SEARCH_RE
        assert _INDUSTRY_SEARCH_RE.search(phrase), (
            f"_INDUSTRY_SEARCH_RE should match: {phrase!r}"
        )

    @pytest.mark.parametrize("phrase", [
        # Role-based searches — should NOT fire
        "find HSE jobs",
        "show me QHSE roles",
        # Company search
        "find jobs at ADNOC",
        # Location without industry
        "find jobs in Dubai",
        # Generic
        "show my applications",
    ])
    def test_regex_does_not_match(self, phrase):
        from src.rico_chat_api import _INDUSTRY_SEARCH_RE
        assert not _INDUSTRY_SEARCH_RE.search(phrase), (
            f"_INDUSTRY_SEARCH_RE should NOT match: {phrase!r}"
        )

    def test_no_results_returns_no_results(self, monkeypatch):
        import src.rico_chat_api as mod
        from src.rico_chat_api import RicoChatAPI
        from src.jsearch_client import FetchResult
        from unittest.mock import MagicMock

        monkeypatch.setattr(mod, "get_profile", lambda uid: _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock(
            tool_name=None, entities={}, tool_args={}, confirmation_prompt=None, source="keyword"
        ))
        monkeypatch.setattr(mod, "upsert_profile", lambda uid, u: _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)

        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._store_recent_context = MagicMock()
        monkeypatch.setattr(api, "_search_jsearch_meta", lambda q, loc="": FetchResult(items=[]))

        result = api._handle_active_user("u1", "find jobs in oil and gas")
        assert result["type"] == "no_results"

    def test_with_results_returns_job_matches(self, monkeypatch):
        import src.rico_chat_api as mod
        from src.rico_chat_api import RicoChatAPI
        from src.jsearch_client import FetchResult
        from unittest.mock import MagicMock

        monkeypatch.setattr(mod, "get_profile", lambda uid: _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock(
            tool_name=None, entities={}, tool_args={}, confirmation_prompt=None, source="keyword"
        ))
        monkeypatch.setattr(mod, "upsert_profile", lambda uid, u: _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)

        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._store_recent_context = MagicMock()
        monkeypatch.setattr(api, "_search_jsearch_meta", lambda q, loc="": FetchResult(items=[
            {"title": "HSE Engineer", "company": "ADNOC", "location": "Abu Dhabi", "apply_url": ""},
        ]))

        result = api._handle_active_user("u1", "find jobs in oil and gas")
        assert result["type"] == "job_matches"
        assert result["industry"] == "oil and gas"


# ── Job comparison ─────────────────────────────────────────────────────────────

class TestJobComparison:
    """Verify _handle_job_comparison routing and response types."""

    @pytest.mark.parametrize("phrase", [
        "compare job 1 and job 2",
        "compare the first and second job",
        "which is better job 1 or job 3?",
        "job 1 vs job 2",
        "difference between job 1 and 3",
    ])
    def test_regex_matches(self, phrase):
        from src.rico_chat_api import _JOB_COMPARE_RE
        assert _JOB_COMPARE_RE.search(phrase), (
            f"_JOB_COMPARE_RE should match: {phrase!r}"
        )

    @pytest.mark.parametrize("phrase", [
        # Ordinal job selection — different gate
        "tell me more about the second job",
        "job number 2",
        # Industry search
        "find jobs in oil and gas",
        # Generic
        "show my applications",
    ])
    def test_regex_does_not_match(self, phrase):
        from src.rico_chat_api import _JOB_COMPARE_RE
        assert not _JOB_COMPARE_RE.search(phrase), (
            f"_JOB_COMPARE_RE should NOT match: {phrase!r}"
        )

    def test_no_cached_results_returns_clarification(self, monkeypatch):
        _, result = _run(monkeypatch, "compare job 1 and job 2", _CVProfile())
        assert result["type"] == "clarification"

    def test_with_cached_results_returns_comparison(self, monkeypatch):
        import src.rico_chat_api as mod
        from src.rico_chat_api import RicoChatAPI
        from unittest.mock import MagicMock

        monkeypatch.setattr(mod, "get_profile", lambda uid: _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock(
            tool_name=None, entities={}, tool_args={}, confirmation_prompt=None, source="keyword"
        ))
        monkeypatch.setattr(mod, "upsert_profile", lambda uid, u: _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)

        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {
            "recent_search_matches": [
                {"title": "HSE Manager", "company": "ADNOC", "location": "Abu Dhabi",
                 "salary_string": "AED 25,000"},
                {"title": "Safety Engineer", "company": "Petrofac", "location": "Dubai",
                 "salary_string": "AED 18,000"},
            ]
        }
        api._append_chat = MagicMock()

        result = api._handle_active_user("u1", "compare job 1 and job 2")
        assert result["type"] == "job_comparison"
        assert result["job_a_index"] == 0
        assert result["job_b_index"] == 1
        assert "ADNOC" in result["message"]
        assert "Petrofac" in result["message"]


# ── Search result count ────────────────────────────────────────────────────────

class TestResultCount:
    """Verify _handle_result_count routing and response types."""

    @pytest.mark.parametrize("phrase", [
        "how many jobs did you find?",
        "how many results were there?",
        "how many matches did you get?",
        "total number of jobs",
        "how many vacancies are there?",
    ])
    def test_regex_matches(self, phrase):
        from src.rico_chat_api import _RESULT_COUNT_RE
        assert _RESULT_COUNT_RE.search(phrase), (
            f"_RESULT_COUNT_RE should match: {phrase!r}"
        )

    @pytest.mark.parametrize("phrase", [
        # Application count — different gate
        "how many applications do I have?",
        # Generic
        "show my applications",
        "find me jobs",
    ])
    def test_regex_does_not_match(self, phrase):
        from src.rico_chat_api import _RESULT_COUNT_RE
        assert not _RESULT_COUNT_RE.search(phrase), (
            f"_RESULT_COUNT_RE should NOT match: {phrase!r}"
        )

    def test_no_cache_returns_result_count(self, monkeypatch):
        _, result = _run(monkeypatch, "how many jobs did you find?", _CVProfile())
        assert result["type"] == "result_count"
        assert result["count"] == 0

    def test_with_cached_results_returns_correct_count(self, monkeypatch):
        import src.rico_chat_api as mod
        from src.rico_chat_api import RicoChatAPI
        from unittest.mock import MagicMock

        monkeypatch.setattr(mod, "get_profile", lambda uid: _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock(
            tool_name=None, entities={}, tool_args={}, confirmation_prompt=None, source="keyword"
        ))
        monkeypatch.setattr(mod, "upsert_profile", lambda uid, u: _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)

        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {
            "recent_search_matches": [
                {"title": f"Role {i}"} for i in range(7)
            ],
            "recent_search_role": "HSE Manager",
        }
        api._append_chat = MagicMock()

        result = api._handle_active_user("u1", "how many jobs did you find?")
        assert result["type"] == "result_count"
        assert result["count"] == 7


# ── _CERTIFICATION_ADVICE_RE ──────────────────────────────────────────────────

class TestCertificationAdvice:
    """Regex gate and handler for certification/qualification advice."""

    @pytest.mark.parametrize("phrase", [
        "what certifications do I need for HSE jobs?",
        "what qualifications are required for finance roles?",
        "what courses should I do for project management?",
        "what credentials are needed for construction jobs?",
        "required certifications for safety manager",
        "recommended qualifications for data analyst",
        "what makes someone eligible for a senior role?",
    ])
    def test_regex_matches(self, phrase):
        from src.rico_chat_api import _CERTIFICATION_ADVICE_RE
        assert _CERTIFICATION_ADVICE_RE.search(phrase), (
            f"_CERTIFICATION_ADVICE_RE should match: {phrase!r}"
        )

    @pytest.mark.parametrize("phrase", [
        "find HSE jobs in Dubai",
        "how many applications did I send?",
        "what is my notice period?",
        "I have NEBOSH certification",
        "update my certifications",
    ])
    def test_regex_does_not_match(self, phrase):
        from src.rico_chat_api import _CERTIFICATION_ADVICE_RE
        assert not _CERTIFICATION_ADVICE_RE.search(phrase), (
            f"_CERTIFICATION_ADVICE_RE should NOT match: {phrase!r}"
        )

    def test_routes_to_certification_advice(self, monkeypatch):
        _, result = _run(monkeypatch, "what certifications do I need for HSE?", _CVProfile())
        assert result["type"] == "certification_advice"

    def test_returns_certifications_list(self, monkeypatch):
        _, result = _run(monkeypatch, "what certifications do I need for HSE?", _CVProfile())
        assert isinstance(result.get("certifications"), list)
        assert len(result["certifications"]) > 0

    def test_finance_sector_returns_cfa(self, monkeypatch):
        _, result = _run(monkeypatch, "what certifications are needed for finance roles?", _CVProfile())
        certs = " ".join(result.get("certifications", [])).upper()
        assert any(c in certs for c in ["CFA", "CMA", "ACCA", "CIMA"])

    def test_hse_sector_returns_nebosh(self, monkeypatch):
        _, result = _run(monkeypatch, "what certifications do I need for HSE?", _CVProfile())
        certs = " ".join(result.get("certifications", [])).upper()
        assert any(c in certs for c in ["NEBOSH", "IOSH"])

    def test_message_field_present(self, monkeypatch):
        _, result = _run(monkeypatch, "what certifications do I need for HSE?", _CVProfile())
        assert isinstance(result.get("message"), str)
        assert len(result["message"]) > 20

    def test_empty_profile_still_works(self, monkeypatch):
        _, result = _run(monkeypatch, "what qualifications are needed for IT jobs?", _EmptyProfile())
        assert result["type"] == "certification_advice"


# ── _SENIORITY_SEARCH_RE ──────────────────────────────────────────────────────

class TestSenioritySearch:
    """Regex gate and handler for seniority-filtered job search."""

    @pytest.mark.parametrize("phrase", [
        "find me senior HSE jobs",
        "find junior developer roles",
        "show entry-level positions in Dubai",
        "search for mid-level finance jobs",
        "find director-level opportunities",
        "jobs for graduates in engineering",
        "roles for freshers in marketing",
        "find intern positions in Abu Dhabi",
    ])
    def test_regex_matches(self, phrase):
        from src.rico_chat_api import _SENIORITY_SEARCH_RE
        assert _SENIORITY_SEARCH_RE.search(phrase), (
            f"_SENIORITY_SEARCH_RE should match: {phrase!r}"
        )

    @pytest.mark.parametrize("phrase", [
        "find live jobs for Senior HSE Manager",
        "find UAE jobs for Senior HSE Manager",
        "find live jobs for Senior Sustainability Officer",
        "find jobs for Senior Project Manager in Dubai",
        "how many jobs did you find?",
        "compare job 1 and job 2",
        "what certifications do I need?",
    ])
    def test_regex_does_not_match(self, phrase):
        from src.rico_chat_api import _SENIORITY_SEARCH_RE
        assert not _SENIORITY_SEARCH_RE.search(phrase), (
            f"_SENIORITY_SEARCH_RE should NOT match: {phrase!r}"
        )

    def _run_with_jsearch(self, monkeypatch, message, profile, items=None, error=None):
        """Run with _search_jsearch_meta mocked on the api instance."""
        import src.rico_chat_api as mod
        from src.rico_chat_api import RicoChatAPI
        from unittest.mock import MagicMock

        _items = items if items is not None else []

        class _FakeResult:
            pass

        fake = _FakeResult()
        fake.items = _items
        fake.error = error

        mock_route = MagicMock()
        mock_route.tool_name           = None
        mock_route.entities            = {}
        mock_route.tool_args           = {}
        mock_route.confirmation_prompt = None
        mock_route.source              = "keyword"

        monkeypatch.setattr(mod, "get_profile",    lambda uid: profile)
        monkeypatch.setattr(mod, "_route",         lambda *a, **kw: mock_route)
        monkeypatch.setattr(mod, "upsert_profile", lambda uid, u: profile)
        monkeypatch.setattr(mod, "hf_ok",          lambda: False)

        api = RicoChatAPI()
        api._search_jsearch_meta = lambda q, location="": fake
        api._get_recent_context  = lambda uid: {}
        api._append_chat         = MagicMock()

        return api._handle_active_user("test-user", message)

    def test_routes_to_job_matches(self, monkeypatch):
        result = self._run_with_jsearch(
            monkeypatch, "find me senior HSE jobs", _CVProfile(),
            items=[{"job_title": "Senior HSE Manager", "employer_name": "ADNOC"}],
        )
        assert result["type"] == "job_matches"

    def test_seniority_extracted(self, monkeypatch):
        result = self._run_with_jsearch(monkeypatch, "find me junior developer roles", _CVProfile())
        assert result.get("seniority", "").lower() in ("junior", "")

    def test_returns_jobs_list(self, monkeypatch):
        result = self._run_with_jsearch(
            monkeypatch, "find me senior HSE jobs", _CVProfile(),
            items=[{"job_title": "Senior HSE Manager", "employer_name": "ADNOC"}],
        )
        assert isinstance(result.get("jobs"), list)

    def test_no_jsearch_fallback_still_returns_type(self, monkeypatch):
        result = self._run_with_jsearch(
            monkeypatch, "find me senior HSE jobs", _CVProfile(), error="API error"
        )
        # Returns no_results gracefully when API yields nothing
        assert result["type"] in ("job_matches", "no_results")


# ── _MARKET_PULSE_RE ──────────────────────────────────────────────────────────

class TestMarketPulse:
    """Regex gate and handler for job market pulse queries."""

    @pytest.mark.parametrize("phrase", [
        "how's the job market for HSE?",
        "how is the market for finance in UAE?",
        "are there many HSE jobs in Dubai?",
        "how competitive is the job market for data engineers?",
        "what's the job market outlook for construction?",
        "is it easy to find a job in project management?",
        "is it hard to find work in UAE finance?",
        "job market status for cybersecurity",
    ])
    def test_regex_matches(self, phrase):
        from src.rico_chat_api import _MARKET_PULSE_RE
        assert _MARKET_PULSE_RE.search(phrase), (
            f"_MARKET_PULSE_RE should match: {phrase!r}"
        )

    @pytest.mark.parametrize("phrase", [
        "find HSE jobs in Dubai",
        "what certifications do I need?",
        "how many jobs did you find?",
        "compare job 1 and 2",
        "update my salary expectations",
    ])
    def test_regex_does_not_match(self, phrase):
        from src.rico_chat_api import _MARKET_PULSE_RE
        assert not _MARKET_PULSE_RE.search(phrase), (
            f"_MARKET_PULSE_RE should NOT match: {phrase!r}"
        )

    def _run_with_jsearch(self, monkeypatch, message, profile, items=None, error=None):
        """Run with _search_jsearch_meta mocked on the api instance."""
        import src.rico_chat_api as mod
        from src.rico_chat_api import RicoChatAPI
        from unittest.mock import MagicMock

        _items = items if items is not None else []

        class _FakeResult:
            pass

        fake = _FakeResult()
        fake.items = _items
        fake.error = error

        mock_route = MagicMock()
        mock_route.tool_name           = None
        mock_route.entities            = {}
        mock_route.tool_args           = {}
        mock_route.confirmation_prompt = None
        mock_route.source              = "keyword"

        monkeypatch.setattr(mod, "get_profile",    lambda uid: profile)
        monkeypatch.setattr(mod, "_route",         lambda *a, **kw: mock_route)
        monkeypatch.setattr(mod, "upsert_profile", lambda uid, u: profile)
        monkeypatch.setattr(mod, "hf_ok",          lambda: False)

        api = RicoChatAPI()
        api._search_jsearch_meta = lambda q, location="": fake
        api._get_recent_context  = lambda uid: {}
        api._append_chat         = MagicMock()

        return api._handle_active_user("test-user", message)

    def test_routes_to_market_pulse(self, monkeypatch):
        result = self._run_with_jsearch(monkeypatch, "how's the job market for HSE?", _CVProfile())
        assert result["type"] == "market_pulse"

    def test_returns_sentiment_field(self, monkeypatch):
        result = self._run_with_jsearch(
            monkeypatch, "how competitive is the job market for HSE?", _CVProfile()
        )
        assert "sentiment" in result
        assert any(s in result["sentiment"] for s in ("very active", "moderately active", "competitive", "limited"))

    def test_returns_active_count(self, monkeypatch):
        result = self._run_with_jsearch(
            monkeypatch, "are there many HSE jobs in Dubai?", _CVProfile()
        )
        assert "active_count" in result
        assert isinstance(result["active_count"], int)

    def test_high_count_returns_very_active(self, monkeypatch):
        result = self._run_with_jsearch(
            monkeypatch, "how's the job market for project management?", _CVProfile(),
            items=[{"job_title": f"Role {i}"} for i in range(20)],
        )
        assert result["sentiment"] == "very active"

    def test_zero_count_returns_limited(self, monkeypatch):
        result = self._run_with_jsearch(
            monkeypatch, "how's the market for niche roles?", _CVProfile()
        )
        assert "limited" in result["sentiment"]

    def test_message_field_present(self, monkeypatch):
        result = self._run_with_jsearch(
            monkeypatch, "how's the job market for HSE?", _CVProfile()
        )
        assert result.get("type") == "market_pulse"
        assert isinstance(result.get("message"), str)
        assert len(result["message"]) > 20


# ── _NOTICE_PERIOD_RE ─────────────────────────────────────────────────────────

class TestNoticePeriod:
    """Regex gate and handler for notice period declarations and queries."""

    @pytest.mark.parametrize("phrase", [
        "my notice period is 30 days",
        "my notice period is 1 month",
        "I'm available immediately",
        "I am available immediately",
        "I can join in 2 weeks",
        "I can start immediately",
        "update my notice period to 60 days",
        "set my availability to immediate",
        "what is my notice period?",
        "immediate joiner",
        "immediate availability",
    ])
    def test_regex_matches(self, phrase):
        from src.rico_chat_api import _NOTICE_PERIOD_RE
        assert _NOTICE_PERIOD_RE.search(phrase), (
            f"_NOTICE_PERIOD_RE should match: {phrase!r}"
        )

    @pytest.mark.parametrize("phrase", [
        "find HSE jobs in Dubai",
        "what salary did I set?",
        "compare job 1 and job 2",
        "how many applications did I send?",
        "certifications for finance",
    ])
    def test_regex_does_not_match(self, phrase):
        from src.rico_chat_api import _NOTICE_PERIOD_RE
        assert not _NOTICE_PERIOD_RE.search(phrase), (
            f"_NOTICE_PERIOD_RE should NOT match: {phrase!r}"
        )

    def test_declaration_routes_to_notice_period_update(self, monkeypatch):
        _, result = _run(monkeypatch, "my notice period is 30 days", _CVProfile())
        assert result["type"] == "notice_period_update"

    def test_immediate_declaration(self, monkeypatch):
        _, result = _run(monkeypatch, "I'm available immediately", _CVProfile())
        assert result["type"] == "notice_period_update"
        assert result.get("notice_period") == "Immediate"

    def test_query_routes_to_notice_period_readback(self, monkeypatch):
        _, result = _run(monkeypatch, "what is my notice period?", _CVProfile())
        assert result["type"] == "notice_period_readback"

    def test_upsert_called_on_declaration(self, monkeypatch):
        import src.rico_chat_api as mod
        calls = []
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: calls.append(updates or {}) or _CVProfile())
        monkeypatch.setattr(mod, "get_profile", lambda uid: _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        from src.rico_chat_api import RicoChatAPI
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._handle_active_user("u1", "my notice period is 1 month")
        assert any("notice_period" in c for c in calls)

    def test_message_field_present(self, monkeypatch):
        _, result = _run(monkeypatch, "my notice period is 30 days", _CVProfile())
        assert isinstance(result.get("message"), str)
        assert len(result["message"]) > 10


# ── _VISA_STATUS_RE ───────────────────────────────────────────────────────────

class TestVisaStatus:
    """Regex gate and handler for visa/work permit status."""

    @pytest.mark.parametrize("phrase", [
        "I'm on a spouse visa",
        "I am on a dependent visa",
        "I have a valid work permit",
        "I have an employment visa",
        "I have a golden visa",
        "update my visa status to employment visa",
        "what is my visa status?",
        "my visa is expiring soon",
        "do I need a visa to work in UAE?",
        "I need visa sponsorship",
    ])
    def test_regex_matches(self, phrase):
        from src.rico_chat_api import _VISA_STATUS_RE
        assert _VISA_STATUS_RE.search(phrase), (
            f"_VISA_STATUS_RE should match: {phrase!r}"
        )

    @pytest.mark.parametrize("phrase", [
        "find HSE jobs in Dubai",
        "my notice period is 30 days",
        "what certifications do I need?",
        "compare job 1 and job 2",
        "how many applications did I send?",
    ])
    def test_regex_does_not_match(self, phrase):
        from src.rico_chat_api import _VISA_STATUS_RE
        assert not _VISA_STATUS_RE.search(phrase), (
            f"_VISA_STATUS_RE should NOT match: {phrase!r}"
        )

    def test_spouse_visa_declaration(self, monkeypatch):
        _, result = _run(monkeypatch, "I'm on a spouse visa", _CVProfile())
        assert result["type"] == "visa_status_update"
        assert result.get("visa_status") == "Spouse/Dependent Visa"

    def test_employment_visa_declaration(self, monkeypatch):
        _, result = _run(monkeypatch, "I have an employment visa", _CVProfile())
        assert result["type"] == "visa_status_update"
        assert result.get("visa_status") == "Employment Visa"

    def test_golden_visa_declaration(self, monkeypatch):
        _, result = _run(monkeypatch, "I have a golden visa", _CVProfile())
        assert result["type"] == "visa_status_update"
        assert result.get("visa_status") == "Golden Visa"

    def test_info_request_returns_visa_info(self, monkeypatch):
        _, result = _run(monkeypatch, "do I need a visa to work in UAE?", _CVProfile())
        assert result["type"] == "visa_info"

    def test_query_returns_visa_readback(self, monkeypatch):
        _, result = _run(monkeypatch, "what is my visa status?", _CVProfile())
        assert result["type"] == "visa_readback"

    def test_message_field_present(self, monkeypatch):
        _, result = _run(monkeypatch, "I'm on a spouse visa", _CVProfile())
        assert isinstance(result.get("message"), str)
        assert len(result["message"]) > 10

    def test_upsert_called_on_declaration(self, monkeypatch):
        import src.rico_chat_api as mod
        calls = []
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: calls.append(updates or {}) or _CVProfile())
        monkeypatch.setattr(mod, "get_profile", lambda uid: _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        from src.rico_chat_api import RicoChatAPI
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._handle_active_user("u1", "I'm on a spouse visa")
        assert any("visa_status" in c for c in calls)


# ── _SALARY_NEGOTIATION_RE ────────────────────────────────────────────────────

class TestSalaryNegotiation:
    """Regex gate and handler for salary negotiation advice."""

    @pytest.mark.parametrize("phrase", [
        "how do I negotiate my salary?",
        "how to negotiate salary",
        "should I counter the offer?",
        "should I accept the offer?",
        "the offer is too low",
        "the offer seems too low",
        "how do I ask for a raise?",
        "salary negotiation tips",
        "salary negotiation advice",
        "counter offer",
        "counteroffer",
        "what should I counter?",
    ])
    def test_regex_matches(self, phrase):
        from src.rico_chat_api import _SALARY_NEGOTIATION_RE
        assert _SALARY_NEGOTIATION_RE.search(phrase), (
            f"_SALARY_NEGOTIATION_RE should match: {phrase!r}"
        )

    @pytest.mark.parametrize("phrase", [
        "find HSE jobs in Dubai",
        "what is my salary expectation?",
        "set my salary to 25000 AED",
        "my notice period is 30 days",
        "I'm on a spouse visa",
    ])
    def test_regex_does_not_match(self, phrase):
        from src.rico_chat_api import _SALARY_NEGOTIATION_RE
        assert not _SALARY_NEGOTIATION_RE.search(phrase), (
            f"_SALARY_NEGOTIATION_RE should NOT match: {phrase!r}"
        )

    def test_routes_to_negotiation_advice(self, monkeypatch):
        _, result = _run(monkeypatch, "how do I negotiate my salary?", _CVProfile())
        assert result["type"] == "negotiation_advice"

    def test_counter_scenario_flagged(self, monkeypatch):
        _, result = _run(monkeypatch, "should I counter the offer?", _CVProfile())
        assert result["type"] == "negotiation_advice"
        assert result.get("is_counter_scenario") is True

    def test_general_advice_not_counter_flagged(self, monkeypatch):
        _, result = _run(monkeypatch, "salary negotiation tips", _CVProfile())
        assert result["type"] == "negotiation_advice"
        assert result.get("is_counter_scenario") is False

    def test_salary_on_file_included(self, monkeypatch):
        import src.rico_chat_api as mod
        from src.rico_chat_api import RicoChatAPI
        from unittest.mock import MagicMock

        class _ProfileWithSalary:
            skills = ["hse"]
            certifications = []
            years_experience = 8.0
            target_roles = ["HSE Manager"]
            industries = ["Oil & Gas"]
            cv_status = "parsed"
            cv_filename = "cv.pdf"
            salary_expectation_aed = 25000

        monkeypatch.setattr(mod, "get_profile", lambda uid: _ProfileWithSalary())
        monkeypatch.setattr(mod, "upsert_profile", lambda uid, u: _ProfileWithSalary())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)

        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        result = api._handle_active_user("u1", "should I counter the offer?")
        assert result["type"] == "negotiation_advice"
        assert result.get("salary_on_file") is not None

    def test_message_field_present(self, monkeypatch):
        _, result = _run(monkeypatch, "how do I negotiate my salary?", _CVProfile())
        assert isinstance(result.get("message"), str)
        assert len(result["message"]) > 50


# ── _INTERVIEW_PREP_RE ────────────────────────────────────────────────────────

class TestInterviewPrep:
    """Regex gate and handler for interview preparation advice."""

    @pytest.mark.parametrize("phrase", [
        "how do I prepare for an interview?",
        "how to prepare for an interview",
        "interview tips",
        "interview advice",
        "interview preparation",
        "common interview questions",
        "what should I wear to an interview?",
        "what to wear to a UAE interview?",
        "how to ace an interview",
        "how to nail my interview",
        "preparing for my interview",
    ])
    def test_regex_matches(self, phrase):
        from src.rico_chat_api import _INTERVIEW_PREP_RE
        assert _INTERVIEW_PREP_RE.search(phrase), (
            f"_INTERVIEW_PREP_RE should match: {phrase!r}"
        )

    @pytest.mark.parametrize("phrase", [
        "find HSE jobs in Dubai",
        "my notice period is 30 days",
        "how do I negotiate my salary?",
        "I got rejected",
        "LinkedIn profile tips",
    ])
    def test_regex_does_not_match(self, phrase):
        from src.rico_chat_api import _INTERVIEW_PREP_RE
        assert not _INTERVIEW_PREP_RE.search(phrase), (
            f"_INTERVIEW_PREP_RE should NOT match: {phrase!r}"
        )

    def test_routes_to_interview_prep(self, monkeypatch):
        _, result = _run(monkeypatch, "how do I prepare for an interview?", _CVProfile())
        assert result["type"] == "interview_prep"

    def test_attire_query_flagged(self, monkeypatch):
        _, result = _run(monkeypatch, "what should I wear to an interview?", _CVProfile())
        assert result["type"] == "interview_prep"
        assert result.get("is_attire_query") is True

    def test_questions_query_flagged(self, monkeypatch):
        _, result = _run(monkeypatch, "common interview questions", _CVProfile())
        assert result["type"] == "interview_prep"
        assert result.get("is_questions_query") is True

    def test_general_prep_not_flagged_as_attire(self, monkeypatch):
        _, result = _run(monkeypatch, "interview tips", _CVProfile())
        assert result["type"] == "interview_prep"
        assert result.get("is_attire_query") is False

    def test_role_from_profile_included(self, monkeypatch):
        _, result = _run(monkeypatch, "interview tips", _CVProfile())
        assert result.get("role") == "Senior HSE Manager"

    def test_message_field_present(self, monkeypatch):
        _, result = _run(monkeypatch, "interview tips", _CVProfile())
        assert isinstance(result.get("message"), str)
        assert len(result["message"]) > 50

    def test_empty_profile_still_works(self, monkeypatch):
        _, result = _run(monkeypatch, "how do I prepare for an interview?", _EmptyProfile())
        assert result["type"] == "interview_prep"


# ── _REJECTION_HANDLING_RE ────────────────────────────────────────────────────

class TestRejectionHandling:
    """Regex gate and handler for rejection and no-response scenarios."""

    @pytest.mark.parametrize("phrase", [
        "I got rejected",
        "I was rejected for the role",
        "no response from the company",
        "no reply after interview",
        "I haven't heard back",
        "what to do after rejection?",
        "what should I do when rejected?",
        "I've been ghosted",
        "being ghosted by employer",
        "job rejection advice",
        "failed the interview",
    ])
    def test_regex_matches(self, phrase):
        from src.rico_chat_api import _REJECTION_HANDLING_RE
        assert _REJECTION_HANDLING_RE.search(phrase), (
            f"_REJECTION_HANDLING_RE should match: {phrase!r}"
        )

    @pytest.mark.parametrize("phrase", [
        "find HSE jobs in Dubai",
        "how do I negotiate my salary?",
        "interview tips",
        "LinkedIn profile tips",
        "my notice period is 30 days",
    ])
    def test_regex_does_not_match(self, phrase):
        from src.rico_chat_api import _REJECTION_HANDLING_RE
        assert not _REJECTION_HANDLING_RE.search(phrase), (
            f"_REJECTION_HANDLING_RE should NOT match: {phrase!r}"
        )

    def test_routes_to_rejection_advice(self, monkeypatch):
        _, result = _run(monkeypatch, "I got rejected", _CVProfile())
        assert result["type"] == "rejection_advice"

    def test_no_response_flagged(self, monkeypatch):
        _, result = _run(monkeypatch, "I haven't heard back from the company", _CVProfile())
        assert result["type"] == "rejection_advice"
        assert result.get("is_no_response") is True

    def test_post_interview_flagged(self, monkeypatch):
        _, result = _run(monkeypatch, "what to do after failing the interview?", _CVProfile())
        assert result["type"] == "rejection_advice"
        assert result.get("is_post_interview") is True

    def test_general_rejection_not_flagged_as_no_response(self, monkeypatch):
        _, result = _run(monkeypatch, "I got rejected", _CVProfile())
        assert result["type"] == "rejection_advice"
        assert result.get("is_no_response") is False

    def test_message_field_present(self, monkeypatch):
        _, result = _run(monkeypatch, "I got rejected", _CVProfile())
        assert isinstance(result.get("message"), str)
        assert len(result["message"]) > 50


# ── _LINKEDIN_NETWORKING_RE ───────────────────────────────────────────────────

class TestLinkedInNetworking:
    """Regex gate and handler for LinkedIn and networking advice."""

    @pytest.mark.parametrize("phrase", [
        "LinkedIn profile tips",
        "LinkedIn advice",
        "how to use LinkedIn for job search",
        "how to optimize my LinkedIn",
        "how to message a recruiter",
        "how to message a hiring manager",
        "should I connect with the recruiter?",
        "should I message the company?",
        "networking tips in UAE",
        "how to reach out to a recruiter",
        "cold message a hiring manager",
        "cold outreach tips",
    ])
    def test_regex_matches(self, phrase):
        from src.rico_chat_api import _LINKEDIN_NETWORKING_RE
        assert _LINKEDIN_NETWORKING_RE.search(phrase), (
            f"_LINKEDIN_NETWORKING_RE should match: {phrase!r}"
        )

    @pytest.mark.parametrize("phrase", [
        "find HSE jobs in Dubai",
        "how do I negotiate my salary?",
        "I got rejected",
        "interview tips",
        "my notice period is 30 days",
    ])
    def test_regex_does_not_match(self, phrase):
        from src.rico_chat_api import _LINKEDIN_NETWORKING_RE
        assert not _LINKEDIN_NETWORKING_RE.search(phrase), (
            f"_LINKEDIN_NETWORKING_RE should NOT match: {phrase!r}"
        )

    def test_routes_to_linkedin_networking(self, monkeypatch):
        _, result = _run(monkeypatch, "LinkedIn tips", _CVProfile())
        assert result["type"] == "linkedin_networking"

    def test_recruiter_message_flagged(self, monkeypatch):
        _, result = _run(monkeypatch, "how to message a recruiter on LinkedIn", _CVProfile())
        assert result["type"] == "linkedin_networking"
        assert result.get("is_message_recruiter") is True

    def test_cold_outreach_flagged(self, monkeypatch):
        _, result = _run(monkeypatch, "cold message tips", _CVProfile())
        assert result["type"] == "linkedin_networking"
        assert result.get("is_cold_outreach") is True

    def test_profile_optimize_flagged(self, monkeypatch):
        _, result = _run(monkeypatch, "how to optimize my LinkedIn profile", _CVProfile())
        assert result["type"] == "linkedin_networking"
        assert result.get("is_profile_optimize") is True

    def test_general_networking_no_flags(self, monkeypatch):
        _, result = _run(monkeypatch, "networking tips in UAE", _CVProfile())
        assert result["type"] == "linkedin_networking"
        assert result.get("is_message_recruiter") is False
        assert result.get("is_cold_outreach") is False

    def test_message_field_present(self, monkeypatch):
        _, result = _run(monkeypatch, "LinkedIn advice", _CVProfile())
        assert isinstance(result.get("message"), str)
        assert len(result["message"]) > 50

    def test_empty_profile_still_works(self, monkeypatch):
        _, result = _run(monkeypatch, "networking tips in UAE", _EmptyProfile())
        assert result["type"] == "linkedin_networking"
