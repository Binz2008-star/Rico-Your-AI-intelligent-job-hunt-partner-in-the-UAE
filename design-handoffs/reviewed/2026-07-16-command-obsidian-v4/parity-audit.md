# Phase 1 — `/command` Obsidian parity audit (read-only)

- **Production baseline:** `origin/main = cafe340a0998e4f815f0b5a350149d6d5c026394` (2026-07-16)
- **Canonical target:** recording `2026-07-16 004205.mp4` + ZIP `src/routes/rico.tsx`,
  `src/styles.css` (Obsidian night), `src/lib/rico-content.ts`, `src/lib/i18n.tsx`
  (see `canonical-files.md`)
- **Audience audited:** authenticated `/command` (the recording shows the operator
  console; the public/guest surface keeps its approved reference chrome and is only
  affected where noted)

## Status correction — owner executive review, 2026-07-16 (second pass)

The first C1 draft was a **visual shell, not the owner-approved Command
experience**. Recorded status (binding until the owner changes it):

| Item | Status |
| --- | --- |
| C1 visual shell | implemented in Draft (#1043) |
| C1 functional no-regression evidence | **partial** — a mounted-component interactive suite now covers send / user turn / thinking / streaming tokens / completion / stop-cancel / retry / New chat / Clear history / panel + language + theme toggles at the network boundary; the full 19-flow acceptance matrix below remains OPEN |
| Sessions rail parity | truthful single-conversation rail shipped in C1 (New chat · current conversation · Clear history · history loading/error). **True multi-session history = backend capability gap, separately scoped — no session APIs exist; nothing may be fabricated** |
| Transcript interaction parity | **missing** (C2) |
| Canonical flow parity | **not implemented** (C2+) |
| PR #1043 | **Draft — not ready for merge**; owner gate required |

Screenshot rule: every synthetic capture is stamped
**MOCKED VISUAL EVIDENCE — NOT FUNCTIONAL SMOKE** and proves layout only.
Functional claims come exclusively from the mounted-component no-regression
suite (`apps/web/__tests__/command-obsidian-noregression.test.tsx`) and,
later, the owner's real authenticated smoke.

**Honest completion vs the recording: ~25%.** Slices 4a–4e delivered the right
*functional* skeleton (three-region layout, Atelier composer, message rows,
job cards, right rail) with business behavior preserved — but the entire
visual language (Obsidian canvas, acid-lime signal, mono-eyebrow meta system,
gutter transcript, status top bar, grid texture/aura, typography) is absent.
No component currently passes a side-by-side frame comparison.

Severity: **B** = blocker (gate cannot pass), **M** = major, **m** = minor.

## Corrective slice plan (smallest-PR routing referenced below)

| Slice | Objective |
| --- | --- |
| **C1** | Route-scoped Command Obsidian foundation: obsidian tokens through the existing workspace-theme context, dark canvas + grid texture + lime aura, top status bar, three-column proportions, rail framing, desktop rail toggles |
| **C2** | **Real Command event/presentation adapter** (owner directive — NOT a typography-only repaint): a maintainable mapping layer from existing production truth to canonical Obsidian presentation. Real source → canonical presentation: user message → YOU · thinking=true → safe working indicator · operationState → safe TOOL/working label · SSE token → streaming RICO response · SSE done → completed response · SSE error/timeout → ERROR + real Retry · agentic_ui.progress → progress rows · agentic_ui.actions → ASK/action rows · permission_request → permission checkpoint · proposed_changes → DIFF/review surface · attachment_analysis → file intelligence surface · matches → JOB MATCH · applications → TRACKER/pipeline · profile_gaps → profile intelligence · options/next_actions → real next-action controls. Never display hidden chain-of-thought; never fabricate PLAN/TOOL steps; render only operational labels supported by real API/state evidence. Includes the transcript gutter/type-scale rhythm those mappings render in |
| **C3** | Composer parity: `/` glyph, hints row, send/stop treatment, gradient fade |
| **C4** | Job intelligence cards: MATCH card structure, ScorePip tiers, WHY-IT-FITS/HONEST-GAPS blocks |
| **C5** | Right-rail content parity: shortlist mini-cards, pipeline stage bars, SIGNAL section, empty states |
| **C6** | Mobile drawers + RTL + typography (Space Grotesk/Inter/JetBrains Mono, Arabic stacks) + final recording-parity visual gate |

## Component-level mismatch matrix

| # | Component | Canonical (recording + `rico.tsx` / `styles.css`) | Production today (`cafe340a`) | Exact difference | Sev | File(s) requiring change | Behavior risk | Slice |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Viewport & dark canvas | `h-dvh` console on Obsidian night paper `#0a0b0d`, ink `#f2f4f0`, overflow-hidden root | Authenticated: WorkspaceShell dark island — warm cacao `#17140F`/`#211C15`, cream ink `#EFE7D6`; inner wrapper still Nocturne `bg-background` | Whole color world wrong: warm cacao/cream vs cold obsidian/lime; double background (island + Nocturne wrapper) | **B** | `components/workspace/theme.ts` (new route palette), `app/command/page.tsx` (`CommandChrome`), new shell component | None — repaint via the theme context all 4a–4e surfaces already consume | C1 |
| 2 | Acid-lime accent & glow | Single signal `--sun #c8ff3f` (dark) / `#3e6b0f` (light); selection lime; plate shadows with lime edge | Accent = sun-red `#E0895A` (dark) / `#C6492E`; legacy Nocturne `gold` classes on state chips/retry | Accent hue entirely different; no lime anywhere; two competing accents (red + gold) | **B** | palette override (`c.red`→sun) covers themed surfaces; remaining hard-coded `gold` classes in `app/command/page.tsx` | None | C1 (tokens) + C2/C4 (gold remnants) |
| 3 | Grid texture & aura | Fixed 64px 1px grid @5% radial-masked + lime radial aura (20% dark) above viewport | Absent (flat island background) | Missing both texture layers | M | new route-scoped canvas layers in the `/command` shell (must NOT touch global `body::before/::after`) | None (pointer-events-none) | C1 |
| 4 | Top status bar | Full-width h-12 sticky bar: PanelLeft · **Rico** · `JOB HUNT · UAE` eyebrow · status dot (lime pulse while working) + mono caps READY/WORKING · EN/ع · theme · PanelRight | Desktop authenticated: **no top bar at all** (side nav only); mobile/public: MobileCommandHeader (different content, no status) | Entire component missing on desktop; no live status indicator anywhere | **B** | new `CommandObsidianShell` top bar; `app/command/page.tsx` passes `busy` | Low — new chrome, no handlers moved | C1 |
| 5 | Left rail | 260px SESSIONS rail: eyebrow + `+ new`, session rows w/ relative time, active lime dot, `N THREADS` footer; collapsible | **C1 draft:** truthful CommandConversationRail (New chat · current conversation title/count · Clear history · history loading/error; nav relocated to compact top-bar icons) | Multi-session list still impossible — no backend session APIs; single-conversation surface is the truthful maximum today | M (product/backend gap) | backend session APIs = separately scoped capability; rail content parity beyond one conversation blocked on it | Must never fabricate sessions | OPEN (backend) |
| 6 | Desktop proportions | 260 / flexible transcript `max-w-[720px]` / 300 | 244 / `max-w-5xl` (1024px) / 300 | Transcript measure ~40% too wide; rails misproportioned | **B** | shell grid + `app/command/page.tsx` main `max-w` | None | C1 |
| 7 | Transcript gutter labels | Mono 10px caps gutter (`min-w-[64px]`): YOU/THINK/PLAN/RUN/DONE/FAIL/ASK/MATCH/RICO, lime for hot states | No gutter column; rico turns get a serif "R" avatar mark, user turns end-aligned | Entire gutter system missing | **B** | `components/command/CommandMessages.tsx`, `app/command/page.tsx` rows | Low — presentational wrapper around existing rows | C2 |
| 8 | User messages | Display font 22–26px tight, gutter `YOU`, start-aligned | 14–15px emphasized ink, end-aligned, no gutter | Type scale, alignment, gutter | **B** | `CommandMessages.tsx` | None | C2 |
| 9 | Assistant responses | 16px ink; final turns: top rule + lime ✦ prefix + `→` suggestion pills | Flowing markdown behind "R" mark; suggestion chips exist (gold/red styling) | Missing rule+✦ treatment; pill styling off; markdown scope colors wrong hue (fixed by tokens) | M | `CommandMessages.tsx`, `RicoMarkdownContent` scope | None | C2 |
| 10 | Progress / reasoning steps | THINK italic rows, PLAN `n/total` checklist w/ lime ✓ boxes + strikethrough, tool rows `name (arg)` + arrow detail lines + `✓ note` | `AtelierWorkingIndicator` (single working row) + `operationState` message; no plan/think/tool rows | Rico's backend does not emit plan/tool steps today — canonical presentation needs a mapping layer over existing operation states; richer steps are a backend capability, out of design scope | M | `CommandStates.tsx` (presentation); backend step events = separate program, **not** this stream | High if faked — must NOT fabricate fake progress steps; only restyle real states | C2 (restyle real states only) |
| 11 | Streaming cursor | 7px ink block caret pulsing at text end; `…` gutter row while waiting | Streaming text appends with no caret; working indicator separate | Missing caret + waiting row treatment | M | `CommandMessages.tsx`/`CommandStates.tsx` | None | C2 |
| 12 | Composer | Sticky, gradient fade from paper, rounded-2xl card: lime `/` glyph · paperclip · textarea · ink send/stop (lime hover); hints `⌘K COMMANDS /FIND /TAILOR /TRACK` + `↻ reset` | Atelier composer card (4a): paperclip/textarea/send/stop/counter/sign-up CTA present; red accents; no `/` glyph; different hints row; no gradient fade | Structure close; token hue wrong (fixed by C1); `/` glyph, hints row content, gradient missing | M | `components/command/CommandComposer.tsx` | Low — keep all handlers/tests (29 composer tests) | C3 |
| 13 | Job-match cards | MATCH card: display 18px role + RICO PICKS pill + ScorePip; mono meta (company/city/salary/posted); lime-bordered WHY IT FITS YOU `→` bullets; HONEST GAPS italic; `TAILOR CV & APPLY / SAVE / SKIP` + `FIT · n%` | Slice-4d Atelier cards: real data incl. verification status + apply-link fallbacks; different block structure, red/gold accents, no lime pip tiers | Structure + accent + labels differ; production has MORE real affordances (verification, fallback links) that must be kept | M | `app/command/page.tsx` `JobMatchCard`, `JobFallbackActions` | Medium — cards carry real apply/save/skip actions through `agent_runtime`; restyle only, keep every action | C4 |
| 14 | Score indicators | ScorePip pill: tiered (strong ≥88 lime / solid / stretch), display numeral + `%` | Rail: plain red pct text; cards: no tiered pip | Missing pip component + tiers | M | shared pip in `CommandRail.tsx` + card file | None | C4/C5 |
| 15 | Right rail — shortlist | 300px SHORTLIST + count, mini-cards (display company + small pip + mono role + caps city + lime ✦ RICO PICKS) | 4e CommandRail: SHORTLIST + count + mini-cards (serif company + red pct + mono title + caps location) — structurally very close | Hue (fixed by C1), pip treatment, RICO PICKS tag missing | m | `CommandRail.tsx` | None | C5 |
| 16 | Right rail — pipeline | PIPELINE + count; stage caps in lime + segmented stage progress bar + `NEXT · …` line | PIPELINE + count + status label; **no segmented bar, no NEXT line** | Missing progress bar + next-check line (needs real stage data already present in `applications`) | M | `CommandRail.tsx` | Low — display-only derivation | C5 |
| 17 | Right rail — SIGNAL | SIGNAL + count: op rows (GREP/READ/WRITE tags, write=lime) | **Absent** | Whole section missing; production has no tool-op event stream — map from real events only (e.g. CV upload/read, search ops) or defer | m | `CommandRail.tsx` (+ real event source) | High if faked — only render real operations | C5 (partial) |
| 18 | Empty states | Rail: italic "Empty for now — Rico fills this as he scores matches."; transcript opens with session slug row | Rail empty state exists (similar copy); transcript empty = hero + quick-action chips (product onboarding, keep) | Slug/session header row missing; hero chips are a Rico product feature to keep (owner UX), restyled | m | `CommandMessages.tsx` empty state styling | None | C2 |
| 19 | Loading / error / retry | FAIL gutter rows: lime `✗ message` behind lime border + italic retry note; retry mono button | Amber slow-banner; gold retry links; red/gold error chips | Wrong hue + structure; banner vs row | M | `app/command/page.tsx`, `CommandStates.tsx` | Low — keep retry semantics exactly (`isError`/`retryText`) | C2 |
| 20 | Mobile drawers | Rails become fixed overlays under the top bar with blur backdrop; composer persists | Left nav: MobileCommandHeader menu + MobileBottomNav; right rail **unreachable on <lg** | No drawer pattern; no mobile access to shortlist rail | M | shell + `CommandRail.tsx` | Medium — don't break MobileBottomNav/e2e | C6 |
| 21 | Arabic / RTL | Full RTL mirroring; Arabic stacks (IBM Plex Sans Arabic/Amiri); mono-eyebrows drop caps-tracking in AR; LTR-forced numerals/paths | RTL supported across shell/composer/messages (existing tests); Arabic uses body stack; no eyebrow AR rules | Works functionally; typographic treatment differs | m | shell + eyebrow utilities | Low | C6 |
| 22 | Typography | Space Grotesk display / Inter body / JetBrains Mono / Fraunces accents | Fraunces serif + `--font-body` + `--font-mono` (Atelier) | Full font system different | **B** for final gate (route-scoped font load) | route-scoped `next/font` load in `/command` shell | Low — route-scoped, no global font change | C6 |
| 23 | Borders / rules | 1px `--rule #1f2229` hairlines; start-border emphasis bars in lime | rgba-cream hairlines (`c.hair`) | Fixed by palette override in C1 | m | palette | None | C1 |
| 24 | Scrolling & sticky | Top bar sticky; transcript sole scroll region pinned-to-bottom w/ 96px threshold; composer sticky w/ gradient | Messages container scrolls, composer fixed below, autoscroll exists | Close; gradient + pin threshold differences only | m | `page.tsx` | None | C3 |
| 25 | Status semantics | READY / RICO IS WORKING / LIVE driven by real run state | `thinking` state exists but no visible status readout | Map `thinking`/streaming → status label (real state only) | M | shell top bar + `page.tsx` | None — derives from existing state | C1 |

## Blocker summary (gate-critical)

1. **Obsidian tokens + dark canvas + lime accent** (rows 1–2) — foundation for everything.
2. **Top status bar** (row 4).
3. **Three-column proportions + rail framing** (rows 5–6).
4. **Transcript gutter system + user-turn type scale** (rows 7–8).
5. **Typography system** (row 22) — final-gate blocker, deliberately last (C6).

**Confirmed first corrective PR: slice C1 — "Command Obsidian foundation"**
(route-scoped tokens through the existing workspace-theme context, dark
canvas + texture/aura, top status bar, 260/720/300 proportions, rail framing,
desktop rail toggles). It is the highest-impact isolated change: through the
theme context it repaints every 4a–4e surface to the Obsidian world in one
reviewable diff, with zero chat-logic movement.


## Functional acceptance matrix (owner-mandated — gate for "Command parity complete")

Real flows that must be verified (mounted components or real authenticated
smoke — synthetic screenshots do not count) before `/command` may be declared
complete. Status as of this revision:

| # | Flow | Status |
| --- | --- | --- |
| 1 | Normal conversation | **covered** — no-regression suite (mounted CommandPage, network fixtures) |
| 2 | Streamed response | **covered** — real `sendChatStream`/`_readSSE` over a driven SSE body |
| 3 | Stop generation | **covered** — abort-wired stream → real AbortError path + Retry |
| 4 | Retry failed response | **covered** — network-failure → error turn → Retry resends same text |
| 5 | Upload CV | OPEN |
| 6 | Upload another document type | OPEN |
| 7 | Profile preview and confirm | OPEN |
| 8 | Job search and results | OPEN (job-card rendering exists in 4d tests; end-to-end flow not yet in the C-suite) |
| 9 | Apply / Save / Verify / fallback actions | OPEN |
| 10 | Application-status response | OPEN |
| 11 | Permission request and approve/cancel | OPEN |
| 12 | Proposed profile change and review | OPEN |
| 13 | Action chips and navigation | OPEN |
| 14 | Current conversation history | **covered** — history fixture restore + truthful load-error surfacing |
| 15 | New Chat and Clear History | **covered** — rail controls → real handlers → real DELETE |
| 16 | Right rail updates from actual messages | partial — unit-tested derivations (4e); live-update flow OPEN |
| 17 | EN/AR and RTL | partial — shell/rail toggle covered; per-flow AR coverage OPEN |
| 18 | Desktop/mobile | partial — desktop covered; mobile drawers are C6 |
| 19 | Loading | partial — history loading covered; per-surface loading states OPEN |

Do not declare `/command` complete until every row is **covered** and the
owner's recording-based visual gate passes on the real product.
