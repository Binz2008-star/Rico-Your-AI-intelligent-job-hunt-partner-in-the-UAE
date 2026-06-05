"""Tests for Rico identity, pricing, and guardrails."""
import pytest
from src.rico_identity import RICO_IDENTITY, get_rico_system_prompt


class TestRicoIdentity:
    """Test Rico identity contains required facts and constraints."""

    def test_contains_rico_hunt_identity(self):
        """Rico identity must mention Rico Hunt and ricohunt.com."""
        assert "Rico Hunt" in RICO_IDENTITY
        assert "ricohunt.com" in RICO_IDENTITY

    def test_contains_subscription_pricing(self):
        """Rico identity must contain AED 29 and AED 49 pricing."""
        assert "AED 29" in RICO_IDENTITY
        assert "AED 49" in RICO_IDENTITY
        assert "Pro plan" in RICO_IDENTITY
        assert "Premium plan" in RICO_IDENTITY
        assert "Free plan" in RICO_IDENTITY

    def test_no_auto_apply_claims(self):
        """Rico identity must not claim auto-apply capability via autonomy level."""
        assert "autonomy level" not in RICO_IDENTITY.lower()
        # "auto-apply" is allowed in the "cannot do" section to explicitly disable it
        assert "What Rico cannot do" in RICO_IDENTITY
        assert "Auto-apply on behalf of users" in RICO_IDENTITY

    def test_anti_hallucination_guardrails(self):
        """Rico identity must contain anti-hallucination constraints."""
        assert "Never fabricates job postings" in RICO_IDENTITY
        assert "salaries" in RICO_IDENTITY
        assert "companies" in RICO_IDENTITY
        assert "links" in RICO_IDENTITY
        assert "verified source" in RICO_IDENTITY
        assert "cannot verify" in RICO_IDENTITY

    def test_can_do_capabilities(self):
        """Rico identity must list what it can do."""
        assert "Prepare application drafts" in RICO_IDENTITY
        assert "Track applications" in RICO_IDENTITY
        assert "Guide users" in RICO_IDENTITY
        assert "Draft recruiter messages" in RICO_IDENTITY
        assert "Open apply links" in RICO_IDENTITY

    def test_cannot_do_capabilities(self):
        """Rico identity must list what it cannot do."""
        assert "What Rico cannot do" in RICO_IDENTITY
        assert "Submit applications directly" in RICO_IDENTITY
        assert "LinkedIn" in RICO_IDENTITY
        assert "job portals" in RICO_IDENTITY
        assert "verified integration" in RICO_IDENTITY

    def test_system_prompt_includes_identity(self):
        """System prompt must include RICO_IDENTITY."""
        prompt = get_rico_system_prompt()
        assert "Rico Hunt" in prompt
        assert "ricohunt.com" in prompt

    def test_system_prompt_safety_rules(self):
        """System prompt must include anti-hallucination safety rules."""
        prompt = get_rico_system_prompt()
        assert "Never fabricate job postings" in prompt
        assert "salaries" in prompt
        assert "companies" in prompt
        assert "links" in prompt
        assert "verified source" in prompt
        assert "cannot verify" in prompt

    def test_no_hidden_system_rules(self):
        """Identity must not mention internal file names or hidden rules."""
        assert "rico_identity.py" not in RICO_IDENTITY.lower()
        assert "internal" not in RICO_IDENTITY.lower()
        assert "system file" not in RICO_IDENTITY.lower()
