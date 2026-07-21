"""Admin operations observability endpoint (DEC-20260721-001 slice 2).

Pins the contract of GET /api/v1/admin/ops/overview:
  1. admin-gated — unauthenticated requests are rejected; the route is wired
     through src.api.deps.require_admin (no parallel auth path);
  2. read-only snapshot with four sections (operations / job_providers /
     ai_provider / chat_api);
  3. the operations section is HONEST about store degradation: when the
     shared store is unavailable (pre-migration-050 or DB outage) it reports
     available=False + memory-fallback instead of healthy-looking zeros;
  4. the ai_provider section is an explicit allowlist of booleans + the
     provider name — future report fields can never leak through it.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("JWT_SECRET", "x" * 32)

from src.api.deps import require_admin
from src.api.routers import admin_ops
from src.repositories.chat_operations_repo import RepoUnavailable

_STATS = {
    "running": 2,
    "timed_out": 1,
    "stuck_lease_dead": 1,
    "completed_24h": 40,
    "failed_24h": 3,
    "expired_24h": 2,
    "started_24h": 46,
    "started_7d": 210,
    "oldest_active_age_seconds": 75.0,
}

_PROVIDERS = {
    "jsearch": {"configured": True, "degraded": False, "reason": None, "cooldown_remaining_s": 0},
    "jooble": {"configured": False, "degraded": False, "reason": None, "cooldown_remaining_s": 0},
    "adzuna": {"configured": False, "degraded": True, "reason": "quota", "cooldown_remaining_s": 120},
}


def _client(admin_override: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(admin_ops.router)
    if admin_override:
        app.dependency_overrides[require_admin] = lambda: {
            "email": "admin@test.com",
            "role": "admin",
        }
    return TestClient(app)


def test_overview_requires_admin_dependency_wiring():
    route = next(
        r for r in admin_ops.router.routes if getattr(r, "path", "") == "/api/v1/admin/ops/overview"
    )
    dep_calls = [d.call for d in route.dependant.dependencies]
    assert require_admin in dep_calls, (
        "overview must be guarded by src.api.deps.require_admin"
    )


def test_overview_rejects_unauthenticated_requests():
    client = _client(admin_override=False)
    resp = client.get("/api/v1/admin/ops/overview")
    assert resp.status_code in (401, 403)


def test_overview_snapshot_shape_when_store_available():
    client = _client()
    with patch.object(admin_ops.chat_operations_repo, "stats", return_value=dict(_STATS)), \
         patch.object(admin_ops, "provider_health", return_value=_PROVIDERS):
        resp = client.get("/api/v1/admin/ops/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"timestamp", "operations", "job_providers", "ai_provider", "chat_api"}

    operations = body["operations"]
    assert operations["available"] is True
    assert operations["store"] == "postgres"
    assert operations["stuck_lease_dead"] == 1
    assert operations["failed_24h"] == 3
    assert operations["lease_seconds"] > 0

    assert body["job_providers"] == _PROVIDERS
    assert body["chat_api"]["scope"] == "process"
    assert body["chat_api"]["total_requests"] >= 0


def test_overview_reports_store_degradation_honestly():
    client = _client()
    with patch.object(
        admin_ops.chat_operations_repo,
        "stats",
        side_effect=RepoUnavailable("chat_operations table not migrated yet"),
    ):
        resp = client.get("/api/v1/admin/ops/overview")
    assert resp.status_code == 200
    operations = resp.json()["operations"]
    assert operations["available"] is False
    assert operations["store"] == "memory-fallback"
    assert "not migrated" in operations["reason"]
    # No fake counters pretending a healthy quiet system.
    assert "stuck_lease_dead" not in operations


def test_ai_provider_section_is_a_strict_allowlist():
    client = _client()
    with patch.object(admin_ops.chat_operations_repo, "stats", return_value=dict(_STATS)):
        resp = client.get("/api/v1/admin/ops/overview")
    section = resp.json()["ai_provider"]
    assert set(section) == {
        "ai_provider",
        "ready_for_openai",
        "ready_for_deepseek",
        "ready_for_hf",
        "openai_key_present",
        "deepseek_key_present",
        "hf_key_present",
        "ready_for_db",
        "ready_for_telegram",
    }
    for key, value in section.items():
        if key == "ai_provider":
            assert isinstance(value, str)
        else:
            assert isinstance(value, bool)
