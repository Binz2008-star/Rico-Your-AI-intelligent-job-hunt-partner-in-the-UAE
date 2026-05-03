"""
Unit Tests for FeedbackLoopOrchestrator
Tests assert expected behavior with explicit boundary testing.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any

from src.decision_engine_v2 import JobDecisionEngine
from src.feedback_loop import FeedbackLoopOrchestrator, CycleState, CycleResult


# Test data factories
def make_job(link: str, score: int = 80) -> Dict[str, Any]:
    """Create a test job with required fields."""
    return {
        "title": f"Job {link}",
        "company": f"Corp {link}",
        "score": score,
        "link": link,
        "location": "Dubai"
    }


def make_app(link: str, status: str = "interview_scheduled") -> Dict[str, Any]:
    """Create a test application with required fields."""
    return {
        "title": f"Job {link}",
        "company": f"Corp {link}",
        "status": status,
        "date_applied": "2024-01-01T10:00:00Z",
        "date_updated": "2024-01-03T14:00:00Z",
        "link": link
    }


class TestFeedbackLoopOrchestrator:
    """Test suite for FeedbackLoopOrchestrator with boundary-aware assertions."""

    def test_orchestrator_initialization(self) -> None:
        """Test orchestrator builds correctly with expected initial state."""
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

    def test_learning_cycle_below_minimum_threshold(self) -> None:
        """Test that cycles fail below the minimum sample threshold."""
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

            # Test boundary: one below minimum (4 pairs)
            n = 4  # Explicitly testing below threshold
            jobs = [make_job(f"j{i}") for i in range(n)]
            apps = [make_app(f"j{i}") for i in range(n)]

            result = orchestrator.run_cycle_sync(lambda: jobs, lambda: apps)

            # Should fail, not silently succeed
            assert result.status == "failed"
            assert result.error is not None
            assert "Need at least" in result.error  # Error message mentions threshold
            assert result.matched_pairs == 0  # Failed cycles report 0 matched pairs

            # State should reflect failure
            state_after = orchestrator.cycle_state
            assert state_after.last_run_status == "failed"
            assert state_after.last_error is not None

    def test_learning_cycle_at_minimum_threshold(self) -> None:
        """Test that cycles succeed exactly at the minimum sample threshold."""
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

            # Test boundary: exactly at minimum (5 pairs)
            n = 5  # Explicitly testing at threshold
            jobs = [make_job(f"j{i}") for i in range(n)]
            apps = [make_app(f"j{i}") for i in range(n)]

            result = orchestrator.run_cycle_sync(lambda: jobs, lambda: apps)

            # Should succeed
            assert result.status == "success"
            assert result.matched_pairs == n
            assert result.adjustments_version >= 1
            assert result.error is None

            # State should reflect success
            state_after = orchestrator.cycle_state
            assert state_after.last_run_status == "success"
            assert state_after.total_samples_processed == n

    def test_learning_cycle_above_minimum_threshold(self) -> None:
        """Test that cycles succeed well above the minimum sample threshold."""
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

            # Test boundary: well above minimum (20 pairs = 4x minimum)
            n = 20  # Explicitly testing above threshold - proves it scales
            jobs = [make_job(f"j{i}") for i in range(n)]
            apps = [make_app(f"j{i}") for i in range(n)]

            result = orchestrator.run_cycle_sync(lambda: jobs, lambda: apps)

            # Should succeed with larger dataset
            assert result.status == "success"
            assert result.matched_pairs == n
            assert result.adjustments_version >= 1
            assert result.error is None

            # State should reflect success with all samples
            state_after = orchestrator.cycle_state
            assert state_after.total_samples_processed == n

    def test_cooldown_boundary_at_expiration(self) -> None:
        """Test cooldown behavior exactly at the expiration boundary."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)

            decision_engine = JobDecisionEngine.from_loaders(
                lambda: {"experience_years": 5, "skills": {}, "location": "Dubai"},
                lambda: ["engineer"]
            )

            # Use short cooldown for testing
            cooldown = timedelta(seconds=1)
            orchestrator = FeedbackLoopOrchestrator.build(
                decision_engine=decision_engine,
                state_dir=state_dir,
                cooldown=cooldown
            )

            # Create sufficient data
            jobs = [make_job(f"j{i}") for i in range(5)]
            apps = [make_app(f"j{i}") for i in range(5)]

            # First cycle should succeed
            result1 = orchestrator.run_cycle_sync(lambda: jobs, lambda: apps)
            assert result1.status == "success"

            # Immediately should be skipped
            result2 = orchestrator.run_cycle_sync(lambda: jobs, lambda: apps)
            assert result2.status == "skipped"
            assert "cooldown" in result2.skipped_reason.lower()

            # Wait exactly the cooldown period
            import time
            time.sleep(cooldown.total_seconds())

            # Should be due again
            assert orchestrator.is_due() == True

            # Should succeed again
            result3 = orchestrator.run_cycle_sync(lambda: jobs, lambda: apps)
            assert result3.status == "success"

    def test_cooldown_before_expiration(self) -> None:
        """Test that cycles are skipped before cooldown expiration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)

            decision_engine = JobDecisionEngine.from_loaders(
                lambda: {"experience_years": 5, "skills": {}, "location": "Dubai"},
                lambda: ["engineer"]
            )

            # Use longer cooldown for testing
            cooldown = timedelta(hours=1)
            orchestrator = FeedbackLoopOrchestrator.build(
                decision_engine=decision_engine,
                state_dir=state_dir,
                cooldown=cooldown
            )

            jobs = [make_job(f"j{i}") for i in range(5)]
            apps = [make_app(f"j{i}") for i in range(5)]

            # First cycle
            result1 = orchestrator.run_cycle_sync(lambda: jobs, lambda: apps)
            assert result1.status == "success"

            # Multiple attempts before expiration should all be skipped
            for attempt in range(3):
                result = orchestrator.run_cycle_sync(lambda: jobs, lambda: apps)
                assert result.status == "skipped"
                assert result.duration_seconds == 0
                assert "cooldown" in result.skipped_reason.lower()

            # State should not have changed after skips
            state_after = orchestrator.cycle_state
            assert state_after.total_cycles == 1  # Only first successful cycle

    def test_state_persistence_across_instances(self) -> None:
        """Test that cycle state persists across orchestrator instances."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)

            decision_engine = JobDecisionEngine.from_loaders(
                lambda: {"experience_years": 5, "skills": {}, "location": "Dubai"},
                lambda: ["engineer"]
            )

            # First orchestrator instance
            orchestrator1 = FeedbackLoopOrchestrator.build(
                decision_engine=decision_engine,
                state_dir=state_dir,
                cooldown=timedelta(hours=1)
            )

            jobs = [make_job(f"j{i}") for i in range(10)]  # Use larger dataset
            apps = [make_app(f"j{i}") for i in range(10)]

            result1 = orchestrator1.run_cycle_sync(lambda: jobs, lambda: apps)
            assert result1.status == "success"
            assert result1.matched_pairs == 10

            # Second orchestrator instance with same state directory
            orchestrator2 = FeedbackLoopOrchestrator.build(
                decision_engine=decision_engine,
                state_dir=state_dir,
                cooldown=timedelta(hours=1)
            )

            # State should be fully restored
            state_restored = orchestrator2.cycle_state
            assert state_restored.total_cycles == 1
            assert state_restored.total_samples_processed == 10
            assert state_restored.last_run_status == "success"
            assert state_restored.last_adjustments_version == result1.adjustments_version
            assert state_restored.last_run_at is not None
            assert state_restored.last_error is None

    def test_background_cycle_non_blocking(self) -> None:
        """Test that background cycle scheduling doesn't block."""
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

            jobs = [make_job(f"j{i}") for i in range(5)]
            apps = [make_app(f"j{i}") for i in range(5)]

            # Schedule background cycle - should return immediately
            start_time = datetime.now()
            orchestrator.schedule_background_cycle(lambda: jobs, lambda: apps)
            end_time = datetime.now()

            # Should return immediately (under 10ms)
            assert (end_time - start_time).total_seconds() < 0.01

            # Give background cycle time to complete
            import time
            time.sleep(0.1)

            # Check that cycle completed in background
            state_after = orchestrator.cycle_state
            assert state_after.total_cycles == 1
            assert state_after.last_run_status == "success"

    def test_empty_data_error_handling(self) -> None:
        """Test error handling with completely empty data."""
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

            # Completely empty data
            result = orchestrator.run_cycle_sync(lambda: [], lambda: [])

            assert result.status == "failed"
            assert "Insufficient data" in result.error
            assert result.matched_pairs == 0

            # Failed cycles should not trigger cooldown
            assert orchestrator.is_due() == True


if __name__ == "__main__":
    # Allow running tests directly
    test_instance = TestFeedbackLoopOrchestrator()

    print("🧪 Running FeedbackLoopOrchestrator Boundary Tests")
    print("=" * 60)

    tests = [
        ("Initialization", test_instance.test_orchestrator_initialization),
        ("Below Minimum Threshold", test_instance.test_learning_cycle_below_minimum_threshold),
        ("At Minimum Threshold", test_instance.test_learning_cycle_at_minimum_threshold),
        ("Above Minimum Threshold", test_instance.test_learning_cycle_above_minimum_threshold),
        ("Cooldown at Expiration", test_instance.test_cooldown_boundary_at_expiration),
        ("Cooldown Before Expiration", test_instance.test_cooldown_before_expiration),
        ("State Persistence", test_instance.test_state_persistence_across_instances),
        ("Background Non-Blocking", test_instance.test_background_cycle_non_blocking),
        ("Empty Data Error", test_instance.test_empty_data_error_handling),
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

    print("=" * 60)
    print(f"Results: {passed}/{passed + failed} tests passed")

    if failed == 0:
        print("🎉 All boundary tests passed!")
    else:
        print(f"⚠️  {failed} test(s) failed")
