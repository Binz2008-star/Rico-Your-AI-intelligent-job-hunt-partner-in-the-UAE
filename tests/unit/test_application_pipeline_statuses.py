"""Unit tests for Application Pipeline V1 status alignment.

Verifies that the frontend ApplicationStatus type (documented here as the
canonical set) is a subset of the backend VALID_STATUSES, and that the three
statuses added in TASK-20260617-013 are present in both sets.

All pure-function; no DB, no network, no external services.
"""
from __future__ import annotations

import pytest

from src.applications import VALID_STATUSES

# Canonical frontend statuses after TASK-20260617-013
FRONTEND_STATUSES = {
    "saved",
    "opened",
    "opened_external",
    "prepared",
    "applied",
    "follow_up_due",
    "interview",
    "offer",
    "rejected",
    "decision_made",
}

# The three statuses added in this task
NEW_STATUSES = {"opened_external", "prepared", "follow_up_due"}


class TestStatusAlignment:
    def test_new_statuses_in_backend_valid_statuses(self):
        for status in NEW_STATUSES:
            assert status in VALID_STATUSES, f"{status!r} missing from backend VALID_STATUSES"

    def test_all_frontend_statuses_accepted_by_backend(self):
        for status in FRONTEND_STATUSES:
            assert status in VALID_STATUSES, (
                f"Frontend status {status!r} not in backend VALID_STATUSES — "
                "backend would reject it with 422"
            )

    def test_opened_external_in_valid_statuses(self):
        assert "opened_external" in VALID_STATUSES

    def test_prepared_in_valid_statuses(self):
        assert "prepared" in VALID_STATUSES

    def test_follow_up_due_in_valid_statuses(self):
        assert "follow_up_due" in VALID_STATUSES

    def test_core_pipeline_statuses_present(self):
        core = {"saved", "applied", "interview", "offer", "rejected"}
        for status in core:
            assert status in VALID_STATUSES

    def test_backend_accepts_no_unknown_frontend_status(self):
        unknown = FRONTEND_STATUSES - VALID_STATUSES
        assert not unknown, f"Frontend has statuses not in backend: {unknown}"
