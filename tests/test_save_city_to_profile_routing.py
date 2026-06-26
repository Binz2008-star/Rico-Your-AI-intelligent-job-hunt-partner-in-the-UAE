"""
Regression: "save it/Dubai to my profile" must NOT be classified as save_job.

Production bug: "My favorite city is Dubai can u save it to my profile please"
triggered _SAVE_JOB_RE (matched save + it) → intent=save_job → Rico saved a
tracked job (Mastercard Director) instead of updating preferred_cities.

After the fix, _SAVE_TO_PROFILE_RE intercepts these messages before _SAVE_JOB_RE
and returns profile_update intent so the profile update flow handles them.
"""
from __future__ import annotations

import pytest

from src.agent.intelligence.intent_classifier import (
    _SAVE_TO_PROFILE_RE,
    classify_intent,
)


# ──────────────────────────────────────────────────────────────────────────────
# Regex unit tests
# ──────────────────────────────────────────────────────────────────────────────

class TestSaveToProfileRegex:
    @pytest.mark.parametrize("msg", [
        "save it to my profile",
        "can u save it to my profile please",
        "My favorite city is Dubai can u save it to my profile please",
        "save Dubai to my profile",
        "save this to my preferences",
        "save it to my account",
        "save it to my settings",
        "save it as my preferred city",
        "save Dubai as my preferred location",
        # Arabic patterns
        "احفظ دبي في ملفي",
        "احفظها في تفضيلاتي",
        "احفظ في حسابي",
    ])
    def test_profile_save_matches(self, msg: str):
        assert _SAVE_TO_PROFILE_RE.search(msg), f"{msg!r} should match save-to-profile regex"

    @pytest.mark.parametrize("msg", [
        "save this job to my pipeline",
        "save this to my pipeline",
        "add this to pipeline",
        "save this as a target job in my pipeline",
        "save the second job to my pipeline",
        "bookmark this role",
        "save it",
        "save this",
    ])
    def test_job_save_does_not_match(self, msg: str):
        assert not _SAVE_TO_PROFILE_RE.search(msg), f"{msg!r} should NOT match save-to-profile regex"


# ──────────────────────────────────────────────────────────────────────────────
# End-to-end classify_intent routing
# ──────────────────────────────────────────────────────────────────────────────

class TestClassifyIntentSaveRouting:
    @pytest.mark.parametrize("msg", [
        "save it to my profile",
        "My favorite city is Dubai can u save it to my profile please",
        "save Dubai to my profile",
        "save this to my preferences",
    ])
    def test_save_to_profile_returns_profile_update(self, msg: str):
        result = classify_intent(msg)
        assert result.intent == "profile_update", (
            f"{msg!r} should be profile_update, got {result.intent!r}"
        )

    @pytest.mark.parametrize("msg", [
        "save this job to my pipeline",
        "save this to my pipeline",
        "bookmark this role",
    ])
    def test_job_save_still_returns_save_job(self, msg: str):
        result = classify_intent(msg)
        assert result.intent == "save_job", (
            f"{msg!r} should be save_job, got {result.intent!r}"
        )

    def test_ordinal_save_unaffected(self):
        result = classify_intent("save the second job to my pipeline")
        assert result.intent == "save_job"
        assert result.entities.get("ordinal") == 2
