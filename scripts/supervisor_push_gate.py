"""Deterministic push gate for rico-development-supervisor sessions.

The ONLY sanctioned way for a supervised session to push its branch. Entry
point: scripts/rico-supervisor-push.sh (thin exec wrapper). Immediately before
pushing it re-fetches origin/main and mechanically enforces the revalidation
the skill contract describes — so a session cannot skip the prose step and
push anyway:

  1. branch must be claude/* and the tree clean;
  2. gh must be available (fail closed — PR overlap cannot be checked blind);
  3. origin/main is re-fetched; if main advanced past the merge-base with
     changes touching any file this branch changed -> REFUSE;
  4. every open PR's changed-file list is checked for overlap -> REFUSE;
  5. Task-ID uniqueness across current AI_WORKSPACE/TASKS.md (frozen
     historical exception pinned to its exact headings) and against Task IDs
     added by open PR patches -> REFUSE;
  6. only then: git push -u origin <current branch>.

Exit codes: 0 pushed (or --check-only passed); 2 refused (conflict/overlap/
duplicate — nothing pushed); 6 precondition failed (nothing pushed).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

TASK_HEADING_RE = re.compile(r"^### (TASK-\d{8}-\d{3})\b(.*)$", re.MULTILINE)

# TASK-20260721-005 was duplicated on main before the uniqueness guard
# existed. The exception is pinned to the EXACT existing headings: replacing
# one of them with a different duplicate still fails.
FROZEN_DUPLICATE_HEADINGS = {
    "TASK-20260721-005": {
        "### TASK-20260721-005 — Command v5 PR 3: live modes (Overview / Applications / Documents)",
        "### TASK-20260721-005 — Bilingual (AR/EN) agent replies — response builder localization",
    }
}

EXIT_OK = 0
EXIT_REFUSED = 2
EXIT_PRECONDITION = 6


def run(*cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def overlap(a: list[str], b: list[str]) -> list[str]:
    return sorted(set(a) & set(b))


def task_headings(text: str) -> dict[str, set[str]]:
    """Map task id -> set of full heading lines found for it."""
    found: dict[str, set[str]] = defaultdict(set)
    for match in TASK_HEADING_RE.finditer(text):
        found[match.group(1)].add(f"### {match.group(1)}{match.group(2)}".rstrip())
    return found


def duplicate_task_ids(text: str) -> dict[str, set[str]]:
    """Duplicated ids that are NOT covered by the frozen exact-heading set."""
    offenders: dict[str, set[str]] = {}
    all_headings = task_headings(text)
    counts: dict[str, int] = {}
    for match in TASK_HEADING_RE.finditer(text):
        counts[match.group(1)] = counts.get(match.group(1), 0) + 1
    for task_id, n in counts.items():
        if n <= 1:
            continue
        frozen = FROZEN_DUPLICATE_HEADINGS.get(task_id)
        if frozen is not None and all_headings[task_id] == frozen and n == len(frozen):
            continue
        offenders[task_id] = all_headings[task_id]
    return offenders


def added_task_ids(diff_text: str) -> set[str]:
    """Task ids introduced by '+### TASK-...' lines of a unified diff."""
    ids = set()
    for line in diff_text.splitlines():
        if line.startswith("+### TASK-"):
            match = re.match(r"\+### (TASK-\d{8}-\d{3})\b", line)
            if match:
                ids.add(match.group(1))
    return ids


def refuse(reason: str) -> int:
    print(f"push-gate: REFUSED — {reason}", file=sys.stderr)
    print("push-gate: nothing was pushed.", file=sys.stderr)
    return EXIT_REFUSED


def precondition(reason: str) -> int:
    print(f"push-gate: precondition failed — {reason}", file=sys.stderr)
    return EXIT_PRECONDITION


def main(argv: list[str]) -> int:
    check_only = "--check-only" in argv

    branch = run("git", "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if not branch.startswith("claude/"):
        return precondition(f"only claude/* branches may be pushed (on '{branch}')")

    if run("git", "status", "--porcelain").stdout.strip():
        return precondition("working tree is dirty; commit or discard first")

    if shutil.which("gh") is None:
        return precondition("gh CLI required for open-PR overlap check (fail closed)")

    fetch = run("git", "fetch", "origin", "main")
    if fetch.returncode != 0:
        return precondition(f"git fetch origin main failed: {fetch.stderr.strip()}")

    base = run("git", "merge-base", "HEAD", "origin/main").stdout.strip()
    origin_main = run("git", "rev-parse", "origin/main").stdout.strip()
    branch_files = [
        f for f in run("git", "diff", "--name-only", base, "HEAD").stdout.splitlines() if f
    ]
    if not branch_files:
        return precondition("branch has no changes against merge-base")

    if origin_main != base:
        main_files = [
            f
            for f in run("git", "diff", "--name-only", base, origin_main).stdout.splitlines()
            if f
        ]
        conflict = overlap(branch_files, main_files)
        if conflict:
            return refuse(
                "origin/main advanced past the recorded base with changes touching "
                f"this branch's files: {conflict}. Rebuild/rebase onto origin/main first "
                "(BLOCKED_CONFLICT)."
            )

    pr_list = run(
        "gh", "pr", "list", "--state", "open",
        "--json", "number,headRefName,files", "--limit", "100",
    )
    if pr_list.returncode != 0:
        return precondition(f"gh pr list failed: {pr_list.stderr.strip()}")
    try:
        prs = json.loads(pr_list.stdout or "[]")
    except json.JSONDecodeError as exc:
        return precondition(f"gh pr list returned unparseable JSON: {exc}")

    prs_touching_tasks: list[int] = []
    for pr in prs:
        if pr.get("headRefName") == branch:
            continue
        pr_files = [f.get("path", "") for f in pr.get("files", [])]
        conflict = overlap(branch_files, pr_files)
        if conflict:
            return refuse(
                f"open PR #{pr.get('number')} ({pr.get('headRefName')}) changes "
                f"overlapping files: {conflict} (BLOCKED_CONFLICT)."
            )
        if "AI_WORKSPACE/TASKS.md" in pr_files:
            prs_touching_tasks.append(pr["number"])

    tasks_path = Path("AI_WORKSPACE/TASKS.md")
    if tasks_path.exists():
        offenders = duplicate_task_ids(tasks_path.read_text(encoding="utf-8"))
        if offenders:
            return refuse(f"duplicate Task IDs in AI_WORKSPACE/TASKS.md: {sorted(offenders)}")

    our_added = added_task_ids(
        run("git", "diff", base, "HEAD", "--", "AI_WORKSPACE/TASKS.md").stdout
    )
    for number in prs_touching_tasks:
        pr_diff = run("gh", "pr", "diff", str(number))
        if pr_diff.returncode != 0:
            return precondition(f"gh pr diff {number} failed (fail closed)")
        collision = our_added & added_task_ids(pr_diff.stdout)
        if collision:
            return refuse(
                f"open PR #{number} also introduces Task ID(s) {sorted(collision)} "
                "(BLOCKED_CONFLICT)."
            )

    print(f"push-gate: all checks passed for {branch} (base {base[:8]}).")
    if check_only:
        return EXIT_OK

    push = subprocess.run(["git", "push", "-u", "origin", branch])
    if push.returncode != 0:
        return precondition(f"git push exited {push.returncode}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
