# Start Here — Rico AI

This is the entrypoint for new Rico AI work sessions.

## Short start command

```text
Rico mode. Start from AI_WORKSPACE/START_HERE.md.
```

## Latest handoff

Before starting new Rico work, read the latest rollout handoff:

1. `AI_WORKSPACE/HANDOFFS/2026-07-10-fe-sidebar-routing-ia.md` (latest — `main` at `a844b71`; PR
   `test(frontend): align sidebar routing with current IA` (B4, owner-approved YELLOW). Owner
   confirmed the `/queue` ("Applications") sidebar nav removal is intentional; removed the obsolete
   `/queue` nav-item test + the orphaned `NAV_ITEM_KEYS["/queue"]` entry (`/queue` page kept, still
   builds). Vitest suite now **320/0** (total dropped by 1 — the obsolete test was deleted, not
   fixed). Known pre-existing full-suite flake in `chat-confirm-profile.test.tsx` (`scrollTo` not
   mocked in jsdom) must be fixed in `vitest.setup.ts` before B5 makes vitest a required gate. See
   TASK-20260710-008.)
2. `AI_WORKSPACE/HANDOFFS/2026-07-10-fe-chat-action-disabled-reasons.md` (`main` at `36f56fc`; PR
   `fix(frontend): align chat action disabled reasons` (B3). Added `open_drawer → "Coming soon"`
   disabled reason in `ChatActionCard.tsx` + a test-string update: vitest 317/4 → 320/1.)
3. `AI_WORKSPACE/HANDOFFS/2026-07-10-fe-green-residual-fixes.md` (`main` at `2c685e7`; PR
   `test(frontend): resolve green residual vitest failures` (B1+B2). Resolved 8 residual FE vitest
   failures **test-only** (no product code): vitest baseline 309/12 → 317/4. See TASK-20260710-008.)
4. `AI_WORKSPACE/HANDOFFS/2026-07-10-fe-test-health-ci-gate.md` (`main` at `877b18b`; PR #942
   "frontend build gate + frontend test visibility baseline" merged. FE vitest baseline established
   (302 passed/19 failed) and 7 shared `next/navigation`/`LanguageProvider` test-crash failures fixed
   via test-config only (309 passed/12 failed, zero product code changed). `npm run build` added as a
   required/blocking CI gate (green); `npm run test` added as informational-only; #941
   terminology-lexicon audit merged read-only, no code)
5. `AI_WORKSPACE/HANDOFFS/2026-07-09-906-907-sync-and-908-909-triage.md` (`main` at
   `ec06ef5`; #906 `profile_repo.py` connection-leak fix and #907 #758 job-key unification both
   merged and Vercel-production-READY; #812 in progress; #908 (attachment-first orchestration bug)
   and #909 (governance-doc conflict) triaged, both awaiting owner direction)
6. `AI_WORKSPACE/HANDOFFS/2026-07-09-board-clean-governance-complete.md` (#890 agent operating model merged at `ac0cd99`; #897 technical handoff merged at `bb9555e`; #898 Docker local-dev merged at `7fb41bc`; board clean with only #872/#873 held; no C3/C4/C8 started)
7. `AI_WORKSPACE/HANDOFFS/2026-07-08-technical-status.md` (#892 #764 trust guard merged, #894 Lovable quarantine merged, #895 C2 legal pages live, #896 duplicate closed, #898 Docker local-dev merged; #886/#867 closed as stale/superseded; #872/#873 held)
8. `AI_WORKSPACE/HANDOFFS/2026-06-22-job-flow-stabilization-complete.md` (PRs #727/#724/#723/#728/#729/#730 merged + deployed; only PR C remains for Tests 1–9)
9. `AI_WORKSPACE/HANDOFFS/2026-06-22-job-flow-stabilization.md` (earlier stabilization handoff — superseded by the complete handoff above)
10. `AI_WORKSPACE/HANDOFFS/2026-06-21-system-quality-audit.md` (codebase audit — bugs fixed, tech debt documented)
11. `AI_WORKSPACE/HANDOFFS/2026-06-21-career-os-roadmap-status.md` (which Career OS milestones are actually built)
12. `AI_WORKSPACE/HANDOFFS/2026-06-21-action-audit-rollout-complete.md`
13. Then continue with the read order below.

## Project map (read first)

Fastest orientation, in order:

- `AI_WORKSPACE/PROJECT_STATUS.md` — **30-second snapshot**: where Rico is, last
  merge, what works, what's next, risks, active PR. Read this first.
- `AI_WORKSPACE/MASTER_INDEX.md` — the living index of every workspace document
  (Active / Historical / Proposed) + the ADR index into `DECISIONS.md`.
- `AI_WORKSPACE/ENGINEERING_ROADMAP.md` — Vision → Architecture → Roadmap →
  Epics → Milestones → PRs → Releases, with the status of every phase (0–7).
- `AI_WORKSPACE/AGENT_OPERATING_MODEL.md` — agent roles, boundaries, and
  response logic for owner, architecture, Claude, Codex, Lovable, and release work.

## Read order

Start with the current repository state, then read:

1. `CLAUDE.md`
2. `AI_WORKSPACE/PROJECT_BRIEF.md`
3. `AI_WORKSPACE/ENGINEERING_ROADMAP.md`
4. `AI_WORKSPACE/AGENT_OPERATING_MODEL.md`
5. `AI_WORKSPACE/ARCHITECTURE.md`
6. `AI_WORKSPACE/CURRENT_STATE.md`
7. `AI_WORKSPACE/TASKS.md`
8. `AI_WORKSPACE/OPERATING_RULES.md`
9. `AI_WORKSPACE/DECISIONS.md`
10. `AI_WORKSPACE/PROMPT_CONTRACT.md`

Optional context bundle:

```bash
python scripts/sync_context.py
```

## Work flow

```text
Task entry
  -> handoff brief
  -> operating rules
  -> one branch
  -> pull request
  -> review and verification
  -> merge
  -> deploy verification when runtime changed
  -> workspace update if needed
```

## Task checklist

Each task should have:

- objective
- branch name
- files in scope
- files out of scope
- constraints
- acceptance criteria
- verification steps
- rollback plan

## Continuity Gate (read before writing anything)

Every agent starts by reading, in order: this file → `TASKS.md` (active
Continuity Blocks) → `CURRENT_STATE.md` → the latest `HANDOFFS/*` → the
active PR body → the linked GitHub issue. Every agent ends by writing/updating
the Continuity Block for the task it touched, and — if the task isn't
`done`/`verified` — a dated `HANDOFFS/<date>-<topic>.md` entry with the
Continuity Block copied in. A task with no Continuity Block, or one left
`in_progress` with no "next exact action," is not a valid stopping point.

**Approaching a token/context/tool/usage/time limit mid-task is its own
mandatory trigger for this same step — do not wait until the task is
finished.** See "Session continuity / limit-approach handoff" in
`AGENT_OPERATING_MODEL.md` for the exact required fields. This applies to
every agent on this repo (Claude, Codex, Lovable, Devin, or any other), not
just Claude.

## Branch ownership

Use one writer per branch. Other tools or reviewers can inspect and comment without editing the same branch.

## Standard handoff prompt

```text
Rico mode. Start from AI_WORKSPACE/START_HERE.md. Read the latest handoff, current state, current task in AI_WORKSPACE/TASKS.md, AI_WORKSPACE/OPERATING_RULES.md, and AI_WORKSPACE/PROMPT_CONTRACT.md. Use one branch and return summary, changed files, commands run, test results, CI/deploy status, risks, rollback plan, and open questions.
```
