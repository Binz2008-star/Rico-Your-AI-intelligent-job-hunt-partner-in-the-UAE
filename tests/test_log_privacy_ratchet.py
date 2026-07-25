"""The differential log-privacy ratchet.

Every case here runs against REAL git repositories with REAL commits: the
fixture initialises a repository, commits a baseline that already carries
pre-existing debt, branches, commits a change, resolves the merge base with
``git merge-base`` and materialises the base tree with ``git worktree`` —
exactly the sequence CI performs. Nothing is asserted against synthetic
strings, because the failure this gate must not have is a base tree that is
silently wrong, and only real commits exercise that path.

The two directions that matter are both covered: the gate goes red when a
violation is introduced, and it stays green on a branch that introduces none.
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from log_privacy_ratchet import (  # noqa: E402
    RatchetError,
    main as ratchet_main,
    run as ratchet_run,
)

# A pre-existing site, so the baseline carries debt exactly as the real
# repository does. The gate must never object to it.
_BASELINE_DEBT = '''\
import logging

logger = logging.getLogger(__name__)


def existing_path(user_id):
    logger.warning("legacy_event user=%s", user_id)
'''

_CLEAN_MODULE = '''\
import logging

from src.log_privacy import user_ref

logger = logging.getLogger(__name__)


def compliant_path(user_id):
    logger.info("compliant_event user=%s", user_ref(user_id))
'''

_NEW_VIOLATION = '''\
import logging

logger = logging.getLogger(__name__)


def added_path(email):
    logger.info("added_event user=%s", email)
'''


def _git(repo: pathlib.Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, check=True,
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def _commit(repo: pathlib.Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """A real repository whose first commit already carries log-privacy debt."""
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    _git(root.parent, "init", "-q", "-b", "main", str(root))

    # The rules travel with the head tree, exactly as in CI.
    shutil.copy(_REPO_ROOT / "tests" / "test_1076_log_privacy.py", root / "tests")
    shutil.copy(_REPO_ROOT / "src" / "log_privacy.py", root / "src")

    (root / "src" / "legacy.py").write_text(_BASELINE_DEBT, encoding="utf-8")
    _commit(root, "baseline with pre-existing debt")
    return root


def _base_tree(repo: pathlib.Path, tmp_path: pathlib.Path) -> tuple[pathlib.Path, str, str]:
    """Resolve the merge base and materialise it, as the workflow does."""
    head_sha = _git(repo, "rev-parse", "HEAD")
    base_sha = _git(repo, "merge-base", "main", "HEAD")
    worktree = tmp_path / f"base-{base_sha[:8]}"
    _git(repo, "worktree", "add", "--detach", "-q", str(worktree), base_sha)
    return worktree, base_sha, head_sha


def _ratchet(repo: pathlib.Path, tmp_path: pathlib.Path) -> int:
    base_tree, base_sha, head_sha = _base_tree(repo, tmp_path)
    return ratchet_run(base_tree, repo, base_sha, head_sha)


class TestRatchetGoesRedOnNewDebt:
    def test_a_new_violation_in_a_new_file_is_rejected(self, repo, tmp_path):
        _git(repo, "checkout", "-q", "-b", "feature")
        (repo / "src" / "added.py").write_text(_NEW_VIOLATION, encoding="utf-8")
        _commit(repo, "add a module with a raw identifier log")
        assert _ratchet(repo, tmp_path) == 1

    def test_a_new_violation_in_an_existing_file_is_rejected(self, repo, tmp_path):
        _git(repo, "checkout", "-q", "-b", "feature")
        existing = repo / "src" / "legacy.py"
        existing.write_text(
            existing.read_text(encoding="utf-8")
            + '\n\ndef second_path(email):\n    logger.info("later_event user=%s", email)\n',
            encoding="utf-8",
        )
        _commit(repo, "append a raw identifier log to an existing module")
        assert _ratchet(repo, tmp_path) == 1

    def test_a_swap_that_keeps_the_total_constant_is_rejected(self, repo, tmp_path):
        """The case a numeric ceiling cannot catch: one fixed, one introduced."""
        _git(repo, "checkout", "-q", "-b", "feature")
        (repo / "src" / "legacy.py").write_text(_CLEAN_MODULE, encoding="utf-8")
        (repo / "src" / "added.py").write_text(_NEW_VIOLATION, encoding="utf-8")
        _commit(repo, "fix one site and introduce another")
        assert _ratchet(repo, tmp_path) == 1

    def test_a_second_identical_site_in_the_same_function_is_rejected(self, repo, tmp_path):
        """Multiset, not set: the second copy must not hide behind the first."""
        _git(repo, "checkout", "-q", "-b", "feature")
        existing = repo / "src" / "legacy.py"
        existing.write_text(
            existing.read_text(encoding="utf-8")
            + '    logger.warning("legacy_event user=%s", user_id)\n',
            encoding="utf-8",
        )
        _commit(repo, "duplicate the existing site inside the same function")
        assert _ratchet(repo, tmp_path) == 1


class TestRatchetStaysGreenWithoutNewDebt:
    def test_a_branch_that_changes_nothing_relevant_is_accepted(self, repo, tmp_path):
        _git(repo, "checkout", "-q", "-b", "feature")
        (repo / "README.md").write_text("docs only\n", encoding="utf-8")
        _commit(repo, "documentation only")
        assert _ratchet(repo, tmp_path) == 0

    def test_adding_a_compliant_module_is_accepted(self, repo, tmp_path):
        _git(repo, "checkout", "-q", "-b", "feature")
        (repo / "src" / "added.py").write_text(_CLEAN_MODULE, encoding="utf-8")
        _commit(repo, "add a module that uses the helper")
        assert _ratchet(repo, tmp_path) == 0

    def test_pre_existing_debt_alone_never_fails_the_gate(self, repo, tmp_path):
        """The baseline is full of debt; an unrelated commit must still pass."""
        _git(repo, "checkout", "-q", "-b", "feature")
        (repo / "src" / "unrelated.py").write_text(
            "VALUE = 1\n", encoding="utf-8"
        )
        _commit(repo, "unrelated constant")
        assert _ratchet(repo, tmp_path) == 0

    def test_removing_debt_is_accepted(self, repo, tmp_path):
        _git(repo, "checkout", "-q", "-b", "feature")
        (repo / "src" / "legacy.py").write_text(_CLEAN_MODULE, encoding="utf-8")
        _commit(repo, "remediate the pre-existing site")
        assert _ratchet(repo, tmp_path) == 0

    def test_moving_a_site_down_the_file_is_not_a_new_violation(self, repo, tmp_path):
        """Descriptors carry no line number, so inserting lines above a
        pre-existing site must not register as newly introduced."""
        _git(repo, "checkout", "-q", "-b", "feature")
        existing = repo / "src" / "legacy.py"
        text = existing.read_text(encoding="utf-8")
        existing.write_text("# padding\n" * 20 + text, encoding="utf-8")
        _commit(repo, "shift the existing site down the file")
        assert _ratchet(repo, tmp_path) == 0


class TestRatchetPublishesNothingAboutExistingDebt:
    """CI logs on a public repository are public.

    The gate may name violations this change introduces — they are already in
    the diff — but it must never emit a repository-wide count, which is the
    posture measurement the differential design exists to avoid publishing.
    """

    def test_clean_run_emits_no_baseline_figures(self, repo, tmp_path, capsys):
        _git(repo, "checkout", "-q", "-b", "feature")
        (repo / "src" / "added.py").write_text(_CLEAN_MODULE, encoding="utf-8")
        _commit(repo, "add a compliant module")
        assert _ratchet(repo, tmp_path) == 0
        out = capsys.readouterr().out
        assert "base=" not in out and "head=" not in out
        assert not any(ch.isdigit() for ch in out), out

    def test_failing_run_names_only_the_new_site(self, repo, tmp_path, capsys):
        _git(repo, "checkout", "-q", "-b", "feature")
        (repo / "src" / "added.py").write_text(_NEW_VIOLATION, encoding="utf-8")
        _commit(repo, "introduce a violation")
        assert _ratchet(repo, tmp_path) == 1
        out = capsys.readouterr().out
        assert "src/added.py" in out          # the new site is actionable
        assert "src/legacy.py" not in out     # pre-existing debt stays private


class TestRatchetFailsLoudlyRatherThanSilently:
    def test_base_identical_to_head_is_refused(self, repo, tmp_path):
        """The dangerous failure: an empty difference passes everything."""
        head = _git(repo, "rev-parse", "HEAD")
        with pytest.raises(RatchetError, match="same commit"):
            ratchet_run(repo, repo, head, head)

    def test_a_base_tree_without_src_is_refused(self, repo, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(RatchetError, match="no src/"):
            ratchet_run(empty, repo, "a" * 40, "b" * 40)

    def test_a_missing_base_tree_is_refused(self, repo, tmp_path):
        with pytest.raises(RatchetError, match="not a directory"):
            ratchet_run(tmp_path / "nope", repo, "a" * 40, "b" * 40)

    def test_a_head_tree_without_the_rule_module_is_refused(self, repo, tmp_path):
        # Commit the removal so base and head are genuinely distinct — the
        # base==head guard fires first otherwise, which is itself correct.
        _git(repo, "checkout", "-q", "-b", "feature")
        (repo / "tests" / "test_1076_log_privacy.py").unlink()
        _commit(repo, "remove the rule module")
        base_tree, base_sha, head_sha = _base_tree(repo, tmp_path)
        with pytest.raises(RatchetError, match="rule module not found"):
            ratchet_run(base_tree, repo, base_sha, head_sha)

    def test_cli_reports_two_for_an_unusable_baseline(self, repo, tmp_path):
        """Exit 2 is distinct from exit 1: cannot run, versus ran and failed."""
        code = ratchet_main([
            "--base-tree", str(tmp_path / "nope"),
            "--head-tree", str(repo),
            "--base-sha", "a" * 40,
            "--head-sha", "b" * 40,
        ])
        assert code == 2
