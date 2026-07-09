from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

_EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
_PUBLIC_USER_ID_RE = re.compile(r"^public:[A-Za-z0-9_-]{8,64}$")

_PASSWORD_MIN_LEN = 8


def _check_password_complexity(password: str) -> str:
    """Enforce: min 8 chars, ≥1 uppercase, ≥1 lowercase, ≥1 digit or symbol."""
    errors = []
    if len(password) < _PASSWORD_MIN_LEN:
        errors.append(f"at least {_PASSWORD_MIN_LEN} characters")
    if not re.search(r"[A-Z]", password):
        errors.append("at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        errors.append("at least one lowercase letter")
    if not (re.search(r"[0-9]", password) or re.search(r"[^A-Za-z0-9]", password)):
        errors.append("at least one digit or special character")
    if errors:
        raise ValueError("Password must contain " + ", ".join(errors))
    return password


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=1, max_length=256, pattern=_EMAIL_RE)
    password: str = Field(..., min_length=1, max_length=128)
    public_user_id_to_merge: str | None = Field(
        None,
        description="Optional public guest user ID to merge profile data from after login",
    )

    @field_validator("public_user_id_to_merge", mode="before")
    @classmethod
    def validate_public_user_id(cls, v: object) -> object:
        if v is not None and not _PUBLIC_USER_ID_RE.match(str(v)):
            raise ValueError("public_user_id_to_merge must match format public:<8-64 alphanumeric chars>")
        return v


class LoginResponse(BaseModel):
    message: str
    email: str


class SignupAttribution(BaseModel):
    """Marketing attribution captured client-side at signup (issue #922).

    All fields are optional and untrusted — the backend re-sanitizes them via
    src.services.signup_source before storage or display.
    """
    model_config = {"extra": "ignore"}

    utm_source: str | None = Field(None, max_length=500)
    utm_medium: str | None = Field(None, max_length=500)
    utm_campaign: str | None = Field(None, max_length=500)
    utm_content: str | None = Field(None, max_length=500)
    utm_term: str | None = Field(None, max_length=500)
    referrer: str | None = Field(None, max_length=2000)
    landing_path: str | None = Field(None, max_length=500)


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=256)
    password: str = Field(..., min_length=8, max_length=128,
                          description="Min 8 chars, upper, lower, digit or symbol")
    name: str | None = Field(None, max_length=200, description="Optional display name")
    role: Literal["admin", "user"] = Field("user", description="User role")
    public_user_id_to_merge: str | None = Field(
        None,
        description="Optional public guest user ID to merge profile data from after signup",
    )
    signup_attribution: SignupAttribution | None = Field(
        None,
        description="Optional UTM/referrer/landing-path attribution captured before signup",
    )

    @field_validator("password", mode="after")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        return _check_password_complexity(v)

    @field_validator("public_user_id_to_merge", mode="before")
    @classmethod
    def validate_public_user_id(cls, v: object) -> object:
        if v is not None and not _PUBLIC_USER_ID_RE.match(str(v)):
            raise ValueError("public_user_id_to_merge must match format public:<8-64 alphanumeric chars>")
        return v


class RegisterResponse(BaseModel):
    email: str
    role: str
    created: bool
    email_verification_required: bool = False


class VerifyEmailResponse(BaseModel):
    message: str
    email: str


class ResendVerificationRequest(BaseModel):
    email: str = Field(..., min_length=1, max_length=256, pattern=_EMAIL_RE)


class ResendVerificationResponse(BaseModel):
    message: str


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=1, max_length=256, pattern=_EMAIL_RE)


class ForgotPasswordResponse(BaseModel):
    message: str


class ResetPasswordRequest(BaseModel):
    token:        str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128,
                              description="Min 8 chars, upper, lower, digit or symbol")

    @field_validator("new_password", mode="after")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        return _check_password_complexity(v)


class ResetPasswordResponse(BaseModel):
    message: str
