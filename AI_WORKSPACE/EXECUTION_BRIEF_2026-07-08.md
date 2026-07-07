# Rico Execution Brief — 2026-07-08

## Purpose

This briefing tells future agents where Rico currently stands and what must be done next.

It is an execution snapshot, not a replacement for the full workspace history.

Canonical references:

- `AI_WORKSPACE/AUDITS/2026-07-08-production-hardening-audit.md`
- `AI_WORKSPACE/CURRENT_STATE.md`
- `AI_WORKSPACE/DECISIONS.md`
- `AI_WORKSPACE/ARCHITECTURE.md`
- `AI_WORKSPACE/TASKS.md`
- `AGENTS.md`

---

## Product invariant

Rico must never forget:

```text
what it found → what the user opened → what was applied → what needs follow-up
```

Operational memory is the highest near-term product priority.

---

## Current production stance

- Render remains the production backend.
- No infrastructure migration is approved right now.
- Neon remains the source of truth for persistent state.
- Production landing remains `LandingPageV2`.
- Landing production swaps are frozen unless the owner explicitly approves a production PR.
- UI facelift work must remain staged through design references, `/design-gallery`, and scoped pilots before production rollout.

---

## Active priorities

### P0/P1 — Operational memory stabilization

Current active implementation PR:

```text
#885 — feat(lifecycle): list applied jobs ready for follow-up
branch: feat/rico-memory-list
status: open draft
```

This PR must remain the active implementation priority until it is either fixed and merged or explicitly closed.

Required before merge:

- Fix Codex P2s inherited from #883.
- Fix pytest failure in QA Tests #1156.
- Keep the endpoint read-only.
- Do not add chat routing in this PR.
- Do not add notifications, email, scheduler, DB writes, migrations, auth, billing, frontend, Render, or Railway work.
- Use synthetic data only in tests.

Expected scope:

- `src/services/operational_memory_readiness.py`
- `src/api/routers/job_lifecycle.py`
- `src/schemas/job_lifecycle.py`
- `tests/unit/test_operational_memory_readiness.py`
- `tests/unit/test_job_lifecycle_followups_endpoint.py`

---

## Required fixes for #885

Codex left valid P2 findings on #883 after it was merged. Since #885 is the first API use of that helper, #885 must absorb these fixes before merge.

Required helper fixes:

1. Use elapsed time, not calendar-date difference, to calculate follow-up readiness.
2. Accept existing date fields: `applied_at`, `date_applied`, `date_updated`.
3. Include `follow_up_due` rows as revisit/follow-up candidates.

Required test fix:

- Do not directly unit-test a FastAPI route function decorated by `@limiter.limit` with `request=None`.
- Move follow-up listing logic into an internal helper such as `_list_followups_for_user(...)` and test that helper.
- The decorated route should stay a thin wrapper around the helper.

---

## Recently merged operational-memory work

```text
#882 — docs(audit): add production hardening audit gate
#883 — feat(memory): add operational memory revisit readiness helper
```

Interpretation:

- #882 is the near-term execution gate.
- #883 added the pure helper but needs correctness fixes in #885 before runtime/API use is merged.

---

## UI facelift / Atelier status

The facelift exists, but it is not fully rolled out to production.

Merged safe groundwork:

```text
#878 — PR A1: Atelier V2 tokens + fonts + /design-gallery specimen
#879 — C1: Atelier terms pilot, scoped light island on /terms
#880 — fix(atelier): font-token fallbacks
```

Open prototype/design PRs:

```text
#872 — design(nocturne): comprehensive UI/UX upgrade
#873 — design(rico-alive): comprehensive UI/UX upgrade
```

These are design-gallery/prototype-oriented and must not be treated as production rollout PRs without a separate owner-approved production PR.

---

## Landing page freeze

Merged governance:

```text
#870 — hotfix(landing): restore LandingPageV2 homepage
#871 — docs(agents): add landing page production freeze rule
```

Rules:

- Do not change `apps/web/app/page.tsx` to a new landing component without explicit owner approval.
- New landing concepts must go through `design-handoffs/`, `/design-gallery`, browser smoke testing, and a separate production PR.
- Do not use a design-gallery PR as a hidden production swap.

---

## Architecture roadmap vs audit gate

`DEC-20260707-001` is the architecture-level roadmap.

The production hardening audit is the near-term execution gate.

Interpretation:

- The architecture roadmap explains where Rico is going.
- The audit gate controls what agents are allowed to do now.
- If they appear to conflict, follow the audit gate for immediate work.
- Do not start worker, notification, infrastructure migration, or full UI rollout work until P0/P1 operational-memory risks are classified and handled.

---

## Branch naming standard

Use:

```text
<type>/<domain>-<scope>
```

Allowed types:

```text
feat
fix
hotfix
docs
design
test
refactor
chore
ci
perf
security
```

Preferred examples:

```text
feat/lifecycle-followup-list
fix/memory-revisit-threshold
design/atelier-terms-page
design/gallery-rico-alive-prototype
docs/architecture-operational-memory-roadmap
chore/archive-design-references
test/lifecycle-followup-regression
hotfix/landing-v2-restore
ci/playwright-browser-install-stability
```

Avoid:

```text
new-ui
final-fix
test123
baki-shogol
random Claude/Devin generated names when a meaningful name is possible
```

Agent-generated branches are acceptable only when the branch name remains descriptive and scoped.

---

## Commit message standard

Use Conventional Commits:

```text
<type>(<scope>): <imperative summary>
```

Examples:

```text
feat(lifecycle): list applied jobs ready for follow-up
fix(memory): calculate revisit readiness by elapsed time
design(atelier): add scoped terms page island
docs(workspace): reconcile architecture roadmap with audit gate
test(lifecycle): cover follow-up candidate selection
chore(refs): archive design reference artifacts
hotfix(landing): restore LandingPageV2 homepage
ci(playwright): stabilize chromium browser install
```

Commit rules:

- Use present-tense imperative summaries.
- Keep the scope meaningful.
- Do not use vague summaries such as `update`, `fix stuff`, `final`, or `changes`.
- Do not mix unrelated objectives in one commit when they should be separate PRs.

---

## PR discipline

Every Rico PR should clearly state:

- Decision
- Scope
- What changed
- What did not change
- Acceptance criteria
- Required tests
- Safety / rollback notes

Default policy:

- Small PRs only.
- One objective per PR.
- No hidden production behavior in prototype/design PRs.
- No real-user mutation in tests or smoke runs.
- Synthetic users and synthetic profile/application data by default.
- Explicit owner approval is required for authenticated production smoke that mutates real production state.

---

## Immediate next action

Finish #885 before starting new production work.

Recommended handoff:

```text
Continue branch feat/rico-memory-list.
Fix helper correctness, endpoint unit tests, and QA Tests #1156.
Keep #885 draft until pytest, Vercel, Playwright, and Codex are green or explicitly triaged.
```
