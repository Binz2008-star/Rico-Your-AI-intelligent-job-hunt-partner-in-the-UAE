"""Tests for the scoped Engineering Review Mode module.

Verifies that:
1. The deterministic detector activates ONLY for repository / engineering
   review contexts (PR, CI, GitHub, branch, merge, diff, ...).
2. The detector stays OFF for normal Rico career chat (job search, CV,
   applications, subscription, interview, acknowledgements).
3. The exported prompt carries the MERGE / SPLIT / BLOCK / DEFER decision
   template and the risk-based triage rules.
4. The live Rico career system prompt remains unchanged — i.e. none of the
   engineering-review behavior leaks into get_rico_system_prompt().
"""
from __future__ import annotations

import pytest

from src.agent.intelligence.engineering_review_mode import (
    get_engineering_review_prompt,
    is_engineering_review_context,
    maybe_review_prompt_section,
)


# ---------------------------------------------------------------------------
# 1. Detector — engineering/repo-review contexts must activate
# ---------------------------------------------------------------------------

class TestEngineeringContextDetected:
    @pytest.mark.parametrize("message", [
        "Can you review this PR?",
        "Should I merge or split these PRs?",
        "Should we merge PR A or PR B first?",
        "What's the merge order for #353 and #354?",
        "Review the pull request before we merge it",
        "The CI pipeline is failing on this branch",
        "The GitHub Actions build is failing",
        "checks are failing on the latest commit",
        "Here's the diff for the feature branch",
        "Please rebase onto main and squash the commits",
        "Review the changed files in this branch",
        "There's a merge conflict in the diff",
        "Can you do a code review of this branch?",
        "Should I block or defer the migration PR?",
    ])
    def test_engineering_messages_activate(self, message):
        assert is_engineering_review_context(message) is True, message

    def test_pr_reference_overrides_career_words(self):
        # An explicit PR reference is authoritative even when career-ish words
        # (e.g. "role") appear in the same sentence.
        assert is_engineering_review_context(
            "merge the role-based-access PR #412 onto main"
        ) is True

    def test_structured_signal_forces_activation(self):
        assert is_engineering_review_context("anything here", signals=["pull_request"]) is True
        assert is_engineering_review_context("status update", signals=["ci"]) is True


# ---------------------------------------------------------------------------
# 2. Detector — normal career chat must NOT activate
# ---------------------------------------------------------------------------

class TestCareerContextNotDetected:
    @pytest.mark.parametrize("message", [
        "Find me HSE manager jobs in Dubai",
        "Show me software engineer roles in Abu Dhabi",
        "Can you review my CV?",
        "Please update my resume and cover letter",
        "I want to apply for a software engineer role",
        "How do I track my job application?",
        "What jobs match my profile?",
        "Upgrade my subscription plan",
        "How much does the billing plan cost?",
        "Prepare me for an interview",
        "What salary should I expect?",
        "thanks!",
        "ok",
        "hello",
        "Block this job",            # job action, not a triage 'block'
        "Skip the first one",        # job action, not engineering
        "Apply for this position",   # career apply, not 'apply the patch'
    ])
    def test_career_messages_do_not_activate(self, message):
        assert is_engineering_review_context(message) is False, message

    def test_empty_and_none_are_off(self):
        assert is_engineering_review_context("") is False
        assert is_engineering_review_context(None) is False  # type: ignore[arg-type]

    def test_bare_decision_verb_without_repo_hint_is_off(self):
        # "merge" alone (no PR/branch/diff/repo hint) must not activate.
        assert is_engineering_review_context("merge my two contacts") is False


# ---------------------------------------------------------------------------
# 3. Exported prompt contents
# ---------------------------------------------------------------------------

class TestPromptContents:
    def test_prompt_includes_decision_template(self):
        prompt = get_engineering_review_prompt()
        assert "Decision: MERGE / SPLIT / BLOCK / DEFER" in prompt

    def test_prompt_includes_template_sections(self):
        prompt = get_engineering_review_prompt()
        for section in ("Reason:", "Scope allowed:", "Scope not allowed:",
                        "Required checks:", "Merge order:"):
            assert section in prompt, section

    def test_prompt_includes_triage_rules_and_gates(self):
        prompt = get_engineering_review_prompt()
        assert "risk-based PR triage" in prompt
        assert "CI green" in prompt
        assert "never all at once" in prompt

    def test_maybe_section_returns_prompt_for_engineering(self):
        section = maybe_review_prompt_section("Should I merge this PR?")
        assert "MERGE / SPLIT / BLOCK / DEFER" in section

    def test_maybe_section_empty_for_career(self):
        assert maybe_review_prompt_section("Find me jobs in Dubai") == ""


# ---------------------------------------------------------------------------
# 4. Live Rico career prompt must remain unchanged (no leakage)
# ---------------------------------------------------------------------------

class TestCareerPromptUnchanged:
    def test_career_system_prompt_has_no_engineering_review_text(self):
        from src.rico_identity import get_rico_system_prompt
        prompt = get_rico_system_prompt()
        # The career-agent identity must not carry any review-mode behavior.
        assert "MERGE / SPLIT / BLOCK / DEFER" not in prompt
        assert "Engineering Review Mode" not in prompt
        assert "PR triage" not in prompt
        # Sanity: it is still the career agent.
        assert "career agent" in prompt

    def test_career_identity_constant_unchanged(self):
        from src.rico_identity import RICO_IDENTITY
        assert "Engineering Review Mode" not in RICO_IDENTITY
        assert "PR triage" not in RICO_IDENTITY
