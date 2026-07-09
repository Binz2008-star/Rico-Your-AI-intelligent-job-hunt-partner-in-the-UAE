# Rico Design Reference Package — Reference Only

**Classification:** Reviewed — keep as inspiration/reference
**Date:** 2026-07-09
**Reviewer decision by:** Roben (owner)
**State:** `reviewed/` — reference material, not approved work

## What this is

`rico-design-reference.zip` is a general, self-contained "Rico Design
Reference — Plug-and-Play Package" (`rico-ref/`, 58 files, ~14 MB):

- `01`–`05` numbered docs: Nocturne design tokens, per-surface component
  notes, interaction notes (streaming/attachments/safety/RTL),
  visual-vs-backend contracts, and an ordered implementation-sequence
  proposal.
- 10 sanitized screenshots (landing, `/command`, signup, login,
  forgot-password — desktop + mobile, anonymous/empty states only).
- Copies of the canonical design docs (`design.md`, both DEV-HANDOFFs,
  `nocturne-reference.html`, tailwind config).
- 19 `rico/` + 5 `shared/` React components, verified **byte-identical to
  production** (`apps/web/components/ui/rico/`,
  `apps/web/components/shared/`) at review time — a snapshot of the live UI,
  not Lovable prototype code.

It originally arrived bundled inside the (rejected, stale) C2
privacy/refund handoff, but its content is unrelated to privacy/refund
pages — it was relocated here under its own name so it isn't buried under a
misleading folder.

## How it may be used

- As **design context/inspiration** for future UI work — e.g., command UX,
  issue #917 (persistent workspace cards), and similar Nocturne-surface work.
- The token/interaction/component notes are useful reading before scoping
  any authenticated-workspace UI change.

## What it is NOT

- **Not an approved production implementation.** Nothing in the zip is a
  work order; the `05-implementation-sequence.md` inside is a proposal, not
  an approved plan.
- **Not code to copy directly into production.** The component files are a
  point-in-time snapshot for reference; production source in `apps/web/`
  remains the only source of truth and will drift from this snapshot.
- **Not Lovable prototype code**, but the same rule applies as if it were:
  do not extract it into `apps/web/`, do not move it into
  `apps/web/app/design-gallery/`, and do not implement from it without a
  separately scoped, owner-approved task.

## Handling rules

- Keep the zip archived here; extract only to a scratch location for
  reading, never into repo source paths.
- Any future work that consumes this reference must be its own scoped,
  approved PR referencing this folder — this README grants no
  implementation approval by itself.
