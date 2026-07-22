---
name: rico-development-supervisor
description: Controlled single-task development loop for Rico. Run one bounded OBSERVE → DECIDE → ACT → VERIFY → RECORD → STOP cycle against live repository state. Use when asked to run the development supervisor, pick up the next safe task, or advance the development loop. Never merges, never deploys, never mutates production.
---

# rico-development-supervisor

A controlled development-loop contract for this repository. This is NOT an
infinite autonomous agent. It never modifies Rico runtime behavior on its own
authority, never merges, and never touches production. One invocation performs
at most ONE implementation task and then stops.

Canonical companion files:

- `AI_WORKSPACE/DEVELOPMENT_LOOP_STATE.md` — machine-readable session ledger.
- `scripts/rico-development-loop.sh` — bounded non-interactive launcher.
- `tests/test_development_supervisor_contract.py` — static contract guard.

This skill layers ON TOP of the existing workspace control plane. It does not
replace `AI_WORKSPACE/OPERATING_RULES.md` or `AI_WORKSPACE/DAILY_AUTOPILOT.md`;
where they are stricter, they win.

## Hard bounds (read first)

- A single invocation may complete **at most ONE implementation task**.
- A single invocation may perform **at most THREE observe/verify correction
  cycles** for that same task. On the third failed cycle, stop with
  `RICO_SUPERVISOR_RESULT: INCOMPLETE_EVIDENCE`.
- The supervisor must not silently select a second implementation objective.
  If the chosen task turns out to be unsafe or blocked, it stops and reports;
  it does not swap tasks mid-invocation.
- Never invent work merely to stay active. No safe task means `IDLE`.
- No broad rewrites. No unrelated cleanup. No multi-agent fan-out.
- No production-specific or user-specific fixes (Product Generalization Rule
  in `CLAUDE.md` / `OPERATING_RULES.md` applies in full).
- Never trust chat memory over repository files and live GitHub state.
- The supervisor must never write code and independently authorize its own
  merge. A WRITER stops with a Draft PR and an evidence report. Merge,
  deploy, and production mutation are owner decisions, always.

## Stage: OBSERVE

1. Fetch latest `main` (`git fetch origin main`) and record its exact SHA.
2. Read, in the canonical order: `AI_WORKSPACE/START_HERE.md`, `CLAUDE.md`,
   `AI_WORKSPACE/CURRENT_STATE.md`, the active Continuity Block in
   `AI_WORKSPACE/TASKS.md`, `AI_WORKSPACE/OPERATING_RULES.md`, the latest
   referenced handoff, and `AI_WORKSPACE/DEVELOPMENT_LOOP_STATE.md`.
3. Inspect all open PRs: owner, head branch, head SHA, draft state,
   mergeability, live CI state, and **changed-file overlap** with any
   candidate task. Overlap inspection means reading each open PR's changed
   FILE LIST (not just titles) for collisions with the candidate task's
   "files allowed" — including shared control-plane files such as
   `AI_WORKSPACE/TASKS.md` — and for Task-ID collisions. Inspect stale
   branches and known workspace conflicts.
4. Build the occupancy picture: which branches/objectives are owned, which
   are frozen/held, which are do-not-resume.
5. If live GitHub state and workspace documents disagree, execution STOPS
   here: declare `REVIEWER` or `IDLE`, report the conflict, and finish with
   `RICO_SUPERVISOR_RESULT: BLOCKED_CONFLICT`. Conflicting workspace/live
   state is never resolved by guessing and never worked around.

## Stage: DECIDE

1. Select **exactly one** highest-priority safe task using the selection
   order in `AI_WORKSPACE/DAILY_AUTOPILOT.md`.
2. Declare exactly one authority role: `WRITER`, `REVIEWER`, `RELEASE`, or
   `IDLE`.
   - `WRITER` — only session allowed to push to its claimed branch; ends at
     a Draft PR plus evidence report, never at a merge.
   - `REVIEWER` — read-only evidence; never edits the writer branch.
   - `RELEASE` — acts only after explicit owner approval already recorded;
     verification only, no code.
   - `IDLE` — no safe task exists. IDLE creates no branch and modifies no
     files; it reports one concrete owner decision and stops with
     `RICO_SUPERVISOR_RESULT: IDLE`.
3. Before any edit, record the claim (in the task's Continuity Block in
   `AI_WORKSPACE/TASKS.md`): objective, authority role, activity pass,
   branch, base SHA, **acceptance criteria**, **files allowed**,
   **files forbidden**, **required tests**, overlaps checked, and
   **stop condition**.
4. A new task takes the next FREE `TASK-YYYYMMDD-NNN` identifier. Task-ID
   reuse is forbidden: check `AI_WORKSPACE/TASKS.md` on the CURRENT fetched
   `origin/main` AND every open PR that touches `TASKS.md` before claiming a
   number. The static guard rejects duplicate Task IDs.
5. If any hard owner gate (below) would be required to complete the task,
   the task is not safe: stop before acting, with
   `RICO_SUPERVISOR_RESULT: OWNER_GATE`.

## Stage: ACT

1. `WRITER` only. Create or reuse exactly one approved branch for the task,
   started from the freshly fetched `origin/main`.
2. Make the **smallest safe change** that satisfies the acceptance criteria.
3. Stay inside "files allowed". Touching a file on the "files forbidden"
   list voids the invocation: revert the touch and stop with
   `RICO_SUPERVISOR_RESULT: OWNER_GATE` (scope expansion).
4. No broad rewrites, no drive-by refactors, no formatting churn, no new
   dependencies, no new env var names, no parallel implementations of an
   objective that already has an open PR.

## Stage: VERIFY

1. Run **focused tests first** — the narrowest suite that can falsify the
   change (specific test files, `py_compile`, `bash -n`, targeted
   `npm run build` only when frontend files changed).
2. Inspect the final diff (`git diff`) line by line against the claim's
   "files allowed" list and acceptance criteria.
3. Run broader CI only when the focused evidence passes.
4. Compare the result against the **written acceptance criteria**, one by
   one. Green CI alone is never proof of correctness — every criterion needs
   its own evidence (test output, diff inspection, or explicit `not run`
   with a reason).
5. **A failed acceptance criterion MUST NOT be reported as complete.** If
   any criterion fails, either run a correction cycle (max three total) or
   stop with `RICO_SUPERVISOR_RESULT: INCOMPLETE_EVIDENCE`, stating exactly
   which criteria passed and which did not.

## Stage: RECORD

1. **Pre-push revalidation (mandatory).** Immediately before committing and
   pushing: run `git fetch origin main` again and re-check (a) that `main`
   has not advanced past the recorded base with changes that touch the
   claim's files, (b) open-PR changed-file overlap, and (c) Task-ID
   uniqueness. If `main` moved with conflicting changes, or a new overlap
   or ID collision appears after OBSERVE, STOP with
   `RICO_SUPERVISOR_RESULT: BLOCKED_CONFLICT` and do NOT push the branch.
2. Update the **existing** Continuity Block for the task in
   `AI_WORKSPACE/TASKS.md` — never duplicate it. Record: branch, base SHA,
   head SHA, files changed, tests run and results, CI state, blockers,
   risks, rollback plan, and the next exact action.
3. Commit in the **two-commit ledger pattern**: first commit the work (call
   its SHA W), run the validation evidence against W, then append ONE
   session entry to `AI_WORKSPACE/DEVELOPMENT_LOOP_STATE.md` with
   `validated_head_sha: W` and commit the ledger entry as W's child. The
   ledger is append-only: never rewrite, amend, or "fill in later" a prior
   entry; a correction is a NEW finalization entry that references the
   earlier one. `files_changed` must equal the FULL diff of the task's
   commits against base — including `AI_WORKSPACE/TASKS.md` and the ledger
   file itself when touched.
4. Push ONLY through `scripts/rico-supervisor-push.sh` — the deterministic
   push gate that mechanically performs step 1 (re-fetch `origin/main`,
   merge-base freshness, changed-file overlap against main and every open
   PR, Task-ID uniqueness including open PR patches) immediately before the
   push and refuses with nothing pushed on any conflict. Direct `git push`
   is denied to supervised sessions; the prose revalidation above is the
   contract, the gate is its enforcement. Then open the **Draft** PR ONLY
   through the gate's `--create-pr` mode — raw `gh pr create` is denied
   because it can implicitly push an unpushed branch (an alternate push
   path). `--create-pr` re-runs the SAME shared validation as the push path
   immediately before creating (main drift, open-PR overlap, Task-ID
   uniqueness — no TOCTOU window), proves `origin/<branch>` exists and
   equals local HEAD, then calls `gh pr create --draft --head <branch>
   --base main` with content flags only (identity/state flags such as
   `--head`, `--base`, `--repo`, `--web`, `--dry-run` are rejected before
   `gh` is invoked). The PR body carries the evidence report.

## Stage: STOP OR LOOP

1. Stop immediately when any hard owner gate is reached —
   `RICO_SUPERVISOR_RESULT: OWNER_GATE`.
2. Otherwise stop when the single task's acceptance criteria are all
   evidenced — `RICO_SUPERVISOR_RESULT: COMPLETE` (Draft PR + evidence
   report; merge remains owner-gated).
3. A correction cycle (re-observe → re-verify on the SAME task) is allowed
   at most THREE times per invocation; after that, stop with
   `RICO_SUPERVISOR_RESULT: INCOMPLETE_EVIDENCE`.
4. Looping to a NEW task always requires a NEW invocation. There is no
   in-process continuation to a second objective.

## Hard owner gates

Always STOP (result `OWNER_GATE`) before any of the following — no
exceptions, no "small" cases:

1. merge (any branch into `main`, or marking a PR ready with intent to merge)
2. production deploy (Render, Vercel, deploy hooks, workflow dispatch)
3. database migration or SQL execution (Neon or any live database)
4. secret or environment-variable changes (create, read, rotate, or delete)
5. Render worker/instance changes (count, plan, scaling — see PR #1187 invariant)
6. billing mutations (Paddle config, plans, prices, subscriptions)
7. production data mutation (any live user or production table)
8. destructive commands (`git push --force`, `git reset --hard`, `git clean`,
   branch deletion, `rm -rf`, history rewrites)
9. scope expansion (files or objectives beyond the recorded claim)
10. opening a competing PR for an objective that already has an open PR
11. accepting a known safety limitation (anything that weakens
    `src/rico_safety.py`, auth identity, approval mode, or log privacy)
12. changing a product or architecture decision (anything recorded in
    `AI_WORKSPACE/DECISIONS.md` or owner-gated in `PROJECT_STATUS.md`)

## Result contract

Every invocation MUST end with the result line as the **last non-empty line**
of its final output, in exactly this format and appearing exactly once:

```text
RICO_SUPERVISOR_RESULT: COMPLETE | IDLE | OWNER_GATE | BLOCKED_CONFLICT | INCOMPLETE_EVIDENCE
```

The launcher enforces this strictly: the last non-empty line must be a single
exact-format result line with a known token, and no other line may begin with
`RICO_SUPERVISOR_RESULT:`. Anything else — trailing text, an early token, a
duplicate result line, an unknown token — is treated as NO RESULT and exits
non-zero.

- `COMPLETE` — one task done; all acceptance criteria evidenced; Draft PR
  open; ledger and Continuity Block updated.
- `IDLE` — no safe task; no branch created; no files modified; one concrete
  owner recommendation reported.
- `OWNER_GATE` — a hard owner gate was reached; work stopped before it.
- `BLOCKED_CONFLICT` — workspace documents and live state disagree (at
  OBSERVE or at pre-push revalidation); nothing was pushed.
- `INCOMPLETE_EVIDENCE` — correction budget exhausted or a criterion could
  not be evidenced; the report states exactly what is missing.

The same result value is appended to the `DEVELOPMENT_LOOP_STATE.md` ledger
entry, except for `IDLE` and `BLOCKED_CONFLICT`, which modify no files and
are reported in chat/launcher output only.

## Launcher preconditions and permission posture

- The launcher refuses to start a supervised run unless the working tree is
  clean AND the checked-out branch is `main` AND local `main` equals the
  freshly fetched `origin/main`. Running from any other branch — however
  clean — exits non-zero before Claude is invoked. The supervisor itself
  creates the task branch during ACT.
- Tool AVAILABILITY is restricted with `--tools` to the built-in minimum
  (Read, Edit, Write, Grep, Glob, Bash) — allow/deny lists then govern
  permission for only those tools. MCP servers and connectors are excluded
  twice over: `--strict-mcp-config` with no MCP config loads none, and
  `mcp__*` is denied besides. `--setting-sources project` keeps user/local
  permission grants and plugins from silently widening the session.
- Read/Edit are path-scoped to the project directory, and known local
  secret paths (`.env*`, `*.env`, credential/token/key files) carry explicit
  deny rules on top of the scoping (Edit rules govern all file-editing
  tools, Write included).
- Direct `git push` AND raw `gh pr create` are denied; pushing and PR
  creation happen only through the `scripts/rico-supervisor-push.sh` gate
  described in RECORD.
- Launcher run logs live OUTSIDE the repository (XDG state dir by default),
  so an `IDLE` or `BLOCKED_CONFLICT` run leaves the working tree
  byte-for-byte untouched — behaviorally, not merely gitignored.
- These permission lists are **defense in depth, not a sandbox**. The static
  guard proves the configuration and the contract text, not the
  impossibility of bypass; search tools (Grep/Glob) accept absolute paths
  and are a known residual read surface. Do not describe this layer as
  making secret access impossible.

## Cost controls

- Cheapest safe path always: focused tests before suites, one review pass,
  concise report (per `CLAUDE.md` cost rules).
- No subagent fan-out, no repeated verifier agents, no broad repo scans.
- If a deep review seems needed, stop and ask the owner with expected token
  range, dollar cost, reason, and a cheaper alternative.
