# Atelier Full-Site Migration Program

Owner decision (2026-07-13/14): migrate the **entire** Rico website to the approved
Atelier design system. This supersedes the earlier 7-surface scope in
`ATELIER_MIGRATION_PROGRAM.md` (that file remains valid history for M1–M3, which
shipped). No production user-facing route may remain on legacy `AppShell` /
Nocturne / glass styling when this program completes.

- Audit base: `main = c11575d645a803084e9271d12293f2f7eea4b703` (verified live origin/main).
- Audited from the actual repository tree (33 `page.tsx` routes), not from prior docs.
- Binding rules: small reviewable PRs; every PR starts from latest `main`; no backend
  behavior change (unless a confirmed frontend contract defect); no Neon/migrations;
  no Paddle credential/entitlement changes; EN/AR + RTL preserved; no fake success
  states; draft PRs; owner approval before merge.

## Phase 0 — Route matrix (audited @ c11575d)

Status codes: **DONE** (on approved Atelier shell) · **PARTIAL** · **LEGACY** ·
**DEAD** (page exists but a config redirect makes it unreachable) · **REDIRECT** ·
**PREVIEW**.

### 1. Public marketing

| Route | Shell/content today | Auth | Target | Status | Tests | Risk |
| --- | --- | --- | --- | --- | --- | --- |
| `/` | `LandingPageV2` (own layout; carries Fraunces/atelier tokens, predates final Atelier public language; hero freeze #871 history) | authed → `/command` | Atelier public shell | **PARTIAL** — needs parity verification vs approved reference | `landing-page.test.tsx` | M |
| `/about` | `AboutContent` — legacy `GlassPanel`/`AuraGlow` | none | Atelier public | **LEGACY** | none | L |
| `/contact` | `ContactContent` — legacy glass | none | Atelier public | **LEGACY** | none | L |
| `/faq` | `FAQContent` — legacy glass | none | Atelier public | **LEGACY** | none | L |
| `/privacy` | Atelier editorial (C2 pilot #895) | none | — | **DONE** (legal copy verbatim) | none | L |
| `/terms` | Atelier editorial (C1 pilot #879/#880) | none | — | **DONE** | none | L |
| `/refund-policy` | Atelier editorial (#895) | none | — | **DONE** | none | L |

### 2. Authentication

| Route | Shell today | Target | Status | Tests | Risk |
| --- | --- | --- | --- | --- | --- |
| `/login` | `AtelierAuthShell` (via `LoginForm`) | — | **DONE** | `login-password-visibility`, `login-onboarding-routing` | L |
| `/signup` | `AtelierAuthShell` (via `SignupForm`) | — | **DONE** | `signup-auth-edge-cases` | L |
| `/forgot-password` | `AtelierAuthShell` | — | **DONE** | none | L |
| `/reset-password` | `AtelierAuthShell` | — | **DONE** | none | L |
| `/verify-email` | `AtelierAuthShell` | — | **DONE** | `teaser-gate-verify-email` — **ORPHANED, see F-1** | L |
| `/onboarding` | Atelier island (tokens; first-run flow, #955) | — | **DONE** | `onboarding-routing` | L |

### 3. Authenticated workspace

| Route | Shell today | Auth guard | Target | Status | Tests | Risk |
| --- | --- | --- | --- | --- | --- | --- |
| `/dashboard` | `WorkspaceShell` + `DashboardAtelier` (server profile check → `/onboarding`) | server-side | — | **DONE but UNREACHABLE** — stale `next.config.js` redirect `/dashboard → /command` (F-2) | `dashboard-overview`, `mission-today` | M |
| `/command` | **legacy `AppShell`**, 2,390 lines (public + auth chat, CV upload, actions) | public + auth | `WorkspaceShell` | **LEGACY — largest surface** | `command-*` ×5, `chat-*` ×3, `send-double-tap-guard`, `bug18` | **H** |
| `/profile` | `WorkspaceShell` + `ProfileAtelier` | `useRequireAuth` | — | **DONE** | `profile-atelier`, `profile-inline-edit`, `profile-name-edit`, `auth-guard` | L |
| `/settings` | `WorkspaceShell` + `SettingsAtelier` | `useRequireAuth` | — | **DONE** | `auth-guard` | L |
| `/applications` | `WorkspaceShell` + `ApplicationsAtelier` | `useRequireAuth` | — | **DONE** | `flow-manual-application`, `bug6-status-taxonomy`, `auth-guard` | L |
| `/upload` | `WorkspaceShell` (+ `AtelierAuthShell` guest mode) | `useRequireAuth` | — | **DONE** | `upload-shell-composition`, `cv-upload-size-message` | L |
| `/queue` | legacy `AppShell`, old ad-hoc `useAuth` redirect (no `next` return path) | `useAuth` (old pattern) | `WorkspaceShell` | **LEGACY** — open draft **#1016** overlaps (guard-only; keeps AppShell) | none on main (#1016 branch carries 3) | M |
| `/jobs` | legacy `AppShell` (336 lines) | `useAuth` | decision needed | **DEAD** behind config redirect → `/command` | `jobs-api` (lib-level) | L |
| `/signals` | legacy glass (`Navigation`/`TopNav`/`AuraGlow`, pre-AppShell era) | none | decision needed | **DEAD** behind config redirect | `signals-interactions` (tests dead UI) | L |
| `/archive` | legacy `AppShell` (162) | `useAuth` | decision needed | **DEAD** behind config redirect | none | L |
| `/saved-searches` | legacy `AppShell` (102) | `useAuth` | decision needed | **DEAD** behind config redirect | none | L |

### 4. Billing

| Route | Shell today | Target | Status | Tests | Risk |
| --- | --- | --- | --- | --- | --- |
| `/subscription` | **legacy `AppShell`** (697 lines; Paddle UI merged via #1008; one plan Rico Monthly **USD 21.50/mo**, backend-authoritative Price ID) | `WorkspaceShell` | **LEGACY** + live Paddle Sandbox “Something went wrong” checkout error to diagnose | none page-level | **H** (money path) |
| `/subscription/success` | **`DashboardShell`** — ancient pre-Nocturne glass shell (only remaining consumer) | `WorkspaceShell` | **LEGACY** | none | M |

### 5. Admin / internal

| Route | Shell today | Target | Status | Risk |
| --- | --- | --- | --- | --- |
| `/admin/leads` | bare page (no shell; client-side `fetchMe` role check) | Atelier admin workspace shell | **LEGACY** | M (verify role gate during migration) |

### 6. Redirect-only (intentional; documented before any change)

| Source | Destination | Mechanism | Verdict |
| --- | --- | --- | --- |
| `/flow` | `/applications` | page-level `redirect()` | keep (M1 contract) |
| `/chat` | `/command` | `next.config.js` | keep |
| `/dashboard` | `/command` | `next.config.js` | **REMOVE in PR 1** (blocks the shipped Shell C dashboard — F-2) |
| `/jobs`, `/signals`, `/archive`, `/saved-searches` | `/command` | `next.config.js` | keep until PR 5 decision (restore-in-Atelier vs delete pages) |
| `/orchestrate` | `/command` | `next.config.js` | keep (no page exists) |

### 7. Preview / design / dev-only

| Route | Protection today | Verdict (PR 8) |
| --- | --- | --- |
| `/design-gallery`, `/design-gallery/atelier` | robots disallow only — **publicly reachable now that the teaser gate is gone** | protect or remove |
| `/design-preview` | page `noindex` only; **NOT in robots.ts disallow** | protect or remove |
| `/rico-preview` | page `noindex` only; **NOT in robots.ts disallow** | protect or remove |
| `/sandbox/command-primitives` | robots disallow only | protect or remove |

## Phase 0 — Findings requiring action

- **F-1 (blocks every PR gate):** `__tests__/teaser-gate-verify-email.test.ts` imports
  `../middleware`, which `96b7efd6` (remove teaser gate) deleted. The frontend vitest
  suite — a required CI gate — cannot pass on `main`. Fix in PR 1: remove the orphaned
  test (the behavior it pinned — verify-email reachable through the teaser gate — no
  longer exists; reachability is now unconditional).
- **F-2:** stale `/dashboard → /command` config redirect makes the merged Atelier
  dashboard unreachable; `WorkspaceShell`'s brand link and quick actions bounce to
  `/command`. Fix in PR 1 (one line).
- **F-3:** legacy `AppSidebar` nav (`app-nav.ts`) still points Pipeline at `/flow`
  (double-hop via redirect). Fix in PR 1 → `/applications`.
- **F-4:** site is fully open (teaser removed) — preview/design routes are now
  publicly reachable (see §7); `/design-preview` + `/rico-preview` are not even in
  robots disallow. Address in PR 8 (or earlier if owner wants).
- **F-5:** open draft **#1016** (queue auth guard) predates this program; coordinate
  in PR 5 (merge it first, or supersede it with the full `/queue` Atelier migration).
- **F-6:** local clone note: the container's local `main` had diverged (stale
  snapshot); all program branches must be cut from **fetched `origin/main`**.

## Canonical navigation map (target)

- `WorkspaceShell` (authenticated): `/dashboard` (brand/home) · `/command` ·
  `/applications` · `/profile` · `/upload` · `/settings` — plus `/subscription`
  (Account) and `/queue` when migrated.
- Legacy `AppSidebar` (interim, until its consumers are migrated): identical
  destinations; Pipeline → `/applications` (PR 1).
- Public: `/` → login/signup CTAs; footer → `/about` `/faq` `/contact` `/privacy`
  `/terms` `/refund-policy`.
- Auth pages cross-link: login ↔ signup ↔ forgot-password; verify-email → login.
- Guests hitting workspace routes → `/login?next=<path>` (shared `useRequireAuth`).

## PR sequence

| PR | Branch (from latest main) | Scope | Key gates |
| --- | --- | --- | --- |
| **PR 1** | `feat/atelier-pr1-foundation` | This document (route matrix + nav map); remove `/dashboard` stale redirect (F-2); Pipeline nav → `/applications` (F-3); remove orphaned teaser test (F-1). **No visual page changes.** | vitest full suite green (currently red on main via F-1), build green |
| **PR 2** | `fix/subscription-atelier-paddle-checkout` | `/subscription` + `/subscription/success` → `WorkspaceShell`; preserve ALL billing behavior (server-created checkout session, `checkout_session_id` custom data, status, portal, one USD 21.50 plan, backend-authoritative Price ID); diagnose + fix the real Paddle Sandbox checkout error from evidence (client token / Price ID / same-account / active price / domain approval / Paddle.js error callback / network traces); no WhatsApp fallback | targeted tests (shell composition, checkout-session-first, session token pass-through, useful error surface, no-fallback); real browser checkout must open before merge |
| **PR 3** | `feat/atelier-command-shell` | `/command` → `WorkspaceShell` chrome only; zero message-behavior redesign; preserve public/guest chat, streaming, tools, attachments, CV flow, history, limits, safety, EN/AR/RTL | full command-* test set + Playwright smoke |
| **PR 4** | `feat/atelier-command-composer` | composer, attachments, tool states, error states, message bubbles, loading/streaming states | same |
| **PR 5** | `feat/atelier-remaining-workspace` | `/queue` full migration (coordinate #1016); owner decisions + execution for DEAD routes (`/jobs`, `/signals`, `/archive`, `/saved-searches`): restore-in-Atelier or delete pages keeping redirects | auth-guard tests extended |
| **PR 6** | `feat/atelier-public-pages` | `/about`, `/contact`, `/faq` → Atelier public; landing `/` parity verification (owner ruling on hero freeze #871) | landing tests updated |
| **PR 7** | `feat/atelier-auth-verification` | auth pages are already DONE — verification pass only (EN/AR, RTL, mobile screenshots) + residual polish | screenshots |
| **PR 8** | `feat/atelier-admin-cleanup` | `/admin/leads` → Atelier admin shell; protect/remove preview routes (§7); delete `AppShell`, `DashboardShell`, glass legacy components **only after zero production imports** | grep-proven zero imports |

## Definition of done (program)

1. Every production route listed in this matrix. 2. Every user-facing route on an
approved Atelier shell. 3. No production navigation opens legacy UI. 4. Zero
user-facing imports of legacy `AppShell`/`DashboardShell`. 5. Desktop + mobile
consistent. 6. EN/AR + RTL pass. 7. Auth + billing work. 8. Paddle checkout + portal
pass real Sandbox browser smoke. 9. Preview/demo routes removed or protected.
10. Full frontend CI + Playwright green.
