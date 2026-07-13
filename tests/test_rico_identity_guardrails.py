"""
tests/test_rico_identity_guardrails.py

Tests for PR A: system prompt trust guardrails.

Coverage:
- RICO_IDENTITY and get_rico_system_prompt() contain required trust anchors
- Subscription pricing facts (AED 29 / AED 49)
- Auto-apply is described as not currently active / requires verified integration
- Company/product identity (Rico Hunt, ricohunt.com)
- Anti-hallucination job listing guardrail
- No claim of automatic submission being live
- No exposure of internal system rules to users
"""
from __future__ import annotations

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.rico_identity import RICO_IDENTITY, get_rico_system_prompt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROMPT = get_rico_system_prompt()
PROMPT_LOWER = PROMPT.lower()
IDENTITY_LOWER = RICO_IDENTITY.lower()


# ---------------------------------------------------------------------------
# Product identity
# ---------------------------------------------------------------------------

class TestProductIdentity:
    def test_rico_hunt_in_identity(self):
        assert "rico hunt" in IDENTITY_LOWER, "RICO_IDENTITY must name the product 'Rico Hunt'"

    def test_ricohunt_com_in_identity(self):
        assert "ricohunt.com" in IDENTITY_LOWER, "RICO_IDENTITY must include ricohunt.com"

    def test_rico_hunt_in_system_prompt(self):
        assert "rico hunt" in PROMPT_LOWER

    def test_ricohunt_com_in_system_prompt(self):
        assert "ricohunt.com" in PROMPT_LOWER


# ---------------------------------------------------------------------------
# Subscription pricing
# ---------------------------------------------------------------------------

class TestSubscriptionFacts:
    def test_rico_monthly_price_usd_in_identity(self):
        assert "USD 21.50" in RICO_IDENTITY, "RICO_IDENTITY must state USD 21.50 Rico Monthly price"
        assert "79" in RICO_IDENTITY, "RICO_IDENTITY must include AED 79 as approximate reference"

    def test_subscription_page_hint_present(self):
        assert "subscription" in IDENTITY_LOWER, "RICO_IDENTITY must reference the /subscription page"

    def test_billing_channel_mentioned(self):
        # Users should know how to upgrade (WhatsApp / platform)
        assert "whatsapp" in IDENTITY_LOWER or "billing" in IDENTITY_LOWER

    def test_free_plan_mentioned(self):
        assert "free" in IDENTITY_LOWER


# ---------------------------------------------------------------------------
# Auto-apply guardrail
# ---------------------------------------------------------------------------

class TestAutoApplyGuardrail:
    def test_auto_submit_not_claimed_active(self):
        """Rico must not claim automatic submission to portals is currently live."""
        identity = RICO_IDENTITY.lower()
        # Must NOT contain uncaveated "auto-apply is available" or "will automatically submit"
        assert "automatically submit" not in identity or "cannot automatically submit" in identity, (
            "RICO_IDENTITY must not claim automatic submission is available"
        )

    def test_cannot_submit_language_present(self):
        assert "cannot automatically submit" in IDENTITY_LOWER or "not currently active" in IDENTITY_LOWER, (
            "RICO_IDENTITY must clarify that auto-submission to portals is not currently active"
        )

    def test_system_prompt_no_uncaveated_auto_apply(self):
        # The system prompt safety rules must prohibit claiming auto-apply is live
        assert "auto-apply" in PROMPT_LOWER or "automatic submission" in PROMPT_LOWER, (
            "System prompt safety rules must address auto-apply claims"
        )
        assert "unless explicitly confirmed" in PROMPT_LOWER or "not currently active" in PROMPT_LOWER

    def test_prepare_track_draft_mentioned(self):
        """Rico's actual apply-assistance capabilities must be described."""
        assert "prepare" in IDENTITY_LOWER
        assert "track" in IDENTITY_LOWER
        assert "draft" in IDENTITY_LOWER


# ---------------------------------------------------------------------------
# Anti-hallucination job listing guardrail
# ---------------------------------------------------------------------------

class TestAntiHallucinationGuardrail:
    def test_never_fabricate_in_identity(self):
        assert "never fabricat" in IDENTITY_LOWER, (
            "RICO_IDENTITY must explicitly prohibit fabricating job listings"
        )

    def test_verified_source_required_in_identity(self):
        assert "verified" in IDENTITY_LOWER, (
            "RICO_IDENTITY must state jobs must come from verified sources"
        )

    def test_no_placeholder_links_rule(self):
        assert "verified" in IDENTITY_LOWER and ("link" in IDENTITY_LOWER or "url" in IDENTITY_LOWER)

    def test_system_prompt_safety_rule_2_prohibits_fabrication(self):
        """Safety rule #2 in the system prompt must forbid fabricating job data."""
        assert "never fabricate job" in PROMPT_LOWER or "fabricat" in PROMPT_LOWER

    def test_system_prompt_requires_tool_data_for_jobs(self):
        assert "search tool" in PROMPT_LOWER or "search results" in PROMPT_LOWER or "verified search" in PROMPT_LOWER

    def test_model_generated_listings_prohibited_in_prompt(self):
        assert "model-generated" in PROMPT_LOWER or "never present" in PROMPT_LOWER


# ---------------------------------------------------------------------------
# Internal rule non-disclosure
# ---------------------------------------------------------------------------

class TestInternalRuleNonDisclosure:
    def test_no_reveal_of_internal_rules(self):
        assert "never reveal" in IDENTITY_LOWER or "never reveals" in IDENTITY_LOWER or "do not reveal" in IDENTITY_LOWER, (
            "RICO_IDENTITY must instruct Rico not to reveal internal system instructions"
        )

    def test_no_file_names_in_prompt(self):
        """System prompt must not reference internal Python file names."""
        for fname in ("rico_chat_api", "rico_identity", "apply_service", "subscription_plans"):
            assert fname not in PROMPT_LOWER, f"System prompt must not expose internal file name: {fname}"


# ---------------------------------------------------------------------------
# get_rico_system_prompt with user_context
# ---------------------------------------------------------------------------

class TestSystemPromptUserContext:
    def test_user_context_injected(self):
        prompt = get_rico_system_prompt(user_context="name: Test User\ntarget_role: HSE Manager")
        assert "Test User" in prompt
        assert "HSE Manager" in prompt

    def test_no_user_context_prompt_still_valid(self):
        prompt = get_rico_system_prompt()
        assert "Rico Hunt" in prompt
        assert "79" in prompt
