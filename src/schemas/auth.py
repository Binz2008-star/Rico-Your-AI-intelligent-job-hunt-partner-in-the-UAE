from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

_EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
_PUBLIC_USER_ID_RE = re.compile(r"^public:[A-Za-z0-9_-]{8,64}$")


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


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=256)
    password: str = Field(..., min_length=8, max_length=128,
                          description="Minimum 8 characters")
    role: Literal["admin", "user"] = Field("user", description="User role")
    public_user_id_to_merge: str | None = Field(
        None,
        description="Optional public guest user ID to merge profile data from after signup",
    )

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
    new_password: str = Field(..., min_length=8,  max_length=128)


class ResetPasswordResponse(BaseModel):
    message: str
