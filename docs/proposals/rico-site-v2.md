# Rico Site v2 — Redesign Proposal

**Status:** Draft for review — _no implementation code until this is approved._
**Author:** Claude (agent)
**Date:** 2026-05-29
**Scope decision:** Foundation-first reimagining, committing to **light mode + Arabic/RTL** the professional way for a UAE-focused product.

---

## 1. Why v2

The current site is live and stable (production commit `3423ae9`), but it carries
structural debt accumulated through the recent incident chain (#281 containment, #282
scope creep). v2 is not a repaint — it is the chance to fix the *causes* of those
incidents by design instead of patching symptoms:

| Current constraint | Root issue | v2 resolution |
|---|---|---|
| Dark-only lock (`color-scheme: dark`) | Light mode shipped with broken contrast and was reverted | Token-driven theming with an enforced AA-contrast gate |
| Arabic/RTL deferred | No logical-direction layout primitives | RTL as a first-class direction from day one |
| `/command` auth-state bug (#281) | Ad-hoc auth rendering per page | One auth-aware shell with a single session source of truth |
| `AppShell.tsx` dead code | Two shell implementations | Consolidate on one canonical shell |
| `lib/client.ts` + `lib/api.ts` split | Mid-migration, two API clients | Finish migration; one validated client |
| `/subscription` page/router parity gap (#187) | Backend router exists, frontend surface inconsistent | Treat subscription as a first-class surface |

**Principle:** every v2 change should make the *next* feature cheaper and safer, not
just look newer.

---

## 2. Product north star

Rico is "your AI intelligent job-hunt partner in the UAE." The site should feel like a
**calm, trustworthy, intelligent companion** — not a dashboard dump and not a marketing
funnel. The CV-first, approval-first, memory-weighted model (per `docs/architecture.md`
and `CLAUDE.md`) is the differentiator and should be the emotional core of the design.

Design tenets:
1. **CV-first, not form-first.** The first useful action is uploading a CV, never a wizard.
2. **Approval-first.** High-impact actions (apply, message) always surface a confirm step — this is a safety rule (`rico_safety.py`), so the UI must make it feel native, not annoying.
3. **Quiet intelligence.** Background work (matching, scoring, alerts) is shown as ambient status, not noisy notifications.
4. **Bilingual by default.** Arabic and English are equal citizens; layout must not "break" in RTL.
5. **Mobile + installed-PWA first.** Most UAE job-seekers are on phones.

---

## 3. Three-track plan

### Track A — Design system foundation (unblocks everything)
- **Token layer.** Formalize the semantic tokens already in Tailwind (`surface`, `text-primary`, `border-subtle`, `magenta`, `cyan`, …) into a single documented source of truth split into:
  - *primitive* tokens (raw palette, spacing scale, type scale, radius)
  - *semantic* tokens (role-based: `bg-surface`, `text-on-surface`, `border-strong`)
  - *theme* maps (dark, light) that remap semantic → primitive.
- **Light mode, done right.** The previous attempt failed on contrast. v2 gate: **every semantic token pair must pass WCAG AA** (4.5:1 text, 3:1 large/UI) in *both* themes, verified by an automated contrast check in CI before light mode is allowed to ship.
- **RTL/Arabic.** Use CSS logical properties (`margin-inline-start`, `padding-inline-end`, `start`/`end`) and `dir`-driven layout. No hardcoded `left`/`right` in new code. Locale drives `<html lang dir>`.
- **Motion + reduced-motion.** Keep the cinematic feel, but every animation respects `prefers-reduced-motion` (already partially done with `motion-reduce:` utilities).

### Track B — Architecture & shell cleanup
- **One canonical shell.** Consolidate on `DashboardShell` + `TopNav` + `Navigation`; remove `AppShell.tsx` (confirmed dead code — imported only by itself). Migrate any stragglers.
- **Single session source of truth.** A `useSession()` hook backed by `fetchMe()` with the three-state model (`checking | authenticated | public`) the #281 fix introduced — promoted from a page-local pattern to a shared primitive so no page re-implements auth rendering.
- **Finish the API-client migration.** Complete `lib/client.ts → lib/api.ts` for dashboard/stats/jobs/applications/settings/health (the remaining pending items per `CLAUDE.md`). One client, Zod-validated responses everywhere. Delete `lib/client.ts` only after `npm run build` passes with zero imports.
- **Subscription parity.** Make `/subscription` a fully-supported surface matching the existing backend `subscription_router` (addresses #187).

### Track C — Surface redesign (in priority order)
1. **`/command`** — the core chat/agent surface. The heart of "Rico, the intelligent AI."
2. **`/upload`** — CV-first entry; should be the most frictionless screen on the site.
3. **`/`** — landing; communicate the CV-first + approval-first model in <1 screen.
4. **`/dashboard`** — ambient intelligence: trajectory, matches, alerts as calm status.
5. **`/subscription`** — clear plans, AED pricing, WhatsApp activation flow (current model).

---

## 4. Surface-by-surface direction (intent, not pixels)

### `/command` (core)
- **Auth-aware header via the shared shell** — never a public-link flash for signed-in users (locks in the #281 fix as architecture).
- **Conversation-first canvas**: the chat *is* the page. Suggestion chips when empty; CV upload reachable from the composer (already the pattern).
- **Composer**: visible, keyboard-safe (`100dvh` + `env(safe-area-inset-bottom)`), grows with content, with an obvious upload affordance.
- **Approval moments** rendered as inline confirm cards (apply/save/message) — the safety layer made visible and pleasant.
- **Bilingual**: messages, chips, and composer flip cleanly to RTL.

### `/upload`
- Single drag-and-drop + file-picker, PDF-first, encrypted-processing reassurance (already present).
- Immediate preview → confirm/edit profile loop (the existing `preview_ready → confirm-cv-profile` flow) as the hero interaction.

### `/` (landing)
- One-screen value prop: "Upload your CV once. Rico remembers, watches the market, asks before big moves."
- Live "profile loop" status panel (already a strong element) kept and refined.
- Two CTAs only: **Upload CV** (primary) and **Sign up free** (secondary). No funnel clutter.

### `/dashboard`
- Ambient, not alarming: trajectory summary, top matches with fit scores, the single "next alert" that matters.
- Approval queue surfaced (anything awaiting user confirmation).

### `/subscription`
- Free / Pro (AED 29) / Premium (AED 49) clearly, with the WhatsApp activation reality stated plainly (matches current FAQ copy).

---

## 5. Phasing (safe, incremental, production-respecting)

Per `CLAUDE.md`, this is production code — so v2 ships in safe increments, never a big-bang
cutover.

| Phase | Deliverable | Risk | Gate |
|---|---|---|---|
| **0** | This proposal approved | — | Your sign-off |
| **1** | Token layer + contrast CI gate (no visual change yet) | Low | AA passes both themes |
| **2** | Shell consolidation + `useSession()` + finish API migration | Medium | `npm run build` + tests green; remove `AppShell.tsx`/`lib/client.ts` only when import-free |
| **3** | Light mode behind a flag | Medium | AA gate; manual QA both themes |
| **4** | Arabic/RTL behind a locale flag | Medium | RTL visual QA on key surfaces |
| **5** | Surface redesign, one screen at a time, starting with `/command` | Medium | Per-surface QA + preview review before each merge |

Each phase is its own small PR with build proof and QA notes — the same discipline that
made the #283 containment clean.

---

## 6. Explicit non-goals (for this proposal)
- No backend API contract changes, DB/schema changes, billing-logic changes, job-matching or CV-parsing changes — those require separate evidence and your explicit approval (per `CLAUDE.md` safety rules).
- No new AI provider or routing changes.
- No auto-apply or approval-bypass behavior — the safety layer is non-negotiable.

---

## 7. Open questions for you
1. **Brand**: keep the current magenta→cyan cinematic identity, or is v2 also a brand refresh?
2. **Figma**: want me to produce visual mockups of `/command` and `/` in Figma before any code, so you approve the look first? (Figma integration is available.)
3. **Arabic copy**: do you have an Arabic copy source/translator, or should the system use a translation layer with human review?
4. **Light vs dark default**: which is the *default* theme for new users in the UAE market?
5. **Sequencing**: are you comfortable with the phase order (foundation before visuals), or do you want a visible `/command` redesign first for momentum?

---

## 8. Recommendation
Approve **Phase 0 → 1 → 2** to start: lock the token foundation and clean the architecture
(invisible but high-leverage), then bring light mode, Arabic, and the surface redesigns
on top of a solid base. This sequence is what prevents a repeat of the light-mode and
`/command` regressions — we fix the foundation that caused them before building on it.

_Awaiting your review. No implementation code will be written until you approve this plan and the open questions above are resolved._
