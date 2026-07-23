# Command Workspace v5 — implementation map & program

Owner adoption decision (2026-07-20): **Command Workspace v5 is the approved
implementation reference** for Command Workspace visual direction, layout,
motion, modes, states and interaction design. GitHub `main` remains the source
of truth for auth, APIs, data, chat behavior, routing and tests. The v4 design
freeze is lifted **only** for this approved v5 implementation scope.

Visual acceptance reference — **superseded 2026-07-21 by owner instruction**:
the owner-supplied artifact
`design-handoffs/incoming/2026-07-21-command-workspace-artifact/Rico_Command_Workspace_v5.dc.html`
is now the sole visual source of truth (palette LIGHT+DARK, fonts
Fraunces/Inter/IBM Plex Mono + Amiri/IBM Plex Sans Arabic, MODE_THEME
accents, hero language). The earlier v5-rebuild palette (#1238 evidence
package) is cancelled and fully replaced in the repo. The standalone
prototype HTML is never deployed and never copied wholesale; AA text-safe
darkened variants are derived where an artifact accent falls below WCAG AA
for small text (same policy the evidence package used).

## Traceability chain

| Level | Value |
| --- | --- |
| Vision | Career OS — Rico as an AI-native career operating system (`AI_WORKSPACE/CAREER_OS_VISION.md`) |
| Epic | Command Workspace v5 implementation (this document) |
| Milestone | v5 visual system live on production workspace routes without behavior regressions |
| Phases | PR 1 foundation → PR 2 shell → PR 3 live modes → PR 4 message/action styling → PR 5 motion + final QA |
| PR (current) | PR 1 merged (#1242 `984edfa`) · PR 2 merged (#1243 `7b40b70`) · PR 3 merged (#1271 `4b33709`) · PR 4 merged (#1275 `a656290` — public /command artifact chrome) · PR 5 (motion/final-QA) **complete** — hover-lift physics + Upload entrance motion merged #1356 (`74247484`) and #1357 (`6585719a`) |
| Task | `AI_WORKSPACE/TASKS.md` → TASK-20260720-004 (done) · TASK-20260720-005 (done) · TASK-20260721-005 (done, merged #1271) · TASK-20260721-006 (done, merged #1275) |

## Artifact → production map (exact)

### Modes → routes (multi-route architecture stands, DEC-20260717-001 — the artifact's SPA switcher is NOT ported; "mode switch" becomes route navigation with entrance replays)

| v5 artifact mode | Artifact anchor (v5.dc.html) | Production target | Status |
| --- | --- | --- | --- |
| Overview ("command deck", score hero, goal, next actions, signals) | `#mode-overview` | `/dashboard` — `apps/web/components/workspace/DashboardAtelier.tsx` | LIVE — restyle in PR 3 |
| Search ("mission control", ranked matches, evidence bars, composer) | `#mode-search` | `/command` — `apps/web/app/command/page.tsx` + `components/command/*` | LIVE — shell PR 2, cards PR 4 |
| Applications (pipeline stages, funnel, stalled/offer states) | `#mode-applications` | `/applications` — `apps/web/components/applications/ApplicationsAtelier.tsx` | LIVE — restyle in PR 3 |
| Documents (identity vault, active CV, lineage, upload) | `#mode-documents` | `/upload` — `apps/web/components/upload/UploadAtelier.tsx` | LIVE — restyle in PR 3 |
| Interview (rehearsal stage) | `#mode-interview` | — no production capability (v4 boundary 5 still holds) | HIDDEN — not built until real capability + owner approval |
| Learning (skill constellation) | `#mode-learning` | — no production capability | HIDDEN — same rule |
| Activity (intelligence ledger) | `#mode-activity` | — requires an owner-approved read-only endpoint first | HIDDEN — same rule |

### Cross-cutting regions

| v5 artifact region | Production target | Phase |
| --- | --- | --- |
| Foundation: tokens / typography / surfaces / motion primitives / presence orb | `apps/web/components/workspace/v5/{tokens.ts, fonts.ts, motion.css, RicoPresence.tsx}` + `scripts/check-contrast-v5.mjs` gate + gallery specimen `/design-gallery/command-v5` | **PR 1 (this PR)** |
| Modes rail (wordmark, goal-mini, nav, active energy marker, per-mode accents) | `apps/web/components/workspace/WorkspaceShell.tsx` + `RailGoalMini.tsx` (restyled, same nav source of truth `WORKSPACE_NAV`) | PR 2 |
| Responsive drawers / mobile nav / panel contracts (≥1600 / 1280–1599 / <1280 / <900) | `WorkspaceShell` responsive layer | PR 2 |
| Ask Rico copilot choreography | `/command` chat surface itself (the production copilot IS `/command`); embedded copilot on other routes stays HOLD — the approved Ask Rico deep-link to `/command` stands | PR 2 (panel chrome) + PR 4 (messages) |
| Context panel / Memory tab | NOT built — Career Memory Engine remains Draft #1025 (flag OFF, frozen); no fake states (DEC-20260710-002) | Deferred |
| Trust & action vocabulary (Information / Recommendation / Action + 6 explicit states) | `components/command/ChatActionCard*`, message renderers | PR 4 |
| Loading / empty / error / completed state family | per-route state components on live modes | PR 3 + PR 4 |
| Directional mode transitions, hover physics, ambient focal motion | v5 motion primitives applied per route | PR 5 (final pass; primitives from PR 1) |
| Design-states drawer | NOT ported (engineering affordance) — replaced by the internal gallery specimen | n/a |
| Artifact keyboard contract (⌘K toggles copilot) | NOT ported — production Ctrl/Cmd+K keeps focusing the `/command` composer (v4 boundary 2) | n/a |
| Embedded data-URI fonts | NOT ported — next/font route-scoped loaders (`v5SpaceGrotesk`; Fraunces via shared atelier-kit) | PR 1 |

## PR ladder (owner-approved sequence; one objective per PR, Draft first, no auto-merge)

| PR | Scope | Explicitly out of scope |
| --- | --- | --- |
| **PR 1 — visual foundation** (merged #1242) | v5 tokens (AA-audited), typography (Space Grotesk + Fraunces roles), surfaces, motion primitives, RicoPresence, contrast gate, internal specimen | chat logic, APIs, routing, backend, any production-route render change |
| PR 2 — workspace shell | rail + layout + panels + responsive + keyboard/a11y contracts on the real `WorkspaceShell` | chat behavior changes |
| PR 3 — live modes | Overview `/dashboard`, Search `/command` frame, Applications `/applications`, Documents `/upload` mapped to REAL data/contracts only; unsupported modes hidden | mock data, new endpoints |
| PR 4 — messages & action cards | chat messages, job/application cards, tool/action states, state family styling | intent/mutation logic |
| PR 5 — motion & final QA | transitions, reduced-motion, performance, mobile, EN/AR + RTL, accessibility | new features |

## Binding rules (restated from the owner decision)

- Preserve current APIs, response shapes, auth, sessions, persistence, billing.
- No mock claims or fake functionality in production; unsupported v5 modes stay hidden or clearly disabled.
- v5 evidence package = visual acceptance reference for every PR review.
- Every PR: scope, risks, acceptance criteria, rollback plan, screenshots; frontend build + unit tests + Playwright + accessibility + mobile smoke before review.
