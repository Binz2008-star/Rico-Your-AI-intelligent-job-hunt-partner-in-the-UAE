# Handoff — FE Auth design migration to the approved `/design-preview` Atelier surface

> **STATUS: MERGED & PRODUCTION-VERIFIED (2026-07-10).** PR #948 squash-merged to `main` as
> `be312e8`. Vercel production (`ricohunt.com`) serves the new build: all 5 auth routes return
> HTTP 200; `/signup`, `/forgot-password`, `/reset-password`, `/verify-email` SSR the `.atelier
> atl-auth` shell; `/login` is the new client-hydrated shell (old Nocturne markup absent). QA Tests
> / PR-branch workflow / Vercel Preview were all green; no blocking review comments. Local + Vercel
> preview verified EN/AR + RTL + desktop/mobile + loading/validation/disabled/success/error via 24
> Playwright screenshots (production serves the byte-identical immutable preview artifact). Merged
> branch deleted (local + remote). Next phase: Support/contact + remaining Legal presentation.

## Task

Migrate the five production Auth surfaces to the approved `/design-preview` Atelier design language
(paper / ink / sun-red), preserving 100% of existing auth behavior. This is the "Auth parity" phase
that follows the completed Landing migration.

- `DEC-20260710-002` — `/design-preview` is the approved production target (shape + content + flows).
- Reference inventory: `AI_WORKSPACE/HANDOFFS/2026-07-10-design-preview-target-inventory.md`.
- Reference PNGs: `apps/web/public/design-preview/{en,ar}-auth-{signin,signup,forgot,verify,reset}-{desktop,mobile}.png`.

## Routes changed

| Route | File | Notes |
|---|---|---|
| `/login` | `apps/web/app/login/page.tsx`, `components/auth/LoginForm.tsx` | JWT store login → `/command` preserved |
| `/signup` | `apps/web/app/signup/page.tsx` (unchanged), `components/auth/SignupForm.tsx` | `register()` + check-inbox state preserved |
| `/forgot-password` | `apps/web/app/forgot-password/page.tsx` | generic-success (no user enumeration) preserved |
| `/reset-password` | `apps/web/app/reset-password/page.tsx` | token + match + min/max-length preserved |
| `/verify-email` | `apps/web/app/verify-email/page.tsx` | real token auto-verify (loading/success/error + resend) preserved |

New shared files:
- `apps/web/app/_atelier/atelier-auth.css` — scoped `.atelier` auth primitives (header, form, buttons,
  fields, states). Consumes the existing `atelier-tokens.css` token layer; **no** global selectors.
- `apps/web/components/auth/AtelierAuthShell.tsx` — shared minimal auth chrome (serif `Rico` wordmark +
  EN/عربي segmented toggle + light/dark toggle), centered single column. Light-first island, same
  pattern as the shipped `/terms` and `/privacy` pages.
- `apps/web/lib/translations.ts` — added an `atl*` EN/AR key block for the approved auth copy.

## Design decisions (grounded in repo evidence + owner rules)

1. **"Continue with Google" omitted.** The reference shows it, but there is **no verified production
   OAuth backend**. Per owner rule ("omit unsupported actions rather than showing fake controls"), the
   Google button and its `OR` divider are not shipped.
2. **Preview-only labels omitted.** The `PREVIEW` eyebrow and "Preview screen — no account is created"
   are `/design-preview` artifacts, not production copy — omitted.
3. **`/verify-email` keeps the real token flow.** The reference "Check your inbox / six-digit code"
   screen is a preview mock with no backend. Production verify-email auto-verifies a token from the
   email link; we styled the **real** loading/success/error + resend states in Atelier rather than
   shipping a fake code input. The "Check your inbox." headline is used for the two real check-email
   moments: post-signup (`email_verification_required`) and forgot-password success.
4. **Dark toggle is not an invented theme.** It reuses the existing, verified `data-atl-theme="dark"`
   Atelier night palette already shipped in `atelier-tokens.css` (used by `/design-gallery`); the auth
   CSS uses only token `var()`s, so it inherits that palette with zero custom dark colors. Default is
   the light paper/ink surface (the primary approved reference). The moon/sun control appears in the
   approved auth reference chrome.

## Behavior preserved (verbatim logic)

- **Login:** `useAuthStore().login()` → `router.push('/command'); router.refresh()`; 403→unverified +
  resend; 401→incorrect + `failedAttempts`; ≥2 failures→reset-password link; `NEXT_PUBLIC_MAINTENANCE_MODE`
  guard; `?email=` prefill; password reveal toggle (accessible `type="button"`, aria-pressed).
- **Signup:** `register(email, password, null, name)`; `email_verification_required`→check-inbox +
  resend, else `router.push('/onboarding')`; 409→already-registered + login link; 400/422→validation;
  password-rule hint; force `role="user"` is backend-enforced (unchanged).
- **Forgot:** `forgotPassword(email.trim())`, always generic success (no user enumeration).
- **Reset:** token from `?token=`; `password !== confirm` guard; `minLength 8 / maxLength 128`;
  `resetPassword(token, password)`; missing-token and success states.
- **Verify:** token auto-verify on mount; success→`/login?email=…` after 2s; error→resend form; no-token
  →error. Cookies/sessions/CORS/rate-limit/user-isolation untouched (frontend-only change).

## Acceptance criteria — met

- [x] All 5 routes use the approved paper/ink/sun-red Atelier language, matching the reference shape,
      content structure, typography (serif display, mono labels), and layout.
- [x] Desktop + mobile verified. EN + AR + RTL verified (full mirroring).
- [x] Loading, validation, disabled, success, and error states handled and styled.
- [x] No horizontal overflow on any route (EN + AR, 390px) — automated check.
- [x] No real console errors from auth pages (only environment noise: Vercel Analytics script served as
      HTML when the prod build runs locally — app-wide, not auth-specific).
- [x] `npm run build` passes (41/41 static pages). Vitest 320/320. Existing auth tests green.

## Tests run

```
npm run build                                  # ✓ compiled, 41/41 static pages, all 5 auth routes
npx vitest run                                 # ✓ 35 files / 320 tests passed
npx vitest run __tests__/login-password-visibility.test.tsx   # ✓ password toggle contract intact
npx vitest run __tests__/signup-auth-edge-cases.test.tsx      # ✓ error-mapping + resend (button label
                                                              #   updated old "begin journey" → "create account")
Playwright screenshots: 24 shots — login/signup/forgot/reset/verify ×
  {EN,AR} × {desktop,mobile} + dark + success/error/validation/disabled states.
```

## Risks

- **Low.** Frontend-only, no API/cookie/session/schema change. Same light-first island pattern already
  in production for `/terms` and `/privacy`. Scoped `.atelier` CSS cannot affect the global dark app.
- Copy changed to the approved reference wording (new `atl*` keys); old auth keys are left in place and
  still used elsewhere. One test assertion updated for the new primary-button label.

## Rollback plan

Revert the single Auth PR commit. The two new files (`atelier-auth.css`, `AtelierAuthShell.tsx`) are
additive and unreferenced after revert; the 5 route/form files return to the prior Nocturne dark
implementation; translation additions are additive. No data, API, or schema migration is involved, so
rollback is immediate and side-effect-free.

## What was NOT touched

Onboarding, workspace shell, dashboard, profile, settings, applications/flow, upload, subscription,
command/chat, backend/API, auth/session/cookie contracts, billing, schema/migrations, provider/prompt
routing, Railway/Render, dependencies, #920. Out-of-scope per the Auth-phase instructions.
