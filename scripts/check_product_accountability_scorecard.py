#!/usr/bin/env python3
"""Validate Rico's machine-readable product accountability scorecard.

The checker is intentionally standard-library only. It prevents:
- missing accountability categories;
- duplicate or unknown metric identifiers;
- reporting an unmeasured metric as zero;
- claiming "verified" without a value and dated evidence;
- stale weekly scorecards when the scheduled workflow requests a freshness gate.

It does not contact production systems and never invents metric values.
"""

from __future__ import annotations

import argparse
import copy
import json
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

DEFAULT_SCORECARD = Path("AI_WORKSPACE/product_accountability_scorecard.json")

REQUIRED_TOP_LEVEL = {
    "schema_version",
    "as_of",
    "owner",
    "north_star_metric_id",
    "strategy_source",
    "required_categories",
    "metrics",
}

REQUIRED_CATEGORIES = {
    "delivery",
    "reliability",
    "activation",
    "engagement",
    "search_quality",
    "applications",
    "outcomes",
    "retention",
    "ai_quality",
    "business",
}

REQUIRED_METRIC_FIELDS = {
    "id",
    "name",
    "category",
    "status",
    "value",
    "unit",
    "target",
    "owner",
    "cadence",
    "source",
    "evidence",
    "blocker",
    "next_action",
}

ALLOWED_STATUSES = {
    "verified",
    "partial",
    "not_instrumented",
    "blocked",
    "not_applicable",
}

ALLOWED_CADENCES = {"daily", "weekly", "monthly", "quarterly"}
FORBIDDEN_PLACEHOLDERS = {"tbd", "todo", "fixme", "unknown", "n/a"}


class ScorecardError(ValueError):
    """Raised when the scorecard violates the accountability contract."""


def _require_nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ScorecardError(f"{field} must be a non-empty string")
    normalized = value.strip()
    if normalized.lower() in FORBIDDEN_PLACEHOLDERS:
        raise ScorecardError(f"{field} contains a placeholder: {normalized!r}")
    return normalized


def _parse_iso_date(value: Any, field: str) -> date:
    text = _require_nonempty_string(value, field)
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ScorecardError(f"{field} must be YYYY-MM-DD") from exc


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_scorecard(
    payload: Any,
    *,
    today: date | None = None,
    max_age_days: int | None = None,
) -> list[str]:
    if not isinstance(payload, dict):
        raise ScorecardError("scorecard root must be an object")

    missing_top = REQUIRED_TOP_LEVEL - set(payload)
    if missing_top:
        raise ScorecardError(f"missing top-level fields: {sorted(missing_top)}")

    if payload["schema_version"] != 1:
        raise ScorecardError("schema_version must equal 1")

    as_of = _parse_iso_date(payload["as_of"], "as_of")
    _require_nonempty_string(payload["owner"], "owner")
    _require_nonempty_string(payload["strategy_source"], "strategy_source")
    north_star = _require_nonempty_string(
        payload["north_star_metric_id"], "north_star_metric_id"
    )

    categories = payload["required_categories"]
    if not isinstance(categories, list) or not categories:
        raise ScorecardError("required_categories must be a non-empty list")
    normalized_categories = {
        _require_nonempty_string(item, "required_categories[]") for item in categories
    }
    missing_categories = REQUIRED_CATEGORIES - normalized_categories
    if missing_categories:
        raise ScorecardError(
            f"required_categories missing: {sorted(missing_categories)}"
        )

    metrics = payload["metrics"]
    if not isinstance(metrics, list) or not metrics:
        raise ScorecardError("metrics must be a non-empty list")

    seen_ids: set[str] = set()
    seen_categories: set[str] = set()
    summaries: list[str] = []

    for index, metric in enumerate(metrics):
        prefix = f"metrics[{index}]"
        if not isinstance(metric, dict):
            raise ScorecardError(f"{prefix} must be an object")
        missing = REQUIRED_METRIC_FIELDS - set(metric)
        if missing:
            raise ScorecardError(f"{prefix} missing fields: {sorted(missing)}")

        metric_id = _require_nonempty_string(metric["id"], f"{prefix}.id")
        if metric_id in seen_ids:
            raise ScorecardError(f"duplicate metric id: {metric_id}")
        seen_ids.add(metric_id)

        _require_nonempty_string(metric["name"], f"{prefix}.name")
        category = _require_nonempty_string(metric["category"], f"{prefix}.category")
        if category not in normalized_categories:
            raise ScorecardError(f"{metric_id}: unknown category {category!r}")
        seen_categories.add(category)

        status = _require_nonempty_string(metric["status"], f"{prefix}.status")
        if status not in ALLOWED_STATUSES:
            raise ScorecardError(f"{metric_id}: unsupported status {status!r}")

        value = metric["value"]
        target = metric["target"]
        if value is not None and not _is_number(value):
            raise ScorecardError(f"{metric_id}: value must be numeric or null")
        if target is not None and not _is_number(target):
            raise ScorecardError(f"{metric_id}: target must be numeric or null")

        _require_nonempty_string(metric["unit"], f"{prefix}.unit")
        _require_nonempty_string(metric["owner"], f"{prefix}.owner")
        cadence = _require_nonempty_string(metric["cadence"], f"{prefix}.cadence")
        if cadence not in ALLOWED_CADENCES:
            raise ScorecardError(f"{metric_id}: unsupported cadence {cadence!r}")
        _require_nonempty_string(metric["source"], f"{prefix}.source")

        evidence = metric["evidence"]
        if not isinstance(evidence, list) or not evidence:
            raise ScorecardError(f"{metric_id}: evidence must be a non-empty list")
        for evidence_index, item in enumerate(evidence):
            _require_nonempty_string(item, f"{prefix}.evidence[{evidence_index}]")

        blocker = metric["blocker"]
        next_action = metric["next_action"]

        if status == "verified":
            if value is None:
                raise ScorecardError(
                    f"{metric_id}: verified metrics require a numeric value"
                )
            verified_at = metric.get("verified_at")
            if verified_at is None:
                raise ScorecardError(
                    f"{metric_id}: verified metrics require verified_at"
                )
            verified_date = _parse_iso_date(verified_at, f"{prefix}.verified_at")
            if verified_date > as_of:
                raise ScorecardError(
                    f"{metric_id}: verified_at cannot be after scorecard as_of"
                )
            if blocker not in ("", None):
                raise ScorecardError(
                    f"{metric_id}: verified metrics must not carry a blocker"
                )
            _require_nonempty_string(next_action, f"{prefix}.next_action")
        elif status in {"partial", "not_instrumented", "blocked"}:
            if status in {"not_instrumented", "blocked"} and value is not None:
                raise ScorecardError(
                    f"{metric_id}: {status} metrics must use null, never a fake zero"
                )
            _require_nonempty_string(blocker, f"{prefix}.blocker")
            _require_nonempty_string(next_action, f"{prefix}.next_action")
        else:
            if value is not None:
                raise ScorecardError(
                    f"{metric_id}: not_applicable metrics must use null"
                )
            if blocker not in ("", None):
                _require_nonempty_string(blocker, f"{prefix}.blocker")
            _require_nonempty_string(next_action, f"{prefix}.next_action")

        summaries.append(f"{metric_id}:{status}")

    missing_metric_categories = REQUIRED_CATEGORIES - seen_categories
    if missing_metric_categories:
        raise ScorecardError(
            "no metric defined for categories: "
            f"{sorted(missing_metric_categories)}"
        )

    if north_star not in seen_ids:
        raise ScorecardError(
            f"north_star_metric_id {north_star!r} does not reference a metric"
        )

    if max_age_days is not None:
        if max_age_days < 0:
            raise ScorecardError("max_age_days cannot be negative")
        current = today or datetime.utcnow().date()
        age = (current - as_of).days
        if age < 0:
            raise ScorecardError("scorecard as_of cannot be in the future")
        if age > max_age_days:
            raise ScorecardError(
                f"scorecard is stale: {age} days old; maximum is {max_age_days}"
            )

    return summaries


def load_scorecard(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ScorecardError(f"scorecard file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ScorecardError(
            f"invalid JSON in {path}: line {exc.lineno}, column {exc.colno}"
        ) from exc


def _expect_failure(payload: dict[str, Any], contains: str) -> None:
    try:
        validate_scorecard(payload, today=date(2026, 7, 29))
    except ScorecardError as exc:
        if contains not in str(exc):
            raise AssertionError(
                f"expected failure containing {contains!r}, got {exc!r}"
            ) from exc
    else:
        raise AssertionError(f"expected validation failure containing {contains!r}")


def run_self_test() -> None:
    valid = {
        "schema_version": 1,
        "as_of": "2026-07-29",
        "owner": "Owner",
        "north_star_metric_id": "ENG-001",
        "strategy_source": "strategy.md",
        "required_categories": sorted(REQUIRED_CATEGORIES),
        "metrics": [],
    }
    for index, category in enumerate(sorted(REQUIRED_CATEGORIES), start=1):
        metric_id = "ENG-001" if category == "engagement" else f"TST-{index:03d}"
        valid["metrics"].append(
            {
                "id": metric_id,
                "name": f"{category} metric",
                "category": category,
                "status": "not_instrumented",
                "value": None,
                "unit": "count",
                "target": None,
                "owner": "Owner",
                "cadence": "weekly",
                "source": "source",
                "evidence": ["evidence"],
                "blocker": "Not wired",
                "next_action": "Wire it",
            }
        )

    validate_scorecard(valid, today=date(2026, 7, 29), max_age_days=0)

    fake_zero = copy.deepcopy(valid)
    fake_zero["metrics"][0]["value"] = 0
    _expect_failure(fake_zero, "must use null, never a fake zero")

    duplicate = copy.deepcopy(valid)
    duplicate["metrics"][1]["id"] = duplicate["metrics"][0]["id"]
    _expect_failure(duplicate, "duplicate metric id")

    no_category = copy.deepcopy(valid)
    no_category["metrics"] = no_category["metrics"][:-1]
    _expect_failure(no_category, "no metric defined for categories")

    false_verified = copy.deepcopy(valid)
    false_verified["metrics"][0]["status"] = "verified"
    false_verified["metrics"][0]["blocker"] = ""
    _expect_failure(false_verified, "require a numeric value")

    stale = copy.deepcopy(valid)
    try:
        validate_scorecard(stale, today=date(2026, 8, 7), max_age_days=8)
    except ScorecardError as exc:
        if "stale" not in str(exc):
            raise
    else:
        raise AssertionError("expected stale scorecard failure")

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "scorecard.json"
        path.write_text(json.dumps(valid), encoding="utf-8")
        validate_scorecard(load_scorecard(path), today=date(2026, 7, 29))

    print("OK: product accountability scorecard self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scorecard",
        type=Path,
        default=DEFAULT_SCORECARD,
        help=f"scorecard JSON path (default: {DEFAULT_SCORECARD})",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=None,
        help="optional freshness gate measured from UTC date",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="exercise positive and negative policy cases",
    )
    args = parser.parse_args()

    try:
        if args.self_test:
            run_self_test()
            return 0

        payload = load_scorecard(args.scorecard)
        summaries = validate_scorecard(
            payload,
            max_age_days=args.max_age_days,
        )
    except ScorecardError as exc:
        print(f"ERROR: {exc}")
        return 1

    status_counts: dict[str, int] = {}
    for item in summaries:
        status = item.split(":", 1)[1]
        status_counts[status] = status_counts.get(status, 0) + 1
    rendered = ", ".join(
        f"{status}={count}" for status, count in sorted(status_counts.items())
    )
    print(
        "OK: product accountability scorecard valid "
        f"({len(summaries)} metrics; {rendered})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
