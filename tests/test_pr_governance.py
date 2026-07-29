"""Regression coverage for Rico's trusted pull-request governance checker."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_pr_governance_self_test() -> None:
    """The exact checker committed to the PR must parse and pass its proofs."""
    result = subprocess.run(
        [sys.executable, "scripts/check_pr_governance.py", "--self-test"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "PR governance self-test: PASS" in result.stdout
