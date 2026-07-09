# Handoff: /command chat UX upgrade

## Task

Upgrade the real `apps/web/app/command/page.tsx` (Next.js 14 App Router, `lib/api.ts`-backed)
with copy/retry/new-chat/shortcut/persistence UX improvements, without replacing the
production chat implementation.

## Context

- Repository: `binz2008-star/rico-your-ai-intelligent-job-hunt-partner-in-the-uae`
- Branch: `claude/command-chat-upgrade-8iv3o3`
- Relevant files: `apps/web/app/command/page.tsx`, `apps/web/lib/translations.ts`
- Relevant architecture notes: `DEC-20260708-001` / `DEC-20260708-002` in `AI_WORKSPACE/DECISIONS.md`
  (prototypes must not smuggle unsafe/stale action UI into production)

**Preceding conflict**: the original task text (from a prior turn) pasted a full
`page.tsx` using `@tanstack/react-router` + `@ai-sdk/react` `useChat`/`DefaultChatTransport`
streaming to `/api/chat`, and claimed it was already shipped and typecheck-clean. That
code does not exist anywhere in this repo, on any branch — this app is Next.js 14 App
Router, has no `tanstack` or `ai-sdk` dependency, and the real `/command` implementation
is a ~2200-line file wired to `lib/api.ts`, JWT-cookie auth, the safety/permission-card
system, and server-truth chat history. That work was not done; this handoff replaces it
with real changes to the real file.

## Constraints

- Out of scope: `/rico`, landing, pricing, auth, profile, settings pages.
- Compatibility requirements: preserve JWT-cookie auth, `lib/api.ts` integrations,
  safety/approval cards (`PermissionRequestCard`, `ProposedChangeCard`), job-action
  wiring (`agent_runtime`/actions router), streaming state machine (id-stability,
  abort/retry-on-timeout, `command-composer-stability.spec.ts` pixel-stability
  guarantees).
- Style and typing requirements: existing file conventions (inline SVG icons,
  `t()` translation keys, Tailwind utility classes).

## Acceptance Criteria

- [x] localStorage conversation history added — scoped to public/guest sessions only
- [x] New chat button (desktop) added
- [x] Copy assistant response added
- [x] Retry added on genuine send failures (network/timeout/generic)
- [x] Keyboard shortcuts added (Esc to cancel, Ctrl/Cmd+K to focus)
- [x] No TanStack Router / ai-sdk dependency introduced
- [x] Production chat (auth, safety cards, job actions) untouched
- [x] `npx tsc --noEmit` clean on changed files
- [x] Existing unit + e2e composer-stability tests unaffected (same pass/fail baseline)

## Deliverables

### Changed files

- `apps/web/app/command/page.tsx`
- `apps/web/lib/translations.ts`

### Implementation summary

1. **Public/guest localStorage history** (`PUBLIC_HISTORY_KEY = "rico_command_public_history_v1"`,
   capped at 40 turns). Scoped to `chatAudience === "public"` only — authenticated
   users keep their existing server-truth history (`fetchChatHistory`/`clearChatHistory`)
   untouched; mixing a local mirror into that path was judged unsafe/unnecessary
   (flagged rather than implemented, per the "report conflicts" instruction).
   Only **plain `{role, text}` pairs** are persisted/restored — `agentic_ui`
   (permission requests, proposed changes), job-match cards, and actions are
   **never** replayed from storage, so a reload can't resurrect a stale
   approve/apply affordance (this follows `DEC-20260708-001`'s "never smuggle
   unsafe action UI" constraint literally). Loaded via a new effect mirroring the
   existing authenticated-history-loading effect (`historyState` pending/has_history/
   empty), guarded so it can't race the welcome-message effect. Written on every
   settled turn (never mid-stream).
2. **New chat button (desktop)** — the mobile header already had one
   (`MobileCommandHeader`, hidden on desktop for authenticated users); desktop
   authenticated users previously had *no* way to start a new chat at all. Added
   inside the existing scrollable messages pane (same place the old
   "Clear history" row lived), `hidden md:flex`, so it can never shift the
   composer — verified against `command-composer-stability.spec.ts`.
3. **Copy** — small Copy/Copied button under every settled (`!m.streaming`) Rico
   turn with non-empty text; `navigator.clipboard.writeText`, 1.6s confirmation,
   silent no-op on clipboard failure (insecure context).
4. **Retry** — new `isError`/`retryText` fields on `Message`, set only at the three
   genuine failure sites in `sendMessage`'s catch block (timeout, network,
   generic — not rate-limit/fallback, which are valid backend responses). Retry
   resends the exact original user text via the existing `sendMessage()`.
5. **Keyboard shortcuts** — `Esc` cancels an in-flight request (reuses the
   existing `cancelRequest()`, previously only reachable via the composer's
   Cancel button); `Ctrl/Cmd+K` focuses the composer. Both are net-new global
   listeners — the page previously wired zero keyboard shortcuts, so neither
   combo collides with anything existing.
6. `cmdHint` copy updated to mention the new shortcuts; two new translation
   keys (`cmdCopy`, `cmdCopied`) added in both `en`/`ar`.

### Demo/preview-only or reduced-safety tradeoffs (explicit, per Product Generalization Rule)

- Public-session history is a plain-text mirror only — rich cards (job matches,
  CV preview, permission/approval cards) do **not** survive a reload for guest
  users. This is a deliberate safety choice, not an oversight.
- Authenticated users get **no** new persistence behavior — they already have
  real server-truth history; this was flagged as an unsafe surface to touch and
  intentionally left alone.
- "Retry" is not a full ChatGPT-style "regenerate in place" (it does not
  remove/replace the prior assistant turn) — it resends the failed user turn
  through the same `sendMessage()` path, matching the existing chat-turn model.

### Tests run

- `npx tsc --noEmit -p tsconfig.json` — no new errors (confirmed identical
  38-line baseline of pre-existing test-runner-global noise, unrelated to this change).
- `npx eslint app/command/page.tsx lib/translations.ts` — 1 new
  `react-hooks/set-state-in-effect` finding, on a `useEffect` that mirrors an
  existing effect with the identical pattern (2 pre-existing instances of the
  same rule already on `main`); not a regression in kind, left consistent with
  the established idiom.
- `npx vitest run` (full suite) — 302 passed / 19 failed, byte-identical to the
  `main` baseline (verified via `git stash`); zero regressions.
- `npx playwright test e2e/command-composer-stability.spec.ts` — all 4 tests
  pass (desktop/mobile composer-anchoring, slow-banner, mobile-header geometry).
- Scratch Playwright smoke spec (not committed) against the dev server,
  covering exactly the new behavior: public send → reload → history restored →
  New chat clears it → reload confirms the clear persisted; Copy writes to the
  real clipboard and shows "Copied"; a simulated stream failure shows Retry and
  successfully recovers on click; `Ctrl+K` focuses the composer and `Escape`
  cancels an in-flight request. All 4 passed.

### Risks

- New `react-hooks/set-state-in-effect` lint finding (see above) — cosmetic,
  consistent with existing code, not a build blocker (repo does not gate on it
  today).
- Guest localStorage history is unbounded across browser profile lifetime aside
  from the 40-turn cap — no TTL/expiry. Low risk (plain text only, client-side,
  same trust boundary as the existing `rico_sid` cookie-less session id already
  stored there).

### Rollback

`git revert` the two changed files, or `git diff main -- apps/web/app/command/page.tsx apps/web/lib/translations.ts | git apply -R`.

## Required Verification

```bash
cd apps/web
npx tsc --noEmit -p tsconfig.json
npx eslint app/command/page.tsx lib/translations.ts
npx vitest run
npx playwright test e2e/command-composer-stability.spec.ts --project=chromium
```

## Open questions

- None blocking. Optional follow-up (not done, not requested): mirror the same
  guest-history/copy/retry/shortcut upgrades onto `/rico` if that surface is
  ever promoted back into active use.
