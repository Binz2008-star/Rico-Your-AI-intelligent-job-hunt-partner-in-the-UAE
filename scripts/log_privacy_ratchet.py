#!/usr/bin/env python3
"""Differential log-privacy ratchet.

Scans every module under ``src/`` in two trees — the merge base and the PR
head — and fails when a violation exists in HEAD that does not exist in base.

Why differential rather than a checked-in manifest:

* it forbids NEW debt without publishing where the existing debt is;
* it catches a swap (one site fixed, another introduced) that a numeric
  ceiling cannot, because the new site is absent from the base set whatever
  the total;
* a newly added file arrives protected, since every violation in it is by
  definition absent from base;
* there is no stored inventory to drift out of step with the code. The code
  plus this scanner are the only source of truth, and the unresolved
  inventory is generated on demand rather than kept in the repository.

The detection predicates are NOT reimplemented here. They are imported from
``tests/test_1076_log_privacy.py``, which owns the two rules and their proofs:

  rule 1 — a sensitive field label in a log format must receive a sanctioned
           ``log_privacy`` helper call in that argument position;
  rule 2 — a bare identifier naming an external identifier must not be handed
           to a logger, whatever the format string says.

This module adds only a stable DESCRIPTOR for each finding so two trees can be
compared. Line numbers are deliberately excluded: inserting a line above a
site would otherwise register as a new violation on every subsequent site.

The descriptor is (module, enclosing qualified name, rule, field), which has a
known and ACCEPTED false positive: a pure refactor can trip the gate. Move a
pre-existing violating call to another module, or rename the function that
encloses it, and its descriptor changes — head then holds an entry base lacks,
and the gate goes red on a change that introduced nothing new.

This is deliberate and must not be "fixed" by loosening the descriptor or
adding an escape hatch. The wrong direction to err in a privacy gate is
silence, and the remedy is cheap and in the right direction: sanitise the site
you were already moving. Anyone who hits this and concludes the gate is broken
should read this paragraph first — it is working as designed.

Exit codes: 0 clean, 1 new violations, 2 the ratchet could not run safely.
"""
from __future__ import annotations

import argparse
import collections
import importlib.util
import pathlib
import sys
from typing import Iterable, NamedTuple

# Which rules are executed depends on the mode:
#
#   advisory (--trusted absent) — both the base tree's and the head tree's
#       rules are executed, so a protection added by the change is exercised
#       in the same PR. This mode imports code from the head tree and is
#       therefore only safe on a `pull_request` trigger with no privileges.
#
#   trusted (--trusted) — ONLY the rules from --rules-tree are executed. The
#       head tree is never imported, only read as data, so this mode is safe
#       under `pull_request_target` where the workflow, the scanner and the
#       rules all come from the base branch and the change cannot alter what
#       judges it.
_RULES_RELPATH = pathlib.Path("tests") / "test_1076_log_privacy.py"

# Vocabulary sets that define the policy surface. Extracted by parsing, never
# by importing, so an untrusted head tree is only ever read as data.
#   shrinking a "must not shrink" set removes protection;
#   growing a "must not grow" set widens what counts as already-safe.
_POLICY_MUST_NOT_SHRINK = ("_SENSITIVE_LABELS", "_BARE_SENSITIVE_NAMES",
                           "_LOG_METHODS", "_SWEPT_MODULES")
_POLICY_MUST_NOT_GROW = ("_APPROVED_REFS", "_INTERNAL_ID_ALLOWLIST")


class RatchetError(RuntimeError):
    """The ratchet cannot run safely — never reported as 'clean'."""


class Finding(NamedTuple):
    module: str      # repo-relative posix path
    scope: str       # enclosing qualified name, stable across edits above it
    rule: str        # which rule fired
    name: str        # the field label or identifier involved

    def describe(self) -> str:
        return f"{self.module} :: {self.scope} :: {self.rule} :: {self.name}"


def load_rules(repo_root: pathlib.Path, *, tag: str = "head", required: bool = True):
    """Import the rule predicates from the guard that owns them.

    Loaded per tree, under a distinct module name, so the base tree's rules and
    the head tree's rules can both be held at once without clobbering.
    """
    rules_path = repo_root / _RULES_RELPATH
    if not rules_path.is_file():
        if not required:
            return None
        raise RatchetError(f"rule module not found at {rules_path}")
    # src.log_privacy is imported at module scope by the guard.
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    spec = importlib.util.spec_from_file_location(f"_log_privacy_rules_{tag}", rules_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for attr in (
        "_log_calls_with_scope", "_sensitive_positions", "_is_sanctioned",
        "_bare_name", "_rule_two_candidates", "_SENSITIVE_LABELS",
        "_BARE_SENSITIVE_NAMES",
    ):
        if not hasattr(module, attr):
            raise RatchetError(
                f"rule module is missing '{attr}' — the ratchet and the guard "
                f"have diverged; fix the guard rather than loosening this check"
            )
    return module


def _literal_strings(node: "ast.AST") -> frozenset:
    """Every string literal reachable inside an expression, flattened.

    Handles a set/tuple of strings and a set of tuples of strings alike, which
    is all the policy vocabularies use.
    """
    import ast

    return frozenset(
        n.value for n in ast.walk(node)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    )


def policy_surface(rules_path: pathlib.Path) -> dict:
    """Extract the policy vocabularies from a rule module BY PARSING IT.

    Never imports. In trusted mode the head tree's rule module is written by
    the change under judgement, so it is read strictly as data.
    """
    import ast

    if not rules_path.is_file():
        raise RatchetError(f"rule module not found at {rules_path}")
    try:
        tree = ast.parse(rules_path.read_text(encoding="utf-8-sig", errors="strict"))
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise RatchetError(f"could not read policy surface from {rules_path}: {exc}")

    wanted = set(_POLICY_MUST_NOT_SHRINK) | set(_POLICY_MUST_NOT_GROW)
    surface: dict = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not node.targets:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id in wanted:
            surface[target.id] = _literal_strings(node.value)
    missing = wanted - set(surface)
    if missing:
        raise RatchetError(
            "policy vocabularies missing from the head rule module: "
            f"{sorted(missing)} — a policy set cannot be removed outright"
        )
    return surface


def policy_weakened(base_surface: dict, head_surface: dict) -> list[str]:
    """Ways the head policy is weaker than the base policy."""
    complaints: list[str] = []
    for name in _POLICY_MUST_NOT_SHRINK:
        removed = sorted(base_surface[name] - head_surface[name])
        if removed:
            complaints.append(f"{name} lost {removed}")
    for name in _POLICY_MUST_NOT_GROW:
        added = sorted(head_surface[name] - base_surface[name])
        if added:
            complaints.append(f"{name} gained {added}")
    return complaints


def scan_file(rules, path: pathlib.Path, relpath: str) -> list[Finding]:
    """Apply both rules to one module, yielding stable descriptors."""
    import ast

    try:
        # utf-8-sig, not utf-8: at least one module in this repository carries
        # a UTF-8 BOM. Python's own tokenizer strips it when compiling from
        # disk, but a BOM left at the head of a decoded string makes
        # ast.parse raise on line 1. Reading it as utf-8 would make the
        # scanner fail on a file that is perfectly valid Python.
        #
        # errors="strict", never "replace": mangled source can still parse,
        # and a format literal whose bytes were substituted may no longer
        # contain the label it used to — a silent false negative in a gate
        # whose whole contract is that it has none.
        source = path.read_text(encoding="utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise RatchetError(f"could not decode {relpath} as utf-8: {exc}")

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        # A tree that does not parse cannot be compared; report it loudly
        # rather than silently contributing zero findings.
        raise RatchetError(f"could not parse {relpath}: {exc.msg} (line {exc.lineno})")

    findings: list[Finding] = []
    for scope, node in rules._log_calls_with_scope(tree):
        fmt = node.args[0]

        # Rule 1 — sensitive field label must receive a sanctioned helper.
        if isinstance(fmt, ast.Constant) and isinstance(fmt.value, str):
            supplied = node.args[1:]
            for index, label in rules._sensitive_positions(fmt.value).items():
                if index < len(supplied) and not rules._is_sanctioned(supplied[index]):
                    findings.append(Finding(relpath, scope, "labelled-field", label))
        elif isinstance(fmt, ast.JoinedStr):
            rendered = "".join(
                part.value for part in fmt.values
                if isinstance(part, ast.Constant) and isinstance(part.value, str)
            )
            # One finding PER matching label, and no early exit. Stopping at
            # the first match would collapse every f-string call to a single
            # descriptor, so adding a second sensitive field to a call that
            # already violates would leave base and head identical and pass a
            # newly introduced violation — the multiset defeated inside one
            # rule. Sorted, because iterating the label set directly made the
            # emitted descriptor depend on hash randomisation.
            for label in sorted(rules._SENSITIVE_LABELS):
                if f"{label}=" in rendered:
                    findings.append(Finding(relpath, scope, "fstring-format", label))

        # Rule 2 — bare identifier naming an external identifier.
        for arg in rules._rule_two_candidates(node):
            name = rules._bare_name(arg)
            if name and name.lower() in rules._BARE_SENSITIVE_NAMES:
                findings.append(Finding(relpath, scope, "bare-identifier", name))

    return findings


def scan_tree(rules, tree_root: pathlib.Path) -> collections.Counter:
    """Scan every module under ``<tree_root>/src`` into a multiset.

    A multiset, not a set: two identical descriptors in one function are two
    sites, and introducing a second must not hide behind the first.
    """
    src_root = tree_root / "src"
    if not src_root.is_dir():
        raise RatchetError(f"no src/ directory under {tree_root}")

    counts: collections.Counter = collections.Counter()
    files = sorted(src_root.rglob("*.py"))
    if not files:
        raise RatchetError(
            f"scanned {src_root} and found no Python files — refusing to treat "
            f"an empty scan as a clean result"
        )
    for path in files:
        relpath = path.relative_to(tree_root).as_posix()
        counts.update(scan_file(rules, path, relpath))
    # NOTE: an empty multiset is a legitimate result, not an error. A tree with
    # no findings is what full remediation looks like, and refusing it would
    # mean the gate breaks precisely when the work succeeds. The structural
    # checks above (src/ present, files found, strict decode, parseable) are
    # what distinguish a broken checkout from a clean one.
    return counts


def new_violations(base: collections.Counter, head: collections.Counter):
    """Descriptors occurring more often in HEAD than in base."""
    regressions = []
    for finding, head_count in sorted(head.items()):
        base_count = base.get(finding, 0)
        if head_count > base_count:
            regressions.append((finding, base_count, head_count))
    return regressions


def run_trusted(base_tree: pathlib.Path, head_tree: pathlib.Path,
                rules_tree: pathlib.Path) -> int:
    """Enforcement path: only the trusted tree's rules are ever executed.

    The change under judgement cannot alter what judges it. Two things are
    checked, both driven entirely by the trusted checkout:

      1. the policy surface may not be weakened — a set of protections may not
         shrink, and the set of already-safe helpers may not grow. This is what
         rejects a weakening-only change, which no source-tree diff can see
         because such a change leaves src/ identical on both sides;
      2. no violation exists in head that is absent from base, judged by the
         TRUSTED rules.

    The head tree is read as data only: parsed, never imported.
    """
    trusted_rules = load_rules(rules_tree, tag="trusted", required=True)

    complaints = policy_weakened(
        policy_surface(rules_tree / _RULES_RELPATH),
        policy_surface(head_tree / _RULES_RELPATH),
    )
    regressions = new_violations(
        scan_tree(trusted_rules, base_tree),
        scan_tree(trusted_rules, head_tree),
    )

    if not complaints and not regressions:
        print("OK — policy not weakened, and no violation introduced by this change.")
        return 0

    if complaints:
        print("\nFAIL — this change weakens the log-privacy policy:\n")
        for complaint in complaints:
            print(f"    {complaint}")
        print(
            "\nA change may not relax the rules that judge it. Weakening must go "
            "through the governance path for policy files, not an ordinary PR."
        )
    if regressions:
        print("\nFAIL — newly introduced log-privacy violation(s), "
              "judged by the trusted policy:\n")
        for finding, was, now in regressions:
            print(f"    {finding.describe()}   (base {was} -> head {now})")
        print(
            "\nWrap the argument with a helper from src/log_privacy.py "
            "(user_ref / token_ref / operation_ref / filename_ref / safe_fields)."
        )
    return 1


def run(base_tree: pathlib.Path, head_tree: pathlib.Path,
        base_sha: str | None, head_sha: str | None) -> int:
    # The dangerous failure is a base that silently equals HEAD: the diff is
    # then empty and every new violation passes. Refuse that outright.
    if base_sha and head_sha and base_sha == head_sha:
        raise RatchetError(
            f"base and head resolve to the same commit ({base_sha[:12]}). The "
            f"difference would be empty and every new violation would pass."
        )
    for label, tree in (("base", base_tree), ("head", head_tree)):
        if not tree.is_dir():
            raise RatchetError(f"{label} tree {tree} is not a directory")

    # TWO comparisons, because one is not enough.
    #
    # Judging both trees only by the HEAD checkout's rules lets a change edit
    # the rules it is judged by: drop a label or a predicate and both scans go
    # blind together, so a violation the old policy forbade slips through with
    # an empty difference.
    #
    #   (a) BASE rules over base vs head — the existing policy still applies to
    #       this change, so weakening the vocabulary cannot licence a new site.
    #   (b) HEAD rules over base vs head — protections ADDED by this change take
    #       effect immediately rather than one PR later.
    #
    # A regression under either comparison fails the gate.
    head_rules = load_rules(head_tree, tag="head", required=True)
    base_rules = load_rules(base_tree, tag="base", required=False)

    comparisons: list[tuple[str, list]] = []
    if base_rules is not None:
        comparisons.append((
            "existing policy (base rules)",
            new_violations(
                scan_tree(base_rules, base_tree),
                scan_tree(base_rules, head_tree),
            ),
        ))
    else:
        # Only legitimate when the base predates the guard entirely.
        print("note: base tree has no rule module; existing-policy comparison skipped")
    comparisons.append((
        "current policy (head rules)",
        new_violations(
            scan_tree(head_rules, base_tree),
            scan_tree(head_rules, head_tree),
        ),
    ))

    # Deliberately no totals, ratios or baseline figures are printed. CI logs
    # on a public repository are public, and a repository-wide count of
    # unresolved sites is exactly the posture measurement this design exists to
    # avoid publishing. Only violations introduced BY THIS CHANGE are named —
    # those lines are already in the PR diff, and the author needs them to act.
    if not any(regressions for _label, regressions in comparisons):
        print("OK — no log-privacy violation introduced by this change.")
        return 0

    print("\nFAIL — newly introduced log-privacy violation(s):")
    for label, regressions in comparisons:
        if not regressions:
            continue
        print(f"\n  under {label}:")
        for finding, was, now in regressions:
            print(f"    {finding.describe()}   (base {was} -> head {now})")
    print(
        "\nEach line logs a user identifier without a sanctioned helper.\n"
        "Wrap the argument with a helper from src/log_privacy.py "
        "(user_ref / token_ref / operation_ref / filename_ref / safe_fields).\n"
        "A failure under the existing policy but not the current one means this "
        "change relaxed the rules; restore the rule rather than the exemption.\n"
        "Pre-existing findings elsewhere are not reported here by design: this "
        "gate only forbids ADDING to them."
    )
    return 1


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-tree", required=True, type=pathlib.Path)
    parser.add_argument("--head-tree", required=True, type=pathlib.Path)
    parser.add_argument("--base-sha", default=None)
    parser.add_argument("--head-sha", default=None)
    parser.add_argument(
        "--trusted", action="store_true",
        help="enforcement mode: execute only --rules-tree's rules, never the "
             "head tree's, and reject a change that weakens the policy",
    )
    parser.add_argument(
        "--rules-tree", type=pathlib.Path, default=None,
        help="trusted checkout supplying the rules (required with --trusted)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        for label, tree in (("base", args.base_tree), ("head", args.head_tree)):
            if not tree.is_dir():
                raise RatchetError(f"{label} tree {tree} is not a directory")
        if args.trusted:
            if args.rules_tree is None:
                raise RatchetError("--trusted requires --rules-tree")
            if not args.rules_tree.is_dir():
                raise RatchetError(f"rules tree {args.rules_tree} is not a directory")
            if args.base_sha and args.head_sha and args.base_sha == args.head_sha:
                raise RatchetError(
                    f"base and head resolve to the same commit ({args.base_sha[:12]})"
                )
            return run_trusted(args.base_tree, args.head_tree, args.rules_tree)
        return run(args.base_tree, args.head_tree, args.base_sha, args.head_sha)
    except RatchetError as exc:
        print(f"log-privacy ratchet ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
