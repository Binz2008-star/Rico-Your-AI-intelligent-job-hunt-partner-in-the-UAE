"""GET /api/v1/journey/today — journey snapshot + daily plan route (#965).

The route derives the authenticated user's journey stage and daily plan from
canonical application stats. Contracts locked here:

  - JWT required (401 otherwise); identity comes from the token, never the body
  - counts flow from applications_repo.get_stats for the JWT user only
  - DB unavailability propagates as 503 (no fabricated empty snapshot)
  - response shape: {journey: {...}, plan: {actions: [...]}}
  - empty/new user → discovery state with a non-empty plan
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app


def _make_token(email: str, role: str = "user") -> str:
    from src.api.auth import create_access_token
    return create_access_token({"sub": email, "role": role})


def _client(email: str) -> TestClient:
    tc = TestClient(app, raise_server_exceptions=False)
    tc.cookies.set("access_token", _make_token(email))
    return tc


def _stats(by_status: dict) -> dict:
    total = sum(v for v in by_status.values() if isinstance(v, int))
    return {"total": total, "by_status": by_status}


class TestJourneyTodayRoute:
    def test_unauthenticated_returns_401(self):
        tc = TestClient(app, raise_server_exceptions=False)
        assert tc.get("/api/v1/journey/today").status_code == 401

    def test_new_user_gets_discovery_state_with_plan(self):
        tc = _client("newbie@rico.ai")
        with patch("src.api.routers.journey.get_stats", return_value=_stats({})) as mock_stats:
            r = tc.get("/api/v1/journey/today")
        assert r.status_code == 200
        body = r.json()
        assert body["journey"]["state"] == "discovery"
        assert body["journey"]["user_id"] == "newbie@rico.ai"
        assert len(body["plan"]["actions"]) >= 1
        assert mock_stats.call_args.kwargs["user_id"] == "newbie@rico.ai"

    def test_populated_user_gets_furthest_stage(self):
        tc = _client("active@rico.ai")
        counts = {"saved": 4, "applied": 3, "interview": 1, "follow_up_due": 2}
        with patch("src.api.routers.journey.get_stats", return_value=_stats(counts)):
            r = tc.get("/api/v1/journey/today")
        assert r.status_code == 200
        body = r.json()
        assert body["journey"]["state"] == "interviewing"
        assert body["journey"]["saved_count"] == 4
        assert body["journey"]["applied_count"] == 3
        assert body["journey"]["follow_up_due_count"] == 2
        actions = {a["action"] for a in body["plan"]["actions"]}
        assert "interview_prep" in actions
        assert "follow_up" in actions

    def test_offer_state(self):
        tc = _client("winner@rico.ai")
        with patch(
            "src.api.routers.journey.get_stats",
            return_value=_stats({"applied": 5, "offer": 1}),
        ):
            r = tc.get("/api/v1/journey/today")
        assert r.status_code == 200
        assert r.json()["journey"]["state"] == "offer"
        assert r.json()["plan"]["actions"][0]["action"] == "review_offer"

    def test_db_unavailable_propagates_503(self):
        from fastapi import HTTPException

        tc = _client("outage@rico.ai")
        with patch(
            "src.api.routers.journey.get_stats",
            side_effect=HTTPException(status_code=503, detail="Database unavailable"),
        ):
            r = tc.get("/api/v1/journey/today")
        assert r.status_code == 503

    def test_identity_comes_from_jwt_only(self):
        """Two different tokens must query stats for their own user only."""
        captured = []

        def spy_stats(user_id=None):
            captured.append(user_id)
            return _stats({})

        with patch("src.api.routers.journey.get_stats", side_effect=spy_stats):
            _client("alice@rico.ai").get("/api/v1/journey/today")
            _client("bob@rico.ai").get("/api/v1/journey/today")
        assert captured == ["alice@rico.ai", "bob@rico.ai"]

    def test_malformed_counts_do_not_fabricate_snapshot(self):
        """Negative/garbage counts are sanitized to 0, never crash or invent data."""
        tc = _client("weird@rico.ai")
        with patch(
            "src.api.routers.journey.get_stats",
            return_value=_stats({"saved": -3, "applied": "x"}),
        ):
            r = tc.get("/api/v1/journey/today")
        assert r.status_code == 200
        assert r.json()["journey"]["state"] == "discovery"
        assert r.json()["journey"]["saved_count"] == 0
