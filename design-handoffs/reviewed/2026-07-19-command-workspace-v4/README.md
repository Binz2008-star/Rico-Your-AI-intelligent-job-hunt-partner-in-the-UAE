# Command Workspace v4 — reviewed design handoff (2026-07-19)

**Status: frozen approved design reference.** `Rico Command Workspace v4.dc.html`
is a **frozen approved design reference** for the authenticated Rico workspace
(Career OS direction). It was approved by the owner on 2026-07-19 with a full
verification PASS matrix (default-open policy, mode isolation, keyboard
contract, responsive contracts, Career Health overflow, technical validation —
no console errors, no malformed markup, no duplicate IDs).

**This handoff adopts a reference and records boundaries. It does not
authorize any implementation work.** Every implementation PR requires its own
owner approval at cut time, and **no implementation tasks are created in
advance** — each future PR creates its own task entry when (and only when) the
owner green-lights that PR.

## Provenance

| Artifact | Identity | Status |
| --- | --- | --- |
| `Rico Command Workspace v4.dc.html` | 1,859 lines · 165,606 bytes · owner's machine (session upload only) | **Canonical reference — intentionally NOT committed** (same policy as the 2026-07-16 obsidian-v4 raw ZIP: the raw artifact stays out of Git history; this README is the committed record) |
| Owner handoff note (2026-07-19) | acceptance contracts + known limitations, quoted below | Canonical |
| Version trail | v1 → v2 (owner 10-point revision) → v3 (Career OS refinement) → **v4 frozen** | Preserved on the owner's machine, untouched |

The prototype is design-only: **no persistence, no backend, no fetch/XHR, no
database or schema requirements, no Career Memory integration** (its
"Long-term memory" tab is illustrative UI only), and no real employer names —
all scenarios are sample data.

## What the reference shows (regions)

Modes rail (logo · goal-mini · 7 modes) · main workspace with per-mode bodies
(Overview: goal panel + milestones, career health, activity timeline,
suggested next actions · Search: query summary, progressive job cards with
reason chips, recommendation, actions row, composer + slash panel ·
Applications/Documents/Interview/Learning stubs · Activity full timeline) ·
Ask Rico copilot panel (per-mode transcripts) · context panel (Context/Memory
tabs, source labels) · responsive drawers (rail drawer, context bottom sheet,
copilot sheet, floating launcher) · design-states drawer (engineering review
affordance — not a production surface).

## Engineering acceptance contracts (owner-approved, recorded verbatim in substance)

- **Copilot default-open policy:** Overview may auto-open the copilot only at
  ≥1280px, only while the user has expressed no preference for that mode; all
  other modes default closed; an explicit user open/close is preserved per
  mode and never overridden; no auto-open below 1280px.
- **Mode-scoped conversations:** each mode owns its own transcript; header
  shows "Scoped to {mode}"; profile knowledge is global, only the transcript
  is mode-scoped; no cross-mode transcript mixing.
- **Keyboard:** in the prototype, Ctrl/Cmd+K toggles Ask Rico only when focus
  is outside editable elements; Escape closes the copilot first, then the next
  active overlay. **See Boundaries: production Ctrl/Cmd+K behavior is NOT
  changed by this adoption.**
- **Responsive:** ≥1600 all four columns may sit inline; 1280–1599 context and
  copilot are mutually exclusive inline; <1280 context/copilot are
  overlay/drawer only; rail inline down to 900, drawer below; main column
  `minmax(320px, 1fr)`; no horizontal overflow at
  1920/1600/1599/1280/1279/1024/768/390.
- **Trust & action vocabulary:** three message classes — Information (plain),
  Recommendation (accent rule, no buttons), Action (card with explicit state:
  Available / Confirmation required / Working / Completed / Failed /
  Unavailable); Rico never implies execution without user confirmation; drafts
  only. Context sources: Verified profile fact / User preference / Observed
  behavior / External job data / Rico inference — inference is never shown as
  verified.

## Known limitations (owner-logged; validate on device when implementing)

1. Width tests were simulated via `innerWidth` override; real-device rounding
   may differ by a few px.
2. Composer uses `env(safe-area-inset-bottom)` + sticky positioning; no
   `visualViewport` handling — verify virtual keyboards on iOS/Android.
3. Resizing wide→desktop with both panels open keeps copilot inline and drops
   context to a drawer — contract-compliant but deserves a UX pass.
4. Rail titles truncate with ellipsis; not stress-tested beyond ~60-char
   Arabic titles.
5. Profile is not in the v4 mode rail; `Rico Profile.dc.html` remains a
   separate surface.

## Boundaries (binding for any future implementation)

1. **Modes map to existing routes.** Overview → `/dashboard`, Search →
   `/command`, Applications → `/applications`, Documents → `/upload`. **Do not
   build a single-page mode switcher** — the multi-route architecture on the
   shared `WorkspaceShell` (DEC-20260717-001) stands.
2. **Production Ctrl/Cmd+K behavior remains unchanged**: it focuses the
   `/command` composer (`app/command/page.tsx`, `CommandComposer.tsx`). The
   prototype's ⌘K-toggles-copilot contract is NOT adopted.
3. **Production tokens only**: `WORKSPACE_THEME`
   (`apps/web/components/workspace/theme.ts`) and the `atelier-kit`
   tokens/fonts are canonical. The reference's hex values and Google-Fonts
   links are composition guidance, never a token source.
4. **Existing `WorkspaceShell` only** — no parallel shell implementations.
5. **Deferred until real capabilities exist — do not build:** Memory tab /
   context persistence (Career Memory Engine is Draft #1025, flag OFF,
   frozen), Interview prep mode, Learning mode, Activity timeline/route
   (requires an owner-approved read-only endpoint first), **embedded Copilot
   surfaces** (the former multi-route/dashboard copilot direction is HOLD;
   the approved replacement is a simple Ask Rico deep-link to `/command`
   using existing routing), and **per-mode transcripts / multi-session
   history** (documented backend capability gap — the frontend must never
   simulate it).
6. **No fake states:** any reference block without a real production data
   source is omitted, not stubbed (per the migration program's binding rules
   and DEC-20260710-002).
7. **The `/command` design freeze remains active**
   (`AI_WORKSPACE/ATELIER_FULL_SITE_MIGRATION.md`, program authority
   section). Every future `/command` PR requires its own separate,
   recorded, one-PR-only freeze lift naming that PR; lifts are never
   blanket, never reusable, and expire when that PR merges or closes.

## Explicitly NOT canonical

The prototype's SPA mode-switcher architecture, its localStorage-free
in-memory session model, its Google-Fonts loading, its sample data, its
design-states drawer as a production surface, and its ⌘K keyboard contract.
The 2026-07-16 obsidian-v4 handoff (dark acid-lime) remains historical
reference only — superseded by DEC-20260716-001 (Atelier V3 product-wide).

## Related records

- Decision: `AI_WORKSPACE/DECISIONS.md` → DEC-20260719-002
- Governance task: `AI_WORKSPACE/TASKS.md` → TASK-20260719-006
- Program inventory: `AI_WORKSPACE/ATELIER_FULL_SITE_MIGRATION.md`
