"""
src/api/routers/agent.py
POST /api/v1/agent/chat — agent interaction endpoint.
GET  /api/v1/agent/reasoning — the user's recent reasoning traces.
GET  /api/v1/agent/reasoning/{trace_id} — one full trace with rendered state.

Passes user identity to the orchestrator for audit logging. Reasoning reads
are always scoped to the JWT identity — a user can only inspect their own
reasoning graph.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from src.agent.orchestrator.orchestrator import process
from src.agent.reasoning import ReasoningTrace
from src.api.deps import get_current_user
from src.api.rate_limit import LIMIT_PROFILE, limiter
from src.repositories import reasoning_repo
from src.schemas.agent import AgentChatRequest, AgentUIResponse

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


@router.post("/chat", response_model=AgentUIResponse)
def agent_chat(
    req: AgentChatRequest,
    user: dict = Depends(get_current_user),
) -> AgentUIResponse:
    """
    Process a natural-language message or execute a direct action.
    All actions are audit-logged and idempotency-checked before execution.
    """
    return process(req.message, req.action, user_email=user.get("email", "anonymous"), actor_is_admin=(user.get("role") == "admin"))


@router.get("/reasoning")
@limiter.limit(LIMIT_PROFILE)
def list_reasoning(
    request: Request,
    limit: int = 20,
    user: dict = Depends(get_current_user),
) -> dict:
    """
    The current user's most recent reasoning traces (summaries, newest first).
    Each trace explains why Rico made a decision: goal, decision, confidence,
    and lifecycle status.
    """
    traces = reasoning_repo.list_recent(
        user_id=user.get("email", ""), limit=min(max(limit, 1), 50)
    )
    return {"traces": traces, "count": len(traces)}


@router.get("/reasoning/{trace_id}")
@limiter.limit(LIMIT_PROFILE)
def get_reasoning(
    request: Request,
    trace_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    """
    One full reasoning trace: the structured execution state (evidence,
    contradictions, decision, outcome) plus its human-readable rendering.
    404 for a trace that does not exist or belongs to another user.
    """
    row = reasoning_repo.get_trace(trace_id, user_id=user.get("email", ""))
    if not row:
        raise HTTPException(status_code=404, detail="Reasoning trace not found")
    try:
        row["state"] = ReasoningTrace.from_dict(row.get("trace") or {}).render()
    except Exception:
        row["state"] = ""
    return row
