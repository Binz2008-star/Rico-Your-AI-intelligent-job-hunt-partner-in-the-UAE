"""
tests/test_application_status.py

Tests for:
1. ApplicationStatus enum completeness and canonical string values
2. "interviewing" is no longer a valid status (replaced by "interview")
3. Legacy alias resolution via normalise()
4. job_lifecycle.py LIFECYCLE_STATUSES consistency with the shared enum
5. Migration 024 SQL correctness (structural checks — no live DB required)
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.models.application_status import (
    ApplicationStatus,
    VALID_STATUSES,
    is_valid,
    normalise,
)


# ── 1. Enum completeness ─────────────────────────────────────────────────────

class TestApplicationStatusEnum:
    def test_all_expected_values_present(self):
        expected = {
            "found", "saved", "opened_external", "prepared", "applied",
            "interview", "offer", "rejected", "withdrawn", "expired",
            "archived", "on_hold", "needs_source_verification", "needs_review",
        }
        assert expected == VALID_STATUSES

    def test_members_are_str_subclass(self):
        for member in ApplicationStatus:
            assert isinstance(member, str), f"{member} should be a str subclass"

    def test_enum_value_equals_string(self):
        assert ApplicationStatus.APPLIED == "applied"
        assert ApplicationStatus.INTERVIEW == "interview"
        assert ApplicationStatus.WITHDRAWN == "withdrawn"

    def test_valid_statuses_frozenset_is_immutable(self):
        with pytest.raises((AttributeError, TypeError)):
            VALID_STATUSES.add("hacked")  # type: ignore[attr-defined]


# ── 2. "interviewing" must not appear ────────────────────────────────────────

class TestInterviewingRemoved:
    def test_interviewing_not_in_valid_statuses(self):
        assert "interviewing" not in VALID_STATUSES

    def test_interviewing_not_a_member(self):
        with pytest.raises(ValueError):
            ApplicationStatus("interviewing")

    def test_interview_is_valid(self):
        assert "interview" in VALID_STATUSES
        assert ApplicationStatus.INTERVIEW == "interview"

    def test_job_lifecycle_statuses_do_not_contain_interviewing(self):
        from src.job_lifecycle import LIFECYCLE_STATUSES
        assert "interviewing" not in LIFECYCLE_STATUSES, (
            "job_lifecycle.LIFECYCLE_STATUSES still contains 'interviewing' — "
            "should use 'interview' (normalised in migration 024)"
        )

    def test_job_lifecycle_contains_interview(self):
        from src.job_lifecycle import LIFECYCLE_STATUSES
        assert "interview" in LIFECYCLE_STATUSES


# ── 3. Legacy alias resolution ───────────────────────────────────────────────

class TestNormalise:
    def test_interviewing_resolves_to_interview(self):
        assert normalise("interviewing") == "interview"

    def test_interview_scheduled_resolves_to_interview(self):
        assert normalise("interview_scheduled") == "interview"

    def test_opened_resolves_to_opened_external(self):
        assert normalise("opened") == "opened_external"

    def test_canonical_values_pass_through(self):
        for v in VALID_STATUSES:
            assert normalise(v) == v, f"normalise({v!r}) should return itself"

    def test_unknown_value_returns_none(self):
        assert normalise("hacked_status") is None
        assert normalise("") is None
        assert normalise("   ") is None

    def test_case_insensitive(self):
        assert normalise("APPLIED") == "applied"
        assert normalise("Interview") == "interview"

    def test_is_valid_true_for_canonical(self):
        assert is_valid("applied") is True

    def test_is_valid_true_for_alias(self):
        assert is_valid("interviewing") is True

    def test_is_valid_false_for_unknown(self):
        assert is_valid("garbage") is False


# ── 4. job_lifecycle consistency ─────────────────────────────────────────────

class TestJobLifecycleConsistency:
    def test_lifecycle_statuses_are_all_known(self):
        from src.job_lifecycle import LIFECYCLE_STATUSES
        for s in LIFECYCLE_STATUSES:
            assert is_valid(s), (
                f"LIFECYCLE_STATUSES contains unknown value {s!r}. "
                "Either add it to ApplicationStatus or fix the typo."
            )

    def test_action_lifecycle_map_target_statuses_are_valid(self):
        from src.job_lifecycle import _ACTION_LIFECYCLE
        for action, (status, _ts_col) in _ACTION_LIFECYCLE.items():
            assert is_valid(status), (
                f"_ACTION_LIFECYCLE[{action!r}] maps to unknown status {status!r}"
            )


# ── 5. Migration 024 structural check ────────────────────────────────────────

MIGRATION_PATH = (
    Path(__file__).parent.parent / "migrations" / "024_application_lifecycle_columns.sql"
)


class TestMigration024:
    def _sql(self) -> str:
        return MIGRATION_PATH.read_text()

    def test_migration_file_exists(self):
        assert MIGRATION_PATH.exists(), f"Migration not found at {MIGRATION_PATH}"

    def test_adds_saved_at_column(self):
        assert "saved_at" in self._sql()

    def test_adds_opened_at_column(self):
        assert "opened_at" in self._sql()

    def test_adds_prepared_at_column(self):
        assert "prepared_at" in self._sql()

    def test_adds_applied_at_column(self):
        assert "applied_at" in self._sql()

    def test_normalises_interviewing(self):
        sql = self._sql()
        assert "interviewing" in sql, "Migration should UPDATE rows with status='interviewing'"
        assert "'interview'" in sql, "Migration should set status to 'interview'"

    def test_check_constraint_includes_all_statuses(self):
        sql = self._sql()
        for status in VALID_STATUSES:
            assert f"'{status}'" in sql, (
                f"CHECK constraint in migration 024 is missing '{status}'"
            )

    def test_check_constraint_excludes_interviewing(self):
        sql = self._sql()
        # "interviewing" should appear only inside the UPDATE (to normalise), not
        # inside the CHECK constraint list.
        check_block = re.search(r"ADD CONSTRAINT.*?CHECK\s*\(.*?\);", sql, re.DOTALL)
        if check_block:
            assert "'interviewing'" not in check_block.group(), (
                "CHECK constraint must not include 'interviewing' — only 'interview'"
            )

    def test_uses_add_column_if_not_exists(self):
        assert "ADD COLUMN IF NOT EXISTS" in self._sql()

    def test_drops_old_constraint_before_adding(self):
        sql = self._sql()
        assert "DROP CONSTRAINT IF EXISTS" in sql
