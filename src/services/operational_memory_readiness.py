"""Pure helpers for Rico operational memory readiness."""
from __future__ import annotations


def normalize_status(value: object) -> str:
    return str(value or "").strip().lower()
