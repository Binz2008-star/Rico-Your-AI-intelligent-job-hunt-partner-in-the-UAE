"""Canonical chat schemas shared by authenticated and public Rico chat endpoints."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ── Agentic UI contracts (CAREER-OS-01) ──────────────────────────────────────


class RicoActionKind(str, Enum):
    navigate = "navigate"
    submit = "submit"
    chat_continue = "chat_continue"
    open_drawer = "open_drawer"
    approve = "approve"
    cancel = "cancel"


class RicoActionImpact(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class RicoChatAction(BaseModel):
    id: str
    label: str
    kind: RicoActionKind
    impact: RicoActionImpact = RicoActionImpact.low
    requires_confirmation: bool = False
    endpoint: str | None = None
    href: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    tracking_key: str | None = None


class RicoPermissionRequest(BaseModel):
    id: str
    title: str
    summary: str
    risk_level: Literal["medium", "high"]
    data_used: list[str] = Field(default_factory=list)
    effects: list[str] = Field(default_factory=list)
    approve_action: RicoChatAction
    review_action: RicoChatAction | None = None
    cancel_action: RicoChatAction


class RicoProgressStep(BaseModel):
    id: str
    label: str
    status: Literal["pending", "running", "complete", "failed"]


class RicoProposedChange(BaseModel):
    field: str
    current_value: Any | None = None
    proposed_value: Any
    source: Literal["chat", "cv", "file", "screenshot", "system", "user_action"]


class RicoAttachmentPurpose(str, Enum):
    cv_resume = "cv_resume"
    job_post = "job_post"
    recruiter_message = "recruiter_message"
    application_form = "application_form"
    certificate = "certificate"
    offer_letter = "offer_letter"
    contract_or_legalish = "contract_or_legalish"
    company_profile = "company_profile"
    public_comment = "public_comment"
    application_evidence = "application_evidence"
    unknown_document = "unknown_document"


class RicoAttachmentAnalysis(BaseModel):
    id: str
    filename: str | None = None
    mime_type: str | None = None
    purpose: RicoAttachmentPurpose
    confidence: float
    extracted_summary: str | None = None
    extracted_fields: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class RicoAgenticUi(BaseModel):
    actions: list[RicoChatAction] = Field(default_factory=list)
    permission_request: RicoPermissionRequest | None = None
    progress: list[RicoProgressStep] = Field(default_factory=list)
    proposed_changes: list[RicoProposedChange] = Field(default_factory=list)
    attachment_analysis: list[RicoAttachmentAnalysis] = Field(default_factory=list)


# ── Chat response ─────────────────────────────────────────────────────────────


class RicoChatResponse(BaseModel):
    """Canonical response shape for Rico chat endpoints.

    Both /chat (authenticated) and /chat/public should conform to this shape.
    All fields are optional/defaulted so legacy response dicts pass through
    without validation errors during the migration period.
    """

    model_config = ConfigDict(extra="allow")

    message: str = ""
    type: str = "response"
    matches: list[dict[str, Any]] = Field(default_factory=list)
    options: list[dict[str, Any]] = Field(default_factory=list)
    next_action: str | None = None
    next_actions: list[dict[str, Any]] = Field(default_factory=list)
    intent: str | None = None
    response_source: str | None = None
    provider: str | None = None
    provider_state: str | None = None
    reasons: list[str] = Field(default_factory=list)
    role: str | None = None
    success: bool = True
    error_ref: str | None = None
    trace_id: str | None = None
    # Legacy alias — some response paths return "response" instead of "message"
    response: str | None = None
    operation_id: str | None = None
    operation_status: str | None = None
    operation_type: str | None = None
    result_count: int | None = None
    agentic_ui: RicoAgenticUi | None = None


class RicoSessionContext(BaseModel):
    """Resolved identity and capability context for a Rico chat request.

    Built at the router level before passing to orchestrator/service so that
    auth logic never leaks into domain code.
    """

    user_id: str
    auth_type: Literal["authenticated", "public", "jotform"]
    can_persist_profile: bool = True
    can_view_private_jobs: bool = False
    rate_limit_tier: Literal["standard", "elevated", "admin"] = "standard"
    session_id: str | None = None

    @classmethod
    def for_authenticated(cls, user_id: str) -> "RicoSessionContext":
        return cls(
            user_id=user_id,
            auth_type="authenticated",
            can_persist_profile=True,
            can_view_private_jobs=True,
            rate_limit_tier="standard",
        )

    @classmethod
    def for_public(cls, session_id: str) -> "RicoSessionContext":
        return cls(
            user_id=f"public:{session_id}",
            auth_type="public",
            can_persist_profile=False,
            can_view_private_jobs=False,
            rate_limit_tier="standard",
            session_id=session_id,
        )
