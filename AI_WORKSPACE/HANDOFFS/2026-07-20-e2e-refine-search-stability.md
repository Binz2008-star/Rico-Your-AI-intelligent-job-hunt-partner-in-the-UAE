# Handoff — E2E stability: refine-search-structured.spec.ts (2026-07-20)

**Type:** CI / test-stability hardening (frontend Playwright). **Scope:** one spec
file. **No application source change. No backend change.**

## Why

The required Playwright job intermittently blocked backend-only PRs (surfaced on
#1239). Proven to be a **baseline flake on clean `origin/main`** (`e44466b2`),
independent of any code under review: a read-only `--repeat-each=5` reproduction
on a clean worktree failed **11 passed / 4 failed**, same test passing and
failing on identical code, with the CI `element detached from the DOM → retry →
timeout` signature. The spec fully mocks `/proxy/api/v1/rico/chat/stream` and
never executes `src/api/routers/rico_chat.py`, so #1239's serializer is
unreachable from it (also verified byte-identical old vs new serialization for
the fixture payload).

## Root causes (all client-render races in the streamed `/command` flow)

1. **Interaction before hydration** — the controlled composer textarea discarded
   a pre-hydration `fill`, so `Enter` sent nothing and the welcome state stayed
   (no cards).
2. **Card remount on the `token`→`done` stream apply** — clicking a `fade-in`
   action card mid-remount detached it (30s timeout).
3. **Nested exact text match** — `RicoUserBubble` nests the composed query in two
   exact-matching elements → strict-mode 2-element violation.
4. **Late unmocked `/chat/sessions`** — 404'd from the dev server; its late
   `catch`→legacy-history fallback fired *after* the search and clobbered the
   optimistic transcript back to welcome (no cards).

## Fix (test-only, assertions preserved)

- Hydration-aware send: retry `fill`+`send-button` click until the request
  actually registers (`chatBodies` grew), skipping once sent so exact
  request-count assertions still hold (no double-send). No fixed sleeps.
- Settle gate `waitForJobMatchCards`: `chat-actions-row` visible → streaming
  caret gone (`transcript-streaming-caret` count 0) → all three cards visible,
  before any interaction. `clickSettledCard` re-resolves + confirms
  visible/enabled immediately before each card click.
- Composed-query assertion scoped to the semantic `transcript-you-row` (same
  product fact, no nested double-match; not an `nth()`/`first()` guess).
- `mockCommand` also mocks `/rico/chat/sessions` → `{sessions:[],total:0}` so
  mount takes the deterministic early-return branch and never resets messages.

## Evidence (Chromium — see PR for the CI-148-download caveat)

| Tree | Command | Result |
|---|---|---|
| clean `origin/main` `e44466b2` | `--repeat-each=5 --workers=1 --retries=0` | 11 passed / **4 failed** |
| fix | `--repeat-each=10 --workers=1 --retries=0` | **30 / 0** |
| fix | `--repeat-each=15 --workers=1 --retries=0` | **45 / 0** |
| fix | normal project config (`--project=chromium`, retries=2) | **3 / 0** |

## Traceability

- Umbrella: `AUDITS/2026-07-20-full-system-audit.md` → "CI flakiness" note.
- Related but unblocked separately: #1239 (SSE done-event encoder) stays Draft;
  its Playwright red was this baseline flake, not its diff.
