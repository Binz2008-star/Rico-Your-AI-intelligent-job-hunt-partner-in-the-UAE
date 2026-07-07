from __future__ import annotations

from datetime import datetime, timezone

from src.services.operational_memory_readiness import (
    build_revisit_candidate,
    select_revisit_candidates,
)

UTC = timezone.utc
NOW = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)


def test_build_revisit_candidate_for_old_applied_row() -> None:
    candidate = build_revisit_candidate(
        {
            "title": "Environmental Manager",
            "company": "AESG",
            "status": "applied",
            "applied_at": "2026-06-30T09:00:00Z",
            "apply_url": "https://example.com/apply",
            "source_url": "https://example.com/job",
        },
        now=NOW,
    )

    assert candidate is not None
    assert candidate.title == "Environmental Manager"
    assert candidate.company == "AESG"
    assert candidate.days_since_applied == 8


def test_recent_applied_row_is_not_ready_to_revisit() -> None:
    candidate = build_revisit_candidate(
        {
            "title": "QHSE Manager",
            "company": "Hotel Group",
            "status": "applied",
            "applied_at": "2026-07-06T09:00:00Z",
        },
        now=NOW,
    )

    assert candidate is None


def test_rows_without_active_applied_state_are_excluded() -> None:
    rows = [
        {
            "title": "Saved Role",
            "company": "A",
            "status": "saved",
            "applied_at": "2026-06-01T09:00:00Z",
        },
        {
            "title": "Handled Role",
            "company": "B",
            "status": "applied",
            "applied_at": "2026-06-01T09:00:00Z",
            "interview_at": "2026-06-05T09:00:00Z",
        },
    ]

    assert select_revisit_candidates(rows, now=NOW) == []


def test_select_revisit_candidates_is_deterministic_and_limited() -> None:
    rows = [
        {
            "title": "Later",
            "company": "B",
            "status": "applied",
            "applied_at": "2026-06-29T09:00:00Z",
        },
        {
            "title": "Earlier",
            "company": "A",
            "status": "applied",
            "applied_at": datetime(2026, 6, 20, 9, 0, tzinfo=UTC),
        },
    ]

    candidates = select_revisit_candidates(rows, now=NOW, limit=1)

    assert len(candidates) == 1
    assert candidates[0].title == "Earlier"
