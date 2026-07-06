# Command Concept Sandbox — Handoff Package

**Source path:** `apps/web/app/sandbox/command-concept/`

**Current location:** `design-handoffs/incoming/command-concept-sandbox/`

## Status

Prototype only. Not production code. Pending review before any move to `/design-gallery`.

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

## Review goal

Decide whether any of these concepts should be:
- Rejected
- Kept as inspiration
- Cleaned up and added to `/design-gallery`
- Eventually promoted to `/command` production (requires separate approval)

## Nocturne identity check

- Navy canvas: uses `rgb(var(--bg))`
- Ember/gold accent: uses `rgb(var(--gold))`
- Aura teal for intelligence: uses `rgb(var(--aura))`
- Glass islands: uses `glass-panel` and `glass-island` classes
- Honest AI action labels: activity chips and "DEMO" labels present
