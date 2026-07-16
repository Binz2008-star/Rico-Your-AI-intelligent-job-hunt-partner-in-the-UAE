"""Plan-copy truth guard (issue #1067).

User-facing Rico Monthly copy must never promise more than the entitlements
enforced in src/subscription_plans.py. These tests derive the expected numbers
from the canonical plan object itself (no duplicated magic numbers), so if the
enforced limits ever change, the copy assertions travel with them.

Scope: the single paid plan's marketing/feature strings, Rico's assistant
identity, and the storage quota upgrade hints. Enforcement numbers are NOT
asserted here beyond reading them off the canonical object.
"""
from __future__ import annotations

from src.rico_identity import RICO_IDENTITY
from src.services.subscription_gating import _UPGRADE_HINTS
from src.subscription_plans import RICO_MONTHLY_PLAN

# Words that would signal a promise the backend does not enforce for the single
# paid plan (no unlimited usage, no premium/automation tier).
_FORBIDDEN_CLAIM_WORDS = ("unlimited", "premium", "auto-apply", "automation")


def _features_text() -> str:
    return " ".join(RICO_MONTHLY_PLAN.features).lower()


def test_rico_monthly_features_make_no_over_promise():
    text = _features_text()
    for word in _FORBIDDEN_CLAIM_WORDS:
        assert word not in text, f"Rico Monthly feature copy still advertises '{word}': {text!r}"


def test_rico_monthly_numeric_features_match_enforced_limits():
    ent = RICO_MONTHLY_PLAN.entitlements
    text = _features_text()
    # Numeric bullets must reference the enforced limits, not inflated figures.
    assert str(ent.monthly_ai_message_limit) in text  # 300 AI messages
    assert str(ent.profile_optimization_limit) in text  # 20 CV & profile optimizations


def test_disabled_capabilities_are_not_advertised():
    ent = RICO_MONTHLY_PLAN.entitlements
    # Guard rails: if these flip on, whoever enables them must revisit the copy.
    assert ent.premium_recommendations_enabled is False
    assert ent.application_automation_enabled is False


def test_identity_states_enforced_message_limit_not_the_retired_figure():
    ent = RICO_MONTHLY_PLAN.entitlements
    assert str(ent.monthly_ai_message_limit) in RICO_IDENTITY  # "300"
    # The retired 1,500 promise must not resurface in the assistant identity.
    assert "1,500" not in RICO_IDENTITY
    assert "1500" not in RICO_IDENTITY


def test_storage_upgrade_hints_reference_no_phantom_premium_tier():
    for hint in _UPGRADE_HINTS.values():
        low = hint.lower()
        assert "premium" not in low, f"Upgrade hint references a non-existent Premium tier: {hint!r}"
        assert "unlimited" not in low, f"Upgrade hint promises unlimited storage: {hint!r}"
