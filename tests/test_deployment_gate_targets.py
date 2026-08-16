"""
tests/test_deployment_gate_targets.py

The deployment gate: no workflow that runs automatically on a push to `main`
may assert against infrastructure that no longer serves production.

Why this file exists. The canonical backend moved to Railway (service
`rico-api`, https://api.ricohunt.com), but two workflows kept targeting the
retired Render host:

  * `deploy-render.yml` POSTed the Render deploy hook  -> HTTP 409
  * `deploy-production.yml` health-checked the Render URL -> HTTP 503

Both ran on every `src/**` push. Both failed. GitHub therefore concluded the
commit's aggregate check suite had FAILED, and Railway's "Wait for CI" gate
skipped the deployment with "CI check suite failed" — so `main` moved on while
production stayed pinned to `ccde2c48`. Merge commit `41a95ad` (Phase 1
grounding) never shipped for this reason.

The lesson these tests encode: **a verification workflow pointed at dead
infrastructure does not merely report a false red — through aggregate CI gating
it stops the real host from ever deploying.** A stale health check is an outage.

Scope note. `keep-warm.yml` was re-pointed at the canonical Railway host
(`https://api.ricohunt.com/health`, final-hardening review) and no longer
references Render. `render-audit.yml` still references the Render host and is
deliberately left alone: it does not run on push-to-main, so it cannot poison a
commit's check suite. These tests pin exactly that distinction, so the cleanup
can happen later without anyone having to re-derive which references were
load-bearing.

Static analysis of workflow YAML only — no network, no database, no provider.
"""
from __future__ import annotations

import pathlib

import pytest

yaml = pytest.importorskip("yaml")

WORKFLOWS = pathlib.Path(__file__).resolve().parents[1] / ".github" / "workflows"

#: The retired Render host. Nothing that gates a push to main may assert on it.
RETIRED_BACKEND_HOST = "rico-job-automation-api.onrender.com"

#: The canonical production backend, verified from the Railway console
#: 2026-07-30 (service `rico-api`, custom domain Active/Verified, /health 200
#: with `Server: railway-hikari`).
CANONICAL_API_BASE = "https://api.ricohunt.com"

#: Still reference the retired host, deliberately, because it does not run on
#: push-to-main and so cannot fail a commit's check suite. Tracked for
#: separate cleanup. A workflow may only sit here while it stays off that
#: trigger — `test_allowlisted_render_workflows_never_run_on_push_to_main`
#: enforces that, so the allowlist cannot quietly become a loophole.
NON_BLOCKING_RENDER_WORKFLOWS = {"render-audit.yml"}


def _load(path: pathlib.Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _triggers(doc: dict) -> dict:
    # PyYAML parses the bare `on:` key as the boolean True.
    raw = doc.get("on", doc.get(True)) or {}
    return raw if isinstance(raw, dict) else {}


def _runs_on_push_to_main(doc: dict) -> bool:
    push = _triggers(doc).get("push")
    if not isinstance(push, dict):
        return False
    return "main" in (push.get("branches") or [])


def _push_to_main_workflows() -> list[pathlib.Path]:
    return [p for p in sorted(WORKFLOWS.glob("*.yml")) if _runs_on_push_to_main(_load(p))]


# ── The gate ─────────────────────────────────────────────────────────────────

class TestNoPushToMainWorkflowTargetsRetiredInfrastructure:
    def test_no_push_to_main_workflow_references_the_retired_backend(self):
        """The load-bearing assertion. Any workflow gating a main push that
        touches the retired host will fail, fail the suite, and block Railway."""
        offenders = [
            p.name for p in _push_to_main_workflows()
            if RETIRED_BACKEND_HOST in p.read_text(encoding="utf-8")
        ]
        assert offenders == [], (
            f"{offenders} run on push to main and reference {RETIRED_BACKEND_HOST}, "
            "which no longer serves production. They will fail, fail the commit's "
            "check suite, and Railway will skip the deployment."
        )

    def test_the_render_deploy_hook_workflow_is_retired(self):
        """`deploy-render.yml` POSTed a hook to a service that returns 409. It
        deployed nothing and blocked everything; Railway auto-deploys from
        GitHub and needs no hook."""
        assert not (WORKFLOWS / "deploy-render.yml").exists()

    def test_no_workflow_posts_a_render_deploy_hook(self):
        """Belt and braces: catches the hook being re-added under any filename."""
        offenders = [
            p.name for p in WORKFLOWS.glob("*.yml")
            if "RENDER_DEPLOY_HOOK_URL" in p.read_text(encoding="utf-8")
        ]
        assert offenders == [], f"{offenders} still POST the retired Render deploy hook"

    def test_allowlisted_render_workflows_never_run_on_push_to_main(self):
        """The allowlist is not a loophole: a file may keep its Render
        reference only while it cannot gate a main push."""
        for name in NON_BLOCKING_RENDER_WORKFLOWS:
            path = WORKFLOWS / name
            if not path.exists():
                continue  # already cleaned up elsewhere — fine
            assert not _runs_on_push_to_main(_load(path)), (
                f"{name} references the retired host AND now runs on push to main. "
                "It must be repointed or removed from NON_BLOCKING_RENDER_WORKFLOWS."
            )

    def test_allowlist_contains_only_files_that_actually_reference_render(self):
        """Keeps the allowlist honest — a stale entry would silently permit a
        future workflow of the same name."""
        for name in NON_BLOCKING_RENDER_WORKFLOWS:
            path = WORKFLOWS / name
            if path.exists():
                assert RETIRED_BACKEND_HOST in path.read_text(encoding="utf-8"), (
                    f"{name} no longer references the retired host — drop it from "
                    "NON_BLOCKING_RENDER_WORKFLOWS."
                )


# ── The replacement verification ─────────────────────────────────────────────

class TestProductionVerificationTargetsTheCanonicalBackend:
    def _deploy_production(self) -> tuple[dict, str]:
        path = WORKFLOWS / "deploy-production.yml"
        return _load(path), path.read_text(encoding="utf-8")

    def test_it_targets_the_canonical_api_base(self):
        doc, raw = self._deploy_production()
        assert doc["env"]["API_BASE"] == CANONICAL_API_BASE
        assert RETIRED_BACKEND_HOST not in raw

    def test_it_still_runs_on_push_to_main(self):
        """Repointing must not quietly disable production verification."""
        doc, _ = self._deploy_production()
        assert _runs_on_push_to_main(doc)

    def test_it_asserts_health_version_and_proxy(self):
        doc, _ = self._deploy_production()
        steps = doc["jobs"]["deploy"]["steps"]
        blob = "\n".join(s.get("run", "") for s in steps)
        assert "$API_BASE/health" in blob
        assert "$API_BASE/version" in blob
        assert "$FRONTEND_BASE/proxy/health" in blob

    def test_every_check_is_fail_closed(self):
        """A real production failure must still fail the workflow. Each check
        compares to 200 and exits 1 otherwise; an unreachable host degrades to
        "000", which is also not 200."""
        doc, _ = self._deploy_production()
        checks = [
            s for s in doc["jobs"]["deploy"]["steps"]
            if "%{http_code}" in s.get("run", "")
        ]
        assert len(checks) == 4, "expected health, version, frontend and proxy checks"
        for step in checks:
            run = step["run"]
            assert '!= "200"' in run, f'{step["name"]!r} does not require HTTP 200'
            assert "exit 1" in run, f'{step["name"]!r} does not fail closed'
            assert 'echo "000"' in run, (
                f'{step["name"]!r} does not force a non-200 when curl cannot reach '
                "the host — an unreachable backend would otherwise read as success"
            )

    def test_the_deployed_commit_is_surfaced(self):
        """Deployment evidence that does not name a commit is not evidence.
        Production sat on ccde2c48 while main moved on precisely because
        nothing compared the two."""
        doc, _ = self._deploy_production()
        blob = "\n".join(s.get("run", "") for s in doc["jobs"]["deploy"]["steps"])
        assert "Deployed commit" in blob
        assert "GITHUB_SHA" in blob

    def test_docs_only_commits_still_do_not_trigger_it(self):
        """The #1086 path filter is preserved: a docs/workspace-only commit
        must not run production verification or contaminate deploy evidence."""
        doc, _ = self._deploy_production()
        paths = _triggers(doc)["push"]["paths"]
        assert "src/**" in paths
        assert "apps/web/**" in paths
        assert "migrations/**" in paths
        for docs_path in ("AI_WORKSPACE/**", "docs/**", "**.md", "*.md"):
            assert docs_path not in paths, (
                f"{docs_path} would make docs-only commits run production verification"
            )
