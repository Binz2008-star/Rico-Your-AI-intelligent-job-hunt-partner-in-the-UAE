#!/usr/bin/env python3
"""Fail-closed pull-request governance check for Rico.

The trusted workflow runs this copy from the base branch via
``pull_request_target``. A pull request therefore cannot weaken the policy that
judges it. Draft PRs may remain incomplete; a PR marked ready must carry the
full governance record for its exact current head.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REQUIRED_SECTIONS = (
    "Objective",
    "Roadmap traceability",
    "Scope",
    "Acceptance criteria",
    "Changed files",
    "Risk",
    "Verification",
    "Review evidence",
    "Production and data impact",
    "Rollback plan",
)

PLACEHOLDERS = {"", "tbd", "todo", "n/a?", "pending", "fill me"}
ALLOWED_VERDICTS = {"PASS", "PASS WITH OWNER-ACCEPTED RISK"}
UNCHECKED_TASK_RE = re.compile(r"(?im)^\s*[-*]\s*\[\s\]\s*")
CHANGED_FILE_RE = re.compile(
    r"(?m)^\s*[-*]\s+`(?!path`)([^`]+)`\s+(?:—|-)\s+\S+"
)
DEFAULT_CHANGED_FILE_RE = re.compile(
    r"(?im)^\s*[-*]\s+`path`\s+(?:—|-)\s+reason\s*$"
)


def _sections(body: str) -> dict[str, str]:
    """Return second-level Markdown sections keyed by normalized heading."""
    found: dict[str, list[str]] = {}
    current: str | None = None
    for raw_line in body.splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", raw_line)
        if match:
            current = match.group(1).strip()
            found.setdefault(current, [])
            continue
        if current is not None:
            found[current].append(raw_line)
    return {name: "\n".join(lines).strip() for name, lines in found.items()}


def _field(section: str, label: str) -> str | None:
    match = re.search(
        rf"(?im)^\s*(?:[-*]\s*)?{re.escape(label)}\s*:\s*(.+?)\s*$",
        section,
    )
    return match.group(1).strip() if match else None


def _missing_or_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    cleaned = value.strip().strip("`*_- ").strip().lower()
    return (
        cleaned in PLACEHOLDERS
        or cleaned.startswith("<")
        or bool(re.fullmatch(r"\[\s*\]", cleaned))
    )


def validate(
    body: str,
    *,
    draft: bool,
    head_sha: str,
    author: str,
) -> list[str]:
    """Return policy violations. An empty list means the PR passes."""
    if draft:
        return []

    errors: list[str] = []
    sections = _sections(body)

    for name in REQUIRED_SECTIONS:
        content = sections.get(name)
        if content is None:
            errors.append(f"missing required section: ## {name}")
        elif _missing_or_placeholder(content):
            errors.append(f"required section is empty or placeholder: ## {name}")

    if UNCHECKED_TASK_RE.search(body):
        errors.append("ready PR contains unchecked task-list items")

    trace = sections.get("Roadmap traceability", "")
    for label in ("Vision", "Epic", "Milestone", "Phase", "Task"):
        if _missing_or_placeholder(_field(trace, label)):
            errors.append(f"Roadmap traceability must define {label}")

    scope = sections.get("Scope", "")
    for label in ("In scope", "Out of scope"):
        if _missing_or_placeholder(_field(scope, label)):
            errors.append(f"Scope must define {label}")
    one_objective = (_field(scope, "One objective only") or "").strip().casefold()
    if one_objective not in {"[x]", "yes", "true"}:
        errors.append("Scope must confirm One objective only with [x], yes, or true")

    changed_files = sections.get("Changed files", "")
    if DEFAULT_CHANGED_FILE_RE.search(changed_files):
        errors.append("Changed files still contains the default `path` placeholder")
    if changed_files and not CHANGED_FILE_RE.search(changed_files):
        errors.append("Changed files must name at least one concrete `path` and reason")

    risk = sections.get("Risk", "")
    if _missing_or_placeholder(_field(risk, "Risk level")):
        errors.append("Risk must define Risk level")

    impact = sections.get("Production and data impact", "")
    for label in ("Production impact", "Data/migration impact"):
        if _missing_or_placeholder(_field(impact, label)):
            errors.append(f"Production and data impact must define {label}")

    review = sections.get("Review evidence", "")
    reviewer = _field(review, "Reviewer")
    reviewed_sha = _field(review, "Reviewed head SHA")
    verdict = _field(review, "Verdict")

    if _missing_or_placeholder(reviewer):
        errors.append("Review evidence must name an independent Reviewer")
    elif reviewer and author and reviewer.casefold() == author.casefold():
        errors.append("PR author cannot be recorded as the independent Reviewer")

    if not reviewed_sha or not re.fullmatch(r"[0-9a-fA-F]{40}", reviewed_sha):
        errors.append("Reviewed head SHA must be a full 40-character commit SHA")
    elif head_sha and reviewed_sha.casefold() != head_sha.casefold():
        errors.append(
            "independent review is stale: Reviewed head SHA does not match the current PR head"
        )

    if not verdict or verdict.upper() not in ALLOWED_VERDICTS:
        errors.append(
            "Verdict must be PASS or PASS WITH OWNER-ACCEPTED RISK for a ready PR"
        )

    return errors


def _valid_body(head_sha: str) -> str:
    return f"""## Objective
Ship one controlled governance change.

## Roadmap traceability
- Vision: AI Career Operating System
- Epic: Operational Excellence
- Milestone: Version Control Maturity
- Phase: Governance
- Task: Exact-head PR gate

## Scope
- In scope: governance files only
- Out of scope: runtime and production settings
- One objective only: [x]

## Acceptance criteria
- [x] Ready PRs carry exact-head review evidence.

## Changed files
- `scripts/check_pr_governance.py` — enforce the ready-state policy

## Risk
- Risk level: Low
- Mitigation: fail closed

## Verification
- Focused tests: self-test passes

## Review evidence
- Reviewer: Independent Reviewer
- Reviewed head SHA: {head_sha}
- Verdict: PASS

## Production and data impact
- Production impact: None
- Data/migration impact: None

## Rollback plan
Revert the governance commit.
"""


def self_test() -> None:
    sha = "a" * 40
    valid = _valid_body(sha)
    assert validate(valid, draft=False, head_sha=sha, author="author") == []
    assert validate("", draft=True, head_sha=sha, author="author") == []
    assert any(
        "missing required section" in item
        for item in validate("## Objective\nOnly", draft=False, head_sha=sha, author="author")
    )
    assert any(
        "stale" in item
        for item in validate(valid, draft=False, head_sha="b" * 40, author="author")
    )
    self_review = valid.replace("Independent Reviewer", "author")
    assert any(
        "cannot be recorded" in item
        for item in validate(self_review, draft=False, head_sha=sha, author="author")
    )
    unchecked = valid.replace(
        "- [x] Ready PRs carry exact-head review evidence.",
        "- [ ] Ready PRs carry exact-head review evidence.",
    )
    assert any(
        "unchecked task-list" in item
        for item in validate(unchecked, draft=False, head_sha=sha, author="author")
    )
    placeholder_path = valid.replace(
        "- `scripts/check_pr_governance.py` — enforce the ready-state policy",
        "- `path` — reason",
    )
    assert any(
        "default `path` placeholder" in item
        for item in validate(placeholder_path, draft=False, head_sha=sha, author="author")
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--body-file", type=Path)
    parser.add_argument("--draft", choices=("true", "false"), default="false")
    parser.add_argument("--head-sha", default="")
    parser.add_argument("--author", default="")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        print("PR governance self-test: PASS")
        return 0

    if args.body_file is None:
        parser.error("--body-file is required unless --self-test is used")

    body = args.body_file.read_text(encoding="utf-8")
    errors = validate(
        body,
        draft=args.draft == "true",
        head_sha=args.head_sha,
        author=args.author,
    )
    if errors:
        print("PR governance: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("PR governance: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
