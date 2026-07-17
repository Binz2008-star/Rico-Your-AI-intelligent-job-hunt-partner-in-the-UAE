"""#1084 — CI security containment for the Render workflows.

Two guard layers are under test:

* ``scripts/render_cleanup_guard.py`` — the fail-closed allowlist validator
  the mutation workflow runs before (and again immediately before) deleting
  anything. The issue's key acceptance point: a renamed production service can
  never become a deletion target — the guard must refuse the ENTIRE run when
  production cannot be identified by its canonical name.
* ``scripts/check_workflow_security.py`` — static guards over the workflow
  files themselves (secret-like dispatch inputs, mutable action refs,
  privileged workflows without permissions, unprotected destructive jobs).

No network, no Render, no secrets — pure fixture data plus the real workflow
files in the repository.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

from render_cleanup_guard import (  # noqa: E402
    GuardError,
    PRODUCTION_SERVICE_NAME,
    parse_service_list,
    validate,
)

PROD = ("srv-prod111", PRODUCTION_SERVICE_NAME)
OLD_A = ("srv-olda222", "rico-legacy-worker")
OLD_B = ("srv-oldb333", "rico-old-preview")


def _services(*pairs):
    return list(pairs)


class TestCleanupGuard:
    def test_happy_path_validates_explicit_allowlist(self):
        targets, preview = validate(
            _services(PROD, OLD_A, OLD_B),
            "srv-olda222, srv-oldb333",
            "srv-olda222, srv-oldb333",
        )
        assert targets == ["srv-olda222", "srv-oldb333"]
        assert preview == [
            "srv-olda222 | rico-legacy-worker",
            "srv-oldb333 | rico-old-preview",
        ]

    def test_renamed_production_refuses_everything(self):
        """THE acceptance case: production renamed → the guard cannot anchor
        the protected service, so NO deletion set is ever authorized."""
        renamed = ("srv-prod111", "rico-job-automation-api-v2")
        with pytest.raises(GuardError) as exc:
            validate(
                _services(renamed, OLD_A),
                "srv-olda222",
                "srv-olda222",
            )
        assert exc.value.code == "production_service_not_found"

    def test_missing_production_refuses_everything(self):
        with pytest.raises(GuardError) as exc:
            validate(_services(OLD_A, OLD_B), "srv-olda222", "srv-olda222")
        assert exc.value.code == "production_service_not_found"

    def test_production_id_can_never_be_a_target(self):
        with pytest.raises(GuardError) as exc:
            validate(
                _services(PROD, OLD_A),
                "srv-prod111, srv-olda222",
                "srv-prod111, srv-olda222",
            )
        assert exc.value.code == "production_service_targeted"

    def test_stale_or_unknown_target_refuses_whole_set(self):
        with pytest.raises(GuardError) as exc:
            validate(
                _services(PROD, OLD_A),
                "srv-olda222, srv-gone9999",
                "srv-olda222, srv-gone9999",
            )
        assert exc.value.code == "unknown_target"

    def test_confirmation_must_repeat_exact_target_set(self):
        with pytest.raises(GuardError) as exc:
            validate(_services(PROD, OLD_A), "srv-olda222", "yes")
        assert exc.value.code == "confirmation_mismatch"

    def test_confirmation_with_different_order_is_rejected(self):
        with pytest.raises(GuardError) as exc:
            validate(
                _services(PROD, OLD_A, OLD_B),
                "srv-olda222, srv-oldb333",
                "srv-oldb333, srv-olda222",
            )
        assert exc.value.code == "confirmation_mismatch"

    def test_empty_target_set_is_refused(self):
        with pytest.raises(GuardError) as exc:
            validate(_services(PROD, OLD_A), "  ", "  ")
        assert exc.value.code == "empty_target_set"

    def test_malformed_service_id_is_refused(self):
        with pytest.raises(GuardError) as exc:
            validate(
                _services(PROD, OLD_A),
                "rico-legacy-worker",
                "rico-legacy-worker",
            )
        assert exc.value.code == "invalid_service_id"

    def test_duplicate_targets_are_refused(self):
        with pytest.raises(GuardError) as exc:
            validate(
                _services(PROD, OLD_A),
                "srv-olda222, srv-olda222",
                "srv-olda222, srv-olda222",
            )
        assert exc.value.code == "duplicate_target"

    def test_parse_service_list_handles_render_envelope(self):
        data = [{"service": {"id": "srv-x1", "name": "a"}}, {"id": "srv-x2", "name": "b"}]
        assert parse_service_list(data) == [("srv-x1", "a"), ("srv-x2", "b")]


class TestStaticWorkflowGuards:
    """Static guards — run against fixtures AND the real repository files."""

    @pytest.fixture(autouse=True)
    def _yaml(self):
        pytest.importorskip("yaml")

    def _check_text(self, text: str):
        import yaml

        from check_workflow_security import (
            check_action_refs,
            check_privileged,
            check_secret_like_inputs,
        )

        doc = yaml.safe_load(text)
        if True in doc and "on" not in doc:
            doc["on"] = doc.pop(True)
        return (
            check_secret_like_inputs(doc, "fixture.yml")
            + check_action_refs(doc, "fixture.yml")
            + check_privileged(doc, text, "fixture.yml")
        )

    def test_secret_like_dispatch_input_is_rejected(self):
        text = (
            "on:\n  workflow_dispatch:\n    inputs:\n      render_api_key:\n"
            "        description: x\njobs:\n  a:\n    runs-on: ubuntu-latest\n"
            "    steps: []\n"
        )
        violations = self._check_text(text)
        assert any("secret-like" in v for v in violations)

    def test_mutable_branch_action_ref_is_rejected(self):
        text = (
            "on: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n    steps:\n"
            "      - uses: actions/checkout@main\n"
        )
        violations = self._check_text(text)
        assert any("mutable action ref" in v for v in violations)

    def test_privileged_workflow_without_permissions_is_rejected(self):
        text = (
            "on: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n    steps:\n"
            "      - run: curl -H \"Authorization Bearer $RENDER_API_KEY\" https://api.render.com/v1/services\n"
        )
        violations = self._check_text(text)
        assert any("permissions" in v for v in violations)

    def test_destructive_job_without_environment_is_rejected(self):
        text = (
            "on:\n  workflow_dispatch:\n    inputs:\n      dry_run:\n"
            "        default: 'true'\npermissions:\n  contents: read\n"
            "jobs:\n  a:\n    runs-on: ubuntu-latest\n    steps:\n"
            "      - run: curl -X DELETE https://api.render.com/v1/services/x\n"
        )
        violations = self._check_text(text)
        assert any("environment" in v for v in violations)

    def test_destructive_workflow_must_default_dry_run_true(self):
        text = (
            "on:\n  workflow_dispatch:\n    inputs:\n      dry_run:\n"
            "        default: 'false'\npermissions:\n  contents: read\n"
            "jobs:\n  a:\n    runs-on: ubuntu-latest\n    environment: production\n"
            "    steps:\n"
            "      - run: curl -X DELETE https://api.render.com/v1/services/x\n"
        )
        violations = self._check_text(text)
        assert any("dry_run" in v for v in violations)

    def test_repository_workflows_pass_all_guards(self):
        """Acceptance evidence: the repo contains no credential-valued dispatch
        input, no mutable action ref, and no unprotected privileged job."""
        from check_workflow_security import check_workflow

        workflows = sorted(pathlib.Path(".github/workflows").glob("*.yml"))
        assert workflows, "expected workflow files in the repository"
        all_violations = []
        for wf in workflows:
            violations, _warnings = check_workflow(wf)
            all_violations += violations
        assert all_violations == []
