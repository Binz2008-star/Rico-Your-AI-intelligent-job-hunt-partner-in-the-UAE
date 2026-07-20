# Command Workspace v5 — cinematic art-direction pass (2026-07-20)

**Status: NEW, unreviewed handoff.** This package proposes the next iteration of
the Command Workspace design reference. It is design-only and awaits owner
review per `design-handoffs/README.md`. Nothing here is production code and
nothing here lifts any freeze.

**Owner ruling (2026-07-20), binding for this package:** the original v4 file
is not in the repo; v5 is a rebuild from the recorded handoff contracts, not a
direct port of the v4 file; visual comparison against the original v4 is not
possible from this repo; this package does not replace the approved design;
and merging its PR stores a review artifact only — it is neither design
adoption nor authorization to implement. Review-gate evidence (contract map,
size/performance report, font licensing, network proof, accessibility audit)
lives in [`EVIDENCE.md`](./EVIDENCE.md).

## 1. Prototype name

`Rico Command Workspace v5.dc.html` — a single self-contained HTML prototype
(no CDN, no fetch/XHR, no persistence; Fraunces + Space Grotesk embedded as
data-URI fonts so the file renders identically offline).

**Relation to v4:** the owner-held v4 file (`Rico Command Workspace v4.dc.html`,
frozen 2026-07-19, intentionally never committed) was not available in this
environment. v5 was therefore rebuilt to the **recorded v4 information
architecture and acceptance contracts** in
`design-handoffs/reviewed/2026-07-19-command-workspace-v4/README.md`, then the
full art-direction pass was applied on top. The v4 reference remains frozen and
untouched; v5 is a new proposal in the same version trail (v1 → v2 → v3 → v4 →
**v5 proposal**).

## 2. Design goal

Push the workspace from "clean SaaS dashboard" to a cinematic, AI-native
career operating system: editorial typography as architecture, per-mode visual
identity, a visible motion language, and an ambient Rico presence — while
keeping the approved IA, the trust/action vocabulary, and the v4 keyboard +
responsive contracts intact.

## 3. Screens/states covered

All seven modes, each with a distinct composition and its own
default / loading / empty / error variants (switchable from the design-states
drawer, an engineering review affordance):

- **Overview** — "Your career is compounding": cinematic deep-ink score panel
  (layered SVG rings, orbiting indicators, count-ups, +delta), goal hero with
  animated milestones, urgency-tiered next actions, live "Rico is working"
  strip, intelligence signal tiles with micro-bars.
- **Search** — "Find work worth moving for": mission-control search bar with
  rotating conic intelligence glow, snapping filter chips, scanning beam demo,
  ranked results (hero match with animated evidence bars; gold/coral/far fit
  tiers), Rico-recommends block, composer with slash-command panel.
- **Applications** — "Your pipeline is moving": momentum/streak/stalled chips,
  flowing stage funnel, five-stage board with stage colors, pulsing stalled
  state, interview countdown card, gold offer card, FLIP "advance" animation
  with live count updates.
- **Documents** — "Your professional identity, organized": identity vault with
  layered active-CV stack ("powered on" glow + periodic scan line), ATS/
  freshness/language quality meters, version lineage rail, verified/draft
  source chips, upload zone with light sweep, 4-step CV analysis sequence on a
  dark panel.
- **Interview** — "Prepare to own the room": dark stage hero with spotlight,
  animated waveform, confidence arc, 48:00 countdown card, three drill decks,
  3-2-1 mock-session countdown overlay.
- **Learning** — "Close the gaps that matter": dusk skill-constellation SVG
  (strong/developing/gap nodes, pulsing gap halos, drawn route lines),
  milestone banner, sprint cards with progress landscapes, skill-completion
  burst demo.
- **Activity** — "Everything Rico has done for you": living ledger timeline
  with traveling spine pulse, five distinct event glyph shapes (action /
  recommendation / milestone / scan / user decision), expandable decision
  cards, trust footer.

Cross-cutting: Ask Rico copilot with per-mode scoped transcripts and the full
action-state vocabulary (Available / Confirmation required / Working /
Completed / Failed / Unavailable), "Rico noticed / Rico recommends"
treatments, context panel with all five source labels (Verified profile fact /
User preference / Observed behavior / External job data / Rico inference),
success bursts, toasts, per-mode atmospheric backgrounds, film grain, presence
orb with ready/thinking/acting/completed/warning states.

## 4. Visual direction

Atelier warm-paper world (anchored to `WORKSPACE_THEME` /
`atelier-kit` values: paper `#F1EADD`, ink `#1F1B15`, terracotta `#C6492E`)
extended with amber/gold/coral energy, deep ink-navy cinematic planes for
focal moments (score, interview stage, constellation, analysis), and a
**selective** electric cobalt (`#3D5BF5`) reserved for AI moments. Editorial
Fraunces display with gradient italic accent words; Space Grotesk UI; mono
micro-labels. Per-mode accent tokens recolor the rail marker, atmosphere and
ambient blobs on every switch. Note: these hex values are **composition
guidance only** — production tokens remain canonical per the v4 boundaries.

## 5. Motion used

CSS keyframes + Web Animations-free rAF count-ups only; no external animation
libraries. Categories: directional mode exits with layered staggered
entrances (rise/unfold/mask/scale/tilt-in, replayed on every mode switch);
pointer-tracked card tilt + border illumination and magnetic buttons (rAF-free,
pointermove, mouse-only); active-state compression; morphing tab pill; ambient
focal-zone motion (orb breathing, scanning beams, funnel flow, spine pulse,
gap halos, light sweeps — deliberately not everything at once); micro-
interactions (success particle bursts, toast spring, FLIP card advance, ring
draws, evidence-bar draws, thinking dots, 3-2-1 countdown).
`prefers-reduced-motion` collapses all animation to final states (verified via
emulation: full content visible, no motion).

## 6. Arabic/English behavior

English-only sample content in this reference (same as the v4 prototype). The
type stack is Latin; Arabic companions (Noto Naskh/Sans Arabic) exist in the
production atelier-kit and would slot into the same hierarchy. RTL
mirroring of the rail/panels is not exercised here and must be validated at
implementation time.

## 7. Mobile behavior

- Rail becomes a drawer (hamburger in the top strip) below 900px.
- Designed bottom mode bar (7 modes, spring active state) + floating Rico orb
  launcher for the copilot.
- Copilot and context become right-side sheets below 1280px; 1280–1599 keeps
  context and copilot mutually exclusive inline; ≥1600 all four columns may
  sit inline (v4 responsive contract preserved).
- Funnel shows counts-only labels on mobile; pipeline board scrolls inside its
  own container; no horizontal page overflow at 1600/1366/390 (verified).
- Keyboard: Ctrl/Cmd+K toggles Ask Rico outside editables; Escape closes
  copilot first, then the next active overlay (v4 prototype contract —
  production ⌘K behavior is NOT changed by this handoff).
- Copilot default-open policy preserved: Overview only, ≥1280px, only while
  the user has expressed no preference for that mode; explicit open/close is
  remembered per mode within the session.

## 8. Production-safe ideas

Editorial hero compositions per route; career-score ring treatment on the
dashboard; evidence bars + fit tiers on job cards; stalled/interview/offer
stage treatments; active-CV "powered on" vault treatment and version lineage;
event-shape vocabulary for the activity ledger; action-state chips exactly
matching the trust vocabulary; empty/loading/error state family; reduced-
motion discipline; per-mode accent tokens.

## 9. Prototype-only ideas

The SPA mode switcher (production stays multi-route on `WorkspaceShell` per
DEC-20260717-001); the design-states drawer; embedded Google-font data URIs;
in-memory session model; all sample data (Meridian Retail Group, Nova
Fintech, Falcon Logistics, Pearl Property Group, Sahara Cloud, Harbor Health,
Atlas Aviation Services are fictional); the Memory tab (illustrative only —
Career Memory Engine remains Draft/OFF); Interview, Learning and Activity
modes as a whole remain deferred until real capabilities exist (v4 boundary
5); scripted copilot replies (labeled as scripted in the UI).

## 10. Risks

- **Performance:** constant ambient animations are limited to focal zones and
  transform/opacity only; blur layers (glass, blobs) are the main GPU cost —
  audit on low-end devices before adopting any of it.
- **Accessibility:** a computed WCAG AA contrast audit was performed on every
  token pair in use — 19 initially-failing pairs were fixed in this version
  (details in `EVIDENCE.md` §6); keyboard traversal, ⌘K/Escape order,
  Enter/Space activation on role=button elements, and reduced-motion were all
  verified. Remaining prototype-grade gaps (control-border contrast,
  screen-reader semantics) are listed in `EVIDENCE.md` for the production
  pass.
- **File size:** ~400KB single file (fonts embedded) — fine as a reference,
  not a production pattern.
- **Governance:** the `/command` design freeze and all v4 boundaries remain in
  force; every implementation PR needs its own owner approval and freeze lift.

## Verification (2026-07-20, Chromium via Playwright)

All modes visually inspected at 1600×1000; loading/empty/error states
captured; scan/analysis/advance/mock/skill/score demos exercised; 1366px
context-vs-copilot mutual exclusion asserted; 390×844 mobile (overview,
pipeline, interview, copilot sheet open/closed, rail drawer) captured; ⌘K and
Escape order asserted; `prefers-reduced-motion` emulated; zero console
errors/warnings; zero page errors; no duplicate IDs; no horizontal overflow.
Screenshots in `screenshots/`.
