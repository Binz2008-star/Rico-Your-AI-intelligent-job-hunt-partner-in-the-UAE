# Review-gate evidence — Command Workspace v5 (2026-07-20)

This file answers the owner's review gate for PR #1238. All measurements were
taken against the committed `Rico Command Workspace v5.dc.html` in Chromium
(Playwright, headless **software rendering** — the worst-case renderer; real
devices with GPU compositing perform strictly better).

## Governance position (restated)

1. The original `Rico Command Workspace v4.dc.html` is **not in the repo** —
   it is owner-held, session-upload-only, per the 2026-07-19 handoff record.
2. v5 was **rebuilt from the recorded handoff contracts**
   (`design-handoffs/reviewed/2026-07-19-command-workspace-v4/README.md`).
   It is **not a direct port** of the v4 file.
3. A **pixel-level visual comparison against the original v4 is therefore not
   possible** from this repo; only contract-level parity can be evidenced
   (see the table below).
4. This PR does **not** replace the approved design. v4 remains the frozen
   approved reference.
5. Merging this PR stores a **review artifact only** — it does not adopt the
   design and does not authorize any product implementation. Every
   implementation PR still requires its own owner approval and `/command`
   freeze lift.

## 1. Screenshots — all seven modes, desktop and mobile

`screenshots/` (27 JPEGs, captured from the committed file):

| Mode | Desktop (1600×1000) | Mobile (390×844) |
| --- | --- | --- |
| Overview | `desktop-overview.jpg` | `mobile-overview.jpg` |
| Search | `desktop-search.jpg` | `mobile-search.jpg` |
| Applications | `desktop-applications.jpg` | `mobile-applications.jpg` |
| Documents | `desktop-documents.jpg` | `mobile-documents.jpg` |
| Interview | `desktop-interview.jpg` | `mobile-interview.jpg` |
| Learning | `desktop-learning.jpg` | `mobile-learning.jpg` |
| Activity | `desktop-activity.jpg` | `mobile-activity.jpg` |

Additional states: copilot open (`desktop-search-copilot.jpg`,
`mobile-copilot-open.jpg`), context panel (`desktop-search-copilot-context.jpg`),
loading/empty/error (`desktop-search-loading/empty/error.jpg`), scanning demo
(`desktop-search-scanning.jpg`), CV analysis (`desktop-documents-analysis.jpg`),
states drawer (`desktop-states-drawer.jpg`), 1366px mutual exclusion
(`desktop-1366-exclusive.jpg`), reduced motion (`desktop-reduced-motion.jpg`),
focus ring (`desktop-focus-visible.jpg`), mobile rail drawer
(`mobile-rail-drawer.jpg`).

## 2. Contract map — recorded v4 contract → v5 implementation

| Recorded v4 contract | Where implemented in v5 | Evidence |
| --- | --- | --- |
| **Copilot default-open policy** — Overview only, ≥1280px, only while no per-mode user preference; explicit open/close preserved per mode, never overridden; no auto-open <1280 | JS `applyDefaultOpen()` + `copPref{}` map; `setCopilot(open, isUser)` records preference only on explicit user action | Asserted in the scripted run: open on Overview load at 1600, closed after user Escape, stays closed on return |
| **Mode-scoped conversations** — per-mode transcript, "Scoped to {mode}" header, global profile knowledge, no cross-mode mixing | Seven `<template id="tx-{mode}">` transcripts; `loadTranscript(mode)` swaps thread + `#scopeLabel`; header reads "Scoped to {Mode} · profile knowledge is global" | `desktop-search-copilot.jpg`, `mobile-copilot-open.jpg` |
| **Keyboard** — Ctrl/Cmd+K toggles Ask Rico only outside editable elements; Escape closes copilot first, then next active overlay | Single `keydown` handler: `inEditable()` guard for ⌘K; Escape priority chain slash-panel → copilot → states drawer → context overlay → rail drawer | Asserted in the scripted run (toggle + Escape order both checked) |
| **Responsive** — ≥1600 four columns inline; 1280–1599 context/copilot mutually exclusive inline; <1280 overlay/drawer only; rail inline ≥900, drawer below; main `minmax(320px,1fr)`; no horizontal overflow | CSS breakpoints at 1600/1280/900 + JS `applyPanels()` (enforces exclusivity, overlay classes, scrim) ; `#main{min-width:320px}` | `desktop-1366-exclusive.jpg`; overflow assertion = 0px at 1600/1366/390 |
| **Trust & action vocabulary** — Information (plain) / Recommendation (accent rule, no buttons) / Action card with explicit state Available / Confirmation required / Working / Completed / Failed / Unavailable; no implied execution; drafts only | `.cmsg-info`, `.cmsg-reco` (accent rule, no buttons), `.cmsg-action` + `.statechip .st-*` (all six states used across the seven transcripts); confirm flow animates Confirmation required → Working → Completed only on user click | `desktop-overview.jpg` (Confirmation required), `mobile-copilot-open.jpg`; Unavailable state in Activity transcript |
| **Context sources** — Verified profile fact / User preference / Observed behavior / External job data / Rico inference; inference never shown as verified | `.src-verified/-pref/-observed/-external/-inference` labels; inference styled dashed, never green | `desktop-search-copilot-context.jpg` |
| **Regions parity** — modes rail (logo · goal-mini · 7 modes) · per-mode bodies · Ask Rico panel · context panel (Context/Memory tabs, source labels) · responsive drawers · floating launcher · design-states drawer | `#rail` (wordmark, `.goalmini`, 7 `.rail-item`) · 7 `section.mode` bodies · `#copilot` · `#ctx` with morphing tabs · rail/context/copilot overlay classes + `#fab` launcher + `#mobilenav` · `#statesTab`/`#statesDrawer` | All screenshots; `desktop-states-drawer.jpg` |
| **Prototype-only ⌘K contract** (recorded as NOT adopted for production) | Kept prototype-side only; production `Ctrl/Cmd+K → /command` composer focus is untouched (no production files in this PR) | PR diff = handoff directory only |

## 3. File size & performance report

**Size budget (404,390 bytes total):**

| Component | Bytes | Share |
| --- | --- | --- |
| Embedded fonts (base64 woff2 ×3, latin subsets) | 228,620 | 56.5% |
| CSS (tokens, atmosphere, components, motion) | ~70,756 | 17.5% |
| Markup (7 modes × 4 states, transcripts, panels) | ~78,027 | 19.3% |
| JavaScript (interaction engine) | ~26,967 | 6.7% |

**Runtime (headless Chromium, software rendering — worst case):**

- DOMContentLoaded 171 ms · load 194 ms · first contentful paint 336–1400 ms
  across runs (variance = decoding the base64 font payload)
- DOM nodes: 1,199 · JS heap: 9.5 MB · startup long tasks: 3 (82–103 ms,
  font decode + first layout), none afterwards
- Ambient animation frame rate: **29.7 fps in pure software rendering**
  (no GPU). Before optimization this was 13.5 fps; profiling attributed the
  cost to `filter: blur(70px)` on the ambient blobs and a full-viewport
  `mix-blend-mode: multiply` grain layer. Both were replaced (pre-softened
  radial gradients; plain low-opacity grain) with no visible design change.
  All remaining animation is transform/opacity only; on GPU-composited
  devices these layers are hardware-cheap.

**Verdict as recorded:** acceptable as a review prototype; the single-file /
embedded-font pattern is explicitly **not** a production implementation
standard (see README "Prototype-only ideas").

## 4. Font licensing

Both embedded typefaces are licensed under the **SIL Open Font License 1.1**,
which permits redistribution and embedding (including subset/base64 form)
provided the license accompanies the redistribution — satisfied by the
verbatim upstream license files committed in `licenses/`:

| Font | Copyright | License file (verbatim from upstream) |
| --- | --- | --- |
| Fraunces (roman + italic, latin subset) | © 2018 The Fraunces Project Authors — github.com/undercasetype/Fraunces | `licenses/OFL-Fraunces.txt` |
| Space Grotesk (latin subset) | © 2020 The Space Grotesk Project Authors — github.com/floriankarsten/space-grotesk | `licenses/OFL-SpaceGrotesk.txt` |

OFL 1.1 requires that the fonts not be **sold by themselves** and that the
license be included — both conditions are met; bundling inside a design
document is expressly permitted use.

## 5. Zero network calls — proof

Playwright request log while loading the file **and cycling through all seven
modes**: exactly **one** request — the `file://` document itself. No Google
Fonts, no Higgsfield or any CDN, no fetch/XHR/WebSocket, no external images
(grain is an inline `data:` SVG; all visuals are CSS/SVG). The page functions
fully offline.

## 6. Accessibility review (performed, not deferred)

**Contrast (WCAG 2.1 AA, computed mathematically for every token pair in
use):** an initial audit found **19 failing pairs**. All were fixed in this
committed version; a re-audit passes every pair:

- Secondary text token raised `rgba(31,27,21,.52)` → `.62` (3.35 → 4.51:1);
  all metadata/placeholder text moved off the border-strength token (2.30:1).
- New text-safe accent tokens per mode (`--modeAText`): terra `#A83A22`
  (5.33), electric `#2F48D1` (5.91), gold `#77560A` (5.63), purple `#5B3ED6`
  (5.65), amber `#8A5E0E` (4.76) — used for micro-label ticks, scope labels,
  slash keys, active nav, count badges.
- Large-numeral tiers re-inked: gold `#9C6705` (4.03), coral `#C05A28`
  (3.71), fit-number gradient darkened — all ≥3.0 (large-text threshold).
- Display headline accent gradient darkened to `#A83A22→#C6492E→#B25419`
  (min stop 4.20:1 ≥ 3.0 large-text).
- Ember buttons re-graded `#A83A22→#BE452B` (white text 6.00–4.85:1).
- Funnel labels: dark ink on light segments, light ink on the terra segment
  (4.57–7.83:1); text-shadow crutch removed.
- CV-analysis idle steps on the dark panel raised to 5.34:1.
- Documented exemption: the "Rico" logotype gradient (WCAG logotype
  exemption).

**Keyboard:** full traversal works — rail modes → goal-mini → top strip →
mode content → copilot (close, actions, suggestions, composer) → states
drawer, in DOM/logical order (sequence captured in the scripted run). ⌘K and
the Escape priority chain asserted. Non-`<button>` interactive elements
(goal-mini, presence orb) carry `role="button"`, `tabindex="0"` **and**
Enter/Space activation handlers (verified). Closed off-canvas panels are
`visibility:hidden`, so focus can never land in invisible content, and the
shell uses `overflow:clip` so no scroll state can reveal it.

**Focus visibility:** global 2.5px `:focus-visible` outline
(`desktop-focus-visible.jpg`).

**Reduced motion:** `prefers-reduced-motion: reduce` collapses every
animation/transition to end state (media query + JS `RM` guards for
count-ups, FLIP, bursts, tilt); emulated run confirms full content visible
with no motion (`desktop-reduced-motion.jpg`).

**Known remaining limitations (honest):** chip/control *borders* rely on text
contrast rather than 3:1 boundary contrast; screen-reader semantics
(aria-live granularity, roving tab-index in the rail) are prototype-grade —
both are called out for the production pass.

## 7. Scope cleanliness

The PR diff contains **only** this handoff directory
(`design-handoffs/incoming/2026-07-20-command-workspace-v5-cinematic/`):
prototype, README, EVIDENCE, licenses, screenshots. No production code, no
workflow, no AI_WORKSPACE mutation, no other files. There are no review
threads on the PR other than the automated Vercel preview comment (the
preview builds the unchanged `apps/web` — this PR does not touch it).
