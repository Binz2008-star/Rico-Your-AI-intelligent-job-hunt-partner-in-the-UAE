# Tasks

Use this file as the shared task ledger. Each task must be small enough to review in one PR.

## Status values

- `proposed`
- `scoped`
- `in_progress`
- `blocked`
- `review`
- `verified`
- `done`

## Task template

```md
### TASK-YYYYMMDD-001 — <title>

Status: proposed
Owner: <human/model>
Branch: <branch-name>
Issue/PR: <link or number>

#### Objective
<objective only>

#### Context
- Relevant files:
- Relevant docs:
- Existing behavior:

#### Constraints
- Do not touch:
- No migrations unless explicitly required:
- Keep scope limited to:

#### Acceptance criteria
- [ ]
- [ ]
- [ ]

#### Required verification
- [ ] Unit tests:
- [ ] Integration tests:
- [ ] Frontend build:
- [ ] Local smoke:
- [ ] Production/deploy smoke if applicable:

#### Continuity Block
- Task ID: TASK-YYYYMMDD-001
- GitHub issue/PR: <#number or link>
- Branch: <branch-name>
- Base branch: <branch, e.g. main>
- Last safe commit SHA: <sha the task can be safely resumed/rolled back to>
- Current head SHA: <sha>
- Uncommitted changes present: <yes/no — if yes, summarize what's staged/unstaged>
- Status: proposed | scoped | in_progress | blocked | review | verified | done
- Files inspected: <path list — read but not necessarily changed>
- Files changed: <path — reason>
- Files intentionally not touched: <path — reason, or "none">
- What is complete: <bullet list>
- What is incomplete: <bullet list>
- Known blockers: <bullet list, or "none">
- Validation already run: <command → result>
- Validation still required: <command or check, not yet run>
- Deployment/CI/Neon/Vercel state to check next: <what, if anything, or "none">
- Next exact action: <single next step, concrete enough to resume cold>
- Stop condition: <what state means "stop and ask the owner" vs. "safe to keep going">
- Rollback plan: <exact revert path>
```

A session that notices it may run out of token/context/tool/usage/time budget
before the task is complete must fill in this exact block (updating the
existing entry if one already exists for the task, never duplicating it)
before continuing further — see "Session continuity / limit-approach
handoff" in `AGENT_OPERATING_MODEL.md`.

## Active tasks

### TASK-20260718-022 — PR #1171: mobile usability pass on /command + /profile

Status: verified — **MERGED + deployed**
Owner: Claude (production-defect remediation, owner directive 2026-07-18)
Branch: `fix/mobile-usability-command-profile` (merged, auto-deleted)
Issue/PR: #1171 (squash `96464b8e101b5a034470b07f359aaebc079a7d6d`)

#### Delivered

- CTRL+K/CTRL+J hint lines hidden below `md` on both chat audiences (desktop
  keeps them + WCAG contrast check); composer proven in-viewport at
  320/360/390 with no fixed-nav overlap; `/profile` unsaved bar compacted
  (Save/Discard on-screen at 320px); warning text `break-words` (zero
  horizontal overflow EN + AR RTL). New `e2e/mobile-usability.spec.ts`
  (10 checks); stability spec re-anchored; `apps/web/e2e/screenshots/`
  gitignored (evidence artifacts never committed). 22/22 focused e2e.

### TASK-20260718-021 — PR #1170: single approved shell on authenticated workspace routes (P0)

Status: verified — **MERGED + deployed ("Deploy to Production" success)**
Owner: Claude (production-defect remediation, owner directive 2026-07-18)
Branch: `fix/single-shell-authenticated-command` (merged, auto-deleted)
Issue/PR: #1170 (squash `e2ba730b497ba07687c53dba5e044194b89e60fa`)

#### Root cause (owner production screenshots)

- Legacy dark MobileCommandHeader + MobileBottomNav still mounted for the
  authenticated audience on `/command` mobile — the #1145 compromise
  (`WorkspaceShell variant="app"` rendered no mobile chrome, so the page kept
  the legacy pair) layered old chrome over the Atelier workspace.

#### Delivered

- WorkspaceShell app variant: opt-in `mobileChrome` (shared mobile bar +
  drawer, single navigation owner) + `mobileExtras` slot; authenticated
  `/command` uses it — New chat / Clear chat / Log out live in the drawer;
  MobileCommandHeader is public/checking-only; MobileBottomNav mount deleted;
  composer 56px dock compensation removed (safe-area kept). `/profile`
  `/settings` `/applications` verified already single-shell and pinned.
  Proof: `e2e/single-shell.spec.ts` + updated stability spec (12 checks,
  real Chromium; AR RTL; public surface unchanged); screenshots delivered
  as artifacts.

### TASK-20260718-020 — PR #1169: restore live profile saves (P0 production outage)

Status: verified — **MERGED + deployed ("Deploy to Production" success)**
Owner: Claude (production-defect remediation, owner directive 2026-07-18)
Branch: `fix/profile-save-wrapper-clear-fields` (merged, auto-deleted)
Issue/PR: #1169 (squash `1e8615ce1137e725485e2a41d1439bf133abd039`)

#### Root cause (owner production screenshot: "Profile update could not be saved")

- #1166 called the router's stable patch-point wrapper with `clear_fields=`;
  the wrapper's signature didn't accept it → TypeError on EVERY save,
  swallowed by the endpoint's broad except into the generic 503. CI green
  because endpoint tests mock the wrapper symbol itself (over-mocking).

#### Delivered

- Wrapper accepts + forwards `clear_fields` (superset-signature invariant
  pinned in a comment); 503/500 failure surfaces carry a correlation ref
  (`(ref XXXX)`) matching the backend log line — the frontend toast already
  renders server detail. Regression: `TestRicoProfileSaveThroughRealWrapper`
  exercises the REAL wrapper, patching one layer down — verified failing
  (503) against the pre-fix code; 4/4 with the fix. Backend suite 3,968 green.

### TASK-20260718-019 — PR #1167: route-exit dirty-state protection (Profile track Phase 4)

Status: verified — **MERGED + deployed (frontend-only)**
Owner: Claude (owner-authorized autonomous track execution 2026-07-18)
Branch: `feat/profile-route-exit-dirty-protection` (merged, auto-deleted)
Issue/PR: #1167 (squash `ae6567871beffdab4ebff3b68bee8d5d75863908`)

#### Delivered

- Closes the #1161 residual P1: browser Back exiting `/profile` is made
  non-destructive — per-tab, account-keyed sessionStorage draft mirror,
  restored with the unsaved bar on return; removed on save/discard;
  foreign-account drafts ignored AND wiped; corrupt storage → clean start.
  No history trap (would break section back/forward), no shell/router change.
  All #1161 guards unchanged. 8 new tests (`profile-draft-persistence.test.tsx`);
  full vitest 711/68 green.

### TASK-20260718-018 — PR #1166: explicit-null clearing for numeric profile fields

Status: verified — **MERGED + deployed ("Deploy to Production" success)**
Owner: Claude (owner-authorized autonomous track execution 2026-07-18)
Branch: `fix/profile-nullable-numeric-clear` (merged, auto-deleted)
Issue/PR: #1166 (squash `0da1c3e23647f6b5bc5529cab8e57214b860e21c`)

#### Delivered

- Defect confirmed real at three layers (Pydantic omitted≡null; repo
  None-strip; mirror None-skip). Contract: omitted=unchanged, explicit
  null=clear, 0=valid, invalid=422 — for `salary_expectation_aed`,
  `minimum_salary_aed`, `years_experience` only. Additive `clear_fields`
  channel (endpoint `model_fields_set` → repo allowlist → JSONB `||` null
  write → mirror clear post-commit); **no migration, no schema change**;
  every existing caller's None-means-unchanged semantics preserved; #764
  verifier checks merged expected state. 13 new backend tests + frontend
  clear-saves-null/zero-valid tests; backend 3,964 + frontend 703 green.

### TASK-20260718-017 — PR #1165: actionable profile warnings (Profile Phase 4B)

Status: verified — **MERGED + deployed ("Deploy to Production" success)**
Owner: Claude (owner-authorized autonomous track execution 2026-07-18)
Branch: `feat/profile-actionable-warnings` (merged, auto-deleted)
Issue/PR: #1165 (squash `ab7075940a309293e6f0738fc7a6553b30ce1577`)

#### Delivered

- Passive `/profile` warning banner → actionable workflow on the Phase 4A
  contract: live count summary (EN/AR singular/plural), blocking-first
  severity badges, direct actions on stable field identifiers
  (`target_roles`/`preferred_cities` → `?section=goals` + param preservation +
  exact-field focus + reduced-motion-safe highlight + SR announcement;
  settings-owned fields → `/settings`), authoritative save-refresh removal +
  hide-when-empty, blocking non-dismissable, session-scoped Review-later with
  restore (never claims resolution). Frontend-only; 16 new vitest cases +
  focused Playwright (EN + AR RTL, screenshots as uncommitted artifacts).

### TASK-20260718-016 — PR #1164: backend-authoritative warning severity contract (Profile Phase 4A)

Status: verified — **MERGED + deployed ("Deploy to Production" success)**
Owner: Claude (owner-authorized autonomous track execution 2026-07-18)
Branch: `fix/profile-warning-severity-contract` (merged, auto-deleted)
Issue/PR: #1164 (squash `63e976d0a06144c28f447ace210ccc453dd5d72f`)

#### Delivered

- `WarningSeverity` enum (`blocking`/`important`/`recommendation`);
  explicit `WARNING_SEVERITY_BY_CODE` + `WARNING_FIELD_BY_CODE` for all 6
  emitted matching-guardrail codes (blocking:
  `excluded_keyword_blocks_target_role`, `invalid_uae_city`; important:
  `excluded_keyword_overlaps_included_keyword`,
  `excluded_keyword_blocks_core_role_word`, `minimum_fit_score_high`;
  recommendation: `too_many_target_roles`); fail-safe `severity_for_code()`
  (unknown → logged + deterministic `important`, unreachable in a green build
  via the exhaustive contract test). Response shape + bilingual contract
  preserved; `cv_quality_warnings` untouched; no DB change.

### TASK-20260718-015 — PR #1161: profile true URL-backed section navigation (Profile Phase 3)

Status: verified — **MERGED + deployed (frontend-only)**
Owner: Claude (Release Captain pass; owner-approved merge 2026-07-18)
Branch: `feat/profile-true-section-navigation` (merged, auto-deleted)
Issue/PR: #1161 (squash `76e52984d0c052dfa9528844bcbb587c032ab021`)

#### Objective

Replace the /profile visual-only section rail (shipped by #1152) with true
URL-backed section navigation. Completes **Profile Phase 3**.

#### Delivered

- `?section=` drives a render-only-selected switch (one section at a time; the old
  IntersectionObserver scroll-spy is removed). Deep links, in-`/profile`
  back/forward, and refresh resolve from the URL; missing→about (URL left clean),
  invalid→about (canonicalized with `replace`), explicit valid section wins; every
  unrelated query param (incl. the #1159 Gmail callback → Integrations) is preserved.
  Unsaved draft survives section switches; `beforeunload` guards refresh/close and a
  profile-scoped capture-phase interceptor guards internal cross-route nav while
  dirty; mobile `<select>`; heading focus on intentional change; RTL mirrored.
- Files: `apps/web/components/profile/ProfileEditorial.tsx`,
  `apps/web/app/profile/page.tsx`, `apps/web/lib/translations.ts` (+2 EN/AR keys),
  `apps/web/__tests__/profile-editorial.test.tsx`. 4 files, +467/−80. Frontend only —
  no backend/schema/API/migration/Gmail/warning/billing change.

#### Deferred / not in scope (still QUEUED)

- **Browser Back that EXITS `/profile`** is not intercepted (refresh/close + internal
  `<Link>` nav ARE; in-profile section back/forward preserves the draft). Owner-accepted
  as a **separate P1**: *Profile cross-route dirty-state protection* at the shared
  WorkspaceShell/navigation layer. Not branched, not implemented.
- **Profile Phase 4A** (backend warning severity contract) and **Phase 4B** (actionable
  warning frontend) — NOT started.

#### Verification

- Rebased onto `main` `f10498cd` (head `b688cdc8`); focused `profile-editorial.test.tsx`
  **32/32**; `next build` clean; full CI green (frontend/pytest/playwright/
  postgres-integration/workflow-security-guards); 0 review threads; `mergeable_state`
  clean. Squash `76e52984`; **"Deploy to Production" run for `76e52984` = success**.
- **Owner live authenticated `/profile` + Arabic RTL visual smoke on `ricohunt.com`
  still PENDING** (production host network-blocked from the executing session).

#### Continuity Block

- Task ID: TASK-20260718-015
- GitHub issue/PR: #1161
- Branch: `feat/profile-true-section-navigation` (merged, auto-deleted)
- Base branch: main
- Last safe commit SHA: `f10498cd` (pre-merge main)
- Current head SHA: `76e52984` (squash on main)
- Uncommitted changes present: no
- Status: verified
- Files inspected: the 4 files above
- Files changed: none pending — merged

### TASK-20260718-007 — Stage 1: Neon data-architecture audit + source-of-truth decision record (docs-only)

Status: review (draft PR open; owner approval is the stop condition)
Owner: Claude (WRITER on `claude/database-audit-results-qcurpe`)
Branch: `claude/database-audit-results-qcurpe`

- Audit baseline (evidence gathered at): `main` @ `4ce678b6`
- Current PR base after reconciliation with main: `main` @ `197d946`
- PR head before this correction pass: `c3cdb95`
Issue/PR: Stage 1 audit PR #1160 (docs-only)
Traceability: Vision: Rico Career OS — trustworthy user data
→ Epic: Neon data architecture remediation (DEC-20260718-001)
→ Milestone: M0 — audit + canonical decisions
→ Phase: Phase 0 (evidence)
→ Proposed PR objective: publish the verified audit + proposed decision
  matrix + phased task ledger, docs-only
→ Task: TASK-20260718-007

#### Objective

Produce the verified, read-only Neon production architecture audit and the
proposed source-of-truth decision matrix; no production or runtime change.

#### Scope / files

- `AI_WORKSPACE/AUDITS/2026-07-18-neon-data-architecture-audit.md` (new)
- `AI_WORKSPACE/DECISIONS.md` (DEC-20260718-001, proposed)
- `AI_WORKSPACE/TASKS.md` (this ledger)

#### Risks

Docs-only; only risk is stale numbers — every figure is dated 2026-07-18 and
sourced (repo `file:line` or aggregate live query).

#### Acceptance criteria

- [x] Every material claim carries repo or aggregate-DB evidence
- [x] No PII/secrets in the diff (aggregate counts only)
- [x] No runtime files changed; no SQL beyond SELECT/catalog reads
- [ ] Owner approves DEC-20260718-001 rows (moves to Accepted)

#### Rollback plan

- Before merge: close PR #1160 without merge; production and runtime remain
  unchanged.
- After squash merge: revert the resulting squash-merge commit.

Dependencies: none. Production impact: none. Neon changes: none.
Documentation impact: adds the canonical audit + proposed decision + phased
task ledger (Phases 1–7 below).

### TASK-20260718-008 — Phase 1 (umbrella): protect and document the production Neon branch

Status: proposed (execution gated only on explicit owner approval of branch
protection itself — NOT on acceptance of the full DEC-20260718-001 matrix)
Owner: owner-gated (Neon console) with agent-prepared checklist
Traceability: Vision: Rico Career OS — trustworthy user data
→ Epic: Neon data architecture remediation (DEC-20260718-001)
→ Milestone: M1 — production containment
→ Phase: Phase 1 (single-slice milestone)
→ Proposed PR objective: see slice 1A (the only slice)
→ Task: TASK-20260718-008 (subtask 008-1A)

A Phase is an umbrella milestone, not a PR. Each slice = one PR / one change
window with exactly one objective. Slices are never combined.

#### Slice 1A — enable production branch protection

- **Objective (one):** turn on Neon branch protection for `production`
  (`br-restless-cherry-amq6wj7o`) and document the branch/backup model.
- **Scope:** one Neon console setting + one AI_WORKSPACE doc section; no
  schema, no code, no data.
- **Risk:** preview-branch automation (Vercel/GitHub create children of
  production — 216 live examples) must be confirmed unaffected first.
- **Acceptance:** branch shows `protected: true`; a test preview branch still
  creates successfully; branch/backup model documented.
- **Rollback:** toggle protection off (one console action, documented).
- **Depends on (only):** (1) explicit owner approval; (2) verification that
  protection does not break Vercel/GitHub preview-branch creation; (3) the
  documented toggle-off rollback above. NOT gated on Neon Data API status,
  the Render `DATABASE_URL` role, or acceptance of the full
  DEC-20260718-001 matrix — those verifications live exclusively in slice
  2A (TASK-20260718-009). **Production impact:** none to data.
  **Docs impact:** branch model section in AI_WORKSPACE.

### TASK-20260718-009 — Phase 2 (umbrella): database access boundary and least privilege

Status: proposed
Owner: agent-prepared on a non-production Neon branch; owner-gated cutover
Traceability: Vision: Rico Career OS — trustworthy user data
→ Epic: Neon data architecture remediation (DEC-20260718-001)
→ Milestone: M2 — least-privilege access boundary
→ Phase: Phase 2 (umbrella; slices 2A–2E, one PR each)
→ Proposed PR objectives: per slice below
→ Task: TASK-20260718-009 (subtasks 009-2A … 009-2E)

Never combined: runtime-role creation, Render cutover, grant revocation, and
RLS rollout are four separate change windows.
Umbrella docs impact: access model documented in AI_WORKSPACE.

#### Slice 2A — verify Data API and runtime access paths (read-only)

- **Objective (one):** record Data API enabled/disabled state (console) and
  inventory every path that connects to `neondb` (Render, workflows, MCP,
  previews), including the role each uses.
- **Scope:** read-only verification + one docs update. **Risk:** none
  (read-only). **Acceptance:** audit §14 items 1–2 closed with evidence.
- **Rollback:** n/a. **Depends on:** TASK-008. **Production impact:** none.

#### Slice 2B — create and test a limited runtime role (non-production)

- **Objective (one):** create the least-privilege FastAPI role and prove the
  full backend test suite + API smoke green under it on a Neon test branch.
- **Scope:** role + grants on a test branch only; zero production change.
- **Risk:** under-granting breaks runtime paths — that is what the test
  branch is for. **Acceptance:** suite + smoke green under the new role.
- **Rollback:** delete the test branch. **Depends on:** 2A.
- **Production impact:** none.

#### Slice 2C — cut Render to the limited role

- **Objective (one):** switch Render's `DATABASE_URL` to the proven limited
  role in one change window.
- **Scope:** one env-var change; no code. **Risk:** missed grant surfaces in
  production — mitigated by 2B parity + post-cutover smoke.
- **Acceptance:** `/health`, auth, chat, applications smoke green; live
  sessions show the new role. **Rollback:** restore the previous connection
  string (instant). **Depends on:** 2B. **Production impact:** one
  change window.

#### Slice 2D — revoke unnecessary `authenticated` grants

- **Objective (one):** revoke the blanket 44-table CRUD from `authenticated`
  (and review `anonymous`), keeping only what 2A's inventory proves needed.
- **Scope:** REVOKE statements, staged on the test branch first. **Risk:**
  breaking a legitimate Data-API consumer — none is known; 2A is the guard.
- **Acceptance:** grants match the documented access model; runtime
  unaffected. **Rollback:** re-GRANT from the recorded previous state.
- **Depends on:** 2C. **Production impact:** one change window.

#### Slice 2E — introduce tested RLS policies incrementally

- **Objective (one):** add user-scoping RLS policies table-group by
  table-group, each group with cross-user denial tests on the test branch
  before production.
- **Scope:** policies only; never a bulk flip; the 17 policy-less
  RLS-enabled tables are regularized in the same passes. **Risk:** a wrong
  policy blocks legitimate access — per-group rollout keeps blast radius
  small. **Acceptance:** cross-user read/write proven denied per group;
  product smoke green after each group. **Rollback:** drop the group's
  policies. **Depends on:** 2C (limited role in place; RLS is meaningless
  under BYPASSRLS). **Production impact:** one change window per group.

### TASK-20260718-010 — Phase 3 (umbrella): canonical identity reconciliation

Status: proposed
Traceability: Vision: Rico Career OS — trustworthy user data
→ Epic: Neon data architecture remediation (DEC-20260718-001)
→ Milestone: M3 — one identity spine (`rico_users.id` UUID)
→ Phase: Phase 3 (umbrella; slices 3A–3E, one PR each)
→ Proposed PR objectives: per slice below
→ Task: TASK-20260718-010 (subtasks 010-3A … 010-3E)

Never combined: identity reporting, data reconciliation, merge
implementation, and constraints are separate PRs.
Umbrella docs impact: identity map updated in audit + ARCHITECTURE.

#### Slice 3A — identity mapping report (read-only)

- **Objective (one):** produce the full identifier-family mapping report
  (users ↔ rico_users ↔ text-keyed tables ↔ guests), aggregate-only.
- **Scope:** read-only queries + one AI_WORKSPACE report. **Risk:** none.
- **Acceptance:** every table's identity key mapped; unlinkable rows
  itemized by class. **Rollback:** n/a. **Depends on:** DEC approval.
- **Production impact:** none.

#### Slice 3B — duplicate-email resolution plan

- **Objective (one):** dry-run resolution plan for the 3 duplicate-email
  groups in `rico_users` (which row survives, where children re-point).
- **Scope:** plan + dry-run report; no writes until owner approves.
- **Risk:** wrong merge joins two real people — exact verified-email match
  only. **Acceptance:** owner-approved per-group plan. **Rollback:** n/a
  (docs). **Depends on:** 3A. **Production impact:** none (execution rides
  the 3C window).

#### Slice 3C — orphan/guest classification and reconciliation

- **Objective (one):** classify and reconcile the 121 onboarding + 12
  job-context + 2 document-context unlinkable rows (link, mark
  guest-expired, or archive) with a reviewed idempotent script.
- **Scope:** one scripted data window, backup branch first; script logs
  every row touched. **Risk:** mislinking a guest row to the wrong account —
  linking requires an exact-key match, else classify-not-link.
- **Acceptance:** unlinkable counts → 0 or documented-guest; no orphan rows
  introduced. **Rollback:** restore from the pre-window backup branch.
- **Depends on:** 3B approved. **Production impact:** one data change
  window.

#### Slice 3D — implement the real guest/auth identity merge

- **Objective (one):** replace the no-op `_attempt_identity_merge`
  (`src/agent/identity/resolver.py:194–219`) with a real merge using the
  044 `guest_identity_claims` single-owner invariant.
- **Scope:** runtime code + tests; no data migration in this PR. **Risk:**
  merge races — 044's PK + same-transaction claim is the guard, covered by
  tests. **Acceptance:** guest→auth merge works end-to-end in tests; a
  second claim on the same guest fails closed. **Rollback:** revert the
  code PR. **Depends on:** 3C. **Production impact:** deploy only.

#### Slice 3E — add identity constraints

- **Objective (one):** enforce what 3A–3D made true:
  `rico_profiles.user_id`, `rico_job_recommendations.user_id`,
  `rico_chat_history.user_id` → `CHECK … NOT VALID → VALIDATE →
  SET NOT NULL` (no table rewrite).
- **Scope:** one additive constraint migration. **Risk:** validation fails
  if stragglers exist — 3C acceptance is the precondition.
- **Acceptance:** constraints VALID; drift signature added. **Rollback:**
  drop the constraints (non-destructive). **Depends on:** 3C, 3D.
- **Production impact:** one change window.

### TASK-20260718-011 — Phase 4 (umbrella): application lifecycle reconciliation

Status: proposed
Traceability: Vision: Rico Career OS — trustworthy user data
→ Epic: Neon data architecture remediation (DEC-20260718-001)
→ Milestone: M4 — one application ledger (`rico_job_recommendations`)
→ Phase: Phase 4 (umbrella; slices 4A–4E, one PR each)
→ Proposed PR objectives: per slice below
→ Task: TASK-20260718-011 (subtasks 011-4A … 011-4E)

Never combined: dry-run, reconciliation writes, write-freeze, linkage, and
constraints are separate PRs. Umbrella docs impact: lifecycle map updated.

#### Slice 4A — lifecycle reconciliation dry-run

- **Objective (one):** produce the row-by-row dry-run report for the 5
  context-`applied` + 2 legacy-`applied` + 1 `interview_scheduled` records
  (the ujc→rjr match is heuristic — no shared key — so every row is
  resolved explicitly, never bulk-matched).
- **Scope:** read-only report. **Risk:** none. **Acceptance:**
  owner-approved disposition per row. **Rollback:** n/a.
- **Depends on:** TASK-010 (canonical user resolution). **Production
  impact:** none.

#### Slice 4B — reconcile approved records

- **Objective (one):** write the 4A-approved records into
  `rico_job_recommendations` via a reviewed idempotent script.
- **Scope:** one scripted data window, backup branch first. **Risk:**
  double-insert — the `(user_id, job_key)` unique upsert path is the guard.
- **Acceptance:** canonical table reflects every real application; quota/
  stats counts match. **Rollback:** restore from the pre-window backup
  branch. **Depends on:** 4A. **Production impact:** one data change window.

#### Slice 4C — freeze legacy `applications` writes

- **Objective (one):** add a repo-layer guard so no code path writes new
  rows to legacy `applications`.
- **Scope:** code + tests only. **Risk:** a legacy pipeline path still
  expecting writes — inventory first, guard logs instead of raising.
- **Acceptance:** guard covered by tests; zero new rows in production over
  an observation window. **Rollback:** revert the code PR.
- **Depends on:** 4B. **Production impact:** deploy only.

#### Slice 4D — shared job identity/linkage

- **Objective (one):** give `user_job_context` a durable link to canonical
  job identity (job_key or FK) so context↔ledger matching is exact, ending
  the heuristic gap 4A worked around.
- **Scope:** one additive migration + backfill script + repo update.
- **Risk:** wrong backfill link — backfill only on exact-URL matches, else
  leave NULL. **Acceptance:** new context rows always carry the link;
  backfill report reviewed. **Rollback:** additive column, harmless to
  leave; revert code. **Depends on:** 4B. **Production impact:** one
  change window.

#### Slice 4E — status constraints and lifecycle smoke

- **Objective (one):** add status CHECK constraints
  (`rico_job_recommendations`, `user_job_context`; `NOT VALID → VALIDATE`)
  and run the full lifecycle smoke
  (search → open → prepared → applied → follow-up → interview).
- **Scope:** one constraint migration + smoke run. **Risk:** unknown status
  values — live scan showed none (audit §10). **Acceptance:** constraints
  VALID; smoke green; drift signatures added. **Rollback:** drop
  constraints. **Depends on:** 4B–4D. **Production impact:** one change
  window.

### TASK-20260718-012 — Phase 5 (umbrella): migration drift resolution

Status: proposed
Traceability: Vision: Rico Career OS — trustworthy user data
→ Epic: Neon data architecture remediation (DEC-20260718-001)
→ Milestone: M5 — zero silent drift
→ Phase: Phase 5 (umbrella; slices 5A–5D, one PR each)
→ Proposed PR objectives: per slice below
→ Task: TASK-20260718-012 (subtasks 012-5A … 012-5D)

Never combined: the Gmail 043 window, the 034 index cleanup, and the
drift-detector code change are separate PRs.
Umbrella docs impact: drift-detector README section.

#### Slice 5A — Gmail migration 043 change window

- **Objective (one):** apply 043 to production in an owner change window
  (additive DDL), before any `RICO_ENABLE_GMAIL_SYNC=true`.
- **Scope:** one migration apply + drift verification; no code, no flag
  change. **Risk:** low (additive, idempotent); backup branch first per the
  044 pattern. **Acceptance:** all seven 043 drift signatures PRESENT.
- **Rollback:** documented DROP rollback in the migration footer.
- **Depends on:** owner window; coordinates with #1159 (frontend-only,
  feature stays disabled). **Production impact:** additive DDL.

#### Slice 5B — finish migration 034

- **Objective (one):** run the two remaining
  `DROP INDEX CONCURRENTLY IF EXISTS` statements
  (`idx_rico_job_recommendations_user_job_key`,
  `idx_rico_profiles_user_id`) — both live-verified as non-unique shadows
  of constraint-owned unique indexes (audit §11 Class B).
- **Scope:** two concurrent drops, one window. **Risk:** minimal — covered
  by the surviving unique indexes; EXPLAIN spot-check first anyway.
- **Acceptance:** both absent; upsert path (`ON CONFLICT`) smoke green.
- **Rollback:** recreate from saved definitions. **Depends on:** owner
  window. **Production impact:** two concurrent index drops.

#### Slice 5C — DROP/absence drift detection

- **Objective (one):** extend `scripts/check_migration_drift.py` with
  absence checks so DROP-only migrations (034 and future ones) can no
  longer stay silently unapplied.
- **Scope:** detector code + unit tests only. **Risk:** false alarms —
  covered by tests. **Acceptance:** detector flags a simulated
  unapplied-DROP; 034 signatures included. **Rollback:** revert the code
  PR. **Depends on:** none (can land before 5B; it would then correctly
  report 034 drift until 5B runs). **Production impact:** none.

#### Slice 5D — verify scheduled drift alerting

- **Objective (one):** confirm the drift check runs on a schedule against
  production and its failure alert reaches the admin/dev channel
  (`admin_ci` routing), fixing the wiring if absent.
- **Scope:** CI workflow verification/config only. **Risk:** none.
- **Acceptance:** a forced failure produces an admin alert; schedule
  evidence recorded. **Rollback:** revert workflow change. **Depends on:**
  5C. **Production impact:** none.

### TASK-20260718-013 — Phase 6 (umbrella): index and retention cleanup

Status: proposed
Traceability: Vision: Rico Career OS — trustworthy user data
→ Epic: Neon data architecture remediation (DEC-20260718-001)
→ Milestone: M6 — lean indexes + documented retention
→ Phase: Phase 6 (umbrella; slices 6A–6D, one PR each)
→ Proposed PR objectives: per slice below
→ Task: TASK-20260718-013 (subtasks 013-6A … 013-6D)

Never combined: index cleanup and retention automation are separate PRs.
Umbrella docs impact: retention policy in AI_WORKSPACE.

#### Slice 6A — index classification

- **Objective (one):** complete the Class A–D inventory of audit §11 —
  including Class C overlap/partial cases not captured by the
  signature-identical query — with per-index EXPLAIN evidence, code-path
  notes (e.g. the `ON CONFLICT` partial unique), and drift-signature
  membership.
- **Scope:** read-only analysis on a Neon test branch + docs. **Risk:**
  none. **Acceptance:** every index classified with an evidence line;
  drop-list is the explicit Class A + proven Class B shadows only.
- **Rollback:** n/a. **Depends on:** TASK-012 (5B done first so the 034
  leftovers exit the list). **Production impact:** none.

#### Slice 6B — small concurrent index-drop batches

- **Objective (one):** drop only the indexes independently proven redundant
  in 6A, in small `DROP INDEX CONCURRENTLY` batches (never Class D
  constraint-owned indexes; never on `idx_scan=0` or signature-listing
  evidence alone).
- **Scope:** one batch per window, each preceded by an EXPLAIN re-check.
- **Risk:** removing a useful planner path — per-index evidence + small
  batches + saved definitions bound it. **Acceptance:** every 6A-approved
  index removed; no query-plan regression in the post-batch smoke; all
  constraint-owned indexes and the upsert partial unique untouched.
  (The goal is NOT zero overlapping signatures — only proven-redundant
  removals.)
- **Rollback:** recreate from saved definitions. **Depends on:** 6A.
- **Production impact:** concurrent drops only.

#### Slice 6C — retention policy

- **Objective (one):** document owner-approved retention windows for
  expired `password_reset_tokens` (16/16 expired live),
  `email_verification_tokens` (130/132), `cv_upload_artifacts` (2/2),
  `paddle_checkout_sessions` (13/13), plus webhook/audit log aging.
- **Scope:** docs only (AI_WORKSPACE). **Risk:** none. **Acceptance:**
  policy covers every temporary-record table with a window and a legal/
  audit rationale. **Rollback:** n/a. **Depends on:** DEC approval.
- **Production impact:** none.

#### Slice 6D — cleanup worker/schedule

- **Objective (one):** implement the 6C policy as a feature-flagged,
  batched, metric-emitting scheduled cleanup.
- **Scope:** worker/cron code + tests; flag default OFF, enabled in its own
  window. **Risk:** over-deletion — batch deletes with policy-derived
  predicates + dry-run mode + metrics. **Acceptance:** expired backlog
  drains; steady-state counts stay bounded; metrics visible.
- **Rollback:** flag OFF. **Depends on:** 6C. **Production impact:**
  scheduled deletes of expired records only.

### TASK-20260718-014 — Phase 7 (umbrella): legacy table isolation or retirement

Status: proposed
Traceability: Vision: Rico Career OS — trustworthy user data
→ Epic: Neon data architecture remediation (DEC-20260718-001)
→ Milestone: M7 — every table maps to a class in audit §12
→ Phase: Phase 7 (umbrella; slices 7A–7D — four INDEPENDENT decisions,
  never one PR)
→ Proposed PR objectives: per slice below
→ Task: TASK-20260718-014 (subtasks 014-7A … 014-7D)

Never combined: `leads`, Stripe retirement, legacy `applications`
retirement, and `search_context` are independent decisions and PRs.
Umbrella docs impact: final inventory update in the audit.

#### Slice 7A — `leads` isolation

- **Objective (one):** owner confirms data ownership (zero repo code paths;
  sibling `eco-technology-leads` Neon project exists), then export/move the
  table out of the Rico production DB.
- **Scope:** export → verify → move/drop, one window. **Risk:** deleting
  unconfirmed-ownership data — export precedes any removal; ownership
  sign-off is a hard gate. **Acceptance:** `leads` no longer in `neondb`;
  export retained. **Rollback:** re-import the export. **Depends on:**
  owner confirmation. **Production impact:** one isolation window.

#### Slice 7B — Stripe-era retirement

- **Objective (one):** read-only freeze then retirement plan for
  `user_subscriptions` / `subscription_events` (aligns with #1066; already
  unused for entitlement per `src/subscription_plans.py:90–119`).
- **Scope:** freeze guard + plan doc; the eventual drop is its own
  owner-signed window. **Risk:** losing billing history — archive export
  before any drop. **Acceptance:** no code writes to Stripe tables;
  retirement plan owner-signed. **Rollback:** revert guard.
- **Depends on:** #1066 owner decision. **Production impact:** none until
  the signed drop window.

#### Slice 7C — legacy `applications` pipeline retirement plan

- **Objective (one):** retirement plan for the legacy pipeline trio
  (`applications`, `auto_apply_attempts`, `weekly_reports`) after the
  lifecycle ledger is reconciled.
- **Scope:** plan + archival strategy; drops are separate signed windows.
- **Risk:** legacy pipeline still reading — usage inventory first.
- **Acceptance:** plan owner-signed; archives defined. **Rollback:** n/a
  (docs until execution). **Depends on:** TASK-011 (4B/4C done).
- **Production impact:** none until execution.

#### Slice 7D — `search_context` decision

- **Objective (one):** delete-or-wire decision for dormant `search_context`
  (repo docstring declares it DORMANT; table live with 0 relevant rows).
- **Scope:** decision + either a removal migration or an explicit wiring
  plan — never silently left ambiguous. **Risk:** none (dormant, unused).
- **Acceptance:** DECISIONS.md entry; table either scheduled for removal or
  assigned an owner feature. **Rollback:** table is recreatable from
  migration history. **Depends on:** DEC approval. **Production impact:**
  none until execution.
<!-- Reconciliation 2026-07-18: the six PRs below merged to main after
TASK-008 (#1145) and were not yet in this ledger. Recorded here as the
canonical per-PR record. Merge order on main (oldest→newest): #1153 →
#1152 → #1156 → #1155 → #1151 → #1157. Presented newest-first. -->

### TASK-20260718-006 — PR #1157: plain-language terminology in user-facing copy (EN+AR)

Status: verified — **MERGED + deployed; owner production visual smoke pending**
Owner: Claude (release owner; owner directive 2026-07-18 — approved to finalize+merge)
Branch: `fix/ui-copy-plain-language` (merged, deleted)
Issue/PR: #1157 (merged as squash commit `4ce678b6400889ebfb838e00079c7dfa86fcaf7c`)

#### Objective

Remove technical product jargon from **user-facing copy only** — no internal
identifiers, translation KEY names, props, test IDs, routes, DB fields, API
contracts, or analytics identifiers renamed.

#### Delivered

- EN+AR value changes across nav / headings / buttons / states / helper text:
  Pipeline→Applications; Job Pipeline / Application Flow→Application tracking;
  Career preferences→Career goals (تفضيلات المسار→أهدافك المهنية); In pipeline→In
  applications; Save to pipeline→Save to applications; Pipeline score→Match score;
  Open Flow / Flow→Open applications / Applications; /applications headline "Your
  pipeline."→"Your applications." (مسار طلباتك.→طلباتك.); AR pipeline terms
  (مسار الطلبات / خط الوظائف / المسار)→طلبات التوظيف / متابعة طلبات التوظيف.
- Files: `apps/web/lib/translations.ts`, `components/applications/ApplicationsAtelier.tsx`,
  `components/landing/HowItWorks.tsx`, `components/layout/app-nav.ts`, and 4 test files.
- Deliberately preserved: translation key names, `CommandRail` `pipeline` prop,
  `command-rail-pipeline` testid, `pipeline_active` state key, career-path wording
  (`Career` / `المسار المهني`). The "no jargon remaining" finding is scoped to the
  `apps/web` product-copy surfaces scanned only (server/email/notification/stored
  copy NOT scanned).

#### Deferred / not in scope

- `Sessions → Conversations` (belongs to the Command Workspace program, not this task).

#### Verification

- Rebased onto post-#1151 main; head `e1e8337` → squash `4ce678b`.
- Full frontend vitest 657 pass; `npm run build` clean (41/41); lint clean on changed files.
- CI all green; 0 review threads; `mergeable_state: clean`.
- Production: "Deploy to Production" run #997 for `4ce678b` = success (health + `ricohunt.com`
  reachability + `/proxy/health`). **Owner live terminology visual smoke pending.**

### TASK-20260718-005 — PR #1151: structured Rico reply presentation (safe markdown) + motion polish

Status: verified — **MERGED + deployed; owner production visual smoke pending**
Owner: Claude (release owner; owner directive 2026-07-18 — approved to finalize first)
Branch: `feat/command-reply-motion-arabic-type` (merged, deleted)
Issue/PR: #1151 (merged as squash commit `965dd6404e6be2d0f2c3b3a06e1b1031ad3c2774`)

#### Objective

Render the **same** answer string the `/command` transcript already receives as
safe, structured markdown, plus the reply-motion layer. No change to response
content, prompts, backend routing, APIs, providers, or DB — frontend
reply-presentation only.

#### Delivered

- `react-markdown` + `remark-gfm` + `skipHtml` renderer (`RicoReplyMarkdown.tsx`, new):
  headings, lists, emphasis, blockquotes, inline + fenced code, sanitized links
  (allowlist http/https/mailto/relative; `javascript:`/`data:`/`vbscript:`/`file:`/
  entity-encoded → inert span; `rel="noopener noreferrer"`), no class/style/HTML
  injection, markdown renders during streaming, reduced-motion caret.
- Files: 13 (+593/−34) incl. `RicoReply.tsx`, motion layer (`fonts.ts`, `tokens.ts`,
  `CommandComposer/Messages/ObsidianShell.tsx`, `JobMatchCardAtelier.tsx`,
  `WorkspaceShell.tsx`, `tailwind.config.ts`, `vitest.setup.ts`), and two new test
  files (`rico-reply-markdown.test.tsx`, `rico-reply-markdown-security.test.tsx`).

#### Verification

- Base `6b62a11` → approved head `a4e7b44` → squash `965dd64`.
- Focused renderer+security+transcript 50 pass; full frontend vitest 657 pass;
  `npm run build` clean; lint clean on changed files; Playwright matrix (EN light/dark,
  AR RTL light/dark, mobile 390px, streaming, reduced-motion) captured.
- CI all green; 0 review threads; `mergeable_state: clean`.
- Production: "Deploy to Production" run #996 for `965dd64` = success. **Owner live
  `/command` structured-reply visual smoke pending.**

### TASK-20260718-004 — PR #1155: explicit Arabic job search reaches the search router (not CV-status)

Status: verified — **MERGED + deployed (Render backend); owner AR production smoke pending**
Owner: Claude (release owner; owner directive 2026-07-18 — approved to finalize+merge first)
Branch: `fix/arabic-jobsearch-vs-cv-status` (merged, deleted)
Issue/PR: #1155 (merged as squash commit `6b62a114771d4da5ed775632703f78da7f92dde6`)

#### Objective

Post-#1153 Arabic-only defect: the second CV-guidance gate in
`_handle_active_user_inner` intercepted explicit Arabic job searches
("ابحث عن وظائف تناسب سيرتي الذاتية") as CV-status guidance.

#### Delivered

- Guard added: the gate now also requires `not is_explicit_job_listing_request(message)`
  — the same canonical public predicate the search router keys on (reused from #1153;
  no duplicated intent logic). Files: `src/rico_chat_api.py` (+21/−1), new
  `tests/test_arabic_jobsearch_vs_cv_status.py` (unit + `_process_message_inner`
  production-path).

#### Deferred / not in scope

- Generic `_JOB_DOC_SCORE_RE` tightening (P1) — explicitly deferred by owner.

#### Verification

- Re-anchored; head `7a8f85d` → squash `6b62a11`.
- 8 targeted tests + regression sweep pass (57 on merged commit); CI all green;
  0 review threads; `mergeable_state: clean`.
- Production: Render backend deploy run #389 = success (gated on `/version` commit ==
  `6b62a11` + `/health` 200); the `main` "Deploy to Production" run for `6b62a11` also
  green. **Owner live Arabic `/command` routing smoke pending.**

### TASK-20260718-003 — PR #1156: legible guardrail-warnings banner on the editorial /profile

Status: verified — **MERGED + deployed (contrast-only)**
Owner: Claude (release owner; owner directive 2026-07-18 — contrast-only scope)
Branch: `fix/profile-warnings-contrast` (merged, deleted)
Issue/PR: #1156 (merged as squash commit `25f19445343533c725916b96ab273fda598775c9`)

#### Objective

Fix the unreadable guardrail-warnings banner on the live editorial `/profile`
(contrast/legibility only).

#### Delivered

- `warning`/`warningTint` tone + scoped CSS so `role="alert"` warnings are legible
  in light and dark. `ProfileEditorial.tsx` + translations only.

#### Deferred / not in scope (still QUEUED — see TASK-20260718-... Phase 4)

- Actionable warning workflow: compact summary, severity model, section/field
  navigation, field focus/highlight, refresh-after-save, resolved-warning removal,
  live count, hide-when-empty, unsaved-edit integration. **NOT delivered here.**

#### Verification

- Squash `25f1944`; CI green; frontend build clean; production "Deploy to Production"
  run #994 = success.

### TASK-20260718-002 — PR #1152: rebuild /profile on the owner editorial design (real-data wiring)

Status: verified — **MERGED + deployed (rebuild + visual section rail only)**
Owner: Claude (release owner; owner directive 2026-07 — profile editorial rebuild)
Branch: `feat/profile-editorial-rebuild` (merged, deleted)
Issue/PR: #1152 (merged as squash commit `cee1d6304...`)

#### Objective

Replace `/profile` with the uploaded editorial design, wired to the real system,
deleting the old profile code.

#### Delivered

- `ProfileEditorial.tsx` editorial rebuild: hero plate, profile-strength meter,
  **visual** sticky numbered section rail, 8 section cards, dirty-draft single-PATCH
  save bar; thin auth+data shell page; honest billing/Telegram states; "Verified email";
  numeric-clear validation. Real-data wired (`lib/api.ts`); auth-guard contract preserved.

#### Deferred / not in scope (DELIVERED 2026-07-18 by #1161 — see TASK-20260718-015)

- **True section navigation is NOT delivered *by this PR (#1152)*.** The rail here is
  visual only; true navigation shipped later in **#1161** (`76e52984`, Profile Phase 3).
  Was missing at #1152 time (all now delivered by #1161):
  render-only-selected-section, `/profile?section=…` URL state, deep links,
  back/forward, refresh persistence, invalid→about fallback, mobile selector,
  unsaved-edit protection, section focus management.

#### Verification

- Squash `cee1d63`; CI green; frontend build clean; production "Deploy to Production" = success.

### TASK-20260718-001 — PR #1153: route "find jobs that match my CV" to job search, not job-doc scoring

Status: verified — **MERGED + deployed (English routing fix)**
Owner: Claude (release owner; owner directive 2026-07 — smallest P0 after read-only audit)
Branch: `fix/find-jobs-cv-routing` (merged, deleted)
Issue/PR: #1153 (merged as squash commit `14b2b2e63...`)

#### Objective

Fix the demonstrated English `/command` failure ("Find UAE jobs that match my CV"
→ "I don't have an uploaded job document yet") — smallest P0 fix.

#### Delivered

- Guard in `_handle_job_doc_action` so a score-intent that is an explicit job-listing
  request (`is_explicit_job_listing_request`) is not intercepted as job-doc scoring;
  production-path regression test; reused canonical public predicate (no broad except).

#### Deferred / not in scope

- **This was the English routing defect only — NOT a full authenticated
  route/API/database/storage/entitlement audit.** That full cross-route audit
  remains NOT STARTED. `_JOB_DOC_SCORE_RE` tightening (P1) deferred. (The Arabic
  equivalent was fixed separately in #1155.)

#### Verification

- Squash `14b2b2e`; CI green; production "Deploy to Production" (backend path) = success.

### TASK-20260717-008 — PR #1145: unify /command visuals with the shared WorkspaceShell

Status: verified — **#1145 PRODUCTION PASS** (merged main @ `ecd29a66`, deployed;
owner-confirmed on ricohunt.com 2026-07-17)
Owner: Claude (release owner; owner directive 2026-07-17 — "اعمل ما تراه مناسب"
after a completed read-only audit of #1145)
Branch: `fix/command-atelier-visual-consistency` (merged)
Issue/PR: #1145 (merged as squash commit `ecd29a66ac43301219ff04a3c5c7fe6b4711a33c`)

#### Objective

Visual/system unification only: make authenticated `/command` a clear part of
the Rico Workspace (shared `WorkspaceShell variant="app"`, single
`WORKSPACE_THEME` token source, light-first default with dark via the shared
toggle) with **zero** chat-behavior change — no endpoint, payload, streaming,
persistence, auth, or quota code touched. Implements DEC-20260717-001.

#### What changed

- `apps/web/components/command/CommandObsidianShell.tsx` — composes
  `WorkspaceShell variant="app"`; keeps only route-scoped console bar
  (status/panel toggles/account-logout), the 260px Sessions rail, and the
  rgba-aware CSS-var reply-surface layer derived from the ACTIVE shared palette
- `apps/web/components/command/commandAtelierTheme.ts` — **deleted** (copied
  token source; no duplicated palette remains)
- `apps/web/app/command/page.tsx` — chrome doc comment only, no logic change
- 3 command vitest specs repinned to the new contract (light default, shared
  palette, shared sidebar nav); composer hint raised ink40→ink70 for WCAG 4.5:1
- `AI_WORKSPACE/DECISIONS.md` — DEC-20260717-001 recorded

#### Verification

- CI on head `75cd1432` (post-rebase onto main `282660dd`): all 9 checks green
  (Setup, pytest, postgres-integration, frontend, playwright,
  workflow-security-guards, Create/Delete Neon Branch, Vercel) — no failures
- Local: `npx vitest run` 625/625; `npm run build` clean (`/command` 79.5 kB)
- Zero review threads / zero pending reviews; `mergeable_state: clean`
- Merged via squash with expected head SHA `75cd1432` → main now `ecd29a66`
- **Production: PASS** — owner confirmed `ricohunt.com/command` serves `ecd29a66`
  (light-first shared WorkspaceShell chrome, not the old forced-dark Obsidian
  console) on 2026-07-17

#### Continuity Block

- Task ID: TASK-20260717-008
- GitHub PR: #1145 (merged)
- Branch: `fix/command-atelier-visual-consistency` | Base: main @ `282660dd`
- Last safe commit SHA (main before merge): `282660dd`
- Current head SHA (main after merge): `ecd29a66`
- Uncommitted changes present: no
- Status: verified — PRODUCTION PASS (merge complete + owner-confirmed deploy)
- Files changed: see "What changed" above (frontend-only)
- Files intentionally not touched: `MobileCommandHeader` / `MobileBottomNav`
  (shared with public/legacy surfaces — documented follow-up); all backend;
  public/guest chrome
- What is complete: rebase, DEC entry, CI green, Ready flip, squash-merge,
  local-main sync to `ecd29a66`, owner-confirmed production deploy
- What is incomplete: none
- Known blockers: none (sandbox could not read production directly — private-repo
  403, unauthenticated Vercel MCP, egress to ricohunt.com proxy-blocked — so the
  production check was owner-run and confirmed PASS)
- Validation already run: full CI on `75cd1432` green; local vitest+build clean;
  owner-confirmed production PASS on ricohunt.com/command
- Validation still required: none
- Deployment/CI/Neon/Vercel state to check next: none
- Next exact action: none — task closed
- Stop condition: reached — production PASS confirmed
- Rollback plan: revert squash commit `ecd29a66` — restores
  `commandAtelierTheme.ts` and prior shell wholesale; no state/storage/API/env
  change involved

### TASK-20260717-007 — PR #1143: Paddle-only subscription checkout; remove manual/WhatsApp payment path

Status: verified — **#1143 PRODUCTION PASS** (merged main @ e903496, deployed)
Owner: Claude (WRITER; owner directive 2026-07-17 — "Proceed with #1143 only",
Paddle is the approved and only billing path)
Branch: `fix/subscription-paddle-runtime-ui` (merged)
Issue/PR: #1143 (merged as squash commit e903496)

#### Production smoke — PASS (owner-run on ricohunt.com, Paddle sandbox mode, 2026-07-17)

Seven-check gate, all confirmed with owner-supplied production evidence:

1. Paddle CTA "Subscribe with Paddle" / "اشترك عبر Paddle" visible (EN + AR) — PASS
2. No WhatsApp / manual-activation payment path or copy anywhere — PASS
3. Sandbox checkout completes (Paddle overlay "transaction completed") — PASS
4. Signed webhook processed (`POST /api/v1/billing/paddle/webhook`) — PASS
5. Neon subscription active (period end 2026-08-17) — PASS
6. `GET /api/v1/subscription/me` → `is_active: true`, plan `pro`, USD 21.50,
   Paddle customer + subscription IDs present — PASS
7. UI reflects Active/Current + "Manage Subscription" (Paddle customer portal) — PASS

Backend billing config confirmed live: `GET /api/v1/billing/config` →
`{"billing_mode":"paddle","paddle_active":true,"sandbox":true}`.

Real-money go-live (`PADDLE_SANDBOX=false` + live Paddle credentials on
Render/Vercel) is an OPTIONAL, owner-only dashboard step — NOT a prerequisite
for anything downstream. This smoke validated the flow end-to-end with Paddle
in sandbox mode.

#### Continuity Block

- Task ID: TASK-20260717-007
- Branch: `fix/subscription-paddle-runtime-ui` | Base: main @ c46a5fa (rebased
  from f2c801e; clean, PR files disjoint from the merged #1148/#1139/#1144/#1146 chain)
- Files changed: `apps/web/lib/billing.ts` (BillingUiMode narrowed to
  paddle|unavailable; legacy backend "manual" config now fails closed; removed
  isManualBillingMode/isPaddleBillingMode/buildWhatsAppUpgradeUrl/
  buildWhatsAppManageUrl; added buildWhatsAppSupportUrl — support contact only);
  `apps/web/components/subscription/SubscriptionAtelier.tsx` (all manual/WhatsApp
  CTA branches removed; FAQ always Paddle variants; intent always "paddle");
  `apps/web/lib/translations.ts` (EN+AR: removed continueOnWhatsApp,
  whatsappPaymentConfirm/UseEmail, all faq*Manual and dead faq*Stripe variants);
  `apps/web/components/settings/SettingsAtelier.tsx` (PaddleBillingSection no
  longer gated on build-time mode); `apps/web/components/layout/AppSidebar.tsx`
  (support link uses generic support prefill, no subscription-manage copy);
  `apps/web/lib/api.ts` (recordSubscriptionIntent billing_mode narrowed to
  "paddle"); `apps/web/components/billing/PaddleBillingSection.tsx` +
  `apps/web/.env.local.example` (stale NEXT_PUBLIC_BILLING_MODE docs removed);
  tests: billing-mode-resolution + subscription-atelier updated (legacy manual
  config → fail-closed; no wa.me anywhere; removed-exports guard)
- Files intentionally not touched: legal/contact/FAQ public pages (their
  WhatsApp mentions are company support contact info, not payment copy);
  backend billing (`src/api/routers/paddle_billing.py`, `src/billing_mode.py`)
  — untouched, backend remains the authority; `#1145` frozen per owner; no
  /command visual redesign
- What is complete: rebase to c46a5fa; Paddle-only removal; vitest 625/625;
  next build clean
- What is incomplete: push + fresh CI on head; owner merge decision
- Known blockers: production go-live needs Render BILLING_MODE=paddle +
  PADDLE_* secrets and Vercel NEXT_PUBLIC_PADDLE_CLIENT_TOKEN; until set, the
  page shows fail-closed "payment temporarily unavailable" (intended — never
  WhatsApp)
- Validation already run: `npx vitest run` 625/625 (66 files); `npm run build`
  clean
- Validation still required: full qa-tests CI on pushed head
- Next exact action: push branch, verify CI green, report to owner (no merge
  without owner approval)
- Stop condition: any CI failure beyond the known chat-confirm-profile flake →
  diagnose and report, no broad fixes
- Rollback plan: revert the squash commit — frontend-only, no API/DB/config
  migration; no env var change needed to roll back

### TASK-20260717-006 — #1076 delta: purge raw user/session ids from chat-stream and CV/profile exception logs

Status: review
Owner: Claude (WRITER; owner-approved single small security PR)
Branch: `fix/1076-stream-log-delta`
Issue/PR: #1076 residual delta (found by the 2026-07-17 reconciliation; #1137 closed superseded)

#### Continuity Block

- Task ID: TASK-20260717-006
- Branch: `fix/1076-stream-log-delta` | Base: main @ 6e95fd9
- Files changed: `src/api/routers/rico_chat.py` (13 log sites: 5 reconciliation
  sites + no-fields warning + 7 more logger.exception sites the new guard
  itself caught — all now log_privacy.user_ref + safe_exc, no tracebacks, no
  raw str(exc), CV filenames as lengths); `tests/test_1076_log_privacy.py`
  (module-scoped static guards + caplog proof on the 503 path)
- Intentionally not touched: ~65 raw `user=%s` sites in OTHER modules
  (follow-up hardening, mirrored on the _QUERY_ALLOWLIST precedent); no new
  helper (uses merged src/log_privacy.py); no policy-doc edit — the canonical
  #1076 block in OPERATING_RULES.md already mandates exactly this
- Validation run: extended suite 21/21; full local unit suite diffed against
  a fresh clean-main baseline — zero new failures
- Next action: owner review (queue position: before #1139 per owner order)
- Rollback: revert the squash commit — log text only, no behavior change

### TASK-20260717-003 — #1080: enforce multipart upload limits before full buffering

Status: review
Owner: Claude (WRITER; Coder pass, owner-directed "full ownership" of the
2026-07-17 reconciliation-audit remediation sequence)
Branch: `fix/1080-bounded-upload-reads`
Issue/PR: #1080

#### Objective

Stop unauthenticated/oversized uploads from forcing full-body buffering:
cap the raw request body at the app ingress before multipart parsing, and
replace unbounded `file.read()` with bounded chunked reads on both upload
surfaces.

#### Context

- Relevant files: `src/api/upload_limits.py` (new), `src/api/app.py`,
  `src/api/routers/rico_chat.py`, `src/api/routers/files.py`
- Existing behavior: both routes checked the multipart-declared `file.size`
  then called `await file.read()` — the advertised 25 MB/10 MB limits were
  enforced only after the complete payload was materialized.

#### Constraints

- Keep the global 25 MB document cap and the 10 MB image rule (applied after
  bounded magic-byte detection) exactly as advertised.
- Friendly 413 messages unchanged.
- No proxy/CDN changes (Render ingress is outside this repo).

#### Acceptance criteria

- [x] Missing/understated/chunked Content-Length stops at the cap
- [x] Peak bytes materialized bounded by limit + one chunk
- [x] Rejection never invokes classifier/parser/quota work
- [x] Temp file closed on rejection
- [x] Normal uploads and friendly messages unchanged

#### Required verification

- [x] Unit tests: `tests/test_1080_bounded_upload_reads.py` — 11 passed
      (wired into qa-tests.yml)
- [x] Regression: full local unit suite diffed vs clean-main baseline —
      only new failures were upload-route test fakes missing the real
      `read(size)` API; fakes fixed to model UploadFile correctly
- [ ] Frontend build: n/a
- [ ] Production/deploy smoke: normal CV upload + oversized rejection

#### Continuity Block

- Task ID: TASK-20260717-003
- GitHub issue/PR: #1080; draft PR from `fix/1080-bounded-upload-reads`
- Branch: `fix/1080-bounded-upload-reads`
- Base branch: main
- Last safe commit SHA: 5069447 (origin/main at branch cut)
- Current head SHA: see branch head on origin
- Uncommitted changes present: no (updated at push time)
- Status: review
- Files inspected: `src/api/routers/rico_chat.py` upload path,
  `src/api/routers/files.py`, `src/api/app.py` middleware stack,
  `tests/test_user_documents_dedup.py`, `tests/test_upload_size_limits.py`
- Files changed: `src/api/upload_limits.py` — BodySizeLimitMiddleware +
  read_upload_bounded; `src/api/app.py` — middleware registration;
  `src/api/routers/rico_chat.py` + `files.py` — bounded reads;
  `tests/test_1080_bounded_upload_reads.py` — 11-test suite;
  `tests/test_user_documents_dedup.py` +
  `tests/integration/test_user_documents_postgres.py` — upload fakes now
  model the real read(size) API; `.github/workflows/qa-tests.yml` — suite
  wired into CI
- Files intentionally not touched: Render/proxy ingress config (outside
  repo); concurrent-upload semaphore (rate limit already bounds request
  count — residual noted in PR)
- What is complete: ingress cap, bounded reads on both routes, tests
- What is incomplete: infrastructure-level (proxy) cap is an ops follow-up
- Known blockers: none
- Validation already run: new suite 11 passed; dedup + size-limit suites
  43 passed; full-suite diff vs baseline clean after fake fixes
- Validation still required: CI on the PR head
- Deployment/CI/Neon/Vercel state to check next: QA Tests on the PR
- Next exact action: owner review of the draft PR
- Stop condition: any legitimate ≤25 MB upload rejected by the ingress cap
  → raise MULTIPART_OVERHEAD_BYTES instead of weakening the bound
- Rollback plan: revert the squash commit — routes return to unbounded
  read; no schema/data change

### TASK-20260717-004 — #1092: replace fake 200-row application pagination with canonical DB paging

Status: review
Owner: Claude (WRITER; Coder pass, owner-directed "full ownership" of the
2026-07-17 reconciliation-audit remediation sequence)
Branch: `fix/1092-canonical-db-pagination`
Issue/PR: #1092

#### Objective

Move application filtering, pagination, counting, stats, and single-record
lookup to the database boundary over ONE canonical logical record set — no
200-row cap, no in-Python dedup, no page-scan PATCH lookups.

#### Context

- Relevant files: `src/rico_db.py` (canonical CTE + new methods),
  `src/repositories/applications_repo.py`, `src/api/routers/applications.py`,
  `src/services/subscription_gating.py` (count_saved_jobs)
- Existing behavior: get_all() always fetched the newest 200 rows, deduped in
  Python, then the router sliced pages from that snapshot; find_by_job_id
  scanned the same 200 rows; stats derived from the capped list; gating
  counted saved jobs from it.

#### Constraints

- get_all() keeps its list contract — chat/agent callers unchanged.
- Physical write paths (upsert/update/job_key schemes) untouched.
- No migration required: (user_id, job_key) uniqueness (011/035) already
  exists; dedup of legacy multi-key rows is a read-boundary rule.
- Data-correctness work only — no provider run, no deploy in verification.

#### Acceptance criteria

- [x] 451 logical records + duplicates: every record reachable exactly once
      across pages with correct total/pages (real Postgres)
- [x] A status existing only beyond row 200 filters and counts correctly
- [x] PATCH addresses the oldest owned row directly; other users' rows never
      visible
- [x] Stats and quota counts run uncapped over the SAME canonical set as
      the pages
- [x] Insert-between-page-reads behavior documented and proven (repeat
      possible, never a silent skip)
- [x] BUG-3 dedup semantics preserved, now proven against real SQL

#### Required verification

- [x] Unit tests: delegation-contract suite (rewritten
      `test_bug3_duplicate_kanban_entries.py`, CI-wired) + rewired
      isolation suites — all passing
- [x] Integration tests: `tests/integration/
      test_1092_applications_pagination_postgres.py` — 14 passed against a
      real local Postgres 16; wired into the postgres-integration CI job
- [x] Full local unit suite diffed vs clean-main baseline — zero new failures
- [ ] Production/deploy smoke: /applications page/total for a real account

#### Continuity Block

- Task ID: TASK-20260717-004
- GitHub issue/PR: #1092; draft PR from `fix/1092-canonical-db-pagination`
- Branch: `fix/1092-canonical-db-pagination`
- Base branch: main
- Last safe commit SHA: 5069447 (origin/main at branch cut)
- Current head SHA: see branch head on origin
- Uncommitted changes present: no (updated at push time)
- Status: review
- Files inspected: `applications_repo.py`, `rico_db.py`
  (get_recommendations/stats/upsert/schema), `routers/applications.py`,
  `subscription_gating.py`, the five mock-based test suites
- Files changed: `rico_db.py` — _CANONICAL_APPS_CTE +
  get_applications_page/count_applications/get_application_stats/
  find_recommendation + row-shaping refactor; `applications_repo.py` —
  get_all uncapped canonical, new get_page/count_by_status, DB-side
  get_stats, direct find_by_job_id, dead Python dedup removed
  (_VALID_STATUSES kept — Gmail route imports it);
  `routers/applications.py` — list route delegates to get_page;
  `subscription_gating.py` — count_saved_jobs uses canonical count;
  integration + rewritten unit suites; qa-tests.yml wiring
- Files intentionally not touched: write paths' job_key derivation
  (write-time canonical identity is a follow-up design), cursor-based
  pagination (documented stable offset chosen per the issue's alternative)
- What is complete: DB-boundary paging/counts/stats/lookup + full proofs
- What is incomplete: unifying job_key derivation at write time (would let
  the CTE collapse be retired eventually)
- Known blockers: none
- Validation already run: 14/14 real-Postgres; full unit suite = baseline
- Validation still required: CI on the PR head
- Deployment/CI/Neon/Vercel state to check next: QA Tests on the PR
- Next exact action: owner review of the draft PR
- Stop condition: any caller found relying on the old 200-row snapshot
  semantics → surface before merging
- Rollback plan: revert the squash commit — read paths return to the capped
  snapshot; no schema/data change in either direction

### TASK-20260717-005 — #1086: one scheduled pipeline; generated dashboard off main; deploy path filters

Status: review
Owner: Claude (WRITER; Coder pass, owner-directed "full ownership" of the
2026-07-17 reconciliation-audit remediation sequence)
Branch: `fix/1086-single-scheduled-pipeline`
Issue/PR: #1086

#### Objective

Retire the duplicate scheduled pipeline, put every pipeline run behind one
queued lock, stop generated dashboard commits to main, and path-filter the
deploy workflows so docs/generated-only changes can never redeploy the
backend.

#### Context

- Relevant files: `.github/workflows/daily.yml`, `daily-job-bot.yml`,
  `deploy-render.yml`, `deploy-production.yml`
- Existing behavior: both daily workflows ran the same crons (06:00/15:00
  UTC), same `src.run_daily` + `src.follow_up`, no shared lock; both pushed
  regenerated `docs/index.html` to main (legacy even under `if: always()`
  with `|| echo` swallowing push failures); every dashboard commit
  re-triggered both deploy workflows.

#### Constraints

- No workflow dispatched or run as part of the fix.
- Apply/auto-action flags stay off.
- Keep a manual fallback for the legacy pipeline (dispatch-only).

#### Acceptance criteria

- [x] Exactly one scheduled invocation owns run_daily + follow_up
- [x] Legacy workflow manual-only, sharing the SAME queued concurrency group
- [x] No workflow pushes to main; dashboard force-published to the dedicated
      `dashboard` branch only after pipeline success, failures loud
- [x] Deploy workflows auto-trigger only on runtime paths
- [x] OAuth temp files written from env vars, chmod 600, cleaned in always()
- [x] Static invariant suite enforces all of the above in CI

#### Required verification

- [x] Unit tests: `tests/test_1086_single_scheduled_pipeline.py` — 8 passed
      (CI-wired); `test_1084_workflow_guards.py` — 17 passed;
      `scripts/check_workflow_security.py` — OK, 16 files
- [x] YAML parse of all changed workflows
- [ ] Owner action after merge: point GitHub Pages at the `dashboard`
      branch `/docs` folder (one-time repo setting); until then the stale
      main copy of docs/index.html remains served

#### Continuity Block

- Task ID: TASK-20260717-005
- GitHub issue/PR: #1086; draft PR from `fix/1086-single-scheduled-pipeline`
- Branch: `fix/1086-single-scheduled-pipeline`
- Base branch: main
- Last safe commit SHA: 5069447 (origin/main at branch cut)
- Current head SHA: see branch head on origin
- Uncommitted changes present: no (updated at push time)
- Status: review
- Files inspected: the four workflows above, `workflow-guards.yml`,
  `scripts/check_workflow_security.py`, repo root (render.yaml,
  Dockerfile.backend)
- Files changed: `daily-job-bot.yml` — schedule removed (dispatch-only),
  shared lock, env-var+chmod OAuth handling with always() cleanup,
  dashboard-push and user-chat failure ping removed; `daily.yml` —
  workflow-level read permissions, env-var+chmod OAuth write, dashboard
  publish rewritten to force-push the dedicated `dashboard` branch (loud
  failure, success-only); `deploy-render.yml` + `deploy-production.yml` —
  runtime path filters; `tests/test_1086_single_scheduled_pipeline.py` —
  8 static invariants (CI-wired via qa-tests.yml)
- Files intentionally not touched: apply jobs' logic (flags stay off),
  error-notifications.yml (already owns admin failure alerts)
- What is complete: containment items 1–6 of the issue
- What is incomplete: full SHA-pinning of action refs (#127 scope)
- Known blockers: none
- Validation already run: invariants 8/8; guards 17/17; checker OK; YAML OK
- Validation still required: CI on the PR head; first scheduled run
  post-merge should be observed

#### Residual fix (2026-07-18): dashboard orphan suppresses Vercel deployments

Follow-up to the #1086 dashboard-publish mechanism, on branch
`claude/vercel-dashboard-deployment-hygiene-yy7pzi` (separate Draft PR).

- Symptom: the dedicated `dashboard` orphan branch still triggered the `web`
  Vercel project (Root Directory `apps/web`), which auto-builds every pushed
  branch. Because the orphan carries no `apps/web` app tree, every publish
  produced ERROR deployments (two per publish: GitHub + Neon integrations) —
  deployment-history noise, no product impact. One user/profile/locale? No:
  the branch is global generated output, so the fix is global.
- Fix: the `deploy-dashboard` publish step now also writes `apps/web/vercel.json`
  into the orphan branch with `git.deploymentEnabled.dashboard=false` (Vercel's
  officially supported per-branch switch). Vercel evaluates it at ingestion,
  before Root-Directory validation, so no deployment is created for the
  `dashboard` ref.
- Proven by a reversible test push (dashboard `f22d2e8`): Vercel created ZERO
  deployments for that SHA (baseline `bccf308` had produced two ERROR
  deployments); `docs/index.html` blob byte-identical; main Production READY
  and PR Previews READY throughout.
- Scope: `.github/workflows/daily.yml` `deploy-dashboard` step only. The
  generated `apps/web/vercel.json` exists ONLY on the `dashboard` orphan, never
  on main's source tree. No change to main's `apps/web/vercel.json`, Vercel
  project settings, Root Directory, or application code.
- Preserved: main → production, normal PR branches → previews, GitHub Pages
  from the `dashboard` `/docs` folder.
- Rollback: revert the squash-merge commit; the next scheduled publish emits an
  orphan without `apps/web/vercel.json`, restoring prior behavior.
- Verify on the next natural scheduled run (do NOT dispatch for this): new
  dashboard commit contains both files; no Vercel deployment for that SHA;
  Pages opens; main Production READY; a normal PR Preview READY.
- Deployment/CI/Neon/Vercel state to check next: after merge, confirm a
  dashboard-only publish does NOT trigger deploy-render
- Next exact action: owner review; after merge, flip GitHub Pages source to
  the `dashboard` branch
- Stop condition: if the Pages flip is undesired, revert to discuss an
  actions/deploy-pages artifact flow instead
- Rollback plan: revert the squash commit — schedules and publication return
  to the previous (duplicated) behavior

### TASK-20260715-002 — Atelier slice 4b: /command message bubbles + empty state

Status: review
Owner: Claude (WRITER; Coder pass, owner-directed)
Branch: `feat/atelier-command-message-bubbles-empty-state`
Issue/PR: draft PR (this slice); program: `ATELIER_FULL_SITE_MIGRATION.md` Step 2

#### Objective

Migrate only the /command message bubbles and empty state to the approved
Atelier direction (typography-first per the in-repo reference
`components/ui/rico/RicoMessageBubble.tsx`), authenticated surface only.

#### Continuity Block

- Task ID: TASK-20260715-002
- GitHub issue/PR: draft PR from `feat/atelier-command-message-bubbles-empty-state`
- Branch: `feat/atelier-command-message-bubbles-empty-state`
- Base branch: main
- Last safe commit SHA: baa427c (main @ branch cut; slice 4a merge)
- Current head SHA: see branch head on origin
- Uncommitted changes present: no (updated at push time)
- Status: review
- Files inspected: `app/command/page.tsx` (message map, empty state, chrome),
  `components/ui/rico/RicoMessageBubble.tsx` + `RicoMarkdownContent.tsx`,
  `components/workspace/theme.ts`, `components/atelier-kit/tokens.ts`,
  `e2e/command-composer-stability.spec.ts`, `__tests__/command-*`
- Files changed: `components/command/CommandMessages.tsx` (new — Atelier row,
  mark, markdown scope, empty state); `app/command/page.tsx` (wrapper swap
  only); `__tests__/command-message-bubbles.test.tsx` (new); this entry
- Files intentionally not touched: composer (#1028), chat API/streaming,
  job/action cards + `--rico-*` globals (4c), thinking/error states (4c),
  right rail (4d), mobile header + canvas background (4e), public surface
- What is complete: implementation; vitest 427/427; build green; composer
  e2e 4/4; visual gate 6 shots (EN/AR × desktop/mobile + empty ×2), 0px
  horizontal overflow measured on all
- What is incomplete: owner review of draft PR; merge (owner-gated)
- Known blockers: none
- Validation already run: `npm run build`; `npx vitest run` (full);
  `playwright test e2e/command-composer-stability.spec.ts` (chromium)
- Validation still required: owner visual approval on the PR; final-head CI
- Next exact action: owner reviews draft PR; on approval, merge; then 4c
- Stop condition: any change requested to job/tool cards or streaming states
  belongs to 4c — do not widen this PR
- Rollback plan: revert the single squash commit; no data/backend impact

### TASK-20260715-001 — Atelier migration: slice 4a — CommandComposer

Status: review
Owner: Claude (WRITER)
Branch: `feat/atelier-command-composer`
Issue/PR: #1028 (draft)

#### Objective

Rebuild PR #1028 as a real Atelier Command Composer migration (slice 4a only).
Replace the legacy extraction with a focused presentational `CommandComposer`
component that uses `WorkspaceThemeContext` palette tokens, adds the required
keyboard shortcuts (Enter, Shift+Enter, IME, Ctrl+K, Ctrl+J, Escape), and adds
29 tests covering all 13 required cases. Minimal diff in `page.tsx`.

#### Context

- Relevant files: `apps/web/components/command/CommandComposer.tsx`,
  `apps/web/app/command/page.tsx`, `apps/web/lib/translations.ts`,
  `apps/web/__tests__/command-composer.test.tsx`
- Relevant docs: `AI_WORKSPACE/ATELIER_FULL_SITE_MIGRATION.md`
- Existing behavior: all handlers and state live in `CommandPage` and are passed
  as props; no backend, streaming, or auth changes

#### Constraints

- Do not touch: other slices (empty state, message bubbles, tool cards, right
  rail, mobile header), backend/streaming/auth/billing
- No other routes touched
- Public/guest composer surface is unchanged in slice 4a

#### Acceptance criteria

- [x] Atelier authenticated surface: panel bg, ink, sun-red, mono hint
- [x] Public/guest surface unchanged
- [x] Enter sends, Shift+Enter newlines, IME guard, Ctrl+K, Ctrl+J, Escape
- [x] RTL mirroring for Arabic
- [x] 29 tests across 13 required cases — all green
- [x] `page.tsx` diff minimal: import, hidden-input removal, component swap
- [x] `npm run build` exit 0
- [x] Full vitest suite 416/416 green
- [ ] Playwright screenshots EN/AR desktop/mobile captured
- [ ] Owner visual review and approval

#### Required verification

- [x] Unit tests: `npx vitest run __tests__/command-composer.test.tsx` → 29/29
- [x] Full suite: `npx vitest run` → 416/416
- [x] Frontend build: `npm run build` → exit 0
- [ ] Playwright screenshots: EN desktop, EN mobile, AR desktop, AR mobile
- [ ] Owner visual review

#### Continuity Block

- Task ID: TASK-20260715-001
- GitHub issue/PR: #1028 (draft — do not merge)
- Branch: `feat/atelier-command-composer`
- Base branch: main
- Last safe commit SHA: 21ae19a7 (origin/main at branch reset)
- Current head SHA: fa6c6e24
- Uncommitted changes present: no
- Status: review
- Files inspected: `apps/web/components/workspace/theme.ts`,
  `apps/web/components/atelier-kit/tokens.ts`,
  `apps/web/components/atelier-kit/primitives.tsx`,
  `apps/web/components/workspace/WorkspaceShell.tsx`,
  `apps/web/app/_atelier/atelier-tokens.css`,
  `apps/web/app/command/page.tsx`,
  `apps/web/lib/translations.ts`
- Files changed:
  `apps/web/components/command/CommandComposer.tsx` (new — Atelier component);
  `apps/web/app/command/page.tsx` (import + hidden-input removal + swap);
  `apps/web/lib/translations.ts` (cmdAtelierPlaceholder + cmdAtelierHint EN/AR);
  `apps/web/__tests__/command-composer.test.tsx` (new — 29 tests)
- Files intentionally not touched: backend, streaming, auth, billing, other routes,
  message bubbles, empty state, tool cards, right rail, mobile header
- What is complete: component built, wired, tested, built, committed, force-pushed;
  backup branch `backup/pr-1028-legacy-extraction` pushed; PR #1028 branch updated
- What is incomplete: Playwright screenshots; owner visual review; PR description
  update (GitHub MCP write access denied — owner must update PR #1028 description manually)
- Known blockers: GitHub MCP 403 on PR update (token read-only); owner must update
  PR title/description manually or grant write access
- Validation already run:
  `npx vitest run __tests__/command-composer.test.tsx` → 29/29 ✅
  `npx vitest run` → 416/416 ✅
  `npm run build` → exit 0 ✅
- Validation still required: Playwright visual smoke (EN/AR desktop/mobile)
- Deployment/CI/Neon/Vercel state to check next: PR CI checks on fa6c6e24
- Next exact action: capture Playwright screenshots for EN desktop, EN mobile,
  AR desktop, AR mobile against local dev server, then add to PR
- Stop condition: do not merge without owner visual approval and Playwright screenshots
- Rollback plan: `git revert fa6c6e24` or reset branch to 21ae19a7

---

### TASK-20260714-001 — Atelier full-site migration REOPENED: refreshed gap matrix + next-PR routing

Status: review
Owner: Claude (WRITER; Planner pass)
Branch: `claude/atelier-fullsite-reopen`
Issue/PR: this docs PR (draft); execution then follows Steps 1→8

#### Objective

Owner reopened the full-site Atelier migration (supersedes the 2026-07-14 program
closure). Flip `ATELIER_FULL_SITE_MIGRATION.md` from CLOSED/DEFERRED to REOPENED,
re-audit the route matrix against live `main`, and route execution to the next
existing in-flight Atelier PR without duplicating work.

**Unified target (updated 2026-07-16, DEC-20260716-001):** the migration target
is now **Atelier V3 as the single production-wide visual system** across
marketing, auth, the authenticated workspace, and `/command`, with dark mode
"**Atelier at Night**" derived from the same semantic tokens. This is the same
program — not a parallel design doc — with the end-state pinned by
`DEC-20260716-001` (which supersedes the Atelier/Nocturne split of
`DEC-20260708-003` and the preview-only stance of `DEC-20260709-006`).

Migration order (foundation-first, `/command` last):

1. Foundation — Atelier V3 semantic tokens + Atelier-at-Night dark set as the
   single source of truth.
2. Shared shell & controls adopt V3 tokens.
3. Low-risk workspace routes (settings/profile/applications/jobs), per-route.
4. `/command` **last** — owner decided 2026-07-16 to **re-skin** the completed
   `/command` slices (C1 tokens, C2 transcript adapter, C3 composer, C4 MATCH
   cards) from Obsidian acid-lime to the Atelier Console tokens (paper +
   Atelier at Night, sun-red), sourced from the existing `/rico-preview`
   Atelier Console. Structure/behavior preserved; token re-skin, not a rebuild.
   Obsidian acid-lime is historical reference only; C4–C6 do not continue under
   Obsidian styling.
5. Visual QA — EN/AR + RTL, light/dark, desktop/mobile parity.
6. Remove legacy Nocturne tokens once unreferenced.

Nocturne is historical/archive; `/rico-preview`, `/design-gallery`, and
`/design-preview` stay internal reference-only. Every production API, auth,
upload, billing, persistence, streaming, and agent contract is preserved — this
is a visual-token migration only; Lovable/reference surfaces are visual reference
only, never a source of behavior.

#### Context

- Target: **every** production user-facing route on the approved Atelier design,
  not the original seven surfaces.
- `main` advanced past the Phase-0 audit base `c11575d` → re-audited @ `5cf9a6f`.
- Existing in-flight PRs mapped: #1026 (Step 1 preview hygiene, VALID — next),
  #1016 (Step 3 `/queue` guard-only), #1022 (Step 7 Paddle runtime).
- Out of scope (owner): #1024/#1025 memory engine; abandoned M1 postgres branch.

#### Constraints

- Docs-only in this PR; no route/component/backend/billing/Neon changes.
- Preserve completed routes; do not rebuild unless a per-route audit proves
  residual legacy UI.
- No direct push to `main`; small draft PRs cut from latest `main`.

#### Acceptance criteria

- [x] Program status flipped to REOPENED with owner directive recorded.
- [x] Route matrix re-audited from the live tree @ `5cf9a6f` (33 `page.tsx`).
- [x] Legacy-shell census recorded (`AppShell`, `DashboardShell` consumers).
- [x] Next existing Atelier PR identified (#1026, Step 1) and validity checked.

#### Required verification

- [x] Route audit: `find app -name page.tsx` + per-route shell grep + `next.config.js` redirects.
- [x] PR validity: #1026 base=`main`, Vercel preview green (bot checks are noise).
- [ ] Integration tests: n/a (docs-only).
- [ ] Frontend build: n/a (no `apps/web` code change).

#### Continuity Block

- Task ID: TASK-20260714-001
- GitHub issue/PR: docs PR (draft)
- Branch: `claude/atelier-fullsite-reopen`
- Base branch: main
- Last safe commit SHA: 5cf9a6f (live origin/main; owner-verified)
- Current head SHA: see branch head on origin
- Uncommitted changes present: no (updated at push time)
- Status: review
- Files inspected: all 33 `apps/web/app/**/page.tsx` routes, `next.config.js`
  redirects, open PR list (#1016/#1022/#1024/#1025/#1026 + unrelated), PR #1026 detail+status
- Files changed: `AI_WORKSPACE/ATELIER_FULL_SITE_MIGRATION.md` (REOPEN status +
  refreshed matrix + in-flight PR map); `AI_WORKSPACE/TASKS.md` (this entry)
- Files intentionally not touched: all `apps/web` route/component code; backend;
  #1024/#1025 memory work; abandoned `claude/m1-postgres-integration-tests-*` branch
- What is complete: reopen recorded; live gap matrix; next-PR routing to #1026
- What is incomplete: Steps 1→8 execution (starting by finishing #1026)
- Known blockers: none for this docs PR
- Validation already run: route/shell audit; #1026 base+status check
- Validation still required: owner ack of matrix; then execute Step 1 via #1026

### TASK-20260713-002 — Atelier migration program: parity matrix + first route PR (/applications)

Status: review
Owner: Claude (WRITER; activity pass: Planner → Coder)
Branch: `claude/atelier-migration-planning-mq6bt6`
Issue/PR: #1012 (draft; owner execution order 2026-07-13)

#### Objective

Own the Atelier Migration Program: publish the route parity matrix, migration order,
and component reuse report (`AI_WORKSPACE/ATELIER_MIGRATION_PROGRAM.md`), and land the
first implementation PR — migrate `/applications` off the legacy dark `/flow` page into
Workspace Shell C with an `ApplicationsAtelier` component.

#### Context

- Relevant files: `apps/web/app/applications/page.tsx`, `apps/web/app/flow/page.tsx`,
  `apps/web/components/applications/ApplicationsAtelier.tsx` (new),
  `apps/web/components/workspace/*`, `apps/web/components/atelier-kit/*`,
  `apps/web/lib/applicationStatus.ts`, `apps/web/lib/translations.ts`
- Relevant docs: `AI_WORKSPACE/ATELIER_MIGRATION_PROGRAM.md`, `DEC-20260710-002`,
  `DEC-20260712-001`, `AI_WORKSPACE/HANDOFFS/2026-07-10-design-preview-target-inventory.md`
- Existing behavior: `/applications` redirects to legacy Nocturne `/flow` (list/board,
  manual tracking, status updates) while Shell C's sidebar already links `/applications`.

#### Constraints

- Do not touch: Paddle/billing (`/subscription` logic, #1008 files), auth logic,
  backend/API contracts, legacy `app-nav.ts` `/flow` contract (redirect covers it).
- No migrations required.
- Keep scope limited to: the `/applications` route group + its tests + program docs.

#### Acceptance criteria

- [x] Parity matrix, migration order, and reuse report published.
- [x] `/applications` renders in Shell C with real data; `/flow` redirects to it.
- [x] Same API calls, translation keys, and status taxonomy (`STAGE_DEFS`) as before.
- [x] Existing flow behavior tests pass against the new page (import swap only).

#### Required verification

- [x] Unit tests: `npx vitest run __tests__/flow-manual-application.test.tsx __tests__/bug6-status-taxonomy.test.tsx`
- [ ] Integration tests: n/a (frontend-only)
- [x] Frontend build: `npm run build` in `apps/web`
- [ ] Local smoke: owner visual approval on the draft PR preview
- [ ] Production/deploy smoke if applicable: none — no deployment in this program step

#### Continuity Block

- Task ID: TASK-20260713-002
- GitHub issue/PR: #1012 (draft)
- Branch: `claude/atelier-migration-planning-mq6bt6`
- Base branch: main
- Last safe commit SHA: b753885 (main after #1010 merge)
- Current head SHA: see branch head on origin
- Uncommitted changes present: no (updated at push time)
- Status: review
- Files inspected: flow/upload/subscription/command/profile/settings/dashboard pages,
  workspace + atelier-kit components, applicationStatus lib, flow tests, PR triage docs
- Files changed: `AI_WORKSPACE/ATELIER_MIGRATION_PROGRAM.md` (new program doc);
  `AI_WORKSPACE/TASKS.md` (this entry);
  `apps/web/components/applications/ApplicationsAtelier.tsx` (new Atelier content);
  `apps/web/app/applications/page.tsx` (redirect → real Shell C page);
  `apps/web/app/flow/page.tsx` (legacy page → redirect);
  `apps/web/__tests__/flow-manual-application.test.tsx`,
  `apps/web/__tests__/bug6-status-taxonomy.test.tsx` (import/pathname re-point +
  stable useRouter mock — the fresh-object mock re-fired useAuth's effect
  forever once the page tree used useAuth, OOMing the vitest fork);
  `apps/web/__tests__/auth-guard.test.tsx` (new /applications guard block)
- Files intentionally not touched: `apps/web/components/layout/app-nav.ts` and
  `apps/web/__tests__/sidebar-nav-routing.test.ts` (legacy `/flow` nav contract; M4),
  `/subscription` + Paddle files (#1008 HOLD), `/command`, auth files
- What is complete: program docs; /applications migration; tests + build green
- What is incomplete: owner visual approval; M2–M6 (see program doc §2)
- Known blockers: none for M1; M5 blocked on #1008 + owner shell decision
- Validation already run: vitest (flow + bug6 + full suite) → pass; `npm run build` → pass
- Validation still required: owner visual review of draft PR; CI on PR head
- Deployment/CI/Neon/Vercel state to check next: PR CI checks after push
- Next exact action: owner review of draft PR; then claim M2 (/profile shell unification)
- Stop condition: any request to merge/deploy, touch billing/auth, or expand beyond the
  /applications route group → stop and ask the owner
- Rollback plan: revert the PR's commits (docs + route migration are self-contained;
  `/flow` redirect flip reverses cleanly)

### TASK-20260713-001 — Reconcile Rico control plane and record governed follow-up direction

Status: review
Owner: ChatGPT (writer) / independent review this session
Branch: `chore/agent-control-plane-reconciliation`
Issue/PR: #1010

#### Objective

Reconcile Rico's stale coordination layer with live GitHub state, establish the binding
execution sequence for interface completion, the one AED 79/month plan, invitations, and
controlled launch, and record (without expanding runtime scope) the governed long-term
direction for the Agent Operating System and the Rico-entity vision.

#### Context

- Relevant files: `AI_WORKSPACE/PROJECT_STATUS.md`, `AI_WORKSPACE/START_HERE.md`,
  `AI_WORKSPACE/DAILY_AUTOPILOT.md`, `AI_WORKSPACE/OPEN_PR_TRIAGE_2026-07-13.md`,
  `AI_WORKSPACE/LAUNCH_EXECUTION_PLAN.md`,
  `AI_WORKSPACE/HANDOFFS/2026-07-13-control-plane-reconciliation.md`,
  `AI_WORKSPACE/AGENT_OS_ROADMAP_AR.md`, `AI_WORKSPACE/VISION/RICO_ENTITY_AR.md`,
  `AI_WORKSPACE/FOLLOW_UPS/AGENT_OS_AND_RICO_ENTITY.md`
- Relevant docs: `AI_WORKSPACE/OPERATING_RULES.md` (canonical boot order)
- Existing behavior: previous workspace snapshot claimed a stale `60978ae…` main state;
  live main had already advanced through Atelier kit, Workspace Shell/dashboard, profile,
  settings, teaser/film, and verification-route fixes.

#### Constraints

- Do not touch: runtime application code, database migrations, environment configuration,
  deployment configuration, billing provider configuration, production data.
- No migrations: none required (docs-only PR).
- Keep scope limited to: control-plane/coordination documentation only.

#### Acceptance criteria

- [x] Open PRs classified (incl. Paddle PR #1008 held for #989 joint review; CI-housekeeping
      PR #988 held as non-launch).
- [x] `START_HERE.md`/`DAILY_AUTOPILOT.md` aligned with `OPERATING_RULES.md` canonical boot
      order (conflict found and corrected).
- [x] Branch-authority roles (WRITER/REVIEWER/RELEASE/IDLE) distinguished from activity-pass
      roles (Planner/Coder/Reviewer/Tester/Deploy verifier).
- [x] Agent OS roadmap and Rico-entity vision recorded as governed follow-up only (no runtime
      scope expansion; explicit "do not implement on ambition alone" gate).
- [x] This Continuity Block present in `AI_WORKSPACE/TASKS.md` before merge.
- [x] Final PR head/CI re-confirmed: head `255e0c69e8c5085233f28b214bfd498f915ef548` —
      pytest ✅ postgres-integration ✅ playwright ✅ frontend ✅ Vercel ✅ Create Neon Branch ✅.
      Independent review finding: stale next-action text (step 1 already done) — corrected
      in this truth-only commit.
- [ ] Independent approval + explicit owner merge approval obtained.

#### Required verification

- [ ] Unit tests: n/a (docs-only)
- [ ] Integration tests: n/a (docs-only)
- [ ] Frontend build: n/a (no `apps/web` files touched)
- [ ] Local smoke: n/a
- [ ] Production/deploy smoke if applicable: n/a — no runtime/production files in diff

#### Continuity Block

- Task ID: TASK-20260713-001
- GitHub issue/PR: #1010
- Branch: `chore/agent-control-plane-reconciliation`
- Base branch: `main`
- Last safe commit SHA: `7aa81aef1bb4ecd717372a40e3e571e96ae070b6` (base at branch creation)
- Current head SHA: `c56fa89e150e98e443f563a01abce6eeaca4b5f1` was the head before the origin/main
  merge; a commit cannot state its own resulting SHA in advance — verify the live PR head
  via `git log -1` or the GitHub PR page rather than treating this field as always-current
- Uncommitted changes present: no
- Status: review
- Files inspected: `AGENTS.md`, `CLAUDE.md` entry references, `AI_WORKSPACE/PROJECT_STATUS.md`,
  `AI_WORKSPACE/START_HERE.md`, `AI_WORKSPACE/TASKS.md`, `AI_WORKSPACE/OPERATING_RULES.md`,
  `AI_WORKSPACE/AGENT_OPERATING_MODEL.md`, open PR metadata, recent main commits
- Files changed: `AI_WORKSPACE/PROJECT_STATUS.md`, `AI_WORKSPACE/START_HERE.md`,
  `AI_WORKSPACE/DAILY_AUTOPILOT.md`, `AI_WORKSPACE/OPEN_PR_TRIAGE_2026-07-13.md`,
  `AI_WORKSPACE/LAUNCH_EXECUTION_PLAN.md`,
  `AI_WORKSPACE/HANDOFFS/2026-07-13-control-plane-reconciliation.md`,
  `AI_WORKSPACE/AGENT_OS_ROADMAP_AR.md`, `AI_WORKSPACE/VISION/RICO_ENTITY_AR.md`,
  `AI_WORKSPACE/FOLLOW_UPS/AGENT_OS_AND_RICO_ENTITY.md`, `AI_WORKSPACE/TASKS.md` (this entry)
- Files intentionally not touched: runtime application code, database migrations,
  environment configuration, deployment configuration, billing provider configuration,
  production data
- What is complete: see acceptance criteria above (checked items)
- What is incomplete: final-head re-confirm, independent review sign-off, owner merge approval
- Known blockers: do not merge while PR remains draft; do not merge without independent review
  and explicit owner merge approval
- Validation already run: branch-compare vs `main` (docs/control files only); origin/main
  merged (no conflicts); truth corrections applied (#1009/#1007 MERGED, #1011 CLOSED,
  TASK block blocker removed, #989 confirmed open, main baseline updated); head
  `255e0c69e8c5085233f28b214bfd498f915ef548` — pytest ✅ postgres-integration ✅ playwright ✅
  frontend ✅ Vercel ✅ Create Neon Branch ✅; independent review second pass: one finding
  (stale next-action step 1) — corrected in this truth-only commit
- Validation still required: final-head CI re-confirmation after this truth-only commit;
  independent approval; owner explicit merge approval
- Deployment/CI/Neon/Vercel state to check next: none — docs-only, no Neon/Render action
- Next exact action: confirm CI green on the truth-only commit head, then stop for
  independent approval and owner explicit merge approval — do not mark ready or merge without it
- Stop condition: stop and ask the owner before merge, production mutation, runtime
  implementation, or opening a parallel branch/Agent Registry/Task Leases track
- Rollback plan: revert PR #1010; no runtime or production rollback required

### TASK-20260710-003 — Migrate the full `/design-preview` package to production (shape + content + flows)

Status: scoped — REVISED 2026-07-10 to full-package scope per `DEC-20260710-002`
(was "Phase 1: landing below-the-fold"). Blocked on owner decisions listed below.
Owner: unassigned
Branch: docs on `docs/design-preview-target-inventory`; implementation branches TBD
Issue/PR: #933 (landing below-the-fold, **paused draft** — see below); governed by
`DEC-20260710-002` (expands `DEC-20260710-001`)

#### Objective

Reproduce the approved `/design-preview` package in production — same visual language,
sections, content structure, page flows, desktop/mobile behavior, and EN/AR coverage — via
small per-route PRs with an owner visual-approval gate before each merge. Authoritative
reference inventory: `HANDOFFS/2026-07-10-design-preview-target-inventory.md` (53 PNGs,
6-group hub tile inventory, live `/design-gallery` + `/rico-preview`). The uploaded PDF is
not present in the agent environment; the in-repo `/design-preview` source is authoritative.

#### Recommended PR sequence (safest first, per DEC-20260710-002 §4)

PR 0 shared Atelier UI kit → PR 1 public landing (full parity) → PR 2 auth → PR 3 support/legal
→ PR 4 onboarding (after hybrid-state fix, TASK-20260710-005) → PR 5 workspace read surfaces →
PR 6 workspace action surfaces (billing-gated) → PR 7 command/chat (own DEC).

#### #933 decision

Recommend: keep #933 as a draft reference and make PR 1 the full public-landing parity that
supersedes it (revise-in-place if the owner unfreezes the hero and rules on #899; otherwise

# 933 does not merge). Do NOT merge #933 as below-the-fold-only

#### Owner-gated decisions before implementation

- [ ] Unfreeze the landing hero for PR 1 + decide #899's fate.
- [ ] Canonical onboarding flow: reference intent-flow vs production CV-first.
- [ ] Adopt the reference workspace left-sidebar (Shell C) in production?
- [ ] Support contact form + auth Google button: omit (recommended) or greenlight as separate
      backend projects.
- [ ] Approve starting PR 0 (shared Atelier UI kit).

#### Constraints

- Excluded/gated (DEC-20260710-002 §3): `/command` (own DEC); no backend/auth/billing/Neon/
  schema without approval; legal copy preserved verbatim; no shadcn without its own DEC;
  no fake live actions; preview/sample data wired to existing endpoints or clearly labelled.
- One objective per PR; owner visual approval before every merge; single-revert rollback.
- Note: draft PR #899 (landing hero polish, held under the #871 freeze) overlaps the hero —
  hero parity work must reconcile with it.

#### Acceptance criteria

- [ ] Per-phase uniform acceptance in `DEC-20260710-001` §5 (build, no new test failures,
      EN/AR RTL, mobile, owner preview approval pre-merge, post-merge smoke).
- [ ] Lighthouse/CLS not worse than current landing; sitemap/robots/meta unchanged.

#### Rollback

Revert the PR → Vercel auto-redeploy → re-smoke landing.

### TASK-20260710-004 — P2: stale apply-link tests + `test_agent.py` absent from CI

Status: proposed (audit 2026-07-10; does not block rollout)
Owner: unassigned
Branch: TBD
Issue/PR: none yet

#### Objective

Three `tests/test_agent.py::TestApplyServiceIndeedMethod` tests encode the pre-trust-gate
link contract and fail on clean `main` (expect `success`/`manual_required`, get
`error: Job is missing a link` because the Phase-0 trust gate in
`src/services/job_link_trust.py` deliberately rejects non-source-backed URLs). CI's
`qa-tests.yml` pytest job never runs `tests/test_agent.py`, so this is invisible.
Test-only fix: update the 3 tests to the trust-gate contract (source-backed fixtures) and
consider adding `tests/test_agent.py` to the CI selection. Production behavior is correct
and unchanged (`RICO_ENABLE_AUTO_APPLY=false` in prod); do NOT weaken the trust gate.

#### Acceptance criteria

- [ ] `python -m pytest tests/test_agent.py -q` green on clean `main`.
- [ ] No `src/` behavior change.

### TASK-20260710-005 — P2: resolve `/onboarding` hybrid dead-UI state (Phase 4 gate)

Status: done (resolved via PR #955, merged + prod-deployed 2026-07-10; main `1238ff9` carries it)
Owner: Claude
Branch: `claude/onboarding-completion-signal-j8qmxz` (merged)
Issue/PR: #955

#### Objective

`next.config.js` redirects `/onboarding` → `/command` while a real 466-line
`apps/web/app/onboarding/page.tsx` still exists — the hybrid state prohibited by
`DEC-20260628-001` (No Dead UI rule). Owner decision then one small PR: either make the
route live (remove redirect) or strip `page.tsx` to nothing/thin passthrough. Must be
resolved before the Phase 4 onboarding-shell work in `DEC-20260710-001`.

#### Acceptance criteria

- [x] Route is in exactly one legal state per the No Dead UI rule — `/onboarding` is now
  live/reachable (the `/onboarding → /command` redirect was removed; page rewritten to the
  Atelier island), routing on the backend `GET /api/v1/onboarding/status` signal.
- [x] CLAUDE.md "Key Frontend Files" entry for onboarding matches reality afterwards —
  verified: `apps/web/app/onboarding/page.tsx — guided onboarding / CV-first flow` is still
  accurate for the live route.
- [x] `/onboarding` is the real authenticated first-run flow per `DEC-20260710-004`.

### TASK-20260711-001 — Auth guard for authenticated account pages (/settings, /profile)

Status: done (merged PR #958 → main `1238ff9`; production-verified 2026-07-11)
Owner: Claude
Branch: `fix/guard-authenticated-account-pages` (merged)
Issue/PR: #958

#### Objective

Guests could render the private AppShell (`/settings`) or fire a private request that showed
a misleading connection error (`/profile`). Add a shared `useRequireAuth` + `AuthGate` guard
so authenticated-only pages wait for auth readiness, redirect guests to
`/login?next=<encoded path>`, never render the private shell, and fire no private API for a
guest. No backend/JWT/cookie/logout change; `/command` stays public; `/onboarding` unchanged.

#### Acceptance criteria

- [x] guest `/settings` → `/login?next=%2Fsettings`, no shell, no private API — **prod-verified**
- [x] guest `/profile` → `/login?next=%2Fprofile`, no shell, no private request — **prod-verified**
- [x] authenticated users retain normal access; neutral `AuthGate` while resolving; no loop
- [x] resolves smoke findings **#2** (`/settings` auth-boundary) and **#5** (`/profile` error)
- Follow-up (NOT started): apply the same guard to `/applications`, `/upload`, `/flow`,
  `/queue`; and the login-return-path `next` gap is tracked as **#962**.

> **Binding sequence (recorded 2026-07-11; do not reorder):**
> `#960` → `#963` → owner production smoke → onboarding PARTIAL becomes **VERIFIED**.
> `#960` is merged and production-smoke verified via #969. `#963` is merged via #975 and its
> authenticated production smoke is **owner-confirmed PASS (2026-07-11)** — onboarding is now
> **VERIFIED**. `#962` remains a separate later increment and is the next objective.

### TASK-20260711-002 — Exact CV duplicate protection and idempotency

Status: done (merged as #969; production-smoke verified)
Owner: Claude / owner release verification
Branch: merged
Issue/PR: #960 / #969

#### Objective

Server-side exact-duplicate detection, atomic idempotency, quota safety, and primary-CV
invariants for CV uploads. Foundation only — **no onboarding wiring in this task**.

#### Acceptance criteria

- [x] server-side exact-duplicate detection for CV uploads
- [x] atomic idempotency (safe under retries/concurrent submits)
- [x] quota safety and primary-CV invariants preserved
- [x] no onboarding-confirmation wiring here (implemented separately by TASK-20260711-003)

### TASK-20260711-003 — Persist confirmed onboarding CV and hydrate extracted fields

Status: done (merged as #975; authenticated production smoke owner-confirmed PASS 2026-07-11)
Owner: Claude / owner authenticated smoke
Branch: merged as `241b85d…`
Issue/PR: #963 / #975

#### Objective

Wire the final onboarding confirmation to the canonical persistence path **after** the exact
dedupe/idempotency foundation (#960) exists: the confirmed onboarding CV persists to My Files
and extracted years / current role / target roles hydrate into the profile. This is what lifts
onboarding out of PARTIAL.

#### Acceptance criteria

- [x] onboarding confirmation persists the CV via the canonical path (built on #960)
- [x] extracted years/current-role/target-roles require durable Neon persistence; failures return non-2xx and retry is idempotent
- [x] final-submit persistence + logout→login completion smoke pass with a verified account (owner-confirmed 2026-07-11)
- [x] owner production smoke → onboarding status lifted PARTIAL → VERIFIED

### TASK-20260711-004 — Consume validated login return path (`next`)

Status: done (merged as #981; CI green, Vercel READY)
Owner: Claude
Branch: merged as `c7aea42…`
Issue/PR: #962 / #981

#### Objective

Independent auth-UX follow-up: make the login success handler safely consume the validated
`?next=<path>` return path (surfaced by the #958 guard, which sets `next` but the login flow
does not yet honor it). **Not part of the onboarding persistence work** — a separate later
increment under the current priority order.

#### Acceptance criteria

- [x] login honors a validated internal `next` (rejects external/`//`/non-`/` per
  `lib/redirect.ts::resolveNextPath`) and returns the guest to the original page
- [x] no open-redirect; no change to onboarding-status-based routing when `next` is absent

#### Verification

- vitest `login-onboarding-routing.test.tsx`: 7 passed (valid `next` honored, open-redirect
  ignored, onboarding-priority preserved for incomplete users)
- `npm run build` green; CI green (pytest/frontend/Playwright/Postgres); Vercel READY

### TASK-20260711-006 — Subscription gating identity-key invariant + audit follow-ups

Status: partial (test locked via #982; two follow-ups open for owner triage)
Owner: Claude / owner triage
Branch: merged as `60978ae…`
Issue/PR: #982

#### Objective

Harden the per-account subscription/plan gating surfaced by an owner question ("is plan
activation per account, per package?"). Confirmed: gating is per-account, package-driven,
active-and-not-expired gated, and not special-cased per account.

#### Done

- [x] Locked the identity-key invariant with tests: plan gating must key on the account email
  (`resolve_effective_user_plan` looks up by the stored email verbatim; a non-email identity
  silently degrades to FREE). Invariant holds at all current authenticated call sites.

#### Open follow-ups (each its own scoped PR when picked up)

- [ ] Per-user entitlement override columns (`monthly_ai_message_limit`, …) are read by
  `get_subscription`/`upsert_subscription` but **ignored** by `resolve_effective_user_plan`
  (documented as reserved). Either apply them or remove them to avoid a silent trap.
- [ ] `count_saved_jobs` fallback counts rows with no `user_id` toward a specific user's quota
  (data-isolation smell; only triggers when the primary repo read fails).

### TASK-20260710-006 — P2: frontend build gate + frontend test visibility baseline (Phase 3 gate)

Status: done (completed by TASK-20260710-008 B1–B5)
Owner: Claude / owner sign-off on B3/B4
Branch: merged follow-up sequence
Issue/PR: follow-up to #942; see TASK-20260710-008

#### Objective

19 pre-existing vitest failures across 9 files sit in exactly the surfaces Phase 3 reskins
(signup/auth/chat/landing/profile/signals). PR #942 fixed the shared `next/navigation`/
`LanguageProvider` test-crash class (test-config only, no component changes): baseline
went from 302 passed/19 failed to 309 passed/12 failed. The residual sequence in
TASK-20260710-008 then reached 320/0 and promoted both `npm run build` and `npm run test`
(Vitest) to required CI gates.

#### Acceptance criteria

- [x] Shared `next/navigation`/`LanguageProvider` test-crash class fixed via test-config
      only — no `apps/web` component/runtime changes (verified: diff is
      `vitest.setup.ts` + 2 test files + CI workflow + docs only).
- [x] `npm run build` wired into CI as a required, currently-green gate.
- [x] `npm run test` (vitest) promoted from informational to a required/blocking gate via
      TASK-20260710-008 B1–B5.

### TASK-20260710-007 — P2: authenticated production smoke path for agent sessions (Phase 3 gate)

Status: proposed (audit 2026-07-10; **blocks Phase 3** together with -006)
Owner: Roben (decision) + Claude (documentation)
Branch: n/a (process/credential task, not a code PR)
Issue/PR: none yet

#### Objective

Agent sessions have no approved smoke credentials, so login → `/me` → profile/settings →
authenticated `/command` (incl. auth-flash and "Sign in while logged in" checks) cannot be
verified without the owner. Owner decides: (a) provision a synthetic smoke account and
expose its credentials to agent sessions as env/secrets (never in repo), or (b) owner runs
the documented auth smoke per release. Document the chosen path in OPERATING_RULES.

#### Acceptance criteria

- [ ] Auth smoke runnable (by agent or documented owner procedure) before the Phase 3
      auth-shell PR merges.
- [ ] No credentials in repo/docs; synthetic account only; never a real user account.

### TASK-20260710-008 — Resolve residual frontend test failures before making vitest blocking

Status: done (B1–B5 all merged; suite 320/0 stable; vitest is now a required CI gate)
Owner: Claude (with owner sign-off on the B3/B4 YELLOW decisions)
Branch: `claude/career-terminology-audit-ojq1xl` (all five PRs)
Issue/PR: follow-up to #942; B1+B2 `test(frontend): resolve green residual vitest failures`,
B3 `fix(frontend): align chat action disabled reasons`, B4 `test(frontend): align sidebar routing
with current IA`, B5 `ci(frontend): make vitest a blocking gate`

#### Objective

`npm run test` (vitest) is wired into CI as informational-only (`continue-on-error: true`) after
PR #942 because residual tests still fail on clean `main`. This task tracks resolving them so
`npm run test` can be promoted to a required/blocking CI gate (the actual completion of
TASK-20260710-006). See `AI_WORKSPACE/HANDOFFS/2026-07-10-fe-test-health-ci-gate.md` and
`AI_WORKSPACE/HANDOFFS/2026-07-10-fe-green-residual-fixes.md` for full detail.

#### RESOLVED — PR B1+B2 (GREEN, test-only, merged/queued via `test(frontend): resolve green residual vitest failures`)

Baseline moved 309/12 → 317/4. All fixes were test-only (no product code):

- [x] `signup-auth-edge-cases.test.tsx` (2) — fixture bug: the 400/422 cases passed a non-empty
      `ApiError` message, so `mapSignupError`'s `err.message || checkDetails` rendered the message
      verbatim and never reached the generic fallback the test asserts. Fixed by using an empty
      backend message.
- [x] `command-auth-state.test.tsx` (2) — stale copy: the logout affordance is an accessible
      control labelled "Log out" (sidebar avatar button + mobile drawer item), never visible
      "Sign out" text. Updated assertions to query the `button` by accessible name `/log out/i`.
- [x] `landing-page.test.tsx` (1) — the whole hero/section copy block predated the landing
      rebuild; rewrote the copy assertions to match current shipped strings.
- [x] `chat-confirm-profile.test.tsx` (2) — race: `handleCVUpload` silently drops files while
      `chatAudience === "checking"`; the test uploaded before the mocked `/me` resolved. Added a
      wait for the public state ("Sign up free") before uploading.
- [x] `profile-name-edit.test.tsx` (1) — three coupled test-fixture issues: (a) the edit field
      seeds its draft from the current name so `userEvent.type` appended → added `user.clear()`;
      (b) `fetchProfile` has an extra caller (`useSidebarStatus` readiness hook) so the positional
      `mockResolvedValueOnce` chain mis-assigned values and the exact `toHaveBeenCalledTimes(2)`
      was wrong → switched to a state-based mock (name flips after `updateProfile`) and a
      before/after-save delta assertion; (c) the saved name renders in two surfaces →
      `findAllByText`.

#### RESOLVED — PR B3 (owner-approved YELLOW, merged via `fix(frontend): align chat action disabled reasons`)

Baseline moved 317/4 → 320/1. One scoped product-code touch (`ChatActionCard.tsx`) + one test update:

- [x] `chat-action-card.test.tsx` (3) — added an explicit `open_drawer → "Coming soon"` branch to
      `disabledReason()` (product), kept the `submit`-no-endpoint message
      `"No endpoint configured for this action"` as-is, and updated that test's expectation to the
      current (more useful) message. No other component behavior changed.

#### RESOLVED — PR B4 (owner-approved YELLOW, merged via `test(frontend): align sidebar routing with current IA`)

Owner decision: the `/queue` ("Applications") sidebar nav removal is **intentional** — do not restore
it; keep the `/queue` page itself untouched. Suite is now **320/0** (total dropped from 321 because
the obsolete nav-item test was removed, not "fixed"):

- [x] `sidebar-nav-routing.test.ts` — removed the obsolete `applications`/`/queue` nav-item lookup and
      its routing test (there is no longer a `/queue` sidebar nav item to assert a contract for). The
      `/queue` route is kept as a valid *origin* pathname in the other cases since the page still
      exists.
- [x] `AppSidebar.tsx` — removed the orphaned `NAV_ITEM_KEYS["/queue"]` entry (verified dead: both
      `NAV_ITEM_KEYS[item.href]` lookups run only over `mainNavSections`, which no longer contains a
      `/queue` item). No sidebar UX/rendering change.

#### RESOLVED — PR B5 (Autonomous GREEN, merged via `ci(frontend): make vitest a blocking gate`)

Fixed the pre-existing `scrollTo` full-suite flake and promoted vitest to a required CI gate:

- [x] `vitest.setup.ts` — added `HTMLElement.prototype.scrollTo` + `window.scrollTo` mocks (jsdom
      implements neither). The command page's `scrollMessagesPane` no longer throws inside a
      requestAnimationFrame callback, which was the cross-file flake source. Stability proven by 6
      consecutive clean full-suite runs (320/0 each).
- [x] `.github/workflows/qa-tests.yml` — removed `continue-on-error: true` from the frontend `Vitest`
      step; it is now a required/blocking gate alongside `npm run build`. `pytest`/`playwright`
      unchanged.

#### Status: DONE — frontend test-health arc complete

`309/12 → 317/4 (B1+B2) → 320/1 (B3) → 320/0 (B4) → 320/0 stable + vitest blocking (B5)`.

#### Constraints

- Do not touch: backend/API, auth/session internals, billing, schema/migrations, dependencies,
  AI provider/prompt/routing, #920.

#### Acceptance criteria

- [x] The 8 clearly test-only failures resolved without touching product code (PR B1+B2).
- [x] B3 (`chat-action-card`) resolved with owner sign-off (scoped product touch).
- [x] B4 (`sidebar-nav-routing`) resolved with owner sign-off (obsolete test + orphaned metadata
      removed; `/queue` nav stays removed, `/queue` page untouched).
- [x] B5: fixed the `scrollTo` full-suite flake in `vitest.setup.ts`, then promoted `npm run test`
      from informational (`continue-on-error: true`) to a required, green CI gate. Suite is 320/0,
      stable across 6 consecutive runs.

### TASK-20260710-002 — #929 `/design-preview` consolidation hub (one preview entry point)

Status: done (merged + production verified)
Owner: Claude
Branch: `feat/design-preview-hub` (merged, squash `9d47711`); docs sync on `claude/design-preview-hub-6o2ev5`
Issue/PR: #929 (merged)

#### Objective

Owner asked for one internal preview URL to review the whole Rico Atelier direction at once
instead of piece by piece. Shipped `/design-preview`: a noindex hub with a sticky
INTERNAL PREVIEW · SAMPLE DATA · ACTIONS DISABLED header, quick-jump nav, and six grouped
sections — live tiles (`/rico-preview`, `/design-gallery`, `/privacy`, `/refund-policy`,
terms) plus 53 labelled reference screenshots (EN/AR, desktop/mobile) covering landing,
auth, onboarding, authenticated workspace, support/legal, and
empty/loading/error/mobile/RTL states.

#### Continuity Block

- Scope: `apps/web/app/design-preview/{page,_client}.tsx` (new), 53 PNGs in
  `apps/web/public/design-preview/`, near-bottom-aware auto-follow in
  `apps/web/components/design-gallery/atelier-console/RicoConsole.tsx` (preview-only
  component). 56 files, +470/−1, one commit.
- Risk: low — additive noindex route + labelled static assets (~5.9 MB in `public/`) +
  contained scroll tweak. No production route/nav change; no backend/auth/billing/Neon/
  schema change; no new deps; no shadcn.
- Validation run: CI green on head `2fc729c` (pytest, playwright, Vercel deploy). The 19
  failing frontend tests are pre-existing `next/navigation` mock issues, confirmed
  identical on clean `main`. Post-merge production smoke PASS: `/design-preview`,
  `/rico-preview`, `/design-gallery`, `/privacy`, `/refund-policy`, landing all 200 on
  ricohunt.com.
- Rollback: revert #929 (squash `9d47711`) and let Vercel redeploy.

#### Merge provenance

Owner approved the draft merge in-chat; PR marked ready then squash-merged.

#### Next (owner-gated)

- Follow-up preview-only PRs by route group to turn the reference surfaces (landing, auth,
  onboarding, dashboard/profile/settings/applications/upload/pricing, support) into live
  interactive previews (shadcn-free rewrites of the Lovable screens).
- Any real `/command` production migration needs its own DEC + approved PR
  (`DEC-20260709-006`).

### TASK-20260710-001 — #908 RC1/RC4 fixes + Atelier Console direction (gallery, DEC, /rico-preview)

Status: done
Owner: Claude
Branch: multiple (all merged); docs sync on `docs/workspace-sync-2026-07-10`
Issue/PR: #914, #916, #921, #919, #924, #925, #926 (merged); #918 (closed); #920 (opened); #908 (closed)

#### Objective

Land the approved #908 attachment/Active-CV fixes, then explore the Atelier Console
as the candidate authenticated-workspace direction behind reference/preview surfaces —
without any production replacement or real actions.

#### What shipped (all owner-approved, merged unless noted)

- #914 — #908 RC1: widen attachment-follow-up regex → transcript-grounded handler.
- #916 — #908 RC4: prevent non-CV documents becoming the Active CV (`/upload-cv` +
  `/confirm-cv-profile`). Both RC1+RC4 confirmed by owner-run production smoke; **#908 closed**.
  RC2 (confidence wording) + RC3 (rejection taxonomy) deferred as separate items.
- #922/#923 — activation analytics (owner-authored); **production verified PASS** via a
  `weekly-admin-digest` `dry_run=true` Actions run (migration 036 applied; no email sent).
- #924 — Atelier Console isolated `/design-gallery` reference tab (Lovable "Atelier" port;
  light/dark, EN/AR, RTL, mobile; demo-only; actions reference-only; +lucide-react +3 fonts).
- #925 — `DEC-20260709-006`: Atelier Console = candidate workspace direction (preview only);
  amends `DEC-20260708-003` for exploration only. Nocturne stays production.
- #926 — internal `/rico-preview` route (noindex, reference-only) reusing the #924 console.
- #919 — dashboard-deploy CI fix (pull before regenerating `docs/index.html`).
- #921 — C2 privacy/refund handoff reclassified (stale brief rejected; ref zip → reviewed).
- #918 closed (command-concept gallery tab; superseded by #924; reviewed ref preserved).
- #920 opened — legal-review question for the shipped `/privacy` & `/refund-policy` copy.

#### Scope guardrails honored

- No production route/nav change; `/command`, `/rico`, `/` untouched. No real chat/job/apply/
  save/CV actions. No backend/auth/billing/Neon/schema change in the frontend/docs PRs.
- Not started: #917, #899, #872, #873, Phase 3, any production migration off Nocturne.

#### Next (owner-gated)

- Answer #920 (legal review of live privacy/refund copy).
- Any `/rico-preview` → production migration needs its own DEC + approved PR.

### TASK-20260709-004 — Sync #906/#907 merges + triage #908/#909

Status: done (docs-only sync/triage)
Owner: Claude
Branch: docs/908-909-triage-and-906-907-sync
Issue/PR: #906 (merged), #907 (merged), #908 (triage only), #909 (triage only)

#### Objective

Record that #906 (`profile_repo.py` connection-leak fix) and #907 (#758 job-key unification) are
merged and live (`main` at `ec06ef5`), and triage two new issues opened after the last
board-health scan: #908 (attachment-first orchestration bug, owner-flagged High) and #909
(governance-doc request, owner-flagged High).

#### Context

- Relevant files: none changed besides `AI_WORKSPACE/*`
- Relevant docs: `HANDOFFS/2026-07-09-board-health-scan.md` (last full scan, 34 issues, predates
  #908/#909), `HANDOFFS/2026-07-09-906-907-sync-and-908-909-triage.md` (full triage detail)

#### Constraints

- Do not touch: runtime code, tests, Neon, Vercel/Render config, issue labels/state, any
  `GOVERNANCE/` files
- No migrations
- Keep scope limited to: `AI_WORKSPACE/PROJECT_STATUS.md`, this file, the new handoff,
  `AI_WORKSPACE/MASTER_INDEX.md`

#### Acceptance criteria

- [x] #906/#907 merge state and production-READY status recorded in `PROJECT_STATUS.md`
- [x] #908 triaged: owner's own comments quoted verbatim (orchestration root-cause, not symptom
      patches); flagged as needing owner sign-off before a deep-dive is launched
- [x] #909 triaged: conflict with existing governance docs and the PR #901 precedent flagged;
      no `GOVERNANCE/` file created

#### Continuity Block

- Task ID: TASK-20260709-004
- GitHub issue/PR: #906 (merged), #907 (merged), #908 (triage only), #909 (triage only)
- Branch: docs/908-909-triage-and-906-907-sync
- Base branch: main
- Last safe commit SHA: ec06ef54d45f6ba81d7ee764e55a1bf8ffa94081
- Current head SHA: (this docs commit, no runtime change)
- Status: done
- Files changed: `AI_WORKSPACE/PROJECT_STATUS.md`, this file,
  `HANDOFFS/2026-07-09-906-907-sync-and-908-909-triage.md`, `AI_WORKSPACE/MASTER_INDEX.md`
- Files intentionally not touched: all runtime code, tests, Neon, Vercel/Render config, issue
  labels/state, any `GOVERNANCE/` files
- What is complete: sync + triage, both new issues read in full including #908's 2 owner comments
- What is incomplete: #908 orchestration deep-dive (not started, awaiting scope/cost approval);
  #909 governance decision (not started, awaiting owner direction)
- Known blockers: owner decision needed on both #908 scope and #909 reuse-vs-new
- Validation already run: `git log origin/main` (`ec06ef5` HEAD confirmed); `list_issues` +
  `issue_read` (34 → 36 open issues, #908/#909 confirmed new)
- Validation still required: none for this docs-only sync
- Next exact action: #812 proceeds per prior explicit approval (separate task); #908/#909 wait for
  owner direction
- Stop condition: do not start #908's investigation or write any `GOVERNANCE/` file without
  explicit owner approval
- Rollback plan: revert this docs-only PR; no schema/env/runtime changes

### TASK-20260709-003 — #446 Stage 1 data-integrity cleanup

Status: done (Stage 1 only — Stage 2 deferred, #446 stays open)
Owner: Roben (execution via a Neon-connector session) / Claude (precheck, documentation)
Branch: docs/446-stage1-cleanup (docs-only persistence PR)
Issue/PR: #446 (Stage 1 of 2)

#### Objective

Clean up the 16 `public:web-*` `rico_users` rows that were corrupted by the old `ON CONFLICT`
bug (root cause fixed in #445), without touching the 5 non-public rows sharing the same email —
those need separate review (Stage 2).

#### Continuity Block

- Task ID: TASK-20260709-003
- GitHub issue/PR: #446 (Stage 1 of 2; issue not closed)
- Branch: none for the cleanup itself (executed via a session with live Neon connector access,
  not a git branch); this entry is persisted via `docs/446-stage1-cleanup`
- Base branch: main
- Last safe commit SHA: b9563a78154743d0270586ce23326bc372be6192
- Current head SHA: b9563a78154743d0270586ce23326bc372be6192 (this task made no code commits)
- Status: done (Stage 1 only)
- Files changed: none by the cleanup itself; this docs-only PR changes `PROJECT_STATUS.md`,
  `CURRENT_STATE.md`, `TASKS.md`, `HANDOFFS/2026-07-09-446-stage1-cleanup.md`, `MASTER_INDEX.md`
- Files intentionally not touched: all runtime code, tests, schema, Vercel/Render config, issue
  labels/state; the 5 non-public `rico_users` rows (Stage 2, deferred)
- What is complete: Stage 1 precheck (fresh capture confirmed 16 target rows, primary excluded),
  Stage 1 `UPDATE` executed and committed, full post-cleanup validation passed
- What is incomplete: Stage 2 (5 non-public rows, including the primary) — not started, needs a
  separate review/decision before any mutation; #446 issue itself not yet updated/closed on GitHub
- Known blockers: none for Stage 1; Stage 2 requires manual inspection of 5 rows' `external_user_id`/
  `source`/`created_at` and cross-reference against Jotform/Telegram history before any decision
- Validation already run (via the Neon-connector session, not this session):
  before-count = 21 → capture confirmed 16 → primary-in-target-set = 0 → `UPDATE` on the 16
  explicit IDs → after-count = 5 → 16/16 target IDs confirmed `email IS NULL` → primary confirmed
  still `email = 'robenedwan@gmail.com'` → 0 orphaned `rico_chat_history` rows
- Validation still required: none for Stage 1 (complete); Stage 2 validation TBD once scoped
- Next exact action: Stage 2 review of the 5 non-public rows (separate task, no mutation without
  a fresh decision); independently, fix `profile_repo.py` connection leak → #758 → #812
- Stop condition: do not run any further Neon mutation without a new explicit owner approval
  scoped to that specific change; do not close #446 until Stage 2 is resolved or the issue is
  updated to reflect partial completion
- Rollback plan: `UPDATE rico_users SET email = 'robenedwan@gmail.com' WHERE id IN (<the 16
  manifest IDs>);` — full manifest and ready-to-run SQL in
  `HANDOFFS/2026-07-09-446-stage1-cleanup.md`

#### Full detail

See `AI_WORKSPACE/HANDOFFS/2026-07-09-446-stage1-cleanup.md` for the complete 16-ID rollback
manifest, before/after counts, and validation detail.

### TASK-20260709-002 — Security/data-risk deep dive on #127 and #198 (read-only)

Status: done
Owner: Roben / Claude
Branch: docs/security-data-risk-deep-dive (docs-only persistence PR)
Issue/PR: #127, #198 (read-only code-inspection deep dive; #263 deferred, not checked)

#### Objective

Verify, by direct code inspection against current `main`, whether the security/data-risk claims
in #127 and #198 (flagged "needs full deep dive" by the 2026-07-09 board-health scan) are still
live, before touching #758/#812/#446.

#### Continuity Block

- Task ID: TASK-20260709-002
- GitHub issue/PR: #127, #198 (read-only; #263 deferred)
- Branch: none during the deep dive itself (read-only); persisted via
  `docs/security-data-risk-deep-dive`
- Base branch: main
- Last safe commit SHA: d2bd86093a155b91522c4cb02e9cd6db23b498d2
- Current head SHA: d2bd86093a155b91522c4cb02e9cd6db23b498d2 (deep dive made no code commits)
- Status: done
- Files changed: none during the deep dive; this docs-only PR changes `PROJECT_STATUS.md`,
  `CURRENT_STATE.md`, `TASKS.md`, `HANDOFFS/2026-07-09-security-data-risk-deep-dive.md`,
  `MASTER_INDEX.md`
- Files intentionally not touched: all runtime code (read-only inspection only — `src/rico_db.py`,
  `src/repositories/subscription_repo.py`, `src/repositories/profile_repo.py`,
  `src/repositories/applications_repo.py`, `src/indeed_apply.py`, `src/run_daily.py`, `src/db.py`,
  `src/services/chat_service.py`, `.github/workflows/daily.yml`, `.env.example`,
  `requirements.txt`, `apps/web/components/auth/LoginForm.tsx`, `apps/web/app/subscription/page.tsx`
  were all read, none edited), tests, Neon, Vercel/Render config, issue labels/state
- What is complete: every named claim in #127 and #198 checked against current code (see handoff
  for the full per-claim table); no Codex/automated review was run — this was direct manual
  inspection only, and is not represented as a Codex-reviewed result
- What is incomplete: #263 (product-behavior contradiction claims) not yet checked — deferred per
  time constraints, same as the original scan noted; several lower-severity #198 findings (C3, C4,
  H1, H2, H4, M1–M7, L1–L4) not checked
- Known blockers: none
- Validation already run: `grep`/`Read` inspection of the specific files/functions named in each
  claim; cross-checked `profile_repo.py` call sites against the leak pattern documented in
  `rico_db.py`'s own code comment
- Validation still required: #263 deep dive (if picked up); the lower-severity #198 items listed
  above
- Next exact action: #446 read-only Neon precheck (count/identify affected rows, confirm #445
  root cause still holds, prepare transaction + rollback SQL) — no cleanup execution without
  explicit owner approval
- Stop condition: do not execute the #446 cleanup, or start #758/#812, or fix the `profile_repo.py`
  leak, until the owner has reviewed the precheck result and explicitly approves each next step
- Rollback plan: revert this docs-only PR; no schema/env/runtime changes, isolated to the 5
  workspace files above

#### Full detail

See `AI_WORKSPACE/HANDOFFS/2026-07-09-security-data-risk-deep-dive.md` for the complete per-claim
table (claim / file-function checked / status / severity / smallest-safe-fix / tests-needed /
rollback) for both #127 and #198.

### TASK-20260709-001 — Board-health scan (read-only)

Status: done
Owner: Roben / Claude
Branch: docs/board-health-scan-sync (docs-only state-sync PR)
Issue/PR: none (read-only board scan); persisted via this docs-only PR

#### Objective

Classify all 34 open GitHub issues (P0/P1/P2/P3/close-candidate/needs-deep-dive) using the
newly-active Rico Continuity Gate, so the next work item is chosen from evidence, not guesswork.

#### Continuity Block

- Task ID: TASK-20260709-001
- GitHub issue/PR: none (read-only board scan)
- Branch: none during the scan itself (no branch created — read-only); this entry is persisted
  via `docs/board-health-scan-sync`
- Base branch: main
- Last safe commit SHA: f6996b4da04f6d3812fe873067e89247c8bb165e
- Current head SHA: f6996b4da04f6d3812fe873067e89247c8bb165e (scan made no code commits)
- Status: done
- Files changed: none during the scan; this docs-only PR changes `PROJECT_STATUS.md`,
  `CURRENT_STATE.md`, `TASKS.md`, `HANDOFFS/2026-07-09-board-health-scan.md`, `MASTER_INDEX.md`
- Files intentionally not touched: all runtime code, tests, Neon, Vercel/Render config, issue
  labels/state
- What is complete: full metadata scan of all 34 open issues; full-body read + classification of
  18 issues matching risk trigger categories, plus #446 per explicit instruction; report delivered
- What is incomplete: #127, #198, #263 flagged "needs full deep dive" — classification pending
  actual code verification against current `main`, not resolved by this scan
- Known blockers: none
- Validation already run: `list_pull_requests` (4 open, all previously triaged),
  `search_issues`/`list_issues` cross-check (34 open, consistent counts across both calls)
- Validation still required: code-level verification for #127 (SQL injection claim in
  `src/rico_db.py#get_recommendations`), #198 (connection-leak claims in `rico_db.py`/
  `subscription_repo.py`, public-chat identity gap in `src/api/routers/rico_chat.py`), #263
  (product-behavior contradiction claims — check against #892/#747 fixes)
- Next exact action: security/data-risk deep dive on #127 and #198 (then #263 if time remains),
  per `HANDOFFS/2026-07-09-board-health-scan.md`; if live issues confirmed, fix those first; if
  stale/fixed, proceed to #446 (owner-gated cleanup) → #758 → #812
- Stop condition: do not start #758/#812/#446 until #127/#198 deep-dive verification is reported
  and the owner confirms priority; stop and report if deep dive finds a live, unpatched security
  issue rather than silently fixing it
- Rollback plan: revert this docs-only PR; no schema/env/runtime changes, isolated to the 5
  workspace files listed above

#### Full detail

See `AI_WORKSPACE/HANDOFFS/2026-07-09-board-health-scan.md` for the complete issue-by-issue
classification, top 10 risks, close candidates, and old-roadmap list.

### TASK-20260708-001 — Phase 3 chat integration: follow-up readiness query (first slice)

Status: done (merged #891 → `80e246b`; deploy verification pending — Render egress blocked from the working session)
Owner: Roben / Claude
Branch: feat/chat-followup-readiness (merged, squash `80e246b`)
Issue/PR: #891 — Engineering Roadmap Phase 3 (Chat Integration)

#### Objective

Let chat answer "what should I follow up?" / "which jobs are due for follow-up?" (EN + AR) by
reusing the merged #885 readiness logic (`get_by_status("applied")` → `select_revisit_candidates`,
the same reads behind `GET /api/v1/jobs/lifecycle/follow-ups`). No new lifecycle logic.

#### Scope

- Add `_FOLLOWUP_READINESS_RE` + `_handle_followup_readiness` in `src/rico_chat_api.py`; dispatch
  before `_FOLLOWUP_TIMING_RE` so timing questions are untouched.
- Out of scope: unifying `applications_repo` vs `user_job_context`; notifications; scheduler;
  migrations; UI; changes to "show my applications" / "opened but not applied" / timing advice.

#### Acceptance criteria

- [x] Follow-up readiness query routes to lifecycle readiness, not job_search or timing.
- [x] Empty state is safe (no fake success), EN + AR.
- [x] Existing lifecycle/timing/applications routes unchanged (regex non-hijack tests + 1264-test regression green).
- [x] `tests/unit/test_chat_followup_readiness.py` passes.

#### Follow-up

- [ ] Phase 4 / DEC-PR-B: reconcile the two application stores (`applications_repo` vs
      `user_job_context`) — deliberately out of this slice.

### TASK-20260707-001 — Phased architecture maturation roadmap (state-first, then migration/redesign)

Status: scoped (roadmap; each phase becomes its own scoped task + PR)
Owner: Roben / Claude
Branch: per-phase (this entry is the roadmap, not a single PR)
Issue/PR: DECISIONS.md → DEC-20260707-001

#### Objective

Mature Rico from a mixed-responsibility backend into a clean API + worker split with Neon as the
single source of truth, in ordered phases. Fix operational state (Rico must never forget what it
found, what the user opened, what was applied, and what needs follow-up) **before** any platform
migration or UI redesign.

#### Context

- Relevant docs: `AI_WORKSPACE/ARCHITECTURE.md` (Target architecture section), DEC-20260707-001,
  and the near-term execution gate `AI_WORKSPACE/AUDITS/2026-07-08-production-hardening-audit.md`
  (+ Codex follow-up). Read the audit before starting any feature/redesign/worker/infra work.
- Existing behavior: FastAPI on Render mixes request handling, temporary chat memory, and the
  job-search script; apply links / job context historically unreliable on Render's ephemeral disk.
- PR A persistence already exists on `main` (`user_job_context_repo.py`, migrations 018–022,
  `rico_chat_api.py` write/read paths, lifecycle routers) — so PR A is verify-first, not rebuild.

#### Constraints

- DEC-20260707-001 is the architecture-level roadmap; the 2026-07-08 production hardening audit is
  the near-term execution gate that controls immediate stabilization work.
- Smallest-safe-first; one phase per PR from current `main`.
- Do not start the UI redesign or the Render→Railway move until phases 1–4 land; Render stays the
  current production backend.
- Verify-first: fix only gaps proven via the audit's checks. No second implementation of job
  persistence.
- Verification/fixes use synthetic users and synthetic profile data only; no real-user smoke or
  mutation unless the owner explicitly approves a specific smoke run.
- Fixes must be global and user-agnostic (Product Generalization Rule), not per-account.

#### Phase order (each becomes its own scoped task; per-phase success criteria in DEC-20260707-001)

- [ ] Phase 1 (PR A, verify-first) — Persist job context + apply links (top-priority reliability fix;
      prove Audit Phase 2 gaps with synthetic data, fix only proven gaps, do not rebuild)
- [ ] Phase 2 (PR B) — Application lifecycle cleanup
- [ ] Phase 3 (PR C) — API / client consolidation
- [ ] Phase 4 (PR D) — Worker / cron separation
- [ ] Phase 5 (PR E) — Move backend from Render to Railway (Render stays production until Railway passes full smoke)
- [ ] Phase 6 (PR F) — Add monitoring / logging
- [ ] Phase 7 (PR G) — UI redesign (only after 1–6)

#### Required verification

- [ ] Per phase: focused unit tests + `apps/web` build where frontend changes; deploy smoke when
      runtime changes (per OPERATING_RULES.md).

<!-- Chat live-QA 2026-07-03 remediation (see AI_WORKSPACE/EVALS/2026-07-03-chat-live-qa.md). -->

### TASK-20260703-038 — Chat intent router over-triggers job_search (P0)

Status: proposed (verified 2026-07-04: TC-8 slice done; TC-11 + general fix still open)
Owner: unassigned
Branch: TBD
Issue/PR: chat-QA 2026-07-03 (TC-8, TC-11; contributes TC-4/TC-5) — TC-8 landed via #834/#835

#### Objective

Stop the intent dispatcher in `src/rico_chat_api.py` from routing to `job_search` on the mere
presence of a company/role token. Verb/sentence structure must decide the intent
("prepare me for an interview …" → coaching, not search).

#### Context

- Relevant files: `src/rico_chat_api.py` (`classify_intent` + `legacy_intent` dispatch from ~L7485).
- Existing behavior: company/role keywords appear to force `job_search` regardless of verb.

#### Acceptance criteria

- [x] "prepare me for an interview for <role> at <company>" routes to interview/coaching, not
      search — `_INTERVIEW_REQUEST_RE` guard + `_resolve_interview_prep_target`
      (`rico_chat_api.py`); confirmed green 2026-07-04 via
      `tests/test_tc8_interview_prep_grounding.py` + `tests/test_tc2_tc8_wiring.py`.
- [ ] "what is my profile?" does not flash a search first (TC-11) — not verified; frontend
      heuristic in `apps/web/app/command/page.tsx` was being reproduced when last checked,
      no confirmed verdict either way. Still open.
- [ ] Explicit search verbs (search/find/ابحث) still route to search — not independently
      re-verified against the TC-8 change.
- [ ] Regression: existing intent tests (#814 suite) stay green.

### TASK-20260703-039 — Application tracking from plain text + OCR (P0)

Status: proposed (verified 2026-07-04: TC-6 applied-confirmation OCR path partial — not the general acceptance; TC-7 plain-text slice open)
Owner: unassigned
Branch: TBD
Issue/PR: chat-QA 2026-07-03 (TC-7, TC-6) — TC-6 slice landed via #806/#807

#### Objective

Classify structured tracking text ("Position: X. Company: Y. Track it.") into the existing
`application_tracking` intent, and feed OCR-extracted entities into the tracking tool from
conversation context instead of re-running extraction.

#### Context

- `application_tracking` intent handler already exists (`rico_chat_api.py:4462`) — this is a
  classify/extract gap, NOT a missing feature. Do not build a parallel tracking path.
- OCR already extracts company/title (TC-6) but the tool call ignores it.

#### Acceptance criteria

- [ ] "Position: X. Company: Y. Track it." saves to the pipeline without a UI button (TC-7) —
      not verified as of 2026-07-04; still open.
- [~] Screenshot OCR entities are consumed by the tracking call for the "applied" confirmation
      case (TC-6) — partially addressed by #806/#807 "use screenshot OCR text for applied
      reports despite failed classification". This proves ONLY the applied-confirmation OCR
      entity path, NOT the general "OCR entities consumed by the tracking call" acceptance.
      Partially addressed; needs broader verification/test beyond the applied-confirmation path.
- [ ] Idempotent save (respects the BUG-14 upsert arbiter) — not independently re-verified here.

### TASK-20260703-040 — Relevance scoring + nationality-gate filtering (P1)

Status: proposed (verified 2026-07-04: TC-2 done; TC-1 badge still open)
Owner: unassigned
Branch: TBD
Issue/PR: chat-QA 2026-07-03 (TC-2, TC-1) — TC-2 landed via #834/#835/#844

#### Objective

Rank by function + seniority + skills overlap, not job-title keyword presence; flag/deprioritize
UAE-national-gated roles when the profile does not confirm eligibility.

#### Acceptance criteria

- [x] ESG/Compliance profile no longer surfaces software-engineering roles in top results (TC-2)
      — `relevance_floor` in `rico_chat_api.py` (~L5589); confirmed green 2026-07-04 via
      `tests/test_tc2_target_role_propagation.py` + `tests/test_search_title_relevance_floor.py`.
- [ ] "Priority for UAE nationals" roles carry a badge and drop out of top-ranked results unless
      eligibility is known (TC-1) — `is_uae_national` gate logic exists (`rico_chat_api.py:5424`)
      but no explicit badge/deprioritization confirmed. Still open.

### TASK-20260703-041 — Search session cache + dedup + render idempotency (P1)

Status: proposed (verified 2026-07-04: TC-3 render idempotency partial — diff-only, no test; TC-10 session cache still open)
Owner: unassigned
Branch: TBD
Issue/PR: chat-QA 2026-07-03 (TC-10, TC-3) — TC-3 landed via #815

#### Objective

Cache search results per session/query, dedup against already-shown jobs, and add an idempotency
key on message render to kill the double-render risk.

#### Acceptance criteria

- [ ] Repeat "search again" does not return a fully disjoint set with no explanation (TC-10) —
      not implemented; existing dedup (`rico_chat_api.py:5460`) is scoped to a single search
      call, not cached/deduped across the session. Still open.
- [ ] Already-shown jobs are not re-shown as new within a session (TC-10, same gap as above).
- [~] Message render is idempotent (no duplicate render on stream completing twice) (TC-3) —
      abort button + request dedup + 45s hard-timeout, #815
      (`apps/web/app/command/page.tsx`). Partially addressed: supported by diff inspection of
      the merged frontend change, but there is NO automated test proving render idempotency on
      double stream-complete. Partially addressed; needs broader verification/test.

### TASK-20260703-042 — Per-message language detection (P1)

Status: proposed (re-verified 2026-07-04: genuinely open — no per-message override found;
`_is_arabic_text` runs per-message for deterministic routing, but the LLM/conversational path
has no `detect_language`/language-override mechanism)
Owner: unassigned
Branch: TBD
Issue/PR: chat-QA 2026-07-03 (TC-9)

#### Objective

Detect language on the latest user message and reply in that language; add a persistent language
override in settings. Confirm this is not a regression from the #813 Arabic-guard move.

#### Acceptance criteria

- [ ] Switching to English mid-session gets English replies (TC-9).
- [ ] Arabic cold-start guard behavior (#813) is preserved.

### TASK-20260703-043 — Conversational UX gates (P2)

Status: proposed (re-verified 2026-07-04: genuinely open, no partial coverage found)
Owner: unassigned
Branch: TBD
Issue/PR: chat-QA 2026-07-03 (TC-4, TC-5, TC-12)

#### Objective

Confirm active targets before the first search after a target update (TC-4); re-ask disambiguation
on a bare "search" when target ambiguity was raised (TC-5); make "what can you do?" onboarding-safe
for cold-start/first-message users while keeping contextual answers when session data exists (TC-12).

#### Acceptance criteria

- [ ] First search after target update confirms the active targets.
- [ ] Bare "ابحث"/"search" re-triggers disambiguation when ambiguity is open.
- [ ] Cold-start "what can you do?" returns a structured capability overview.

### TASK-20260703-037 — Neon redundant-index cleanup (migrations 034 + 035)

Status: done
Owner: Claude (GitHub session)
Branch: claude/neon-db-index-cleanup-67ewh9
Issue/PR: #826 (034, merged), #828 (035, merged), #827 (closed dup)

#### Objective

Drop write-amplifying redundant duplicate/subset indexes on the Neon hot per-user
tables, and codify the covering full-UNIQUE that production carried but the repo
never created.

#### Outcome

- #826 merged: 034 drops 6 redundant indexes (each covered by a surviving index);
  `034` added to `_NO_OBJECT_MIGRATIONS`.
- #828 merged: 035 codifies `rico_job_recommendations_user_id_job_key_key`
  (idempotent) + adds a drift-check entry for it.
- Production apply owner-verified on Neon `production` branch: 0 redundant indexes
  remain (diff query); covering uniques present.
- Migration Drift Check workflow green on `b021273` (live DB has all signature
  objects incl. 035's constraint).
- Load-bearing indexes preserved: partial-unique arbiter (BUG-14),
  `idx_user_job_context_user_searched_at` (028 drift signature).

#### Follow-up

- [ ] Confirm any other Neon branch Render's `DATABASE_URL` may use also shows 0 rows.
- [ ] #712 005 remainder (keyword tables / view / enum / trigger) still to verify.

### TASK-20260703-036 — BUG-14: pipeline save idempotency (owner-gated migration)

Status: in_progress (migration 011 APPLIED 2026-07-03; only draft PR #784 + smoke remain)
Owner: a coder for #784 + owner authenticated smoke
Branch: — (PR #784)
Issue/PR: BUG-14; draft PR #784; migration drift #711

#### Objective

Make a second "save this job" a no-op (no counter increment) on both save paths.

#### Context

- Diagnosed 2026-07-03. The chat ordinal-save persists via
  `rico_db.upsert_recommendation`, whose `ON CONFLICT (user_id, job_key) WHERE job_key
  IS NOT NULL` requires the partial unique index from **migration 011**
  (`idx_rico_recommendations_user_job_unique`) — **APPLIED in production, owner-verified
  2026-07-03** via `pg_indexes`. So the chat ordinal-save path is now idempotent.
- The non-ordinal `jobs_service.save_job/skip/block` path dedups via the JSON-file
  `is_applied()`, which returns False for DB-backed SaaS users → duplicates. Fixed only
  in **draft PR #784** (`skip/save/block` → `applications_repo.find_by_job_id`), unmerged.
- Runbook for applying migration 011 safely (dedup DELETE + partial unique index):
  `docs/runbooks/production-drift-005-011.md` (Step A).

#### Constraints

- Migration is owner-gated and includes a destructive dedupe `DELETE` — apply only at the
  Neon console after the runbook's pre-checks. Sandbox cannot reach Neon.
- No new idempotency scheme; reuse the existing `save_key` / unique-index design.

#### Acceptance criteria

- [x] Migration 011 applied to production Neon (unique index present) — verified 2026-07-03.
- [ ] PR #784 reviewed + merged (non-ordinal path uses `applications_repo`).
- [ ] Owner smoke: "save the second job" twice → count +1 then unchanged; repeat on the
      non-ordinal save path.

---

### TASK-20260702-035 — JobFromAttachmentService: first-class job entities from attachments

Status: proposed (owner architecture note, 2026-07-02)
Owner: unassigned
Branch: —
Issue/PR: follows merged PR #807 (`c7d8343`)

#### Objective

Replace the #807 heuristic fallback with a first-class service that turns any attachment
transcript into a job entity and links it to the user's pipeline. Owner-sketched design:
`JobFromAttachmentService(attachment_text, user_id)` → `extract_job_entities` (company,
title, location — NER or stronger regex) → fuzzy/trigram match against the user's existing
pipeline jobs → create a new `JobAd` (`source_type="screenshot"`) when no match → build a
`JobApplication` with `confidence_source="user_confirmed_from_screenshot"` on user
confirmation.

#### Context

- PR #807 shipped the interim behavior: `_applied_from_screenshot_fallback` +
  `_extract_job_entities_from_transcript` in `src/rico_chat_api.py` (heuristics; one-click
  confirm / disambiguation buttons; no pipeline matching, no new entities).
- Known limits of the interim fix this service should close: no fuzzy match against
  already-tracked jobs (can create near-duplicates), heuristic extraction (role-keyword
  lists), no `source_type` provenance on the created record beyond `source="chat"`.

#### Constraints

- Keep `src/rico_safety.py` guardrails and the mark-applied confirmation gate.
- No schema change without owner sign-off (JobAd/JobApplication entities imply migrations).
- False-positive guard: never create an application without explicit user confirmation.

#### Acceptance criteria

- [ ] Screenshot of an already-tracked job matches the existing pipeline row (no duplicate).
- [ ] Screenshot of a new job creates one record with screenshot provenance.
- [ ] Multi-job screenshot produces a disambiguation step (parity with #807).
- [ ] CV / identity transcripts never produce job entities.

---

### TASK-20260702-033 — Enable personalized job-alert emails (PR-3, owner-gated)

Status: in_progress (migration applied + plumbing smoke done; activation still owner-gated)
Owner: unassigned (owner-gated enable steps)
Branch: —
Issue/PR: follows merged PR #805 (`f64e7e0`)

#### Objective

Turn on the opt-in job-alert emails shipped inert in PR #805. No new feature code required to
start; this is the enable + harden pass.

#### Context

- Feature merged and gated/inert. See `CURRENT_STATE.md` → "Email job alerts — PR #805".
- Key files: `src/services/email_alert_service.py`, `src/services/email_notifications.py`,
  `migrations/033_email_job_alerts.sql`, `.github/workflows/job-alert-emails.yml`.

#### Enable steps (in order)

- [x] Apply `migrations/033` to Neon (done 2026-07-02; both tables + idx_eal_user_sent /
      idx_eut_token + primary/unique indexes verified).
- [x] Plumbing smoke: `POST /api/v1/pipeline/job-alert-emails?dry_run=true` (X-Cron-Secret) →
      `{status: ok, users: 0, sent: 0, dry_run: true}` (2026-07-02). Endpoint deployed + cron
      auth OK + dry-run bypasses kill-switch without sending. (Optional GitHub-workflow path
      still needs `RICO_API_URL` / `RICO_CRON_SECRET` repo secrets if run via CI instead.)
- [ ] Match-quality smoke: opt in one test/owner account (`POST /api/v1/settings/email/opt-in`),
      re-run the dry-run; expect `users:1` and non-zero would-send or a match-related skip reason.
- [ ] Set `RICO_ENABLE_EMAIL_ALERTS=true` on Render.
- [ ] Enable the daily `schedule:` in `job-alert-emails.yml`.
- [ ] Monitor `email_alert_log` for the first sends; verify unsubscribe link end-to-end.

#### Hardening (address before/with scale — review findings #3/#5)

- [ ] #3 — cron runs live JSearch per user sequentially in a sync request: move to async/batched
      or a queue so large opt-in volume doesn't time out or exhaust JSearch quota.
- [ ] #5 — dedup opens a new DB connection per candidate job: fetch the user's already-sent
      job_keys once per user instead of per-job.

#### Follow-on

- [ ] Arabic (RTL) email localization (English-only in MVP).

#### Rollback

Unset `RICO_ENABLE_EMAIL_ALERTS` (runtime off), disable the workflow schedule; migration 033 is
additive and code tolerates the tables being present.

### TASK-20260630-032 — Rico UX Improvements: Search & Intent Flow (engineering spec, owner-authored)

Status: proposed (tracking task — spin each item into its own TASK-NNN when picked up)
Owner: unassigned
Branch: —
Issue/PR: docs-only (this ledger entry)

#### Objective

Capture the owner's engineering spec for chat/intent-flow UX so it is not lost in chat
history. Source: owner review of the conversational search/recommendation flow, reframed as
a directly-implementable spec ("لكنني سأعيد صياغتها لتكون Engineering Spec قابلة للتنفيذ
مباشرة بدون إدخال حلول قد تقيد التصميم" — agree with most points, but reframed as an
implementable engineering spec without baking in solutions that would constrain design).
Priority: P1 (Core Conversation UX). No implementation in this entry — docs/ledger only.

#### Source

Owner-authored spec, pasted verbatim into this session on 2026-06-30, titled "Rico UX
Improvements — Search & Intent Flow." Touches `src/rico_chat_api.py` (intent classification /
role intelligence pipeline), `src/services/chat_service.py`, and the public/`/command` and
`/chat` frontends. Any implementation must continue to respect `src/rico_safety.py` guardrails
and `src/agent/runtime.py` approval-gating — interrupting a pending confirmation flow must
never be used to bypass an approval-gated action (e.g. apply).

#### Backlog (spec sections, in the owner's priority order)

1. **Interruptible Conversation Flow** — a newly detected high-confidence intent should
   interrupt a pending confirmation flow instead of Rico continuing to wait on the stale
   question. Interrupt only when: intent confidence is high, the new intent differs from the
   pending confirmation, and the request is executable immediately. Do NOT interrupt when the
   user is answering the pending question or genuine clarification is required.
   Example: Assistant asks "What sounds best to you?"; user says "Find me a job" — Rico should
   immediately start the job search ("Got it. I'll start searching for jobs that match your
   profile.") rather than re-asking the original question.
2. **Search-first Principle** — for "Find me a job" / "Find jobs from my CV" / "Search jobs",
   the primary goal is to search immediately and return results, then offer improvements —
   not to pause for configuration questions first unless search is genuinely impossible
   without them. Preferred flow: Search → Return results → Offer improvements (not the
   reverse).
3. **Internal Terms Must Never Reach Users** — internal state labels (`STALE`, `DIRTY`,
   `NEEDS_REFRESH`, `LOW_CONFIDENCE_ROLE`, etc.) must be translated into natural language
   before reaching user-facing text. E.g. not "Target roles are STALE" but "Your saved target
   roles no longer fully reflect your current experience."
4. **Recommendation Confidence** — role recommendations should surface a match percentage
   (e.g. ESG Manager 96%, Compliance Manager 94%, Operations Manager 93%, HSE Manager 92%)
   with a brief explanation of why each role is recommended.
5. **Preserve Valid Existing Roles** — do not reject a user's saved role outright just because
   stronger matches exist; grade existing + recommended roles together (✅ Strong match / ✅
   Moderate match / ❌ Weak match) instead of a categorical rejection like "Logistics doesn't
   fit." Prefer comparative phrasing: "Logistics-focused roles are a weaker match than
   Operations, ESG, Compliance, and HSE positions based on your experience."
6. **Immediate Actions** — after recommendations, present executable actions (e.g. "Search
   these roles now", "Update my saved target roles", "Compare current vs recommended roles",
   "Keep my current target roles") instead of another open-ended question; these actions
   should execute immediately when chosen.
7. **Long-running Search Experience** — searching should show an elapsed timer and progress
   updates, with a single retry if appropriate. Target max wait: 20s. If the search can't
   complete in time, return partial results when possible; otherwise explain clearly
   (provider unavailable / timeout / retry available) rather than leaving the user waiting
   indefinitely.
8. **Preserve User Intent** — the user's original request must complete before optional
   improvements are offered. E.g. for "Find jobs from my CV": (1) search jobs, (2) return
   results, (3) suggest role improvements, (4) offer to save new target roles — never reverse
   this order.

#### Owner's overall assessment (verbatim)

"The current implementation demonstrates good profile reasoning and CV understanding. The
biggest remaining UX gap is execution flow: Rico identifies improvements well, but it
sometimes pauses for confirmation instead of completing the task the user explicitly
requested. Prioritizing task completion first, followed by optional optimization, will make
the assistant feel significantly more responsive and aligned with user intent."

#### Constraints

- Docs/ledger only in this entry — no code changes.
- Each numbered item becomes its own scoped TASK-NNN + branch when implemented. Do not start
  without explicit scope/branch assignment.
- Implementation must not weaken `src/rico_safety.py` guardrails or
  `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS` — "interruptible flow" (item 1) is about routing a
  new intent, not about skipping approval gates for high-impact actions.

#### Notes

- Logged per explicit owner instruction ("note the following as we need to work on it as
  well") on 2026-06-30, immediately after BUG-2/BUG-3/BUG-6 closure. Not yet prioritized
  against BUG-7/BUG-9/BUG-10/BUG-11.

---

### TASK-20260622-031 — PR C: strongest CV/profile selection + session-context retention

Status: done (merged as PR #801 `b94ec1f` on 2026-07-01, deployed; branch deleted)
Owner: Claude
Branch: `fix/profile-context-role-selection` (merged + deleted)
Issue/PR: PR #801

#### Objective

Fix the remaining production Tests 1 and 7 after the job-flow stabilization train (#727/#724/#723/#728/#729/#730).

#### Test 1 — ✅ fixed (pending PR/merge)

Prompt: `Find UAE jobs that match my strongest CV profile.`

Expected:

- Do not blindly use stale `target_role` such as Software Engineer.
- Use the strongest confirmed active CV/profile signal.
- If multiple profile tracks exist and confidence is ambiguous, ask the user to choose.
- Do not silently choose stale or irrelevant target_role.

Fix: search-first behavior in `job_search_profile_match` and the location-guard path of
`_classified_role_search` (`src/rico_chat_api.py`) — when a saved role is stale but the CV
yields a clear single-family suggestion list, search the top CV-evidenced role immediately
with an explanatory note instead of pausing to ask. Falls back to ask-to-choose when CV
suggestions are empty or span 2+ families. Commit `48e9cba` on `fix/profile-context-role-selection`.

#### Test 7 — ✅ fixed, already on `main`

Prompt: `Search UAE jobs for Environmental Manager.`

Expected:

- Do not silently substitute Environmental Manager with Environmental Officer.
- If exact role is unavailable, ask permission before broadening.
- Preserve authenticated user/CV/session context.
- Do not ask a logged-in Pro user with uploaded CV to sign up or upload again.
- Keep location UAE-focused with safe preference for UAE/Ajman/Dubai/Sharjah/Abu Dhabi.

Fix landed directly on `main` at `bd4c4f8` ("honor verbatim role text in classified role
search") — `_classified_role_search`'s `profile_relevant` branch now passes `role_text.strip()`
instead of the taxonomy canonical alias.

#### Constraints

- No auth rewrite.
- No billing changes.
- No DB migration.
- No #712 work.
- No landing-page work.
- No provider scraping.
- No repeated real provider searches.
- Use mocks/fixtures only in tests.
- Keep `src/services/job_link.py` as the only canonical resolver.
- Do not reintroduce `src/rico_link_resolver.py`.
- Do not touch unrelated chat flows.

#### Required process

- [x] Start from clean current `origin/main`.
- [x] Read-only map current CV/profile selection flow.
- [x] Read-only map where `target_role` is loaded.
- [x] Read-only map where auth/CV context is lost.
- [x] Read-only map where role substitution happens.
- [x] Report the smallest safe implementation plan before large edits.
- [x] Add regression tests for T1 and T7.
- [x] Open PR (merged as #801).
- [x] Run focused tests and related chat/profile tests — 27/27 in
      `tests/unit/test_profile_context_role_selection.py`; 143/143 across
      `test_bug17_pipeline_reset.py`, `test_bug12_arabic_search_locale.py`,
      `test_arabic_context_retention.py`, `test_apply_tracking_and_freshness.py`,
      `test_manual_application_tracking.py`, `test_lifecycle_followup.py`,
      `test_application_tracking_intelligence.py`, `test_p0_trust_fixes.py`.
- [x] Merge only if CI is green and scope is clean (merged #801, CI green).
- [x] Verify `/version` and `/health` after deploy (verified through the #806/#807/#808
      deploy chain — production at `a2a53b4`, health ok, 2026-07-02).

#### Handoff notes

- Latest full handoff: `AI_WORKSPACE/HANDOFFS/2026-06-22-job-flow-stabilization-complete.md`.
- Current production baseline before PR C: `38fbf5da19975df6f7d3d21168b137741d502e6d`.
- T1 fix source: an unmerged background session left the search-first behavior on
  `origin/claude/workflow-progress-check-qycxuo` (commit `52e44b8`) alongside T7 and TASK-030
  fixes that had already been hand-ported to `main` separately (`bd4c4f8`, `77563af`). Only the
  search-first hunks were hand-applied to `fix/profile-context-role-selection` — that branch
  also carried a stale `_build_tracking_message` hunk (pre-dating PR #797's opened/applied
  stage-count fix) which was intentionally NOT ported, since applying it would have regressed
  that fix. `claude/workflow-progress-check-qycxuo` has since been deleted as fully superseded.
- Rollback plan: revert the merge commit for `fix/profile-context-role-selection`; no
  schema/env changes, isolated to `src/rico_chat_api.py` chat-routing logic.
- Rollback plan: revert PR C only; no schema/env changes allowed.

---

### TASK-20260621-030 — CAREER-OS-04 remaining gap: inject uploaded document context into Rico AI prompt

Status: proposed
Owner: unassigned
Branch: —
Issue/PR: —

#### Objective

When a user uploads a non-CV document (offer letter, contract, cover letter, etc.) and then chats
about it, Rico currently has no access to the document type or content in its AI prompt. The upload
route now stores `last_uploaded_document` in `recent_context` (fixed in PR #717), but the chat
handler does not yet inject this into the AI system prompt or message context.

#### Existing behavior after PR #717

- Explicit meta-queries ("what did I upload?", "document type?") → answered from `recent_context`
  without an AI call via `_get_recent_upload_document_reply`.
- All other messages about the document (e.g. "can you review it?") → falls through to normal AI
  routing with no document context injected.

#### Required change

In `rico_chat_api.py` `_process_message_inner` or the AI context builder, check for
`last_uploaded_document` in `recent_context` and if the document is non-CV and recent (< 24h),
inject a brief note into the system prompt / user context:

```
[Uploaded document: {label} ({filename}) — confidence {pct}%]
```

This lets the AI model answer "can you review it?", "summarize this offer letter" etc. with
context about what was uploaded.

For non-trivial document types (offer_letter, contract, cover_letter), also check whether the
document content is available in the user's parsed files (via `user_documents` DB table) and
include a brief extract if available.

#### Constraints

- Do not touch: the document classifier, the upload route, `_get_recent_upload_document_reply`
- No migrations required
- Must not break existing job-search or onboarding flows
- Add regression tests for the injection path

#### Acceptance criteria

- [ ] User uploads a cover letter → types "can you review my cover letter?" → Rico responds
  with content-aware review (not generic advice)
- [ ] User uploads an offer letter → types "summarize it" → Rico summarizes using the document type
- [ ] No regression in job-search or onboarding flows (all existing tests pass)

---

### TASK-20260621-029 — System quality audit: bug fixes and technical debt documentation

Status: review
Owner: Claude
Branch: `claude/system-quality-audit-ikkamf`
Issue/PR: #717 (draft, CI green — pytest ✅ playwright ✅ Vercel ✅)

#### Objective

Continuous codebase audit across auth, DB, repositories, services, migrations, and routers —
fix small isolated bugs immediately, document larger issues for separate PRs.

#### Bugs fixed (all in commit `3c11717`)

1. **`src/repositories/users_repo.py`** — `list_active_users()` omitted `email_verified` from
   SELECT; all User objects silently defaulted to `email_verified=True`. Fixed by adding
   `COALESCE(email_verified, TRUE)` as column 8 and accessing as `row[7]`.

2. **`src/repositories/audit_repo.py`** — `List` used in type annotations for
   `log_profile_hydration` and `_db_write_profile_hydration` but not imported;
   `typing.get_type_hints()` would raise `NameError`. Fixed by adding `List` to
   `from typing import …`.

3. **`src/api/auth.py`** — Duplicate `response.delete_cookie()` call in `register()`
   (second call at lines 580-583 was dead code, identical to lines 482-485). Removed.

4. **`tests/test_users_scheduler.py`** — Mock fixture rows were 7-element tuples; crashed with
   `IndexError: tuple index out of range` after the `users_repo` fix added an 8th column.
   Updated both rows to 8-element tuples.

#### Issues documented (separate PRs required — do NOT touch without explicit scope)

| # | Issue | File | Recommended action |
|---|---|---|---|
| D1 | Runtime DDL bypasses migration system | `audit_repo.py` | Move 3 table creates to numbered migrations |
| D2 | `_DEDUP_CACHE` unbounded memory growth | `audit_repo.py` | Add periodic sweep or size cap in `_mem_seed` |
| D3 | Safety regex over-breadth (`password`, `bypass`) | `rico_safety.py` | Narrow with word-boundary anchors + regression tests |
| D4 | No password complexity enforcement | `src/api/auth.py` | Add length + complexity check at register and reset |
| D5 | No JWT revocation after password reset | `src/api/auth.py` | Token blacklist or rotating JWT family ID |
| D6 | `mark_webhook_event_processed` Optional[str] for UUID FK | `src/rico_db.py` | Validate UUID or change signature to Optional[UUID] |

#### Acceptance criteria

- [x] `list_active_users()` returns correct `email_verified` value from DB
- [x] `audit_repo.py` imports `List` — no `NameError` from `get_type_hints()`
- [x] No duplicate cookie deletion in `register()`
- [x] Test fixture updated to 8-element tuples
- [x] All CI checks green (pytest, playwright, Vercel, Neon)

#### Required verification

- [x] pytest ✅ (all 6 CI checks passed on PR #717)
- [x] playwright ✅
- [x] Vercel ✅ (DEPLOYED)
- [x] No regressions vs main baseline

#### Handoff notes

- Changed files: `src/repositories/users_repo.py`, `src/repositories/audit_repo.py`,
  `src/api/auth.py`, `tests/test_users_scheduler.py`, `AI_WORKSPACE/CURRENT_STATE.md`,
  `AI_WORKSPACE/TASKS.md`, `AI_WORKSPACE/START_HERE.md`
- Rollback plan: revert PR #717 — no DB schema changes, no migrations, no env changes.
- Full detail: `AI_WORKSPACE/HANDOFFS/2026-06-21-system-quality-audit.md`

---

### TASK-20260619-028 — UI/UX live-audit backlog (2026-06-19)

Status: proposed (tracking task — spin each item into its own TASK-NNN when picked up)
Owner: unassigned
Branch: —
Issue/PR: docs-only (this ledger entry)

#### Objective

Track the prioritized recommendations from the 2026-06-19 live production UI/UX audit so they
are not lost in chat history. Full detail (problem + fix + mockups) lives in
`docs/audits/ui-ux-live-audit-2026-06-19.md` (shipped via #658); this entry is the actionable
backlog distilled from it.

#### Source

Direct live audit of `ricohunt.com` covering `/command`, `/flow`, `/profile`, `/upload`,
`/settings`, `/subscription`, and the global sidebar. 20 recommendations, prioritized by
impact vs. effort. `ref` below = the section id in the audit doc.

#### Backlog (grouped by audit impact)

Critical:

- [x] 1-A — Replace A/B/C/D typed options with clickable inline action buttons. DONE via PR #678.
- [x] 1-B — Real fit-score badge on job cards (e.g. "82% match") + skills/gaps/location breakdown. DONE via PR #679.

High:

- [x] 1-D — Sidebar widgets load on every mount. DONE via TASK-20260619-027 / PR #658.
- [ ] 2-D — "Mark as Applied" inline CTA button on Link-opened cards.
- [ ] 3-B — Surface profile conflict warnings as a top-of-page banner.
- [ ] 5-A — Input validation: City (UAE list), Target roles (max 3–4), excluded-vs-target keyword warn.
- [ ] 1-C — Search timeout/countdown indicator with reliable fallback buttons (30s).
- [ ] 3-A — Profile completeness score: single source of truth (sidebar 71% vs profile 54%).

Medium:

- [x] 6-A — Navy/indigo design system. DONE via PR #641 (v4 tokens, `6fac4c0`); live + smoke-PASS 2026-06-20.
- [ ] 2-A — Demote "Link Opened" from a primary pipeline stage to card metadata.
- [ ] 4-A — CV role-mismatch warning banner on My Files.
- [ ] 6-B — First-use onboarding checklist (dismissable).
- [ ] 1-E — Cold-start amber banner ("Rico is starting up ~45s").

Low:

- [ ] 6-D — Move WhatsApp support to a floating help icon; free the sidebar for navigation.

Additional (in the audit body, outside the top-14 priority table):

- [ ] 2-B — Drag-and-drop between pipeline columns / larger stage pill.
- [ ] 2-C — Collapse zero-value pipeline stat boxes; lead with Applied/Interview/Offer.
- [ ] 3-C — "Active CV" indicator chip on the Profile page.
- [ ] 4-B — CV parse-confidence indicator + "Review parsed data".
- [ ] 5-B — Fit-score slider guidance text (explain what 80% hides).
- [ ] 6-C — Visual hierarchy: make "Ask Rico" the dominant sidebar action.

#### Constraints

- Docs/ledger only in this PR — no code changes.
- Each item becomes its own scoped TASK-NNN + branch when implemented. Do not start without
  explicit scope/branch assignment (per the Operating target in `CURRENT_STATE.md`).

#### Notes

- Per the audit, 1-A is the biggest UX win for the least effort — likely first to spin out.
- Sourced solely from the in-repo 2026-06-19 live audit doc. If a separate/larger UI/UX
  review exists, append its items here rather than starting a parallel list.

---

### TASK-20260619-027 — Sidebar status widgets: retry after failed cold-start load

Status: done (verified — production smoke PASS 2026-06-20)
Owner: Claude
Branch: `fix/sidebar-status-retry-653` (merged → `712be79` via PR #658)
Issue/PR: #658 (replaced #653, which was closed/superseded)

#### Objective

Stop the desktop sidebar READINESS/PIPELINE widgets from showing permanent blank grey boxes
when navigating back to a page after a cold-start (backend-idle) load.

#### Root cause

`useSidebarStatus` cached failed/empty cold-start loads for 60s. When the backend was cold,
all sources resolved to `null`, that empty result was cached, and subsequent remounts served
the stuck nulls — so the widgets stayed blank on navigate-back.

#### Fix (PR #658, merged `712be79`, 2026-06-19)

- `loadStatus()` uses `Promise.allSettled` and throws when both core reads (profile + stats)
  reject, so a failed cold-start is never cached and the next mount retries.
- Cached successes are served instantly and revalidated (stale-while-revalidate) to avoid flicker.
- Sidebar shows a retry affordance when status can't load (`navStatusRetry`, en + ar); the chip
  calls a TTL-bypassing `refresh()`.
- Changed files: `apps/web/hooks/useSidebarStatus.ts`,
  `apps/web/components/layout/AppSidebar.tsx`, `apps/web/lib/translations.ts`,
  `docs/audits/ui-ux-live-audit-2026-06-19.md` (audit doc).

#### Verification

- `npm run build` green; CI (pytest + playwright) green on #658.
- Production smoke PASS (2026-06-20): widgets render on mount, repopulate instantly on
  navigate-back (SWR), skeleton→data on hard refresh. Retry chip not exercised (Render warm —
  `status.error` only flips when both core reads reject on a cold mount); rendering path is
  covered by build + the both-locale `navStatusRetry` key. Smoke table recorded on PR #658
  (issuecomment-4756899519).

#### Notes

- Addresses audit item 1-D (see TASK-20260619-028).
- This is NOT TASK-024 — earlier chat shorthand mislabeled it. TASK-024 is BUG-04. The sidebar
  fix had no ledger ID until this entry, which closes that gap.

---

### TASK-20260619-026 — BUG-05: Public-chat onboarding infinite loop

Status: review
Owner: Claude
Branch: `claude/ai-workspace-review-vtdjrb`
Issue/PR: (draft PR created 2026-06-19)

#### Objective

Fix the `/command` public chat returning identical "Welcome to Rico AI…" on every message
after the first, and the double API call from the streaming fallback guard.

#### Root cause

Three compounding issues:

1. `IntentRouter` sends most messages (not starting with `?` / question word / "show me") to
   the legacy classifier.
2. Legacy classifier always returns the onboarding welcome when `profile is None`, and never
   saves state for public sessions (`_persist=False`), creating an infinite loop.
3. Frontend `if (!streamStarted)` fallback fired even when the legacy path already applied a
   response via the SSE `"done"` event — causing a duplicate API call.

#### Fix summary

- **Fix A** (`src/services/chat_service.py`): `_force_ai` gate redirects public no-profile
  legacy decisions to `_conversational_ai_reply`.
- **Fix B** (`src/api/routers/rico_chat.py`): streaming endpoint only takes legacy path when
  `profile is not None`.
- **Fix C** (`apps/web/app/command/page.tsx`): fallback guard changed to
  `!streamStarted && !responseApplied`.
- 7 unit tests in `tests/test_public_chat_no_profile_loop.py` (all PASS).

#### Acceptance criteria

- [x] Public user messages (interview prep, profile data, injection) route to AI, not welcome
- [x] Public user WITH existing profile still routes to legacy (unchanged)
- [x] Authenticated users unaffected (legacy for no-profile, AI for AI-decision)
- [x] No duplicate API call from streaming fallback
- [x] 7 unit tests passing

#### Required verification

- [x] Unit tests: 7/7 PASS (`tests/test_public_chat_no_profile_loop.py`)
- [ ] Frontend build: node_modules not installed in this environment; change is a 1-line guard
- [ ] Render deploy: pending PR merge
- [ ] Production smoke: pending PR merge

#### Handoff notes

- Changed files: `src/services/chat_service.py`, `src/api/routers/rico_chat.py`,
  `apps/web/app/command/page.tsx`, `tests/test_public_chat_no_profile_loop.py`
- Risks: `_force_ai` gate is additive; authenticated users and public users with profiles
  are unaffected. Rollback: revert `_force_ai` conditional in `send_message`.
- Open: #653 sidebar retry still draft; unrelated to BUG-05.

---

### TASK-20260716-001 — Gmail M0 read-only connector

Status: done — merged; inactive in production
Merge/runtime state (explanatory, not a status value): #1055 merged into `main`
        2026-07-17; the feature is INACTIVE — `RICO_ENABLE_GMAIL_SYNC=false` and
        migration 043 not auto-applied (see reconciliation below).
Owner: Windsurf (REVIEWER → WRITER for blocker fixes);
       post-merge reconciliation by Claude (2026-07-17)
Branch: `feat/gmail-readonly-connector-m0` (merged, head `a10a6493`)
Issue/PR: #1055 — MERGED 2026-07-17T08:32:45Z by Binz2008-star,
          merge commit `bcd71c2`, 19 files (+3497/-3), 15 commits

#### Post-merge reconciliation (audited on `main` `900972c`, merge commit `bcd71c2`)

The three P1 review blockers were tracked against the pre-merge draft head
(`dd595a3b`); the branch then advanced to `a10a6493` (15 commits) before merge.
Audited the exact MERGED code + tests on `main` `900972c` (not the PR body or the
old ledger). Result: blockers 1 and 3 are RESOLVED in the merged head; blocker 2
is PARTIALLY RESOLVED — the backend privacy gate is fully implemented, but fleet
activation remains blocked by a missing user-facing consent flow (recorded as a
separate pre-fleet task, TASK-20260717-009). Migration 043 is not auto-applied at
startup (it is absent from the startup auto-apply list —
`migrations/043_gmail_connections.sql:7-11`), so its production application remains
blocked pending a fresh owner-approved Neon verification; `RICO_ENABLE_GMAIL_SYNC`
remains `false` by default (`test_status_shape_flag_off`,
`tests/test_gmail_connector_m0.py:149-163`), so nothing in this feature is live.
Validation:
`pytest tests/test_gmail_connector_m0.py` → 36 passed. This reconciliation is
docs-only — no code, migration, secret, or flag was touched.

#### Objective

First-party OAuth Gmail read-only connector (M0): connect, bounded inbox sync,
recruiter-thread detection wired into existing review machinery. Everything OFF
by default behind `RICO_ENABLE_GMAIL_SYNC=false`.

#### Roadmap traceability

```text
Vision          AI_WORKSPACE/PROJECT_BRIEF.md — UAE-focused career companion
   ↓
Epic            Career Operating System
   ↓
Milestone       Email Integration
   ↓
Phase           4 — Lifecycle Intelligence
   ↓
PR              #1055 — Gmail read-only connector M0
   ↓
Task            TASK-20260716-001 (this entry)
```

#### Continuity Block

- Task ID: TASK-20260716-001
- GitHub issue/PR: #1055 (draft)
- Branch: `feat/gmail-readonly-connector-m0`
- Base branch: main (`f2267b37`)
- Last safe commit SHA: `f2267b37` (main at branch cut)
- Current head SHA: `a10a6493` (final branch head, merged into main as `bcd71c2`)
- Audited-on SHA (post-merge reconciliation): `900972c` (main after #1145)
- Uncommitted changes present: no
- Status: done — merged; inactive in production (flag OFF; migration 043 not
  auto-applied — production application pending a fresh owner-approved Neon check)
- Files inspected: `src/gmail_importer.py`, `src/services/gmail_sync_service.py`,
  `src/services/gmail_oauth.py`, `src/services/token_crypto.py`,
  `src/api/routers/integrations_gmail.py`, `src/repositories/gmail_repo.py`,
  `migrations/043_gmail_connections.sql`, `scripts/check_migration_drift.py`,
  `render.yaml`, `src/api/app.py`, `src/api/rate_limit.py`,
  `tests/test_gmail_connector_m0.py`, `tests/test_users_auth.py`
- Files changed:
  - `scripts/check_migration_drift.py` — registered 043 signature objects
  - `src/services/gmail_sync_service.py` — bounded pagination (`_fetch_messages_bounded`)
  - `tests/test_gmail_pagination_bounds.py` — 8 new pagination/budget tests
  - `tests/test_users_auth.py` — JWT_SECRET 32+ chars in production-mode test
  - `.github/workflows/gmail-sync.yml` — removed (fleet activation is later PR)
  - All other files are from the original PR branch
- Files intentionally not touched: `requirements.txt` (deps already present),
  `docs/integrations/gmail-readonly-connector.md` (design doc, not code)
- What is complete:
  - Branch re-anchored on main `f2267b37`
  - `gmail-sync.yml` removed
  - Migration 043 drift checks registered + 5 regression tests pass
  - Bounded listing: deadline, 10-page cap, 500-candidate cap, repeated-token guard
  - 8 pagination/budget tests pass
  - Test-order pollution fixed (auth test 500 → pass)
  - 26 connector tests pass, 540 vitest pass, frontend build green
  - GitHub required CI all green on head `dd595a3b`
- What is incomplete (post-merge): the user-facing recurring-sync consent control
  (blocker 2 UI half — TASK-20260717-009); independent security/privacy review;
  isolated migration-043 verification on a throwaway Neon branch; limited
  real-account OAuth test with a tester allowlist. These are activation gates, not
  merge blockers — the code is on `main`, inactive.
- Blocker verdicts (audited on `main` `900972c` / merge commit `bcd71c2` — code +
  tests, not comments; the 3 P1 blockers were originally logged on `dd595a3b`):
  1. **Privacy/revocation — RESOLVED.** `/status` resolves the real connection
     unconditionally and reports `connected` independent of the flag
     (`src/api/routers/integrations_gmail.py:88`, `:101-115`; repo
     `src/repositories/gmail_repo.py:64`), and `/disconnect` is deliberately
     ungated (`integrations_gmail.py:182-193`). Frontend keeps a live connection
     visible and Disconnect always enabled while the flag is off
     (`apps/web/components/settings/GmailConnectionCard.tsx:118-133` and
     `:231-241` — Disconnect `disabled={busy}` only, never the flag). Regression:
     `test_status_reports_connection_even_when_flag_off`
     (`tests/test_gmail_connector_m0.py:166-191`) — asserts `connected:true` +
     `sync_enabled:false` + Disconnect 200 with the flag off.
  2. **Consent/scope — PARTIALLY RESOLVED.** *Backend privacy gate implemented;
     fleet activation remains blocked by missing user-facing consent flow.*
     Backend substrate complete: consent column `recurring_sync_consent_at`
     (`migrations/043_gmail_connections.sql:39`, idempotent add `:51-52`,
     consent-scoped sweep index `:66-69`); JWT-scoped grant/revoke
     `POST /consent` (`integrations_gmail.py:199-228`) →
     `set_recurring_sync_consent` (`gmail_repo.py:270-306`); the fleet query
     selects only consented rows — `list_active_connections`
     `WHERE status = 'active' AND recurring_sync_consent_at IS NOT NULL`
     (`gmail_repo.py:88-117`). Tests: `test_fleet_sweep_query_requires_consent`
     (`tests/test_gmail_connector_m0.py:573`), `test_consent_grant_round_trip` /
     `test_consent_revoke_round_trip` (`:489`, `:506`),
     `test_manual_sync_does_not_require_recurring_consent` (`:630`).
     **GAP (still open):** the Settings UI exposes NO control to grant or revoke
     this recurring-sync consent — `GmailConnectionCard.tsx` renders only
     Connect / Sync / Disconnect and never imports the existing
     `setGmailRecurringSyncConsent` helper (`apps/web/lib/api.ts:968`). Tracked as
     separate pre-fleet task **TASK-20260717-009**. NOT implemented here (docs-only).
  3. **Trust/idempotency — RESOLVED.** Approval is a single atomic conditional
     claim — `claim_review_item_for_approval` runs one
     `UPDATE ... SET review_status='approved' WHERE user_id=%s AND id=%s AND
     review_status='pending' RETURNING ...` so exactly one racer wins
     (`gmail_repo.py:583-622`); the router claims before applying and reverts the
     claim on apply failure (`integrations_gmail.py:336`, `:349-352`), and the
     status apply is itself idempotent. Regression:
     `test_double_approve_applies_status_exactly_once` — second racer 409s,
     `update_status.call_count == 1`, revert not called
     (`tests/test_gmail_connector_m0.py:393-426`).
- Validation already run (pre-merge):
  - `pytest tests/test_gmail_connector_m0.py` → 26/26 passed
  - `pytest tests/test_gmail_pagination_bounds.py` → 8/8 passed (bounded-pagination fix)
  - `pytest tests/unit/test_migration_drift_checks.py` → 5/5 passed
  - `npm run build` → 41/41 pages · `npm test -- --run` → 540/540 · CI green
- Validation re-run (post-merge reconciliation, `main` `900972c`):
  - `pytest tests/test_gmail_connector_m0.py` → 36/36 passed
- **Merge gates — SATISFIED (merged 2026-07-17).** For the record: blockers 1 and
  3 were fixed with tests; blocker 2's backend gate was fixed with tests (its UI
  half is a pre-fleet activation gate, TASK-20260717-009). Independent
  security/privacy review, isolated migration-043 verification, and a real-account
  OAuth test were NOT bundled into the merge and remain owner-gated activation
  prerequisites below.
- **Activation gates (SEPARATE — the feature is INACTIVE until every one is met;
  owner-gated; nothing here is unblocked by the merge):**
  - Google restricted-scope verification / CASA for `gmail.readonly` on the public domain.
  - Provision `GMAIL_TOKEN_ENCRYPTION_KEY` + Google OAuth creds in Render.
  - Apply migration 043 to Neon production — not auto-applied at startup;
    production application remains blocked pending a fresh owner-approved Neon
    verification (no retained in-session evidence of a production table check).
  - **User-facing recurring-sync consent flow before enabling `/sync-all`** — the
    backend gate exists, but no Settings control does; blocks any fleet sweep.
    Tracked as TASK-20260717-009.
  - Independent (non-author) security/privacy review + isolated migration-043
    verification on a throwaway Neon branch + limited real-account OAuth test.
  - Flip `RICO_ENABLE_GMAIL_SYNC=true` last, per-cohort.
- Next exact action: none for M0 code (merged). Before any fleet activation, land
  TASK-20260717-009 and clear the remaining activation gates above, owner-gated.
- Stop condition: do not deploy/activate, apply migration 043, provision secrets,
  add a fleet workflow, or enable `RICO_ENABLE_GMAIL_SYNC` without explicit owner
  approval.
- Rollback plan: revert merge commit `bcd71c2` on `main`; no production impact
  either way (flag is OFF; migration 043 not auto-applied).

---

### TASK-20260717-009 — Gmail recurring-sync consent: user-facing Settings control

Status: scoped (pre-fleet activation gate for #1055 / Gmail M0)
Owner: unassigned
Branch: TBD
Issue/PR: TBD

#### Objective

Add a user-facing control in the Gmail Settings card to grant and revoke the
separate recurring/fleet-sync consent that the backend already gates on. Without
it, no user can opt in, so the fleet sweep (`/sync-all`) can never legitimately
process anyone — this blocks fleet activation even after the flag is flipped.

#### Context

- Discovered by the post-merge reconciliation of #1055 (audited on `main`
  `900972c`). Backend privacy gate is fully implemented; only the UI is missing.
- Precise classification: *backend privacy gate implemented; fleet activation
  remains blocked by missing user-facing consent flow.*
- Backend already in place (do NOT rebuild):
  - Column: `recurring_sync_consent_at` — `migrations/043_gmail_connections.sql:39`
  - Endpoint: `POST /api/v1/integrations/gmail/consent` (JWT-scoped) —
    `src/api/routers/integrations_gmail.py:199-228`
  - Repo setter: `set_recurring_sync_consent` — `src/repositories/gmail_repo.py:270-306`
  - Fleet filter: `list_active_connections` (consented rows only) —
    `src/repositories/gmail_repo.py:88-117`
  - Frontend API helper ALREADY EXISTS but is unused by the card:
    `setGmailRecurringSyncConsent` — `apps/web/lib/api.ts:968`
  - `GmailStatusResponse.recurring_sync_consent` is already returned by `/status`.
- Gap to close: `apps/web/components/settings/GmailConnectionCard.tsx` renders only
  Connect / Sync / Disconnect. Add a clear grant/revoke control (e.g. a toggle)
  that reads `status.recurring_sync_consent`, calls `setGmailRecurringSyncConsent`,
  and refreshes status. EN + AR copy; plain language that this authorizes recurring
  background sync (distinct from the read grant and from manual sync).

#### Constraints

- Scope is UI + wiring only — no backend, migration, secret, or flag changes.
- Only meaningful once a connection exists (mirror the backend 409-when-not-connected).
- Revoke must always be available (privacy-reducing action), consistent with Disconnect.

#### Acceptance criteria

- Connected users can clearly grant recurring/background Gmail-sync consent.
- Connected users can revoke that consent at any time, including while sync is disabled.
- The control reads the real `recurring_sync_consent` status and refreshes after mutation.
- Manual Sync remains separate and does not grant recurring consent.
- No control is shown as active for an unconnected account.
- EN and AR copy clearly distinguish OAuth read access, manual sync, and recurring
  background sync.
- No migration, backend, environment flag, fleet workflow, or production activation change.

#### Required verification

- `GmailConnectionCard` unit tests for: grant, revoke, disabled-sync revoke, API
  failure, and unconnected state.
- Existing Gmail frontend tests (regression).
- Complete frontend vitest suite.
- Production frontend build (`npm run build` in `apps/web`).
- EN/AR and mobile visual check.

#### Continuity Block

- Task ID: TASK-20260717-009
- GitHub issue/PR: TBD
- Branch: TBD
- Base branch: main
- Last safe commit SHA: TBD (branch not yet cut)
- Uncommitted changes present: no
- Status: scoped
- Files expected to change:
  - `apps/web/components/settings/GmailConnectionCard.tsx` — add grant/revoke control
  - `apps/web/lib/translations*` (EN + AR strings for the three sync concepts)
  - `apps/web/components/settings/__tests__/` (or the existing Gmail card test path)
    — new vitest cases for grant/revoke/disabled-sync-revoke/API-failure/unconnected
  - (wiring only) reuse `setGmailRecurringSyncConsent` (`apps/web/lib/api.ts:968`)
    and `GmailStatusResponse.recurring_sync_consent` — no new API surface
- Files/areas explicitly excluded:
  - `migrations/*` (043 already carries the column) — no migration change
  - `src/**` backend (endpoint + repo + fleet filter already exist) — no backend change
  - env flags (`RICO_ENABLE_GMAIL_SYNC`), Render/Neon/Vercel config — untouched
  - `.github/workflows/*` — no fleet/sweep workflow added
- Next exact action: cut a branch, implement the toggle in `GmailConnectionCard.tsx`
  wired to `setGmailRecurringSyncConsent`, add EN/AR strings, add the five vitest
  cases above, run the frontend suite + build, EN/AR + mobile visual check.
- Stop condition: this task does NOT enable sync, apply migration 043, provision
  secrets, or add a fleet workflow — those remain separate owner-gated activation
  gates; do not activate anything without explicit owner approval.
- Rollback plan: revert the single frontend PR; no production impact (the control
  only records a consent flag the fleet sweep already honors, and the sweep itself
  stays gated OFF).

---

### TASK-20260716-002 — Career Memory Engine M1 (shadow, flag OFF)

Status: blocked (paused — hold as draft pending shadow evidence)
Owner: Claude (reconciled with main; independent review pending)
Branch: `feat/memory-engine-m1`
Issue/PR: #1025 (draft)

#### Objective

Additive career-memory substrate (M1): migration 042 (`career_memory_events` /
`career_memory_facts`), a shadow `MemoryWriter` inside `agent_runtime.handle_action`
(after the legacy write, own try/except — cannot change the action result), no
`MemoryReader`, feature flag `RICO_MEMORY_ENGINE_ENABLED=false` + kill switch +
circuit breaker. No user-visible behavior change.

#### Roadmap traceability

```text
Vision          AI_WORKSPACE/PROJECT_BRIEF.md — trusted Career Operating System
   ↓
Epic            Career Operating System
   ↓
Milestone       Professional Memory
   ↓
Phase           4 — Lifecycle Intelligence
   ↓
PR              #1025 — Career Memory Engine M1 (shadow)
   ↓
Task            TASK-20260716-002 (this entry)
```

#### Continuity Block

- Task ID: TASK-20260716-002
- GitHub issue/PR: #1025 (draft)
- Branch: `feat/memory-engine-m1`
- Base branch: main
- Last safe commit SHA: `b37ad583` (merge of origin/main into the branch, 0 conflicts)
- Uncommitted changes present: no
- Status: blocked (paused as draft — owner directive: do not activate until
  shadow evidence proves the stored memory is reliable; no `MemoryReader` and no
  change to Rico's answers before then)
- Files inspected: `migrations/042_career_memory_engine.sql`,
  `src/services/memory_writer.py` (path per branch: repo layer + fact history),
  `src/agent/runtime.py`, `src/api/app.py`, `scripts/check_migration_drift.py`,
  `tests/test_memory_engine_m1.py`
- Validation already run: `test_memory_engine_m1` 38/38; legacy memory + runtime
  suites 74/74; postgres integration correctly gated (skipped without DATABASE_URL);
  migration 042 confirmed next-free (after 041); drift signatures match objects
- Invariants verified: flag OFF default + kill switch + circuit breaker; shadow-only
  (write never raises); no `MemoryReader` anywhere; `public:*` sessions never merge
  into accounts. Caveat: `_EXCLUDED_KEY_RE` matches payload KEYS not values (safe
  today because the shadow payload is minimized to action/title/company/job_key/surface)
- Next exact action: keep DRAFT + flag OFF; independent review; measure shadow
  writes (failures/duplication/drift) before any MemoryReader or activation
- Stop condition: do not merge, activate the flag, or add a MemoryReader without
  explicit owner approval + shadow-evidence review
- Rollback plan: revert PR; migration 042 is additive (code tolerates the schema);
  flag OFF means no runtime path exercises it

---

### TASK-20260716-003 — Opening-film chooser: rotate on every guest visit, non-repeating 3-film cycle

Status: review → merge authorized. Containment exception RECORDED: the owner
(Binz2008-star) explicitly authorized merging #1085 via direct in-session
instruction ("Ok do it", 2026-07-16, after the review notes were addressed
and CI was green), taking it ahead of secret rotation / #1066 / #1067 / #1068
in merge order. Production deploy of main via Vercel follows automatically.
Owner: Claude (owner directive delivered in-session, 2026-07-16)
Branch: `claude/rico-film-rotation-fix-g7tua4`
Issue/PR: #1085 (draft)

#### Objective

Guests opening ricohunt.com get the launch film on EVERY visit (retire the
once-per-browser-session gate), rotating exactly option-2 / option-3 /
option-3b in a randomized non-repeating cycle (all three before any repeat),
with reload/revisit re-entering the chooser instead of staying locked to the
previously selected option URL. Preserve the authenticated `/command`
redirect, `/signup` CTAs, SEO prerender, and all film content.

#### Roadmap traceability

```text
Vision          AI_WORKSPACE/PROJECT_BRIEF.md — trusted Career Operating System
   ↓
Epic            Official-site opening experience (launch films)
   ↓
Milestone       Public launch funnel — /explainer rotation
   ↓
PR              #1085 — fix(landing): film chooser runs every guest visit
   ↓
Task            TASK-20260716-003 (this entry)
```

#### Continuity Block

- Task ID: TASK-20260716-003
- GitHub issue/PR: #1085 (draft)
- Branch: `claude/rico-film-rotation-fix-g7tua4`
- Base branch: main (`5cb1fd13`)
- Status: review — Draft/HELD; owner to record containment exception and merge
  order relative to secret rotation, #1066/#1067, #1068 before any merge; no
  production deploy (Vercel PREVIEW auto-deploys on push, as with every PR)
- Files touched: `apps/web/public/explainer/index.html` (chooser: persisted
  shuffle deck + in-place render), `apps/web/app/page.tsx`,
  `apps/web/lib/openingFilm.ts`, `apps/web/__tests__/landing-opening-film.test.tsx`,
  `apps/web/__tests__/explainer-film-rotation.test.ts` (new),
  `apps/web/public/explainer/README.md`
- Constraints honored: no billing/auth-implementation/Gmail/Memory/Atelier/film-content
  changes; film URLs remain a closed hardcoded allowlist inside the chooser
- Validation already run: vitest full suite green; `next build` green; real-Chromium
  smoke (6 visits = 2 full non-repeating cycles, URL stays on chooser, film renders);
  persisted-deck validation hardened (unique-valid-subset only) with regression tests
- Next exact action: owner manual smoke on the Vercel preview + record the
  exception/merge order; PR stays draft until then

---

### TASK-20260716-004 — After the films comes the landing page (+ film-boot robustness fix)

Status: merge authorized — owner (Binz2008-star) explicitly said "merge"
in-session (2026-07-16) after CI went green and the Vercel preview was up;
containment exception recorded, same basis as TASK-20260716-003 / #1085.
Owner: Claude
Branch: `claude/rico-film-rotation-fix-g7tua4` (restarted from main after #1085 merged)
Issue/PR: follow-up to #1085

#### Objective

1. A rotation film's single pass ends by handing the visitor to the landing
   page (`/?after-film=1` → landing renders once, marker stripped, next "/"
   entry rotates again) instead of looping forever. Skip/Join keep /signup.
2. Robustness fix discovered while verifying: replace the chooser's
   fetch + document.write film render (merged in #1085) with a real
   navigation tagged `#rico-rotation` + in-film `history.replaceState` mask.
   A parser-inserted end-of-body script waits on pending stylesheets, so a
   stalled fonts CDN froze the written film entirely; native navigation has
   no such dependency and keeps the same reload-re-enters-rotation behavior.

#### Continuity Block

- Task ID: TASK-20260716-004
- Files touched: `apps/web/public/explainer/index.html`,
  `apps/web/public/explainer/option-2.html` / `option-3.html` / `option-3b.html`
  (goLanding at end of pass + #rico-rotation URL mask; visuals/copy/CTAs untouched),
  `apps/web/app/page.tsx`, `apps/web/lib/openingFilm.ts` (claimAfterFilmLanding),
  `apps/web/__tests__/landing-opening-film.test.tsx`,
  `apps/web/__tests__/explainer-film-rotation.test.ts`,
  `apps/web/public/explainer/README.md`
- Validation already run: vitest 600/600; next build green; real-Chromium E2E:
  "/" → film plays (scene active = script live, URL masked to chooser) →
  fast-forward → landing renders once with marker stripped → reload → next film
- Next exact action: owner merge word; production deploy via Vercel on merge

---

### TASK-20260717-001 — Stabilize flaky chat-confirm-profile vitest file (CI tax)

Status: in review (owner granted execution autonomy in-session 2026-07-17 to finish outstanding work; test-only change)
Owner: Claude
Branch: `claude/rico-film-rotation-fix-g7tua4` (restarted from main after #1116 merged)
Issue/PR: follow-up; flaked 3x on 2026-07-16 (#1085 and #1116 CI, plus one local run) always in `chat-confirm-profile.test.tsx`

#### Objective

Remove the two flake modes without weakening the guard:

1. 5s default test timeout too tight for the full CommandPage render + CV
   upload flow on loaded CI runners → per-test 15s timeout on the three
   heavy tests.
2. Raw `fetchMock.mock.calls.length` equality races with `useAuth`'s
   per-mount `/api/v1/me` re-check (the Edit click mounts the editor panel)
   → count only non-`/api/v1/me` calls, and additionally assert that
   neither `/chat/public` nor `confirm-cv-profile` is ever called by Edit.

#### Continuity Block

- Task ID: TASK-20260717-001
- Files touched: `apps/web/__tests__/chat-confirm-profile.test.tsx` only
- Validation: file passed 10/10 consecutive local runs post-fix
- Next exact action: PR, CI green, merge under the in-session autonomy grant

---

### TASK-20260717-002 — Job Result Integrity Gate (incident #1121)

Status: review
Owner: model
Branch: fix/job-result-integrity-gate
Issue/PR: incident #1121 → Draft PR #1123 (this branch) → TASK-20260717-002

Traceability: Issue #1121 (the real Job Result Integrity incident) → Draft PR
# 1123 → TASK-20260717-002. The PR "Addresses #1121" (not "Closes") and must not
auto-close #1121 while Draft. #1118 is a DIFFERENT issue (the CV-parse quality
gate for #1119) and is not tracked here.

#### Hierarchy

- Vision → Career Operating System
- Epic → Rico Command Runtime Restoration
- Milestone → Trusted Job Search
- Phase → Job Result Integrity Gate
- Issue → #1121 (production Job Result Integrity failure)
- PR → Draft PR #1123, one objective: reject non-trustworthy listings before scoring/card/shortlist
- Tests → provider-to-card integrity contract (`tests/test_job_result_integrity.py`)

#### Incident

Production surfaced a Totaljobs listing — title "Project Manager", body "Mental
Health Practitioner / Recovery Service", location Manchester (UK), apply state
Unavailable — in a UAE workflow. Withdraws the prior "job-search vertical is
genuinely strong" assessment. Classes: non-UAE market leak; title/description
role-family conflict; unavailable/dead apply link; no trust decision before
scoring/shortlist admission.

#### Objective

Rico owns the final trust decision: a job may be CV-scored, carded, or shortlisted
only after Market + Role + Listing + Freshness + Evidence integrity pass.

#### Root cause

`src/job_providers.py` forwards `country="ae"` only to JSearch; Adzuna is hard-
scoped to its GB index (`ADZUNA_COUNTRY` default `gb`) and the cascade short-
circuits on the first provider with items, with NO post-cascade market/role/
availability filter before scoring. First layer that should have rejected the
record: market/country normalization.

#### Fix

- `src/job_integrity.py` (new): `RejectionReason` + `validate_listing` +
  `filter_listings` (market/role/title-body-conflict/availability/apply-url/
  source-page/freshness/evidence). Role step: the REQUESTED role's own
  occupational domain participates in the title/body comparison (protected-domain
  review fix) — a valid Nurse/Mental-Health request is not falsely conflicted.
  Protected-domain detection is bilingual (EN + Arabic vocabulary) so Arabic
  listings are validated with Arabic signals, never skipped; sparse Arabic
  evidence → `INSUFFICIENT_LISTING_EVIDENCE`. `filter_listings` tags each
  accepted record `apply_verified` (True only with a usable http(s) URL).
- `src/rico_chat_api.py`: run the gate in `_target_role_search_response` right
  after fetch, before scoring/formatting/shortlist; surface a safe aggregate
  `integrity_filtered` count only. `_format_match` surfaces `apply_verified` on
  the card (tied to the resolved usable link) so a missing/invalid-link card
  renders the fallback CTA and never an Apply action.
- `src/job_providers.py`: drop Adzuna from the cascade when its configured index
  ≠ the requested country (stops the GB short-circuit).

#### Constraints

- Do not touch PR #1119 files (`src/api/routers/rico_chat.py`, `src/cv_parser.py`,
  `src/cv_parse_quality.py`, and their tests).
- No new providers; no broadened search; no UI redesign; no migrations.
- Context-durability (reload → recent_search_role loss) is a SEPARATE defect — not
  in this PR.

#### Acceptance criteria

- [x] UAE search rejects UK/non-UAE listings even at high provider rank.
- [x] title/body role-family conflict (Project Manager + Mental Health) rejected.
- [x] protected-domain request (Nurse / Mental Health Practitioner) NOT falsely
      conflicted; requested role's own domain participates in the comparison.
- [x] unavailable listing / malformed apply URL never a recommendation; missing
      URL kept as unverified (`apply_verified=false`), never an Apply action.
- [x] valid UAE listing remains scoreable; rejected never scored/carded/shortlisted
      (proven through the real `_target_role_search_response` path).
- [x] Arabic listings validated with Arabic vocabulary (not skipped); conflicts
      caught; insufficient Arabic evidence → INSUFFICIENT_LISTING_EVIDENCE.
- [ ] PRE-MERGE BRANCH QUALITY SMOKE (branch/local, NOT production — production
      runs main): five role searches, zero UK/mismatch/unavailable in top 10.

#### Separate follow-up (do NOT implement here)

- Search-context durability: `recent_search_role` non-durable under
  `RICO_MEMORY_BACKEND=postgres`; multi-role option click triggers page reload;
  refinement falls back to profile after reload. Tracked separately.

---

### TASK-20260718-023 — Data-integrity foundation: posting-history archive + learning-signal hygiene

Status: done
Owner: Claude (Fable session, owner-directed "choose highest long-term impact and execute")
Branch: claude/release-captain-queue-76nrwz
Issue/PR: (draft PR from this branch)

#### Objective

Start the two time-sensitive data-integrity foundations of the Product Truth
Sprint: (1) an append-only `job_observations` posting archive (longitudinal
market data cannot be backfilled), and (2) stop + quarantine the daily
pipeline's echo learning-signals (system output recorded as user behavior).

#### Context

- Strategy: owner-approved Product Truth Sprint; owner note "Data Integrity
  before Analytics".
- Evidence: `run_daily._update_learning_repo` recorded pipeline matches as
  user "save" signals (`source="daily_pipeline"`, `auto_saved: True`);
  `jobs` table is a rolling 14-day window (jobs_repo filters
  `date_found >= now() - interval '14 days'`) so posting history was being
  discarded by design.
- Files: `migrations/046_job_observations.sql`,
  `src/repositories/job_observations_repo.py`, hooks in
  `src/jsearch_client.py` (+ `posted_at` passthrough) and
  `src/job_providers.py` (jooble/adzuna), `src/run_daily.py` (writer removed),
  `src/repositories/learning_repo.py` (`_EXCLUDED_SIGNAL_SOURCES` filter at
  DB load, decay aggregation, and write-time EMA).

#### Constraints

- Migration 046 is a FILE ONLY in this PR — applying it to Neon is an owner
  action; the archive code fail-safes to a disabled no-op (pgcode 42P01
  latches off per process) until the table exists.
- `job_observations` carries ZERO user data (market-side only; no PDPL scope).
- Append-only: no update/delete code paths.
- No analytics, no taste-loop UI, no ranking changes in this PR.

#### Acceptance criteria

- [x] Fresh provider fetches (jsearch/jooble/adzuna) record observations;
      cache hits never do.
- [x] Fingerprint v1 is provider-format stable (EN + AR) and versioned.
- [x] Description text never stored (hash + length only); apply URL reduced
      to domain.
- [x] Pipeline echo writer gone; `daily_pipeline` source inert on every read
      path; real user-action signals unaffected (pinned by
      `tests/unit/test_learning_signal_hygiene.py`).
- [x] `tests/unit/test_job_observations_repo.py` +
      `tests/unit/test_learning_signal_hygiene.py` green; adjacent suites
      (jsearch, providers, run_daily-touching) green.

##### Addendum (owner review round, 2026-07-18)

- **Privacy contract amended (owner catch)**: the migration stored raw
  `query_context` while claiming "zero user data" — query text can embed
  profile-derived terms. Resolved: column is now `query_hash CHAR(64)`
  (sha256 one-way); raw query text is never stored nor logged. Hash equality
  fully preserves the longitudinal instrument (same query → same hash).
- **Dual-scope merge accepted (documented per owner's option 2)**: PR #1173
  intentionally carries BOTH (a) the archive and (b) learning-signal hygiene.
  Rationale: one shared objective (data integrity), hygiene is read-path
  filtering + writer removal with no migration dependency, the archive
  fail-safes to a no-op until 046 exists — coupled risk ≈ union of two small
  independent risks; a split would cost a second branch/PR cycle with no
  added safety.
- **Owner-directed rollout gate**: 046 is applied to the Neon PREVIEW branch
  first (`preview/pr-1173-claude/release-captain-queue-76nrwz`, project
  `robenjob`) with table/index/write verification there; production
  application requires a separate explicit owner approval; only then
  Draft → Ready → merge.

##### Addendum 2 (owner privacy review, 2026-07-18 — supersedes the sha256 note above)

- Owner rejected plain sha256: the query space is small/guessable, so an
  unkeyed hash is dictionary-attackable — pseudonymous, NOT "zero user data".
- Approved contract implemented: `query_context_hmac CHAR(64)` =
  HMAC-SHA256(`RICO_ARCHIVE_HMAC_KEY`, normalized query). Key is dedicated
  (never JWT_SECRET), never stored in DB. Absent key ⇒ archive writes skipped
  entirely (fail-closed, one structured warning without query text, search
  unaffected); NO fallback to an unkeyed hash. Documentation claim corrected
  everywhere to: "No direct user identifiers or raw query text; query context
  stored only as a keyed, non-reversible HMAC for longitudinal grouping."
- Drift signature extended with the `query_context_hmac` column so a stale
  pre-review table shape is detected as drift.
- Dual-scope single-PR merge recorded as an EXPLICIT owner-granted exception
  to the one-task-one-PR rule (rationale in Addendum 1).
- Operational note: `RICO_ARCHIVE_HMAC_KEY` must be set on Render for the
  archive to record in production; until then it is safely OFF (fail-closed).

##### Closeout (2026-07-18, post-merge)

- Merged: squash `4879c04d` on `main` (PR #1173; expected-head `fbe1b2e4`
  protection; CI green; 0 review threads).
- Migration 046 applied to Neon `production`
  (`robenjob`/`br-restless-cherry-amq6wj7o`, db `neondb`) with owner
  approval AFTER preview-branch validation; post-apply verification: 17
  columns exact, `query_context_hmac` present, no stale
  `query_context`/`query_hash` columns, both indexes, 0 rows (no synthetic
  data in production). Scheduled drift check reads 046 green from its first
  run (apply-before-merge ordering — no alert window).
- `RICO_ARCHIVE_HMAC_KEY` generated and set on Render by the OWNER
  (value never transited this session); deploy Live confirmed by owner.
  Archive fully armed — first real user search writes the first
  production observations.
- "Deploy to Production" run 29664542075 triggered on `4879c04d`
  (completion tracked via scheduled self check-in).

---

### TASK-20260719-001 — P1: "Refine search" as a structured action (never chat input)

Status: done
Owner: Claude (Fable session; owner CPO decision: fix before analytics/taste-loop)
Branch: claude/refine-search-structured-action
Issue/PR: (draft PR from this branch)

#### Objective

The "Refine search" card sent its LABEL as a chat message; the intent router
parsed it as a job role ("I didn't catch 'Refine search' as a specific
role"). Separate UI actions from natural language: the card becomes an
`open_drawer` structured action opening a refinement panel; the LLM only ever
sees the final composed search query.

#### Root cause (two layers)

- Contract mismatch: composer sent `payload.prompt`; the frontend reads
  `payload.message` — so the fallback `?? action.label` fired. Same silent
  break affected "Save search" and "Find new jobs".
- The fallback itself: a UI label must never become chat input.

#### Changes

- `src/services/agentic_ui_composer.py`: refine → `open_drawer`
  (`drawer: "refine_search"`, carries `search_query`); all remaining
  `chat_continue` payloads renamed `prompt` → `message`; contract documented
  in the module docstring.
- `apps/web/components/ui/rico/ChatActionCard.tsx`: `chat_continue` enabled
  ONLY with non-empty `payload.message`; label fallback removed (disabled +
  reason instead).
- `apps/web/components/command/RefineSearchPanel.tsx` (new): role prefill +
  UAE city chips; composes a real natural query (EN/AR) sent as a normal
  user message; `page.tsx` `handleOpenDrawer` routes `refine_search` to it.
- Bilingual keys `cmdRefine*` in translations.

#### Acceptance criteria

- [x] Backend contract tests: no `prompt` key anywhere; every chat_continue
      carries non-empty `payload.message`; refine pinned as open_drawer
      (tests/test_agentic_ui_composer.py — 70 green).
- [x] Frontend pins: label NEVER sent as chat input (disabled without
      message); open_drawer passes the full action; panel composes EN/AR
      queries with zero UI wording (chat-action-card + refine-search-panel
      suites; full vitest 724 green; `npm run build` clean).
- [x] Analytics-purity side effect: no more synthetic "Refine search"
      user messages polluting chat history or future analytics.

---

### TASK-20260719-002 — analytics_events foundation (migration 047)

Status: review
Owner: Claude (Fable session; owner directive post-#1175: single-objective PR)
Branch: claude/analytics-events-foundation
Issue/PR: (draft PR from this branch)

#### Objective

Product Truth Sprint track 1 ("eyes"): first-party behavioral event store —
migration + storage foundation ONLY. No emitters wired, no Taste Loop, no
structured-action changes.

#### Scope delivered

- `migrations/047_analytics_events.sql` — append-mostly store; unique
  `dedupe_key` (idempotency); `schema_version` on every row; indexes for
  funnels + retention sweeps. NOT applied anywhere — production application
  requires a separate owner approval gate (preview-first, as 046).
- `src/repositories/analytics_events_repo.py` — `record_event()` (never
  raises; 42P01 latch; ON CONFLICT DO NOTHING) + `purge_expired()`
  (RETENTION_DAYS=180; scheduled invocation is a LATER change).
- Strict `EVENT_ALLOWLIST` (8 events): unknown events rejected, unknown
  properties stripped; values limited to bools, bounded ints, and enum-like
  tokens `^[a-z0-9_.:-]{1,64}$` — free text/emails/query strings are
  significantly reduced (token validator still accepts identifier-shaped
  strings and digit-only values, so caller discipline remains required).
  `search_performed` deliberately has no query-text property.
- Actor = keyed HMAC-SHA256 under dedicated `RICO_ANALYTICS_HMAC_KEY`
  (documented in .env.example; never JWT_SECRET / never the archive key so
  datasets stay unlinkable); absent key ⇒ all writes skipped fail-closed
  with one structured warning; no unkeyed fallback.
- Drift signatures for 047 (table + dedupe index).

#### Rollback

Revert the commit; drop the table if created — nothing references it.

#### Acceptance criteria

- [x] Privacy pins: unknown event rejected without DB touch; PII-shaped
      values cannot pass the validator; raw user id never in a row;
      fail-closed no-key path warns once without identifiers.
- [x] Idempotency pins: client_event_id-stable keys; canonical
      order-independent minute-bucket keys; conflict ⇒ False, no error.
- [x] Resilience pins: DB-down no-op; 42P01 latch; transient errors don't
      latch.
- [x] Retention pin: purge SQL + 180-day constant.
      (tests/unit/test_analytics_events_repo.py — 16 tests.)

##### Housekeeping

TASK-20260719-001 (Refine search structured action): merged as `d5f96f1e`
on `main` (PR #1175, expected-head protection, CI green incl. the new
real-browser smoke) → Status: done.
