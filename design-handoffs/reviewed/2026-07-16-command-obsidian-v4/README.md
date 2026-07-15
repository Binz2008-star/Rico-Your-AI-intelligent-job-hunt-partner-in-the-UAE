# Command Obsidian v4 — reviewed design handoff (2026-07-16)

**Scope: `/command` only.** Owner-approved executive design correction
(2026-07-16): the production `/command` route must reach visual parity with
the dark acid-lime "Obsidian" three-column operator console shown in the
owner's recording. This is a **route-specific exception** to the Atelier
paper/ink/sun-red identity documented in `design-handoffs/README.md` and used
by the rest of the workspace. It is **not** a global Rico identity
replacement: `/profile`, `/settings`, `/applications`, `/upload`, `/queue`,
auth, and marketing surfaces keep their current approved design language.

## Provenance

| Artifact | Location | Status |
| --- | --- | --- |
| Recording `Recording 2026-07-16 004205.mp4` (35 s, 1574×1290, EN desktop) | Owner's machine, `C:\Users\loyal\Videos\RICO ADD\` | **Canonical #1** — key frames extracted below |
| `Remix of Career Compass AI.zip` (16.8 MB Lovable prototype export) | `design-handoffs/incoming/` (raw ZIP, **intentionally uncommitted** — do not add to Git history, do not delete the owner's local copy) | **Canonical #2** — only the four files listed in `canonical-files.md` |
| Owner visual acceptance | recording-based parity gate | **Canonical #3** — final authority |

## Canonical source priority

1. The recording (`recording-*.jpg` frames in `screenshots/`).
2. ZIP files: `src/routes/rico.tsx`, the dark "Obsidian night" system in
   `src/styles.css`, `src/lib/rico-content.ts`, `src/lib/i18n.tsx`.
3. Owner visual acceptance.

**Explicitly NOT canonical:** `src/routes/app.command.tsx` in the ZIP, old
cream/paper Atelier screenshots, old orange/gold Nocturne screenshots,
`design-reference/command-concept/*`, and every prototype backend/API/server
file. The archive carries conflicting historical directions; the dark
three-column `/rico` prototype in the recording is the only target.

## Architecture contract (what may NOT be ported)

Rico production stays Next.js with its existing auth, chat API, streaming,
message persistence, attachments, CV analysis, job matching, application
tracking, safety/permissions, backend, and Neon data. Do not port: TanStack
route architecture, prototype localStorage business state, Lovable AI
Gateway, prototype server functions, mock job data, fake auth, or demo
behavior. Port **visual composition and safe interaction patterns only**.
Route-scope all new design variables under `/command`; do not modify global
`:root`, `body::before`, `body::after`, or unrelated pages.

## Status correction (recorded per owner directives, incl. 2026-07-16 second pass)

`/command` is **not** "Fully Atelier" and not visually complete:

- functional migration slices 4a–4e (#1028, #1032, #1034, #1037, #1038): **merged**
- current Rico business behavior: **preserved**
- owner-approved Obsidian visual parity: **pending**
- Command migration completion: **OPEN until the recording-based parity gate passes**
- C1 visual shell: **implemented in Draft (#1043)** — a visual shell is NOT the
  owner-approved Command experience
- C1 functional no-regression evidence: **partial** (mounted-component
  interactive suite for send/stream/stop/retry/new-chat/clear-history/toggles;
  the 19-flow acceptance matrix in `parity-audit.md` remains OPEN)
- Sessions rail parity: truthful single-conversation rail shipped;
  **multi-session history = separately scoped backend capability gap**
- transcript interaction parity: **missing** (C2 adapter)
- canonical flow parity: **not implemented**
- PR #1043: **Draft — not ready for merge**

Closed PR #1042 is superseded; it must not be reopened or reused.

**Evidence rule:** every synthetic screenshot in `screenshots/` is stamped
`MOCKED VISUAL EVIDENCE — NOT FUNCTIONAL SMOKE`. Those images prove layout
only — never chat, action, upload, or session behavior. Functional claims come
from `apps/web/__tests__/command-obsidian-noregression.test.tsx` (real mounted
CommandPage over network-boundary fixtures) and the owner's real smoke.

## Contents

- `canonical-files.md` — reviewed inventory of the canonical ZIP files
- `parity-audit.md` — Phase-1 component-level mismatch matrix
  (production `/command` @ `cafe340a` vs recording/canonical source)
- `risks.md` — behavior risks and mitigations for the port
- `c2-adapter-interfaces.md` — C2 real event/presentation adapter contracts
  (production truth → canonical transcript; anti-fabrication rules)
- multi-session architecture proposal:
  `AI_WORKSPACE/ADR/ADR-002-command-multi-session-history.md` (PROPOSED —
  separate approval required; never implemented inside design slices)
- `screenshots/` — extracted recording frames (canonical) and production
  evidence used for the side-by-side gate
