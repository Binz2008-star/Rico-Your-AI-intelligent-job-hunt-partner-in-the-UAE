# Risks — porting the Obsidian console onto production `/command`

## R1 — Prototype architecture leakage (HIGH if ignored, prevented by contract)
The ZIP is a TanStack Start + Lovable prototype with localStorage business
state, a scripted demo runner, mock jobs, and its own AI gateway. **None of it
may cross into production.** Only visual composition and safe interaction
patterns are ported. Guard: every slice PR states "no backend, Neon, billing,
Paddle, or Profile changes"; reviewers reject any import from the ZIP.

## R2 — Fabricated intelligence (HIGH)
The recording shows PLAN checklists, tool rows (`read_profile`, `search_jobs`),
FAIL/backfill notes, and a SIGNAL ops feed. Production Rico does not emit
those step events today. Porting the *presentation* must not fabricate fake
progress: only real states (`thinking`, `operationState`, streaming, real
errors, real matches/applications) may drive these components. Richer step
telemetry is a separate backend program, not a design slice.

## R3 — Breaking preserved behavior (MEDIUM)
`/command` carries live business surfaces: streaming chat, CV upload,
permission/approval cards, apply/save/skip actions (via `agent_runtime`),
quotas, public/guest session isolation. Slices are presentation-only wrappers;
all handlers, data contracts, and test IDs stay. Full command test set +
`npm run build` gate every slice.

## R4 — Global style bleed (MEDIUM)
Prototype styles live on global `body::before/::after`, `:root`, `.dark`.
Porting those globally would repaint the whole product. All Obsidian variables
are route-scoped under the `/command` chrome (theme-context override + scoped
elements). `/profile`, `/settings`, auth, marketing and the global Nocturne
theme remain untouched. The workspace-theme *interface* is shared — the
override must be passed only by `/command`.

## R5 — Identity fork confusion (MEDIUM)
Rico now intentionally runs two visual languages: Atelier paper/ink/red
(workspace + marketing) and Obsidian lime (`/command` only, owner-approved
exception). Recorded here and in `AI_WORKSPACE/ATELIER_FULL_SITE_MIGRATION.md`
to stop future agents from "unifying" in either direction without an owner
decision.

## R6 — Public/guest surface divergence (LOW)
The recording shows the authenticated-style console. The public `/command`
surface keeps its approved reference chrome until the owner decides whether
Obsidian applies there too. Slices must keep the public branch byte-stable
unless a slice explicitly scopes it.

## R7 — Sessions rail is a product gap (LOW, visual; OPEN, product)
Canonical left rail lists chat sessions; Rico has a single conversation per
user today. C1 frames the rail in Obsidian with the existing workspace nav;
a real sessions feature is a product decision outside this design stream.

## R8 — RTL/Arabic regressions (LOW)
Existing EN/AR + RTL behavior is covered by tests; every slice re-runs them
and ships EN + AR screenshots (desktop + mobile).

## Rollback
Each slice is an isolated PR; revert restores the previous approved state.
C1 confines the repaint to the palette override + new shell component — a
single revert returns `/command` to the WorkspaceShell island exactly as
merged in 4a–4e.
