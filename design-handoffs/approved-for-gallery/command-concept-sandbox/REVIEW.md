# Review — Command Concept Sandbox

**Classification:** Approved as Design Reference (requires production adaptation)
**Date:** 2026-07-08
**Reviewer decision by:** Roben (owner)
**State transition:** `incoming/` → `reviewed/` (after cleanup below; not promoted to `/design-gallery` or production)

## Decision

Approved as a **design reference**, not for direct promotion to production. The
prototype is on-identity (Nocturne), dependency-safe (`framer-motion` only, an
existing dependency), and uses the real theme tokens. Four concepts are aligned
with Rico's long-term vision and worth keeping as reference:

- Tool Activity Timeline (`ThinkingState`)
- Explainable Match Card (`JobIntelCard`)
- Safety Approval Surface (`SafetyCheckpoint`)
- Thinking State (`ThinkingState`)

It is **not rejected** and is **not** to be wired into `/command` or any
production surface as-is.

## Adaptation contract (required before any production use)

Every interactive action must be rebuilt on Rico's production architecture:

- **No** frontend-only approval logic.
- **No** `alert()` actions.
- **No** local state pretending persistence.
- Every future action must route through:

  ```text
  Intent → Safety Policy → Agent Runtime → Persistence → Confirmation
  ```

  i.e. `rico_safety.py` guardrails + `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS` +
  `agent_runtime.handle_action()` + `POST /api/v1/actions/{action}` (idempotent,
  audit-logged), with the confirmation surfaced back to the user.

## Cleanup applied for the `reviewed/` state

1. **Hardcoded RGB colors → design tokens.** All raw `rgb(255 196 110)`,
   `rgb(240 169 74)`, `rgb(129 140 248)`, and `#0a0a0f` values replaced with
   `--gold-hover`, `--gold`, `--magenta`, and `--rico-on-primary` tokens (plus
   `--overlay` for the white inset). Nothing hardcoded remains.
2. **English leaks localized.** The `Done` activity chip, the score-ring
   `aria-label`, and the skeleton `aria-label` now switch EN/AR.
3. **Frontend approval simulation removed.** `SafetyCheckpoint` no longer runs a
   local approve/reject state machine or shows "action processed"
   fake-persistence copy; it renders the gate at rest with **non-functional**
   (disabled) buttons and an explicit "Required production routing" reference.
   `JobIntelCard` Apply/Save `alert()` calls removed; buttons are disabled and
   labeled "reference — no action".

## Design-system boundary (recorded decision)

- Public marketing surfaces → **Atelier**
- Authenticated Career Workspace → **Nocturne**
- The two design systems must **not** be merged into one.

This prototype is a **Nocturne** (authenticated workspace) reference.

## Not done (intentionally)

- No production implementation.
- No `/design-gallery` route added.
- No `/command` change.

See `AI_WORKSPACE/DECISIONS.md` for the recorded architectural decisions.

---

## Gallery promotion note (2026-07-09)

**State transition:** `reviewed/` → `approved-for-gallery/` → staged as an
isolated `/design-gallery` entry (draft PR).

Per the `design-handoffs/README.md` workflow, this package is promoted to
`approved-for-gallery/` and added to `/design-gallery` as its own variant tab,
under `apps/web/components/design-gallery/command-concept-sandbox/`. This is
a **gallery-only** move:

- No production route (`/`, `/command`, `/rico`, `/applications`, `/profile`,
  `/settings`, auth) is touched.
- No backend, auth, Neon, or schema change.
- No real action wiring — `search_jobs`, apply, save, CV upload, and profile
  save remain unimplemented; all buttons stay disabled/reference-only exactly
  as cleaned up above, and all data stays sample/demo.
- The Adaptation contract above is unchanged and still required in full
  before any of this reaches `/command` or another real surface.

This does **not** re-open or revise the original review decision — it only
executes the "add to gallery" outcome the decision already allowed.
