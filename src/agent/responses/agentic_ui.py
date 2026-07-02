"""src/agent/responses/agentic_ui.py

Typed backend contracts for the Rico Agentic UI Action Layer (PR-A).

These models are an OPTIONAL extension to existing chat responses — old clients
that only read `message`/`type` continue working without change.  New clients
render the `agentic_ui` envelope for action cards, permission prompts, progress
steps, proposed changes, and multimodal attachment analysis.

Architecture reference: docs/architecture/agentic-ui-action-layer.md
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# ── Enumerations ──────────────────────────────────────────────────────────────

class RicoActionKind(str, Enum):
    """Describes how the frontend should handle a user clicking an action."""
    navigate = "navigate"           # open a URL / route
    submit = "submit"               # POST to an endpoint
    chat_continue = "chat_continue" # inject a follow-up message into the chat
    open_drawer = "open_drawer"     # open a focused side panel (safe no-op fallback)
    approve = "approve"             # approve a pending permission_request
    cancel = "cancel"               # cancel a pending permission_request


class RicoActionImpact(str, Enum):
    """Impact level — controls whether a permission prompt is shown."""
    low = "low"       # navigate / safe read
    medium = "medium" # saves data, side-effectful but reversible
    high = "high"     # apply, send, mutate profile — always needs approval


class RicoAttachmentPurpose(str, Enum):
    """Classified purpose of an uploaded file or screenshot."""
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


# ── Core action model ─────────────────────────────────────────────────────────

class RicoChatAction(BaseModel):
    """A single clickable action card attached to a chat message.

    Low/medium impact actions are rendered as buttons that navigate, continue the
    chat, or submit safe payloads.  High-impact actions must go through a
    `RicoPermissionRequest` — they must not be placed directly in `actions[]`.
    """
    id: str
    label: str
    kind: RicoActionKind
    impact: RicoActionImpact = RicoActionImpact.low
    requires_confirmation: bool = False
    endpoint: str | None = None   # POST target for kind=submit
    href: str | None = None       # navigation target for kind=navigate
    payload: dict[str, Any] = Field(default_factory=dict)
    tracking_key: str | None = None


# ── Permission prompt (high-impact gate) ──────────────────────────────────────

class RicoPermissionRequest(BaseModel):
    """Explicit approval card for high-impact actions.

    Shown before: applying to a job, sending a message, mutating profile/settings,
    replacing a CV, enabling recurring behavior.

    The `approve_action` must be a kind=approve action.
    The `cancel_action` must be a kind=cancel action.
    `review_action` is optional (e.g., "Edit before sending").
    """
    id: str
    title: str
    summary: str
    risk_level: Literal["medium", "high"]
    data_used: list[str] = Field(default_factory=list)
    effects: list[str] = Field(default_factory=list)
    approve_action: RicoChatAction
    review_action: RicoChatAction | None = None
    cancel_action: RicoChatAction


# ── Progress steps ────────────────────────────────────────────────────────────

class RicoProgressStep(BaseModel):
    """One visible step in a multi-step execution sequence.

    Rendered as a step list (✓ done / ● running / … pending / ✗ failed) inside
    a chat message while Rico is working.
    """
    id: str
    label: str
    status: Literal["pending", "running", "complete", "failed"]


# ── Proposed changes (settings / profile mutations) ───────────────────────────

class RicoProposedChange(BaseModel):
    """A single field mutation waiting for user approval.

    Shown as a review card: "Rico will change X from A to B."
    `source` indicates why Rico is proposing this change.
    """
    field: str
    current_value: Any | None = None
    proposed_value: Any
    source: Literal["chat", "cv", "file", "screenshot", "system", "user_action"]


# ── Attachment analysis ───────────────────────────────────────────────────────

class RicoAttachmentAnalysis(BaseModel):
    """Structured result of classifying and extracting an uploaded file.

    Rico must classify before acting on any upload. `confidence` is 0–1.
    High-sensitivity documents (offer_letter, contract_or_legalish) should have
    their `warnings` list populated and never trigger silent profile mutations.
    """
    id: str
    filename: str | None = None
    mime_type: str | None = None
    purpose: RicoAttachmentPurpose
    confidence: float
    extracted_summary: str | None = None
    extracted_fields: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


# ── Top-level envelope ────────────────────────────────────────────────────────

class RicoAgenticUi(BaseModel):
    """Optional agentic UI envelope attached to any Rico chat response.

    All fields default to empty/None so callers can construct a minimal envelope
    with only the fields they need.  The frontend must ignore unknown keys and
    render gracefully when any list is empty.

    Usage::

        from src.agent.responses.agentic_ui import RicoAgenticUi, RicoChatAction, RicoActionKind

        ui = RicoAgenticUi(actions=[
            RicoChatAction(id="view_jobs", label="View jobs", kind=RicoActionKind.navigate, href="/flow"),
        ])
        response["agentic_ui"] = ui.model_dump(exclude_none=True)
    """
    actions: list[RicoChatAction] = Field(default_factory=list)
    permission_request: RicoPermissionRequest | None = None
    progress: list[RicoProgressStep] = Field(default_factory=list)
    proposed_changes: list[RicoProposedChange] = Field(default_factory=list)
    attachment_analysis: list[RicoAttachmentAnalysis] = Field(default_factory=list)

    def is_empty(self) -> bool:
        """True when no agentic UI payload is attached (nothing to render)."""
        return (
            not self.actions
            and self.permission_request is None
            and not self.progress
            and not self.proposed_changes
            and not self.attachment_analysis
        )

    def to_response_dict(self) -> dict[str, Any]:
        """Serialize for inclusion in a chat response dict.

        Omits None values; empty lists are preserved so the frontend type-checks
        cleanly without needing `?.` guards on every field.
        """
        return self.model_dump(exclude_none=True)
