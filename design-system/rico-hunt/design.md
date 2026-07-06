# Rico Hunt — Design Audit & System Reference

**Status date:** 2026-07-06 · **Ratified:** 2026-07-06 (`AI_WORKSPACE/DECISIONS.md` DEC-20260706-001)
**Type:** Audit + reference. No production code changed. No build, no tests, no PR.
**Source-of-truth decision (owner-approved, DEC-20260706-001):** the shipped Nocturne system (§2) is the production design source of truth. `MASTER.md`, `Rico Hunt V2 - Offline.html`, and `docs/archive/DESIGN.md` are explicitly **not** to be used as source of truth — historical/reference only unless a future brand migration is explicitly approved. "Conversation is the system" (§1) remains approved independently of this palette decision.
**Relationship to other files in this folder:**
- Supersedes `MASTER.md` as the practical reference for what is actually shipped (see §3.1 — `MASTER.md` describes a design system that was never implemented, now formally not-source-of-truth per the decision above).
- Treats `DEV-HANDOFF-command-chat-auth-ux.md` as the active, still-unbuilt spec for `/command` attachment UX + auth password parity (see §4.7–4.8).
- Treats `nocturne-reference.html`, `Rico Hunt V2 - Offline.html`, and `docs/archive/DESIGN.md` as historical references only — all predate the shipped, "professionalized" token palette (see §3.2).

Scope: `apps/web` (Next.js 14 / TypeScript / Tailwind). Backend, chat engine, and auth API are out of scope, per the standing rule in `DEV-HANDOFF-command-chat-auth-ux.md` §12.

---

## 1. Product vision → what the UI is supposed to be

Source: `AI_WORKSPACE/CAREER_OS_VISION.md` (2026-06-28), `AI_WORKSPACE/PROJECT_BRIEF.md`, `design-system/rico-hunt/DEV-HANDOFF-command-chat-auth-ux.md` §0.

Rico is scoped as a **Career Operating System**, not a jobs board with a chat bolted on. Two statements anchor everything below:

- **"Not a feature list, but an Operating System."** (Owner's original framing, `CAREER_OS_VISION.md`.) The 10-layer model puts the **AI Orchestrator (Layer 1)** and **Trust Layer (Layer 5)** at ⭐⭐⭐⭐⭐ priority — the chat *is* the product, and every action it surfaces must be honest about what actually happened.
- **"Conversation is the system."** (`DEV-HANDOFF` §0.) Concretely: the chat thread is the primary surface and single source of flow; Jobs/Applications/Profile/Settings are *views into state the conversation created*, reachable from chat, never a replacement for it; every card in the UI must be preceded by Rico explaining why it's there.

**Design implication:** the UI's job is to make the chat trustworthy (no fake "Done" states, honest empty/loading states, one clarifying question at a time) and to keep every other route feeling like a drill-down from the conversation rather than a competing home screen. §4 below checks how far the current build actually lives up to that framing — this audit did not have time to trace the sidebar/navigation copy in `layout/Sidebar.tsx` and `layout/AppShell.tsx` closely enough to confirm whether Jobs/Applications/etc. are actually framed as "views into chat state" versus standalone destinations; that check is flagged as a roadmap item (§6, R7) rather than asserted here.

---

## 2. Current design system (ratified source of truth): "Nocturne"

Defined in `apps/web/tailwind.config.ts` + `apps/web/app/globals.css`. This — not any of the markdown docs in this folder — is what's actually shipped, and is the owner-ratified source of truth as of DEC-20260706-001.

| Token | Role | Value (dark, default) |
|---|---|---|
| `--bg` / `--surface` / `--surface-elevated` | Canvas + elevation | Deep navy/indigo (`11 13 28` → `23 28 58`), not pure black |
| `--gold` | Primary / brand / CTA | `#f0a94a` (amber) |
| `--magenta` (aliased `rico-magenta`, "secondary") | Interactive/actions | `#818cf8` — **indigo**, deliberately detoned from hot pink |
| `--cyan` (tertiary) | Data/links | `#60a5fa` — **sky blue**, deliberately detoned from neon cyan |
| `--aura` | "Intelligence" accent, data/AI output only | `#6fe9d0` teal |
| `--success` | Confirmed/applied/live | `#10b981` emerald |

Fonts (wired in `apps/web/app/layout.tsx` via `next/font/google`): **Space Grotesk** (display), **Inter** (body), **IBM Plex Mono** (mono), **IBM Plex Sans** (secondary). A `.light` class remaps the same tokens to an AA-contrast light theme; `.command-dark-lock` force-locks `/command` to dark regardless of the global toggle. Glass surfaces (`.glass-panel`, `.glass-island`), ambient grain overlay, and `prefers-reduced-motion` handling are already built into `globals.css`.

**Read this as intentional, not sloppy:** inline comments in both files show a deliberate detoning pass — magenta → indigo, cyan → sky-blue, "void-black" → navy — explicitly to move from a neon/hot aesthetic toward something more professional. Any redesign work should treat this token system as the foundation to extend, not replace.

---

## 3. Documentation lineage & conflicts

Five artifacts in this repo claim or have claimed to describe "the Rico design system." Only one matches the shipped code — **resolved by DEC-20260706-001**: Nocturne (§2) is authoritative; the other four below are historical/reference only.

### 3.1 `MASTER.md` is orphaned and contradicts the shipped system — **not source of truth**

`design-system/rico-hunt/MASTER.md` (auto-generated 2026-06-03) specifies: `#FAFAF9` near-white background, `#1C1917` warm near-black text/primary, `#CA8A04` gold CTA, Satoshi + General Sans fonts, explicit `box-shadow` tokens, "Flat Design... no gradients/shadows." This is a **different design system** from Nocturne — light vs. dark canvas, flat vs. glass/glow, different font families, different gold hex even for the one color they nominally share.

`MASTER.md`'s own header says a page-specific file in `design-system/pages/[page-name].md` overrides it — that directory doesn't exist, so nothing scopes `MASTER.md` down. Nothing in `apps/web` actually consumes it either (no Satoshi/General Sans font loading, no `#FAFAF9`/`#CA8A04` anywhere in `tailwind.config.ts`). **Risk:** any future agent (including the newly installed `design-taste-frontend`/`redesign-existing-projects` skills) that "checks the design system doc first" and finds `MASTER.md` will get instructions that actively conflict with the shipped app. Per DEC-20260706-001, `MASTER.md` must not be treated as source of truth; it should get an explicit historical banner or be retired (roadmap R9).

### 3.2 The original brand spec and its HTML mocks predate the detoning pass — **historical only**

- `docs/archive/DESIGN.md` is the origin of the original brand spec: pure black `#000000` canvas, magenta `#ff2d8e` primary, cyan `#00e5ff`/`#00ffff` secondary, IBM Plex Sans + Sora typography. It is already self-labeled "Archived document... not the current source of truth" at its own header, and DEC-20260706-001 reconfirms it must not be used as source of truth.
- `Rico Hunt V2 - Offline.html` is a static bundler export whose loading-screen SVG renders that same original spec: pure black background + hot pink (`#ff2d8e`) and electric cyan (`#00e3fd`) glows, IBM Plex Sans only. DEC-20260706-001 explicitly excludes it from source-of-truth status.
- `nocturne-reference.html` is a later, richer static mock: `--ember` gold + `--aura` teal, Space Grotesk + Inter + IBM Plex Mono — much closer to what shipped, but its CSS variables are still literally named after the pre-detoning colors in places.

All three are useful as *historical* references for motion/layout ideas (the `.aura` breathing-ring pattern, glass nav, glow blobs), but none should be handed to a designer or agent as "the current palette" — the shipped tokens in §2 are the ratified direction.

`docs/proposals/rico-site-v2.md` (2026-05-29, draft) posed this exact fork as an open question in §7.1 ("keep the current magenta→cyan cinematic identity, or is v2 also a brand refresh?") and was never marked approved. DEC-20260706-001 resolves that question retroactively in favor of the shipped Nocturne refresh; the proposal doc should be explicitly closed out to match (roadmap follow-up, not yet done).

### 3.3 `docs/frontend-audit.md` route/component inventory is 6 weeks stale

Dated 2026-05-24. Confirmed by direct file listing today: 8 routes now exist that aren't in that inventory — `/queue`, `/verify-email`, `/about`, `/contact`, `/faq`, `/privacy`, `/refund-policy`, `/terms` — plus `/admin/leads`, which wasn't audited at all. The component/hook/lib duplication questions it raised (`DashboardShell` vs `AppShell`, `lib/api.ts` vs `lib/api/*`) are **resolved** — see §4.4–4.5, both are legitimate, non-duplicate. That doc's mobile-risk flags on `/onboarding`, `/jobs`, `/profile`, however, are **still open** — see §4.11.

### 3.4 `DEV-HANDOFF-command-chat-auth-ux.md` is a real, unimplemented spec

Untracked, not yet merged, but concrete and current (written against the live `/command` behavior). Confirmed today: **neither of its two deliverables is built yet** — the staged-attachment chip and the signup/reset password-toggle parity. See §4.7–4.8. This is the most actionable, already-scoped item in this audit.

---

## 4. Implementation inconsistency catalog (verified 2026-07-06)

Findings below were gathered by a full sweep of `apps/web/app` and `apps/web/components`, then spot-checked directly against source for the highest-stakes items.

### 4.1 Color tokens — one page is completely off-system

`apps/web/app/reset-password/page.tsx` uses raw `indigo-*`/`zinc-*` Tailwind classes throughout (`bg-indigo-600`, `bg-zinc-800`, `bg-zinc-950`, `focus:ring-indigo-500` — lines 51, 62, 70, 81, 94, 102, 113, 127) instead of the Nocturne `gold`/`surface`/`rico-*` tokens every other auth page uses. Login and signup are correctly on-token. This is a copy-paste-from-somewhere-else page, not an intentional exception.

Everywhere else checked (landing page's cyan/black CTA contrast, `StatusBadge`, `PermissionRequestCard` risk badges) uses color deliberately and consistently — not a system violation.

### 4.2 Fonts — consistent

No inline `font-family` overrides or arbitrary Tailwind font arbitrary-values found outside one intentional exception (`ScoreBadge` uses `font-['Cabinet_Grotesk',sans-serif]` for its numeric badge — a deliberate one-off, not drift).

### 4.3 `DashboardShell` vs `AppShell` — not a duplication problem

`DashboardShell.tsx` is a minimal frame used only by `/dashboard`. `layout/AppShell.tsx` is the full sidebar+topbar+mobile-dock shell used by 8+ other authenticated routes (archive, flow, jobs, profile, queue, saved-searches, settings, signals). They're genuinely different layouts for different jobs — the `docs/frontend-audit.md` "possible duplication" flag is resolved: no merge needed.

### 4.4 `lib/api.ts` vs `lib/api/*` — not a duplication problem

`lib/api/orchestration.ts` is a helper layer that imports and re-uses functions from `lib/api.ts`; it does not reimplement auth or client logic. `lib/auth.ts` is intentionally a thin stub pending live session-cookie integration. The old audit's "check for duplication" flag is resolved: no cleanup needed here.

### 4.5 Sandbox route — low risk, needs a decision, not a fix

`/sandbox/command-primitives` still exists and is still unlinked from all navigation components. Fine to leave as-is short term; still worth an explicit keep/archive decision per the old audit's suggestion.

### 4.6 Maintenance-mode framing — login only

`LoginForm.tsx` reads `NEXT_PUBLIC_MAINTENANCE_MODE`, shows an amber banner, and disables submit during backend maintenance. `SignupForm.tsx` and `reset-password/page.tsx` have **no equivalent** — during a backend outage they'll fail silently/generically instead of explaining why, which directly contradicts the "no fake/misleading states" principle both `docs/frontend-audit.md` and `DEV-HANDOFF` call out as non-negotiable.

### 4.7 Attachment chip — spec exists, build doesn't

`DEV-HANDOFF-command-chat-auth-ux.md` §3 Flow A specifies a staged chip (type glyph · filename · size · remove ×) with distinct staged/error/reading/done states before anything posts to the thread. The actual `/command` composer (`app/command/page.tsx` `handleCVUpload`, ~lines 1304–1399) posts a `📎 Uploading …` message into the thread **immediately on file selection** — no staging, no remove, no per-state chip UI, no unsupported-file/oversize inline error before send. This is the largest gap between an already-written, current spec and shipped code found in this audit.

### 4.8 Password-visibility toggle — login only

`LoginForm.tsx` has a correct toggle (`aria-pressed`, `aria-label`, eye icon swap, `type="password"`/`"text"` swap). `SignupForm.tsx` (confirmed: plain `type="password"`, no `showPassword` state, no toggle anywhere in the file) and `reset-password/page.tsx` (same, both password fields) have **none**. `DEV-HANDOFF` §10 explicitly calls for parity here; it doesn't exist yet.

### 4.9 Accessibility — one real gap, otherwise clean

Sampled 8 interactive components across command/dashboard/profile/jobs-adjacent surfaces. Login's toggle, `DashboardShell`'s logout button, `ProfileSummaryCard`'s retry link, `StatusBadge`, `MaterialIcon`'s `aria-hidden`/`role` handling, and the global `Button` focus-visible ring are all correctly built.

One confirmed gap: `components/ui/ScoreBadge.tsx` conveys match-quality entirely through color (teal ≥85%, amber ≥65%, dim white below) with **no `aria-label`, no icon, no text beyond the raw number** — a screen-reader or color-blind user gets "72%" with no sense of whether that's good or bad. Small, isolated, easy fix.

### 4.10 Responsive coverage — flagged 6 weeks ago, still unfixed on 3 of 5 routes

| Route | Breakpoint classes (`sm:`/`md:`/`lg:`/`xl:`) | Status |
|---|---|---|
| `/command` | 14 | Good |
| `/flow` | 20 | Good |
| `/profile` | 3 | Minimal |
| `/jobs` | 2 | Minimal |
| `/onboarding` | **0** (confirmed by direct grep) | Not handled |

`/onboarding` — the CV-upload/profile-confirmation flow every new user goes through — has zero responsive breakpoint classes. This was already flagged high-risk in the 2026-05-24 audit and has not moved.

---

## 5. Component library options — VengeanceUI / SkiperUI (not yet integrated)

Per your instruction, these are noted for **where they'd help**, not applied yet.

- **Stack fit:** both are copy-paste component registries (shadcn-CLI style — you own the source, no npm runtime dependency) built on React/Next.js + Tailwind + Framer Motion (SkiperUI) or Radix UI + Framer Motion (VengeanceUI). `apps/web` already depends on `framer-motion` and Tailwind, so integration cost is low — no new animation runtime, no design-system collision (both are unstyled/token-friendly, not opinionated theme packages like Material or Carbon).
- **SkiperUI** — scroll effects, card swipers, marquees, theme toggles. Best fit: the landing page (`LandingPageV2.tsx`) and any future marketing/editorial surfaces, where Nocturne's glow/glass language could use a few more polished motion primitives without hand-rolling GSAP.
- **VengeanceUI** — displacement hover effects, spotlight nav, glass dock, animated hero/perspective-grid components. Best fit: the "Aura" motif already in `globals.css` (`.aura-glow-*`, `.glow-aura`, breathing-ring animation) — VengeanceUI's glass/spotlight primitives are conceptually close to what Nocturne is already reaching for, so a component could replace a hand-rolled one **only if it measurably reduces code or fixes a real interaction bug** (see constraints below).
- Both are paid/licensed component sources (one-time-payment tiers) — confirm licensing before pulling any component into the repo.

No current bug or gap in §4 requires either library to fix. They're an option for the "polish" tier of the roadmap below (R8), not for any of the P0/P1 items, which are all either missing-functionality or off-token-usage problems that existing Rico primitives already solve elsewhere in the app.

---

## 6. Prioritized redesign roadmap

Ranked by user impact × how cheap the fix is, given everything in §4 is either a small isolated fix or a scoped-but-unbuilt spec — nothing here requires a rewrite.

**Status (2026-07-06): on hold.** The owner has explicitly paused R1–R4 and R7 pending this reconciliation; DEC-20260706-001 resolves the source-of-truth question these items depend on, but does not itself lift the hold. Do not start implementation on any item below until explicitly told to resume.

### P0 — honesty & parity gaps (small, isolated, high user impact)

1. **R1 — Reset-password color-token fix.** Swap `indigo-*`/`zinc-*` classes in `app/reset-password/page.tsx` for the Nocturne `gold`/`surface`/`rico-*` tokens already used by login/signup. Pure class-name swap, no logic change. *(§4.1)*
2. **R2 — Password-visibility toggle parity.** Lift the exact pattern from `LoginForm.tsx` (`aria-pressed`, `aria-label`, icon swap) into `SignupForm.tsx` and `reset-password/page.tsx`. `DEV-HANDOFF` §10 already specifies this precisely. *(§4.8)*
3. **R3 — Maintenance-mode parity.** Port the `NEXT_PUBLIC_MAINTENANCE_MODE` banner + disabled-submit pattern from `LoginForm.tsx` into `SignupForm.tsx` and `reset-password/page.tsx`. *(§4.6)*
4. **R4 — ScoreBadge accessibility.** Add an `aria-label` (e.g. "Match score 72 percent, moderate") to `components/ui/ScoreBadge.tsx`; optionally add a small icon per tier. *(§4.9)*

### P1 — scoped spec, not yet built

5. **R5 — Attachment staged-chip flow.** Build the staged/error/reading/done chip described in `DEV-HANDOFF-command-chat-auth-ux.md` for `/command`'s composer, reusing existing glass/pill/dashed-drop-outline primitives per that doc's §11 ("no new component vocabulary"). This is the single biggest gap between spec and shipped code found here — largest effort in this list, but already fully designed. *(§4.7)*
6. **R6 — Onboarding responsive pass.** `/onboarding` has zero breakpoint classes; audit and add mobile handling for the multi-step CV/profile flow, matching the level of care already in `/command` and `/flow`. Do the same, lighter-weight, for `/jobs` and `/profile` (currently 2–3 breakpoint classes). *(§4.10)*

### P2 — decisions, not builds

7. **R7 — Verify "conversation is the system" in navigation.** Confirm whether `Sidebar`/`AppShell`/`Navigation` actually frame Jobs/Applications/Profile/Settings as views-into-chat-state (per the product vision, §1) or as standalone destinations competing with `/command`. This wasn't traced in this audit — read the nav copy and routing logic before deciding if anything needs to change.
8. **R8 — Sandbox route decision.** Keep, archive, or move `/sandbox/command-primitives` out of the production build — currently harmless (unlinked) but undecided. *(§4.5)*
9. **R9 — `MASTER.md` retirement.** Per DEC-20260706-001, `MASTER.md` is confirmed not-source-of-truth. Either delete it or rewrite it to describe Nocturne (§2), and add the same kind of historical banner `docs/archive/DESIGN.md` already has to `MASTER.md`, `Rico Hunt V2 - Offline.html`, and `nocturne-reference.html`. *(§3.1–3.2)*
10. **R10 — VengeanceUI/SkiperUI, opportunistic only.** Pull in a specific component only when a specific P1/P2 polish task calls for one and doing it by hand would clearly cost more or produce a worse result — not as a blanket adoption. *(§5)*

---

## 7. Constraints carried into every item above

- **No rewrites without measurable benefit.** `DashboardShell`/`AppShell` and `lib/api.ts`/`lib/api/*` are confirmed non-duplicates (§4.3–4.4) — do not touch either pair as part of this roadmap.
- **Preserve behavior.** R1–R4 are class/markup-level or additive (new toggle/banner) changes; none should alter existing working request flows.
- **Accessibility, responsiveness, and performance are floors, not goals to trade off** — R2–R4 and R6 exist specifically to bring weaker surfaces up to the bar the stronger surfaces (login, `/command`, `/flow`) already meet, not to introduce new patterns.
- **Backend/chat-engine/auth-API are out of scope**, per `DEV-HANDOFF` §12 — R5 in particular is composer/UI-state only; it must not touch the upload endpoint or CV parser.
- **Every new user-facing string goes through the translation layer** (EN/AR) — applies to R2, R3, R5 especially, per `DEV-HANDOFF` §6 and the Product Generalization Rule in `CLAUDE.md`.
