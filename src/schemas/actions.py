"""
src/schemas/actions.py
HTTP contracts for POST /api/v1/actions/run and POST /api/v1/rico/actions/execute.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator

from src.agent.orchestrator.intent_detector import VALID_ACTION_TYPES

_VALID = sorted(VALID_ACTION_TYPES)

# Subset of VALID_ACTION_TYPES that the permission engine may approve on behalf of a
# user. trigger_pipeline is excluded — it is an admin/scheduler action that must never
# be reachable through a user-facing permission card.
EXECUTE_ALLOWED_ACTIONS: frozenset[str] = frozenset({
    "apply", "save", "skip", "not_relevant", "block", "draft", "why", "remind",
})


class ActionRequest(BaseModel):
    action: str = Field(
        ...,
        description=f"One of: {', '.join(_VALID)}",
    )
    job_key: str = Field(
        "",
        max_length=256,
        description="Hex fingerprint from get_job_id() — used to look up cached job when 'job' is omitted",
    )
    job: Optional[Dict[str, Any]] = Field(
        None,
        description="Full job dict. If omitted, resolved from Telegram job cache via job_key.",
    )
    source: str = Field(
        "api",
        max_length=64,
        description="Caller label for audit logs",
    )
    dry_run: bool = Field(
        False,
        description="When true: log intent only, skip execution and audit",
    )


class ActionResponse(BaseModel):
    ok: bool
    message: str
    action: str
    job_key: str
    source: str
    user_id: str
    dry_run: bool
    data: Dict[str, Any]
    error: Optional[str]
    confidence: float
    explanation: str
    duration_ms: int


class ExecutePermissionActionRequest(BaseModel):
    """Request body for POST /api/v1/rico/actions/execute (CAREER-OS-03).

    Called by the frontend PermissionRequestCard when the user explicitly
    approves a high-impact action surfaced via agentic_ui.permission_request.

    Only actions in EXECUTE_ALLOWED_ACTIONS are accepted — admin/scheduler
    actions like trigger_pipeline are explicitly excluded at this layer so
    they can never be reached through a user permission card.
    """
    permission_id: str = Field(..., min_length=1, max_length=128,
                               description="ID from permission_request.id")
    action: str = Field(..., description="Action name — must be in EXECUTE_ALLOWED_ACTIONS")
    job_key: str = Field("", max_length=256)
    job: Optional[Dict[str, Any]] = Field(None, description="Full job dict when available")
    source: str = Field("permission_card", max_length=64)

    @field_validator("action")
    @classmethod
    def action_must_be_allowed(cls, v: str) -> str:
        if v not in EXECUTE_ALLOWED_ACTIONS:
            raise ValueError(
                f"action '{v}' is not permitted via the permission engine. "
                f"Allowed: {sorted(EXECUTE_ALLOWED_ACTIONS)}"
            )
        return v
