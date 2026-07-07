"""Pure helpers for Rico operational memory readiness."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

UTC = timezone.utc
DEFAULT_REVISIT_DAYS = 7


@dataclass(frozen=True)
class RevisitCandidate:
    title: str
    company: str
    applied_at: datetime
    days_since_applied: int
    apply_url: str = ""
    source_url: str = ""


def normalize_status(value: object) -> str:
    return str(value or "").strip().lower()


def clean_text(value: object) -> str:
    return str(value or "").strip()


def as_utc_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def build_revisit_candidate(
    row: dict[str, Any],
    *,
    now: datetime | None = None,
    min_days_since_applied: int = DEFAULT_REVISIT_DAYS,
) -> RevisitCandidate | None:
    current = (now or datetime.now(UTC)).astimezone(UTC)
    minimum_days = max(0, int(min_days_since_applied))

    if normalize_status(row.get("status")) != "applied":
        return None
    if row.get("interview_at") or row.get("closed_at"):
        return None

    applied_at = as_utc_datetime(row.get("applied_at"))
    if applied_at is None:
        return None

    days_since = (current.date() - applied_at.date()).days
    if days_since < minimum_days:
        return None

    title = clean_text(row.get("title"))
    company = clean_text(row.get("company"))
    if not title or not company:
        return None

    return RevisitCandidate(
        title=title,
        company=company,
        applied_at=applied_at,
        days_since_applied=days_since,
        apply_url=clean_text(row.get("apply_url")),
        source_url=clean_text(row.get("source_url")),
    )


def select_revisit_candidates(
    rows: Iterable[dict[str, Any]],
    *,
    now: datetime | None = None,
    min_days_since_applied: int = DEFAULT_REVISIT_DAYS,
    limit: int = 25,
) -> list[RevisitCandidate]:
    max_items = max(0, int(limit))
    if max_items == 0:
        return []

    candidates: list[RevisitCandidate] = []
    for row in rows:
        candidate = build_revisit_candidate(
            row,
            now=now,
            min_days_since_applied=min_days_since_applied,
        )
        if candidate is not None:
            candidates.append(candidate)

    candidates.sort(key=lambda item: (item.applied_at, item.company.lower(), item.title.lower()))
    return candidates[:max_items]
