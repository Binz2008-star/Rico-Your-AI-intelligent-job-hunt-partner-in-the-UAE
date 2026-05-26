"""Centralized billing mode helpers.

Controls whether checkout routes use Stripe or manual (WhatsApp-assisted) activation.
Default is 'manual' so Stripe sandbox is never accidentally exposed in production.
"""
from __future__ import annotations

import os


def is_manual_billing_mode() -> bool:
    return os.getenv("BILLING_MODE", "manual").strip().lower() != "stripe"


def is_stripe_billing_mode() -> bool:
    return os.getenv("BILLING_MODE", "manual").strip().lower() == "stripe"
