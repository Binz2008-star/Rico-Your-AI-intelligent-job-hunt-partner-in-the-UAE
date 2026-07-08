# Command Concept Sandbox — Handoff Package

**Source path:** `apps/web/app/sandbox/command-concept/`

**Current location:** `design-handoffs/incoming/command-concept-sandbox/`

## Status

**Reviewed — Approved as Design Reference (requires production adaptation).** See
`REVIEW.md` for the full decision and the adaptation contract. Not production
code; not promoted to `/design-gallery`. Every interactive action must be
rebuilt on Rico's production architecture (Intent → Safety Policy → Agent
Runtime → Persistence → Confirmation) before any production use.

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
a Nocturne (authenticated workspace) reference. Not rejected; not added to
`/design-gallery`; not promoted to `/command`. Any future production use requires
a separate, safety-reviewed implementation. See `REVIEW.md`.

## Nocturne identity check

- Navy canvas: uses `rgb(var(--bg))`
- Ember/gold accent: uses `rgb(var(--gold))`
- Aura teal for intelligence: uses `rgb(var(--aura))`
- Glass islands: uses `glass-panel` and `glass-island` classes
- Honest AI action labels: activity chips and "DEMO" labels present
