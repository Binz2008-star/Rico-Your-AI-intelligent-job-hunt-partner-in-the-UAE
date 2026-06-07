from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from src.schemas.subscription import CheckoutResponse, SubscriptionCreateRequest, SubscriptionTier
from src.subscription_plans import _whatsapp_checkout_url, build_checkout_response


def _make_request(plan: str = "pro") -> SubscriptionCreateRequest:
    return SubscriptionCreateRequest(plan=SubscriptionTier(plan))


# ── WhatsApp URL builder ──────────────────────────────────────────────────────

def test_whatsapp_url_contains_default_number() -> None:
    url = _whatsapp_checkout_url("Pro")
    assert "971585989080" in url


def test_whatsapp_url_pro_plan_label() -> None:
    url = _whatsapp_checkout_url("Pro")
    assert "Pro" in url
    assert url.startswith("https://wa.me/")


def test_whatsapp_url_premium_plan_label() -> None:
    url = _whatsapp_checkout_url("Premium")
    assert "Premium" in url


def test_whatsapp_url_custom_number_env() -> None:
    with patch.dict(os.environ, {"RICO_WHATSAPP_NUMBER": "971500000000"}):
        url = _whatsapp_checkout_url("Pro")
    assert "971500000000" in url
    assert "971585989080" not in url


# ── Manual billing mode: checkout returns safe response ───────────────────────

def test_manual_billing_checkout_returns_200_not_exception() -> None:
    with patch.dict(os.environ, {"BILLING_MODE": "manual"}):
        result = build_checkout_response("user@example.com", _make_request("pro"))
    assert isinstance(result, CheckoutResponse)


def test_manual_billing_checkout_provider_is_manual() -> None:
    with patch.dict(os.environ, {"BILLING_MODE": "manual"}):
        result = build_checkout_response("user@example.com", _make_request("pro"))
    assert result.provider == "manual"


def test_manual_billing_checkout_status_is_manual() -> None:
    with patch.dict(os.environ, {"BILLING_MODE": "manual"}):
        result = build_checkout_response("user@example.com", _make_request("pro"))
    assert result.status == "manual"


def test_manual_billing_checkout_url_is_whatsapp() -> None:
    with patch.dict(os.environ, {"BILLING_MODE": "manual"}):
        result = build_checkout_response("user@example.com", _make_request("pro"))
    assert result.checkout_url.startswith("https://wa.me/")


def test_manual_billing_pro_plan_url_contains_pro() -> None:
    with patch.dict(os.environ, {"BILLING_MODE": "manual"}):
        result = build_checkout_response("user@example.com", _make_request("pro"))
    assert "Pro" in result.checkout_url


def test_manual_billing_premium_plan_url_contains_premium() -> None:
    with patch.dict(os.environ, {"BILLING_MODE": "manual"}):
        result = build_checkout_response("user@example.com", _make_request("premium"))
    assert "Premium" in result.checkout_url


def test_manual_billing_plan_field_matches_request() -> None:
    with patch.dict(os.environ, {"BILLING_MODE": "manual"}):
        result = build_checkout_response("user@example.com", _make_request("premium"))
    assert result.plan == SubscriptionTier.PREMIUM


def test_manual_billing_mode_even_when_stripe_key_present() -> None:
    """BILLING_MODE=manual takes priority even if STRIPE_SECRET_KEY is set."""
    with patch.dict(os.environ, {"BILLING_MODE": "manual", "STRIPE_SECRET_KEY": "sk_test_fake"}):
        result = build_checkout_response("user@example.com", _make_request("pro"))
    assert result.provider == "manual"
    assert result.checkout_url.startswith("https://wa.me/")
