"""
src/services/permission_factory.py
Factory functions for building RicoPermissionRequest objects.

These are the canonical constructors — any Rico chat handler or action layer
that needs to surface a permission prompt to the UI should call these rather
than building the dict by hand, so the contract stays consistent.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict

from src.schemas.chat import (
    RicoActionImpact,
    RicoActionKind,
    RicoChatAction,
    RicoPermissionRequest,
)


def _gen_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def build_apply_permission_request(
    job: Dict[str, Any],
    user_id: str,
    *,
    permission_id: str | None = None,
) -> RicoPermissionRequest:
    """Build a RicoPermissionRequest for an apply action.

    Call this when apply_to_job() returns status='approval_required' and you
    want to surface a PermissionRequestCard in the UI instead of plain text.

    The approve_action.payload carries exactly the fields that
    POST /api/v1/rico/actions/execute expects so the frontend can forward
    them directly.
    """
    from src.services import pending_permissions
    pid = permission_id or _gen_id("perm-apply")
    pending_permissions.register(pid, user_id, "apply")
    title = job.get("title", "Unknown role")
    company = job.get("company", "Unknown company")
    job_key = str(job.get("id") or job.get("job_key") or "")

    approve_action = RicoChatAction(
        id=_gen_id("approve"),
        label="Apply now",
        kind=RicoActionKind.approve,
        impact=RicoActionImpact.high,
        requires_confirmation=False,
        endpoint="/api/v1/rico/actions/execute",
        payload={
            "permission_id": pid,
            "action": "apply",
            "job_key": job_key,
            "job": job,
        },
    )
    cancel_action = RicoChatAction(
        id=_gen_id("cancel"),
        label="Cancel",
        kind=RicoActionKind.cancel,
        impact=RicoActionImpact.low,
        requires_confirmation=False,
        payload={},
    )

    link = job.get("link") or job.get("apply_url") or ""
    data_used = ["Your CV and profile", "Your contact details"]
    effects = [f"Application submitted for {title} at {company}"]
    if link:
        effects.append(f"Application URL: {link[:80]}")

    return RicoPermissionRequest(
        id=pid,
        title=f"Apply to {title}",
        summary=(
            f"Rico will submit your application to {company} on your behalf. "
            "This action cannot be undone once submitted."
        ),
        risk_level="high",
        data_used=data_used,
        effects=effects,
        approve_action=approve_action,
        cancel_action=cancel_action,
    )


def build_apply_permission_dict(
    job: Dict[str, Any],
    user_id: str,
    *,
    permission_id: str | None = None,
) -> Dict[str, Any]:
    """Same as build_apply_permission_request() but returns a plain dict.

    Use this when attaching to RuntimeResult.data or any dict-based
    response layer that doesn't hold Pydantic objects.
    """
    req = build_apply_permission_request(job, user_id, permission_id=permission_id)
    return req.model_dump(mode="json")
