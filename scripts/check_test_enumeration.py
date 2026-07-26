#!/usr/bin/env python3
"""Fail when a test file exists but no workflow ever runs it.

The pytest jobs in this repository do not run ``tests/``. They run enumerated
lists of explicit paths. A list is only as complete as the last person who
remembered to append to it, and a test file nobody remembered is not a failing
test — it is an invisible one. CI goes green, the file looks like coverage in
the tree, and the invariant it was written to protect is unguarded.

That has now happened repeatedly: fail-closed invariants landed in files that
were never added to the list, and each was caught by hand, after merge. This
guard exists so the next one is caught by CI instead.

What it does
------------
Discovers every test file under ``tests/``, extracts the ``tests/...`` paths
from every pytest invocation in every workflow, and fails if a discovered file
is reachable from none of them. A directory token such as ``tests/unit/``
covers everything beneath it, which is how pytest itself treats it.

Deliberate exclusions go in the allowlist, and every entry must carry a
reason. An unexplained exclusion is how this disease comes back: it looks like
a decision and behaves like an oversight, and six months later nobody can say
which it was.

Fail-closed
-----------
Every error path exits non-zero. If the workflow directory is missing, if a
workflow cannot be read, if no pytest invocation can be found where one is
expected, or if the allowlist is malformed, this guard fails. A guard that
passes when it cannot see what it is checking is worse than no guard, because
it produces a green tick that means nothing.

This script never writes to a workflow. It reads them.
"""

from __future__ import annotations

import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TESTS_DIR = REPO_ROOT / "tests"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
ALLOWLIST = REPO_ROOT / ".github" / "test-enumeration-allowlist.txt"

# Workflows expected to contain at least one pytest invocation. If one of these
# stops invoking pytest the guard fails rather than silently measuring less:
# a workflow that quietly stopped running tests is exactly the failure mode
# this script exists to catch.
WORKFLOWS_EXPECTED_TO_RUN_TESTS = (
    "qa-tests.yml",
    "log-privacy-ratchet.yml",
)


class GuardError(Exception):
    """Raised for any condition that must fail the guard rather than pass it."""


def discover_test_files() -> list[str]:
    """Every test file pytest would collect under ``tests/``."""
    if not TESTS_DIR.is_dir():
        raise GuardError(f"tests directory not found at {TESTS_DIR}")
    found = [
        str(p.relative_to(REPO_ROOT)).replace("\\", "/")
        for p in TESTS_DIR.glob("**/*.py")
        if p.name.startswith("test_") or p.name.endswith("_test.py")
    ]
    if not found:
        raise GuardError(
            "no test files discovered under tests/ — refusing to report "
            "'nothing unenumerated' from an empty discovery"
        )
    return sorted(found)


def _pytest_path_tokens(text: str) -> set[str]:
    """``tests/...`` tokens from every pytest invocation in one workflow.

    Only tokens inside a pytest command are taken. A path named in a comment or
    in prose is not something CI runs, and treating it as coverage would let a
    file be 'enumerated' by being mentioned.
    """
    tokens: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # A pytest invocation, or a continuation line beneath one.
        tokens.update(re.findall(r"(?<![\w/.-])(tests/[\w./-]+)", stripped))
    return tokens


def enumerated_paths() -> tuple[set[str], set[str]]:
    """(files, directories) reachable from the workflows' pytest invocations."""
    if not WORKFLOWS_DIR.is_dir():
        raise GuardError(f"workflow directory not found at {WORKFLOWS_DIR}")

    workflows = sorted(
        list(WORKFLOWS_DIR.glob("*.yml")) + list(WORKFLOWS_DIR.glob("*.yaml"))
    )
    if not workflows:
        raise GuardError(f"no workflow files found in {WORKFLOWS_DIR}")

    tokens: set[str] = set()
    seen_pytest_in: set[str] = set()
    for wf in workflows:
        try:
            text = wf.read_text(encoding="utf-8")
        except OSError as exc:
            raise GuardError(f"cannot read workflow {wf.name}: {exc}") from exc
        if "pytest" in text:
            seen_pytest_in.add(wf.name)
        tokens.update(_pytest_path_tokens(text))

    for expected in WORKFLOWS_EXPECTED_TO_RUN_TESTS:
        if expected not in seen_pytest_in:
            raise GuardError(
                f"{expected} was expected to invoke pytest and does not — "
                "either it stopped running tests, or it was renamed and this "
                "guard's expectations are stale. Both must be looked at."
            )
    if not tokens:
        raise GuardError(
            "no tests/ paths found in any pytest invocation — refusing to "
            "report every file as unenumerated from a failed parse"
        )

    files = {t for t in tokens if t.endswith(".py")}
    dirs = {t.rstrip("/") + "/" for t in tokens if not t.endswith(".py")}
    return files, dirs


def read_allowlist() -> dict[str, str]:
    """``{path: reason}`` for deliberately excluded files.

    Format is one entry per line, ``path  # reason``. A blank reason fails:
    the reason is the whole point of the entry.
    """
    if not ALLOWLIST.exists():
        return {}
    try:
        raw = ALLOWLIST.read_text(encoding="utf-8")
    except OSError as exc:
        raise GuardError(f"cannot read allowlist {ALLOWLIST}: {exc}") from exc

    entries: dict[str, str] = {}
    unexplained: list[str] = []
    for number, line in enumerate(raw.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        path, _, reason = stripped.partition("#")
        path, reason = path.strip(), reason.strip()
        if not path:
            raise GuardError(f"{ALLOWLIST.name} line {number}: no path")
        if not reason:
            unexplained.append(f"{ALLOWLIST.name} line {number}: {path}")
            continue
        entries[path] = reason
    if unexplained:
        raise GuardError(
            "allowlist entries without a reason — an unexplained exclusion is "
            "indistinguishable from an oversight:\n  "
            + "\n  ".join(unexplained)
        )
    return entries


def unenumerated(
    discovered: list[str], files: set[str], dirs: set[str]
) -> list[str]:
    def covered(rel: str) -> bool:
        return rel in files or any(rel.startswith(d) for d in dirs)

    return [rel for rel in discovered if not covered(rel)]


def main() -> int:
    try:
        discovered = discover_test_files()
        files, dirs = enumerated_paths()
        allowed = read_allowlist()
        missing = unenumerated(discovered, files, dirs)
    except GuardError as exc:
        print(f"FAIL: test-enumeration guard could not complete: {exc}")
        print("\nThe guard fails closed. It does not pass when it cannot see "
              "what it is checking.")
        return 1

    stale = sorted(set(allowed) - set(missing))
    unexplained_gap = [rel for rel in missing if rel not in allowed]

    print(f"discovered test files under tests/ : {len(discovered)}")
    print(f"enumerated file paths in workflows : {len(files)}")
    print(f"enumerated directory paths         : {len(dirs)}")
    print(f"reachable by no pytest invocation  : {len(missing)}")
    print(f"of those, allowlisted with reason  : {len(missing) - len(unexplained_gap)}")

    if stale:
        print(
            f"\nFAIL: {len(stale)} allowlist entr"
            f"{'y is' if len(stale) == 1 else 'ies are'} no longer needed — "
            "the file is enumerated now, so the exclusion is stale and must be "
            "removed:"
        )
        for rel in stale:
            print(f"  {rel}")

    if unexplained_gap:
        print(
            f"\nFAIL: {len(unexplained_gap)} test file"
            f"{'' if len(unexplained_gap) == 1 else 's'} exist but no pytest "
            "invocation in any workflow runs them. A test nobody runs is not "
            "coverage:"
        )
        for rel in unexplained_gap:
            print(f"  {rel}")
        print(
            "\nAdd the path to the pytest invocation that should run it, or "
            f"add it to {ALLOWLIST.name} with a one-line reason."
        )

    if stale or unexplained_gap:
        return 1
    print("\nOK: every test file under tests/ is reachable from a pytest "
          "invocation, or allowlisted with a stated reason.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
