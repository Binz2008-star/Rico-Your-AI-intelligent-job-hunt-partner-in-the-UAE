# Handoff — 2026-07-09 Board-health scan

## Task

Read-only lightweight scan of all open GitHub issues (34) and open PRs (4, previously triaged),
using the newly-active Rico Continuity Gate, to classify P0/P1/P2/P3/close-candidate/needs-deep-dive
so the next work item is chosen from evidence, not guesswork.

## Context

- Repository: Binz2008-star/Rico-Your-AI-intelligent-job-hunt-partner-in-the-UAE
- Branch: none during the scan (read-only); persisted via `docs/board-health-scan-sync`
- Issue or PR: none (board-wide scan, not a single issue/PR)
- Relevant files: none (GitHub metadata only)
- Relevant architecture notes: `AI_WORKSPACE/START_HERE.md` Continuity Gate section,
  `AI_WORKSPACE/TASKS.md` Continuity Block template

## Constraints

- Out of scope: any code change, test change, label change, issue close, Neon/Vercel/Render touch
- Compatibility requirements: n/a (read-only)
- Style and typing requirements: n/a (read-only)

## Acceptance Criteria

- [x] All 34 open issues scanned by number/title/created/updated/comment-count
- [x] Full body opened only for issues matching risk trigger categories (data corruption,
      duplicate data, Neon/migration drift, persistence failure, OCR, lost context, application
      tracking, apply link, intent routing, auth/security/privacy, billing, production reliability,
      user trust), plus #446 per explicit instruction
- [x] Every issue classified into one of: P0 / P1 / P2 / P3 / Close candidate / Needs full deep dive
- [x] Report delivered: totals, buckets, top 10 risks, deep-dive list, close candidates, old-roadmap
      list, recommended next 3 work items
- [x] No fixes started, no files changed, no labels touched, no issues closed during the scan

## Continuity Block

Copy verbatim from the `AI_WORKSPACE/TASKS.md` entry this handoff closes (`TASK-20260709-001`):

- Task ID: TASK-20260709-001
- GitHub issue/PR: none (read-only board scan)
- Branch: none during the scan; persisted via `docs/board-health-scan-sync`
- Base branch: main
- Last safe commit SHA: f6996b4da04f6d3812fe873067e89247c8bb165e
- Current head SHA: f6996b4da04f6d3812fe873067e89247c8bb165e (scan made no code commits)
- Status: done
- Files changed: none during the scan; this docs-only PR changes `PROJECT_STATUS.md`,
  `CURRENT_STATE.md`, `TASKS.md`, this handoff, `MASTER_INDEX.md`
- Files intentionally not touched: all runtime code, tests, Neon, Vercel/Render config, issue
  labels/state
- Known blockers: none
- Validation already run: `list_pull_requests` (4 open, all previously triaged),
  `search_issues`/`list_issues` cross-check (34 open, consistent counts)
- Validation still required: code-level verification for #127, #198, #263 (see below)
- Next exact action: security/data-risk deep dive on #127 and #198 (then #263 if time remains)
- Stop condition: do not start #758/#812/#446 until #127/#198 deep-dive is reported and the owner
  confirms priority
- Rollback plan: revert the docs-only PR; no schema/env/runtime changes

## Board-health scan result

### Totals

- 34 open issues, 4 open PRs (#872, #873, #899 open; #900 merged same day as this scan)

### Issues by bucket

| Bucket | Count | Issues |
|---|---:|---|
| P0 — production/trust/data-integrity/security | 1 | #446 |
| P1 — core Rico loop bug | 6 | #758, #831, #812, #654, #712, #96 |
| P2 — product quality/UX/test gap | 2 | #875, #187 |
| P3 — stale docs/old epic/cleanup | 19 | #745, #618, #531, #356, #355, #354, #353, #352, #294, #269, #213, #196, #179, #140, #138, #118, #105, #99, #746 |
| Close candidate | 3 | #884, #485, #147 |
| Needs full deep dive | 3 | #263, #198, #127 |

### Top 10 risks

1. **#198** — DB connection leaks in `rico_db.py`/`subscription_repo.py` (leak under load);
   **H5: public chat email identity accepted without ownership proof** (privacy/security);
   billing webhook race conditions (stale-pending events, invoice retry-loop). Old (2026-05-24),
   needs verification against current `main`, not dismissal.
2. **#127** — Named **SQL injection risk** in `src/rico_db.py#get_recommendations` (user-controlled
   `status` in clause construction) + hardcoded PII/credentials in `.env.example`/`indeed_apply.py`.
   Old (2026-05-14) but an unverified SQL-injection claim outranks product-quality work.
3. **#446** — Confirmed data corruption: 20 duplicate `rico_users` rows, emails overwritten by an
   old `ON CONFLICT` bug. Root cause fixed in #445; cleanup is owner-gated and still pending.
4. **#758** — Confirmed duplicate DB rows: `_fallback_identity` (job_save.py) and
   `_derive_lifecycle_job_key` (rico_chat_api.py) hash the same job differently, so `ON CONFLICT`
   never fires — every job gets an orphaned "opened" row alongside its "saved" row. Well
   root-caused, no schema change needed.
5. **#831** — Chat live-QA tracking issue: criticals TC-8/7/6 partially landed; TC-11 (profile
   flash), TC-9 (language stickiness), TC-10 (session cache/dedup) confirmed still open in
   `TASKS.md`.
6. **#712** — Neon migration drift: 011 (recommendation indexes) resolved; 005 remainder
   (`pipeline_runs`, keyword tables, view, trigger) still unverified in production.
7. **#812** — Chat role extraction splits compound titles on "and"
   (`"Environmental Health and Safety Manager"` → 2 fragments) — common in the UAE market (HSE,
   F&B, oil & gas); degrades match quality and burns JSearch quota on wrong queries.
8. **#263** — Product-trust audit: Rico reportedly contradicted itself about a tracked
   application, misrouted subscription/pricing questions to job search, broken no-CV flow, didn't
   know the user's name while logged in. Some may already be fixed by #892
   (`MutationConfirmationGuard`) and #747 (trust gate) — needs verification.
9. **#654** — Owner-labeled P1 tracker for session-aware intent routing + session memory
   (7-phase plan). Overlaps existing `TASK-20260703-04x` items — real, needs reconciling with
   current roadmap before any phase starts.
10. **#96** — Profile/CV/Jotform context unification — ties directly to open **BUG-13**
    ("profile/role drift across multiple CVs") listed unstarted in `PROJECT_STATUS.md`.

### Needs full deep dive

- **#127** — verify whether the named SQL-injection risk and hardcoded-credential findings are
  still present in current code.
- **#198** — verify DB connection-leak and security/privacy findings (esp. H5 public-chat email
  identity) against current `rico_db.py`/`subscription_repo.py`/`rico_chat_api.py`.
- **#263** — verify which product-trust claims are already fixed (likely #892/#747) vs. still open
  (subscription misclassification, no-CV flow, identity question).

**Required output format for the #127/#198 deep dive** (per owner instruction):
claim → current file/function checked → still present / fixed / partially fixed / cannot verify →
severity → smallest safe fix PR if still present → tests needed → rollback plan.

**Priority after verification:** if #127/#198 contain live security/data issues, fix those first.
If stale/fixed, proceed to #446 (owner-gated cleanup) → #758 → #812.

### Close candidates

- **#884** — CI browser-setup flake, self-described non-blocking. Recent CI runs (#900, #901,
  #902) all show clean `playwright` — likely already resolved; verify then close.
- **#485** — `RicoProfile.preferred_industries` field-mismatch TypeError (2026-06-07), references
  specific named tests. Codebase has moved substantially since; verify the named tests still
  exist/pass, then close.
- **#147** — References the old repository name (`Binz2008-star/job-automation-system-1`), Asana
  task links, and a deprecated `src/rico_server.py` shim. Superseded by current
  `AI_WORKSPACE`/`CLAUDE.md` governance — safe to close as obsolete.

### Old roadmap/epic issues — not to mix with current work

- Career Operations Lifecycle epic family: #352 (parent), #353 (Application Lifecycle
  Completion), #354 (Apply-Link Verification), #355 (Follow-up Reminders/Workers), #356 (Inbox
  Intelligence). Overlaps already-shipped work (#747 trust gate, #892 `MutationConfirmationGuard`,
  #885/#891 lifecycle persistence) — needs reconciliation before restarting.
- #654 (Workflow V2 tracker), #618 (audit backlog after #615/#616/#617) — both meta-trackers
  overlapping `TASKS.md`'s existing `TASK-2026070x-04x` items.
- #179 (Core v2 rewrite) — conflicts with the accepted phased-architecture roadmap
  (DEC-20260707-001), which prefers evolution over rewrite.
- #213 (Career Execution State Machine), #531 (landing redesign), #196 (frontend audit), #140/#138
  (cinematic auth/redesign epics — superseded by the Atelier/Nocturne design system), #118
  (SpikingBrain provider — not part of the current DeepSeek/OpenAI/HF strategy), #105 (Agent OS
  epic — largely already built via `agent/runtime.py`/`agent/registry`), #99 (Companion UX epic),
  #746 (Command UX funnel upgrade), #745 (Git workflow audit), #294 (career trajectory intent),
  #269 (link-verifier test task — folds into #354 if ever picked up).

## Deliverables

- Changed files: `AI_WORKSPACE/PROJECT_STATUS.md`, `AI_WORKSPACE/CURRENT_STATE.md`,
  `AI_WORKSPACE/TASKS.md`, this handoff, `AI_WORKSPACE/MASTER_INDEX.md`
- Implementation summary: docs-only state-sync recording the new live baseline (`main` at
  `f6996b4`, #900+#902 merged, Continuity Gate active) and persisting the 2026-07-09 board-health
  scan
- Tests run: none (docs-only; no runtime/test files touched)
- Risks: none — pure documentation, no schema/env/runtime changes
- Rollback notes: revert this PR; no schema/env/runtime changes, isolated to the 5 files above

## Required Verification

```bash
grep -n "f6996b4" AI_WORKSPACE/PROJECT_STATUS.md AI_WORKSPACE/CURRENT_STATE.md
grep -n "TASK-20260709-001" AI_WORKSPACE/TASKS.md
grep -n "board-health-scan" AI_WORKSPACE/MASTER_INDEX.md
```

## Expected Response

```md
## Summary
Docs-only state-sync: main advanced to f6996b4 (#900 + #902 merged/live); board-health scan
(34 open issues classified) persisted to TASKS.md + a dated handoff.

## Changed files
- AI_WORKSPACE/PROJECT_STATUS.md — refreshed dashboard (main SHA, active PR, risks, next)
- AI_WORKSPACE/CURRENT_STATE.md — new reconciliation header superseding the stale one
- AI_WORKSPACE/TASKS.md — TASK-20260709-001 Continuity Block added
- AI_WORKSPACE/HANDOFFS/2026-07-09-board-health-scan.md — full scan detail (new)
- AI_WORKSPACE/MASTER_INDEX.md — handoff indexed as latest pointer

## Verification
- grep checks above — all found

## Risks
None — docs-only, no runtime/schema/env changes.

## Rollback
Revert this PR.

## Open questions
None.
```

## Reviewer Notes

- Scope respected: yes — only the 5 files listed above changed; no runtime code, tests, labels,
  issue state, Neon, or Vercel/Render config touched.
- Evidence complete: yes — scan methodology, bucket counts, and top-risk reasoning are recorded
  above and cross-check against `TASKS.md`'s existing `TASK-2026070x-04x` entries.
- Follow-up tasks: security/data-risk deep dive on #127 and #198 (then #263 if time remains) is
  the required next step before #758/#812/#446.
