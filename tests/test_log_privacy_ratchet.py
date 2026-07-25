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
import re
import shutil
import subprocess
import sys

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from log_privacy_ratchet import (  # noqa: E402
    RatchetError,
    main as ratchet_main,
    policy_surface,
    policy_weakened,
    run as ratchet_run,
    run_trusted as ratchet_run_trusted,
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

# An f-string log call carrying ONE sensitive label, and the same call carrying
# TWO. Both render one log statement, so a rule that stops at the first match
# produces an identical descriptor for each and the difference between them is
# empty — a newly introduced violation that the gate would pass.
_FSTRING_ONE_LABEL = '''\
import logging

logger = logging.getLogger(__name__)


def fstring_path(a, b):
    logger.info(f"fstring_event user={a}")
'''

_FSTRING_TWO_LABELS = '''\
import logging

logger = logging.getLogger(__name__)


def fstring_path(a, b):
    logger.info(f"fstring_event user={a} email={b}")
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
    # Idempotent: a test may resolve the base more than once (e.g. to compare
    # the advisory and trusted paths on the same commit), and re-adding an
    # existing worktree is an error.
    if not worktree.exists():
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

    def test_a_second_sensitive_label_on_one_fstring_call_is_rejected(self, repo, tmp_path):
        """One log call must be able to contribute more than one finding.

        A rule that stops at the first matching label collapses every f-string
        call to a single descriptor, so adding a second sensitive field to a
        call that already violates leaves base and head identical and the
        difference empty. That is the multiset argument defeated inside one
        rule, and it passes a newly introduced violation.
        """
        (repo / "src" / "fstr.py").write_text(_FSTRING_ONE_LABEL, encoding="utf-8")
        _commit(repo, "baseline f-string site with one sensitive label")

        _git(repo, "checkout", "-q", "-b", "feature")
        (repo / "src" / "fstr.py").write_text(_FSTRING_TWO_LABELS, encoding="utf-8")
        _commit(repo, "add a second sensitive label to the same call")
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


class TestRatchetResistsRuleWeakening:
    """A change must not be able to edit the rules it is judged by.

    Judging both trees only by the HEAD checkout's rule module lets a PR drop a
    label or predicate so that both scans go blind together — the new site
    produces no finding on either side and the difference is empty. The base
    tree's rules are therefore applied as well, so the policy in force before
    the change still binds it.
    """

    def _weaken_head_vocabulary(self, repo: pathlib.Path, label: str) -> None:
        rules = repo / "tests" / "test_1076_log_privacy.py"
        text = rules.read_text(encoding="utf-8")
        for variant in (f'"{label}", ', f'"{label}",', f'"{label}"'):
            if variant in text:
                text = text.replace(variant, "", 1)
                break
        else:  # pragma: no cover - guards the fixture, not the product
            raise AssertionError(f"could not remove {label!r} from the rule vocabulary")
        rules.write_text(text, encoding="utf-8")

    def test_dropping_a_label_cannot_licence_a_new_site(self, repo, tmp_path):
        _git(repo, "checkout", "-q", "-b", "feature")
        # Remove 'email' from BOTH rule vocabularies in the head checkout, then
        # add a site that only that label would have caught.
        self._weaken_head_vocabulary(repo, "email")   # _SENSITIVE_LABELS
        self._weaken_head_vocabulary(repo, "email")   # _BARE_SENSITIVE_NAMES
        (repo / "src" / "added.py").write_text(
            'import logging\n\nlogger = logging.getLogger(__name__)\n\n\n'
            'def added_path(email):\n'
            '    logger.info("added_event email=%s", email)\n',
            encoding="utf-8",
        )
        _commit(repo, "relax the rule vocabulary and add a site it no longer sees")
        assert _ratchet(repo, tmp_path) == 1

    def test_the_weakened_head_rules_alone_would_have_passed_it(self, repo, tmp_path):
        """Proves the base-rules comparison is what rejects it, not luck."""
        from log_privacy_ratchet import load_rules, new_violations, scan_tree

        _git(repo, "checkout", "-q", "-b", "feature")
        self._weaken_head_vocabulary(repo, "email")
        self._weaken_head_vocabulary(repo, "email")
        (repo / "src" / "added.py").write_text(
            'import logging\n\nlogger = logging.getLogger(__name__)\n\n\n'
            'def added_path(email):\n'
            '    logger.info("added_event email=%s", email)\n',
            encoding="utf-8",
        )
        _commit(repo, "relax the rule vocabulary and add a site it no longer sees")
        base_tree, _base_sha, _head_sha = _base_tree(repo, tmp_path)

        head_rules = load_rules(repo, tag="w_head")
        assert new_violations(
            scan_tree(head_rules, base_tree), scan_tree(head_rules, repo)
        ) == [], "head rules should be blind here — that is the bypass"

        base_rules = load_rules(base_tree, tag="w_base")
        assert new_violations(
            scan_tree(base_rules, base_tree), scan_tree(base_rules, repo)
        ) != [], "base rules must still catch it"

    def test_a_protection_added_by_this_change_takes_effect_immediately(
        self, repo, tmp_path
    ):
        """The head-rules comparison is what makes a NEW rule bite now."""
        _git(repo, "checkout", "-q", "-b", "feature")
        rules = repo / "tests" / "test_1076_log_privacy.py"
        text = rules.read_text(encoding="utf-8")
        text = text.replace(
            '_BARE_SENSITIVE_NAMES = frozenset({\n',
            '_BARE_SENSITIVE_NAMES = frozenset({\n    "passport_no",\n',
            1,
        )
        rules.write_text(text, encoding="utf-8")
        (repo / "src" / "added.py").write_text(
            'import logging\n\nlogger = logging.getLogger(__name__)\n\n\n'
            'def added_path(passport_no):\n'
            '    logger.info("added_event ref=%s", passport_no)\n',
            encoding="utf-8",
        )
        _commit(repo, "add a protection and a site it forbids")
        assert _ratchet(repo, tmp_path) == 1


class TestTrustedEnforcementResistsSelfModification:
    """The enforcement path must not execute the policy the change can edit.

    The advisory dual-pass rejects "weaken AND add a site" but cannot see
    "weaken only": such a change leaves src/ identical on both sides, so every
    source diff is empty. It would land, and its relaxed rule would become the
    merge-base policy for the next change — the bypass delayed by one PR, not
    prevented. These cases model that two-PR sequence against the trusted path,
    which executes only the base branch's rules.
    """

    _EXPOSED_SITE = (
        'import logging\n\nlogger = logging.getLogger(__name__)\n\n\n'
        'def added_path(email):\n'
        '    logger.info("added_event email=%s", email)\n'
    )

    def _drop_label(self, repo: pathlib.Path, label: str, times: int = 2) -> None:
        rules = repo / "tests" / "test_1076_log_privacy.py"
        text = rules.read_text(encoding="utf-8")
        for _ in range(times):
            for variant in (f'"{label}", ', f'"{label}",', f'"{label}"'):
                if variant in text:
                    text = text.replace(variant, "", 1)
                    break
        rules.write_text(text, encoding="utf-8")

    def test_pr_a_weakening_only_is_rejected(self, repo, tmp_path):
        """PR A: relax the policy, change no source. src/ diffs are empty."""
        trusted = repo / "tests" / "test_1076_log_privacy.py"
        assert trusted.is_file()

        _git(repo, "checkout", "-q", "-b", "pr-a")
        self._drop_label(repo, "email")
        _commit(repo, "relax the policy vocabulary only")
        base_tree, _b, _h = _base_tree(repo, tmp_path)

        # The source-only comparison sees nothing: src/ is byte-identical.
        assert _ratchet(repo, tmp_path) == 0
        # The trusted path rejects it on the policy surface alone.
        assert ratchet_run_trusted(base_tree, repo, base_tree) == 1

    def test_pr_b_cannot_inherit_a_weakened_baseline(self, repo, tmp_path):
        """PR B: with PR A merged, exploit the now-weakened baseline.

        Trusted enforcement is anchored to the base branch's rules, so this is
        only safe because PR A was stopped. Modelled here by keeping a trusted
        rules tree that never saw PR A's weakening.
        """
        trusted_rules_tree = tmp_path / "trusted"
        shutil.copytree(repo, trusted_rules_tree)

        # PR A lands (as it would have, without the trusted gate).
        _git(repo, "checkout", "-q", "-b", "pr-a")
        self._drop_label(repo, "email")
        _commit(repo, "PR A: relax the policy vocabulary")
        _git(repo, "checkout", "-q", "main")
        _git(repo, "merge", "-q", "--no-ff", "-m", "merge PR A", "pr-a")

        # PR B adds a site that only the dropped label would have caught.
        _git(repo, "checkout", "-q", "-b", "pr-b")
        (repo / "src" / "added.py").write_text(self._EXPOSED_SITE, encoding="utf-8")
        _commit(repo, "PR B: add a site the weakened policy no longer sees")
        base_tree, _b, _h = _base_tree(repo, tmp_path)

        # Judged by the inherited (weakened) policy, PR B looks clean.
        assert _ratchet(repo, tmp_path) == 0
        # Judged by a policy PR A never touched, it is caught.
        assert ratchet_run_trusted(base_tree, repo, trusted_rules_tree) == 1

    def test_trusted_path_passes_an_honest_change(self, repo, tmp_path):
        _git(repo, "checkout", "-q", "-b", "feature")
        (repo / "src" / "added.py").write_text(_CLEAN_MODULE, encoding="utf-8")
        _commit(repo, "add a compliant module")
        base_tree, _b, _h = _base_tree(repo, tmp_path)
        assert ratchet_run_trusted(base_tree, repo, base_tree) == 0

    def test_trusted_path_still_rejects_an_ordinary_new_violation(self, repo, tmp_path):
        _git(repo, "checkout", "-q", "-b", "feature")
        (repo / "src" / "added.py").write_text(_NEW_VIOLATION, encoding="utf-8")
        _commit(repo, "introduce a violation without touching policy")
        base_tree, _b, _h = _base_tree(repo, tmp_path)
        assert ratchet_run_trusted(base_tree, repo, base_tree) == 1

    def test_widening_the_approved_helper_set_counts_as_weakening(self, repo, tmp_path):
        """Growing "already safe" is weakening by another route."""
        _git(repo, "checkout", "-q", "-b", "feature")
        rules = repo / "tests" / "test_1076_log_privacy.py"
        text = rules.read_text(encoding="utf-8")
        text = text.replace(
            '_APPROVED_REFS = frozenset({\n',
            '_APPROVED_REFS = frozenset({\n    "str",\n', 1,
        )
        rules.write_text(text, encoding="utf-8")
        _commit(repo, "treat str() as a sanctioned helper")
        base_tree, _b, _h = _base_tree(repo, tmp_path)
        assert ratchet_run_trusted(base_tree, repo, base_tree) == 1

    def test_removing_a_policy_set_outright_is_refused(self, repo, tmp_path):
        _git(repo, "checkout", "-q", "-b", "feature")
        rules = repo / "tests" / "test_1076_log_privacy.py"
        text = rules.read_text(encoding="utf-8")
        text = re.sub(
            r"_BARE_SENSITIVE_NAMES = frozenset\(\{.*?\}\)\n",
            "_BARE_SENSITIVE_NAMES = frozenset()\n",
            text, count=1, flags=re.S,
        )
        rules.write_text(text, encoding="utf-8")
        _commit(repo, "empty a policy vocabulary")
        base_tree, _b, _h = _base_tree(repo, tmp_path)
        assert ratchet_run_trusted(base_tree, repo, base_tree) == 1

    def test_policy_surface_is_read_without_importing(self, repo):
        """The head rule module is untrusted data in the enforcement path."""
        rules = repo / "tests" / "test_1076_log_privacy.py"
        rules.write_text(
            rules.read_text(encoding="utf-8")
            + '\nraise SystemExit("importing the head policy must never happen")\n',
            encoding="utf-8",
        )
        surface = policy_surface(rules)          # parses; must not execute
        assert "email" in surface["_BARE_SENSITIVE_NAMES"]

    def test_policy_weakened_reports_both_directions(self):
        base = {n: frozenset({"a"}) for n in
                ("_SENSITIVE_LABELS", "_BARE_SENSITIVE_NAMES", "_LOG_METHODS",
                 "_SWEPT_MODULES", "_APPROVED_REFS", "_INTERNAL_ID_ALLOWLIST")}
        head = dict(base)
        head["_SENSITIVE_LABELS"] = frozenset()
        head["_APPROVED_REFS"] = frozenset({"a", "b"})
        complaints = policy_weakened(base, head)
        assert any("lost" in c for c in complaints)
        assert any("gained" in c for c in complaints)


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

    def test_a_fully_remediated_tree_is_a_valid_clean_state(self, repo, tmp_path):
        """Zero findings is what success looks like, not a broken checkout.

        Refusing an empty baseline would mean the gate breaks at exactly the
        moment the remediation work finishes.
        """
        # Remove the only debt in the base, on the base itself.
        (repo / "src" / "legacy.py").write_text(_CLEAN_MODULE, encoding="utf-8")
        _commit(repo, "remediate every site — the baseline is now clean")

        _git(repo, "checkout", "-q", "-b", "feature")
        (repo / "src" / "another.py").write_text(_CLEAN_MODULE, encoding="utf-8")
        _commit(repo, "add another compliant module on a clean baseline")
        assert _ratchet(repo, tmp_path) == 0

    def test_a_clean_baseline_still_rejects_a_new_violation(self, repo, tmp_path):
        (repo / "src" / "legacy.py").write_text(_CLEAN_MODULE, encoding="utf-8")
        _commit(repo, "remediate every site")

        _git(repo, "checkout", "-q", "-b", "feature")
        (repo / "src" / "added.py").write_text(_NEW_VIOLATION, encoding="utf-8")
        _commit(repo, "regress on a clean baseline")
        assert _ratchet(repo, tmp_path) == 1

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

    def test_undecodable_bytes_are_refused_not_silently_mangled(self, repo, tmp_path):
        """errors="replace" would substitute bytes and carry on.

        Mangled source can still parse, and a format literal whose bytes were
        substituted may no longer contain the label it used to — a silent
        false negative in a gate whose contract is that it has none.
        """
        _git(repo, "checkout", "-q", "-b", "feature")
        # Valid Python, invalid UTF-8: a latin-1 byte inside a string literal.
        (repo / "src" / "broken.py").write_bytes(
            b'import logging\nlogger = logging.getLogger(__name__)\n'
            b'MSG = "caf\xe9 user=%s"\n'
        )
        _commit(repo, "add a module that is not valid utf-8")
        base_tree, base_sha, head_sha = _base_tree(repo, tmp_path)
        with pytest.raises(RatchetError, match="could not decode"):
            ratchet_run(base_tree, repo, base_sha, head_sha)

    def test_a_module_that_does_not_parse_is_refused(self, repo, tmp_path):
        _git(repo, "checkout", "-q", "-b", "feature")
        (repo / "src" / "bad.py").write_text("def (:\n", encoding="utf-8")
        _commit(repo, "add a module that does not parse")
        base_tree, base_sha, head_sha = _base_tree(repo, tmp_path)
        with pytest.raises(RatchetError, match="could not parse"):
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
