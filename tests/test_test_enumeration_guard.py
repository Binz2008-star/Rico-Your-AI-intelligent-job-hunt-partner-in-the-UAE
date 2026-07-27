"""The enumeration guard's own proofs.

The guard exists because an enumerated list silently omits things. A guard with
the same weakness would be worse than none, so each rule here is proved by
constructing the condition and asserting the guard fails on it — a rule whose
removal changes nothing is not a rule.

The fail-closed cases matter most. A guard that passes when it cannot parse its
inputs produces a green tick that means nothing, which is the exact failure it
was written to prevent.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import check_test_enumeration as guard  # noqa: E402

WORKFLOW = """\
name: qa
on: [pull_request]
jobs:
  pytest:
    runs-on: ubuntu-latest
    steps:
      - run: |
          pytest \\
            tests/unit/ \\
            tests/test_enumerated.py \\
            -v
"""

RATCHET_WORKFLOW = """\
name: ratchet
on: [pull_request]
jobs:
  ratchet:
    runs-on: ubuntu-latest
    steps:
      - run: python -m pytest tests/test_ratchet.py -q
"""


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A miniature repository the guard can be pointed at."""
    (tmp_path / "tests").mkdir()
    (tmp_path / ".github" / "workflows").mkdir(parents=True)

    def write_tests(*names):
        for name in names:
            (tmp_path / "tests" / name).write_text("def test_x(): pass\n")

    def write_workflow(name, text):
        (tmp_path / ".github" / "workflows" / name).write_text(text)

    def allowlist(text):
        (tmp_path / ".github" / "test-enumeration-allowlist.txt").write_text(text)

    monkeypatch.setattr(guard, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(guard, "TESTS_DIR", tmp_path / "tests")
    monkeypatch.setattr(guard, "WORKFLOWS_DIR", tmp_path / ".github" / "workflows")
    monkeypatch.setattr(
        guard, "ALLOWLIST", tmp_path / ".github" / "test-enumeration-allowlist.txt"
    )
    # The miniature repo has none of the real repository's baseline paths, so
    # the frozen set starts empty here. Cases that need a baseline install
    # their own via the `frozen` fixture.
    monkeypatch.setattr(guard, "FROZEN_BASELINE", frozenset())
    monkeypatch.setattr(guard, "BASELINE_HIGH_WATER", 0)

    write_workflow("qa-tests.yml", WORKFLOW)
    write_workflow("log-privacy-ratchet.yml", RATCHET_WORKFLOW)
    write_tests("test_enumerated.py", "test_ratchet.py")

    ns = type("Repo", (), {})()
    ns.path = tmp_path
    ns.write_tests = write_tests
    ns.write_workflow = write_workflow
    ns.allowlist = allowlist
    return ns


class TestTheGuardCatchesAnUnenumeratedFile:
    def test_the_clean_baseline_passes(self, repo, capsys):
        """Guards every case below: they must fail for their own reason."""
        assert guard.main() == 0
        assert "OK:" in capsys.readouterr().out

    def test_an_unenumerated_file_fails(self, repo, capsys):
        """THE acceptance case: a file nobody runs must not ship silently."""
        repo.write_tests("test_forgotten.py")
        assert guard.main() == 1
        out = capsys.readouterr().out
        assert "tests/test_forgotten.py" in out
        assert "no pytest invocation in any workflow runs them" in out

    def test_a_directory_token_covers_files_beneath_it(self, repo):
        """``tests/unit/`` is how pytest itself reaches a whole tree."""
        (repo.path / "tests" / "unit").mkdir()
        (repo.path / "tests" / "unit" / "test_deep.py").write_text("def test(): pass\n")
        assert guard.main() == 0

    def test_a_second_workflow_can_supply_the_coverage(self, repo):
        """Coverage is the union across workflows, not one file's list."""
        repo.write_tests("test_only_in_ratchet.py")
        repo.write_workflow(
            "log-privacy-ratchet.yml",
            RATCHET_WORKFLOW.replace(
                "tests/test_ratchet.py",
                "tests/test_ratchet.py tests/test_only_in_ratchet.py",
            ),
        )
        assert guard.main() == 0

    def test_a_path_named_only_in_a_comment_is_not_coverage(self, repo, capsys):
        """Mentioning a file is not running it."""
        repo.write_tests("test_mentioned.py")
        repo.write_workflow(
            "qa-tests.yml",
            WORKFLOW.replace(
                "      - run: |",
                "      # tests/test_mentioned.py is important\n      - run: |",
            ),
        )
        assert guard.main() == 1
        assert "tests/test_mentioned.py" in capsys.readouterr().out


class TestTheAllowlistMustExplainItself:
    def test_an_allowlisted_file_passes(self, repo):
        repo.write_tests("test_excluded.py")
        repo.allowlist("tests/test_excluded.py  # needs a live database\n")
        assert guard.main() == 0

    def test_an_allowlist_entry_without_a_reason_fails(self, repo, capsys):
        """An unexplained exclusion is how the disease comes back."""
        repo.write_tests("test_excluded.py")
        repo.allowlist("tests/test_excluded.py\n")
        assert guard.main() == 1
        assert "without a reason" in capsys.readouterr().out

    def test_an_entry_with_an_empty_comment_fails(self, repo, capsys):
        repo.write_tests("test_excluded.py")
        repo.allowlist("tests/test_excluded.py  #   \n")
        assert guard.main() == 1
        assert "without a reason" in capsys.readouterr().out

    def test_comments_and_blank_lines_are_not_entries(self, repo):
        repo.allowlist("# a header\n\n#\n")
        assert guard.main() == 0

    def test_a_stale_allowlist_entry_fails(self, repo, capsys):
        """Once a file is enumerated, its exclusion is a false record."""
        repo.allowlist("tests/test_enumerated.py  # was excluded once\n")
        assert guard.main() == 1
        out = capsys.readouterr().out
        assert "no longer needed" in out
        assert "tests/test_enumerated.py" in out


class TestTheGuardFailsClosed:
    """Every error path must exit non-zero. None may pass."""

    def test_a_missing_workflow_directory_fails(self, repo, capsys):
        for f in (repo.path / ".github" / "workflows").iterdir():
            f.unlink()
        (repo.path / ".github" / "workflows").rmdir()
        assert guard.main() == 1
        assert "fails closed" in capsys.readouterr().out

    def test_a_workflow_directory_with_no_workflows_fails(self, repo, capsys):
        for f in (repo.path / ".github" / "workflows").iterdir():
            f.unlink()
        assert guard.main() == 1
        assert "fails closed" in capsys.readouterr().out

    def test_a_missing_tests_directory_fails(self, repo, capsys):
        for f in (repo.path / "tests").iterdir():
            f.unlink()
        (repo.path / "tests").rmdir()
        assert guard.main() == 1
        assert "fails closed" in capsys.readouterr().out

    def test_no_discovered_tests_fails_rather_than_reporting_all_clear(
        self, repo, capsys
    ):
        """An empty discovery must not be reported as nothing unenumerated."""
        for f in (repo.path / "tests").iterdir():
            f.unlink()
        assert guard.main() == 1
        assert "fails closed" in capsys.readouterr().out

    def test_a_workflow_that_stopped_running_pytest_fails(self, repo, capsys):
        """A gate that quietly stopped running tests is the same disease."""
        repo.write_workflow("qa-tests.yml", "name: qa\non: [pull_request]\njobs: {}\n")
        assert guard.main() == 1
        out = capsys.readouterr().out
        assert "expected to invoke pytest" in out
        assert "fails closed" in out

    def test_a_pytest_invocation_with_no_test_paths_fails(self, repo, capsys):
        """Refuse to call every file unenumerated on the back of a failed parse."""
        repo.write_workflow(
            "qa-tests.yml",
            "name: qa\non: [pull_request]\njobs:\n  t:\n    steps:\n"
            "      - run: pytest --version\n",
        )
        repo.write_workflow(
            "log-privacy-ratchet.yml",
            "name: r\non: [pull_request]\njobs:\n  t:\n    steps:\n"
            "      - run: pytest --version\n",
        )
        assert guard.main() == 1
        out = capsys.readouterr().out
        assert "no tests/ paths found" in out
        assert "fails closed" in out


class TestTheGuardIsItselfEnumerated:
    """The most embarrassing possible outcome is a guard nobody runs."""

    def test_this_test_file_is_reachable_from_a_real_workflow(self):
        """Run against the real repository, not a fixture.

        If this file is ever dropped from every pytest invocation, this
        assertion fails — the guard's own coverage is held by the same rule it
        applies to everything else.
        """
        discovered = guard.discover_test_files()
        me = "tests/test_test_enumeration_guard.py"
        assert me in discovered, f"{me} not discovered under tests/"

        files, dirs = guard.enumerated_paths()
        covered = me in files or any(me.startswith(d) for d in dirs)
        assert covered, (
            f"{me} is not reachable from any pytest invocation — the "
            "enumeration guard would not run in CI"
        )

    def test_the_guard_script_is_referenced_by_a_workflow(self):
        """The script must actually be invoked somewhere, not merely exist."""
        workflows = sorted(guard.WORKFLOWS_DIR.glob("*.yml"))
        assert any(
            "check_test_enumeration.py" in wf.read_text(encoding="utf-8")
            for wf in workflows
        ), "no workflow invokes scripts/check_test_enumeration.py"

    def test_the_real_repository_passes_the_guard(self, capsys):
        """The committed tree must satisfy its own rule."""
        assert guard.main() == 0, capsys.readouterr().out


class TestTheBaselineIsFrozenAndRatchetsOneWay:
    """The baseline is a recorded debt, not a standing permission.

    An allowlist where every entry shares one reason satisfies the
    has-a-reason rule in text and defeats it in substance: it can no longer
    tell a decision apart from an oversight. Splitting the two — a frozen
    baseline in code for "nobody has looked yet", an allowlist for "somebody
    decided, and said why" — is what restores that distinction, and these
    proofs hold the split in place.
    """

    @pytest.fixture
    def frozen(self, repo, monkeypatch):
        """A miniature repo whose baseline holds one unrun file."""
        repo.write_tests("test_legacy_gap.py")
        monkeypatch.setattr(guard, "FROZEN_BASELINE", frozenset({"tests/test_legacy_gap.py"}))
        monkeypatch.setattr(guard, "BASELINE_HIGH_WATER", 1)
        return repo

    def test_the_frozen_baseline_passes(self, frozen, capsys):
        """Guards the cases below: they must fail for their own reason."""
        assert guard.main() == 0
        assert "frozen baseline still unrun      : 1" in capsys.readouterr().out

    # (a) a new file cannot borrow the baseline excuse

    def test_a_new_unrun_file_cannot_join_the_frozen_baseline(self, frozen, capsys):
        """The set is frozen in code, so a new gap has nowhere to hide."""
        frozen.write_tests("test_brand_new_gap.py")
        assert guard.main() == 1
        out = capsys.readouterr().out
        assert "tests/test_brand_new_gap.py" in out
        assert "The frozen baseline is closed" in out

    def test_a_new_file_reusing_the_baseline_reason_fails(self, frozen, capsys):
        """The excuse belongs to the measured paths, not to whoever copies it."""
        frozen.write_tests("test_brand_new_gap.py")
        frozen.allowlist(
            f"tests/test_brand_new_gap.py  # {guard.BASELINE_SENTINEL}, pending\n"
        )
        assert guard.main() == 1
        out = capsys.readouterr().out
        assert "reusing the frozen baseline's reason" in out
        assert "fails closed" in out

    def test_a_new_file_with_its_own_reason_is_accepted(self, frozen):
        """The escape hatch stays open — it just has to be spelled out."""
        frozen.write_tests("test_brand_new_gap.py")
        frozen.allowlist(
            "tests/test_brand_new_gap.py  # needs a live Paddle sandbox\n"
        )
        assert guard.main() == 0

    # (b) one-way ratchet

    def test_a_baseline_larger_than_the_high_water_mark_fails(
        self, frozen, monkeypatch, capsys
    ):
        """Growth is the forbidden direction."""
        frozen.write_tests("test_second_gap.py")
        monkeypatch.setattr(
            guard,
            "FROZEN_BASELINE",
            frozenset({"tests/test_legacy_gap.py", "tests/test_second_gap.py"}),
        )
        assert guard.main() == 1
        out = capsys.readouterr().out
        assert "the baseline may only shrink" in out.lower()

    def test_shrinking_the_baseline_is_allowed(self, frozen, monkeypatch):
        """Paying debt down must not be punished."""
        monkeypatch.setattr(guard, "FROZEN_BASELINE", frozenset())
        monkeypatch.setattr(guard, "BASELINE_HIGH_WATER", 0)
        repo_wf = (frozen.path / ".github" / "workflows" / "qa-tests.yml")
        repo_wf.write_text(
            WORKFLOW.replace(
                "            tests/test_enumerated.py \\\n",
                "            tests/test_enumerated.py \\\n"
                "            tests/test_legacy_gap.py \\\n",
            )
        )
        assert guard.main() == 0

    # (c) the debt is visible in every run

    def test_every_run_prints_the_remaining_debt(self, frozen, capsys):
        assert guard.main() == 0
        out = capsys.readouterr().out
        assert "DEBT: 1 of 1 baseline files are still run by no workflow" in out
        assert "may only go down" in out

    def test_the_debt_line_is_printed_on_failure_too(self, frozen, capsys):
        """A failing run must still say how large the debt is."""
        frozen.write_tests("test_brand_new_gap.py")
        assert guard.main() == 1
        assert "DEBT: 1 of 1 baseline files" in capsys.readouterr().out

    # (d) a stale exemption is a false record and must bite

    def test_a_baseline_path_that_is_now_enumerated_fails(self, frozen, capsys):
        """Enumerated means the exemption is a lie about intent."""
        (frozen.path / ".github" / "workflows" / "qa-tests.yml").write_text(
            WORKFLOW.replace(
                "            tests/test_enumerated.py \\\n",
                "            tests/test_enumerated.py \\\n"
                "            tests/test_legacy_gap.py \\\n",
            )
        )
        assert guard.main() == 1
        out = capsys.readouterr().out
        assert "are enumerated now" in out
        assert "tests/test_legacy_gap.py" in out
        assert "lower BASELINE_HIGH_WATER to 0" in out

    def test_a_baseline_path_whose_file_vanished_fails(self, frozen, capsys):
        """A path pointing at nothing is also a false record."""
        (frozen.path / "tests" / "test_legacy_gap.py").unlink()
        assert guard.main() == 1
        out = capsys.readouterr().out
        assert "no longer exist as test files" in out
        assert "tests/test_legacy_gap.py" in out
