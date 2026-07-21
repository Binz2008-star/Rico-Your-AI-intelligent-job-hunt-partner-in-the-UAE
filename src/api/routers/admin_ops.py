"""Admin-only operations observability (DEC-20260721-001 stabilization slice 2).

GET /api/v1/admin/ops/overview — one read-only snapshot of what an operator
needs to see: stuck/pending chat operations (heartbeat-lease view over the
shared store from slice 1), 24h/7d search volume and failure counts (the
honest cost/error proxies available today), job-provider degradation state,
AI-provider readiness, and chat-API process counters.

Deliberately NOT in this slice: per-token AI spend counters (needs provider
instrumentation — a later increment) and any mutation. This endpoint reads;
it never expires, retries, or repairs anything. Exposes booleans, counts and
enum-like strings only — never key values, user identifiers, or query text.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends

from src.api.deps import require_admin
from src.job_providers import provider_health
from src.repositories import chat_operations_repo
from src.repositories.chat_operations_repo import RepoUnavailable
from src.rico_env import get_rico_env_report
from src.services.operation_state import LEASE_SECONDS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/ops", tags=["admin-ops"])


def _operations_section() -> Dict[str, Any]:
    try:
        data = chat_operations_repo.stats(lease_seconds=LEASE_SECONDS)
        return {
            "available": True,
            "store": "postgres",
            "lease_seconds": LEASE_SECONDS,
            **data,
        }
    except RepoUnavailable as exc:
        # Pre-migration-050 or DB trouble: the store (and therefore this
        # view) is on the legacy in-process fallback — say so honestly
        # instead of returning zeros that look like a healthy quiet system.
        return {
            "available": False,
            "store": "memory-fallback",
            "reason": str(exc),
        }


def _ai_provider_section() -> Dict[str, Any]:
    report = get_rico_env_report().to_dict()
    # Booleans + provider name only (the report is already value-free, but
    # keep an explicit allowlist so future report fields never leak here).
    keys = (
        "ai_provider",
        "ready_for_openai",
        "ready_for_deepseek",
        "ready_for_hf",
        "openai_key_present",
        "deepseek_key_present",
        "hf_key_present",
        "ready_for_db",
        "ready_for_telegram",
    )
    return {k: report.get(k) for k in keys}


def _chat_api_section() -> Dict[str, Any]:
    # Process-local counters (reset on deploy/restart) — labeled as such.
    try:
        from src.api.routers.rico_chat import _metrics
        return {
            "scope": "process",
            "uptime_seconds": _metrics.uptime_seconds,
            "total_requests": _metrics.request_count,
            "avg_response_time_ms": _metrics.avg_response_time_ms,
        }
    except Exception:  # pragma: no cover - metrics must never break the view
        return {"scope": "process", "error": "unavailable"}


@router.get("/overview")
def admin_ops_overview(
    admin: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Read-only operations snapshot for the admin/owner."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "operations": _operations_section(),
        "job_providers": provider_health(),
        "ai_provider": _ai_provider_section(),
        "chat_api": _chat_api_section(),
    }
