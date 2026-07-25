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


_WORKFLOWS = pathlib.Path(".github/workflows")
_TRUSTED = _WORKFLOWS / "log-privacy-ratchet-trusted.yml"

# A minimal well-formed pull_request_target workflow: base-branch checkout with
# no ref, read-only token, dependency by name, and only repository-controlled
# event fields. Each case below breaks exactly one of those.
_SAFE_PR_TARGET = """\
name: fixture
on:
  pull_request_target:
permissions:
  contents: read
jobs:
  a:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - run: python -m pip install --quiet pytest
      - run: echo "${{ github.event.pull_request.head.sha }}"
"""


class TestPullRequestTargetContainment:
    """The containment properties of the privileged trigger, as executable rules.

    Each case constructs a workflow that breaks exactly one property and proves
    the checker rejects it, then the suite proves the repository's real files
    still pass. Without the negative case a rule could be quietly inert.
    """

    @pytest.fixture(autouse=True)
    def _yaml(self):
        pytest.importorskip("yaml")

    def _violations(self, text: str, tmp_path: pathlib.Path) -> list[str]:
        """Run the real entry point over a real file, not a hand-parsed dict."""
        from check_workflow_security import check_workflow

        wf = tmp_path / "fixture.yml"
        wf.write_text(text, encoding="utf-8")
        violations, _warnings = check_workflow(wf)
        return violations

    def test_the_safe_fixture_is_accepted(self, tmp_path):
        """Guards the cases below: they must fail for their own reason."""
        assert self._violations(_SAFE_PR_TARGET, tmp_path) == []

    # (a) permissions

    def test_missing_permissions_block_is_rejected(self, tmp_path):
        text = _SAFE_PR_TARGET.replace("permissions:\n  contents: read\n", "")
        assert any("without an explicit 'permissions:'" in v
                   for v in self._violations(text, tmp_path))

    def test_write_permission_is_rejected(self, tmp_path):
        text = _SAFE_PR_TARGET.replace(
            "permissions:\n  contents: read\n",
            "permissions:\n  contents: read\n  pull-requests: write\n",
        )
        assert any("nothing above read" in v
                   for v in self._violations(text, tmp_path))

    def test_write_all_shorthand_is_rejected(self, tmp_path):
        text = _SAFE_PR_TARGET.replace(
            "permissions:\n  contents: read\n", "permissions: write-all\n")
        assert any("nothing above read" in v
                   for v in self._violations(text, tmp_path))

    def test_a_job_level_write_scope_is_rejected(self, tmp_path):
        """Narrow at the top, widen inside the job — still a widening."""
        text = _SAFE_PR_TARGET.replace(
            "    runs-on: ubuntu-latest\n",
            "    runs-on: ubuntu-latest\n    permissions:\n      contents: write\n",
        )
        assert any("nothing above read" in v
                   for v in self._violations(text, tmp_path))

    # (b) checkout ref

    def test_checkout_with_a_ref_is_rejected(self, tmp_path):
        text = _SAFE_PR_TARGET.replace(
            "          fetch-depth: 0\n",
            "          ref: ${{ github.event.pull_request.head.sha }}\n"
            "          fetch-depth: 0\n",
        )
        assert any("takes no 'ref:'" in v
                   for v in self._violations(text, tmp_path))

    # (c) dependency installs

    def test_requirement_file_install_is_rejected(self, tmp_path):
        text = _SAFE_PR_TARGET.replace(
            "pip install --quiet pytest", "pip install --quiet -r requirements.txt")
        assert any("resolved by name" in v
                   for v in self._violations(text, tmp_path))

    def test_editable_local_install_is_rejected(self, tmp_path):
        text = _SAFE_PR_TARGET.replace(
            "pip install --quiet pytest", "pip install -e .")
        assert any("resolved by name" in v
                   for v in self._violations(text, tmp_path))

    def test_bare_local_path_install_is_rejected(self, tmp_path):
        text = _SAFE_PR_TARGET.replace(
            "pip install --quiet pytest", "pip install .")
        assert any("resolved by name" in v
                   for v in self._violations(text, tmp_path))

    # (d) secrets

    def test_secret_in_a_run_step_is_rejected(self, tmp_path):
        text = _SAFE_PR_TARGET.replace(
            'echo "${{ github.event.pull_request.head.sha }}"',
            'echo "${{ secrets.SOME_TOKEN }}"')
        assert any("references a secret" in v
                   for v in self._violations(text, tmp_path))

    def test_secret_smuggled_through_env_is_rejected(self, tmp_path):
        text = _SAFE_PR_TARGET.replace(
            "      - run: python -m pip install --quiet pytest\n",
            "      - run: python -m pip install --quiet pytest\n"
            "        env:\n          T: ${{ secrets.SOME_TOKEN }}\n",
        )
        assert any("references a secret" in v
                   for v in self._violations(text, tmp_path))

    # (e) author-controlled interpolation

    def test_branch_name_interpolation_is_rejected(self, tmp_path):
        """A fork branch name is free text and reaches the shell verbatim."""
        text = _SAFE_PR_TARGET.replace(
            "${{ github.event.pull_request.head.sha }}", "${{ github.head_ref }}")
        assert any("author controls" in v
                   for v in self._violations(text, tmp_path))

    def test_title_interpolation_is_rejected(self, tmp_path):
        text = _SAFE_PR_TARGET.replace(
            "${{ github.event.pull_request.head.sha }}",
            "${{ github.event.pull_request.title }}")
        assert any("author controls" in v
                   for v in self._violations(text, tmp_path))

    def test_fork_metadata_passed_to_an_action_is_rejected(self, tmp_path):
        text = _SAFE_PR_TARGET.replace(
            "          fetch-depth: 0\n",
            "          fetch-depth: 0\n"
            "          repository: ${{ github.event.pull_request.head.repo.full_name }}\n",
        )
        assert any("author controls" in v
                   for v in self._violations(text, tmp_path))

    def test_repository_controlled_fields_are_allowed(self, tmp_path):
        """No false positive on the fields a trusted job legitimately reads."""
        text = _SAFE_PR_TARGET.replace(
            'echo "${{ github.event.pull_request.head.sha }}"',
            'echo "${{ github.event.pull_request.number }} '
            '${{ github.event.pull_request.base.ref }} '
            '${{ github.event.pull_request.head.sha }}"',
        )
        assert self._violations(text, tmp_path) == []

    # scoping

    def test_an_ordinary_pull_request_workflow_is_untouched(self, tmp_path):
        """These rules must not leak onto the unprivileged trigger."""
        text = _SAFE_PR_TARGET.replace(
            "  pull_request_target:\n", "  pull_request:\n"
        ).replace("permissions:\n  contents: read\n", "")
        text = text.replace(
            "pip install --quiet pytest", "pip install -r requirements.txt")
        assert self._violations(text, tmp_path) == []

    def test_a_comment_mentioning_the_trigger_is_not_swept_in(self, tmp_path):
        """Detection reads the parsed on: block, never the raw text.

        The advisory ratchet workflow explains pull_request_target at length in
        its header while running on the ordinary trigger. A substring match
        would fail it for its documentation.
        """
        text = "# pull_request_target is explained here but not used\n" + (
            _SAFE_PR_TARGET
            .replace("  pull_request_target:\n", "  pull_request:\n")
            .replace("permissions:\n  contents: read\n", "")
        )
        assert self._violations(text, tmp_path) == []


class TestTheShippedTrustedWorkflowIsHeldByTheseRules:
    """Mutation proofs against the real file, not only fixtures.

    A rule that passes a fixture but does not actually bind the workflow it was
    written for is decorative. Each case removes one property from the shipped
    file and proves CI would now object.
    """

    @pytest.fixture(autouse=True)
    def _yaml(self):
        pytest.importorskip("yaml")

    @pytest.fixture
    def shipped(self) -> str:
        if not _TRUSTED.is_file():
            pytest.skip("trusted workflow not present in this tree")
        return _TRUSTED.read_text(encoding="utf-8")

    def _violations(self, text: str, tmp_path: pathlib.Path) -> list[str]:
        from check_workflow_security import check_workflow

        wf = tmp_path / "mutated.yml"
        wf.write_text(text, encoding="utf-8")
        violations, _warnings = check_workflow(wf)
        return violations

    def test_it_passes_as_shipped(self, shipped, tmp_path):
        assert self._violations(shipped, tmp_path) == []

    def test_removing_the_permissions_block_fails_it(self, shipped, tmp_path):
        mutated = shipped.replace("permissions:\n  contents: read\n", "", 1)
        assert mutated != shipped
        assert any("without an explicit 'permissions:'" in v
                   for v in self._violations(mutated, tmp_path))

    def test_widening_the_token_fails_it(self, shipped, tmp_path):
        mutated = shipped.replace(
            "permissions:\n  contents: read\n",
            "permissions:\n  contents: write\n", 1)
        assert mutated != shipped
        assert any("nothing above read" in v
                   for v in self._violations(mutated, tmp_path))

    def test_checking_out_the_head_fails_it(self, shipped, tmp_path):
        mutated = shipped.replace(
            "          fetch-depth: 0\n",
            "          ref: ${{ github.event.pull_request.head.sha }}\n"
            "          fetch-depth: 0\n", 1)
        assert mutated != shipped
        assert any("takes no 'ref:'" in v
                   for v in self._violations(mutated, tmp_path))

    def test_installing_from_a_requirement_file_fails_it(self, shipped, tmp_path):
        mutated = shipped.replace(
            "python -m pip install --quiet pytest",
            "python -m pip install --quiet -r requirements.txt", 1)
        assert mutated != shipped
        assert any("resolved by name" in v
                   for v in self._violations(mutated, tmp_path))

    def test_exposing_a_secret_fails_it(self, shipped, tmp_path):
        mutated = shipped.replace(
            "        run: python -m pip install --quiet pytest",
            "        run: python -m pip install --quiet pytest\n"
            "        env:\n          T: ${{ secrets.SOME_TOKEN }}", 1)
        assert mutated != shipped
        assert any("references a secret" in v
                   for v in self._violations(mutated, tmp_path))

    def test_interpolating_the_branch_name_fails_it(self, shipped, tmp_path):
        mutated = shipped.replace(
            "${{ github.event.pull_request.base.ref }}",
            "${{ github.head_ref }}", 1)
        assert mutated != shipped
        assert any("author controls" in v
                   for v in self._violations(mutated, tmp_path))
