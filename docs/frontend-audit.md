# Frontend Audit Inventory

Status date: 2026-05-24

Scope: `apps/web/app`, `apps/web/components`, `apps/web/hooks`, and `apps/web/lib`.

Render/backend status: backend-dependent behavior must be treated as unavailable until Render hosting is restored. This audit does not require Render, Stripe, Telegram, Neon, migrations, or backend endpoint checks.

## Inventory Commands

Windows PowerShell equivalents used:

```powershell
Get-ChildItem -Path apps\web\app -Recurse -Include page.tsx,layout.tsx | Sort-Object FullName
Get-ChildItem -Path apps\web\components -Recurse -File | Sort-Object FullName
Get-ChildItem -Path apps\web\hooks -Recurse -File | Sort-Object FullName
Get-ChildItem -Path apps\web\lib -Recurse -File | Sort-Object FullName
```

## Route Inventory

| File / route | Purpose | Backend dependency | State coverage | Mobile risk | Status | Action |
| --- | --- | --- | --- | --- | --- | --- |
| `/` | Public landing page | none for primary render | static page; pricing links depend on subscription page | medium | keep | Review mobile hero/pricing after PR #193 and Vercel preview. |
| `/applications` | Tracked application list and status updates | applications API | loading/error present through shared states; mutation errors use toast | medium | keep | Follow-up: verify empty/error states on mobile. |
| `/archive` | Chat history/archive view | chat history API | loading/error/empty present | medium | keep | Follow-up: verify long messages and backend outage copy. |
| `/chat` | Redirect to canonical command page | none | server redirect only | low | merge/redirect | Keep redirect to `/command`; no duplicate UI. |
| `/command` | Rico chat, public/auth chat, CV upload, profile confirm | auth, chat, public chat, upload, profile confirm APIs | backend maintenance gating present; normal loading/error exists but route is large | high | fix | Follow-up PR: split state handling, audit mobile input overlap, and test outage/normal states. |
| `/dashboard` | Authenticated overview | auth/session and dashboard data APIs | redirects to onboarding; summary cards have partial loading/error | medium | keep | Follow-up: verify SSR/auth behavior after backend returns. |
| `/flow` | Application flow board/manual tracking | applications API | loading/error/manual submit states present | high | fix | Follow-up: mobile board layout and mutation error review. |
| `/forgot-password` | Password reset request | auth/password reset API | submit/loading/error states present | low | keep | Verify production copy after backend returns. |
| `/jobs` | Job match list and actions | jobs/applications APIs | loading/error/empty present; action toasts present | high | fix | Follow-up: mobile card density and failed action states. |
| `/layout` | Root document layout and metadata | none | not a page state surface | low | keep | Keep as canonical layout. |
| `/login` | Sign-in page | auth API | backend maintenance gating present in form | medium | keep | Remove hard-coded maintenance flag after Render recovery plan is complete. |
| `/onboarding` | CV upload/profile confirmation onboarding | auth, upload, profile APIs | multi-step loading/error states present | high | fix | Follow-up: mobile form length, auth redirect, and outage state review. |
| `/orchestrate` | Redirect to canonical command page | none | server redirect only | low | merge/redirect | Keep redirect to `/command`; no duplicate UI. |
| `/profile` | Profile read/edit | profile API | loading/error/empty/edit states present | high | fix | Follow-up: mobile edit controls and save failure recovery. |
| `/reset-password` | Password reset completion | auth/password reset API | token/error/success states present | low | keep | Verify invalid-token copy after backend returns. |
| `/sandbox/command-primitives` | UI primitive sandbox | none | static demo | low | archive/remove | Consider excluding from production navigation or moving to docs/dev-only. |
| `/saved-searches` | Saved search list | saved searches/search context API | loading/error/empty present | medium | keep | Follow-up: verify empty-state CTA during backend outage. |
| `/settings` | User settings and channel preferences | settings, health, auth APIs | partial; maintenance and Telegram fake-state cleanup in PR #193 | medium | keep | Merge PR #193, then verify normal backend-on copy. |
| `/signals` | Intelligence signals | orchestration API/store | loading/error present through hook | medium | keep | Follow-up: empty state and mobile card stacking. |
| `/signup` | Account registration | auth/register API | form error/loading states in component | low | keep | Consider backend maintenance copy parity with login. |
| `/subscription` | Plan cards, checkout, portal | subscription plans, current subscription, checkout, portal APIs | maintenance gating added in PR #192; stronger static/paused behavior in PR #193 | medium | keep/fix later | Merge PR #193; verify live plan/status only after Render returns. |
| `/subscription/success` | Checkout success landing | subscription/session follow-up link | static success copy | low | needs backend later | Verify real checkout success semantics only after Stripe/backend validation resumes. |
| `/upload` | CV upload entry point | upload API | upload/loading/error states present | medium | keep | Align with `/onboarding` and `/command` upload behavior later. |

No `/command-v2` route exists in the current `apps/web/app` tree.

## Shared Component Inventory

| File / component | Purpose | Backend dependency | State coverage | Mobile risk | Status | Action |
| --- | --- | --- | --- | --- | --- | --- |
| `auth/LoginForm.tsx` | Login form | auth API | maintenance/loading/error present | medium | keep | Remove temporary outage flag after backend recovery. |
| `auth/SignupForm.tsx` | Signup form | register API | loading/error present | medium | keep | Add backend maintenance copy parity if outage continues. |
| `DashboardShell.tsx` | Authenticated page frame | auth/session via `useAuth` | redirects when unauthenticated | medium | keep | Verify sidebar/header on small screens. |
| `DashboardStats.tsx` | Dashboard metrics | jobs/applications/settings APIs | loading/error partial | medium | fix | Consolidate loading/error cards. |
| `jobs/JobCard.tsx` | Job display/action card | action callbacks only | caller-owned mutation states | high | keep | Mobile action layout review. |
| `LandingPage.tsx` | Marketing/landing content | none directly | static | medium | keep | Check pricing links during subscription maintenance. |
| `layout/Navigation.tsx` | Navigation shell | none directly | static nav | medium | keep | Verify route list excludes sandbox/dev-only pages. |
| `layout/Sidebar.tsx` | Sidebar navigation | none directly | static nav | medium | keep | Mobile collapse/overflow review. |
| `layout/TopNav.tsx` | Top navigation | none directly | static nav | low | keep | Keep. |
| `ProfileSummaryCard.tsx` | Profile summary widget | profile API | loading/error/ready present | medium | keep | Align errors with shared `ErrorState`. |
| `SavedSearchesList.tsx` | Saved searches widget | saved searches API | loading/error/empty present | medium | keep | Verify route duplication with page-level list. |
| `shared/AppShell.tsx` | Alternate authenticated shell | auth/session | redirects when unauthenticated | medium | fix | Compare with `DashboardShell`; possible duplication. |
| `shared/EmptyState.tsx` | Empty-state primitive | none | reusable | low | keep | Keep. |
| `shared/ErrorState.tsx` | Error-state primitive | none | reusable | low | keep | Keep. |
| `shared/LoadingState.tsx` | Loading-state primitive | none | reusable | low | keep | Keep. |
| `shared/PageHeader.tsx` | Header primitive | none | static | low | keep | Keep. |
| `StatusCard.tsx` | Dashboard/status card | none directly | static card states | low | keep | Keep. |
| `ui/*` primitives | Visual primitives, buttons, panels, icons, toast | none | mostly caller-owned | low | keep | Prefer reuse before adding new card styles. |
| `ui/rico/*` primitives | Rico command/chat UI primitives | none directly | caller-owned | medium | keep | Audit command mobile composition before refactor. |

## Hooks Inventory

| File | Purpose | Backend dependency | State coverage | Status | Action |
| --- | --- | --- | --- | --- | --- |
| `hooks/useAuth.ts` | Current user/session state | `/me` auth API or mock mode | ready/user state; fallback guest/null | keep | Verify outage behavior after backend returns. |
| `hooks/useOptimisticUpdates.ts` | Optimistic mutation helper | caller-owned | rollback helper | keep | Keep. |
| `hooks/useOrchestration.ts` | Signals/orchestration hook | orchestration API/store | loading/error from store | keep | Pair with `/signals` empty-state review. |
| `hooks/useToast.ts` | Toast state | none | local queue | keep | Keep. |

## Lib Inventory

| File | Purpose | Backend dependency | Status | Action |
| --- | --- | --- | --- | --- |
| `lib/api.ts` | Main proxy API client and types | all app backend APIs | keep | Large file; split by domain later if API churn continues. |
| `lib/api/auth.ts` | Auth API helpers | auth API | keep | Check duplication with `lib/api.ts`. |
| `lib/api/client.ts` | Axios/client helper | backend proxy | keep | Check if still used consistently. |
| `lib/api/orchestration.ts` | Orchestration API helpers | orchestration API | keep | Keep with store. |
| `lib/auth.ts` | Auth utility | token/session helper | keep | Verify overlap with store/hook. |
| `lib/cache/index.ts` | Client cache/indexedDB helpers | optional local persistence | keep | Review stale retry behavior later. |
| `lib/config/*` | Static config | none | keep | Keep. |
| `lib/intelligence/*` | Frontend scoring/trajectory helpers | none | keep | Keep separate from backend scoring. |
| `lib/memory/index.ts` | Local memory helper | local persistence | keep | Review privacy/storage copy later. |
| `lib/redirect.ts` | Auth redirect helper | none | keep | Keep. |
| `lib/schemas/index.ts` | Zod schemas | API response validation | keep | Continue using for boundary validation. |
| `lib/store/*` | Zustand auth/orchestration stores | backend APIs through helpers | keep | Audit duplicate auth sources later. |
| `lib/utils.ts` | Utility helpers | none | keep | Keep. |

## Priority Findings

1. Fake/misleading states
   - Settings Telegram status was misleading and is addressed in PR #193.
   - Subscription maintenance behavior is clearer in PR #193; live checkout remains paused.
   - Signup does not currently have the same maintenance framing as login.

2. Broken or duplicate routes
   - `/chat` and `/orchestrate` are intentional redirects to `/command`.
   - `/command-v2` is absent.
   - `/sandbox/command-primitives` is a dev/demo surface; decide whether to keep in production build.

3. Missing loading/error/empty states
   - Most data pages have some coverage.
   - `/command`, `/onboarding`, `/profile`, `/jobs`, and `/flow` need deeper state-path tests because they have multi-step mutations.

4. Mobile layout risks
   - Highest risk: `/command`, `/onboarding`, `/jobs`, `/flow`, `/profile`.
   - Medium risk: `/subscription`, `/settings`, `/applications`, `/archive`, landing pricing section.

5. Component duplication
   - `DashboardShell`, `shared/AppShell`, and `layout/*` should be compared before more shell/navigation changes.
   - `lib/api.ts` overlaps with `lib/api/*`; avoid adding new API helpers until ownership is clarified.

6. Design/copy polish
   - Keep outage copy centralized if maintenance continues.
   - Avoid claiming live backend, Telegram, or subscription status while Render is unavailable.

## Targeted Follow-up PRs

1. `fix/frontend-signup-maintenance-copy`
   - Add backend maintenance framing to signup to match login.
   - Frontend-only.

2. `fix/command-mobile-state-audit`
   - Test `/command` mobile input, disabled states, CV upload, and outage copy.
   - No backend validation; mock only.

3. `fix/profile-flow-mobile-errors`
   - Review `/profile` and `/flow` loading/error/mutation states on mobile.
   - Keep changes targeted to visible state handling.

4. `chore/sandbox-route-decision`
   - Decide whether `/sandbox/command-primitives` stays, redirects, or moves to dev-only docs.

5. `chore/frontend-shell-dedupe-plan`
   - Compare `DashboardShell`, `shared/AppShell`, and `layout/*`.
   - Produce a plan before refactoring.

## Validation For This Audit PR

Run:

```powershell
npm --prefix apps/web run lint
npm --prefix apps/web run build
node apps/web/node_modules/typescript/bin/tsc -p apps/web/tsconfig.json --noEmit
```

Do not run:

- Render deploy
- Stripe test events
- Telegram production validation
- Neon/live backend validation
- Backend endpoint checks
- Migrations
- Agent/core backend refactors
