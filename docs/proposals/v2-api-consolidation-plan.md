# Rico Site v2 — API Client Consolidation: Mapping Plan

**Status:** Plan for review — _no migration code until this is approved._
**Author:** Claude (agent)
**Date:** 2026-05-29
**Context:** Phase 2 remainder of `docs/proposals/rico-site-v2.md`. The original proposal
framed this as `lib/client.ts → lib/api.ts`, but that migration already completed and
`lib/client.ts` is gone. The *actual* remaining split is **two parallel API layers**
that grew up side by side. This document maps that split before any code moves.

---

## 1. The real split (as of `main` @ `51e2e1a`)

| Layer | Style | Transport | Size | Extras |
|---|---|---|---|---|
| **`lib/api.ts`** (canonical) | flat per-endpoint `async function`s (`fetchMe`, `login`, `getJobs`, …) | `fetch()` via `/proxy`, `credentials: "include"` | 1267 lines | hand-rolled `ApiError`, mock mode (`NEXT_PUBLIC_USE_MOCK`) |
| **`lib/api/` directory** | namespaced objects (`authApi`, `jobsApi`, `orchestrationApi`, …) on a shared axios instance | `axios` via `/proxy` (browser) / raw base (SSR), `withCredentials: true` | 786 lines (`client.ts` 520 + `orchestration.ts` 232 + `auth.ts` 34) | Zod response validation, 401-redirect interceptor |

### Cookie-correctness finding (important, de-risks the migration)
Both layers route through `/proxy` in the browser:
- `lib/api.ts` — `const PROXY = "/proxy"`, every call `credentials: "include"`.
- `lib/api/client.ts` — `RESOLVED_BASE_URL = typeof window === "undefined" ? API_BASE_URL : "/proxy"`, `withCredentials: true`.

So **neither client makes cross-origin browser calls** — the first-party session-cookie
guarantee (the thing that prevents the Safari/iOS third-party-cookie auth bug) holds in
both. Consolidation is therefore a code-organization change, **not** an auth-transport
change. This is the single most important risk, and it is already mitigated by design.

---

## 2. Consumer inventory

### `lib/api.ts` — dominant (22 importers)
All core pages + auth + shells: `command`, `jobs`, `profile`, `settings`, `upload`,
`onboarding`, `subscription`, `saved-searches`, `archive`, `flow`, `verify-email`,
`forgot/reset-password`, `DashboardShell`, `DashboardStats`, `ProfileSummaryCard`,
`SavedSearchesList`, `LoginForm`, `SignupForm`, `useAuth`, `useAuthStore`.

### `lib/api/` directory — narrow (5 external importers)
| Consumer | Imports | Surface it powers |
|---|---|---|
| `hooks/useOrchestration.ts` | `orchestrationApi.{getTrajectory,getSignals,executeCommand}` | `/signals`, command orchestration |
| `lib/store/useOrchestrationStore.ts` | `orchestrationApi.executeCommand` | orchestration store |
| `app/signals/page.tsx` | (orchestration types/api) | `/signals` |
| `hooks/useLinkVerification.ts` | `linkVerificationApi.{verify,verifyBatch}` | link verification |
| `components/auth/SignupForm.tsx` | `authApi.register` **and** `resendVerification`, `ApiError` from `lib/api` | signup |

### ⚠️ Split-brain finding: `SignupForm.tsx`
It imports **both** clients — `authApi.register` (axios, `lib/api/auth` → `lib/api/client`)
*and* `resendVerification` + `ApiError` (fetch, `lib/api`). Registration and
resend-verification therefore travel different transports with different error shapes in
one component. This is the clearest correctness wart and should be the **first** thing
fixed.

---

## 3. Direction of migration

**Consolidate the `lib/api/` directory into `lib/api.ts`** (collapse the few directory
consumers onto the canonical flat client), because:
- `lib/api.ts` is canonical per `CLAUDE.md` and has 22 importers vs ~5.
- It already owns auth, jobs, applications, settings, profile, CV, onboarding — the
  directory's `authApi/jobsApi/applicationsApi/settingsApi/statsApi` are **duplicates**
  of functions that already exist in `lib/api.ts`.
- Only three capabilities are **unique** to the directory and must be *ported*, not
  dropped: `orchestrationApi`, `linkVerificationApi`, and the Zod-validation +
  401-interceptor conveniences.

### What to preserve from the directory layer
1. **Zod response validation** — `lib/api.ts` is largely unvalidated. Porting orchestration/
   link-verification is the moment to bring their Zod schemas across (keep them).
2. **401-redirect interceptor** — `lib/api.ts` has no global 401 handler. Decide explicitly:
   replicate the public-route-aware redirect as a shared helper, or keep redirects in
   `useAuth`. (Recommendation: a small `handle401()` in `lib/api.ts`'s fetch wrapper,
   mirroring the interceptor's public-route allowlist.)

---

## 4. Phased migration (each phase = its own small PR, build + tests green)

| Phase | Change | Risk | Gate |
|---|---|---|---|
| **A** | Fix `SignupForm` split-brain: route `register` through `lib/api.ts` (add `register()` there if missing, mirroring `login()`'s proxy+credentials+ApiError shape). Remove its `lib/api/auth` import. | Low–Med (auth path) | Manual signup QA both happy + duplicate-email; build+tests |
| **B** | Port `orchestrationApi` → `lib/api.ts` functions (`getTrajectory`, `getSignals`, `executeCommand`) carrying the Zod schemas. Repoint `useOrchestration`, `useOrchestrationStore`, `app/signals`. | Med (`/signals`) | `/signals` renders; orchestration command round-trips; e2e `opportunity-radar.spec` |
| **C** | Port `linkVerificationApi` → `lib/api.ts` (`verifyLink`, `verifyLinkBatch` + schemas). Repoint `useLinkVerification`. | Low | link-verify happy + cache path |
| **D** | Decide + implement the shared 401 handling in `lib/api.ts` fetch wrapper (or confirm `useAuth` covers it). | Low | authed-route 401 redirects; public routes don't |
| **E** | Delete `lib/api/client.ts`, `lib/api/auth.ts`, `lib/api/orchestration.ts` **only after** `grep -r "@/lib/api/" apps/web` returns zero non-self imports and `npm run build` is clean. | Low | zero residual imports; build green |

Phases A–C are independent and can land in any order; **D before E**; **E last**.

---

## 5. Risks & mitigations
- **Auth regression on signup (Phase A).** Mitigate: mirror `login()` exactly (proxy,
  `credentials:"include"`, `ApiError`), QA duplicate-email path (the 409 → friendly copy
  currently keyed off axios error shape — must be re-mapped to `ApiError.status`).
- **Losing Zod validation.** Mitigate: port schemas, don't drop them (§3.1).
- **`/signals` is a live surface with an e2e spec.** Mitigate: Phase B must keep
  `e2e/opportunity-radar.spec.ts` green.
- **Error-shape divergence.** axios throws `AxiosError` (`.response.status`); `lib/api.ts`
  throws `ApiError` (`.status`). Every repointed `catch` must be re-checked — this is the
  most likely place for a silent behavior change.

## 6. Non-goals
- No backend, DB, billing, auth-contract, job-logic, or CV-parsing changes.
- No transport change (both already proxy-routed).
- No new endpoints — pure consolidation.

## 7. Test gates (every phase)
- `cd apps/web && npm run build`
- `cd apps/web && npm test` (28+ unit; keep green)
- `cd apps/web && npm run check:contrast` (unaffected, but cheap)
- Targeted manual/e2e per phase as noted above.

---

_Awaiting review. Recommend approving Phase A first (it fixes a real split-brain bug),
then B/C/D/E in sequence. No migration code until approved._
