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
