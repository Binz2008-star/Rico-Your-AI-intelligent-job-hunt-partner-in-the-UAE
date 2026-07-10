# C8 — Rico Command Surface: Implementation Proposal

**Status:** Proposal (docs-only). **Not an approval to build.**
**Date:** 2026-07-08
**Author:** Claude (GitHub session)
**Surface:** `/command` (authenticated workspace chat / job-hunt session)
**Related decisions:** DEC-20260708-004 (Lovable quarantine), DEC-20260708-003
(Atelier=marketing / Nocturne=workspace), DEC-20260708-002 (action routing
contract), DEC-20260708-001 (prototype = design reference), DEC-20260707-001
(phased architecture; verify-first). Execution authority remains the production
hardening audit gate (`AI_WORKSPACE/AUDITS/2026-07-08-*`).

---

## 0. Purpose & hard non-goals

**Purpose.** Give the owner a decision-ready comparison for *eventually* building
the dynamic "Rico command" experience in production — the thinking states, plan
checklist, tool-activity timeline (THINK → PLAN → DONE/FAIL → RUN), streaming,
explainable match cards, and shortlist rail seen in the Lovable prototype's
command view.

**Hard non-goals (this document changes nothing):**
- No code, no branch except this docs-only one, no implementation.
- **C8 stays deferred.** This does not reprioritize it.
- **Workspace/command stays Nocturne** (DEC-20260708-003 not overridden).
- No Lovable/TanStack code copied; no streaming/tool execution ported from Lovable.
- No backend, prompt, model, provider, persistence, or agent-runtime changes.

## 1. What the Lovable command view actually is

A **mock/demo** — the prototype screenshot is badged `SAMPLE DATA · DEMO`. The
THINK/PLAN/DONE/FAIL/RUN steps, the `read_profile` / `search_jobs` /
`enrich_company` (FAIL) / `score_matches` tool calls, and the scores are
**hardcoded** in the prototype; there is no real backend behind them. It *looks*
dynamic; it does not do the work.

**What is valuable = the UX pattern**, not the implementation:
agentic transparency (visible thinking, an explicit plan, live tool activity,
*honest* failures), explainable match reasoning, and a persistent shortlist.
Everything below is about reproducing that pattern **safely and for real** in the
production Next.js + FastAPI + Neon stack — not copying the prototype.

## 2. Visual target options

### Option A — Nocturne command evolution *(default; honors DEC-20260708-003)*
Keep the dark Nocturne workspace identity and add the agentic-transparency UI
(thinking indicator, plan checklist, tool timeline, match/plate cards, shortlist)
using existing Nocturne tokens.
- **Pros:** no ratified-decision reversal; consistent with the authenticated app
  and `/command`'s existing dark-lock; smallest design blast radius; lower risk.
- **Cons:** visually diverges from the Atelier marketing landing (accepted
  trade-off in DEC-20260708-003).

### Option B — Atelier-light command override
Re-theme `/command` (and, for consistency, the wider authenticated shell) to the
Atelier-light look matching the Lovable prototype.
- **Requires:** formally revising DEC-20260708-003 (workspace → Atelier);
  re-theming the whole authenticated shell or accepting a jarring
  marketing↔workspace boundary; solving AA contrast for a **dense, data-heavy
  UI on light paper** (harder than legal prose).
- **Pros:** visual unity with the marketing site; matches what the owner saw.
- **Cons:** reverses a ratified decision; blast radius is the entire workspace,
  not just `/command`; higher design + accessibility risk; larger effort.

> **Recommendation:** default to **A** unless the owner explicitly chooses **B**
> as a separate, deliberate design decision (Gate 1).

## 3. UI-only scope (reproducible without backend changes)

These are presentational and can be built/reviewed in an isolated preview
(`/design-gallery` or a `/preview` route), driven by **clearly-labelled sample
data**:
- Thinking indicator; plan checklist (visual step states).
- Tool-activity timeline layout (THINK/PLAN/DONE/FAIL/RUN rows).
- Explainable match / "plate" cards; shortlist rail; session list; composer with
  `/commands`.

**Constraint (DEC-20260708-002):** a mock version must **never** ship to the live
`/command` — fake tool activity / fake persistence in production is forbidden. UI
-only work is for design preview, not the live surface.

## 4. What requires real backend wiring

| Capability | Existing Rico component to reuse (verify-first, DEC-20260707-001) |
| --- | --- |
| Streaming responses | `src/api/routers/rico_chat.py`, `src/rico_chat_api.py` (today: single JSON response) |
| Tool execution + progress events | `src/agent/runtime.py` (`agent_runtime`), `src/agent/registry/tool_registry.py` |
| Job search / candidates | `src/api/routers/jobs.py`, JSearch/provider layer |
| Match scoring + reasons | scoring pipeline (`src/run_daily.py` / repo layer) |
| Shortlist / sessions / apply-link context | `user_job_context_repo.py`, migrations 018–022, Neon |

**Reuse, do not rebuild.** DEC-20260707-001 says the persistence layer already
exists; C8 must verify the specific gap first, then ship the smallest safe fix —
not a second implementation.

## 5. Streaming requirements

- **Today:** `/api/v1/rico/chat` returns one response; there is no token/event
  stream. Live thinking/tool activity needs a **structured agent-event stream**
  (SSE or chunked) plus an event schema, e.g.:
  `think` · `plan` · `plan_step` · `tool_start` · `tool_result` · `tool_fail`
  · `token` · `done`.
- **Provider constraint:** the routing chain is DeepSeek → HuggingFace →
  keyword/templated fallback. Streaming support varies by provider; the keyword
  fallback **cannot** stream. A graceful **non-streaming fallback** is mandatory
  (never leave the user with a frozen "Rico is working").
- **Backend change** — real work; **out of scope now** (Gate 3 to approve).

## 6. Safety pipeline requirements (DEC-20260708-002)

- Every actionable item surfaced (apply / save / skip / mark-applied) MUST route:
  **Intent → `rico_safety` policy → `agent_runtime.handle_action()` → persistence
  → confirmation**, idempotent + audit-logged, honoring
  `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true`.
- **No** frontend-only approval, **no** `alert()`-style actions, **no** local
  state pretending persistence.
- The tool-activity display must reflect **real server-side execution**, not a
  client-side simulation. Honest failure states (like the demo's
  `enrich_company` timeout) must be real provider errors, surfaced truthfully.

## 7. Persistence requirements

- Sessions/threads (the left "sessions" list), shortlist, and job context (apply
  links) are **Neon-backed**. `user_job_context_repo.py` + migrations already
  exist — **verify-first**, do not add a parallel store.
- Public/guest vs authenticated isolation must hold (public sessions prefixed;
  no collision with JWT users), per current `/chat` rules.

## 8. Tool execution requirements

- Real tools run through `tool_registry` + `agent_runtime`; surfacing progress
  requires the runtime to **emit structured events** (a new capability, additive).
- Idempotency key scheme (`MD5(user_id:action:job_key)`) and the audit-log schema
  must not change (Agent Runtime Rules).

## 9. Evaluation requirements

Before any live enablement:
- Eval harness for: chat quality, intent routing accuracy, **safety-gate coverage**
  (no action bypasses approval), streaming + fallback correctness, bilingual
  EN/AR parity, latency budget, and honest-failure rendering.
- **Synthetic users + synthetic data only** (product generalization rule). No
  live-user smoke or mutation without explicit owner approval (Gate 5).

## 10. Risk table

| # | Risk | Severity | Mitigation |
| - | ---- | -------- | ---------- |
| 1 | Streaming infra is new backend surface area | High | Additive event endpoint behind a flag; non-stream fallback; verify-first |
| 2 | Provider streaming gaps (HF/keyword can't stream) | Med | Mandatory graceful fallback; per-provider capability check |
| 3 | Safety bypass via "quick" frontend actions | **Critical** | Enforce DEC-20260708-002 pipeline; reject any client-only action path in review |
| 4 | Mock/sample data leaking to live `/command` | High | Sample UI only in `/design-gallery`/preview; never on live route |
| 5 | Option B light-mode contrast on dense data | Med-High | AA audit; default to Option A |
| 6 | Scope creep to the whole workspace (Option B) | High | Keep C8 to `/command`; treat shell re-theme as a separate decision |
| 7 | Latency / "frozen working" UX | Med | Timeouts, retry/stop control, honest failure copy |
| 8 | Neon load from sessions/shortlist writes | Med | Reuse existing repos/migrations; verify indexes before adding |
| 9 | `/command` is the most sensitive live surface | High | Feature-flagged staged rollout; owner smoke before enable |

## 11. Phased PR sequence *(only when C8 is greenlit — each small, reviewed, flag-gated)*

- **C8.0 — Decision & design lock (docs):** owner picks A vs B; ratify/revise
  DEC-20260708-003; freeze the event schema.
- **C8.1 — Command UI in preview (no prod):** build the chosen-theme agentic UI
  in `/design-gallery`/`/preview` with clearly-labelled sample data. No live
  route touched.
- **C8.2 — Streaming contract (backend, flagged):** add the agent-event schema +
  streaming endpoint behind a server flag; no UI wiring yet.
- **C8.3 — Wire UI to real events:** replace sample data with the real stream;
  enforce the full safety pipeline; non-stream fallback verified.
- **C8.4 — Persistence (sessions/shortlist/context):** Neon-backed, reusing
  existing repos; verify-first.
- **C8.5 — Evals + bilingual + a11y + reduced-motion.**
- **C8.6 — Staged rollout:** behind `NEXT_PUBLIC_RICO_COMMAND_V2` (+ server
  flag) → owner smoke on synthetic data → gradual enable.

## 12. Rollback plan

- Every phase is **feature-flagged** (client `NEXT_PUBLIC_RICO_COMMAND_V2` +
  server capability flag). Instant disable → current `/command`, no redeploy.
- Vercel (frontend) and Render (backend) instant-rollback available.
- **No destructive/irreversible DB migration** without a reversible plan; migrations
  reviewed under Neon migration-safety rules.
- Because C8.1 is preview-only and C8.2/C8.3 are flag-gated, the live `/command`
  is never at risk until the final enable step.

## 13. Explicit owner decision gates

- **Gate 1 — Look:** Option A (Nocturne) *[default]* vs Option B (Atelier-light +
  revise DEC-20260708-003).
- **Gate 2 — Priority:** reprioritize C8 now vs keep deferred until after
  C3/C4 + the hardening-audit priorities *[current decision: keep deferred].*
- **Gate 3 — Backend:** approve streaming + agent-event work (touches backend —
  currently forbidden).
- **Gate 4 — Per-PR:** approve each C8.x PR (all Draft-first, reviewed).
- **Gate 5 — Live/data:** approve any live-user smoke or production data
  mutation (else synthetic-only).

## 14. Recommendation

Keep **C8 deferred** and **Nocturne (Option A)** as the default. Treat the Lovable
command view as **design reference only**. Revisit after the current safer
sequence (C3 landing review → C4 marketing/support, if approved) and the
production-hardening-audit priorities. When C8 is greenlit, start at **C8.0/C8.1
(design-only, preview)** — the cheapest, fully reversible first step — and do not
touch the live `/command` until the flag-gated final enable with owner smoke.

This delivers the experience the owner paid to design, **rebuilt natively and
safely**, without letting a mock prototype pull Rico into a risky rewrite.
