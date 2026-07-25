# Command — Atelier Visual-Polish Reference

**Date:** 2026-07-24 · **Branch:** `claude/command-visual-polish-51dq2z` · **Status:** design reference (composition-only, not a drop-in)

A focused visual-polish pass over the structurally-complete Command reference, then the
strongest patterns propagated to the other 14 surfaces. Same information architecture, same
verified-state model, no invented backend behaviour. It does **not** touch `apps/web` production
code — the Command migration remains program item **M6** (see `AI_WORKSPACE/ATELIER_MIGRATION_PROGRAM.md`).

## Deliverable

- **`command-atelier-polish.html`** — one self-contained, CSP-safe reference (no external
  requests; opens in any browser and doubles as a Claude Artifact page).

Everything the brief asked for lives inside that one file, navigable from the header:

| Section | What it shows |
| --- | --- |
| Overview | Palette (Atelier, unchanged), the truth contract, motion legend |
| Command | Flagship desktop workspace — sessions rail · living operation thread · adaptive job-search rail · composer. **Play sequence** button runs the real state machine. |
| States | 15 states, each designed on purpose: empty · session-loading · streaming · needs-input · permission · proposed-change · running-timeline · verified-receipt · stopped · network-failure · rate-limit · quota · unauthenticated · guest · failed-step + inline retry |
| Motion | 13-cell storyboard with live prototypes + exact specs, plus "motion rules" / "what never moves" |
| Mobile · RTL | Phone frame (drawer tab) and fully-mirrored Arabic frame |
| Before / After | The flat, diagram-like card vs. the living operation thread |
| Surfaces | The 14 other surfaces + the reusable polish kit |
| Audit | Surface × pattern consistency matrix + the truth checklist + asset list |

## Two modes (top-right toggle)

1. **Product Preview** — the clean customer experience. No engineering labels, no "backend
   required" copy inside the frame.
2. **Implementation Review** — the same frames with capability chips, repository evidence
   (`agent/runtime.py`, `search_dedup.py`, `applicationStatus.ts` …), backend-event requirements,
   and production gaps.

The header also carries a **motion switch** (preview reduced-motion) and a **light/dark island** toggle.

## The truth contract (non-negotiable)

- Motion fires only on a real `pending → running → complete/failed` transition
  (`RicoProgressStepSchema` — the only step states that exist).
- No fabricated percentages, search counts, tools, or hidden reasoning shown as fact.
- The **moss verified receipt** appears only for a real completed verification step / `live_verified`.
- Verification vocabulary is exactly the nine backend-emitted `verification_status` values.
- Proposed changes render `field · current_value → proposed_value · source` and confirm from
  **persisted** state (#1361), never pre-write intent.
- The approval gate (`RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true`) is never bypassed.
- Historical / non-live threads carry `.frozen` and never animate; everything sits behind
  `prefers-reduced-motion`.

## Palette (Atelier, kept)

warm paper `#F1EADD` · black ink `#1F1B15` · clay `#C6492E` (attention/action) ·
moss `#3C7A52` (verified only) · muted blue `#3A5F7D` (info, where the system already uses it) ·
amber `#D99C4E` (documents/provenance). No glassmorphism, no neon gradients, no cyberpunk.

## Assets — original, self-contained

34-symbol inline line-icon set · letterpress **Verified** seal · CV page-fragment thumbnails ·
job-result mini cards (company monogram + location pin) · provenance/source marks ·
paper-grain wash (one shared `feTurbulence` filter) · 14 per-surface editorial motifs ·
empty-state artworks. No stock photos, no copyrighted screenshots, no external requests.

## Viewing

Open the HTML directly, or render it — it was verified in Chromium (desktop, mobile 390, RTL,
Preview + Implementation, and the full played sequence) with zero console errors. A live Artifact
link is attached in the PR / chat for the interactive toggle + motion.

## Reuse map (when M6 is scheduled)

`WorkspaceShell` (Shell C) · `atelier-kit` tokens/fonts · `JobMatchCardAtelier` ·
`STAGE_DEFS` from `applicationStatus.ts` · `RicoAgenticUiSchema` (`progress[]`,
`permission_request`, `proposed_changes[]`, `attachment_analysis[]`). This reference is the
composition source; it is not a component drop-in and must not regress public chat, rate limits,
or the safety affordances.
