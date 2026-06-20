"""Canonical chat schemas shared by authenticated and public Rico chat endpoints."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ── Agentic UI Contract (CAREER-OS-01) ───────────────────────────────────────
# Optional structured UI hints that a Rico response MAY attach so future
# renderers can display richer components (cards, action buttons, etc.).
# All fields have defaults so existing code paths that never set agentic_ui
# continue to work unchanged. Set agentic_ui=None (default) to omit entirely.


class AgenticUIActionContract(BaseModel):
    """A single action the UI can render as a button or chip."""

    model_config = ConfigDict(extra="allow")

    action_id: str = ""
    type: str = "send_message"
    label: str = ""
    style: Literal["primary", "secondary", "danger"] = "secondary"
    job_id: str | None = None
    href: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class AgenticUIComponentContract(BaseModel):
    """A single renderable UI component hint."""

    model_config = ConfigDict(extra="allow")

    component: str = "text_block"
    title: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    actions: list[AgenticUIActionContract] = Field(default_factory=list)


class AgenticUIContract(BaseModel):
    """Optional structured UI hints attached to a RicoChatResponse.

    If absent the message field provides the text fallback.
    Version-stamped so future schema changes can be detected by renderers.
    """

    model_config = ConfigDict(extra="allow")

    version: str = "1"
    components: list[AgenticUIComponentContract] = Field(default_factory=list)
    primary_action: AgenticUIActionContract | None = None


# ─────────────────────────────────────────────────────────────────────────────


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
    agentic_ui: AgenticUIContract | None = None


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
