from __future__ import annotations

import re
from typing import Any, Dict

from pydantic import BaseModel, Field, field_validator

_EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
_ALLOWED_LOCATIONS = {
    "Abu Dhabi",
    "Dubai",
    "Sharjah",
    "Ajman",
    "Umm Al Quwain",
    "Ras Al Khaimah",
    "Fujairah",
    "Outside UAE",
}


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned or None


class WaitlistRegisterRequest(BaseModel):
    model_config = {"extra": "ignore"}

    email: str = Field(..., min_length=3, max_length=256, pattern=_EMAIL_RE)
    first_name: str | None = Field(None, max_length=100)
    target_role: str | None = Field(None, max_length=200)
    location: str | None = Field(None, max_length=100)
    consent: bool
    source: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("email", mode="after")
    @classmethod
    def normalise_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("first_name", "target_role", mode="before")
    @classmethod
    def clean_text(cls, value: object) -> object:
        return _clean_optional(str(value)) if value is not None else None

    @field_validator("location", mode="before")
    @classmethod
    def validate_location(cls, value: object) -> object:
        cleaned = _clean_optional(str(value)) if value is not None else None
        if cleaned is not None and cleaned not in _ALLOWED_LOCATIONS:
            raise ValueError("unsupported location")
        return cleaned

    @field_validator("consent", mode="after")
    @classmethod
    def require_consent(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("consent is required")
        return value

    @field_validator("source", mode="before")
    @classmethod
    def sanitise_source(cls, value: object) -> Dict[str, str]:
        if not isinstance(value, dict):
            return {}
        allowed = {
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_content",
            "utm_term",
            "referral_code",
            "landing_path",
        }
        clean: Dict[str, str] = {}
        for key, raw in value.items():
            if key not in allowed or raw is None:
                continue
            text = _clean_optional(str(raw))
            if text:
                clean[key] = text[:500]
        return clean


class WaitlistRegisterResponse(BaseModel):
    success: bool = True
    message: str
