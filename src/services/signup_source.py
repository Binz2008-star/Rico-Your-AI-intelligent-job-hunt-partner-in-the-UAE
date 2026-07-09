"""Signup attribution sanitization and formatting (issue #922).

Cleans raw UTM/referrer/landing-path fields submitted at registration and
formats a short human-readable source summary for admin surfaces. The input is
untrusted: every field is stripped, control characters are removed, and length
is capped before storage or display. Signups with no usable attribution fall
back to "direct / unknown" — never a fake "website".
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

SIGNUP_SOURCE_FALLBACK = "direct / unknown"

ATTRIBUTION_FIELDS = (
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "referrer",
    "landing_path",
)

_MAX_FIELD_LEN = 300
_MAX_SUMMARY_LEN = 200

# Hosts that mean "the user navigated inside our own site" — not a real referrer.
_INTERNAL_REFERRER_HOSTS = {"ricohunt.com", "www.ricohunt.com", "localhost", "127.0.0.1"}

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


def sanitize_attribution(raw: Any) -> dict[str, str]:
    """Return only known attribution fields, cleaned and length-capped.

    Non-dict input, non-string values, and empty/whitespace values are dropped.
    Returns {} when nothing usable remains.
    """
    if not isinstance(raw, dict):
        return {}
    cleaned: dict[str, str] = {}
    for field in ATTRIBUTION_FIELDS:
        value = raw.get(field)
        if not isinstance(value, str):
            continue
        value = _CONTROL_CHARS_RE.sub("", value).strip()
        if not value:
            continue
        cleaned[field] = value[:_MAX_FIELD_LEN]
    return cleaned


def _referrer_host(referrer: str) -> str | None:
    """Extract a display host from a referrer URL; None for internal/invalid hosts."""
    candidate = referrer if "://" in referrer else f"https://{referrer}"
    try:
        host = (urlparse(candidate).hostname or "").lower()
    except ValueError:
        return None
    if not host or host in _INTERNAL_REFERRER_HOSTS:
        return None
    return host


def format_signup_source(attribution: dict[str, str] | None) -> str:
    """Build the source summary: UTM chain first, then external referrer host.

    - UTM present:       "google / cpc / brand-uae" (source / medium / campaign)
    - External referrer: "referrer: linkedin.com"
    - Otherwise:         "direct / unknown"
    """
    if not attribution:
        return SIGNUP_SOURCE_FALLBACK

    utm_source = attribution.get("utm_source")
    if utm_source:
        parts = [utm_source]
        for key in ("utm_medium", "utm_campaign"):
            if attribution.get(key):
                parts.append(attribution[key])
        return " / ".join(parts)[:_MAX_SUMMARY_LEN]

    referrer = attribution.get("referrer")
    if referrer:
        host = _referrer_host(referrer)
        if host:
            return f"referrer: {host}"[:_MAX_SUMMARY_LEN]

    return SIGNUP_SOURCE_FALLBACK
