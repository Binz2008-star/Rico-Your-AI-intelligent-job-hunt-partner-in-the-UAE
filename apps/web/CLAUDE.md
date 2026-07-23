# apps/web/ — Frontend Implementation Detail

Scoped to the Next.js frontend. Loaded on demand when working in this directory. Root `CLAUDE.md` covers the cross-tool contract; this file covers frontend-internal detail.

## Additional Key Frontend Files

Beyond `apps/web/lib/api.ts` and `apps/web/app/command/page.tsx` listed in root `CLAUDE.md`:

- `apps/web/app/signup/page.tsx` — self-signup UI
- `apps/web/app/login/page.tsx` — login UI
- `apps/web/app/onboarding/page.tsx` — guided onboarding / CV-first flow
- `apps/web/services/*` — older service wrappers (dashboard stats, jobs, applications, settings, health)

## Migration Status: `lib/client.ts` → `lib/api.ts`

Migration is complete. `apps/web/lib/client.ts` has been deleted. All API calls now go through `apps/web/lib/api.ts`. Do not reintroduce `lib/client.ts`.

## Landing Page Production Freeze

Full incident history and rule: `AGENTS.md` → "Landing Page Production Freeze" (the canonical version — this is a working-context copy, not a second source of truth).

PR #866 changed `apps/web/app/page.tsx` to render `LandingPageV3` as production; it did not pass owner review, and PR #870 reverted to `LandingPageV2`. Until the owner explicitly lifts this freeze, **do not change `apps/web/app/page.tsx` to swap the production landing component** (`LandingPageV2`, `LandingPageV3`, or any successor) without explicit owner approval.

New landing designs go through `design-handoffs/` → `/design-gallery` → browser smoke tests → owner approval → a separate minimal swap PR. Copy-only or bug-fix changes inside the current production component are allowed.
