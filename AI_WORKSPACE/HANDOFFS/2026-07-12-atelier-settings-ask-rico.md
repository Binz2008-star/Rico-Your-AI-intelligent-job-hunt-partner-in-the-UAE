# Handoff — Atelier /settings + "Ask Rico" honesty correction (2026-07-12)

Durable continuity note so any agent can resume if this session runs out of
tokens. Owner directive: update after each accomplishment; be token-frugal.

## Product model (owner contract — do not violate)

- **Chat (`/command`) = the AI operating surface** (primary control point).
- **Pages = visible state + manual controls** for users who prefer to see/edit.
- **Backend = single source of truth.** Manual and chat must write the SAME
  production state. No localStorage that contradicts the DB, no separate
  chat-vs-page settings, no fake success, no Safety-policy bypass from the UI.
- Every page must feel like one living Rico entity, anchored by the chat, in
  the approved Atelier / `/design-preview` (Lovable) visual language.
- Formula for each surface:
  `Lovable visual reference + Rico conversational intelligence + real
  production state + manual fallback controls + one shared backend contract`.
- Capability present in Lovable but not in Rico: if essential → build as a real
  capability in a separate PR; if cosmetic/fake → do not show; if it needs
  backend/Safety → defer until a real production contract exists.

## Shipped & merged

- **#1000** (`feat/atelier-settings-reference`) — `/settings` rebuilt to the
  reference composition: eyebrow `SETTINGS` + serif `Preferences.` + two-column
  tabs (Account · Preferences · Notifications · Danger zone) inside
  `WorkspaceShell` (Shell C). Real data via `getSettings/updateSettings`,
  `updateProfile`, telegram opt-in/out, `logout`. Timezone omitted (no backend);
  prototype "REQUIRES BACKEND" banner dropped.
- **#1001** (`feat/atelier-settings-control-center`) — reframed `/settings` as a
  Rico control center: per-tab Rico-voice intros, contextual copy, "Match
  selectivity" reframe, and an "Ask Rico" deep link (`/command?q=`) on each
  control.

## Correction in progress (this branch: `feat/settings-ask-rico-honesty`)

**Problem:** #1001's "Ask Rico to make this stricter" etc. implied Rico would
EXECUTE the setting. A real `/command?q=` deep-link does NOT prove execution.

**Code-verified capability matrix** (chat mutation path in
`src/rico_chat_api.py`, `upsert_profile`):

| Setting (manual control) | Chat mutation path? | Evidence |
|---|---|---|
| Notifications enable/disable | YES — but writes `notifications_enabled`, a DIFFERENT field than the manual Telegram opt-in/out (`telegramOptIn/Out`) | `rico_chat_api.py:5220-5248` |
| Account name/phone/email | YES — `upsert_profile` | `rico_chat_api.py:5079` (phone), `:5094` (email), `:3841/:3882` (profile) |
| Match selectivity (`min_score`) | NO chat mutation (only read as a job-search param) | `agent/tools/job_tools.py:35,51`; no `update_settings` in chat |
| Daily limit (`max_daily_applies`) | NO | (no handler anywhere in chat/agent) |
| Include/exclude keywords | NO — env-based; not persisted from chat | `response_builder.py:247` ("Add to EXCLUDE_KEYWORDS in .env") |

**Fix:** relabel all four affordances to honest **"Discuss with Rico"**
(`ناقش مع ريكو`) — the link opens a guidance conversation; it does NOT claim to
execute the setting. Manual controls remain the real mutation path
(`getSettings/updateSettings`, `updateProfile`, telegram opt-in/out).

## Logged capability gaps (future real-capability PRs, each backend + Safety)

- GAP-1: chat cannot execute **match selectivity** (`min_score`) mutation.
- GAP-2: chat cannot execute **daily application limit** (`max_daily_applies`).
- GAP-3: chat cannot persist **include/exclude keyword** filters (env-based).
- GAP-4: notifications state not unified — chat writes `notifications_enabled`;
  manual writes Telegram opt-in/out. Unify before promoting notifications back
  to an execution-claiming label.
- Account name/phone/email DO have a real chat mutation path (same profile
  state) — candidate to promote to an execution label once the one-shot intent
  is verified end-to-end.

## Conventions (reuse; already on main)

- Shell: `components/workspace/WorkspaceShell.tsx` (Shell C). Palette via
  `useWorkspaceTheme()` so content tracks the shell's local light/dark toggle.
- Atelier kit: `components/atelier-kit/{tokens,fonts,primitives}`.
- Fonts crash vitest unless mocked → `vitest.setup.ts` mocks
  `next/font/google` (already on main since #1000).
- Auth-guard test asserts the private shell via the `<main>` landmark
  (`__tests__/auth-guard.test.tsx`), not a `data-testid`.
- Chat deep-link: `/command?q=<encodeURIComponent(prompt)>` — existing one-shot
  prompt pattern (`app/command/page.tsx:900`), auto-sends and strips the param.
- Preview screenshots: temp route `app/zz-preview-*` (NO leading underscore),
  `next dev` with `NEXT_PUBLIC_USE_MOCK=true`, Playwright
  `executablePath: /opt/pw-browsers/chromium`. DELETE the temp route before commit.
- "Continuous AI: *" commit statuses fail on every PR = noise. Real CI =
  frontend · pytest · playwright · postgres-integration.

## Remaining Atelier migration plan (one surface per PR, off clean main)

All large — each its own careful PR with owner visual approval before merge:

1. `/flow` (the `/applications` redirect target; ~604 lines) → Shell C + the
   "Your pipeline." board, reframed as Rico's operational memory (saved ·
   applied · needs follow-up · why the next step). Preserve List/Board toggle,
   `updateApplicationStatus` optimistic mutations, manual-add, stats, i18n.
   Drop the prototype SAMPLE/DEMO chrome and the fake per-card score (no such
   field on `Application`).
2. `/upload` (~725 lines) → Shell C; reframe as "what Rico read / understood /
   couldn't read / needs confirmation". Preserve upload/set-primary/delete/guest.
3. `/profile` (~1039 lines, owner's #993 inline editor) → shell swap to Shell C;
   closes the last chrome seam. Handle with care (protected inline editor).

Deferred: **#995** preview-domain cookie fix (dedicated auth/config session).
