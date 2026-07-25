#!/usr/bin/env python3
"""#1084 — static CI guards for GitHub Actions workflow security.

Hard failures (exit 1):
  1. secret-like ``workflow_dispatch`` inputs — a dispatch input is not a
     secret transport (unmasked, retained in run metadata), so any input whose
     name looks credential-shaped is rejected.
  2. mutable branch refs in ``uses:`` — ``@main`` / ``@master`` / ``@latest``
     or a missing ref track a moving target. (Full commit-SHA pinning of
     version tags is supply-chain scope tracked in #127, not enforced here.)
  3. privileged workflows (anything touching the Render account API or its
     credential) without an explicit least-privilege ``permissions:`` block.
  4. destructive provider jobs (PATCH/DELETE against the provider API) not
     attached to a protected ``environment:`` or without a ``dry_run`` input
     defaulting to ``'true'``.
  5. ``pull_request_target`` workflows that break any of the containment
     properties documented in their own headers — see below.

Soft warnings (printed, exit 0): non-privileged workflows without an explicit
``permissions:`` block — broad hardening tracked in #127.

``pull_request_target`` containment
-----------------------------------
That trigger runs the BASE branch's copy of a workflow while a pull request
supplies the head, so the job is privileged and its input is author-controlled.
Workflows using it already document the properties that keep them safe in a
header comment; group 5 makes those same properties executable, so an edit that
drops one fails CI instead of relying on a reviewer noticing:

  a. an explicit ``permissions:`` block granting nothing above ``read``;
  b. ``actions/checkout`` with no ``ref:``, so the workspace stays the base
     branch and the head is never checked out over it;
  c. dependencies installed by name — no ``-r``/``--requirement``, no ``-e``
     and no local-path install, since a dependency file is author-controlled
     input in this context;
  d. no ``secrets.*`` reference reaching the job;
  e. no author-controlled event field (branch name, title, body, fork
     metadata, login) interpolated into ``run:``, ``env:`` or ``with:``, where
     it would be evaluated by the shell or handed to an action.

Detection keys off the parsed ``on:`` block, never a raw substring, so a
workflow that merely mentions the trigger in a comment is not swept in.

Property (b) and (c) are the mechanically decidable half of "the head is read
as data, never executed". Whether the tooling a workflow invokes goes on to
import the head tree is a property of that tooling, not of the YAML, and is out
of reach of a static check over workflow files.
"""

from __future__ import annotations

import pathlib
import re
import sys

import yaml

WORKFLOWS_DIR = pathlib.Path(".github/workflows")

_SECRET_INPUT_RE = re.compile(
    r"(key|token|secret|password|passwd|credential|bearer|auth)", re.IGNORECASE
)
_MUTABLE_REFS = {"main", "master", "latest", "head"}
_PRIVILEGED_MARKERS = ("api.render.com", "RENDER_API_KEY")
_MUTATION_MARKERS = ("-X PATCH", "-X DELETE", '"DELETE"', "'DELETE'", "method=DELETE")

# Event fields the opener of a pull request controls. A fork branch name, a
# title or a body is free text; interpolated into a shell command it is
# executed, and handed to an action it is that action's input. Head SHA, PR
# number and base ref are absent on purpose — those are repository-controlled
# and the trusted workflow legitimately reads all three.
_UNTRUSTED_EVENT_FIELDS = (
    "github.head_ref",
    "github.event.pull_request.title",
    "github.event.pull_request.body",
    "github.event.pull_request.head.ref",
    "github.event.pull_request.head.label",
    "github.event.pull_request.head.repo",
    "github.event.pull_request.user",
)
# Installs that read an author-controlled dependency file or build a local
# path, rather than resolving a name from the index.
_LOCAL_INSTALL_RE = re.compile(
    r"""(?:pip3?|pip)\s+install\b[^\n;&|]*?
        (?:\s-r\b|\s--requirement\b|\s-e\b|\s--editable\b|\s\.(?:\s|$)|\s\./)""",
    re.VERBOSE,
)
_PERMISSION_LEVELS_ALLOWED = {"read", "none"}


def _load(path: pathlib.Path):
    doc = yaml.safe_load(path.read_text())
    if not isinstance(doc, dict):
        return {}
    # PyYAML parses the bare key `on:` as boolean True.
    if True in doc and "on" not in doc:
        doc["on"] = doc.pop(True)
    return doc


def check_secret_like_inputs(doc: dict, path: str) -> list[str]:
    violations = []
    on = doc.get("on") or {}
    dispatch = on.get("workflow_dispatch") if isinstance(on, dict) else None
    inputs = (dispatch or {}).get("inputs") if isinstance(dispatch, dict) else None
    for name in (inputs or {}):
        if _SECRET_INPUT_RE.search(str(name)):
            violations.append(
                f"{path}: workflow_dispatch input '{name}' is secret-like — "
                "dispatch inputs are not a secret transport (#1084)"
            )
    return violations


def check_action_refs(doc: dict, path: str) -> list[str]:
    violations = []
    for job_name, job in (doc.get("jobs") or {}).items():
        for step in (job or {}).get("steps") or []:
            uses = (step or {}).get("uses")
            if not uses or str(uses).startswith("./"):
                continue
            ref = str(uses).rsplit("@", 1)
            if len(ref) != 2 or not ref[1] or ref[1].lower() in _MUTABLE_REFS:
                violations.append(
                    f"{path}: job '{job_name}' uses mutable action ref '{uses}' "
                    "(pin a tag or commit SHA; full SHA pinning: #127)"
                )
    return violations


def _has_permissions(doc: dict) -> bool:
    if "permissions" in doc:
        return True
    jobs = doc.get("jobs") or {}
    return bool(jobs) and all("permissions" in (j or {}) for j in jobs.values())


def check_privileged(doc: dict, raw: str, path: str) -> list[str]:
    violations = []
    if not any(m in raw for m in _PRIVILEGED_MARKERS):
        return violations
    if not _has_permissions(doc):
        violations.append(
            f"{path}: privileged workflow (Render credential) without an "
            "explicit least-privilege 'permissions:' block"
        )
    mutating = any(m in raw for m in _MUTATION_MARKERS)
    if mutating:
        jobs = doc.get("jobs") or {}
        if not all("environment" in (j or {}) for j in jobs.values()):
            violations.append(
                f"{path}: destructive provider job not attached to a protected "
                "'environment:' (approval boundary required)"
            )
        on = doc.get("on") or {}
        dispatch = on.get("workflow_dispatch") if isinstance(on, dict) else None
        inputs = (dispatch or {}).get("inputs") or {}
        dry = inputs.get("dry_run") or {}
        if str(dry.get("default", "")).lower() != "true":
            violations.append(
                f"{path}: destructive provider workflow must default to "
                "dry_run='true'"
            )
    return violations


def _triggers(doc: dict) -> set[str]:
    """Trigger names from the parsed ``on:`` block, in any of its three forms.

    Parsed, never grepped: a workflow that names a trigger in a comment or in
    prose does not use it, and sweeping those in would make the guard something
    authors work around rather than with.
    """
    on = doc.get("on")
    if isinstance(on, str):
        return {on}
    if isinstance(on, list):
        return {str(item) for item in on}
    if isinstance(on, dict):
        return {str(key) for key in on}
    return set()


def _expression_sources(doc: dict):
    """Yield (where, text) for every value a workflow expression can reach.

    ``run:`` is evaluated by the shell; ``env:`` and ``with:`` are handed to
    the shell or to an action. Values that are only ever displayed, such as
    ``name:``, are excluded — interpolating there executes nothing.

    A job's ``container`` and each of its ``services`` are configured from the
    same expressions, so they are the same kind of position and are walked the
    same way. Both ``credentials`` and ``env`` are yielded in full: every
    service rather than the first, and every key rather than a fixed list of
    the names one expects to find. ``username`` carries a secret exactly as
    well as ``password`` does, and a rule that reads only the keys it predicts
    is complete only against the inputs it predicted.
    """
    def _walk_env(env, where):
        if isinstance(env, dict):
            for key, value in env.items():
                yield f"{where} env '{key}'", str(value)

    def _walk_container(block, where):
        # ``container: image`` is legal shorthand and holds no expressions.
        if not isinstance(block, dict):
            return
        credentials = block.get("credentials")
        if isinstance(credentials, dict):
            for key, value in credentials.items():
                yield f"{where} credentials '{key}'", str(value)
        yield from _walk_env(block.get("env"), where)

    yield from _walk_env(doc.get("env"), "workflow")
    for job_name, job in (doc.get("jobs") or {}).items():
        job = job or {}
        yield from _walk_env(job.get("env"), f"job '{job_name}'")
        yield from _walk_container(
            job.get("container"), f"job '{job_name}' container")
        services = job.get("services")
        if isinstance(services, dict):
            for service_name, service in services.items():
                yield from _walk_container(
                    service, f"job '{job_name}' service '{service_name}'")
        for index, step in enumerate(job.get("steps") or []):
            step = step or {}
            where = f"job '{job_name}' step {index + 1}"
            if step.get("run"):
                yield f"{where} run", str(step["run"])
            yield from _walk_env(step.get("env"), where)
            with_block = step.get("with")
            if isinstance(with_block, dict):
                for key, value in with_block.items():
                    yield f"{where} with '{key}'", str(value)


def _permission_violations(doc: dict, path: str) -> list[str]:
    """Every declared scope must be read or none, wherever it is declared."""
    def _scopes(block, where):
        if block is None:
            return None
        if isinstance(block, str):
            # 'read-all' / 'write-all' / '{}' shorthand.
            return [] if block.strip() in ("{}", "read-all") else [(where, block, block)]
        if isinstance(block, dict):
            return [
                (where, scope, str(level))
                for scope, level in block.items()
                if str(level).strip().lower() not in _PERMISSION_LEVELS_ALLOWED
            ]
        return [(where, "permissions", str(block))]

    top = doc.get("permissions")
    jobs = doc.get("jobs") or {}
    found = []
    offenders = []

    if top is not None:
        found.append("workflow")
        offenders += _scopes(top, "workflow") or []
    for job_name, job in jobs.items():
        block = (job or {}).get("permissions")
        if block is not None:
            found.append(f"job '{job_name}'")
            offenders += _scopes(block, f"job '{job_name}'") or []

    violations = []
    if top is None and not all("permissions" in (j or {}) for j in jobs.values()):
        violations.append(
            f"{path}: pull_request_target workflow without an explicit "
            "'permissions:' block — this trigger is privileged, so the token "
            "must be narrowed rather than inherited"
        )
    for where, scope, level in offenders:
        violations.append(
            f"{path}: pull_request_target {where} grants '{scope}: {level}' — "
            "this trigger must grant nothing above read"
        )
    return violations


def check_pull_request_target(doc: dict, path: str) -> list[str]:
    """Make the containment properties of a pull_request_target workflow executable."""
    if "pull_request_target" not in _triggers(doc):
        return []

    violations = _permission_violations(doc, path)

    for job_name, job in (doc.get("jobs") or {}).items():
        for index, step in enumerate((job or {}).get("steps") or []):
            step = step or {}
            where = f"job '{job_name}' step {index + 1}"

            uses = str(step.get("uses") or "")
            if uses.split("@", 1)[0].strip().lower().endswith("actions/checkout"):
                with_block = step.get("with")
                if isinstance(with_block, dict) and "ref" in with_block:
                    violations.append(
                        f"{path}: pull_request_target {where} checks out "
                        f"ref '{with_block['ref']}' — this trigger must leave "
                        "the workspace on the base branch, so checkout takes "
                        "no 'ref:'"
                    )

            run = str(step.get("run") or "")
            if run and _LOCAL_INSTALL_RE.search(run):
                violations.append(
                    f"{path}: pull_request_target {where} installs from a "
                    "requirement file or local path — dependencies must be "
                    "resolved by name, because a dependency file is "
                    "author-controlled input under this trigger"
                )

    for where, text in _expression_sources(doc):
        if "secrets." in text:
            violations.append(
                f"{path}: pull_request_target {where} references a secret — "
                "no secret may reach a job running against an "
                "author-controlled head"
            )
        for field in _UNTRUSTED_EVENT_FIELDS:
            if field in text:
                violations.append(
                    f"{path}: pull_request_target {where} interpolates "
                    f"'{field}', which the pull request author controls — read "
                    "it through an intermediate env var, or use a "
                    "repository-controlled field such as head.sha"
                )
    return violations


def check_workflow(path: pathlib.Path) -> tuple[list[str], list[str]]:
    """Return (violations, warnings) for one workflow file."""
    raw = path.read_text()
    doc = _load(path)
    rel = str(path)
    violations = (
        check_secret_like_inputs(doc, rel)
        + check_action_refs(doc, rel)
        + check_privileged(doc, raw, rel)
        + check_pull_request_target(doc, rel)
    )
    warnings = []
    if not _has_permissions(doc) and not any(m in raw for m in _PRIVILEGED_MARKERS):
        warnings.append(
            f"{rel}: no explicit 'permissions:' block (non-privileged — "
            "tracked by #127, not fatal here)"
        )
    return violations, warnings


def main() -> int:
    files = sorted(
        list(WORKFLOWS_DIR.glob("*.yml")) + list(WORKFLOWS_DIR.glob("*.yaml"))
    )
    if not files:
        print("No workflow files found — nothing to check.")
        return 0
    all_violations: list[str] = []
    all_warnings: list[str] = []
    for f in files:
        v, w = check_workflow(f)
        all_violations += v
        all_warnings += w
    for w in all_warnings:
        print(f"WARN: {w}")
    if all_violations:
        for v in all_violations:
            print(f"FAIL: {v}")
        print(f"\n{len(all_violations)} workflow security violation(s).")
        return 1
    print(f"OK: {len(files)} workflow file(s) pass the #1084 security guards.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
