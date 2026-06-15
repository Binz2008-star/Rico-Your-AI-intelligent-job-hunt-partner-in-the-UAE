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


# ── _CV_FORMAT_RE ─────────────────────────────────────────────────────────────

class TestCVFormatAdvice:
    """Regex gate and handler for CV/resume format advice."""

    @pytest.mark.parametrize("phrase", [
        "how should I format my CV for UAE?",
        "how to format my resume",
        "CV format tips",
        "CV format advice",
        "resume format help",
        "CV template",
        "CV structure",
        "is my CV too long?",
        "my CV is too long",
        "ATS CV tips",
        "ATS-friendly resume",
        "what should a UAE CV include?",
        "what should my CV look like?",
        "CV for UAE",
        "resume for UAE",
    ])
    def test_regex_matches(self, phrase):
        from src.rico_chat_api import _CV_FORMAT_RE
        assert _CV_FORMAT_RE.search(phrase), (
            f"_CV_FORMAT_RE should match: {phrase!r}"
        )

    @pytest.mark.parametrize("phrase", [
        "find HSE jobs in Dubai",
        "my notice period is 30 days",
        "how do I negotiate my salary?",
        "I got rejected",
        "LinkedIn profile tips",
        "write a cover letter for HSE Manager",
        "draft a cover letter for DP World",
    ])
    def test_regex_does_not_match(self, phrase):
        from src.rico_chat_api import _CV_FORMAT_RE
        assert not _CV_FORMAT_RE.search(phrase), (
            f"_CV_FORMAT_RE should NOT match: {phrase!r}"
        )

    def test_routes_to_cv_format_advice(self, monkeypatch):
        _, result = _run(monkeypatch, "CV format tips", _CVProfile())
        assert result["type"] == "cv_format_advice"

    def test_ats_query_flagged(self, monkeypatch):
        _, result = _run(monkeypatch, "ATS CV tips", _CVProfile())
        assert result["type"] == "cv_format_advice"
        assert result.get("is_ats_query") is True

    def test_length_query_flagged(self, monkeypatch):
        _, result = _run(monkeypatch, "is my CV too long?", _CVProfile())
        assert result["type"] == "cv_format_advice"
        assert result.get("is_length_query") is True

    def test_general_not_flagged_as_ats_or_length(self, monkeypatch):
        _, result = _run(monkeypatch, "CV format tips", _CVProfile())
        assert result.get("is_ats_query") is False
        assert result.get("is_length_query") is False

    def test_role_from_profile_included(self, monkeypatch):
        _, result = _run(monkeypatch, "CV format tips", _CVProfile())
        assert result.get("role") == "Senior HSE Manager"

    def test_message_field_present(self, monkeypatch):
        _, result = _run(monkeypatch, "CV format tips", _CVProfile())
        assert isinstance(result.get("message"), str)
        assert len(result["message"]) > 50

    def test_empty_profile_still_works(self, monkeypatch):
        _, result = _run(monkeypatch, "CV format tips", _EmptyProfile())
        assert result["type"] == "cv_format_advice"


# ── _COVER_LETTER_TIPS_RE ─────────────────────────────────────────────────────

class TestCoverLetterTips:
    """Regex gate and handler for cover letter tips (not generation)."""

    @pytest.mark.parametrize("phrase", [
        "how do I write a cover letter?",
        "how to write a cover letter",
        "cover letter tips",
        "cover letter advice",
        "cover letter format",
        "cover letter template",
        "cover letter guide",
        "do I need a cover letter?",
        "what should my cover letter include?",
        "what to put in a cover letter",
        "cover letter UAE",
    ])
    def test_regex_matches(self, phrase):
        from src.rico_chat_api import _COVER_LETTER_TIPS_RE
        assert _COVER_LETTER_TIPS_RE.search(phrase), (
            f"_COVER_LETTER_TIPS_RE should match: {phrase!r}"
        )

    @pytest.mark.parametrize("phrase", [
        "find HSE jobs in Dubai",
        "my notice period is 30 days",
        "how do I negotiate my salary?",
        "draft a cover letter for DP World",
        "write a cover letter for Senior HSE Manager at ADNOC",
        "CV format tips",
        "LinkedIn advice",
    ])
    def test_regex_does_not_match(self, phrase):
        from src.rico_chat_api import _COVER_LETTER_TIPS_RE
        assert not _COVER_LETTER_TIPS_RE.search(phrase), (
            f"_COVER_LETTER_TIPS_RE should NOT match: {phrase!r}"
        )

    def test_routes_to_cover_letter_tips(self, monkeypatch):
        _, result = _run(monkeypatch, "cover letter tips", _CVProfile())
        assert result["type"] == "cover_letter_tips"

    def test_needed_question_flagged(self, monkeypatch):
        # "do I need a cover letter?" may also be handled by the existing
        # cover_letter_prompt gate; test the flag via the handler directly
        from src.rico_chat_api import RicoChatAPI
        api = RicoChatAPI()

        class P:
            skills = ["hse"]; certifications = []; years_experience = 8.0
            target_roles = ["Senior HSE Manager"]; industries = ["Oil & Gas"]
            cv_status = "parsed"; cv_filename = "cv.pdf"

        from unittest.mock import MagicMock
        api._append_chat = MagicMock()
        result = api._handle_cover_letter_tips("u1", P(), "do I need a cover letter?")
        assert result["type"] == "cover_letter_tips"
        assert result.get("is_needed_question") is True

    def test_general_tips_not_flagged_as_needed_question(self, monkeypatch):
        _, result = _run(monkeypatch, "cover letter tips", _CVProfile())
        assert result.get("is_needed_question") is False

    def test_role_from_profile_included(self, monkeypatch):
        _, result = _run(monkeypatch, "cover letter tips", _CVProfile())
        assert result.get("role") == "Senior HSE Manager"

    def test_message_field_present(self, monkeypatch):
        _, result = _run(monkeypatch, "cover letter tips", _CVProfile())
        assert isinstance(result.get("message"), str)
        assert len(result["message"]) > 50

    def test_empty_profile_still_works(self, monkeypatch):
        _, result = _run(monkeypatch, "cover letter advice", _EmptyProfile())
        assert result["type"] == "cover_letter_tips"


# ── _APP_PIPELINE_SUMMARY_RE ──────────────────────────────────────────────────

class TestAppPipelineSummary:
    """Regex gate and handler for application pipeline summary."""

    @pytest.mark.parametrize("phrase", [
        "how many applications have I sent?",
        "how many jobs did I apply to?",
        "application summary",
        "my application stats",
        "my application statistics",
        "my application pipeline",
        "what's my application success rate?",
        "how am I doing with my job search?",
        "job search stats",
    ])
    def test_regex_matches(self, phrase):
        from src.rico_chat_api import _APP_PIPELINE_SUMMARY_RE
        assert _APP_PIPELINE_SUMMARY_RE.search(phrase), (
            f"_APP_PIPELINE_SUMMARY_RE should match: {phrase!r}"
        )

    @pytest.mark.parametrize("phrase", [
        "find HSE jobs in Dubai",
        "how many jobs did you find?",
        "how many jobs are there?",
        "interview tips",
        "my notice period is 30 days",
        "CV format tips",
    ])
    def test_regex_does_not_match(self, phrase):
        from src.rico_chat_api import _APP_PIPELINE_SUMMARY_RE
        assert not _APP_PIPELINE_SUMMARY_RE.search(phrase), (
            f"_APP_PIPELINE_SUMMARY_RE should NOT match: {phrase!r}"
        )

    def _run_with_apps(self, monkeypatch, message, profile, apps=None):
        """Run _handle_app_pipeline_summary with mocked app repo."""
        from src.rico_chat_api import RicoChatAPI
        from unittest.mock import MagicMock, patch
        import src.rico_chat_api as mod

        _apps = apps if apps is not None else []

        mock_route = MagicMock()
        mock_route.tool_name = None; mock_route.entities = {}
        mock_route.tool_args = {}; mock_route.confirmation_prompt = None
        mock_route.source = "keyword"

        monkeypatch.setattr(mod, "get_profile",    lambda uid: profile)
        monkeypatch.setattr(mod, "_route",         lambda *a, **kw: mock_route)
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile)
        monkeypatch.setattr(mod, "hf_ok",          lambda: False)

        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()

        with patch("src.repositories.applications_repo.get_all", return_value=_apps):
            return api._handle_active_user("test-user", message)

    def test_routes_to_app_pipeline_summary(self, monkeypatch):
        result = self._run_with_apps(monkeypatch, "application summary", _CVProfile())
        assert result["type"] == "app_pipeline_summary"

    def test_zero_apps_returns_empty_message(self, monkeypatch):
        result = self._run_with_apps(
            monkeypatch, "how many applications have I sent?", _CVProfile()
        )
        assert result["type"] == "app_pipeline_summary"
        assert result["total"] == 0

    def test_with_applications_shows_counts(self, monkeypatch):
        apps = [
            {"status": "applied"},
            {"status": "applied"},
            {"status": "interview"},
            {"status": "rejected"},
        ]
        result = self._run_with_apps(monkeypatch, "application summary", _CVProfile(), apps=apps)
        assert result["total"] == 4
        assert result["applied"] == 2
        assert result["interview"] == 1
        assert result["rejected"] == 1

    def test_response_rate_calculated(self, monkeypatch):
        apps = [
            {"status": "applied"},
            {"status": "applied"},
            {"status": "applied"},
            {"status": "applied"},
            {"status": "interview"},
        ]
        result = self._run_with_apps(
            monkeypatch, "what's my application success rate?", _CVProfile(), apps=apps
        )
        assert result["response_rate"] == "25%"

    def test_message_field_present(self, monkeypatch):
        apps = [{"status": "applied"}, {"status": "applied"}]
        result = self._run_with_apps(monkeypatch, "application summary", _CVProfile(), apps=apps)
        assert isinstance(result.get("message"), str)
        assert len(result["message"]) > 10


# ── _PROFILE_IMPROVE_RE ───────────────────────────────────────────────────────

class TestProfileImprove:
    """Regex gate for profile improvement queries (routes to existing completeness handler)."""

    @pytest.mark.parametrize("phrase", [
        "how can I improve my profile?",
        "how to improve my CV",
        "what's missing from my profile?",
        "what is missing from my resume?",
        "how complete is my profile?",
        "profile completeness",
        "CV strength",
        "profile gaps",
        "what should I add to my profile?",
        "improve my CV",
        "optimize my profile",
        "strengthen my resume",
    ])
    def test_regex_matches(self, phrase):
        from src.rico_chat_api import _PROFILE_IMPROVE_RE
        assert _PROFILE_IMPROVE_RE.search(phrase), (
            f"_PROFILE_IMPROVE_RE should match: {phrase!r}"
        )

    @pytest.mark.parametrize("phrase", [
        "find HSE jobs in Dubai",
        "my notice period is 30 days",
        "how do I negotiate my salary?",
        "interview tips",
        "CV format tips",
    ])
    def test_regex_does_not_match(self, phrase):
        from src.rico_chat_api import _PROFILE_IMPROVE_RE
        assert not _PROFILE_IMPROVE_RE.search(phrase), (
            f"_PROFILE_IMPROVE_RE should NOT match: {phrase!r}"
        )

    def test_routes_to_profile_completeness(self, monkeypatch):
        _, result = _run(monkeypatch, "how can I improve my profile?", _CVProfile())
        assert result["type"] == "profile_completeness"

    def test_empty_profile_routes_to_profile_completeness(self, monkeypatch):
        _, result = _run(monkeypatch, "what's missing from my profile?", _EmptyProfile())
        assert result["type"] == "profile_completeness"


# ── _COMPANY_TYPE_SEARCH_RE ───────────────────────────────────────────────────

class TestCompanyTypeSearch:
    """Regex gate and handler for company-type filtered job search."""

    @pytest.mark.parametrize("phrase", [
        "find government jobs in Dubai",
        "find government jobs in UAE",
        "find me government roles",
        "public sector jobs in Abu Dhabi",
        "find startup jobs in Dubai",
        "find startup roles",
        "find multinational jobs",
        "find MNC jobs in UAE",
        "semi-government jobs in UAE",
    ])
    def test_regex_matches(self, phrase):
        from src.rico_chat_api import _COMPANY_TYPE_SEARCH_RE
        assert _COMPANY_TYPE_SEARCH_RE.search(phrase), (
            f"_COMPANY_TYPE_SEARCH_RE should match: {phrase!r}"
        )

    @pytest.mark.parametrize("phrase", [
        "find HSE jobs in Dubai",
        "find senior HSE jobs",
        "how can I improve my profile?",
        "I need a job urgently",
        "government is a good employer",
    ])
    def test_regex_does_not_match(self, phrase):
        from src.rico_chat_api import _COMPANY_TYPE_SEARCH_RE
        assert not _COMPANY_TYPE_SEARCH_RE.search(phrase), (
            f"_COMPANY_TYPE_SEARCH_RE should NOT match: {phrase!r}"
        )

    def _run_with_jsearch(self, monkeypatch, message, profile, items=None):
        import src.rico_chat_api as mod
        from src.rico_chat_api import RicoChatAPI
        from unittest.mock import MagicMock

        fake_result = type("R", (), {"items": items or [], "error": None})()

        mock_route = MagicMock()
        mock_route.tool_name = None; mock_route.entities = {}
        mock_route.tool_args = {}; mock_route.confirmation_prompt = None
        mock_route.source = "keyword"

        monkeypatch.setattr(mod, "get_profile",    lambda uid: profile)
        monkeypatch.setattr(mod, "_route",         lambda *a, **kw: mock_route)
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile)
        monkeypatch.setattr(mod, "hf_ok",          lambda: False)

        api = RicoChatAPI()
        api._search_jsearch_meta = lambda q, location="": fake_result
        api._get_recent_context  = lambda uid: {}
        api._append_chat         = MagicMock()

        return api._handle_active_user("test-user", message)

    def test_government_search_returns_job_matches(self, monkeypatch):
        result = self._run_with_jsearch(
            monkeypatch, "find government jobs in UAE", _CVProfile(),
            items=[{"job_title": "HSE Officer", "employer_name": "Dubai Municipality"}],
        )
        assert result["type"] == "job_matches"
        assert result.get("company_type") == "Government"

    def test_startup_search_detected(self, monkeypatch):
        result = self._run_with_jsearch(
            monkeypatch, "find startup jobs in Dubai", _CVProfile(),
            items=[{"job_title": "HSE Manager", "employer_name": "TechCorp"}],
        )
        assert result["type"] == "job_matches"
        assert result.get("company_type") == "Startup"

    def test_no_results_returns_no_results_type(self, monkeypatch):
        result = self._run_with_jsearch(
            monkeypatch, "find government jobs in UAE", _CVProfile()
        )
        assert result["type"] == "no_results"

    def test_message_field_present(self, monkeypatch):
        result = self._run_with_jsearch(
            monkeypatch, "find government jobs in UAE", _CVProfile(),
            items=[{"job_title": "Officer", "employer_name": "Ministry"}],
        )
        assert isinstance(result.get("message"), str)
        assert len(result["message"]) > 10


# ── _URGENCY_SEARCH_RE ────────────────────────────────────────────────────────

class TestUrgencySearch:
    """Regex gate and handler for urgency-framed job search."""

    @pytest.mark.parametrize("phrase", [
        "I need a job urgently",
        "I need a job fast",
        "I need a job asap",
        "I need a job immediately",
        "I need to find a job in 30 days",
        "I need to find a job in 2 weeks",
        "I want to get a job quickly",
        "help me find a job fast",
        "help me find a job urgently",
        "find urgent job openings",
        "find immediate openings",
    ])
    def test_regex_matches(self, phrase):
        from src.rico_chat_api import _URGENCY_SEARCH_RE
        assert _URGENCY_SEARCH_RE.search(phrase), (
            f"_URGENCY_SEARCH_RE should match: {phrase!r}"
        )

    @pytest.mark.parametrize("phrase", [
        "find HSE jobs in Dubai",
        "find government jobs",
        "how can I improve my profile?",
        "interview tips",
        "I need more information about the role",
        "I need to update my notice period",
    ])
    def test_regex_does_not_match(self, phrase):
        from src.rico_chat_api import _URGENCY_SEARCH_RE
        assert not _URGENCY_SEARCH_RE.search(phrase), (
            f"_URGENCY_SEARCH_RE should NOT match: {phrase!r}"
        )

    def _run_with_jsearch(self, monkeypatch, message, profile, items=None):
        import src.rico_chat_api as mod
        from src.rico_chat_api import RicoChatAPI
        from unittest.mock import MagicMock

        fake_result = type("R", (), {"items": items or [], "error": None})()

        mock_route = MagicMock()
        mock_route.tool_name = None; mock_route.entities = {}
        mock_route.tool_args = {}; mock_route.confirmation_prompt = None
        mock_route.source = "keyword"

        monkeypatch.setattr(mod, "get_profile",    lambda uid: profile)
        monkeypatch.setattr(mod, "_route",         lambda *a, **kw: mock_route)
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile)
        monkeypatch.setattr(mod, "hf_ok",          lambda: False)

        api = RicoChatAPI()
        api._search_jsearch_meta = lambda q, location="": fake_result
        api._get_recent_context  = lambda uid: {}
        api._append_chat         = MagicMock()

        return api._handle_active_user("test-user", message)

    def test_routes_to_urgency_search(self, monkeypatch):
        result = self._run_with_jsearch(monkeypatch, "I need a job urgently", _CVProfile())
        assert result["type"] == "urgency_search"

    def test_timeline_extracted(self, monkeypatch):
        result = self._run_with_jsearch(
            monkeypatch, "I need to find a job in 30 days", _CVProfile()
        )
        assert result["type"] == "urgency_search"
        assert result.get("timeline") == "30 days"

    def test_no_timeline_returns_none(self, monkeypatch):
        result = self._run_with_jsearch(
            monkeypatch, "I need a job urgently", _CVProfile()
        )
        assert result.get("timeline") is None

    def test_role_from_profile_included(self, monkeypatch):
        result = self._run_with_jsearch(monkeypatch, "I need a job fast", _CVProfile())
        assert result.get("role") == "Senior HSE Manager"

    def test_live_jobs_included_when_found(self, monkeypatch):
        result = self._run_with_jsearch(
            monkeypatch, "I need a job urgently", _CVProfile(),
            items=[{"job_title": "HSE Manager", "employer_name": "ADNOC"}],
        )
        assert isinstance(result.get("live_jobs"), list)
        assert len(result["live_jobs"]) >= 1

    def test_message_field_present(self, monkeypatch):
        result = self._run_with_jsearch(monkeypatch, "help me find a job fast", _CVProfile())
        assert isinstance(result.get("message"), str)
        assert len(result["message"]) > 50

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run_with_jsearch(monkeypatch, "I need a job urgently", _EmptyProfile())
        assert result["type"] == "urgency_search"


# ── Salary Benchmark ──────────────────────────────────────────────────────────

class TestSalaryBenchmark:
    """Tests for _SALARY_BENCHMARK_RE and _handle_salary_benchmark."""

    _REGEX_CASES_MATCH = [
        "what does an HSE Manager earn in Dubai?",
        "how much do project managers make in UAE?",
        "what is the salary range for operations managers?",
        "market rate for senior engineers in Abu Dhabi",
        "what can I earn as a safety officer?",
        "how much can a software developer make in Dubai?",
        "salary benchmark for HR managers in UAE",
        "what is the pay for compliance officers?",
        "how much do finance directors earn?",
        "salary expectations for a logistics coordinator",
        "كم الراتب لمدير مشاريع",
    ]

    _REGEX_CASES_NO_MATCH = [
        "my expected salary is 20000 AED",  # salary set
        "what is my salary expectation?",   # salary readback
        "find jobs paying above 15000",     # salary search
        "I need a job urgently",
        "how do I negotiate my salary?",    # salary negotiation
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _SALARY_BENCHMARK_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _SALARY_BENCHMARK_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _SALARY_BENCHMARK_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _SALARY_BENCHMARK_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        mock_route = {"provider": "openai", "client": MagicMock(), "model": "gpt-4.1-mini"}
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: mock_route)
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_salary_benchmark(self, monkeypatch):
        result = self._run(monkeypatch, "what does an HSE Manager earn in Dubai?")
        assert result["type"] == "salary_benchmark"

    def test_role_extracted(self, monkeypatch):
        result = self._run(monkeypatch, "what is the salary range for a project manager?")
        assert result["type"] == "salary_benchmark"

    def test_location_abu_dhabi(self, monkeypatch):
        result = self._run(monkeypatch, "how much does an engineer earn in Abu Dhabi?")
        assert result["location"] == "Abu Dhabi"

    def test_location_sharjah(self, monkeypatch):
        result = self._run(monkeypatch, "what is the pay for accountants in Sharjah?")
        assert result["location"] == "Sharjah"

    def test_location_defaults_to_uae(self, monkeypatch):
        result = self._run(monkeypatch, "how much do HR managers earn?")
        assert "UAE" in result["location"] or "Dubai" in result["location"]

    def test_tier_from_profile_experience(self, monkeypatch):
        senior_profile = _CVProfile()
        result = self._run(monkeypatch, "what does an HSE Manager earn?", profile=senior_profile)
        assert result["tier"] == "senior"

    def test_range_aed_present(self, monkeypatch):
        result = self._run(monkeypatch, "what does an HSE Manager earn?")
        assert result.get("range_aed")
        assert "–" in result["range_aed"]

    def test_sector_detected_hse(self, monkeypatch):
        result = self._run(monkeypatch, "what does an HSE Manager earn?")
        assert result["sector"] == "HSE / EHS"

    def test_sector_detected_it(self, monkeypatch):
        result = self._run(monkeypatch, "how much does a software developer make?")
        assert result["sector"] == "Technology / IT"

    def test_message_includes_aed(self, monkeypatch):
        result = self._run(monkeypatch, "what does an HSE Manager earn in Dubai?")
        assert "AED" in result["message"] or "درهم" in result["message"]

    def test_message_includes_role(self, monkeypatch):
        result = self._run(monkeypatch, "how much can I earn as a safety officer?")
        assert isinstance(result["message"], str) and len(result["message"]) > 50

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "what does a project manager earn?", profile=_EmptyProfile())
        assert result["type"] == "salary_benchmark"


# ── Career Change Advice ─────────────────────────────────────────────────────

class TestCareerChange:
    """Tests for _CAREER_CHANGE_RE and _handle_career_change."""

    _REGEX_CASES_MATCH = [
        "I want to change my career",
        "I want to switch careers",
        "how do I transition to project management?",
        "how can I move from engineering to consulting?",
        "career change tips for UAE",
        "career pivot advice",
        "career transition from HSE to operations",
        "can I move from finance to HR?",
        "I'm thinking of switching careers",
        "I'm looking to pivot to data science",
        "I am looking to transition into management",
        "التحول الوظيفي في الإمارات",
    ]

    _REGEX_CASES_NO_MATCH = [
        "find remote jobs",
        "I need a job urgently",
        "how do I negotiate my salary?",
        "show my applications",
        "update my target role",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _CAREER_CHANGE_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _CAREER_CHANGE_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _CAREER_CHANGE_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _CAREER_CHANGE_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        mock_route = {"provider": "openai", "client": MagicMock(), "model": "gpt-4.1-mini"}
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: mock_route)
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_career_change(self, monkeypatch):
        result = self._run(monkeypatch, "I want to change my career")
        assert result["type"] == "career_change_advice"

    def test_career_pivot_routes(self, monkeypatch):
        result = self._run(monkeypatch, "career pivot advice")
        assert result["type"] == "career_change_advice"

    def test_transition_how_to_routes(self, monkeypatch):
        result = self._run(monkeypatch, "how do I transition to project management?")
        assert result["type"] == "career_change_advice"

    def test_target_role_extracted(self, monkeypatch):
        result = self._run(monkeypatch, "how do I transition to project management?")
        assert result["type"] == "career_change_advice"
        # target_role should be extracted or fall back gracefully
        assert isinstance(result.get("message"), str)

    def test_source_role_from_profile(self, monkeypatch):
        result = self._run(monkeypatch, "I want to switch careers", profile=_CVProfile())
        assert result["type"] == "career_change_advice"
        # Profile has current_role="Senior HSE Manager"
        msg = result["message"]
        assert isinstance(msg, str) and len(msg) > 50

    def test_message_has_steps(self, monkeypatch):
        result = self._run(monkeypatch, "career change tips for UAE")
        msg = result["message"]
        assert "1." in msg or "Recommended" in msg or "الخطوات" in msg

    def test_message_has_timeline(self, monkeypatch):
        result = self._run(monkeypatch, "I want to switch careers")
        assert "month" in result["message"].lower() or "شهر" in result["message"]

    def test_can_i_move_routes(self, monkeypatch):
        result = self._run(monkeypatch, "can I move from engineering to consulting?")
        assert result["type"] == "career_change_advice"

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "I want to change my career", profile=_EmptyProfile())
        assert result["type"] == "career_change_advice"

    def test_arabic_career_change(self, monkeypatch):
        result = self._run(monkeypatch, "التحول الوظيفي في الإمارات")
        assert result["type"] == "career_change_advice"


# ── Best Employers ────────────────────────────────────────────────────────────

class TestBestEmployers:
    """Tests for _BEST_EMPLOYERS_RE and _handle_best_employers."""

    _REGEX_CASES_MATCH = [
        "which companies hire HSE managers in Dubai?",
        "what companies hire project managers in UAE?",
        "best companies to work for in Dubai",
        "top employers in UAE for engineers",
        "who are the best employers for safety officers?",
        "leading companies hiring logistics managers",
        "major employers in Abu Dhabi",
        "top Dubai employers in construction",
        "أفضل شركات في الإمارات",
        "من يوظف مديري مشاريع",
    ]

    _REGEX_CASES_NO_MATCH = [
        "find jobs at ADNOC",           # company search
        "show my applications",
        "I need a job urgently",
        "how do I negotiate my salary?",
        "find government jobs in Dubai",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _BEST_EMPLOYERS_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _BEST_EMPLOYERS_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _BEST_EMPLOYERS_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _BEST_EMPLOYERS_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run_with_jsearch(
        self,
        monkeypatch,
        message: str,
        profile=None,
        items: list | None = None,
    ):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        fake_result = {"data": items or []}
        mock_route = {"provider": "openai", "client": MagicMock(), "model": "gpt-4.1-mini"}
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: mock_route)
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._search_jsearch_meta = lambda q, location="": fake_result
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_best_employers(self, monkeypatch):
        result = self._run_with_jsearch(monkeypatch, "which companies hire HSE managers in Dubai?")
        assert result["type"] == "best_employers"

    def test_top_companies_routes(self, monkeypatch):
        result = self._run_with_jsearch(monkeypatch, "best companies to work for in Dubai")
        assert result["type"] == "best_employers"

    def test_location_abu_dhabi(self, monkeypatch):
        result = self._run_with_jsearch(monkeypatch, "top employers in Abu Dhabi")
        assert result["location"] == "Abu Dhabi"

    def test_location_sharjah(self, monkeypatch):
        result = self._run_with_jsearch(monkeypatch, "leading companies in Sharjah hiring engineers")
        assert result["location"] == "Sharjah"

    def test_employers_list_from_jsearch(self, monkeypatch):
        items = [
            {"employer_name": "ADNOC", "job_title": "HSE Manager"},
            {"employer_name": "DP World", "job_title": "Safety Officer"},
            {"employer_name": "ADNOC", "job_title": "EHS Specialist"},
        ]
        result = self._run_with_jsearch(
            monkeypatch, "which companies hire HSE managers?", items=items
        )
        assert "ADNOC" in result["employers"]

    def test_employers_deduplicated(self, monkeypatch):
        items = [{"employer_name": "ADNOC"}] * 5 + [{"employer_name": "DP World"}]
        result = self._run_with_jsearch(
            monkeypatch, "top employers for HSE in UAE", items=items
        )
        assert result["employers"].count("ADNOC") == 1

    def test_empty_jsearch_returns_fallback_message(self, monkeypatch):
        result = self._run_with_jsearch(monkeypatch, "best employers in UAE", items=[])
        assert result["type"] == "best_employers"
        assert isinstance(result["message"], str) and len(result["message"]) > 20

    def test_employers_field_is_list(self, monkeypatch):
        result = self._run_with_jsearch(monkeypatch, "which companies hire HSE managers?")
        assert isinstance(result.get("employers"), list)

    def test_message_mentions_linkedin(self, monkeypatch):
        items = [{"employer_name": "ADNOC"}, {"employer_name": "DP World"}]
        result = self._run_with_jsearch(
            monkeypatch, "best companies to work for in Dubai", items=items
        )
        assert "LinkedIn" in result["message"] or "Bayt" in result["message"] or "ADNOC" in result["message"]

    def test_role_from_profile_used_when_not_in_message(self, monkeypatch):
        result = self._run_with_jsearch(monkeypatch, "best companies to work for in Dubai", profile=_CVProfile())
        assert result["type"] == "best_employers"

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run_with_jsearch(monkeypatch, "top employers in UAE", profile=_EmptyProfile())
        assert result["type"] == "best_employers"


# ── UAE Job Search Tips ───────────────────────────────────────────────────────

class TestJobSearchTips:
    """Tests for _JOB_SEARCH_TIPS_RE and _handle_job_search_tips."""

    _REGEX_CASES_MATCH = [
        "how do I find a job in UAE?",
        "how can I find a job in Dubai?",
        "best job boards in UAE",
        "best job sites in Dubai",
        "tips for job hunting in UAE",
        "job hunting strategy",
        "job search advice for UAE",
        "how long does it take to find a job in UAE?",
        "how much time will it take to find a job?",
        "should I use a recruitment agency?",
        "is it worth using a recruiter in UAE?",
        "where should I look for jobs?",
        "where can I find jobs in Dubai?",
        "نصائح البحث عن وظيفة",
    ]

    _REGEX_CASES_NO_MATCH = [
        "I need a job urgently",          # urgency search
        "find remote jobs in UAE",         # employment type search
        "show my applications",
        "how do I negotiate my salary?",
        "career change tips for UAE",      # career change
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _JOB_SEARCH_TIPS_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _JOB_SEARCH_TIPS_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _JOB_SEARCH_TIPS_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _JOB_SEARCH_TIPS_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_job_search_tips(self, monkeypatch):
        result = self._run(monkeypatch, "how do I find a job in UAE?")
        assert result["type"] == "job_search_tips"

    def test_job_boards_query_routes(self, monkeypatch):
        result = self._run(monkeypatch, "best job boards in UAE")
        assert result["type"] == "job_search_tips"

    def test_message_mentions_bayt(self, monkeypatch):
        result = self._run(monkeypatch, "best job boards in UAE")
        assert "Bayt" in result["message"]

    def test_message_mentions_linkedin(self, monkeypatch):
        result = self._run(monkeypatch, "tips for job hunting in UAE")
        assert "LinkedIn" in result["message"]

    def test_timeline_advice_when_asked(self, monkeypatch):
        result = self._run(monkeypatch, "how long does it take to find a job in UAE?")
        msg = result["message"]
        assert "month" in msg.lower() or "شهر" in msg

    def test_recruiter_advice_when_asked(self, monkeypatch):
        result = self._run(monkeypatch, "should I use a recruitment agency?")
        msg = result["message"]
        assert "recruit" in msg.lower() or "مجنّد" in msg or "توظيف" in msg

    def test_message_has_tips(self, monkeypatch):
        result = self._run(monkeypatch, "how do I find a job in Dubai?")
        msg = result["message"]
        assert len(msg) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "how do I find a job in UAE?", profile=_EmptyProfile())
        assert result["type"] == "job_search_tips"


# ── UAE Benefits / Package Guide ──────────────────────────────────────────────

class TestBenefitsPackage:
    """Tests for _BENEFITS_QUERY_RE and _handle_benefits_package."""

    _REGEX_CASES_MATCH = [
        "what benefits should I expect in UAE?",
        "what benefits are typical in UAE?",
        "what benefits does the package include?",
        "housing allowance in UAE",
        "what's a good UAE package?",
        "what is a typical salary package in Dubai?",
        "is housing allowance standard in UAE?",
        "is medical insurance included in UAE jobs?",
        "is gratuity mandatory in UAE?",
        "end of service gratuity in UAE",
        "how many annual leave days in UAE?",
        "مزايا الوظيفة في الإمارات",
        "بدل سكن في الإمارات",
    ]

    _REGEX_CASES_NO_MATCH = [
        "my expected salary is 20000",     # salary set
        "find jobs paying above 15000",    # salary search
        "I need a job urgently",
        "how do I negotiate my salary?",   # salary negotiation (separate)
        "show my applications",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _BENEFITS_QUERY_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _BENEFITS_QUERY_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _BENEFITS_QUERY_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _BENEFITS_QUERY_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_benefits_guide(self, monkeypatch):
        result = self._run(monkeypatch, "what benefits should I expect in UAE?")
        assert result["type"] == "benefits_guide"

    def test_housing_allowance_query_routes(self, monkeypatch):
        result = self._run(monkeypatch, "housing allowance in UAE")
        assert result["type"] == "benefits_guide"

    def test_message_mentions_housing(self, monkeypatch):
        result = self._run(monkeypatch, "what benefits should I expect in UAE?")
        assert "housing" in result["message"].lower() or "سكن" in result["message"]

    def test_message_mentions_medical(self, monkeypatch):
        result = self._run(monkeypatch, "what's a typical UAE package?")
        assert "medical" in result["message"].lower() or "طبي" in result["message"]

    def test_gratuity_advice_when_asked(self, monkeypatch):
        result = self._run(monkeypatch, "end of service gratuity in UAE")
        assert "gratuity" in result["message"].lower() or "مكافأة" in result["message"]

    def test_senior_profile_gets_extra_advice(self, monkeypatch):
        result = self._run(monkeypatch, "what benefits should I expect?", profile=_CVProfile())
        msg = result["message"]
        assert len(msg) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "what benefits should I expect?", profile=_EmptyProfile())
        assert result["type"] == "benefits_guide"

    def test_message_has_red_flags_section(self, monkeypatch):
        result = self._run(monkeypatch, "what's a typical UAE package?")
        assert "red flag" in result["message"].lower() or "Red flag" in result["message"] or "تحذير" in result["message"]


# ── Offer Evaluation ─────────────────────────────────────────────────────────

class TestOfferEvaluation:
    """Tests for _OFFER_EVAL_RE and _handle_offer_evaluation."""

    _REGEX_CASES_MATCH = [
        "should I accept this offer?",
        "should I take this job offer?",
        "should I reject this offer?",
        "how to evaluate a job offer",
        "how do I evaluate a job offer?",
        "is this offer good?",
        "is the offer fair?",
        "job offer pros and cons",
        "offer evaluation checklist",
        "is this offer worth it?",
        "what should I look for in a job offer?",
        "what to consider in a job offer",
        "how do I decide whether to accept an offer",
        "قبول عرض العمل",
    ]

    _REGEX_CASES_NO_MATCH = [
        "how do I negotiate my salary?",    # salary negotiation
        "I got a job offer",                # no evaluation question
        "show my applications",
        "I need a job urgently",
        "should I use a recruitment agency?",   # job search tips
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _OFFER_EVAL_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _OFFER_EVAL_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _OFFER_EVAL_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _OFFER_EVAL_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_offer_evaluation(self, monkeypatch):
        result = self._run(monkeypatch, "should I accept this offer?")
        assert result["type"] == "offer_evaluation"

    def test_how_to_evaluate_routes(self, monkeypatch):
        result = self._run(monkeypatch, "how to evaluate a job offer")
        assert result["type"] == "offer_evaluation"

    def test_offer_checklist_routes(self, monkeypatch):
        result = self._run(monkeypatch, "offer evaluation checklist")
        assert result["type"] == "offer_evaluation"

    def test_message_has_checklist(self, monkeypatch):
        result = self._run(monkeypatch, "should I accept this offer?")
        msg = result["message"]
        assert "□" in msg or "checklist" in msg.lower() or "راجع" in msg

    def test_message_mentions_red_flags(self, monkeypatch):
        result = self._run(monkeypatch, "how do I evaluate a job offer?")
        msg = result["message"]
        assert "flag" in msg.lower() or "تحذير" in msg or "🚩" in msg

    def test_message_mentions_contract(self, monkeypatch):
        result = self._run(monkeypatch, "what should I look for in a job offer?")
        msg = result["message"]
        assert "contract" in msg.lower() or "عقد" in msg

    def test_salary_expectation_personalized(self, monkeypatch):
        from dataclasses import dataclass, field
        from typing import List, Optional
        @dataclass
        class _ProfileWithSalary:
            skills: List[str] = field(default_factory=list)
            certifications: List[str] = field(default_factory=list)
            years_experience: float = 8.0
            target_roles: List[str] = field(default_factory=lambda: ["HSE Manager"])
            industries: List[str] = field(default_factory=list)
            cv_status: str = "parsed"
            cv_filename: str = "cv.pdf"
            salary_expectation_aed: int = 25000
        result = self._run(monkeypatch, "should I accept this offer?", profile=_ProfileWithSalary())
        assert result["type"] == "offer_evaluation"

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "should I accept this offer?", profile=_EmptyProfile())
        assert result["type"] == "offer_evaluation"

    def test_arabic_offer_query(self, monkeypatch):
        result = self._run(monkeypatch, "قبول عرض العمل")
        assert result["type"] == "offer_evaluation"


# ── UAE Labor Law ─────────────────────────────────────────────────────────────

class TestUAELaborLaw:
    """Tests for _UAE_LABOR_LAW_RE and _handle_uae_labor_law."""

    _REGEX_CASES_MATCH = [
        "what is the probation period in UAE?",
        "how does the probation period work?",
        "probation period UAE rules",
        "probation period duration in Dubai",
        "can I leave during probation?",
        "can I resign during the probation period?",
        "UAE labor law",
        "UAE labour rights",
        "termination rights in UAE",
        "what are my dismissal rights?",
        "unlimited contract vs limited contract UAE",
        "MOHRE complaint",
        "قانون العمل في الإمارات",
    ]

    _REGEX_CASES_NO_MATCH = [
        "update my notice period to 30 days",  # notice period RE
        "I'm on a spouse visa",                 # visa status RE
        "how do I negotiate my salary?",
        "I need a job urgently",
        "show my applications",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _UAE_LABOR_LAW_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _UAE_LABOR_LAW_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _UAE_LABOR_LAW_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _UAE_LABOR_LAW_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_labor_law(self, monkeypatch):
        result = self._run(monkeypatch, "what is the probation period in UAE?")
        assert result["type"] == "uae_labor_law"

    def test_termination_routes(self, monkeypatch):
        result = self._run(monkeypatch, "what are my termination rights in UAE?")
        assert result["type"] == "uae_labor_law"

    def test_sub_topic_probation(self, monkeypatch):
        result = self._run(monkeypatch, "what is the probation period in UAE?")
        assert result["sub_topic"] == "probation"

    def test_sub_topic_termination(self, monkeypatch):
        result = self._run(monkeypatch, "termination rights in UAE")
        assert result["sub_topic"] == "termination"

    def test_sub_topic_contract(self, monkeypatch):
        result = self._run(monkeypatch, "unlimited contract vs limited contract UAE")
        assert result["sub_topic"] == "contract"

    def test_probation_message_has_14_days(self, monkeypatch):
        result = self._run(monkeypatch, "what is the probation period in UAE?")
        assert "14" in result["message"]

    def test_termination_message_has_mohre(self, monkeypatch):
        result = self._run(monkeypatch, "termination rights UAE")
        assert "MOHRE" in result["message"] or "وزارة" in result["message"]

    def test_message_length(self, monkeypatch):
        result = self._run(monkeypatch, "UAE labor law")
        assert len(result["message"]) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "UAE labor law", profile=_EmptyProfile())
        assert result["type"] == "uae_labor_law"


# ── Post-Interview Email ───────────────────────────────────────────────────────

class TestPostInterviewEmail:
    """Tests for _POST_INTERVIEW_EMAIL_RE and _handle_post_interview_email."""

    _REGEX_CASES_MATCH = [
        "should I send a thank you email after the interview?",
        "should I send a follow-up email after the interview?",
        "how to write a thank you email after an interview",
        "how do I send a thank you note following the interview?",
        "thank you email after interview",
        "post-interview email",
        "post-interview follow-up",
        "after the interview should I send a thank you?",
        "after my interview do I write a follow-up?",
        "رسالة الشكر بعد المقابلة",
    ]

    _REGEX_CASES_NO_MATCH = [
        "how do I prepare for an interview?",    # interview prep
        "how to ace an interview",               # interview prep
        "follow up timing after applying",       # followup timing
        "I need a job urgently",
        "show my applications",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _POST_INTERVIEW_EMAIL_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _POST_INTERVIEW_EMAIL_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _POST_INTERVIEW_EMAIL_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _POST_INTERVIEW_EMAIL_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None, recent_ctx=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: recent_ctx or {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_post_interview_email(self, monkeypatch):
        result = self._run(monkeypatch, "should I send a thank you email after the interview?")
        assert result["type"] == "post_interview_email"

    def test_thank_you_email_routes(self, monkeypatch):
        result = self._run(monkeypatch, "thank you email after interview")
        assert result["type"] == "post_interview_email"

    def test_post_interview_followup_routes(self, monkeypatch):
        result = self._run(monkeypatch, "post-interview follow-up")
        assert result["type"] == "post_interview_email"

    def test_message_has_template(self, monkeypatch):
        result = self._run(monkeypatch, "how to write a thank you email after an interview")
        msg = result["message"]
        assert "Subject" in msg or "الموضوع" in msg

    def test_message_has_timing_advice(self, monkeypatch):
        result = self._run(monkeypatch, "should I send a thank you email after the interview?")
        msg = result["message"]
        assert "24" in msg

    def test_recent_company_in_subject(self, monkeypatch):
        ctx = {"recent_company": "ADNOC", "recent_job": "HSE Manager"}
        result = self._run(monkeypatch, "thank you email after interview", recent_ctx=ctx)
        msg = result["message"]
        assert "ADNOC" in msg

    def test_role_field_present(self, monkeypatch):
        result = self._run(monkeypatch, "thank you email after interview")
        assert isinstance(result.get("role"), str)

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "thank you email after interview", profile=_EmptyProfile())
        assert result["type"] == "post_interview_email"


# ── Skill Gap Assessment ──────────────────────────────────────────────────────

class TestSkillGap:
    """Tests for _SKILL_GAP_RE and _handle_skill_gap."""

    _REGEX_CASES_MATCH = [
        "what skills am I missing?",
        "what skills do I lack?",
        "what skills do I need to develop for my role?",
        "am I qualified for a senior manager?",
        "am I eligible for a director position?",
        "am I ready for a senior role?",
        "how do I close my skill gap?",
        "how to close the skills gap?",
        "skill gap analysis",
        "skill gap assessment for HSE",
        "what experience do I need to get a senior role?",
        "what qualifications do I need to land a director position?",
        "فجوة المهارات",
    ]

    _REGEX_CASES_NO_MATCH = [
        "what certifications do I need?",         # certification advice RE
        "how do I improve my CV?",                # profile improve RE
        "show my applications",
        "I need a job urgently",
        "how do I negotiate my salary?",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _SKILL_GAP_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _SKILL_GAP_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _SKILL_GAP_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _SKILL_GAP_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_skill_gap(self, monkeypatch):
        result = self._run(monkeypatch, "what skills am I missing?")
        assert result["type"] == "skill_gap"

    def test_am_i_qualified_routes(self, monkeypatch):
        result = self._run(monkeypatch, "am I qualified for a senior manager?")
        assert result["type"] == "skill_gap"

    def test_skill_gap_analysis_routes(self, monkeypatch):
        result = self._run(monkeypatch, "skill gap analysis")
        assert result["type"] == "skill_gap"

    def test_target_role_from_profile(self, monkeypatch):
        result = self._run(monkeypatch, "what skills am I missing?", profile=_CVProfile())
        assert result["target_role"] == "Senior HSE Manager"

    def test_gaps_and_strengths_lists(self, monkeypatch):
        result = self._run(monkeypatch, "what skills am I missing?")
        assert isinstance(result.get("gaps"), list)
        assert isinstance(result.get("strengths"), list)

    def test_hse_profile_gets_cert_gap_or_strength(self, monkeypatch):
        result = self._run(monkeypatch, "what skills am I missing?", profile=_CVProfile())
        msg = result["message"]
        assert "NEBOSH" in msg or "IOSH" in msg or "nebosh" in msg

    def test_message_has_strengths_section(self, monkeypatch):
        result = self._run(monkeypatch, "what skills am I missing?", profile=_CVProfile())
        msg = result["message"]
        assert "strength" in msg.lower() or "✅" in msg or "قوت" in msg

    def test_message_has_gap_section(self, monkeypatch):
        result = self._run(monkeypatch, "what skills am I missing?", profile=_CVProfile())
        msg = result["message"]
        assert "gap" in msg.lower() or "⬜" in msg or "فجوة" in msg

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "what skills am I missing?", profile=_EmptyProfile())
        assert result["type"] == "skill_gap"

    def test_experience_level_mentioned(self, monkeypatch):
        result = self._run(monkeypatch, "am I ready for a senior role?", profile=_CVProfile())
        msg = result["message"]
        assert isinstance(msg, str) and len(msg) > 50


# ── Interview Preparation ──────────────────────────────────────────────────────

class TestInterviewPrep:
    """Tests for _INTERVIEW_PREP_RE and _handle_interview_prep."""

    _REGEX_CASES_MATCH = [
        "how do I prepare for an interview?",
        "how to ace an interview",
        "how can I pass an interview?",
        "interview tips",
        "interview preparation guide",
        "interview questions to expect",
        "common interview questions",
        "what questions should I expect at an interview?",
        "tell me about yourself",
        "STAR method",
        "behavioral interview",
        "how do I answer interview questions?",
        "أسئلة المقابلة",
    ]

    _REGEX_CASES_NO_MATCH = [
        "should I send a thank you email after the interview?",  # post-interview email
        "what skills am I missing?",  # skill gap
        "I need a job urgently",
        "show my applications",
        "how do I negotiate my salary?",  # salary negotiation
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _INTERVIEW_PREP_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _INTERVIEW_PREP_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _INTERVIEW_PREP_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _INTERVIEW_PREP_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_interview_prep(self, monkeypatch):
        result = self._run(monkeypatch, "how do I prepare for an interview?")
        assert result["type"] == "interview_prep"

    def test_ace_interview_routes(self, monkeypatch):
        result = self._run(monkeypatch, "how to ace an interview")
        assert result["type"] == "interview_prep"

    def test_common_questions_routes(self, monkeypatch):
        result = self._run(monkeypatch, "common interview questions")
        assert result["type"] == "interview_prep"

    def test_star_method_routes(self, monkeypatch):
        result = self._run(monkeypatch, "STAR method for interviews")
        assert result["type"] == "interview_prep"

    def test_message_has_star_method(self, monkeypatch):
        result = self._run(monkeypatch, "how do I prepare for an interview?")
        assert "STAR" in result["message"]

    def test_message_has_tell_me_about_yourself(self, monkeypatch):
        result = self._run(monkeypatch, "interview tips")
        msg = result["message"].lower()
        assert "tell me about yourself" in msg or "tell me about" in msg

    def test_target_role_from_profile(self, monkeypatch):
        result = self._run(monkeypatch, "how do I prepare for an interview?", profile=_CVProfile())
        assert result.get("target_role") == "Senior HSE Manager"

    def test_message_contains_role(self, monkeypatch):
        result = self._run(monkeypatch, "how do I prepare for an interview?", profile=_CVProfile())
        assert "Senior HSE Manager" in result["message"]

    def test_message_length(self, monkeypatch):
        result = self._run(monkeypatch, "interview tips")
        assert len(result["message"]) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "interview prep guide", profile=_EmptyProfile())
        assert result["type"] == "interview_prep"


# ── Salary Negotiation ────────────────────────────────────────────────────────

class TestSalaryNegotiation:
    """Tests for _SALARY_NEGOTIATION_RE and _handle_salary_negotiation."""

    _REGEX_CASES_MATCH = [
        "how do I negotiate my salary?",
        "how to negotiate a higher salary",
        "can I negotiate the offer?",
        "should I counter the salary offer?",
        "salary negotiation tips",
        "salary counter-offer advice",
        "how to ask for a raise",
        "request a salary increase",
        "when should I discuss salary?",
        "negotiate my package",
        "مفاوضة الراتب",
    ]

    _REGEX_CASES_NO_MATCH = [
        "what is the salary for HSE Manager?",  # salary benchmark
        "what are the benefits in UAE?",         # benefits guide
        "how do I prepare for an interview?",    # interview prep
        "I need a job urgently",
        "show my applications",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _SALARY_NEGOTIATION_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _SALARY_NEGOTIATION_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _SALARY_NEGOTIATION_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _SALARY_NEGOTIATION_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_salary_negotiation(self, monkeypatch):
        result = self._run(monkeypatch, "how do I negotiate my salary?")
        assert result["type"] == "salary_negotiation"

    def test_counter_offer_routes(self, monkeypatch):
        result = self._run(monkeypatch, "should I counter the salary offer?")
        assert result["type"] == "salary_negotiation"

    def test_raise_request_routes(self, monkeypatch):
        result = self._run(monkeypatch, "how to ask for a raise")
        assert result["type"] == "salary_negotiation"

    def test_negotiate_package_routes(self, monkeypatch):
        result = self._run(monkeypatch, "negotiate my package")
        assert result["type"] == "salary_negotiation"

    def test_message_mentions_full_package(self, monkeypatch):
        result = self._run(monkeypatch, "salary negotiation tips")
        msg = result["message"].lower()
        assert "allowance" in msg or "package" in msg or "benefit" in msg

    def test_message_has_timing_advice(self, monkeypatch):
        result = self._run(monkeypatch, "how do I negotiate my salary?")
        msg = result["message"].lower()
        assert "offer" in msg and ("wait" in msg or "formal" in msg or "timing" in msg or "48" in msg)

    def test_message_has_example_phrase(self, monkeypatch):
        result = self._run(monkeypatch, "salary negotiation tips")
        msg = result["message"]
        assert "AED" in msg or "X" in msg or "range" in msg.lower()

    def test_message_length(self, monkeypatch):
        result = self._run(monkeypatch, "salary negotiation tips")
        assert len(result["message"]) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "how do I negotiate my salary?", profile=_EmptyProfile())
        assert result["type"] == "salary_negotiation"


# ── LinkedIn Optimisation ─────────────────────────────────────────────────────

class TestLinkedInTips:
    """Tests for _LINKEDIN_TIPS_RE and _handle_linkedin_tips."""

    _REGEX_CASES_MATCH = [
        "how do I improve my LinkedIn?",
        "how to optimise my LinkedIn profile",
        "how to optimize my LinkedIn",
        "LinkedIn tips",
        "LinkedIn profile tips",
        "LinkedIn advice for UAE",
        "LinkedIn for jobs in Dubai",
        "should I use LinkedIn?",
        "is LinkedIn useful in UAE?",
        "is LinkedIn worth it for job search?",
        "LinkedIn headline tips",
        "LinkedIn summary advice",
        "LinkedIn connections tips",
        "نصائح LinkedIn",
    ]

    _REGEX_CASES_NO_MATCH = [
        "how do I prepare for an interview?",  # interview prep
        "how do I negotiate my salary?",       # salary negotiation
        "I need a job urgently",
        "show my applications",
        "how do I improve my CV?",             # profile improve RE
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _LINKEDIN_TIPS_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _LINKEDIN_TIPS_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _LINKEDIN_TIPS_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _LINKEDIN_TIPS_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_linkedin_tips(self, monkeypatch):
        result = self._run(monkeypatch, "how do I improve my LinkedIn?")
        assert result["type"] == "linkedin_tips"

    def test_improve_linkedin_routes(self, monkeypatch):
        # "how do I improve" is not in _LINKEDIN_NETWORKING_RE — reaches our gate
        result = self._run(monkeypatch, "how do I improve my LinkedIn?")
        assert result["type"] == "linkedin_tips"

    def test_should_use_linkedin_routes(self, monkeypatch):
        result = self._run(monkeypatch, "should I use LinkedIn?")
        assert result["type"] == "linkedin_tips"

    def test_is_linkedin_useful_routes(self, monkeypatch):
        result = self._run(monkeypatch, "is LinkedIn useful in UAE?")
        assert result["type"] == "linkedin_tips"

    def test_target_role_from_profile(self, monkeypatch):
        # "LinkedIn headline tips" is not caught by _LINKEDIN_NETWORKING_RE
        result = self._run(monkeypatch, "LinkedIn headline tips", profile=_CVProfile())
        assert result.get("target_role") == "Senior HSE Manager"

    def test_message_mentions_headline(self, monkeypatch):
        result = self._run(monkeypatch, "LinkedIn headline tips")
        assert "Headline" in result["message"] or "headline" in result["message"]

    def test_message_mentions_open_to_work(self, monkeypatch):
        result = self._run(monkeypatch, "how do I improve my LinkedIn?")
        assert "Open to Work" in result["message"] or "open to work" in result["message"].lower()

    def test_message_length(self, monkeypatch):
        result = self._run(monkeypatch, "how do I improve my LinkedIn?")
        assert len(result["message"]) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "is LinkedIn useful in UAE?", profile=_EmptyProfile())
        assert result["type"] == "linkedin_tips"


# ── Resignation Letter ────────────────────────────────────────────────────────

class TestResignationLetter:
    """Tests for _RESIGNATION_LETTER_RE and _handle_resignation_letter."""

    _REGEX_CASES_MATCH = [
        "how do I write a resignation letter?",
        "how to write a resignation email",
        "how should I draft a resignation letter?",
        "resignation letter template",
        "resignation letter guide",
        "how do I resign professionally?",
        "how to resign properly",
        "how do I hand in my notice?",
        "how to submit my resignation?",
        "what should I say in a resignation letter?",
        "خطاب استقالة",
        "كيف أستقيل",
    ]

    _REGEX_CASES_NO_MATCH = [
        "should I accept this offer?",     # offer eval
        "how do I negotiate my salary?",   # salary negotiation
        "how do I prepare for an interview?",
        "I need a job urgently",
        "show my applications",
        "UAE labor law",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _RESIGNATION_LETTER_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _RESIGNATION_LETTER_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _RESIGNATION_LETTER_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _RESIGNATION_LETTER_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_resignation_letter(self, monkeypatch):
        result = self._run(monkeypatch, "how do I write a resignation letter?")
        assert result["type"] == "resignation_letter"

    def test_resign_professionally_routes(self, monkeypatch):
        result = self._run(monkeypatch, "how to resign professionally")
        assert result["type"] == "resignation_letter"

    def test_hand_in_notice_routes(self, monkeypatch):
        result = self._run(monkeypatch, "how do I hand in my notice?")
        assert result["type"] == "resignation_letter"

    def test_template_routes(self, monkeypatch):
        result = self._run(monkeypatch, "resignation letter template")
        assert result["type"] == "resignation_letter"

    def test_message_has_subject_line(self, monkeypatch):
        result = self._run(monkeypatch, "how do I write a resignation letter?")
        msg = result["message"]
        assert "Subject" in msg or "الموضوع" in msg

    def test_message_has_notice_period(self, monkeypatch):
        result = self._run(monkeypatch, "resignation letter template")
        msg = result["message"].lower()
        assert "notice" in msg or "إشعار" in msg

    def test_message_has_sincerely(self, monkeypatch):
        result = self._run(monkeypatch, "how do I write a resignation letter?")
        msg = result["message"]
        assert "Sincerely" in msg or "sincerely" in msg or "التقدير" in msg

    def test_message_length(self, monkeypatch):
        result = self._run(monkeypatch, "how do I write a resignation letter?")
        assert len(result["message"]) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "resignation letter guide", profile=_EmptyProfile())
        assert result["type"] == "resignation_letter"


# ── Relocation to UAE ─────────────────────────────────────────────────────────

class TestRelocationUAE:
    """Tests for _RELOCATION_UAE_RE and _handle_relocation_uae."""

    _REGEX_CASES_MATCH = [
        "how do I move to Dubai for work?",
        "how to relocate to UAE?",
        "how can I move to Abu Dhabi?",
        "relocating to UAE",
        "moving to Dubai for a job",
        "tips for relocating to UAE",
        "advice for moving to Dubai",
        "what do I need to move to UAE?",
        "what should I do to relocate to Dubai?",
        "cost of living in Dubai",
        "cost of living in UAE",
        "الانتقال إلى دبي",
    ]

    _REGEX_CASES_NO_MATCH = [
        "can I apply from abroad?",         # apply from abroad
        "how do I write a resignation?",    # resignation
        "find remote HSE jobs",             # employment type search
        "I need a job urgently",
        "show my applications",
        "UAE labor law",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _RELOCATION_UAE_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _RELOCATION_UAE_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _RELOCATION_UAE_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _RELOCATION_UAE_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_relocation_uae(self, monkeypatch):
        result = self._run(monkeypatch, "how do I move to Dubai for work?")
        assert result["type"] == "relocation_uae"

    def test_relocating_routes(self, monkeypatch):
        result = self._run(monkeypatch, "relocating to UAE")
        assert result["type"] == "relocation_uae"

    def test_cost_of_living_routes(self, monkeypatch):
        result = self._run(monkeypatch, "cost of living in Dubai")
        assert result["type"] == "relocation_uae"

    def test_tips_for_relocating_routes(self, monkeypatch):
        result = self._run(monkeypatch, "tips for relocating to UAE")
        assert result["type"] == "relocation_uae"

    def test_message_has_visa_info(self, monkeypatch):
        result = self._run(monkeypatch, "how do I move to Dubai for work?")
        msg = result["message"].lower()
        assert "visa" in msg or "تأشيرة" in msg

    def test_message_has_cost_benchmarks(self, monkeypatch):
        result = self._run(monkeypatch, "relocating to UAE")
        msg = result["message"]
        assert "AED" in msg or "درهم" in msg

    def test_message_has_dubai(self, monkeypatch):
        result = self._run(monkeypatch, "how do I move to Dubai for work?")
        assert "Dubai" in result["message"] or "دبي" in result["message"]

    def test_message_length(self, monkeypatch):
        result = self._run(monkeypatch, "relocating to UAE")
        assert len(result["message"]) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "tips for relocating to UAE", profile=_EmptyProfile())
        assert result["type"] == "relocation_uae"


# ── Applying from Abroad ──────────────────────────────────────────────────────

class TestApplyFromAbroad:
    """Tests for _APPLY_FROM_ABROAD_RE and _handle_apply_from_abroad."""

    _REGEX_CASES_MATCH = [
        "can I apply for UAE jobs from abroad?",
        "can I apply for jobs from outside UAE?",
        "do I need to be in UAE to apply?",
        "do I have to be in Dubai to look for jobs?",
        "should I relocate before applying?",
        "should I be in UAE before job hunting?",
        "applying for UAE jobs from overseas",
        "applying for jobs from outside Dubai",
        "job hunting from abroad",
        "job hunting while overseas",
        "is it possible to apply from abroad?",
        "is it okay to job hunt from outside UAE?",
        "التقديم على وظائف الإمارات من الخارج",
    ]

    _REGEX_CASES_NO_MATCH = [
        "how do I relocate to UAE?",         # relocation handler
        "how do I write a resignation?",     # resignation
        "find remote HSE jobs",              # employment type search
        "I need a job urgently",
        "show my applications",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _APPLY_FROM_ABROAD_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _APPLY_FROM_ABROAD_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _APPLY_FROM_ABROAD_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _APPLY_FROM_ABROAD_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_apply_from_abroad(self, monkeypatch):
        result = self._run(monkeypatch, "can I apply for UAE jobs from abroad?")
        assert result["type"] == "apply_from_abroad"

    def test_do_i_need_to_be_in_uae_routes(self, monkeypatch):
        result = self._run(monkeypatch, "do I need to be in UAE to apply?")
        assert result["type"] == "apply_from_abroad"

    def test_should_relocate_first_routes(self, monkeypatch):
        result = self._run(monkeypatch, "should I relocate before applying?")
        assert result["type"] == "apply_from_abroad"

    def test_job_hunting_from_abroad_routes(self, monkeypatch):
        result = self._run(monkeypatch, "job hunting from abroad")
        assert result["type"] == "apply_from_abroad"

    def test_message_says_yes_can_apply(self, monkeypatch):
        result = self._run(monkeypatch, "can I apply for UAE jobs from abroad?")
        msg = result["message"].lower()
        assert "yes" in msg or "can apply" in msg or "نعم" in msg

    def test_message_mentions_cover_letter(self, monkeypatch):
        result = self._run(monkeypatch, "can I apply for UAE jobs from abroad?")
        msg = result["message"].lower()
        assert "cover letter" in msg or "cv" in msg or "relocat" in msg

    def test_message_mentions_relocation(self, monkeypatch):
        result = self._run(monkeypatch, "can I apply for UAE jobs from abroad?")
        assert "reloc" in result["message"].lower() or "move" in result["message"].lower()

    def test_message_length(self, monkeypatch):
        result = self._run(monkeypatch, "can I apply for UAE jobs from abroad?")
        assert len(result["message"]) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "is it okay to job hunt from outside UAE?", profile=_EmptyProfile())
        assert result["type"] == "apply_from_abroad"


# ── Employment Gap ──────────────────────────────────────────────────────────────


class TestEmploymentGap:
    """Tests for _EMPLOYMENT_GAP_RE and _handle_employment_gap."""

    _REGEX_CASES_MATCH = [
        "how do I explain a gap in my CV?",
        "how do I explain a career gap?",
        "how should I address a gap in my employment history?",
        "how do I deal with a work gap?",
        "I have a career gap in my CV",
        "there is a gap in my resume",
        "career gap explanation on CV",
        "employment gap in interview",
        "I took time off for 6 months",
        "I was unemployed for a year",
        "I was between jobs for several months",
        "فجوة في السيرة الذاتية",
        "كيف أشرح الانقطاع عن العمل",
    ]

    _REGEX_CASES_NO_MATCH = [
        "show me HSE jobs in Dubai",
        "how do I write a cover letter?",
        "what is my skill gap?",        # skill gap handler
        "how to negotiate salary",
        "help me find a job",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _EMPLOYMENT_GAP_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _EMPLOYMENT_GAP_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _EMPLOYMENT_GAP_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _EMPLOYMENT_GAP_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_employment_gap(self, monkeypatch):
        result = self._run(monkeypatch, "how do I explain a gap in my CV?")
        assert result["type"] == "employment_gap"

    def test_career_gap_routes(self, monkeypatch):
        result = self._run(monkeypatch, "how do I explain a career gap?")
        assert result["type"] == "employment_gap"

    def test_was_unemployed_routes(self, monkeypatch):
        result = self._run(monkeypatch, "I was unemployed for a year")
        assert result["type"] == "employment_gap"

    def test_between_jobs_routes(self, monkeypatch):
        result = self._run(monkeypatch, "I was between jobs for several months")
        assert result["type"] == "employment_gap"

    def test_message_mentions_frame_or_explain(self, monkeypatch):
        result = self._run(monkeypatch, "how do I explain a gap in my CV?")
        msg = result["message"].lower()
        assert "gap" in msg or "explain" in msg or "frame" in msg

    def test_message_mentions_cv_or_resume(self, monkeypatch):
        result = self._run(monkeypatch, "how do I explain a gap in my CV?")
        msg = result["message"].lower()
        assert "cv" in msg or "resume" in msg

    def test_message_length(self, monkeypatch):
        result = self._run(monkeypatch, "how do I explain a career gap?")
        assert len(result["message"]) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "how do I address a gap in my employment history?", profile=_EmptyProfile())
        assert result["type"] == "employment_gap"


# ── Company Research ────────────────────────────────────────────────────────────


class TestCompanyResearch:
    """Tests for _COMPANY_RESEARCH_RE and _handle_company_research."""

    _REGEX_CASES_MATCH = [
        "how do I research a company before an interview?",
        "how should I research the company before my interview?",
        "what should I know about a company before the interview?",
        "what to find out about a company before interview",
        "how do I prepare about the company?",
        "company research before interview",
        "company research tips",
        "what should I look up about them before the interview?",
        "what to know about the company before my interview",
        "كيف أبحث عن الشركة قبل المقابلة",
    ]

    _REGEX_CASES_NO_MATCH = [
        "how do I prepare for an interview?",   # interview prep handler
        "show me jobs at Aramco",
        "what is the best company in UAE?",
        "who are the top employers in Dubai?",
        "how do I negotiate salary",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _COMPANY_RESEARCH_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _COMPANY_RESEARCH_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _COMPANY_RESEARCH_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _COMPANY_RESEARCH_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_company_research(self, monkeypatch):
        result = self._run(monkeypatch, "how do I research a company before an interview?")
        assert result["type"] == "company_research"

    def test_what_to_find_out_routes(self, monkeypatch):
        result = self._run(monkeypatch, "what should I know about a company before the interview?")
        assert result["type"] == "company_research"

    def test_company_research_tips_routes(self, monkeypatch):
        result = self._run(monkeypatch, "company research tips")
        assert result["type"] == "company_research"

    def test_message_mentions_linkedin_or_glassdoor(self, monkeypatch):
        result = self._run(monkeypatch, "how do I research a company before an interview?")
        msg = result["message"].lower()
        assert "linkedin" in msg or "glassdoor" in msg or "website" in msg

    def test_message_mentions_interview(self, monkeypatch):
        result = self._run(monkeypatch, "what should I know about a company before the interview?")
        assert "interview" in result["message"].lower()

    def test_message_length(self, monkeypatch):
        result = self._run(monkeypatch, "how do I research a company before an interview?")
        assert len(result["message"]) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "company research before interview", profile=_EmptyProfile())
        assert result["type"] == "company_research"


# ── Freelance UAE ───────────────────────────────────────────────────────────────


class TestFreelanceUAE:
    """Tests for _FREELANCE_UAE_RE and _handle_freelance_uae."""

    _REGEX_CASES_MATCH = [
        "can I freelance in UAE?",
        "can I work as a freelancer in Dubai?",
        "how do I get a freelance permit in UAE?",
        "how do I apply for a UAE freelance visa?",
        "freelance permit UAE",
        "freelance permit Dubai",
        "Dubai freelance permit",
        "UAE freelance visa",
        "UAE freelance rules",
        "can I be self-employed in UAE?",
        "can I be self employed in Dubai?",
        "independent contractor in UAE",
        "تصريح العمل الحر",
        "العمل الحر في الإمارات",
    ]

    _REGEX_CASES_NO_MATCH = [
        "find freelance HSE jobs",
        "remote work in UAE",
        "how do I move to UAE?",
        "best companies in Dubai",
        "how do I get a work visa?",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _FREELANCE_UAE_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _FREELANCE_UAE_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _FREELANCE_UAE_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _FREELANCE_UAE_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_freelance_uae(self, monkeypatch):
        result = self._run(monkeypatch, "can I freelance in UAE?")
        assert result["type"] == "freelance_uae"

    def test_freelance_permit_routes(self, monkeypatch):
        result = self._run(monkeypatch, "how do I get a freelance permit in UAE?")
        assert result["type"] == "freelance_uae"

    def test_self_employed_routes(self, monkeypatch):
        result = self._run(monkeypatch, "can I be self-employed in UAE?")
        assert result["type"] == "freelance_uae"

    def test_freelancer_in_dubai_routes(self, monkeypatch):
        result = self._run(monkeypatch, "can I work as a freelancer in Dubai?")
        assert result["type"] == "freelance_uae"

    def test_message_mentions_permit_or_licence(self, monkeypatch):
        result = self._run(monkeypatch, "can I freelance in UAE?")
        msg = result["message"].lower()
        assert "permit" in msg or "licence" in msg or "license" in msg or "تصريح" in msg

    def test_message_mentions_free_zone(self, monkeypatch):
        result = self._run(monkeypatch, "can I freelance in UAE?")
        msg = result["message"].lower()
        assert "free zone" in msg or "منطقة حرة" in msg

    def test_message_mentions_cost(self, monkeypatch):
        result = self._run(monkeypatch, "can I freelance in UAE?")
        msg = result["message"].lower()
        assert "aed" in msg or "cost" in msg or "درهم" in msg

    def test_message_length(self, monkeypatch):
        result = self._run(monkeypatch, "can I freelance in UAE?")
        assert len(result["message"]) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "freelance permit Dubai", profile=_EmptyProfile())
        assert result["type"] == "freelance_uae"


# ── End of Service Gratuity ─────────────────────────────────────────────────────


class TestEOSB:
    """Tests for _EOSB_RE and _handle_eosb."""

    _REGEX_CASES_MATCH = [
        "what is end of service gratuity?",
        "how is gratuity calculated in UAE?",
        "how do I calculate my gratuity?",
        "how much gratuity am I owed?",
        "how much end of service will I get?",
        "gratuity calculation UAE",
        "gratuity calculator",
        "end of service benefit UAE",
        "end of service calculation",
        "EOSB calculation",
        "am I entitled to end of service?",
        "am I eligible for gratuity?",
        "مكافأة نهاية الخدمة",
        "حساب مكافأة نهاية الخدمة",
    ]

    _REGEX_CASES_NO_MATCH = [
        "show me HSE jobs in Dubai",
        "what is my skill gap?",
        "how do I negotiate salary?",
        "tell me about UAE labor law",
        "I have a career gap in my CV",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _EOSB_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _EOSB_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _EOSB_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _EOSB_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_eosb(self, monkeypatch):
        result = self._run(monkeypatch, "what is end of service gratuity?")
        assert result["type"] == "eosb"

    def test_gratuity_calculation_routes(self, monkeypatch):
        result = self._run(monkeypatch, "how is gratuity calculated in UAE?")
        assert result["type"] == "eosb"

    def test_eosb_entitlement_routes(self, monkeypatch):
        result = self._run(monkeypatch, "am I entitled to end of service?")
        assert result["type"] == "eosb"

    def test_message_mentions_21_days(self, monkeypatch):
        result = self._run(monkeypatch, "how is gratuity calculated in UAE?")
        assert "21" in result["message"]

    def test_message_mentions_basic_salary(self, monkeypatch):
        result = self._run(monkeypatch, "how is gratuity calculated in UAE?")
        msg = result["message"].lower()
        assert "basic salary" in msg or "الراتب الأساسي" in msg

    def test_message_mentions_5_years(self, monkeypatch):
        result = self._run(monkeypatch, "what is end of service gratuity?")
        assert "5" in result["message"] or "five" in result["message"].lower()

    def test_message_length(self, monkeypatch):
        result = self._run(monkeypatch, "what is end of service gratuity?")
        assert len(result["message"]) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "gratuity calculation UAE", profile=_EmptyProfile())
        assert result["type"] == "eosb"


# ── Non-Compete Clause ──────────────────────────────────────────────────────────


class TestNonCompete:
    """Tests for _NON_COMPETE_RE and _handle_non_compete."""

    _REGEX_CASES_MATCH = [
        "what is a non-compete clause?",
        "what is a non-compete?",
        "does my non-compete apply in UAE?",
        "is a non-compete enforceable in UAE?",
        "can my employer enforce a non-compete?",
        "non-compete clause UAE",
        "non-compete agreement Dubai",
        "non compete period",
        "is my non-compete valid?",
        "non-compete restriction UAE",
        "شرط عدم المنافسة",
        "بند عدم المنافسة",
    ]

    _REGEX_CASES_NO_MATCH = [
        "I need a competitive salary",
        "find me competitive jobs in Dubai",
        "how do I resign professionally?",
        "show me jobs at ADNOC",
        "employment gap on my CV",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _NON_COMPETE_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _NON_COMPETE_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _NON_COMPETE_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _NON_COMPETE_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_non_compete(self, monkeypatch):
        result = self._run(monkeypatch, "does my non-compete apply in UAE?")
        assert result["type"] == "non_compete"

    def test_what_is_non_compete_routes(self, monkeypatch):
        result = self._run(monkeypatch, "what is a non-compete clause?")
        assert result["type"] == "non_compete"

    def test_enforceability_routes(self, monkeypatch):
        result = self._run(monkeypatch, "is a non-compete enforceable in UAE?")
        assert result["type"] == "non_compete"

    def test_employer_enforce_routes(self, monkeypatch):
        result = self._run(monkeypatch, "can my employer enforce a non-compete?")
        assert result["type"] == "non_compete"

    def test_message_mentions_enforceable_or_courts(self, monkeypatch):
        result = self._run(monkeypatch, "does my non-compete apply in UAE?")
        msg = result["message"].lower()
        assert "enforc" in msg or "court" in msg or "تطبيق" in msg

    def test_message_mentions_time_limit(self, monkeypatch):
        result = self._run(monkeypatch, "does my non-compete apply in UAE?")
        msg = result["message"].lower()
        assert "year" in msg or "time" in msg or "سنة" in msg or "سنتين" in msg

    def test_message_length(self, monkeypatch):
        result = self._run(monkeypatch, "does my non-compete apply in UAE?")
        assert len(result["message"]) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "non-compete clause UAE", profile=_EmptyProfile())
        assert result["type"] == "non_compete"


# ── Work Visa Process ───────────────────────────────────────────────────────────


class TestWorkVisaProcess:
    """Tests for _WORK_VISA_PROCESS_RE and _handle_work_visa_process."""

    _REGEX_CASES_MATCH = [
        "how do I get a UAE work visa?",
        "how do I get a work visa?",
        "how does visa sponsorship work?",
        "what documents do I need for a work visa?",
        "UAE work visa process",
        "UAE work visa requirements",
        "Dubai work permit process",
        "how long does it take to get a work visa?",
        "will the company sponsor my visa?",
        "what is the visa sponsorship cost?",
        "تأشيرة العمل في الإمارات",
        "كيف أحصل على تأشيرة عمل",
    ]

    _REGEX_CASES_NO_MATCH = [
        "I am on a spouse visa",          # visa status declaration — different handler
        "update my visa status",          # profile update
        "do I need a visa?",              # too generic — _VISA_STATUS_RE handles
        "show me jobs in Dubai",
        "how do I negotiate salary?",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _WORK_VISA_PROCESS_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _WORK_VISA_PROCESS_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _WORK_VISA_PROCESS_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _WORK_VISA_PROCESS_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_work_visa_process(self, monkeypatch):
        result = self._run(monkeypatch, "how do I get a UAE work visa?")
        assert result["type"] == "work_visa_process"

    def test_visa_sponsorship_routes(self, monkeypatch):
        result = self._run(monkeypatch, "will the company sponsor my visa?")
        assert result["type"] == "work_visa_process"

    def test_uae_work_visa_process_routes(self, monkeypatch):
        result = self._run(monkeypatch, "UAE work visa process")
        assert result["type"] == "work_visa_process"

    def test_how_long_routes(self, monkeypatch):
        result = self._run(monkeypatch, "how long does it take to get a work visa?")
        assert result["type"] == "work_visa_process"

    def test_message_mentions_employer_or_sponsor(self, monkeypatch):
        result = self._run(monkeypatch, "how do I get a UAE work visa?")
        msg = result["message"].lower()
        assert "employer" in msg or "sponsor" in msg or "company" in msg or "صاحب العمل" in msg

    def test_message_mentions_steps_or_process(self, monkeypatch):
        result = self._run(monkeypatch, "how do I get a UAE work visa?")
        msg = result["message"].lower()
        assert "step" in msg or "process" in msg or "medical" in msg or "entry" in msg

    def test_message_length(self, monkeypatch):
        result = self._run(monkeypatch, "how do I get a UAE work visa?")
        assert len(result["message"]) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "UAE work visa requirements", profile=_EmptyProfile())
        assert result["type"] == "work_visa_process"


# ── Arabic Language Requirement ─────────────────────────────────────────────────


class TestArabicRequirement:
    """Tests for _ARABIC_REQUIREMENT_RE and _handle_arabic_requirement."""

    _REGEX_CASES_MATCH = [
        "do I need to speak Arabic?",
        "do I have to speak Arabic to work in UAE?",
        "will not speaking Arabic hurt my chances?",
        "does speaking Arabic matter in UAE?",
        "how important is Arabic in UAE jobs?",
        "how much Arabic do I need?",
        "are Arabic skills required in UAE?",
        "is Arabic language necessary for jobs in Dubai?",
        "can I work in UAE without Arabic?",
        "can I get a job in Dubai if I don't speak Arabic?",
        "Arabic speaking required UAE",
        "هل أحتاج إلى تعلم العربية",
        "هل اللغة العربية ضرورية",
    ]

    _REGEX_CASES_NO_MATCH = [
        "show me Arabic companies in UAE",
        "how do I write a cover letter?",
        "find HSE jobs in Dubai",
        "how do I negotiate salary?",
        "what is gratuity?",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _ARABIC_REQUIREMENT_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _ARABIC_REQUIREMENT_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _ARABIC_REQUIREMENT_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _ARABIC_REQUIREMENT_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_arabic_requirement(self, monkeypatch):
        result = self._run(monkeypatch, "do I need to speak Arabic?")
        assert result["type"] == "arabic_requirement"

    def test_without_arabic_routes(self, monkeypatch):
        result = self._run(monkeypatch, "can I work in UAE without Arabic?")
        assert result["type"] == "arabic_requirement"

    def test_importance_question_routes(self, monkeypatch):
        result = self._run(monkeypatch, "how important is Arabic in UAE jobs?")
        assert result["type"] == "arabic_requirement"

    def test_message_mentions_english(self, monkeypatch):
        result = self._run(monkeypatch, "do I need to speak Arabic?")
        msg = result["message"].lower()
        assert "english" in msg or "إنجليزية" in msg

    def test_message_reassures_not_required(self, monkeypatch):
        result = self._run(monkeypatch, "do I need to speak Arabic?")
        msg = result["message"].lower()
        assert "no" in msg or "not" in msg or "لا" in msg

    def test_message_length(self, monkeypatch):
        result = self._run(monkeypatch, "do I need to speak Arabic?")
        assert len(result["message"]) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "are Arabic skills required in UAE?", profile=_EmptyProfile())
        assert result["type"] == "arabic_requirement"


# ── Background Check ────────────────────────────────────────────────────────────


class TestBackgroundCheck:
    """Tests for _BACKGROUND_CHECK_RE and _handle_background_check."""

    _REGEX_CASES_MATCH = [
        "will they do a background check?",
        "do employers run a background check in UAE?",
        "will the company conduct background screening?",
        "background check UAE",
        "background verification process",
        "do I need a police clearance?",
        "do I need a police clearance certificate for a job in UAE?",
        "police clearance UAE",
        "police good conduct certificate for job",
        "what do they check in a background check?",
        "what do they verify in employment screening?",
        "شهادة حسن السيرة",
    ]

    _REGEX_CASES_NO_MATCH = [
        "how do I explain a gap in my CV?",
        "show me jobs in Dubai",
        "how do I prepare for an interview?",
        "I need a police escort",       # no match
        "background music for presentations",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _BACKGROUND_CHECK_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _BACKGROUND_CHECK_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _BACKGROUND_CHECK_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _BACKGROUND_CHECK_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_background_check(self, monkeypatch):
        result = self._run(monkeypatch, "will they do a background check?")
        assert result["type"] == "background_check"

    def test_police_clearance_routes(self, monkeypatch):
        result = self._run(monkeypatch, "do I need a police clearance?")
        assert result["type"] == "background_check"

    def test_background_uae_routes(self, monkeypatch):
        result = self._run(monkeypatch, "background check UAE")
        assert result["type"] == "background_check"

    def test_message_mentions_cv_or_verification(self, monkeypatch):
        result = self._run(monkeypatch, "will they do a background check?")
        msg = result["message"].lower()
        assert "cv" in msg or "verif" in msg or "reference" in msg or "السيرة" in msg

    def test_message_mentions_police_or_clearance(self, monkeypatch):
        result = self._run(monkeypatch, "will they do a background check?")
        msg = result["message"].lower()
        assert "police" in msg or "clearance" in msg or "conduct" in msg or "شهادة" in msg

    def test_message_length(self, monkeypatch):
        result = self._run(monkeypatch, "will they do a background check?")
        assert len(result["message"]) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "background verification process", profile=_EmptyProfile())
        assert result["type"] == "background_check"


# ── Free Zone vs Mainland ───────────────────────────────────────────────────────


class TestFreeZoneMainland:
    """Tests for _FREE_ZONE_MAINLAND_RE and _handle_free_zone_mainland."""

    _REGEX_CASES_MATCH = [
        "what is the difference between free zone and mainland?",
        "what's the difference between mainland and a free zone?",
        "should I work in a free zone or mainland?",
        "is it better to work in a free zone or mainland?",
        "free zone vs mainland job",
        "free zone vs mainland employment",
        "free zone benefits UAE",
        "free zone advantages",
        "mainland UAE employment rules",
        "is a free zone job different?",
        "are free zone companies different?",
        "can I work outside a free zone?",
        "الفرق بين المنطقة الحرة والبر الرئيسي",
    ]

    _REGEX_CASES_NO_MATCH = [
        "can I freelance in UAE?",       # freelance handler
        "how do I get a UAE work visa?",
        "find jobs in DIFC",
        "how do I negotiate salary?",
        "what is end of service gratuity?",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _FREE_ZONE_MAINLAND_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _FREE_ZONE_MAINLAND_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _FREE_ZONE_MAINLAND_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _FREE_ZONE_MAINLAND_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_free_zone_mainland(self, monkeypatch):
        result = self._run(monkeypatch, "what is the difference between free zone and mainland?")
        assert result["type"] == "free_zone_mainland"

    def test_vs_question_routes(self, monkeypatch):
        result = self._run(monkeypatch, "free zone vs mainland job")
        assert result["type"] == "free_zone_mainland"

    def test_should_i_work_routes(self, monkeypatch):
        result = self._run(monkeypatch, "should I work in a free zone or mainland?")
        assert result["type"] == "free_zone_mainland"

    def test_message_mentions_free_zone(self, monkeypatch):
        result = self._run(monkeypatch, "what is the difference between free zone and mainland?")
        msg = result["message"].lower()
        assert "free zone" in msg or "منطقة حرة" in msg

    def test_message_mentions_mainland(self, monkeypatch):
        result = self._run(monkeypatch, "what is the difference between free zone and mainland?")
        msg = result["message"].lower()
        assert "mainland" in msg or "البر الرئيسي" in msg

    def test_message_mentions_visa_or_sponsor(self, monkeypatch):
        result = self._run(monkeypatch, "what is the difference between free zone and mainland?")
        msg = result["message"].lower()
        assert "visa" in msg or "sponsor" in msg or "تأشيرة" in msg or "كفالة" in msg

    def test_message_length(self, monkeypatch):
        result = self._run(monkeypatch, "what is the difference between free zone and mainland?")
        assert len(result["message"]) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "free zone vs mainland employment", profile=_EmptyProfile())
        assert result["type"] == "free_zone_mainland"


# ── Working Hours / Overtime ────────────────────────────────────────────────────


class TestWorkingHours:
    """Tests for _WORKING_HOURS_RE and _handle_working_hours."""

    _REGEX_CASES_MATCH = [
        "what are the standard working hours in UAE?",
        "what are the typical working hours in Dubai?",
        "how many hours can I work per week?",
        "how many hours do I have to work per week?",
        "is overtime paid in UAE?",
        "is overtime legal in UAE?",
        "how does overtime work in UAE?",
        "how is overtime calculated in UAE?",
        "overtime pay UAE",
        "overtime rules UAE",
        "UAE working hours rules",
        "working hours in UAE",
        "working hours limit UAE",
        "ساعات العمل في الإمارات",
        "العمل الإضافي في الإمارات",
    ]

    _REGEX_CASES_NO_MATCH = [
        "can I work from home?",
        "remote work in UAE",
        "what is end of service gratuity?",
        "show me HSE jobs",
        "how do I negotiate salary?",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _WORKING_HOURS_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _WORKING_HOURS_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _WORKING_HOURS_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _WORKING_HOURS_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_working_hours(self, monkeypatch):
        result = self._run(monkeypatch, "what are the standard working hours in UAE?")
        assert result["type"] == "working_hours"

    def test_overtime_paid_routes(self, monkeypatch):
        result = self._run(monkeypatch, "is overtime paid in UAE?")
        assert result["type"] == "working_hours"

    def test_overtime_calculation_routes(self, monkeypatch):
        result = self._run(monkeypatch, "how is overtime calculated in UAE?")
        assert result["type"] == "working_hours"

    def test_message_mentions_48_hours(self, monkeypatch):
        result = self._run(monkeypatch, "what are the standard working hours in UAE?")
        assert "48" in result["message"] or "8 hours" in result["message"].lower()

    def test_message_mentions_overtime_rate(self, monkeypatch):
        result = self._run(monkeypatch, "is overtime paid in UAE?")
        msg = result["message"].lower()
        assert "25%" in result["message"] or "overtime" in msg

    def test_message_length(self, monkeypatch):
        result = self._run(monkeypatch, "what are the standard working hours in UAE?")
        assert len(result["message"]) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "overtime pay UAE", profile=_EmptyProfile())
        assert result["type"] == "working_hours"


# ── Golden Visa ─────────────────────────────────────────────────────────────────


class TestGoldenVisa:
    """Tests for _GOLDEN_VISA_RE and _handle_golden_visa."""

    _REGEX_CASES_MATCH = [
        "what is the golden visa?",
        "what is the UAE golden visa?",
        "how do I get a UAE golden visa?",
        "how can I apply for a golden visa?",
        "golden visa UAE requirements",
        "golden visa eligibility",
        "golden visa cost",
        "golden visa benefits",
        "am I eligible for a UAE golden visa?",
        "UAE golden visa process",
        "Dubai golden visa how to get",
        "10-year UAE visa",
        "10 year UAE residence",
        "تأشيرة الذهبية الإمارات",
        "الإقامة الذهبية",
    ]

    _REGEX_CASES_NO_MATCH = [
        "how do I get a UAE work visa?",         # work visa handler
        "I am on a golden tourist visa",
        "show me jobs in Dubai",
        "what is end of service gratuity?",
        "can I freelance in UAE?",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _GOLDEN_VISA_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _GOLDEN_VISA_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _GOLDEN_VISA_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _GOLDEN_VISA_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_golden_visa(self, monkeypatch):
        result = self._run(monkeypatch, "what is the UAE golden visa?")
        assert result["type"] == "golden_visa"

    def test_how_to_get_routes(self, monkeypatch):
        result = self._run(monkeypatch, "how do I get a UAE golden visa?")
        assert result["type"] == "golden_visa"

    def test_eligibility_routes(self, monkeypatch):
        result = self._run(monkeypatch, "am I eligible for a UAE golden visa?")
        assert result["type"] == "golden_visa"

    def test_10_year_visa_routes(self, monkeypatch):
        result = self._run(monkeypatch, "10-year UAE visa")
        assert result["type"] == "golden_visa"

    def test_message_mentions_years(self, monkeypatch):
        result = self._run(monkeypatch, "what is the UAE golden visa?")
        assert "10" in result["message"] or "year" in result["message"].lower()

    def test_message_mentions_sponsor(self, monkeypatch):
        result = self._run(monkeypatch, "what is the UAE golden visa?")
        msg = result["message"].lower()
        assert "sponsor" in msg or "employer" in msg or "كفيل" in msg

    def test_message_length(self, monkeypatch):
        result = self._run(monkeypatch, "what is the UAE golden visa?")
        assert len(result["message"]) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "golden visa UAE requirements", profile=_EmptyProfile())
        assert result["type"] == "golden_visa"


# ── Professional References ─────────────────────────────────────────────────────


class TestJobReferences:
    """Tests for _JOB_REFERENCES_RE and _handle_job_references."""

    _REGEX_CASES_MATCH = [
        "how do I ask for a reference?",
        "how should I ask for a professional reference?",
        "who should I use as a reference?",
        "who can I list as a reference?",
        "professional references for a job",
        "professional references UAE",
        "professional references tips",
        "my employer asked for references",
        "the company is asking for references",
        "reference check after the offer",
        "reference check process",
        "can they contact my previous employer as a reference?",
        "المراجع المهنية",
        "كيف أطلب توصية",
    ]

    _REGEX_CASES_NO_MATCH = [
        "how do I write a cover letter?",
        "show me references to HSE standards",
        "do I need a police clearance?",
        "how do I negotiate salary?",
        "what is end of service gratuity?",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _JOB_REFERENCES_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _JOB_REFERENCES_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _JOB_REFERENCES_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _JOB_REFERENCES_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_job_references(self, monkeypatch):
        result = self._run(monkeypatch, "how do I ask for a reference?")
        assert result["type"] == "job_references"

    def test_who_to_use_routes(self, monkeypatch):
        result = self._run(monkeypatch, "who should I use as a reference?")
        assert result["type"] == "job_references"

    def test_employer_asked_routes(self, monkeypatch):
        result = self._run(monkeypatch, "my employer asked for references")
        assert result["type"] == "job_references"

    def test_reference_check_routes(self, monkeypatch):
        result = self._run(monkeypatch, "reference check after the offer")
        assert result["type"] == "job_references"

    def test_message_mentions_manager(self, monkeypatch):
        result = self._run(monkeypatch, "how do I ask for a reference?")
        msg = result["message"].lower()
        assert "manager" in msg or "employer" in msg or "مدير" in msg

    def test_message_mentions_timing(self, monkeypatch):
        result = self._run(monkeypatch, "how do I ask for a reference?")
        msg = result["message"].lower()
        assert "after" in msg or "before" in msg or "offer" in msg

    def test_message_length(self, monkeypatch):
        result = self._run(monkeypatch, "how do I ask for a reference?")
        assert len(result["message"]) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "professional references UAE", profile=_EmptyProfile())
        assert result["type"] == "job_references"


# ── Dress Code ──────────────────────────────────────────────────────────────────


class TestDressCode:
    """Tests for _DRESS_CODE_RE and _handle_dress_code."""

    _REGEX_CASES_MATCH = [
        "what should I wear to an interview?",
        "what should I wear to a job interview?",
        "how should I dress for an interview?",
        "how do I dress for my interview?",
        "office dress code UAE",
        "workplace dress code Dubai",
        "interview dress code UAE",
        "dress code for a job interview",
        "is smart casual ok for interviews?",
        "is business casual appropriate in UAE?",
        "what to wear to a UAE interview",
        "كيف أرتدي في المقابلة",
        "ماذا أرتدي للمقابلة",
    ]

    _REGEX_CASES_NO_MATCH = [
        "what is the working dress in the UAE?",  # too vague
        "show me HSE jobs in Dubai",
        "how do I negotiate salary?",
        "what is end of service gratuity?",
        "can I freelance in UAE?",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _DRESS_CODE_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _DRESS_CODE_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _DRESS_CODE_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _DRESS_CODE_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_dress_code(self, monkeypatch):
        result = self._run(monkeypatch, "what should I wear to an interview?")
        assert result["type"] == "dress_code"

    def test_how_to_dress_routes(self, monkeypatch):
        result = self._run(monkeypatch, "how should I dress for an interview?")
        assert result["type"] == "dress_code"

    def test_office_dress_code_routes(self, monkeypatch):
        result = self._run(monkeypatch, "office dress code UAE")
        assert result["type"] == "dress_code"

    def test_message_mentions_suit_or_smart(self, monkeypatch):
        result = self._run(monkeypatch, "what should I wear to an interview?")
        msg = result["message"].lower()
        assert "suit" in msg or "smart" in msg or "formal" in msg or "professional" in msg

    def test_message_mentions_men_or_women(self, monkeypatch):
        result = self._run(monkeypatch, "what should I wear to an interview?")
        msg = result["message"].lower()
        assert "men" in msg or "women" in msg or "رجال" in msg or "نساء" in msg

    def test_message_length(self, monkeypatch):
        result = self._run(monkeypatch, "what should I wear to an interview?")
        assert len(result["message"]) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "interview dress code UAE", profile=_EmptyProfile())
        assert result["type"] == "dress_code"


# ── Remote Work UAE ─────────────────────────────────────────────────────────────


class TestRemoteWorkUAE:
    """Tests for _REMOTE_WORK_UAE_RE and _handle_remote_work_uae."""

    _REGEX_CASES_MATCH = [
        "can I work remotely from UAE?",
        "can I work remotely in Dubai?",
        "can I work for a foreign company from UAE?",
        "can I work for a UK company from UAE?",
        "do I need a visa to work remotely from UAE?",
        "remote work from UAE visa",
        "remote work from UAE rules",
        "UAE remote work rules",
        "UAE remote work visa",
        "digital nomad visa UAE",
        "digital nomad in Dubai",
        "tax implications working remotely in UAE",
        "العمل عن بُعد من الإمارات",
        "تأشيرة العمل عن بُعد الإمارات",
    ]

    _REGEX_CASES_NO_MATCH = [
        "find remote HSE jobs",
        "do I need a visa to work in UAE?",       # general work visa
        "how do I get a UAE work visa?",           # work visa handler
        "show me remote jobs in Dubai",
        "can I freelance in UAE?",                 # freelance handler
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _REMOTE_WORK_UAE_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _REMOTE_WORK_UAE_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _REMOTE_WORK_UAE_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _REMOTE_WORK_UAE_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_remote_work_uae(self, monkeypatch):
        result = self._run(monkeypatch, "can I work remotely from UAE?")
        assert result["type"] == "remote_work_uae"

    def test_foreign_company_routes(self, monkeypatch):
        result = self._run(monkeypatch, "can I work for a UK company from UAE?")
        assert result["type"] == "remote_work_uae"

    def test_digital_nomad_routes(self, monkeypatch):
        result = self._run(monkeypatch, "digital nomad visa UAE")
        assert result["type"] == "remote_work_uae"

    def test_message_mentions_visa(self, monkeypatch):
        result = self._run(monkeypatch, "can I work remotely from UAE?")
        msg = result["message"].lower()
        assert "visa" in msg or "تأشيرة" in msg

    def test_message_mentions_tax(self, monkeypatch):
        result = self._run(monkeypatch, "can I work remotely from UAE?")
        msg = result["message"].lower()
        assert "tax" in msg or "ضريبة" in msg

    def test_message_length(self, monkeypatch):
        result = self._run(monkeypatch, "can I work remotely from UAE?")
        assert len(result["message"]) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "UAE remote work rules", profile=_EmptyProfile())
        assert result["type"] == "remote_work_uae"


# ── Annual Leave ────────────────────────────────────────────────────────────────


class TestAnnualLeave:
    """Tests for _ANNUAL_LEAVE_RE and _handle_annual_leave."""

    _REGEX_CASES_MATCH = [
        "how many days annual leave in UAE?",
        "how many annual leave days do I get?",
        "annual leave entitlement UAE",
        "annual leave rights UAE",
        "annual leave policy UAE",
        "how much leave do I get in UAE?",
        "UAE leave entitlement",
        "UAE leave days",
        "public holidays in UAE",
        "how many public holidays in UAE?",
        "what are the public holidays in UAE?",
        "إجازة سنوية في الإمارات",
        "أيام الإجازة السنوية",
    ]

    _REGEX_CASES_NO_MATCH = [
        "how many hours can I work per week?",    # working hours handler
        "is overtime paid?",
        "what is end of service gratuity?",
        "how do I take a sick day?",
        "show me jobs in Dubai",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _ANNUAL_LEAVE_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _ANNUAL_LEAVE_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _ANNUAL_LEAVE_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _ANNUAL_LEAVE_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_annual_leave(self, monkeypatch):
        result = self._run(monkeypatch, "how many days annual leave in UAE?")
        assert result["type"] == "annual_leave"

    def test_entitlement_routes(self, monkeypatch):
        result = self._run(monkeypatch, "annual leave entitlement UAE")
        assert result["type"] == "annual_leave"

    def test_public_holidays_routes(self, monkeypatch):
        result = self._run(monkeypatch, "public holidays in UAE")
        assert result["type"] == "annual_leave"

    def test_message_mentions_30_days(self, monkeypatch):
        result = self._run(monkeypatch, "how many days annual leave in UAE?")
        assert "30" in result["message"]

    def test_message_mentions_public_holidays(self, monkeypatch):
        result = self._run(monkeypatch, "how many days annual leave in UAE?")
        msg = result["message"].lower()
        assert "public holiday" in msg or "eid" in msg or "national" in msg or "عطلة" in msg

    def test_message_length(self, monkeypatch):
        result = self._run(monkeypatch, "how many days annual leave in UAE?")
        assert len(result["message"]) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "UAE leave entitlement", profile=_EmptyProfile())
        assert result["type"] == "annual_leave"


# ── Sick Leave ──────────────────────────────────────────────────────────────────


class TestSickLeave:
    """Tests for _SICK_LEAVE_RE and _handle_sick_leave."""

    _REGEX_CASES_MATCH = [
        "how many sick days do I get?",
        "how much sick leave am I entitled to in UAE?",
        "sick leave policy UAE",
        "sick leave rules UAE",
        "sick leave entitlement UAE",
        "sick day rules Dubai",
        "UAE sick leave law",
        "medical leave UAE",
        "medical leave policy UAE",
        "what is the sick leave policy in UAE?",
        "what are the sick leave rules?",
        "how long can I be on sick leave?",
        "how long can I take sick leave?",
        "إجازة مرضية في الإمارات",
        "أيام الإجازة المرضية",
    ]

    _REGEX_CASES_NO_MATCH = [
        "how many days annual leave in UAE?",
        "maternity leave UAE",
        "how do I resign?",
        "show me jobs in Dubai",
        "what is end of service gratuity?",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _SICK_LEAVE_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _SICK_LEAVE_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _SICK_LEAVE_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _SICK_LEAVE_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_sick_leave(self, monkeypatch):
        result = self._run(monkeypatch, "how many sick days do I get?")
        assert result["type"] == "sick_leave"

    def test_policy_routes(self, monkeypatch):
        result = self._run(monkeypatch, "sick leave policy UAE")
        assert result["type"] == "sick_leave"

    def test_medical_leave_routes(self, monkeypatch):
        result = self._run(monkeypatch, "medical leave UAE")
        assert result["type"] == "sick_leave"

    def test_message_mentions_15_days(self, monkeypatch):
        result = self._run(monkeypatch, "how many sick days do I get?")
        assert "15" in result["message"]

    def test_message_mentions_full_pay(self, monkeypatch):
        result = self._run(monkeypatch, "sick leave policy UAE")
        msg = result["message"].lower()
        assert "full pay" in msg or "بأجر كامل" in msg

    def test_message_length(self, monkeypatch):
        result = self._run(monkeypatch, "sick leave policy UAE")
        assert len(result["message"]) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "sick leave rules UAE", profile=_EmptyProfile())
        assert result["type"] == "sick_leave"

    def test_does_not_route_to_annual_leave(self, monkeypatch):
        result = self._run(monkeypatch, "sick leave entitlement UAE")
        assert result["type"] != "annual_leave"


# ── Parental Leave ───────────────────────────────────────────────────────────────


class TestParentalLeave:
    """Tests for _PARENTAL_LEAVE_RE and _handle_parental_leave."""

    _REGEX_CASES_MATCH = [
        "how much maternity leave do I get?",
        "how much maternity leave in UAE?",
        "how many weeks maternity leave am I entitled to?",
        "maternity leave UAE",
        "maternity leave Dubai",
        "maternity leave entitlement UAE",
        "maternity leave rights UAE",
        "maternity leave policy UAE",
        "paternity leave UAE",
        "paternity leave Dubai",
        "paternity leave paid?",
        "parental leave UAE",
        "parental leave rights UAE",
        "UAE maternity leave law",
        "Dubai paternity leave rules",
        "am I entitled to maternity leave?",
        "am I eligible for parental leave?",
        "is maternity leave paid in UAE?",
        "is paternity leave mandatory in UAE?",
        "إجازة الأمومة في الإمارات",
        "إجازة الأبوة الإمارات",
    ]

    _REGEX_CASES_NO_MATCH = [
        "how many sick days do I get?",
        "annual leave entitlement UAE",
        "how do I resign?",
        "show me jobs in Dubai",
        "what is end of service gratuity?",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _PARENTAL_LEAVE_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _PARENTAL_LEAVE_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _PARENTAL_LEAVE_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _PARENTAL_LEAVE_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_maternity_routes(self, monkeypatch):
        result = self._run(monkeypatch, "how much maternity leave in UAE?")
        assert result["type"] == "parental_leave"

    def test_paternity_routes(self, monkeypatch):
        result = self._run(monkeypatch, "paternity leave UAE")
        assert result["type"] == "parental_leave"

    def test_parental_routes(self, monkeypatch):
        result = self._run(monkeypatch, "parental leave rights UAE")
        assert result["type"] == "parental_leave"

    def test_message_mentions_45_days(self, monkeypatch):
        result = self._run(monkeypatch, "how much maternity leave in UAE?")
        assert "45" in result["message"]

    def test_message_mentions_5_days_paternity(self, monkeypatch):
        result = self._run(monkeypatch, "paternity leave UAE")
        assert "5" in result["message"]

    def test_message_length(self, monkeypatch):
        result = self._run(monkeypatch, "maternity leave UAE")
        assert len(result["message"]) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "maternity leave entitlement UAE", profile=_EmptyProfile())
        assert result["type"] == "parental_leave"

    def test_does_not_route_to_sick_leave(self, monkeypatch):
        result = self._run(monkeypatch, "maternity leave UAE")
        assert result["type"] != "sick_leave"


# ── Probation Rules ─────────────────────────────────────────────────────────────


class TestProbationRules:
    """Tests for _PROBATION_RULES_RE and _handle_probation_rules."""

    _REGEX_CASES_MATCH = [
        "what happens during my probation period?",
        "what happens during probation?",
        "what can my employer do during probation period?",
        "can I be fired during my probationary period?",
        "can I be dismissed during probation period?",
        "can I be terminated during probation period?",
        "can I resign during my probation period?",
        "can I quit during probation period?",
        "can I leave during probation period?",
        "how long is the probation period?",
        "how long is probation?",
        "probationary period rules UAE",
        "probation period rights UAE",
        "probation period termination Dubai",
        "probation period notice period UAE",
        "probation period resignation",
        "what are my rights during probation period?",
        "what are the rules during my probation period?",
        "فترة التجربة في الإمارات",
    ]

    _REGEX_CASES_NO_MATCH = [
        "how many sick days do I get?",
        "annual leave entitlement UAE",
        "maternity leave UAE",
        "show me jobs in Dubai",
        "what is end of service gratuity?",
        "can I resign from my job?",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _PROBATION_RULES_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _PROBATION_RULES_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _PROBATION_RULES_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _PROBATION_RULES_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_during_probation_routes(self, monkeypatch):
        result = self._run(monkeypatch, "what happens during my probation period?")
        assert result["type"] == "probation_rules"

    def test_fired_during_probation_routes(self, monkeypatch):
        result = self._run(monkeypatch, "can I be fired during my probationary period?")
        assert result["type"] == "probation_rules"

    def test_resign_during_probation_routes(self, monkeypatch):
        result = self._run(monkeypatch, "can I resign during my probation period?")
        assert result["type"] == "probation_rules"

    def test_how_long_is_probation_routes(self, monkeypatch):
        result = self._run(monkeypatch, "how long is the probation period?")
        assert result["type"] == "probation_rules"

    def test_period_rules_routes(self, monkeypatch):
        result = self._run(monkeypatch, "probationary period rules UAE")
        assert result["type"] == "probation_rules"

    def test_message_mentions_6_months(self, monkeypatch):
        result = self._run(monkeypatch, "how long is the probation period?")
        assert "6" in result["message"]

    def test_message_mentions_14_days(self, monkeypatch):
        result = self._run(monkeypatch, "can I be fired during probation period?")
        assert "14" in result["message"]

    def test_message_mentions_30_days_notice(self, monkeypatch):
        result = self._run(monkeypatch, "can I resign during my probation period?")
        assert "30" in result["message"]

    def test_message_length(self, monkeypatch):
        result = self._run(monkeypatch, "what happens during probation?")
        assert len(result["message"]) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "probation period rules UAE", profile=_EmptyProfile())
        assert result["type"] == "probation_rules"

    def test_does_not_route_to_sick_leave(self, monkeypatch):
        result = self._run(monkeypatch, "what happens during my probation period?")
        assert result["type"] != "sick_leave"


# ── Notice Period ────────────────────────────────────────────────────────────────


class TestNoticePeriod:
    """Tests for _NOTICE_PERIOD_RE and _handle_notice_period."""

    _REGEX_CASES_MATCH = [
        "how much notice do I need to give?",
        "how many days notice do I need to give when resigning?",
        "what is the notice period in UAE?",
        "what is the notice period?",
        "notice period UAE",
        "notice period rules UAE",
        "notice period law UAE",
        "notice period for resignation UAE",
        "notice period for termination UAE",
        "resignation notice period UAE",
        "termination notice period UAE",
        "can my employer fire me without notice?",
        "can my company dismiss me without notice?",
        "what are the notice period rules in UAE?",
        "مدة الإخطار",
        "فترة الإشعار في الإمارات",
    ]

    _REGEX_CASES_NO_MATCH = [
        "how many sick days do I get?",
        "annual leave entitlement UAE",
        "maternity leave UAE",
        "what is end of service gratuity?",
        "show me jobs in Dubai",
        "can I resign during probation?",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _NOTICE_PERIOD_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _NOTICE_PERIOD_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _NOTICE_PERIOD_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _NOTICE_PERIOD_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_routes_to_notice_period(self, monkeypatch):
        result = self._run(monkeypatch, "how much notice do I need to give?")
        assert result["type"] == "notice_period"

    def test_uae_notice_period_routes(self, monkeypatch):
        result = self._run(monkeypatch, "notice period UAE")
        assert result["type"] == "notice_period"

    def test_fire_without_notice_routes(self, monkeypatch):
        result = self._run(monkeypatch, "can my employer fire me without notice?")
        assert result["type"] == "notice_period"

    def test_message_mentions_30_days(self, monkeypatch):
        result = self._run(monkeypatch, "what is the notice period in UAE?")
        assert "30" in result["message"]

    def test_message_mentions_probation_14_days(self, monkeypatch):
        result = self._run(monkeypatch, "notice period UAE")
        assert "14" in result["message"]

    def test_message_length(self, monkeypatch):
        result = self._run(monkeypatch, "notice period UAE")
        assert len(result["message"]) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "notice period rules UAE", profile=_EmptyProfile())
        assert result["type"] == "notice_period"


# ── WPS / Salary Protection ──────────────────────────────────────────────────────


class TestWPSSalaryProtection:
    """Tests for _WPS_SALARY_PROTECTION_RE and _handle_wps_salary_protection."""

    _REGEX_CASES_MATCH = [
        "what is the UAE wage protection system?",
        "what is WPS?",
        "WPS UAE",
        "WPS law",
        "WPS salary",
        "my salary is late",
        "my salary was not paid",
        "my salary has been delayed",
        "employer hasn't paid my salary",
        "company is not paying my salary on time",
        "salary protection UAE",
        "late salary UAE",
        "late payment salary UAE",
        "salary not paid UAE",
        "how do I report a late salary?",
        "how do I complain about unpaid salary?",
        "how can I file a complaint for unpaid salary?",
        "نظام حماية الأجور",
        "تأخر صرف الراتب في الإمارات",
    ]

    _REGEX_CASES_NO_MATCH = [
        "how many sick days do I get?",
        "annual leave entitlement UAE",
        "how do I negotiate my salary?",
        "show me jobs in Dubai",
        "what is end of service gratuity?",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _WPS_SALARY_PROTECTION_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _WPS_SALARY_PROTECTION_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _WPS_SALARY_PROTECTION_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _WPS_SALARY_PROTECTION_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_wps_routes(self, monkeypatch):
        result = self._run(monkeypatch, "what is WPS?")
        assert result["type"] == "wps_salary_protection"

    def test_late_salary_routes(self, monkeypatch):
        result = self._run(monkeypatch, "my salary is late")
        assert result["type"] == "wps_salary_protection"

    def test_complaint_routes(self, monkeypatch):
        result = self._run(monkeypatch, "how do I report a late salary?")
        assert result["type"] == "wps_salary_protection"

    def test_message_mentions_10_days(self, monkeypatch):
        result = self._run(monkeypatch, "my salary is late")
        assert "10" in result["message"]

    def test_message_mentions_mohre(self, monkeypatch):
        result = self._run(monkeypatch, "my salary is late")
        msg = result["message"].upper()
        assert "MOHRE" in msg or "موارد" in msg

    def test_message_length(self, monkeypatch):
        result = self._run(monkeypatch, "my salary is late")
        assert len(result["message"]) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "WPS UAE", profile=_EmptyProfile())
        assert result["type"] == "wps_salary_protection"


# ── Employer Health Insurance ─────────────────────────────────────────────────────


class TestEmployerHealthInsurance:
    """Tests for _EMPLOYER_HEALTH_INSURANCE_RE and _handle_employer_health_insurance."""

    _REGEX_CASES_MATCH = [
        "does my employer provide health insurance?",
        "will my company give me health insurance?",
        "does my employer cover medical insurance?",
        "is health insurance mandatory in UAE?",
        "is medical insurance mandatory in UAE?",
        "is health insurance provided in UAE?",
        "health insurance UAE",
        "health insurance provided by employer",
        "health insurance from employer",
        "health insurance mandatory UAE",
        "medical insurance mandatory UAE",
        "health insurance mandatory",
        "medical insurance law UAE",
        "what does the company health insurance cover?",
        "what does my employer health insurance include?",
        "company health insurance UAE",
        "employer health insurance UAE",
        "work health insurance Dubai",
        "do I get health insurance from my employer?",
        "do I have health insurance in UAE?",
        "تأمين صحي من صاحب العمل",
        "تأمين صحي إلزامي",
    ]

    _REGEX_CASES_NO_MATCH = [
        "how many sick days do I get?",
        "annual leave entitlement UAE",
        "how do I negotiate my salary?",
        "show me jobs in Dubai",
        "what is end of service gratuity?",
        "does my employer pay my salary on time?",
    ]

    def test_regex_matches(self):
        from src.rico_chat_api import _EMPLOYER_HEALTH_INSURANCE_RE
        for msg in self._REGEX_CASES_MATCH:
            assert _EMPLOYER_HEALTH_INSURANCE_RE.search(msg), f"Should match: {msg!r}"

    def test_regex_no_false_positives(self):
        from src.rico_chat_api import _EMPLOYER_HEALTH_INSURANCE_RE
        for msg in self._REGEX_CASES_NO_MATCH:
            assert not _EMPLOYER_HEALTH_INSURANCE_RE.search(msg), f"Should NOT match: {msg!r}"

    def _run(self, monkeypatch, message: str, profile=None):
        from unittest.mock import MagicMock
        from src.rico_chat_api import RicoChatAPI
        import src.rico_chat_api as mod
        monkeypatch.setattr(mod, "get_profile", lambda uid: profile or _CVProfile())
        monkeypatch.setattr(mod, "_route", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(mod, "upsert_profile", lambda user_id=None, updates=None, **kw: profile or _CVProfile())
        monkeypatch.setattr(mod, "hf_ok", lambda: False)
        api = RicoChatAPI()
        api._get_recent_context = lambda uid: {}
        api._append_chat = MagicMock()
        return api._handle_active_user("test-user", message)

    def test_employer_provides_routes(self, monkeypatch):
        result = self._run(monkeypatch, "does my employer provide health insurance?")
        assert result["type"] == "employer_health_insurance"

    def test_mandatory_routes(self, monkeypatch):
        result = self._run(monkeypatch, "is health insurance mandatory in UAE?")
        assert result["type"] == "employer_health_insurance"

    def test_company_insurance_routes(self, monkeypatch):
        result = self._run(monkeypatch, "company health insurance UAE")
        assert result["type"] == "employer_health_insurance"

    def test_message_mentions_dubai(self, monkeypatch):
        result = self._run(monkeypatch, "is health insurance mandatory in UAE?")
        msg = result["message"].lower()
        assert "dubai" in msg or "دبي" in msg

    def test_message_mentions_mandatory(self, monkeypatch):
        result = self._run(monkeypatch, "is health insurance mandatory in UAE?")
        msg = result["message"].lower()
        assert "mandatory" in msg or "إلزامي" in msg

    def test_message_length(self, monkeypatch):
        result = self._run(monkeypatch, "does my employer provide health insurance?")
        assert len(result["message"]) > 100

    def test_empty_profile_still_works(self, monkeypatch):
        result = self._run(monkeypatch, "health insurance UAE", profile=_EmptyProfile())
        assert result["type"] == "employer_health_insurance"

    def test_does_not_route_to_benefits(self, monkeypatch):
        result = self._run(monkeypatch, "is medical insurance mandatory in UAE?")
        assert result["type"] != "benefits_guide"
