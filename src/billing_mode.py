"""Centralized billing mode helpers.

Controls whether checkout routes use Paddle or manual (WhatsApp-assisted) activation.
Default is 'manual' so Paddle sandbox is never accidentally exposed in production.
"""
from __future__ import annotations

import os


def is_manual_billing_mode() -> bool:
    return os.getenv("BILLING_MODE", "manual").strip().lower() != "paddle"


def is_paddle_billing_mode() -> bool:
    return os.getenv("BILLING_MODE", "manual").strip().lower() == "paddle"
