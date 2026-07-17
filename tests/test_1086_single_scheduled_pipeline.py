"""tests/test_1086_single_scheduled_pipeline.py

#1086 — exactly one scheduled pipeline; generated content never lands on main.

Static invariants over .github/workflows/, enforced in CI so the containment
cannot silently regress:

  1. Exactly ONE workflow owns a schedule that runs src.run_daily — the
     canonical daily.yml. The legacy workflow must stay manual-only.
  2. Every workflow that runs src.run_daily shares ONE concurrency group with
     cancel-in-progress disabled (queued, never concurrent, never killed
     mid-run).
  3. No workflow pushes to main (generated dashboard commits contaminated
     deploy history and triggered backend redeploys twice a day).
  4. Dashboard publication happens only after pipeline success and its push
     failure is never swallowed with `|| echo`.
  5. The Render/production deploy workflows only auto-trigger for runtime
     paths.
  6. Apply/auto-action flags stay off in the scheduled pipeline.
"""
from __future__ import annotations

import os
import re

import pytest

yaml = pytest.importorskip("yaml")

_WF_DIR = os.path.join(os.path.dirname(__file__), "..", ".github", "workflows")


def _load(name: str) -> tuple[dict, str]:
    path = os.path.join(_WF_DIR, name)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    return yaml.safe_load(text), text


def _all_workflows() -> dict[str, tuple[dict, str]]:
    out = {}
    for name in os.listdir(_WF_DIR):
        if name.endswith((".yml", ".yaml")):
            out[name] = _load(name)
    return out


def _on_block(doc: dict) -> dict:
    # PyYAML parses the bare `on:` key as boolean True.
    block = doc.get("on", doc.get(True, {}))
    return block if isinstance(block, dict) else {}


class TestSingleScheduledPipeline:
    def test_exactly_one_workflow_schedules_run_daily(self):
        owners = []
        for name, (doc, text) in _all_workflows().items():
            if "src.run_daily" in text and "schedule" in _on_block(doc):
                owners.append(name)
        assert owners == ["daily.yml"], (
            f"exactly one scheduled owner of src.run_daily allowed, got: {owners}"
        )

    def test_legacy_workflow_is_manual_only(self):
        doc, _ = _load("daily-job-bot.yml")
        on = _on_block(doc)
        assert "schedule" not in on
        assert "workflow_dispatch" in on

    def test_run_daily_workflows_share_one_queued_concurrency_group(self):
        groups = set()
        for name, (doc, text) in _all_workflows().items():
            if "src.run_daily" not in text:
                continue
            conc = doc.get("concurrency")
            assert isinstance(conc, dict), f"{name}: missing workflow-level concurrency"
            assert conc.get("cancel-in-progress") is False, (
                f"{name}: pipeline runs must queue, never cancel mid-run"
            )
            groups.add(conc.get("group"))
        assert groups == {"daily-job-bot"}, (
            f"all run_daily workflows must share ONE lock group, got: {groups}"
        )


class TestNoGeneratedContentOnMain:
    def test_no_workflow_pushes_to_main(self):
        offenders = []
        for name, (_, text) in _all_workflows().items():
            if re.search(r"git\s+push\s+(--\S+\s+)*origin\s+(HEAD:)?main\b", text):
                offenders.append(name)
        assert not offenders, f"workflows must never push to main: {offenders}"

    def test_dashboard_publishes_only_after_success_and_loudly(self):
        doc, text = _load("daily.yml")
        job = doc["jobs"]["deploy-dashboard"]
        assert job.get("needs") == "intelligence"
        assert job.get("if") == "success()"
        publish_snippets = [
            step.get("run", "") for step in job["steps"] if "git push" in step.get("run", "")
        ]
        assert publish_snippets, "dashboard publish step missing"
        for snippet in publish_snippets:
            assert "origin dashboard" in snippet
            assert "|| echo" not in snippet, "push failure must not be swallowed"
        assert "[skip ci]" not in text, "no skip-ci commits — nothing lands on main"


class TestDeployPathFilters:
    @pytest.mark.parametrize("name", ["deploy-render.yml", "deploy-production.yml"])
    def test_push_trigger_is_runtime_path_filtered(self, name):
        doc, _ = _load(name)
        push = _on_block(doc).get("push", {})
        paths = push.get("paths") or []
        assert "src/**" in paths, f"{name}: runtime paths filter required"
        joined = " ".join(paths)
        assert "docs" not in joined and "AI_WORKSPACE" not in joined, (
            f"{name}: docs/workspace paths must not trigger deploys"
        )


class TestApplyFlagsStayOff:
    def test_scheduled_pipeline_keeps_auto_apply_off(self):
        _, text = _load("daily.yml")
        assert 'RICO_ENABLE_AUTO_APPLY:   "false"' in text or \
               'RICO_ENABLE_AUTO_APPLY: "false"' in text
        assert 'NG_ENABLED:               "false"' in text or \
               'NG_ENABLED: "false"' in text
