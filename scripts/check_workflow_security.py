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

Soft warnings (printed, exit 0): non-privileged workflows without an explicit
``permissions:`` block — broad hardening tracked in #127.
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


def check_workflow(path: pathlib.Path) -> tuple[list[str], list[str]]:
    """Return (violations, warnings) for one workflow file."""
    raw = path.read_text()
    doc = _load(path)
    rel = str(path)
    violations = (
        check_secret_like_inputs(doc, rel)
        + check_action_refs(doc, rel)
        + check_privileged(doc, raw, rel)
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
