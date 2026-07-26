# 2026-07-21 — System audit: designed-but-unwired tools, import breakage, test rot

Owner request: "analyze the system for errors, tools that were designed but never
executed, and anything unusual; fix what is needed."

Authority role: WRITER (branch `claude/system-tools-analysis-wc4o4g`).
Activity passes: Planner → Reviewer → Coder → Tester.
Base: `main` @ `48e932e`.

## Method

- Import-scan of every module under `src/` (importlib walk).
- Tool inventory: `src/agent/registry/tool_registry.py` vs actual callables vs
  `ACTION_TO_TOOL` in `src/agent/orchestrator/intent_detector.py`.
- Focused pytest run (CLAUDE.md focused set) + flake bisection.
- CI coverage reconciliation against `.github/workflows/qa-tests.yml`.
- Production reachability check: `src.api.app`, `src.services.chat_service`,
  `src.rico_chat_api` all import cleanly — none of the findings below affect
  the deployed request path.

## Findings

### F1 — Stateful-agent stack is dead code that cannot even import (NOT fixed here; owner decision)

These modules fail at import time on `main` (verified by import-scan):

| Module | Missing symbol it imports |
|---|---|
| `src/agent/identity/resolver.py` | `audit_repo.log_identity_resolution` / `log_identity_merge` / `log_identity_link` (never implemented) |
| `src/agent/identity/__init__.py` | transitively broken |
| `src/agent/workflow/coordinator.py` | `learning_repo.infer_signals_from_job_action` (exists only as a method of `LearningRepository`, not a module function) |
| `src/agent/workflow/__init__.py` | transitively broken |
| `src/agent/coordinator.py` | `learning_repo.record_learning_signal` (never implemented) + transitive |
| `src/services/stateful_chat_adapter.py` | transitive |

Additional latent bug in the same stack: `WorkflowResult` (workflow/coordinator.py)
has no `confirmation_token` field, yet `_request_confirmation()` passes
`confirmation_token=` to its constructor and `src/agent/coordinator.py:171`
reads `workflow_result.confirmation_token` — the confirmation flow would raise
`TypeError` even if the imports were repaired.

Reachability: nothing in the production app imports this stack. Its only
consumers are each other and docs (`docs/STATEFUL_AGENT_ARCHITECTURE.md`,
`docs/DEEP_ARCHITECTURE_ANALYSIS.md`).

`AI_WORKSPACE/RICO_CODEBASE_INVENTORY_2026_06_21.md` already classifies this
stack as a duplicate of the canonical `agent_runtime` path ("That path should
not be extended… retire duplicate confirmation/action execution"). Implementing
the five missing repo functions would be feature work on code marked for
retirement; deleting it is destructive and owner-gated.

**Recommendation:** owner-approved removal PR for
`src/agent/identity/`, `src/agent/workflow/`, `src/agent/coordinator.py`,
`src/services/stateful_chat_adapter.py` (+ update the two docs). Until then
this handoff is the record that the stack is non-functional.

### F2 — Legacy scripts in `src/` that cannot import (NOT fixed; same removal decision)

- `src/linkedin_demo.py` → `ModuleNotFoundError: linkedin_integration`
- `src/test_refactored_system.py` → imports `FeedbackLoopSystem` which
  `src/feedback_loop.py` does not define

Both are demo/manual scripts, unreachable from production. Candidates for the
same cleanup PR.

### F3 — Thread-unsafe mock patching leaked a MagicMock across the whole pytest session (FIXED)

`tests/test_jotform_webhook.py::test_concurrent_duplicate_delivery_only_one_processed`
applied `patch("src.repositories.onboarding_repo.mark_onboarding_complete")`
(and the RicoDB / os.environ patches) **inside each of two worker threads**.
`unittest.mock.patch` is not thread-safe: with the right interleaving, thread B
saves thread A's MagicMock as the "original" and restores it on exit, leaving
the module's `mark_onboarding_complete` permanently mocked for the rest of the
session. Observed effect: `tests/test_onboarding_state.py::TestOnboardingRepo::
test_mark_complete_calls_set_with_completed` failed ~1 in 3 multi-file runs
("Called 0 times") while always passing alone.

Fix (global, deterministic): apply all patches once from the main thread around
both worker threads. Verified: 5 consecutive runs of the 5-file focused set,
228/228 passing each time.

### F4 — Stale tests asserting pre-#354 behavior, invisible because CI never runs them (FIXED)

`tests/test_agent.py::TestApplyServiceIndeedMethod` — 3 tests asserted that
`apply_to_job` follows legacy URL keys (`apply_link`, nested
`job_data.job_apply_link`, `alt_link`) with **no provenance**. Since the Phase-0
trust gate (#354, `src/services/job_link_trust.py`), such records are correctly
rejected ("Job is missing a link") — the tests failed, but nobody saw it
because `.github/workflows/qa-tests.yml` runs a curated list that does NOT
include `tests/test_agent.py` (nor `test_agent_runtime.py`,
`test_jotform_webhook.py`, `test_onboarding_state.py`, …).

Fix: the 3 tests now pin the *current* contract — trusted
(`external_url`/`alt_url` + `source_job_id`) URLs reach the engine / manual
message; untrusted legacy-key records are rejected before any engine runs and
the engine is asserted NOT called. The smoke-exposed behavior is product
behavior; the fix is global and synthetic-data only.

**Recommendation (separate decision):** add the focused CLAUDE.md test set to
`qa-tests.yml` now that it is green and deterministic — small CI-only PR.

### F5 — Verified healthy (no action)

- All 12 registered tools in `tool_registry` resolve to real implementations;
  `ACTION_TO_TOOL` and `VALID_ACTION_TYPES` are consistent; `trigger_pipeline`
  correctly remains the only `PRIVILEGED_TOOLS` entry.
- Production import path clean; `qa-tests.yml` pytest/postgres/playwright/
  frontend gates green on recent `main` pushes; latest `main` deploy workflows
  green (two older `Deploy Render Backend` failures at `95362b4`/`9a55439` were
  superseded by the green `853ea01` run).

## Scope / generalization statement

Affected scope: all users (test-infrastructure truth + dead-code inventory);
no live-account special-casing; synthetic data only; no production mutation,
no migration, no env change, no deploy required. Runtime behavior is unchanged
— the PR is test-only plus this document.

## Rollback

Revert the PR. No deploy or migration involved.

## Next exact action

1. Owner review + merge of the test-repair PR (branch above).
2. Owner decision on F1/F2 removal PR and on adding the focused test set to CI (F4).

---

# Control dashboard — 2026-07-25 (evening) — **SUPERSEDED**

> **SUPERSEDED as of 2026-07-26 (late). Do not read the dashboard below as current state.**
>
> It is preserved as a dated record of what was true that evening. Live control
> state is `AI_WORKSPACE/PROJECT_STATUS.md`, reconciled onto `main@97af6ded`.
>
> Specifically stale below, verified line by line at the superseding pass:
>
> - **"`main` is `fc2e107d`"** — `main` is now `97af6ded`; five further merges have landed (`#1402`, `#1398`, `#1404`, and `#1399`/`#1400` already listed).
> - **L1 `HELD`/`WRITING` on `#1398`** — `#1398` merged as `70c2af7c`; the lane is `RELEASED`/`IDLE`. Its follow-up `#1404` merged as `97af6ded`.
> - **L7 `HELD`/`WRITING` on `#1402`** — `#1402` merged as `805dd4d6`; that lease is released.
> - **L2 "sequenced behind `#1398`"** — that hold has cleared; `#1389`'s base `70c2af7c` is now the stale part.
> - **The concurrency counts** ("3 of 4 active") describe leases that no longer exist.
>
> The identity work is **not** finished despite the merges — see `PROJECT_STATUS.md`
> → "Open production-integrity item", and the OPEN CI gap that `#1406` closes.

Appended to the latest dated handoff rather than opened as a new file, so the
control plane keeps one place to look.

**Read the evidence class before relying on any line below.** Repository state —
`main`, PR heads, merge commits, CI conclusions — was fetched live from the
GitHub API when this was written. Live production state was **not**: the
production host is unreachable from the reconciling container, so nothing here
asserts what is deployed, healthy, or smoke-passing at this pass. API-verified
and production-verified are different claims and are never merged into one.

Lanes are referred to by alias only. This repository is public: no session
identifiers, no session or browser links, no personal data, and no per-account
detail appear here.

## Lane state

Read as of the 2026-07-26 reconciliation. **Lease holder is ownership; activity is
what is happening now; write authorization is what a push may rely on.** Counts
against the caps are derived from activity, never from lease possession.

| Lane | Objective | Lease holder | Ownership | Activity | Write auth | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `L1` | Identity ownership | `L1` | `HELD` | `WRITING` | `AUTHORIZED` | `#1398`, next integrity merge. Local work not yet on the remote |
| `L2` | CV and documents | `L2` | `HELD` | `HOLDING` | read at resumption | `#1389`, sequenced behind `#1398`. Sole writer after a two-writer collision |
| `L3` | Routing | none | `RELEASED` | `IDLE` | — | Closed and merged in a **prior** cycle at `e433c7d`; its deploy was verified then, and that verification is not restated as current |
| `L4` | Workflow-trigger containment | none | `RELEASED` | `IDLE` | — | `#1400` merged as `03450277`. No runtime path touched, so no deploy expected |
| `L5` | Documents domain contract | none | `RELEASED` | `IDLE` | — | `#1399` merged as `fc2e107d`. Five runtime paths touched, so a deploy **is** expected. Branch deleted on merge |
| `L6` | Review | none | `RELEASED` | `REVIEWING` | — | Read-only. Holds no lease and pushes nothing |
| `L7` | Control plane | `L7` | `HELD` | `WRITING` | `AUTHORIZED` | `#1402`, docs-only, five files. Its predecessor `#1401` is closed unmerged with the branch preserved |

**Against the caps:** active agents 3 of 4 (L1, L6, L7); simultaneous code writers 1 of 2 (L1 only — L7 is docs-only and does not count); writers per branch 1 of 1 wherever a lease is held.

## Control facts

Each line carries its evidence class. A line without live evidence says so
rather than inheriting confidence from the lines around it.

- **`main` is `fc2e107d`.** *API-verified at this pass.*
- **Deployed backend `/version`: not verified at this pass.** The production host
  is unreachable from the reconciling container, so parity between `main` and the
  deployment is **neither asserted nor denied**. Before this cycle the two agreed
  at `e433c7d`. Confirmation is owner-side.
- **Backend health and provider status: not verified at this pass.** No health or
  provider claim is made here. The last such reading predates this cycle and is
  not restated as current.
- **Production smoke: not run at this pass.** The prior baseline on `e433c7d`
  passed three of three classes — an ownership-qualified account question
  answered from the database with reconciled counts; a CV file-list question
  answered deterministically from the file store; and a general documents
  question answered by the model without listing any personal file.
  **Evidence class: owner-verified in a browser session through the proxy, with
  no automated artifact.** It is real evidence of live behaviour, it is not a
  regression gate, and **it predates `#1399` and does not cover it.**
- **Two merges this cycle, with different deploy expectations.** `#1400` touches
  no runtime path, so no deploy was expected and its absence is correct. `#1399`
  changes five runtime paths under `src/`, so a backend deploy **is expected** —
  expected, not confirmed. Whether it has landed is unverified here.

`main` moving ahead of the deployed `/version` after a non-runtime merge is
expected divergence, not deployment drift. Do not chase parity, and do not fire a
deploy to manufacture it.

## What this reconciliation corrected

A control plane that hides its own corrections cannot be trusted, so the drift is
recorded rather than quietly overwritten:

- One lane carried a branch name without its actual suffix.
- The same lane carried an expected head that is not the branch tip; a lease check
  against it would have compared the wrong commit and reported agreement that did
  not exist.
- One lane carried no PR number at all.

Each is now the live value.

## Standing rule that came out of this cycle

Two sessions wrote to one branch concurrently. Nothing was lost — the collision
was resolved by merge — but the outcome was luck, not design. The **Writer Lease
Protocol** in `AI_WORKSPACE/OPERATING_RULES.md` is the mechanism that replaces the
bare instruction: one `WRITING` lease per branch, verified against the remote
before every push, and an unexpected commit means stop and report rather than
overwrite.

## Next action

Per lane: read the continuity block in `AI_WORKSPACE/TASKS.md`, confirm the lease
is yours, fetch the remote, and compare the remote head against the expected head
before any push. No merge and no deploy is authorized by this handoff.
