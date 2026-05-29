# Rico Full-System Regression Audit (Frontend + Backend)

Branch audited: `claude/adoring-curie-DqJZ6`
Scope: `apps/web/**` (frontend) **and** `src/api/**` (FastAPI backend contracts, auth/session,
proxy, CORS/cookies). No changes to DB schema, billing rules, job matching, CV parsing, or
service worker (none of those were proven broken).
Related issues: #281 (P0 master), #196, #153, #263, #83, #187, #85, #20.

> **Important divergence from issue #281.** Issue #281 was written against a different
> broken preview branch that contained a theme system, i18n (`lib/translations.ts`),
> and components such as `CommandClient.tsx`, `ThemeSwitcher.tsx`, `LanguageSwitcher.tsx`,
> and `MobileControls.tsx`. **None of those files exist on this branch.** This branch is a
> cleaner, dark-only implementation. The audit below maps every symptom in #281 to the
> *actual* files present here, and marks symptoms that do not exist on this branch as such.

---

## 1. Real frontend file map

### Routes (`apps/web/app/**/page.tsx`)

| Route | File | Shell | Auth model | Status |
|---|---|---|---|---|
| `/` | `app/page.tsx` → `components/LandingPage.tsx` | none (own header) | `useAuth`, redirects authed → `/command` | OK |
| `/command` | `app/command/page.tsx` | none (own header) | `fetchMe` → `chatAudience` | **Broken (auth state + input)** |
| `/login` | `app/login/page.tsx` | none | public | OK |
| `/signup` | `app/signup/page.tsx` | none | public | OK |
| `/forgot-password` | `app/forgot-password/page.tsx` | none | public | OK |
| `/reset-password` | `app/reset-password/page.tsx` | none | public | OK |
| `/onboarding` | `app/onboarding/page.tsx` | none | mixed | Needs manual QA |
| `/upload` | `app/upload/page.tsx` | none | mixed | Needs manual QA |
| `/chat` | `app/chat/page.tsx` | none | public/session | Needs manual QA |
| `/dashboard` | `app/dashboard/page.tsx` | `DashboardShell` | authed | OK (shell safe-area) |
| `/jobs` | `app/jobs/page.tsx` | `DashboardShell` | authed | OK (shell safe-area) |
| `/applications` | `app/applications/page.tsx` | `DashboardShell` | authed | OK (shell safe-area) |
| `/profile` | `app/profile/page.tsx` | `DashboardShell` | authed | OK (shell safe-area) |
| `/settings` | `app/settings/page.tsx` | `DashboardShell` | authed | OK (shell safe-area) |
| `/saved-searches` | `app/saved-searches/page.tsx` | `DashboardShell` | authed | OK (shell safe-area) |
| `/signals` | `app/signals/page.tsx` | none (TopNav target) | authed | Needs manual QA |
| `/flow` | `app/flow/page.tsx` | none (TopNav target) | authed | Needs manual QA |
| `/archive` | `app/archive/page.tsx` | none (TopNav target) | authed | Needs manual QA |
| `/orchestrate` | `app/orchestrate/page.tsx` | none | authed | Needs manual QA |
| `/subscription` | **does not exist** | — | — | #187 references a missing page |

### Shared layout / shell

| File | Role | Notes |
|---|---|---|
| `app/layout.tsx` | root layout | `<html className="dark">`, fonts, metadata. **No `viewport` export** → `env(safe-area-inset-*)` inert. |
| `components/DashboardShell.tsx` | **the live shared shell** (6 pages) | fixed `TopNav` + fixed bottom `Navigation`, `main` `pt-36 pb-52`. |
| `components/layout/TopNav.tsx` | floating top pill, `fixed top-4 z-50` | no safe-area-top. |
| `components/layout/Navigation.tsx` | floating bottom pill, `fixed bottom-6 z-50` | no safe-area-bottom. |
| `components/layout/Sidebar.tsx` | sidebar | used by `AppShell` only. |
| `components/shared/AppShell.tsx` | **dead code** | referenced only by itself; no page imports it. Removal candidate (out of containment scope). |

### Supporting libs / hooks

| File | Role |
|---|---|
| `lib/api.ts` | canonical API client (`fetchMe`, `login`, `logout`, chat, CV, profile…). All client calls go through `/proxy`. |
| `lib/api/auth.ts`, `lib/api/client.ts`, `lib/api/orchestration.ts` | secondary API modules. |
| `hooks/useAuth.ts` | auth hook used by `/` and others. |
| `lib/store/useAuthStore.ts` | auth store. |
| `lib/redirect.ts` | `buildAuthHref` (login/signup redirect targets). |
| `components/ui/MaterialIcon.tsx` | **SVG-based** icon set (no icon font dependency). |
| `app/globals.css` | dark cinematic tokens. No light-mode tokens, no `color-scheme`. |
| `tailwind.config.ts` | design tokens. Has a static `"safe-area": "48px"` spacing token (unused, **not** `env()`). |

### Not present (so cannot be the cause here)

`apps/web/contexts/`, `ThemeContext.tsx`, `ThemeSwitcher.tsx`, `LanguageContext.tsx`,
`LanguageSwitcher.tsx`, `MobileControls.tsx`, `lib/translations.ts`,
`app/command/CommandClient.tsx`, `apps/web/public/` (no manifest / PWA icons),
any `dark_mode` / `light_mode` / `desktop_windows` strings, any `material-icons` /
`material-symbols` font, any `useTheme` / `next-themes`.

---

## 2. Actual command page file path

`apps/web/app/command/page.tsx` (single client component `CommandPage`; there is **no**
`CommandClient.tsx`).

## 3. Actual app shell / nav file path

- Live shared shell: `apps/web/components/DashboardShell.tsx`
- Top nav: `apps/web/components/layout/TopNav.tsx` (`fixed top-4`)
- Bottom nav: `apps/web/components/layout/Navigation.tsx` (`fixed bottom-6`)
- Dead alternative shell: `apps/web/components/shared/AppShell.tsx` (unused)

## 4. Actual command input component path

There is **no** separate input component. The command input is inline inside
`apps/web/app/command/page.tsx` (the floating bar at the bottom of `CommandPage`,
the `<textarea ref={textareaRef}>` block). A generic `components/ui/CommandInput.tsx`
exists but is **not** used by `/command`.

## 5. Actual auth / session hook / API path

- `fetchMe(signal)` in `apps/web/lib/api.ts` → `GET /proxy/api/v1/me` → `{ authenticated, email, role, guest }`.
- `logout()` in `apps/web/lib/api.ts` → `POST /proxy/api/v1/auth/logout`.
- `/command` consumes `fetchMe` directly into local `chatAudience` state (`"checking" | "authenticated" | "public"`).
- `hooks/useAuth.ts` + `lib/store/useAuthStore.ts` are used by other routes (`/`).

---

## 6. Open issues → current codebase mapping

Legend — **Area**: FE (frontend), BE (backend), Infra/CI, Product.
**Containment**: ✅ addressed by this pass · ◑ partially · ✖ out of scope.

| # | Title (short) | Area | Maps to current code | Containment |
|---|---|---|---|---|
| 281 | P0 frontend regression audit | FE | command page, DashboardShell, TopNav/Navigation, layout.tsx, globals.css | ✅ this report + fixes |
| 196 | Audit frontend pages/components | FE | this report | ✅ |
| 153 | P0 chat failure + restore mobile | FE/BE | command page error branches (present) + input visibility; backend chat error ✖ | ◑ input/mobile only |
| 263 | Audit product behavior / dead links | FE/Product | route map above; dead-link sweep pending | ◑ |
| 83 | Critical UX/product audit | FE/Product | this report | ◑ |
| 133 | Chat follow-up intent regression | BE | `src/rico_chat_api.py` | ✖ backend |
| 101 | Public CV profile persistence | BE | `src/api/routers/rico_chat.py` | ✖ backend |
| 187 | Subscription frontend polish | FE | **no `/subscription` page exists** — needs build | ✖ not present |
| 140 | Redesign auth/onboarding flow | FE | login/signup/onboarding pages | ✖ future |
| 138 | Cinematic redesign system (epic) | FE | globals.css + components | ✖ future |
| 99 | Companion UX (match/rejection/interview) | FE | command page + new views | ✖ future |
| 27 | Preserve frontend prototype | Docs | archival | ✖ |
| 26 | Build website + dashboard | FE | mostly done (pages exist) | ✖ mostly done |
| 85 | OpenAI 429 + frontend visibility | BE/FE | `response_source`/`getSourceLabel` already surfaced in command page | ◑ FE part present |
| 269 | Link verifier tests in qa-tests.yml | CI | `.github/workflows` | ✖ CI |
| 213 | Career execution state machine | BE | `src/agent/**` | ✖ backend |
| 198 | Defensive bug hunt (DB/webhooks) | BE | `src/**` | ✖ backend |
| 179 | Core v2 chat backend | BE | `src/rico_chat_api.py` | ✖ backend |
| 154 | Harden/retire Daily Job Bot | BE | `src/run_daily.py` | ✖ backend |
| 147 | Engineering guardrails/hardening | Infra/BE | repo-wide | ✖ backend |
| 143 | AI-first chat routing boundaries | BE | `src/agent/runtime.py` | ✖ backend |
| 135 | Activate DeepSeek/HF/Jotform | BE/Env | Render env + `src/rico_*` | ✖ backend |
| 127 | P0/P1 production hardening | Infra/BE | repo-wide | ✖ backend |
| 124 | Audit disconnected features | Mixed | repo-wide | ◑ FE portion in report |
| 118 | SpikingBrain LLM provider | BE | `src/rico_openai_agent.py` | ✖ backend |
| 105 | Rico Agent OS | BE | `src/agent/**` | ✖ backend |
| 98 | Verify save route/resolvers | BE | `src/api/routers/**` | ✖ backend |
| 97 | Map user identity flows | BE | auth/webhooks | ✖ backend |
| 96 | Unify Jotform/CV/chat profile | BE | `src/rico_*` | ✖ backend |
| 48 | God mode connect providers | BE | `src/rico_*` | ✖ backend |
| 20 | Production-safe user model | BE | `src/api/auth.py`, `deps.py` | ✖ backend |
| 13 | Universal multi-user agent | Product | architecture | ✖ product |
| 10 | Ship production stack | Infra | deploy | ✖ infra (done) |

All 33 open issues reviewed and classified. Only the FE-containment subset (#281, #196,
#153 mobile/input, #83/#263 partial) is actioned in this pass; everything else is recorded
as out-of-scope (backend / infra / future feature) per the explicit guardrails.

---

## 6b. Backend API map & contract status

FastAPI app: `src/api/app.py`. All routers mounted under `/api/v1/*`. Auth context is
hydrated from the `access_token` httpOnly cookie by middleware
(`hydrate_request_auth_context`). Every client call reaches the backend through the
Next.js same-origin proxy (`/proxy/* → <backend>/*`).

| Frontend call (`lib/api.ts`) | Backend route | Zod schema | Required fields verified | Status |
|---|---|---|---|---|
| `GET /api/v1/me` | `auth.py:267` | `MeResponseSchema` | `email`(nullable),`role`,`authenticated`,`guest?` | ✅ match |
| `POST /api/v1/auth/login` | `auth.py:226` | `LoginResponseSchema` | `message`,`email` | ✅ match |
| `POST /api/v1/auth/logout` | `auth.py:258` | — | — | ✅ |
| `POST /api/v1/auth/register` | `auth.py:373` | `RegisterResponseSchema` | `email`,`role`,`created` | ✅ |
| `POST /api/v1/auth/forgot-password` | `auth.py:303` | — | `message` | ✅ |
| `POST /api/v1/auth/reset-password` | `auth.py:344` | — | `message` | ✅ |
| `POST /api/v1/rico/chat` | `rico_chat.py` | `RicoChatResponseSchema` (all optional, passthrough) | tolerant | ✅ |
| `POST /api/v1/rico/chat/public` | `rico_chat.py:554` | `RicoChatResponseSchema` | tolerant | ✅ |
| `POST /api/v1/rico/upload-cv` | `rico_chat.py:873` | `UploadCVResponseSchema` | `ok`,`status` returned | ✅ match |
| `POST /api/v1/rico/confirm-cv-profile` | `rico_chat.py:1059` | `ConfirmCVProfileResponseSchema` | `ok`,`status`,`message`,`profile` returned | ✅ match |
| `GET /api/v1/rico/profile` | `rico_chat.py` | `RicoProfileResponseSchema` | `profile_exists` returned | ✅ match |
| `GET/POST/DELETE …/rico/settings/saved-searches` | `rico_chat.py` | `SavedSearchesResponseSchema` | `searches`,`total` | ✅ |
| `GET /api/v1/jobs`, `GET /api/v1/jobs/{id}` | `jobs.py:47/59` | `JobListResponseSchema` | normalized client-side | ✅ |
| `GET /api/v1/applications` | `applications.py:91` | `ApplicationListResponseSchema` | normalized client-side | ✅ |
| `PATCH /api/v1/applications/{id}` | `applications.py:119` | `StatusUpdateResponseSchema` | `status`,`job_id`,`message` | ✅ |
| `GET /api/v1/applications/stats` | `applications.py:142` | — | record | ✅ |
| `GET/PUT /api/v1/settings` | `settings.py:18/23` | `SettingsResponseSchema` | ✅ |
| `POST /api/v1/onboarding/submit` | `onboarding.py` | — | `status`,`updated_fields` | ✅ |
| `POST /api/v1/agent/chat` | `agent.py:17` | `AgentUIResponseSchema` | ✅ (unused by current UI) |
| `GET /health`, `GET /api/v1/version` | `app.py:199` / version router | `HealthResponse` | ✅ |
| **subscription** (`subscription.py`, mounted) | exists | — | **no frontend page** (#187) |

**Conclusion: zero missing routes and zero response-shape contract mismatches.** The only
contract-level defect is the **proxy target env var** (see 7.6), which is a frontend config
file, not a backend route.

### Cookie / session behaviour (`src/api/auth.py`)

| Attribute | Value | Source |
|---|---|---|
| Cookie name | `access_token`, `httpOnly` | `_COOKIE_NAME` |
| `Secure` | `COOKIE_SECURE` env, else `true` in prod | `_cookie_secure()` |
| `SameSite` | `none` when Secure, else `lax` | `_cookie_samesite()` |
| `Domain` | explicit `COOKIE_DOMAIN`, else `.ricohunt.com` when APP_URL is ricohunt.com **or** env is production; else host-only | `_cookie_domain()` |
| `Path` | `/` | `_cookie_set_kwargs()` |

`SameSite=None; Secure` is correct for the proxy model. CORS (`app.py:152`) allows
`["*"]` with `allow_credentials=False` when `CORS_ORIGINS=*`; this is **not** a problem
because the browser never calls the backend cross-origin — all traffic is same-origin via
`/proxy`, so CORS credentials rules never apply to real requests.

---

## 7. Root-cause summary (reported symptoms)

### 7.1 Signed-in user sees public auth links on `/command` — **REAL, fixed**

`app/command/page.tsx` initialises `chatAudience = "checking"` and the header renders a
**binary** ternary:

```tsx
{chatAudience === "authenticated" ? ( …Dashboard / Sign out… )
                                  : ( …Sign in / Sign up free… )}
```

So `"checking"` falls into the public branch. Consequences:
1. Every signed-in user sees a **flash** of "Sign in / Sign up free" during the `fetchMe`
   round-trip.
2. The effect persists if `fetchMe` is slow or errors: a 5 s safety timeout **and** the
   `.catch` both force `chatAudience = "public"`. On a cold Render backend (documented to
   take up to a minute), a genuinely signed-in user is left showing public auth links.

**Fix:** make the header three-way. During `"checking"` render a neutral, non-committal
placeholder (skeleton) that reveals **no** auth state; show "Sign in / Sign up free" only
after `"public"` is confirmed.

### 7.2 Command input hidden / "almost invisible, covered at the bottom" — **REAL, fixed**

The chat column is `h-[calc(100vh-57px)]` and the input is `absolute bottom-0` inside it.
On mobile, `100vh` includes the area behind the browser chrome, so `bottom-0` sits **below
the visible fold** → the input is pushed off-screen / under the toolbar. There is also no
safe-area padding, so on an installed iOS PWA it collides with the home indicator.

**Fix:** switch the column height to `100dvh` (dynamic viewport height) and add
`env(safe-area-inset-bottom)` padding to the input bar. Also requires the `viewport-fit=cover`
viewport (see 7.4) for the inset to resolve.

### 7.3 Shell / nav overlap — **REAL (safe-area), fixed**

`DashboardShell` uses `TopNav` (`fixed top-4`) and `Navigation` (`fixed bottom-6`). The
`main` padding (`pt-36 pb-52`) clears them on normal viewports, so there is no content
overlap on desktop/Android. The real defect is **no safe-area handling**: on notched / PWA
devices the top pill collides with the status bar/notch and the bottom pill collides with
the home indicator, and `env()` was inert because no viewport set `viewport-fit=cover`.

**Fix:** add `viewport-fit=cover` viewport, and make the floating navs respect safe area:
`top-[max(1rem,env(safe-area-inset-top))]` and `bottom-[max(1.5rem,env(safe-area-inset-bottom))]`.
These are backward-compatible (`env()` = 0 on non-notched devices → identical layout).

### 7.4 Broken theme controls (`dark_mode` / `light_mode` / `desktop_windows` raw text) — **NOT PRESENT on this branch**

There are **no theme controls** in this branch: no `ThemeSwitcher`, no `useTheme`, no
`next-themes`, no `dark_mode`/`light_mode`/`desktop_windows` strings, and `MaterialIcon` is
SVG-based (so it cannot render Material font names as raw text). The app is dark-only via
`<html className="dark">`. This is already the state #281's "emergency containment rule"
prescribes ("ship Dark only until each page is theme-safe").

**Action taken (hardening):** lock the dark-only stance explicitly by adding
`color-scheme: dark` so native browser UI (form controls, scrollbars, autofill) renders dark
and never flashes white. No control is added; nothing to remove.

### 7.5 Light-mode unreadable pages — **NOT REACHABLE on this branch**

Because there is no theme toggle and `<html>` is fixed to `dark`, pages can never be switched
to light, so the "unreadable light mode" class of bug from the audited preview cannot occur
here. `color-scheme: dark` reinforces this. Building a real, theme-safe light mode is a
future PR (out of containment scope; do not attempt Arabic/light yet).

### 7.6 Proxy target env var mismatch — **REAL, fixed (frontend config)**

`apps/web/next.config.js` resolved the `/proxy/*` rewrite target from only
`BACKEND_API_BASE_URL || NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"`. But
`lib/api.ts`, `lib/api/client.ts`, `app/dashboard/page.tsx`, and `CLAUDE.md` all use
**`NEXT_PUBLIC_RICO_API`** as the documented production backend var. If a deployment sets
only `NEXT_PUBLIC_RICO_API` (as CLAUDE.md documents), the proxy silently fell back to
`http://localhost:8000`, so **every** client-side call (`/me`, chat, jobs, applications…)
hit a dead localhost target. That single misconfiguration reproduces:
- #153 — chat returns "Something went wrong" (the POST to `/proxy/api/v1/rico/chat` fails).
- #281 — `/command` shows a signed-in user as public (`/me` via proxy fails → `.catch()` →
  `chatAudience = "public"`).

**Fix:** add `NEXT_PUBLIC_RICO_API` to the `next.config.js` fallback chain so the proxy
target matches the API client and the documented env var. Purely additive — no behaviour
change when `BACKEND_API_BASE_URL`/`NEXT_PUBLIC_API_BASE_URL` are set.

### 7.7 Cookie domain on Vercel preview domains — **EXPECTED on preview, NOT a production bug**

`_cookie_domain()` (`src/api/auth.py`) sets `Domain=.ricohunt.com` in production (and when
APP_URL is ricohunt.com). The cookie is `Secure` + `SameSite=None`. Because all traffic
flows through the same-origin `/proxy`, the browser stores the `Set-Cookie` against the
**frontend origin**:
- On **`ricohunt.com`** (production): origin matches `.ricohunt.com` → cookie stored and
  sent → `/proxy/api/v1/me` returns `authenticated:true`. **Works.**
- On a **`*.vercel.app` preview** talking to the shared production backend: the browser
  **rejects** a `Domain=.ricohunt.com` cookie because it does not match the `*.vercel.app`
  origin → no cookie stored → `/proxy/api/v1/me` returns `authenticated:false` → the user
  appears signed-out and sees public auth links.

This is the backend-side explanation of #281's preview symptom. **It is expected behaviour
on preview domains given the cookie domain, not a production defect.** Production
(`ricohunt.com`) is unaffected on this axis.

**Recommendation (not auto-applied — production auth change):** for preview deployments,
either run a preview backend with `COOKIE_DOMAIN` unset (host-only cookie), or add a
host-only sentinel to `_cookie_domain()`. Not applied here because (a) production is not
broken, and (b) changing production cookie scoping is high-risk and warrants explicit owner
sign-off rather than bundling into a containment PR.

### 7.8 Direct answer: is "signed-in user → public links" a bug or expected?

- **On preview (`*.vercel.app`): EXPECTED** — cookie `Domain=.ricohunt.com` cannot be stored
  by a `*.vercel.app` origin (7.7).
- **On production (`ricohunt.com`): it was a real, fixable bug** with two code causes, both
  now fixed: the proxy env-var fallback to localhost (7.6) and the frontend rendering public
  links during the `checking`/timeout state (7.1). With those fixed and the cookie domain
  matching, a signed-in production user resolves to `authenticated:true` and never sees
  public links.

---

## 8. Fixes applied in this pass

| # | File | Change | Symptom fixed |
|---|---|---|---|
| 1 | `app/command/page.tsx` | three-way auth header (neutral skeleton while `checking`, public links only after `public` confirmed) | 7.1 signed-in→public links |
| 2 | `app/command/page.tsx` | chat column `100vh`→`100dvh`; input bar `env(safe-area-inset-bottom)` padding; stronger input surface (`bg-surface` + visible border/focus) | 7.2 input hidden/invisible |
| 3 | `app/layout.tsx` | add `viewport` export with `viewportFit: "cover"` + `themeColor` | 7.2 / 7.3 (enables `env()` safe-area) |
| 4 | `components/layout/TopNav.tsx` | `top-4`→`top-[max(1rem,env(safe-area-inset-top))]` | 7.3 nav vs notch |
| 5 | `components/layout/Navigation.tsx` | `bottom-6`→`bottom-[max(1.5rem,env(safe-area-inset-bottom))]` | 7.3 nav vs home indicator |
| 6 | `app/globals.css` | `color-scheme: dark` | 7.4 / 7.5 lock dark-only |
| 7 | `next.config.js` | add `NEXT_PUBLIC_RICO_API` to proxy target fallback | 7.6 proxy→localhost (breaks all API) |
| 8 | `__tests__/command-auth-state.test.tsx` | new regression test (3 cases) for auth header states | locks 7.1 |

Explicitly **not** done (per instructions): Arabic/RTL, light mode, theme switchers,
redesign, backend route/billing/job/CV/DB changes, cookie-domain code change (7.7),
removing `AppShell`/`CommandInput` dead code, building the `/subscription` page (#187).

## 9. Verification

- `npm run build` (`apps/web`): **PASS** (Next 14.2.35, 24/24 routes, `✓ Compiled successfully`).
- `npm test` (vitest): **PASS** — 6 files / 10 tests, including the 3 new auth-state cases.
- `npm run lint`: **1 pre-existing error** in `components/ui/ProcessingOverlay.tsx:27`
  (`react-hooks/set-state-in-effect`) — untouched by this PR; `next build`'s lint step
  tolerates it. **Zero** lint errors introduced by changed files.
- Backend tests: **not run** — no backend code changed (the only contract-level fix,
  7.6, is a frontend config file).
- Manual QA still required at 360 / 390 / 430 / 768 / desktop + installed iOS PWA:
  - `/command` signed-in shows Dashboard/Sign out (never a flash of Sign in/Sign up).
  - `/command` signed-out shows Sign in/Sign up only after the check resolves.
  - `/command` input bar fully visible above the keyboard / home indicator.
  - `DashboardShell` top/bottom pills clear the notch and home indicator.
- Do not merge until screenshots pass.

## 10. Remaining risks / follow-ups (not in this PR)

| Risk | Severity | Notes |
|---|---|---|
| Preview-domain auth (7.7) | Medium | EXPECTED given cookie domain; fix is preview env config / opt-in host-only cookie. Production unaffected. |
| Pre-existing lint error in `ProcessingOverlay.tsx` | Low | Not introduced here; fix separately. |
| No PWA manifest / icons (`apps/web/public/` absent) | Medium | Installable-PWA + `apple-mobile-web-app-*` metadata pending (#281 §F). |
| `components/shared/AppShell.tsx` dead code | Low | Unused; removal candidate after grep confirms no future need. |
| `/subscription` page missing while backend router exists | Medium | #187 — build the page; do not touch billing logic. |
| Light mode + Arabic/RTL | By design deferred | Locked dark-only until a real theme system + i18n pass. |

## 11. Production risk level of this PR

**Low.** Changes are frontend-only: a three-way conditional + CSS/layout tokens + a
viewport export + a `color-scheme` declaration + an additive proxy env fallback + a new
test. No backend, DB, billing, job, or CV code touched. The proxy env change is strictly
additive. Build + tests green.
