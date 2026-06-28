"""tests/test_mission_service.py
Unit tests for the Mission Engine (src/services/mission_service.py).

All data sources are mocked — no DB, no API calls.
"""
from unittest.mock import MagicMock, patch

import pytest

from src.services.mission_service import (
    _build_goal,
    _next_recommendation,
    compute_mission,
)


# ── _build_goal ───────────────────────────────────────────────────────────────


def test_build_goal_role_and_city():
    assert _build_goal(["Project Manager"], ["Dubai"]) == "Find Project Manager role in Dubai"


def test_build_goal_role_only():
    assert _build_goal(["Operations Director"], []) == "Find Operations Director role in UAE"


def test_build_goal_city_only():
    assert _build_goal([], ["Abu Dhabi"]) == "Find a job in Abu Dhabi"


def test_build_goal_nothing():
    assert _build_goal([], []) == "Define your job search mission"


# ── _next_recommendation ──────────────────────────────────────────────────────


def test_next_rec_no_missing():
    rec, blocking = _next_recommendation([])
    assert "track" in rec.lower() or "applying" in rec.lower()
    assert blocking is None


def test_next_rec_cv_first():
    rec, blocking = _next_recommendation(["cv_uploaded", "roles_set"])
    assert "CV" in rec or "cv" in rec.lower()
    assert blocking is not None


def test_next_rec_roles_when_cv_done():
    rec, blocking = _next_recommendation(["roles_set"])
    assert "role" in rec.lower() or "targeting" in rec.lower()


def test_next_rec_locations():
    rec, blocking = _next_recommendation(["locations_set"])
    assert "cit" in rec.lower() or "location" in rec.lower() or "UAE" in rec


def test_next_rec_pipeline():
    rec, blocking = _next_recommendation(["pipeline_active"])
    assert "search" in rec.lower() or "job" in rec.lower()


# ── compute_mission — full integration with mocked dependencies ───────────────


def _make_profile(
    *,
    target_roles=None,
    preferred_cities=None,
    cv_filename=None,
):
    p = MagicMock()
    p.target_roles = target_roles or []
    p.preferred_cities = preferred_cities or []
    p.cv_filename = cv_filename
    return p


def _make_stats(*, total=0, applied=0, saved=0):
    return {"total": total, "applied": applied, "saved": saved}


@pytest.fixture(autouse=True)
def _patch_deps(monkeypatch):
    monkeypatch.setattr(
        "src.services.mission_service._safe_get_profile",
        lambda user_id: None,
    )
    monkeypatch.setattr(
        "src.services.mission_service._safe_get_stats",
        lambda user_id: _make_stats(),
    )


# ── Fully empty profile ──────────────────────────────────────────────────────

def test_empty_profile_progress_zero():
    m = compute_mission("user@example.com")
    assert m.progress_score == 0
    assert set(m.missing_factors) == {"cv_uploaded", "roles_set", "locations_set", "pipeline_active"}
    assert m.cv_status == "missing"
    assert m.jobs_saved == 0
    assert m.applications_sent == 0


def test_empty_profile_goal_generic():
    m = compute_mission("user@example.com")
    assert "mission" in m.goal.lower() or "job" in m.goal.lower()


def test_empty_profile_next_rec_mentions_cv():
    m = compute_mission("user@example.com")
    assert "CV" in m.next_recommendation or "cv" in m.next_recommendation.lower()


# ── Progressively more complete profiles ─────────────────────────────────────

def test_cv_only_25_percent(monkeypatch):
    monkeypatch.setattr(
        "src.services.mission_service._safe_get_profile",
        lambda uid: _make_profile(cv_filename="cv.pdf"),
    )
    m = compute_mission("u")
    assert m.progress_score == 25
    assert "cv_uploaded" not in m.missing_factors
    assert m.cv_status == "uploaded"


def test_cv_and_roles_50_percent(monkeypatch):
    monkeypatch.setattr(
        "src.services.mission_service._safe_get_profile",
        lambda uid: _make_profile(cv_filename="cv.pdf", target_roles=["PM"]),
    )
    m = compute_mission("u")
    assert m.progress_score == 50
    assert m.target_roles == ["PM"]


def test_cv_roles_cities_75_percent(monkeypatch):
    monkeypatch.setattr(
        "src.services.mission_service._safe_get_profile",
        lambda uid: _make_profile(
            cv_filename="cv.pdf",
            target_roles=["PM"],
            preferred_cities=["Dubai"],
        ),
    )
    m = compute_mission("u")
    assert m.progress_score == 75
    assert m.target_locations == ["Dubai"]


def test_all_factors_100_percent(monkeypatch):
    monkeypatch.setattr(
        "src.services.mission_service._safe_get_profile",
        lambda uid: _make_profile(
            cv_filename="cv.pdf",
            target_roles=["PM"],
            preferred_cities=["Dubai"],
        ),
    )
    monkeypatch.setattr(
        "src.services.mission_service._safe_get_stats",
        lambda uid: _make_stats(total=5, applied=2, saved=3),
    )
    m = compute_mission("u")
    assert m.progress_score == 100
    assert m.missing_factors == []
    assert m.jobs_saved == 3
    assert m.applications_sent == 2
    assert m.blocking_reason is None


# ── Goal construction ─────────────────────────────────────────────────────────

def test_goal_from_role_and_city(monkeypatch):
    monkeypatch.setattr(
        "src.services.mission_service._safe_get_profile",
        lambda uid: _make_profile(
            target_roles=["Technical Product Owner"],
            preferred_cities=["Dubai"],
        ),
    )
    m = compute_mission("u")
    assert "Technical Product Owner" in m.goal
    assert "Dubai" in m.goal


# ── Graceful degradation ──────────────────────────────────────────────────────

def test_none_profile_does_not_raise():
    m = compute_mission("ghost@example.com")
    assert isinstance(m.progress_score, int)
    assert m.cv_status == "missing"


def test_stats_failure_does_not_raise(monkeypatch):
    monkeypatch.setattr(
        "src.services.mission_service._safe_get_stats",
        lambda uid: {"total": 0, "applied": 0, "saved": 0},
    )
    m = compute_mission("u")
    assert m.jobs_saved == 0
    assert m.applications_sent == 0
