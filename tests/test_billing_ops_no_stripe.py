"""Regression guard: retired Stripe tooling/config must not return (issue #1066).

The Stripe billing flow was fully removed in favour of single-plan Paddle
(DEC-20260713-005). These checks fail loudly if a Stripe endpoint, a Stripe
env-var declaration, or the retired Premium/AED config sneaks back into the
Render blueprint or the active billing smoke scripts.

Static file checks only — no network, no DB, no imports of the app.
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RENDER_YAML = REPO_ROOT / "render.yaml"
SCRIPTS_DIR = REPO_ROOT / "scripts"

# Active billing smoke/diagnostic scripts that must stay on the current
# manual/Paddle contract (never call the removed Stripe checkout).
ACTIVE_BILLING_SCRIPTS = [
    "subscription_smoke_test.py",
    "smoke_subscription_me.py",
]

# Substrings that only ever appear in the retired Stripe flow. Chosen so they do
# NOT collide with legitimate "Stripe is removed" retirement notes.
FORBIDDEN_STRIPE_MARKERS = [
    "/api/v1/subscription/checkout",  # removed endpoint
    "subscription/checkout",           # removed endpoint (any prefix)
    "checkout.stripe.com",             # Stripe-hosted checkout URL
    "stripe_customer_id",              # Stripe DB columns (now paddle_*)
    "stripe_subscription_id",
]


def _load_render_env_keys():
    yaml = pytest.importorskip("yaml")
    data = yaml.safe_load(RENDER_YAML.read_text(encoding="utf-8"))
    keys = []
    for service in data.get("services", []):
        for env in service.get("envVars", []) or []:
            key = env.get("key")
            if key:
                keys.append(key)
    return keys


class TestRenderBlueprintPaddleNotStripe:
    def test_render_yaml_is_valid(self):
        yaml = pytest.importorskip("yaml")
        # Must parse without error — declaration hygiene depends on valid YAML.
        assert yaml.safe_load(RENDER_YAML.read_text(encoding="utf-8")) is not None

    def test_no_stripe_env_vars_declared(self):
        keys = _load_render_env_keys()
        stripe_keys = [k for k in keys if k.startswith("STRIPE_")]
        assert stripe_keys == [], f"retired Stripe env vars in render.yaml: {stripe_keys}"

    def test_no_retired_aed_or_premium_env_vars(self):
        keys = _load_render_env_keys()
        retired = [k for k in keys if k in {"RICO_PRO_PRICE_AED", "RICO_PREMIUM_PRICE_AED"}]
        assert retired == [], f"retired AED/Premium env vars in render.yaml: {retired}"

    def test_paddle_and_billing_mode_declared(self):
        keys = set(_load_render_env_keys())
        required = {
            "BILLING_MODE",
            "RICO_PRO_PRICE_USD",
            "PADDLE_SANDBOX",
            "PADDLE_API_KEY",
            "PADDLE_WEBHOOK_SECRET",
            "PADDLE_PRO_MONTHLY_PRICE_ID",
        }
        missing = required - keys
        assert not missing, f"render.yaml missing Paddle/billing declarations: {sorted(missing)}"

    def test_billing_mode_default_is_manual(self):
        yaml = pytest.importorskip("yaml")
        data = yaml.safe_load(RENDER_YAML.read_text(encoding="utf-8"))
        billing_mode_value = None
        for service in data.get("services", []):
            for env in service.get("envVars", []) or []:
                if env.get("key") == "BILLING_MODE":
                    billing_mode_value = env.get("value")
        assert billing_mode_value == "manual", (
            f"BILLING_MODE must stay 'manual' (owner-gated activation), got {billing_mode_value!r}"
        )

    def test_paddle_secrets_have_no_committed_values(self):
        yaml = pytest.importorskip("yaml")
        data = yaml.safe_load(RENDER_YAML.read_text(encoding="utf-8"))
        # Secrets and the environment-specific Price ID must be sync:false with no value.
        secret_keys = {"PADDLE_API_KEY", "PADDLE_WEBHOOK_SECRET", "PADDLE_PRO_MONTHLY_PRICE_ID"}
        for service in data.get("services", []):
            for env in service.get("envVars", []) or []:
                if env.get("key") in secret_keys:
                    assert env.get("sync") is False, f"{env.get('key')} must be sync:false"
                    assert "value" not in env, f"{env.get('key')} must not carry a committed value"


class TestActiveScriptsHaveNoStripeFlow:
    def test_stripe_runtime_diagnostic_deleted(self):
        assert not (SCRIPTS_DIR / "stripe_runtime_diagnostic.py").exists(), (
            "scripts/stripe_runtime_diagnostic.py was retired and must stay deleted"
        )

    @pytest.mark.parametrize("script_name", ACTIVE_BILLING_SCRIPTS)
    def test_no_removed_stripe_markers(self, script_name):
        content = (SCRIPTS_DIR / script_name).read_text(encoding="utf-8")
        for marker in FORBIDDEN_STRIPE_MARKERS:
            assert marker not in content, (
                f"{script_name} references retired Stripe flow marker: {marker!r}"
            )
