"""
Unit Tests for FeedbackLoopOrchestrator
Tests assert expected behavior with deterministic data.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any
import pytest

from src.decision_engine_v2 import JobDecisionEngine
from src.feedback_loop import FeedbackLoopOrchestrator, CycleState, CycleResult


class TestFeedbackLoopOrchestrator:
    """Test suite for FeedbackLoopOrchestrator with deterministic assertions."""

    def test_orchestrator_initialization(self) -> None:
        """Test orchestrator builds correctly with expected initial state."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)

            # Create decision engine
            decision_engine = JobDecisionEngine.from_loaders(
                lambda: {"experience_years": 5, "skills": {}, "location": "Dubai"},
                lambda: ["engineer"]
            )

            # Build orchestrator
            orchestrator = FeedbackLoopOrchestrator.build(
                decision_engine=decision_engine,
                state_dir=state_dir,
                cooldown=timedelta(hours=1)
            )

            # Assert initial state
            state = orchestrator.cycle_state
            assert state.last_run_status == "never"
            assert state.total_cycles == 0
            assert state.total_samples_processed == 0
            assert state.last_adjustments_version == 0
            assert state.last_run_at is None
            assert state.last_error is None

            # Should be due initially
            assert orchestrator.is_due() == True

            # Engine should be accessible
            assert hasattr(orchestrator.engine, 'adjusted_probability')

    def test_successful_learning_cycle(self) -> None:
        """Test successful learning cycle with exactly 5 matched pairs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)

            decision_engine = JobDecisionEngine.from_loaders(
                lambda: {"experience_years": 5, "skills": {}, "location": "Dubai"},
                lambda: ["engineer"]
            )

            orchestrator = FeedbackLoopOrchestrator.build(
                decision_engine=decision_engine,
                state_dir=state_dir,
                cooldown=timedelta(hours=1)
            )

            # Create exactly 5 jobs and 5 matching applications (minimum required)
            jobs = [
                {"title": "Engineer", "company": "Corp A", "score": 80, "link": "job1", "location": "Dubai"},
                {"title": "Developer", "company": "Corp B", "score": 75, "link": "job2", "location": "Abu Dhabi"},
                {"title": "Senior Engineer", "company": "Corp C", "score": 85, "link": "job3", "location": "Dubai"},
                {"title": "Tech Lead", "company": "Corp D", "score": 90, "link": "job4", "location": "Sharjah"},
                {"title": "Principal Engineer", "company": "Corp E", "score": 95, "link": "job5", "location": "Abu Dhabi"},
            ]

            apps = [
                {"title": "Engineer", "company": "Corp A", "status": "interview_scheduled", "date_applied": "2024-01-01T10:00:00Z", "date_updated": "2024-01-03T14:00:00Z", "link": "job1"},
                {"title": "Developer", "company": "Corp B", "status": "rejected", "date_applied": "2024-01-02T11:00:00Z", "date_updated": "2024-01-04T16:00:00Z", "link": "job2"},
                {"title": "Senior Engineer", "company": "Corp C", "status": "offer_extended", "date_applied": "2024-01-03T12:00:00Z", "date_updated": "2024-01-05T18:00:00Z", "link": "job3"},
                {"title": "Tech Lead", "company": "Corp D", "status": "interview_completed", "date_applied": "2024-01-04T13:00:00Z", "date_updated": "2024-01-06T17:00:00Z", "link": "job4"},
                {"title": "Principal Engineer", "company": "Corp E", "status": "screening", "date_applied": "2024-01-05T14:00:00Z", "date_updated": "2024-01-07T19:00:00Z", "link": "job5"},
            ]

            # Run cycle
            result = orchestrator.run_cycle_sync(lambda: jobs, lambda: apps)

            # Assert expected results - exactly 5 matched pairs
            assert result.status == "success"
            assert result.matched_pairs == 5  # All 5 jobs have matching applications
            assert result.adjustments_version >= 1
            assert result.duration_seconds >= 0
            assert result.error is None
            assert result.skipped_reason is None

            # Assert state updated correctly
            state_after = orchestrator.cycle_state
            assert state_after.last_run_status == "success"
            assert state_after.total_cycles == 1
            assert state_after.total_samples_processed == 5
            assert state_after.last_adjustments_version == result.adjustments_version
            assert state_after.last_error is None
            assert state_after.last_run_at is not None

    def test_insufficient_data_error(self) -> None:
        """Test error handling when insufficient data provided."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)

            decision_engine = JobDecisionEngine.from_loaders(
                lambda: {"experience_years": 5, "skills": {}, "location": "Dubai"},
                lambda: ["engineer"]
            )

            orchestrator = FeedbackLoopOrchestrator.build(
                decision_engine=decision_engine,
                state_dir=state_dir,
                cooldown=timedelta(hours=1)
            )

            # Empty data should fail
            result = orchestrator.run_cycle_sync(lambda: [], lambda: [])

            assert result.status == "failed"
            assert "Insufficient data" in result.error
            assert result.matched_pairs == 0
            assert result.adjustments_version == 0
            assert result.duration_seconds >= 0

            # State should reflect failure
            state_after = orchestrator.cycle_state
            assert state_after.last_run_status == "failed"
            assert state_after.last_error is not None
            assert "Insufficient data" in state_after.last_error

            # Failed cycles should not trigger cooldown
            assert orchestrator.is_due() == True

    def test_cooldown_skip_logic(self) -> None:
        """Test that cycles are skipped during cooldown period."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)

            decision_engine = JobDecisionEngine.from_loaders(
                lambda: {"experience_years": 5, "skills": {}, "location": "Dubai"},
                lambda: ["engineer"]
            )

            orchestrator = FeedbackLoopOrchestrator.build(
                decision_engine=decision_engine,
                state_dir=state_dir,
                cooldown=timedelta(hours=1)  # Long cooldown
            )

            # Create sufficient data for learning
            jobs = [
                {"title": f"Job {i}", "company": f"Corp {i}", "score": 80, "link": f"job{i}", "location": "Dubai"}
                for i in range(5)  # Need at least 5 for learning
            ]

            apps = [
                {"title": f"Job {i}", "company": f"Corp {i}", "status": "interview_scheduled",
                 "date_applied": "2024-01-01T10:00:00Z", "date_updated": "2024-01-03T14:00:00Z", "link": f"job{i}"}
                for i in range(5)
            ]

            # First cycle should succeed
            result1 = orchestrator.run_cycle_sync(lambda: jobs, lambda: apps)
            assert result1.status == "success"
            assert result1.matched_pairs == 5

            # Second cycle immediately should be skipped
            result2 = orchestrator.run_cycle_sync(lambda: jobs, lambda: apps)
            assert result2.status == "skipped"
            assert "cooldown" in result2.skipped_reason.lower()
            assert result2.duration_seconds == 0

            # State should not have changed after skip
            state_after = orchestrator.cycle_state
            assert state_after.total_cycles == 1  # Still only 1 successful cycle
            assert state_after.total_samples_processed == 5

    def test_state_persistence(self) -> None:
        """Test that cycle state persists across orchestrator instances."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)

            decision_engine = JobDecisionEngine.from_loaders(
                lambda: {"experience_years": 5, "skills": {}, "location": "Dubai"},
                lambda: ["engineer"]
            )

            # Create first orchestrator and run a cycle
            orchestrator1 = FeedbackLoopOrchestrator.build(
                decision_engine=decision_engine,
                state_dir=state_dir,
                cooldown=timedelta(hours=1)
            )

            jobs = [{"title": f"Job {i}", "company": f"Corp {i}", "score": 80, "link": f"job{i}", "location": "Dubai"} for i in range(5)]
            apps = [{"title": f"Job {i}", "company": f"Corp {i}", "status": "interview_scheduled", "date_applied": "2024-01-01T10:00:00Z", "date_updated": "2024-01-03T14:00:00Z", "link": f"job{i}"} for i in range(5)]

            result1 = orchestrator1.run_cycle_sync(lambda: jobs, lambda: apps)
            assert result1.status == "success"

            # Create second orchestrator with same state directory
            orchestrator2 = FeedbackLoopOrchestrator.build(
                decision_engine=decision_engine,
                state_dir=state_dir,
                cooldown=timedelta(hours=1)
            )

            # State should be restored
            state_restored = orchestrator2.cycle_state
            assert state_restored.total_cycles == 1
            assert state_restored.total_samples_processed == 5
            assert state_restored.last_run_status == "success"
            assert state_restored.last_adjustments_version == result1.adjustments_version
            assert state_restored.last_run_at is not None

    def test_background_cycle_scheduling(self) -> None:
        """Test background cycle scheduling doesn't block."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)

            decision_engine = JobDecisionEngine.from_loaders(
                lambda: {"experience_years": 5, "skills": {}, "location": "Dubai"},
                lambda: ["engineer"]
            )

            orchestrator = FeedbackLoopOrchestrator.build(
                decision_engine=decision_engine,
                state_dir=state_dir,
                cooldown=timedelta(hours=1)
            )

            jobs = [{"title": f"Job {i}", "company": f"Corp {i}", "score": 80, "link": f"job{i}", "location": "Dubai"} for i in range(5)]
            apps = [{"title": f"Job {i}", "company": f"Corp {i}", "status": "interview_scheduled", "date_applied": "2024-01-01T10:00:00Z", "date_updated": "2024-01-03T14:00:00Z", "link": f"job{i}"} for i in range(5)]

            # Schedule background cycle - should return immediately
            orchestrator.schedule_background_cycle(lambda: jobs, lambda: apps)

            # Give it a moment to complete
            import time
            time.sleep(0.1)

            # Check that cycle completed
            state_after = orchestrator.cycle_state
            assert state_after.total_cycles == 1
            assert state_after.last_run_status == "success"


if __name__ == "__main__":
    # Allow running tests directly
    test_instance = TestFeedbackLoopOrchestrator()

    print("🧪 Running FeedbackLoopOrchestrator Unit Tests")
    print("=" * 50)

    tests = [
        ("Initialization", test_instance.test_orchestrator_initialization),
        ("Successful Learning Cycle", test_instance.test_successful_learning_cycle),
        ("Insufficient Data Error", test_instance.test_insufficient_data_error),
        ("Cooldown Skip Logic", test_instance.test_cooldown_skip_logic),
        ("State Persistence", test_instance.test_state_persistence),
        ("Background Scheduling", test_instance.test_background_cycle_scheduling),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            test_func()
            print(f"✅ {name}")
            passed += 1
        except Exception as e:
            print(f"❌ {name}: {str(e)}")
            failed += 1

    print("=" * 50)
    print(f"Results: {passed}/{passed + failed} tests passed")

    if failed == 0:
        print("🎉 All tests passed!")
    else:
        print(f"⚠️  {failed} test(s) failed")
