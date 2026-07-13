# Atelier Migration Program

Owner execution order (2026-07-13): replace the Rico frontend incrementally using the
approved Atelier design across **Dashboard, Profile, Settings, Applications, Upload,
Pricing, Command**. No redesign, reuse existing backend and APIs, do not touch Paddle,
Billing, or Authentication logic. Small PRs only. No production deployment, no merge
without owner approval.

This document is the program control file. It contains the three planning deliverables:

1. Route parity matrix (§1)
2. Migration order (§2)
3. Component reuse report (§3)

The fourth deliverable (first implementation PR) is tracked as `TASK-20260713-002`
in `AI_WORKSPACE/TASKS.md`.

Authoritative design reference: the in-repo `/design-preview` package
(`apps/web/public/design-preview/*.png`, 53 PNGs) per `DEC-20260710-002` and the
2026-07-10 target-inventory handoff. Workspace chrome is "Shell C"
(`apps/web/components/workspace/WorkspaceShell.tsx`) per `DEC-20260712-001`.

## 1. Route parity matrix

Verified against working-tree `main` (`b753885`, includes merged #1010) on 2026-07-13.
"Shell C" = Atelier workspace sidebar island; "AppShell" = legacy dark Nocturne chrome.

| Surface | Route(s) | Current shell | Current content | Data binding | EN/AR | Classification | Closing PR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Dashboard | `/dashboard` | Shell C | `DashboardAtelier` | Real (`getMission`, server-side profile check → `/onboarding`) | Yes (inline T) | **Complete but SHADOWED** — see conflict note below | Owner decision + 1-line config PR |
| Settings | `/settings` | Shell C | `SettingsAtelier` + `useRequireAuth` | Real settings API | Yes | **Complete** (merged; #997 superseded) | — |
| Profile | `/profile` | **Legacy AppShell** | `ProfileAtelier` read view; legacy `ProfileDetail` edit mode; legacy empty/error/loading states | Real (`fetchProfile`, `updateProfile`) | Yes | **Partial** — Atelier content inside legacy shell | M2 |
| Applications | `/applications` → redirect → `/flow` | Legacy AppShell | Legacy Nocturne list/board (`flow/page.tsx`, 604 lines) | Real (`getApplications`, `getApplicationStats`, `updateApplicationStatus`, `createManualApplication`; stages from shared `lib/applicationStatus.ts`) | Yes (`flow*` keys) | **Legacy** — Shell C sidebar already links `/applications`, which lands users back in the dark legacy UI | **M1 (this PR)** |
| Upload | `/upload` | Legacy AppShell | Legacy Nocturne document manager (725 lines: list, upload, rename, set-primary, delete, guest mode) | Real (`listUserFiles`, `uploadCV`, `uploadUserFile`, `updateUserFile`, `setPrimaryFile`, `deleteUserFile`) | Yes | **Legacy** | M3 |
| Pricing | `/subscription` (no `/pricing` route) | Legacy AppShell | Legacy plans + checkout/portal + WhatsApp manual-billing mode | Real (`getSubscriptionPlans`, `getMySubscription`, `createCheckoutSession`, `createCustomerPortalSession`) | Yes | **Legacy + cross-track constraints** (see notes) | M5 |
| Command | `/command` | Own legacy dark chat layout | Legacy chat (2,390 lines): public+auth chat, CV upload, actions, pipeline summary | Real (`sendChatPublic`, chat/actions APIs) | Yes | **Legacy — largest and riskiest surface** | M6 (split) |

**Conflict found during inventory (reported, not fixed here):**
`apps/web/next.config.js` `redirects()` still contains
`{ source: "/dashboard", destination: "/command" }` from the earlier
"chat is the app" era. It predates the merged Shell C `/dashboard` migration
(PR 5A, `85bea03`) and was never removed, so config-level redirects make the
migrated Atelier dashboard page unreachable at `/dashboard` — every visit lands
on `/command` (the teaser middleware currently masks this in production).
Workspace docs (`PROJECT_STATUS.md` "Recent main reality") describe `/dashboard`
as live, so docs and code disagree. Per `OPERATING_RULES.md` this is reported
for an owner decision rather than silently patched: if the Shell C dashboard
should be reachable, the fix is deleting that one redirect line in a dedicated
follow-up PR; if "chat is the app" still stands for guests, the redirect stays
and the docs need correcting. WorkspaceShell's brand link and DashboardAtelier
quick actions already point at `/dashboard`, so today they bounce to `/command`.

Reference notes recorded during inventory:

- **Applications reference** (`en-applications-*.png`): Shell C, eyebrow `APPLICATIONS`,
  serif "Your pipeline.", SAMPLE/BOARD/LIST toggle, five sample columns
  (SAVED/APPLIED/INTERVIEW/OFFER/CLOSED). Production's canonical stage model is the
  four-stage `STAGE_DEFS` (`lead/applied/interview/outcome`) shared with the chat
  pipeline summary (BUG-6 fix). The migration keeps the production data model and
  reproduces the reference composition; the five sample columns are prototype sample
  data, not a contract. The SAMPLE toggle is a prototype affordance and is not shipped
  (no fake data, per DEC-20260710-002).
- **Upload reference** (`en-upload-*.png`): Shell C, "Bring your CV.", documents card +
  drop zone. The mono caption "STORED IN THIS BROWSER ONLY (LOCALSTORAGE)… CONNECT
  LOVABLE CLOUD TO SYNC" is a Lovable prototype artifact and must **not** be reproduced;
  production upload is a real backend flow.
- **Pricing reference** (`desktop-pricing-*-light.png`): uses **Shell A** (marketing
  masthead), not the workspace shell, and shows **two paid plans** (Pro Monthly AED 79,
  Pro Yearly AED 690) with "PREVIEW — BILLING NOT LIVE" captions. The binding product
  contract (`LAUNCH_EXECUTION_PLAN.md` Phase 3) is **one** paid plan (Rico Monthly
  AED 79). The pricing migration is presentation-only, renders whatever plans the real
  API returns, and needs an owner decision on shell placement (Shell A vs workspace).
  It also shares files with held Paddle PR #1008 — see §2.
- **Command reference**: `RicoConsole` prototype
  (`apps/web/components/design-gallery/atelier-console/`, 2,459 lines) and live
  `/rico-preview`. It is a fake-data prototype with DEMO ACTION notices — reference
  for composition only, never a drop-in.

## 2. Migration order

Ordering principle: unblock the already-shipped Shell C navigation first (every sidebar
link should land in the same design world), then finish partially-migrated routes, then
the self-contained legacy routes, and only then the two constrained surfaces (pricing:
cross-track billing overlap; command: sheer size).

| # | PR | Scope | Size | Preconditions / risks |
| --- | --- | --- | --- | --- |
| M1 | **`/applications` → Atelier (this PR)** | New `ApplicationsAtelier` in Shell C; `/flow` becomes a redirect to `/applications`; tests re-pointed | S–M (one component + page swap) | None. Supersedes what #987 wanted for `/flow` (guard) on this route via `useRequireAuth`. Legacy `app-nav.ts` keeps `/flow` (redirect covers it) to avoid churning its regression test — follow-up in M4. |
| M2 | `/profile` shell unification | Swap AppShell → WorkspaceShell; restyle `ProfileDetail` edit mode + empty/error/loading states to Atelier | M | None; content component already Atelier. |
| M3 | `/upload` → Atelier | Port document manager to reference composition (documents card + drop zone); all file APIs unchanged; CV-safety behavior unchanged | M | Keep guest-session upload path intact. |
| M4 | Cross-route QA + nav cleanup | RTL/mobile/dark-island/a11y sweep of M1–M3; point legacy `app-nav.ts` Pipeline at `/applications` and update its test | S | After M1–M3. |
| M5 | Pricing (`/subscription`) presentation | Atelier presentation only; plans from real API; checkout/portal/manual-billing logic untouched | M | **Blocked** on: #1008 (Paddle, HOLD) file-overlap triage; owner decision on Shell A vs workspace shell; one-plan contract vs two-plan reference. Do not start without owner go. |
| M6 | `/command` → Atelier | Largest surface; use `RicoConsole` as composition reference only; split into sub-PRs (theme/shell first, composer, then message/response types) | L (multi-PR) | Own decision record per the standing `/command` DEC carve-out; must not regress public chat, rate limits, or safety affordances. |

Pending owner decision (outside the M-sequence, can run any time): the
`/dashboard` → `/command` stale config redirect conflict (§1). If the owner
confirms the Shell C dashboard should be reachable, it is a one-line
`next.config.js` deletion in its own tiny PR.

Constraints in force for every PR: no redesign (reproduce the approved composition), no
backend/API changes, no Paddle/Billing/Auth-logic changes, no new env vars, no fake
data, EN/AR + RTL first-class, `npm run build` + focused tests green, draft PR, no merge
and no production deployment without owner approval.

## 3. Component reuse report

Reused as-is (zero changes) by M1 and available to M2–M6:

| Asset | Path | Role |
| --- | --- | --- |
| WorkspaceShell (Shell C) | `apps/web/components/workspace/WorkspaceShell.tsx` | Workspace chrome, nav, EN/AR + local light/dark island |
| Workspace palette | `apps/web/components/workspace/theme.ts` | `useWorkspaceTheme()` palette context shared shell ↔ content |
| Atelier tokens/fonts | `apps/web/components/atelier-kit/tokens.ts`, `fonts.ts` | Type stack (Fraunces/Inter/mono) + color tokens |
| `Mono`, `Plate` primitives | `apps/web/components/atelier-kit/primitives.tsx` | Editorial mono labels (AR-safe), corner-tick plates |
| Auth guard | `apps/web/hooks/useRequireAuth.ts` | Same guard pattern as `/settings` |
| API layer | `apps/web/lib/api.ts` | All data calls unchanged (`getApplications`, `getApplicationStats`, `updateApplicationStatus`, `createManualApplication`, …) |
| Status taxonomy | `apps/web/lib/applicationStatus.ts` | `APPLICATION_STATUSES`, `STAGE_DEFS` — single source for board columns (BUG-6) |
| Translations | `apps/web/lib/translations.ts` `flow*` keys | All EN/AR strings for applications functionality reused; only the three reference editorial strings (eyebrow/headline/intro) are new inline T, per `DashboardAtelier` precedent |
| Tests | `apps/web/__tests__/flow-manual-application.test.tsx`, `bug6-status-taxonomy.test.tsx` | Behavior contracts preserved; only the page import/pathname changes |

New in M1: `apps/web/components/applications/ApplicationsAtelier.tsx` (one component).

Reference-only (composition source, never copied wholesale): `RicoConsole` prototype,
`/design-preview` PNGs, `/design-gallery/atelier` specimen, `_atelier/*.css`.

Explicitly not reused on migrated routes: legacy `AppShell`/Nocturne chrome
(`components/layout/*`), Nocturne `Card`/`Badge`/`StatusBadge`/`MaterialIcon` visual
components (functional equivalents are restyled in Atelier), `AuraGlow`.

Retirement path: once M1–M3 land, `/flow`'s legacy page is already gone (redirect);
`AppShell` remains only for out-of-scope routes (`/jobs`, `/queue`, legacy redirects)
until the owner scopes them.
