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

## Program closure — 2026-07-14 (owner decision)

Owner directive: close the UI-unification program after merging #1019 and
splitting #1018, and shift full focus to Rico's intelligent features (AI and
product) — the real user value.

Final state:

| Item | Outcome |
| --- | --- |
| PR 1 foundation (#1017) | **MERGED** `745bb41d` — matrix, canonical nav, /dashboard unblocked, F-1 CI fix |
| PR 3 /command shell (#1020) | **MERGED** `fe0d2199` — authenticated /command in WorkspaceShell (app/dark variant); guest reference chrome untouched |
| Opening films (#1019) | **MERGED** `ccdf7bff` — waitlist retired; random launch film once per session; 7-point launch smoke passed |
| PR 2 (#1018) | **CLOSED, split** per owner decision → **#1021** (A: /subscription Atelier UI only) + **#1022** (B: Paddle Setup-level eventCallback fix). Gate unchanged: real browser Sandbox smoke before B merges/activates |
| PR 4 (command composer/messages) | **DEFERRED** — owner pivot to AI features |
| PR 5 (/queue + dead routes /jobs /signals /archive /saved-searches) | **DEFERRED** (open draft #1016 = /queue guard, still valid) |
| PR 6 (public /about /contact /faq + landing parity) | **DEFERRED** |
| PR 7 (auth verification pass) | **DEFERRED** — all auth pages already on AtelierAuthShell |
| PR 8 (admin + preview-route protection) | **DEFERRED** — note F-4 stands: /design-preview, /rico-preview, /sandbox/* are publicly reachable on the open site |

Re-opening any deferred item requires a fresh owner instruction; the matrix
above (§1–§7) remains the authoritative inventory when that happens.

## Program status — 2026-07-14 (owner re-open)

**REOPENED BY OWNER — FULL-SITE ATELIER MIGRATION REQUIRED.**

The closure above is superseded. The owner directs migrating the **entire** Rico
website to the approved Atelier design — not the seven selected surfaces, but
**every production user-facing route**. All previously DEFERRED items (PR 4/5/6/7/8)
are re-activated. Completed routes are preserved and are **not** rebuilt unless a
per-route audit proves they still expose legacy UI.

### Refreshed route matrix — audited @ `main = 5cf9a6f` (2026-07-14)

`main` advanced past the Phase-0 base (`c11575d`): #1017 (foundation),
#1020 (`/command` → WorkspaceShell), #1019 (opening films), #1021
(`/subscription` Atelier UI), #1022-history merged. Re-audited from the live tree
(33 `page.tsx` routes) — shell import verified per route.

| Route | Shell on `main` 5cf9a6f | Status | Owner step |
| --- | --- | --- | --- |
| `/` | `LandingPageV2` (own layout) | **PARTIAL** — parity verify vs approved public reference | Step 4 |
| `/about` `/contact` `/faq` | legacy glass content (no shell) | **LEGACY** | Step 4 |
| `/privacy` `/terms` `/refund-policy` | Atelier editorial | **DONE** | — |
| `/login` `/signup` | `AtelierAuthShell` (via `LoginForm`/`SignupForm`) | **DONE** | Step 5 verify |
| `/forgot-password` `/reset-password` `/verify-email` | `AtelierAuthShell` | **DONE** | Step 5 verify |
| `/onboarding` | Atelier island | **DONE** | Step 5 verify |
| `/dashboard` | `WorkspaceShell` + `DashboardAtelier` | **DONE** — reachable (stale redirect removed; confirmed absent from `next.config.js`) | — |
| `/command` | `WorkspaceShell` | **SHELL DONE** (#1020); composer/messages/tool-states still legacy | Step 2 |
| `/profile` `/settings` `/applications` `/upload` | `WorkspaceShell` | **DONE** | — |
| `/queue` | **`AppShell`** | **LEGACY** — draft #1016 = auth-guard only (keeps AppShell) | Step 3 |
| `/jobs` `/archive` `/saved-searches` | **`AppShell`** | **LEGACY + DEAD** (config redirect → `/command`) | Step 3 (restore-in-Atelier or delete) |
| `/signals` | legacy glass (no shell) | **LEGACY + DEAD** (config redirect) | Step 3 |
| `/subscription` | `WorkspaceShell` | **SHELL DONE** (#1021); live Paddle Sandbox checkout error outstanding | Step 7 |
| `/subscription/success` | **`DashboardShell`** (only remaining consumer) | **LEGACY** | Step 3/7 |
| `/admin/leads` | bare page (no shell) | **LEGACY** | Step 6 |
| `/design-gallery`(+`/atelier`) `/design-preview` `/rico-preview` `/sandbox/command-primitives` | preview/dev | **PUBLICLY REACHABLE** (F-4) | Step 1 |

Legacy-shell import census on `main` (production routes only): `AppShell` →
`/queue` `/jobs` `/archive` `/saved-searches`; `DashboardShell` →
`/subscription/success`. Step 8 legacy deletion is gated until these reach zero.

### Existing Atelier PRs in flight (do not duplicate)

| Owner step | Existing PR | State | Verdict |
| --- | --- | --- | --- |
| Step 1 — preview-route hygiene (F-4) | **#1026** `fix/protect-internal-preview-routes` | **MERGED** `21ae19a7` (squash) | **DONE** — verified locally (focused 20/20, vitest 387/387, prod build green, prod-mode smoke 5×404 + `/`,`/login` 200) and "Deploy to Production" workflow success. Direct production curl not runnable from CI env (network policy blocks `ricohunt.com`). |
| Step 2 — `/command` composer (slice 4a) | **#1028** `feat/atelier-command-composer` | **DRAFT** — sole active Step-2 implementation PR | **ACTIVE** — Atelier paper/ink composer + sun-red controls in workspace theme tokens; 29/29 composer + 416/416 vitest + build green. Visual gate (EN/AR desktop+mobile Playwright) required before it leaves draft. **Claude is writer** (owner directive); Windsurf reviewer-only. |
| Step 2 — `/command` composer (reference) | **#1029** (editorial-console composer) | **CLOSED, no merge** | **Technical reference only** — do not reopen or re-cut. Superseded by #1028. |
| Step 3 — `/queue` | **#1016** `claude/queue-auth-guard` | DRAFT, guard-only (keeps `AppShell`) | Coordinate: merge-then-migrate, or supersede with full `/queue` Atelier PR |
| Step 7 — Paddle runtime | **#1022** `fix/paddle-event-callback` | DRAFT (split B of #1018) | Real Sandbox browser smoke gates merge |

Out of scope for this program (owner: do not touch): #1024, #1025 (Career Memory
Engine M1), and the abandoned `claude/m1-postgres-integration-tests-*` branch.

**Step 1 complete (#1026 merged @ `21ae19a7`). Step 2 in progress — `/command`
composer/messages/tool-state Atelier migration**, split into slices:

Slice map — **renumbered by owner directive (2026-07-15)** and now fully
landed; this list supersedes the earlier draft map that had "4d — right
rail, 4e — remaining Command chrome":

- **4a — composer** → **#1028 MERGED** (`baa427c`).
- **4b — empty state + message bubbles/markdown** → **#1032 MERGED** (`6dc535c`).
- **4c — tool/permission/attachment/error/loading states** → **#1034 MERGED**
  (`5ac8b2b`); owner production smoke PASS, gate closed 2026-07-15. Built on
  the AtelierCardScope CSS-variable remap over the existing states (the
  draft-spec shimmer + tail caret streaming treatment was superseded by the
  approved AtelierWorkingIndicator; revisit only if the visual-QA pass asks).
- **4d — job-match / application / profile-gap cards** → **#1037 MERGED**
  (`4129015`).
- **4e — right rail ("opportunity panel", from the atelier-console
  ShortlistRail reference; session-derived, display-only) + supporting
  workspace panels (MissionContextBar)** → **#1038 MERGED** (`eff8e66`).

**/command status — corrected by owner directive (2026-07-16). Do NOT record
/command as "Fully Atelier" or visually complete:**

- existing functional migration slices 4a–4e: **merged** (above)
- current Rico business behavior: **preserved**
- owner-approved Obsidian visual parity: **pending**
- Command migration completion: **OPEN until the recording-based parity gate
  passes** (see the Command Obsidian program below)

Profile Dashboard Atelier shipped as **#1041 MERGED** (`d6fa60a`); its real
authenticated production smoke remains **pending owner verification** (does
not block Command work).

### Command Obsidian program (owner-approved, 2026-07-16 — route-specific)

Owner executive design correction: production `/command` must reach visual
parity with the dark acid-lime **"Obsidian" three-column operator console**
in the owner's recording (`Recording 2026-07-16 004205.mp4`). This applies to
`/command` only — it does **not** convert Profile or the rest of Rico to this
language. Canonical source priority, reviewed file inventory, the Phase-1
component mismatch matrix, and risks live in
`design-handoffs/reviewed/2026-07-16-command-obsidian-v4/` (single source —
do not fork). The raw ZIP stays uncommitted in `design-handoffs/incoming/`.

Slice plan (each its own draft PR from latest `main`, full per-PR gate;
presentation-only — no backend/Neon/Paddle/Profile changes, no fabricated
progress states; public/guest surface unchanged unless a slice scopes it):

- **C1 — Obsidian foundation** → **Draft #1043, not ready for merge** (owner
  second-pass correction 2026-07-16): route-scoped tokens, dark canvas +
  texture/aura, top status bar, 260/720/300 proportions, rail toggles, PLUS
  the corrections: truthful **CommandConversationRail** in the canonical
  Sessions position (New chat · current conversation · Clear history · real
  history loading/error; general nav relocated to compact top-bar icons; no
  fabricated sessions — **multi-session history is a separately scoped
  backend capability gap** (ADR-002, PROPOSED)), an interactive **no-regression suite** over the
  real mounted CommandPage (send, streaming tokens, completion, stop/cancel,
  retry, New chat, Clear history, panel/language/theme toggles — network-
  boundary fixtures, real SSE), and all synthetic screenshots stamped
  `MOCKED VISUAL EVIDENCE — NOT FUNCTIONAL SMOKE`. Status: **C1 visual shell
  in Draft; functional evidence partial; transcript interaction parity
  missing; canonical flow parity not implemented.**
- **C2 — real Command event/presentation adapter** (owner directive — NOT a
  typography-only repaint): maintainable mapping from existing production
  truth to canonical Obsidian presentation — user→YOU, thinking→working
  indicator, operationState→safe TOOL label, SSE token/done/error→streaming/
  completed/ERROR+Retry, agentic_ui progress/actions→progress/ASK rows,
  permission_request→checkpoint, proposed_changes→DIFF review,
  attachment_analysis→file intelligence, matches→JOB MATCH,
  applications→TRACKER, profile_gaps→profile intelligence,
  options/next_actions→real controls. Never display hidden chain-of-thought;
  never fabricate PLAN/TOOL steps. Includes the gutter/type-scale rhythm.
- **C3 — composer parity.** **C4 — job intelligence cards.**
- **C5 — right-rail content parity.** **C6 — mobile drawers + RTL +
  route-scoped typography + final recording-parity visual gate.**

Gate: the **19-flow functional acceptance matrix** in the reviewed manifest's
`parity-audit.md` must be fully covered (mounted-component or real
authenticated smoke — stamped synthetic screenshots never count as functional
proof) before `/command` may be declared complete.

Superseded/closed: **#1042** (superseded slice-4c re-cut) — do not reopen or
reuse. Old Atelier `/command` branches must not be reused; each slice starts
from a fresh branch off latest `main`.

Execution order otherwise follows Steps 2→8 above; each step/slice ships as its own
small draft PR cut from latest `main` with the full per-PR gate (vitest + build +
Playwright smoke + EN/AR/RTL + desktop/mobile screenshots + Vercel preview).

### Program authority (owner directive, 2026-07-14)

- **#1028 is the sole active Step-2 slice-4a implementation PR.** Do not open
  parallel `/command` implementation PRs; one active slice at a time.
- **#1029 is closed without merge** and may be used only as a technical reference.
- Remaining phases **derive from the repository's existing Atelier tokens, approved
  migrated surfaces, and the WorkspaceShell/AuthShell patterns** — with EN/AR/RTL,
  accessibility, and mobile parity — **not** from new owner mockups. **No agent
  should pause and request new owner mockups** for the remaining phases.
- **Claude is writer** for the active PR; **Windsurf is reviewer-only** unless
  authority is explicitly transferred.
