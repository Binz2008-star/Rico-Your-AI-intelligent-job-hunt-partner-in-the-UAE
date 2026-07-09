# Command Concept Sandbox — Handoff Package

**Source path:** `apps/web/app/sandbox/command-concept/`

**Current location:** `design-handoffs/approved-for-gallery/command-concept-sandbox/`
(promoted from `design-handoffs/reviewed/command-concept-sandbox/`)

## Status

**Approved for gallery — staged as an isolated `/design-gallery` entry.** See
`REVIEW.md` for the full decision, the adaptation contract, and the gallery
promotion note appended at the end of that file. Still not production code —
the gallery entry renders the same reference-only components reviewed below
(disabled buttons, sample/demo data, no real actions). Every interactive
action must still be rebuilt on Rico's production architecture (Intent →
Safety Policy → Agent Runtime → Persistence → Confirmation) before any
production use.

## What it contains

- `page.tsx` — sandbox shell (scene picker, language toggle, demo label)
- `_components/ChatThread.tsx` — bilingual chat thread concept
- `_components/JobIntelCard.tsx` — explainable job intelligence cards
- `_components/SafetyCheckpoint.tsx` — high-impact action approval UI
- `_components/ThinkingState.tsx` — visible AI thinking/tool rail concept

## Important notes

- **No route after move:** This package no longer lives under `apps/web/app/`, so it does not create any real Next.js route.
- **Demo data only:** All jobs, messages, tool steps, and action summaries are simulated and labeled as DEMO.
- **No backend/auth/billing/database:** The prototype does not call any API, backend, or real service.
- **Dependencies:** Uses only `framer-motion`, which is already a project dependency.

## Review outcome

Decided: **Approved as Design Reference (requires production adaptation).** Kept as
a Nocturne (authenticated workspace) reference. Not rejected; promoted to an
isolated `/design-gallery` entry (see gallery promotion note in `REVIEW.md`);
not promoted to `/command`. Any future production use requires a separate,
safety-reviewed implementation. See `REVIEW.md`.

## Nocturne identity check

- Navy canvas: uses `rgb(var(--bg))`
- Ember/gold accent: uses `rgb(var(--gold))`
- Aura teal for intelligence: uses `rgb(var(--aura))`
- Glass islands: uses `glass-panel` and `glass-island` classes
- Honest AI action labels: activity chips and "DEMO" labels present
