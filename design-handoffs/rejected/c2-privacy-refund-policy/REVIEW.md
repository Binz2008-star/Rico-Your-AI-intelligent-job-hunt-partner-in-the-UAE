# Review — C2 Privacy/Refund Implementation Brief

**Classification:** Rejected — stale/duplicate
**Date:** 2026-07-09
**Reviewer decision by:** Roben (owner)
**State transition:** `incoming/` → `rejected/` (brief only; the accompanying
`rico-design-reference.zip` was general reference material unrelated to this
brief and was relocated to `design-handoffs/reviewed/rico-design-reference/`)

## Decision

Rejected as **stale/duplicate**. The brief's entire scope — add `/privacy` and
`/refund-policy` routes mirroring `/terms`, plus footer links — already shipped
before this handoff arrived:

- **PR #895 — "C2 — Atelier /privacy + /refund-policy islands" (commit
  `277260c`)** delivered both routes as Atelier light-first islands mirroring
  the `/terms` (C1) pattern: `apps/web/app/privacy/` and
  `apps/web/app/refund-policy/`, with SEO metadata, EN/AR bilingual copy, and
  self-contained RTL.
- Footer links to both pages already exist in `LandingPage.tsx` and
  `LandingPageNocturne.tsx`.

**No production implementation is required from this brief.**

## Naming note

The brief uses the bare `C2` label. Per **DEC-20260709-005**
(`AI_WORKSPACE/DECISIONS.md`), bare `C#` labels are retired as implementation
identifiers due to a naming collision across the Atelier design phases, PR
self-labels, and security-audit finding IDs. Do not use bare `C#` labels for
future work items.

## Follow-up filed separately (not part of this rejection)

The brief required all legal/business facts to be `TODO: legal review` markers
behind a visible draft banner. The *shipped* pages instead contain actual copy
("Last updated: June 2026") with no markers or banner. Whether that copy
received legal review is an open owner/legal question, tracked as its own
issue — it is a legal-review task, not a design implementation task, and the
shipped pages are not to be changed from this handoff.

## History

The original brief is preserved unmodified in this folder as `README.md`.
