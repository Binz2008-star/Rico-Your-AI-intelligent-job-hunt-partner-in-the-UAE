# P0 Hotfix — signup email verification broken by teaser gate (PR #1005)

**Priority:** P0 (production). **Do NOT touch PR #967. No Neon/Render. No merge until exact-head CI green + preview proof.**
**Branch:** `fix/allow-email-verification-through-teaser-gate` · **PR #1005**
**Head (with my regression test):** `08a4a778` (base hotfix commit `3f884d05`)

## Root cause (verified)
`main`'s teaser middleware (`apps/web/middleware.ts`, from #1003) ALLOW list omitted
`/verify-email`. Email-verification links were redirected to `/explainer/` and the
`?token=` query was dropped → backend kept `email_verified=false` → login rejected.

## PR #1005 review — APPROVED
Minimal, correct: adds `/verify-email`, `/privacy`, `/terms` to the teaser `ALLOW`
list. No logic/matcher change; the app stays gated. Nothing else touched.

## Done this session
- Reviewed #1005 (verdict above).
- **Added regression test** `apps/web/__tests__/teaser-gate-verify-email.test.ts`
  (committed `08a4a778`, pushed): asserts `/verify-email?token=abc` is NOT redirected
  (token preserved), `/privacy` + `/terms` reachable, login/signup/forgot/reset open,
  and `/dashboard` still redirects to `/explainer`.
- Pushed → **CI (QA Tests) running on `08a4a778`** = tasks 2+3 (Vitest + Next build + Playwright).

## Remaining (next session — exact-head only)
1. **Confirm CI green on `08a4a778`:** `gh run list --branch fix/allow-email-verification-through-teaser-gate` → QA Tests success (frontend Build+Vitest, playwright, pytest). If red, read `gh run view <id> --log-failed` and fix.
2. **Preview smoke** on the #1005 Vercel preview alias
   `web-git-fix-allow-email-verification-through-teaser-gate-robens-projects.vercel.app`
   (teaser mode must be active — Preview env `NEXT_PUBLIC_SITE_LIVE` unset/false):
   - `/verify-email?token=fake` → renders the verification UI/error state, **NOT** the teaser (curl: `200`, no redirect to `/explainer`; token in URL preserved).
   - `/login`, `/signup`, `/forgot-password`, `/reset-password`, `/privacy`, `/terms` → `200` (accessible).
   - `/dashboard` → `307 → /explainer` (gated).
   - Use `curl -sI --max-time 30 "$ALIAS/<path>"` with `dangerouslyDisableSandbox`.
3. **Report exact SHA + CI + preview proof, then STOP for merge approval.** Do not merge.

## Follow-up (separate ISSUE — NOT code in this hotfix)
Create with `gh issue create` after the hotfix is reported:
- Branded HTML verification email (replace plaintext link).
- Bilingual EN/عربي verification email + verify-email page.
- Clear verification-success UX (success screen → login/onboarding).
- Mobile end-to-end signup test (Playwright, real device viewport).
- Full fresh-user production smoke (signup → email → verify → login → onboarding).

## Constraints (standing)
No PR #967 changes · no Neon · no Render · no parallel branch/PR · no merge until exact-head CI green + preview proof.
