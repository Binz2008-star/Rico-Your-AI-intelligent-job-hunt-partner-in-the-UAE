"""Learning-signal hygiene: personalization learns from USERS only.

The daily pipeline used to record Rico's own top matches as user "save"
signals (source="daily_pipeline") — an echo loop that trained the taste model
on system output. These tests pin the remediation at all three layers:

1. the pipeline-side writer is gone from src/run_daily.py;
2. every read path (DB load + decay aggregation + write-time EMA cache)
   excludes the historical polluted source;
3. real user-action signals keep flowing untouched.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.repositories import learning_repo
from src.repositories.learning_repo import (
    LearningProfile,
    LearningRepository,
    LearningSignal,
    _EXCLUDED_SIGNAL_SOURCES,
)

_NOW = datetime.now(timezone.utc)


def _repo() -> LearningRepository:
    # Force the in-memory cache so tests never create a diskcache directory.
    with patch.object(learning_repo, "DISKCACHE_AVAILABLE", False):
        return LearningRepository()


def _signal(source: str, value: str, weight: float = 0.8) -> LearningSignal:
    return LearningSignal(
        signal_type="role_preference",
        signal_value=value,
        signal_weight=weight,
        source=source,
        timestamp=_NOW - timedelta(days=1),
    )


def test_daily_pipeline_writer_is_gone_from_run_daily():
    text = Path("src/run_daily.py").read_text(encoding="utf-8")
    assert "_update_learning_repo" not in text
    assert "infer_signals_from_job_action" not in text
    assert 'source="daily_pipeline"' not in text


def test_daily_pipeline_source_is_excluded():
    assert "daily_pipeline" in _EXCLUDED_SIGNAL_SOURCES


def test_decay_aggregation_ignores_excluded_sources():
    repo = _repo()
    profile = LearningProfile(canonical_user_id="u@x.com")
    profile.signal_history = [
        _signal("daily_pipeline", "Ghost Role"),
        _signal("job_action", "Real Role"),
    ]
    decayed = repo._apply_decay_to_profile(profile)
    assert "Ghost Role" not in decayed.role_preferences
    assert "Real Role" in decayed.role_preferences


def test_db_load_filters_excluded_sources_in_sql():
    repo = _repo()
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchall.return_value = []
    with patch.object(learning_repo, "get_db_connection", return_value=conn):
        repo._db_load_profile("u@x.com")
    sql, params = cursor.execute.call_args[0]
    assert "source = ANY" in sql
    assert list(_EXCLUDED_SIGNAL_SOURCES) in list(params)


def test_write_time_cache_aggregation_ignores_excluded_sources():
    repo = _repo()
    with patch.object(learning_repo, "is_db_available", return_value=False):
        repo.record_signal("u@x.com", "role_preference", "Ghost Role",
                           signal_weight=0.9, source="daily_pipeline")
        repo.record_signal("u@x.com", "role_preference", "Real Role",
                           signal_weight=0.9, source="job_action")
    profile = repo._cache["u@x.com"]
    assert "Ghost Role" not in profile.role_preferences
    assert "Real Role" in profile.role_preferences
    # history keeps both (record vs influence are different things)
    assert {s.signal_value for s in profile.signal_history} == {"Ghost Role", "Real Role"}


def test_user_action_signals_still_flow_end_to_end():
    repo = _repo()
    with patch.object(learning_repo, "is_db_available", return_value=False):
        repo.infer_signals_from_job_action(
            "u@x.com", "save",
            {"title": "Operations Manager", "company": "ACME", "location": "Dubai"},
        )
    top_roles = repo.get_top_preferences("u@x.com", "role")
    assert any("Operations" in role for role, _ in top_roles)
