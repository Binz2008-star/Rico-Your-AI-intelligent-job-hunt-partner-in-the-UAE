# Decisions

Use this file for decisions that affect product behavior, architecture, AI workflow, release policy, or contributor workflow.

## Decision template

```md
### DEC-YYYYMMDD-001 — <title>

Status: accepted | superseded | proposed
Date: YYYY-MM-DD
Owner: <name/tool>
Related task: TASK-YYYYMMDD-001

#### Context
<why this decision is needed>

#### Decision
<what was decided>

#### Consequences
- Positive:
- Negative/trade-off:

#### Follow-up
- [ ]
```

## Accepted decisions

### DEC-20260710-002 — `/design-preview` is the approved production target: shape + content + flows

Status: accepted
Date: 2026-07-10
Owner: Roben (clarified in-session; recorded by Claude)
Related task: TASK-20260710-003 (revised scope)

#### Context
`DEC-20260710-001` framed the Atelier rollout as "visual-only, below-the-fold first." During
Phase 1 (#933) the owner clarified that this under-scoped the goal. The approved production
direction is to **reproduce the full Rico `/design-preview` package** — same visual language,
same sections, same content structure, same page flows, same desktop/mobile behavior, same
EN/AR coverage where applicable — and, where a section/page does not yet exist in production,
to design and build it to match the package.

The authoritative reference is the in-repo `/design-preview` source (live at
`https://ricohunt.com/design-preview`), catalogued from repo evidence in
`HANDOFFS/2026-07-10-design-preview-target-inventory.md`: 53 reference PNGs in
`apps/web/public/design-preview/`, the 6-group tile inventory in
`apps/web/app/design-preview/_client.tsx`, and the live previews `/design-gallery` and
`/rico-preview`. The uploaded design-preview PDF is **not present in the agent environment**;
per owner instruction the repo source is used as authoritative in its place.

#### Decision
1. **`/design-preview` is the approved production target for shape, content, and flows** — not
   merely palette/typography. This **expands** `DEC-20260710-001`; the phased, per-route,
   owner-gated delivery model is retained.
2. **Scope of the package:** public landing; auth (login/signup/forgot/reset/verify);
   onboarding; authenticated workspace (dashboard/profile/settings/applications/upload/pricing);
   support + legal; and states (empty/loading/error/mobile/RTL/light-dark). Three shells apply
   (marketing masthead, minimal auth header, workspace left sidebar).
3. **Still excluded / gated, unchanged from prior decisions:**
   - `/command` (and any `/rico` route) — core product behavior; requires its **own DEC**.
   - No backend/auth/billing/Neon/schema changes unless separately approved (e.g. the auth
     "Continue with Google" button and the support contact-form endpoint are **omitted or
     gated**, not built, without approval).
   - Legal copy (`/privacy`, `/refund-policy`, `/terms`) preserved verbatim unless legal review
     approves changes.
   - No shadcn/ui adoption without its own DEC — the workspace reference screens must be rebuilt
     on the existing Tailwind stack.
   - No fake live actions; preview/sample data must be wired to existing endpoints or clearly
     labelled/disabled.
4. **Delivery:** small per-route PRs, one objective each, owner **visual approval before every
   merge**, single-revert rollback. Recommended order (safest first): PR 0 shared Atelier UI
   kit → PR 1 public landing (full parity) → PR 2 auth → PR 3 support/legal → PR 4 onboarding
   (after the hybrid-state fix) → PR 5 workspace read surfaces → PR 6 workspace action surfaces
   (billing-gated) → PR 7 command/chat (own DEC).
5. **PR #933** (landing below-the-fold cream) does **not** merge unless it becomes full
   public-landing parity (masthead + hero + content), which requires the owner to (a) unfreeze
   the landing hero (currently under the #871 freeze) and (b) rule on draft #899 (hero polish).
   Otherwise #933 is kept as a draft reference only.

#### Consequences
- Positive: one canonical, evidence-based target removes the re-interpretation risk seen in
  #933's first two attempts; scope, order, and gates are explicit.
- Negative/trade-off: substantially larger than a visual polish — includes new shells and
  screens; workspace surfaces need shadcn-free rebuilds; several screens surface
  backend/billing/OAuth decisions that are deferred, not resolved, by this decision.

#### Follow-up (owner-gated decisions before implementation)
- [ ] Unfreeze the landing hero for PR 1, and decide #899's fate.
- [ ] Choose canonical onboarding flow: reference intent-flow vs production CV-first.
- [ ] Adopt the reference workspace left-sidebar (Shell C) in production?
- [ ] Support contact form + auth Google button: omit (recommended) or greenlight as separate
      backend projects.
- [ ] Approve starting with PR 0 (shared Atelier UI kit).

### DEC-20260710-001 — Atelier production rollout, phases 1–6 (visual-only, per-phase owner gate)

Status: accepted
Date: 2026-07-10
Owner: Roben (plan + audit verdict accepted in-session; recorded by Claude)
Related task: TASK-20260710-003 (Phase 1); TASK-20260710-004..007 (audit P2 items)

#### Context
The owner reviewed and approved the `/design-preview` consolidation hub (#929, merged,
production-verified) as the intended Rico Atelier direction, and accepted a phased
production implementation plan. A full read-only system audit (2026-07-10, on `main`
`db3d722`) returned **YELLOW — acceptable: zero P0/P1 blockers**, production stable
(Render serving `main` exactly, all public routes healthy, chat EN/AR correct, billing in
safe manual/WhatsApp mode, no security exposures). Full audit record:
`HANDOFFS/2026-07-10-system-audit-phase0-gate.md`.

#### Decision
1. **Phased visual-only rollout** of the approved Atelier direction, one route group per
   small PR, logic/handlers/endpoints frozen in every phase:
   - Phase 1: public landing static sections (`/`, about/contact/FAQ statics) — below the
     fold first, hero as its own PR.
   - Phase 2: legal/support alignment (`/terms`, support surface; `/privacy` and
     `/refund-policy` are already Atelier-live).
   - Phase 3: auth visual shells (`/login`, `/signup`, `/forgot-password`,
     `/reset-password`, `/verify-email`).
   - Phase 4: onboarding shell (`/onboarding` steps).
   - Phase 5: workspace read surfaces (`/dashboard`, `/profile`, `/settings`).
   - Phase 6: workspace action surfaces (`/flow`/applications, `/upload`;
     `/subscription` additionally gated on a separate billing DEC).
2. **Scope of amendment**: phases 1–2 are consistent with `DEC-20260708-003` (Atelier
   already owns marketing). For phases 3–6 this DEC amends `DEC-20260709-006`: Atelier
   workspace surfaces may migrate to production **visually, per phase, with explicit
   per-PR owner approval** — logic unchanged.
3. **Explicit exclusions**: `/command` (and any `/rico` route) migration requires its own
   future DEC + approved PR — not authorized here. shadcn/ui adoption requires its own
   DEC — conversions must be shadcn-free on the existing stack (Tailwind, lucide-react,
   fonts shipped by #924). No backend/auth/billing/Neon/schema change is authorized by
   this DEC. No real data/action wiring beyond what already exists.
4. **Phase gates** (from the 2026-07-10 audit):
   - **Phase 3 gate**: the vitest `next/navigation` router-mock baseline must be fixed
     (TASK-20260710-006) AND an authenticated production smoke path must exist —
     owner-run or via a provisioned synthetic smoke account (TASK-20260710-007).
   - **Phase 4 gate**: the `/onboarding` hybrid dead-UI state must be resolved first
     (TASK-20260710-005, per DEC-20260628-001).
5. **Per-phase acceptance (uniform)**: build passes; no new test failures vs the known
   baseline; diff shows zero logic changes; EN + AR RTL verified; mobile verified;
   owner approves the phase PR on its Vercel preview before merge; post-merge production
   smoke on affected routes; workspace docs synced.
6. **Rollback (uniform)**: revert the phase PR → Vercel auto-redeploy → re-run the
   phase's smoke set. Every phase must remain single-PR revertible; each phase deletes
   the Nocturne code it replaces (No Dead UI rule) so reverts restore it cleanly.
7. **Stop conditions**: any new P0/P1 mid-rollout; a failed post-merge smoke; a phase PR
   touching backend/auth/billing/Neon/schema; or an unsatisfiable phase gate.

#### Consequences
- Positive: the approved direction ships incrementally with bounded blast radius, explicit
  gates, and one-revert rollback at every step.
- Negative/trade-off: Nocturne and Atelier coexist in the workspace during phases 3–6
  (accepted in DEC-20260709-006); reference screens needing shadcn must be rewritten
  shadcn-free, which is slower.

#### Follow-up
- [ ] Phase 1 PR (landing below-the-fold statics) — TASK-20260710-003; requires this DEC
      merged first (owner instruction 2026-07-10: migration starts only after Phase 0 docs merge).
- [ ] Future `/command` migration DEC (not started).
- [ ] Billing DEC before any `/subscription` visual conversion implies purchasable plans.

### DEC-20260709-006 — Atelier Console is the candidate authenticated-workspace direction (preview/exploration only)

Status: accepted
Date: 2026-07-09
Owner: Roben
Related task: Atelier Console gallery reference (#924)

#### Context
The Lovable "Atelier Console" — a warm editorial paper/ink/sun console with a
matched dark mode, EN/AR + RTL, and a scripted job-hunt workflow — was ported at
high fidelity into an isolated `/design-gallery` reference tab and merged (#924).
The owner has accepted it visually as the intended future direction for the
authenticated Career Workspace surface. `DEC-20260708-003` currently scopes the
authenticated workspace to Nocturne (dark navy/gold/aura) and forbids merging the
Atelier and Nocturne systems. That boundary needs an explicit, bounded amendment
so future workspace *exploration* can proceed — without changing any production
surface. This record captures the direction only; it authorizes no code.

#### Decision
1. **Atelier Console is the candidate design direction for the authenticated
   Career Workspace**, going forward, for preview and exploration only.
2. This **amends / supersedes `DEC-20260708-003` for future workspace-exploration
   work only** — the "authenticated workspace = Nocturne" boundary no longer
   blocks Atelier-based *preview* surfaces. It does **not** retroactively change
   any shipped surface, and it still governs all production surfaces.
3. **The current production workspace is unchanged.** Nocturne remains the
   production design for the authenticated app. **`/command` is not replaced.
   `/rico` is not replaced** (no such production route exists today, and none is
   created by this decision). No production route changes under this decision.
4. **`/design-gallery` remains reference-only** — internal, `noindex`, demo/sample
   data, all actions disabled/reference-only, not linked from production
   navigation.
5. **The next implementation step, if approved separately, is `/rico-preview`** —
   an internal, `noindex`, demo-only preview route reusing the #924 Atelier
   Console. It is **not approved by this decision** and must be its own separately
   approved PR before any code is written.
6. **No real actions are approved** (no real chat send, job search, save, apply,
   follow-up, or CV action), and **no backend/auth/billing/Neon/schema changes are
   approved** by this decision.

#### Consequences
- Positive: records the accepted workspace direction as a single source of truth
  and unblocks *future* exploration without any risky production swap.
- Negative/trade-off: Rico will temporarily carry two workspace design languages
  (Nocturne in production, Atelier in reference/preview) until a future,
  separately-approved migration decision.

#### Follow-up
- [ ] `/rico-preview` preview route — separate approval required before implementation.
- [ ] A production migration of any authenticated surface to Atelier requires its
      own separate DEC + approved PR (this decision does not authorize it).

### DEC-20260709-005 — Retire "C-number" as a product-phase implementation identifier; use explicit names

Status: accepted
Date: 2026-07-09
Owner: Roben (approved); recorded by Claude (GitHub session)
Related task: none (documentation clarification only — no code, no issue closed, no roadmap reprioritization)

#### Context
"C3" is currently used for at least two unrelated things in this workspace, and "C4" for one
undefined placeholder plus one unrelated thing:

- **Atelier design-phase C3** (canonical scope, per `PROJECT_STATUS.md` and the
  `2026-07-08-technical-status.md` / `2026-07-09-board-clean-governance-complete.md` handoffs):
  Atelier V2 migration of `/about`, `/contact`, `/faq`. Its own governing scope **explicitly
  forbids "No landing hero animation."**
- **PR #899**, titled *"C3 — landing hero polish"*: a rotating slogan tail, hand-drawn underline,
  and ambient wash added to the **production landing hero** — open draft, unmerged. This both
  reuses the "C3" label *and* does the exact thing the canonical C3 scope forbids.
- **#198 security-audit finding IDs `C1`–`C4`** (`2026-07-09-security-data-risk-deep-dive.md`,
  `TASKS.md`): a completely unrelated "Critical"-tier finding-severity numbering from the #198
  bug-hunt issue (alongside `H1`–`H6`, `M1`–`M7`, `L1`–`L4`). `C1`/`C2` there are connection-leak
  and maintenance-mode findings, already triaged; `C3`/`C4` there are unrelated, uninvestigated
  findings, deferred as lower-severity.
- **Design-phase "C4"** is referenced repeatedly across three handoffs only as "not started" /
  a forbidden-list filler (`no C4/C8`) — no page, feature, or PR has ever had a defined C4 scope.
- Separately, PR #912 (merged, live) shipped real `/command` chat UX polish (copy, retry,
  new-chat button, keyboard shortcuts, guest-only history) without ever using a "C" label —
  it sits outside this numbering system entirely and is not the C8 rewrite.

Continuing to use bare "C#" labels risks a real production mistake: an agent or reviewer could
treat PR #899 as satisfying the canonical "C3" milestone (`/about`/`/contact`/`/faq`) when it is
an entirely different, still-unapproved change to the production landing hero — or confuse a
design-phase reference with a security-finding reference sharing the same short code.

#### Decision
Retire bare "C#" labels (`C1`–`C8`) as implementation identifiers for new work. Use explicit
names instead:

| Old label | Canonical explicit name | Status |
|---|---|---|
| Design C1 | **Legal Pages Migration — `/terms`** | done, live |
| Design C2 | **Legal Pages Migration — `/privacy` + `/refund-policy`** | done, live |
| Design C3 (canonical scope) | **About/Contact/FAQ Migration** | not started, owner-gated |
| PR #899 ("C3" landing hero) | **Landing Hero Polish** — kept fully separate from About/Contact/FAQ Migration; not renamed by this decision, not started/merged by this decision | open draft, unmerged, held |
| Design "C4" (undefined) | *(retired — no scope was ever assigned; do not reuse until a real scope is defined and named explicitly)* | n/a |
| Design C8 | **Command Streaming Chat Rewrite** | deferred |
| PR #912 (already shipped) | **Command UI Incremental Polish** (retroactive label for board clarity only) | done, live |
| #872 | **Design Gallery Integration — Nocturne Prototype** | held |
| #873 | **Design Gallery Integration — Rico-Alive Prototype** | held |
| #198 findings `C1`–`C4` | Reference as **`#198-C1`…`#198-C4`** (issue-scoped prefix) so a security-finding ID can never again collide with a product-phase name | 2 fixed, 2 not yet investigated |

This decision is documentation clarification only. It does not rename PR #899, does not start
#899/#872/#873/#908/#909/#446 Stage 2, does not close any issue, and does not reprioritize the
roadmap. Existing "C1"/"C2" references to already-shipped work (`/terms`, `/privacy`,
`/refund-policy`) are historical fact and are not being undone — future *new* work should use the
explicit names above instead of minting further "C#" labels.

#### Consequences
- Positive: a design-phase reference and a security-finding reference can no longer collide on
  the same short code; a mislabeled PR (like #899) can be spotted immediately by name instead of
  requiring cross-referencing three handoffs; future planning docs read unambiguously without
  needing this decision as a lookup table.
- Negative/trade-off: existing docs (`PROJECT_STATUS.md`, `CURRENT_STATE.md`, several historical
  handoffs) still contain the old "C#" phrasing for already-shipped work; those are left as
  historical record rather than rewritten, per the Historical-handoffs rule in `MASTER_INDEX.md`.

#### Follow-up
- [ ] When any of About/Contact/FAQ Migration, Landing Hero Polish, Command Streaming Chat
  Rewrite, or Design Gallery Integration is next picked up, use the explicit name above in the
  PR title/branch, not a "C#" label.
- [ ] If #899 is revisited, resolve it under its own explicit name (Landing Hero Polish) —
  independently of whether/when About/Contact/FAQ Migration starts.

### DEC-20260708-004 — Quarantine the Lovable streaming-chat experiment; command chat must be reimplemented in the production repo

Status: accepted
Date: 2026-07-08
Owner: Roben Edwan (owner); recorded by Claude (GitHub session)
Related task: C-series Atelier migration (C8 = `/command`)

#### Context
A streaming command-chat foundation ("PR-1") was built in the Lovable / TanStack
prototype repo (`Binz2008-star/rico-hunt-ai`): a new `src/routes/api/chat.ts`
route wired to the Lovable AI Gateway (`google/gemini-2.5-flash`), a server-only
`LOVABLE_API_KEY`, a rewrite of `src/routes/app.command.tsx`, and added `ai` /
`@ai-sdk/react` / `@ai-sdk/openai-compatible` deps; 13/13 headless smoke passed
under Bun. That repo is under a standing freeze (reference-only): no publish, no
`main` changes, no backend/auth/DB/billing/DNS, and production code must not
depend on Lovable code. The experiment adds a live backend integration and
rewrites the prototype's command surface — outside the freeze. Consistent with
DEC-20260708-001 (prototype sandboxes are design reference requiring production
adaptation, not portable code).

#### Decision
Quarantine the experiment. It must NOT be merged, published, or used as
production code — it is reference research only. The Lovable prototype stays
frozen. Any streaming command chat must be re-implemented in the production Rico
repo (Next.js, `apps/web`) under the approved phased Atelier migration plan,
where `/command` is phase **C8** (last, most sensitive) and is not to be touched
until explicitly reprioritized. The TanStack implementation is not to be ported.

#### Consequences
- Positive: production stays stable and single-sourced in the real repo; the
  Lovable freeze stays intact; no premature or backend-coupled command changes;
  a clear provenance boundary (prototype = reference, real repo = build target).
- Negative/trade-off: the prototype streaming-chat effort is not directly
  reusable; a future C8 re-implements it natively in Next.js rather than porting.

#### Follow-up
- [ ] When C8 is reprioritized, design streaming `/command` in `apps/web`
  (Next.js) from scratch — not a port of the TanStack prototype.
- [ ] Keep the Lovable prototype reference-only; revisit the freeze only on an
  explicit owner decision.

### DEC-20260708-003 — Design-system boundary: Atelier for marketing, Nocturne for the workspace

Status: accepted (amended in part by DEC-20260709-006)
Date: 2026-07-08
Owner: Roben
Related task: design-handoffs review (command-concept-sandbox)

> **Amended by DEC-20260709-006 (2026-07-09):** the "authenticated workspace =
> Nocturne" boundary below is amended for **preview/exploration only** — Atelier
> Console is now the candidate workspace direction behind internal preview
> surfaces (`/design-gallery`, `/rico-preview`). Nocturne remains the current
> **production** workspace design until a separate approved replacement PR. This
> boundary still governs all shipped/production surfaces.

#### Context
Rico now has two live design directions: Atelier V2 (light-first "paper/ink/sun",
piloted on `/terms`) and Nocturne (dark navy/gold/aura, used by `/command` and the
authenticated app). Without an explicit boundary, future work risks trying to merge
them into a single system and eroding both.

#### Decision
Split the two systems by surface, and do not merge them:

- Public marketing surfaces → **Atelier**.
- Authenticated Career Workspace → **Nocturne**.

Each system stays scoped to its surface class. Do not attempt to unify Atelier and
Nocturne into one design system.

#### Consequences
- Positive: clear identity per surface class; no cross-contamination of tokens;
  reviewers can reject "merge the two" proposals on sight.
- Negative/trade-off: some shared primitives may be authored twice, once per system.

#### Follow-up
- [ ] Tag future design handoffs with their target system (Atelier vs Nocturne).

### DEC-20260708-002 — Action routing contract for agentic UI (no frontend-only actions)

Status: accepted
Date: 2026-07-08
Owner: Roben
Related task: design-handoffs review (command-concept-sandbox)

#### Context
The reviewed prototype demonstrated a Safety Approval Surface and job Apply/Save
CTAs using frontend-only approval state and `alert()` calls. That pattern pretends
persistence and bypasses Rico's backend safety layer.

#### Decision
Any interactive action promoted from a design reference into production MUST route
through the full pipeline:

```text
Intent → Safety Policy → Agent Runtime → Persistence → Confirmation
```

Concretely: `rico_safety.py` guardrails + `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS`
+ `agent_runtime.handle_action()` + `POST /api/v1/actions/{action}` (idempotent,
audit-logged), with confirmation surfaced back to the user. Hard rules:

- No frontend-only approval logic.
- No `alert()` actions.
- No local state pretending persistence.

#### Consequences
- Positive: prototypes cannot smuggle unsafe action paths into production; safety
  stays backend-owned and auditable.
- Negative/trade-off: promoting a UI concept always requires backend wiring work,
  never a copy-paste of the prototype interactions.

#### Follow-up
- [ ] Apply this contract to any future promotion of the command-concept scenes.

### DEC-20260708-001 — Classify `command-concept-sandbox` as Approved Design Reference (requires production adaptation)

Status: accepted
Date: 2026-07-08
Owner: Roben
Related task: design-handoffs review (command-concept-sandbox)

#### Context
The `command-concept-sandbox` handoff (Tool Activity Timeline, Explainable Match
Card, Safety Approval Surface, Thinking State) is on-identity (Nocturne),
dependency-safe (`framer-motion` only), and built on real theme tokens, but its
interactions were mock-only (frontend approval, `alert()`, fake persistence).

#### Decision
Classify it as **Approved as Design Reference (requires production adaptation)** —
not rejected, not promoted to production or `/design-gallery`. Move it to
`design-handoffs/reviewed/` only after cleanup: hardcoded RGB → design tokens,
English leaks localized, and the frontend approval simulation removed (buttons made
non-functional; required production routing documented). Any production use is a
separate, safety-reviewed effort governed by DEC-20260708-002.

#### Consequences
- Positive: the four concepts are preserved as a clean, tokenized, honest reference
  without any unsafe interaction path or production risk.
- Negative/trade-off: the reference is intentionally non-functional; real behavior
  must be rebuilt on the production architecture later.

#### Follow-up
- [ ] If prioritized, scope a gallery-only or workspace implementation PR that wires
  actions through the DEC-20260708-002 pipeline.

### DEC-20260707-001 — Split Rico's architecture maturation into phases; persist state before any migration or redesign

Status: accepted (Approved roadmap)
Implementation: Not started — this is a roadmap only. No phase has been built. Railway, the
worker service, and Redis/Queue do **not** yet exist in production; Render remains the production
backend. Do not read this decision as describing shipped infrastructure.
Date: 2026-07-07
Owner: Roben / Claude
Related task: TASK-20260707-001 (phased architecture roadmap)

#### Relationship to the production hardening audit gate (2026-07-08)
This decision is the **architecture-level roadmap**. The **near-term execution authority is the
production hardening audit gate**: `AI_WORKSPACE/AUDITS/2026-07-08-production-hardening-audit.md`
(+ Codex follow-up `AI_WORKSPACE/AUDITS/2026-07-08-audit-gate-codex-followup.md`). Agents must
read that audit before starting any feature, redesign, worker, notification, or infrastructure
work; it controls immediate stabilization, and its Phase 2 (job context & apply-link lifecycle)
governs the near-term work this decision calls "PR A".

The two do not compete: DEC-20260707-001 keeps the higher-level sequence (including the deferred
Railway/worker/UI phases the audit explicitly does **not** authorize yet); the audit gate is how
the near-term operational-memory phases actually get proven and shipped. Render stays the current
production backend; no infrastructure migration work starts from either document now.

**PR A is verify-first, not rebuild-first.** The persistence layer already exists on `main`
(`user_job_context_repo.py`, migrations 018–022, the `rico_chat_api.py` write/read paths, and the
lifecycle routers). PR A therefore means: prove the specific gap first (Audit Phase 2 checks),
then ship the smallest safe fix for a **proven** gap only. Do not build a second implementation of
job persistence. Verification and any fix use **synthetic users and synthetic profile data only** —
no real-user smoke or mutation is authorized unless the owner explicitly approves a specific run.

#### Context
Rico's current architecture is valid but not mature. It works as a stable production stack
(Vercel frontend → `/proxy` → Render FastAPI → Rico chat/NLU/safety/job logic → Neon), but
several backend responsibilities are still mixed: request handling, temporary chat memory, and
the job-search script share the same process, and some important state (job search results,
apply links, follow-up state) has historically been unreliable on Render's ephemeral disk.

Rico is evolving from a job board into an **AI career operator**. The product direction is
strong; the weak point is **operational state**. The clearest warning is the apply-link problem:
Rico can find a job but lose the apply URL because job context was not reliably persisted to Neon.

Concrete risks:
| Area | Risk |
| --- | --- |
| Render | ephemeral disk, weaker worker/cron story |
| Memory | job context previously unreliable on Render |
| Frontend | proxy/env mismatch can break auth state |
| Product logic | chat, job search, applications, and memory overlap |
| AI | too much depends on intent-routing correctness |
| UI | redesign branches can break stable production |

#### Decision
Mature the architecture in **ordered phases**, smallest-safe first, and do not redesign the UI
or migrate the whole platform while operational state is still unstable.

Target architecture (end state, not a big-bang migration):

```text
Vercel            Next.js frontend
API service       FastAPI (requests only): Rico chat controller, auth/session, job/application API
Worker service    job scans, follow-up checks, alerts, link verification, scheduled tasks
Neon              users, profiles, job_context, applications, memory, billing/subscription
Redis / Queue     background tasks, retries, rate guards
Telegram / Email  notifications only
```

Guiding principles:
1. **Separate API from worker logic.** FastAPI handles requests only; workers own job scans,
   email alerts, follow-ups, link verification, and scheduled tasks.
2. **Neon is the single source of truth.** No important state lives only in memory or on Render
   disk. Must persist: job search results, apply links, application state, target role,
   chat-derived preferences, follow-up state.
3. **Keep the Vercel frontend; move the backend later.** Migration target is Railway first,
   Google Cloud Run later if scale grows. Do not migrate everything at once.
4. **Do not redesign while the architecture is unstable.** Safe near-term work is shell cleanup,
   API consolidation, job-lifecycle persistence, application-lifecycle cleanup, and worker/cron
   structure — not theme switching or a big UI replacement.

Recommended PR / phase order (each an independently reviewable slice from current `main`).
Rationale for ordering: Rico's biggest current product risk is **losing operational state**, so
persistence and application lifecycle come before API consolidation. Each phase has measurable
completion criteria; a phase is not "done" until its criteria are met and regression tests pass.

1. **Persist job context + apply links** (PR A — **verify-first**) — top-priority reliability fix.
   Persistence already exists on `main`; this phase proves Audit Phase 2 gaps (synthetic data only)
   and fixes only what is proven — it does not rebuild persistence.
   - [ ] Job search results persisted in Neon (not memory / Render disk).
   - [ ] Apply links survive a backend restart.
   - [ ] "Open apply link" uses the persisted context, not in-memory state.
   - [ ] Regression tests pass.
2. **Application lifecycle cleanup** (PR B).
   - [ ] Application states defined and reconciled across router + agent runtime writes.
   - [ ] Application state persisted and survives restart.
   - [ ] No lifecycle path bypasses the audit / approval layer.
   - [ ] Regression tests pass.
3. **API / client consolidation** (PR C).
   - [ ] Duplicate/legacy client paths (`apps/web/services/*` vs `apps/web/lib/api.ts`) consolidated.
   - [ ] No behavior change to auth/chat/CV/profile/onboarding flows (verified by build + smoke).
   - [ ] Regression tests pass.
4. **Worker / cron separation** (PR D).
   - [ ] Job scans, follow-up checks, alerts, and link verification run outside the request path.
   - [ ] FastAPI serves requests only; scheduled work has its own service boundary.
   - [ ] Regression tests pass.
5. **Move backend from Render to Railway** (PR E).
   - [ ] Railway backend passes full production smoke (auth, chat, jobs, applications, webhooks).
   - **Rollback / safety:** Render remains the production backend until Railway passes full
     production smoke testing. Do not cut DNS/proxy traffic to Railway before that gate.
6. **Add monitoring / logging** (PR F).
   - [ ] Error, deploy, and provider-health signals observable; alerts route per the Telegram
     audience rules (admin/dev channel only for technical alerts).
7. **UI redesign** (PR G) — only after phases 1–6 land.

Note: the letters PR A–G above map to the merge sequence recommended by the reviewer; earlier
drafts of this decision listed API consolidation first — it has been demoted below persistence
and application lifecycle because state reliability is the higher current risk.

#### Consequences
- Positive: reliability-first ordering — Rico stops forgetting what it found, what the user
  opened, what was applied, and what needs follow-up, before any risky migration or redesign.
- Positive: each phase is a small, reviewable PR from current `main`; production stays stable.
- Negative/trade-off: the desired UI redesign is deliberately deferred behind operational work;
  the Render→Railway move is sequenced late, so ephemeral-disk risk persists until phases 2–4
  reduce reliance on process-local state.

#### Follow-up
- [ ] Phase 1 (PR A): confirm job-context + apply-link persistence to Neon end-to-end (top-priority
      reliability fix; ties into DEC-20260703-001 recommendation-table work).
- [ ] Phase 2 (PR B): define the application lifecycle states and reconcile router/runtime writes.
- [ ] Phase 3 (PR C): audit API/client surface for duplicate/legacy paths (`apps/web/services/*`
      vs `apps/web/lib/api.ts`) and consolidate.
- [ ] Phase 4 (PR D): scope the worker/cron service boundary (job scans, follow-ups, link verify).
- [ ] Phases 5–7 (Railway move, monitoring, UI redesign) stay proposed until 1–4 land; Render
      stays the production backend until Railway passes full production smoke.

### DEC-20260703-001 — Keep partial-unique as ON CONFLICT arbiter; codify full-unique for read coverage

Status: accepted
Date: 2026-07-03
Owner: Claude (GitHub session)
Related task: TASK-20260703-037

#### Context
`rico_job_recommendations` carries both a partial-UNIQUE
(`idx_rico_recommendations_user_job_unique`, WHERE job_key IS NOT NULL — migration 011)
and a full-UNIQUE (`rico_job_recommendations_user_id_job_key_key`) in production.
Migration 034 dropped the two plain `(user_id, job_key)` indexes; something must cover
their read role, and the upsert's ON CONFLICT targets a specific arbiter.

#### Decision
Keep the partial-UNIQUE as the named `ON CONFLICT (user_id, job_key) WHERE job_key IS NOT NULL`
arbiter (do not replace it). Codify the full-UNIQUE in migration 035 so a fresh DB matches
production and covers general `(user_id, job_key)` lookups after 034's drops. Chose #826's
6-drop set over #827's 8: the 2 extra drops were unsafe — `idx_rico_recommendations_user_status`
is re-created by the `rico_db.py` runtime DDL on every startup, so a migration DROP would not stick.

#### Consequences
- Positive: less write amplification on hot tables; code and production schema agree; BUG-14
  idempotency arbiter untouched; drift checker now verifies the full-unique constraint.
- Negative/trade-off: production briefly carried a schema object (the full-unique) the repo
  did not declare; 035 closes that gap retroactively rather than at table-create time.

#### Follow-up
- [ ] Verify remaining 005 objects for #712 before closing it.

### DEC-20260628-001 — No Dead UI Rule

Status: accepted
Date: 2026-06-28
Owner: Roben / Claude
Related task: PR #775 (cleanup); audit surfaced during P2-A production verification

#### Context

During P2-A production verification, a route audit found that `next.config.js` redirected 9 routes
to `/command` or `/flow`, while 7 of those routes still contained substantial `page.tsx` implementations
(48–576 lines each). The most notable case: `/onboarding` redirects to `/command`, but
`apps/web/app/onboarding/page.tsx` is 466 lines of real code including CV upload, classification,
and bilingual error messages — none of which is reachable in production.

This "redirect + live page" pattern creates an invisible class of dead code: it passes `npm run build`,
passes TypeScript, and passes CI, but is never executed by any user. It silently accumulates drift,
bugs, and maintenance debt without any signal.

#### Decision

**No route may redirect away while still keeping meaningful `page.tsx` code behind it.**

A route must be exactly one of:

1. **Active and reachable** — no redirect; the page is the live production UI.
2. **Redirect-only** — `next.config.js` redirect is the correct mechanism AND the `page.tsx` either does
   not exist or contains only a thin passthrough (e.g. `redirect("/command")`) with no meaningful logic.
3. **Removed** — route, redirect, and page file all deleted.

Hybrid state (redirect + real page.tsx) is prohibited. If a page cannot be made live yet, keep it
redirect-only with no implementation, or gate it behind a feature flag that makes the page reachable.

#### Consequences

- Positive: CI failures, type errors, and behavioral bugs in `page.tsx` files are guaranteed to matter —
  there is no silent dead-code escape hatch.
- Positive: redirect inventory in `next.config.js` is the single truthful routing contract.
- Trade-off: routes with meaningful page code that are intentionally hidden (future features, WIP)
  must live on a feature branch until they are either live or formally removed.

#### Follow-up

- [x] Phase A (2026-06-28): delete `/chat` and `/orchestrate` stubs; remove `/pipeline → /flow` redirect
      (no page file exists for `/pipeline`).
- [ ] Phase B: resolve `/dashboard`, `/onboarding`, `/jobs`, `/signals`, `/archive`, `/saved-searches` —
      each requires an explicit product decision: make live, strip to stub, or delete.


### DEC-20260621-003 — Action-audit hardening rolled out; migration drift surfaced and tracked

Status: accepted
Date: 2026-06-21
Owner: Roben / Claude
Related task: PR #708, issues #710, #711

#### Context

DEC-20260621-002 approved #708 as the draft implementation candidate for hardening the existing
`action_audit_log` (migration 030). This decision records the completed rollout and the production
migration drift it surfaced.

#### Decision

- Apply migration 030 to production Neon before deploying, then merge + deploy #708. Done:
  #708 merged at `9078d77`, migration 030 applied + verified in production, backend live on `9078d77`.
- Treat production migration drift as separate, gated cleanups — never bundled with #708:
  - #710 (`021_user_job_context_alt_url.sql`) applied + closed.
  - #711 (`005` `pipeline_runs`, `011` `rico_job_recommendations` unique index) logged, NOT applied
    (verify-first; 011 deletes rows).

#### Consequences

- Positive: audit log is now DB-enforced append-only; request-time DDL removed from `write_audit_log()`.
- Positive: a full `005`–`030` prod drift audit now exists and is repeatable.
- Trade-off: numbered migrations are still applied manually (no deploy-time runner) — the systemic
  root cause behind both 030's manual apply and the 021/005/011 drift.

#### Follow-up
- [ ] #711 — apply 005 (targeted) and 011 (verify-first) under explicit approval.
- [ ] Add a migration runner / CI gate so prod schema can't silently fall behind `main`.


### DEC-20260621-002 — Harden existing `action_audit_log`; do not build parallel audit/approval systems

Status: accepted
Date: 2026-06-21
Owner: Roben / Claude
Related task: PR #708

#### Context

After PR #706 merged, the canonical Agentic Vision foundation is the existing action runtime,
pending-permission system, and `action_audit_log`. PR #685 attempted a parallel audit and approval
foundation (`agent_audit_events`, `agent_approval_tokens`, duplicate `audit_writer.py`, and
parallel `policy_gate.py`), which creates duplicate-risk against the now-merged inventory guidance.

The audit repository also still had request-time schema mutation: `write_audit_log()` checked
`information_schema` and executed `ALTER TABLE action_audit_log ADD COLUMN ...` during normal
request handling.

#### Decision

Proceed with PR #708 as a draft implementation candidate on branch
`feat/action-audit-schema-hardening`.

Allowed direction:

- extend existing `action_audit_log`
- move `event_type` and `data` additions into numbered migration 030
- add database-level append-only protection where safe
- update focused `audit_repo` tests
- keep existing action runtime and pending-permission system

Explicitly not allowed:

- frontend or `/ask`
- permission token format changes
- `agent_approval_tokens`
- duplicate HMAC approval infrastructure
- duplicate `audit_writer.py`
- parallel `policy_gate.py`
- `agent_audit_events`
- browser automation
- CV tailoring
- FitScorer

Stale PR queue decision:

- #685 closed as superseded / duplicate-risk
- #695 closed as superseded by #706 and #707 workspace state
- #699 closed as template/unclear not planned
- #688 kept open only as preview/mock UX; do not merge, wire, or treat its 300-second timer as production truth
- #697 kept as a separate small bugfix candidate; do not mix with audit-schema hardening

#### Consequences

- Positive: keeps audit hardening on Rico's canonical audit path and avoids a second approval/audit stack.
- Positive: removes schema DDL from request-time repository code.
- Trade-off: migration 030 must be reviewed and applied before deploying the repository change, because `write_audit_log()` no longer creates missing columns at runtime.
- Trade-off: the append-only trigger intentionally blocks update/delete/truncate operations on `action_audit_log`; this is correct for audit integrity but requires explicit rollback approval if future maintenance needs mutation.

#### Verification

Implementation report for #708:

- PR: #708 draft, open, unmerged
- Head: `fb63a60a9ba0c35debdff2dfa734caf1c271a183`
- Changed files: 4
  - `migrations/030_action_audit_log_hardening.sql`
  - `src/repositories/audit_repo.py`
  - `tests/unit/test_action_audit_schema_migration.py`
  - `tests/unit/test_write_audit_log.py`
- Focused tests: 27 passed
- Python compilation: passed
- Git diff check: passed
- GitHub pytest, Playwright, Vercel: passed

#### Follow-up

- [ ] Review migration 030 carefully before marking #708 ready.
- [ ] Confirm no current code path updates/deletes/truncates `action_audit_log`.
- [ ] Plan safe Neon/production migration rollout.
- [ ] Apply migration 030 before deploying the repository change.
- [ ] Keep #708 draft until migration rollout is explicitly approved.

### DEC-20260621-001 — Smallest-safe security hardening batch (#700–#705) merged to `main`

Status: accepted
Date: 2026-06-21
Owner: Roben / Claude
Related task: TASK-20260621-001

#### Context
A codebase sweep surfaced a class of high-impact correctness and security gaps in the
agent action / approval path:
- The permission approval engine (CAREER-OS-03) issued `apply` permissions that were not
  bound to a specific job, allowing a valid `permission_id` to be replayed against a
  *different* job.
- Permission denials were not audited.
- Multiple DB writers inserted/upserted without `conn.commit()` in the psycopg2
  non-autocommit environment, so the writes were silently rolled back. Only the in-memory
  dedup/cache survived, which is why the data loss went unnoticed.
- A connection-pool leak in identity merge left connections open on the exception path.
- `/api/v1/actions/run` passed the client-provided `job` dict straight to the runtime
  without stripping the `_approved` sentinel, letting a caller forge approval and bypass
  `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS`.

Per the user directive, the chosen approach was the smallest safe fix first — harden in
place through existing systems rather than building a parallel audit/approval framework.

#### Decision
Ship the hardening as small, focused PRs from current `main`, each independently testable:

- **#700** — Bind `job_key` to issued `apply` permissions; reject replay against a different
  job (mismatch does *not* consume the token, so the legitimate job can still approve). Audit
  permission denials through the existing `audit_repo.log_action()` with
  `result_status="denied"`, `failure_reason="permission_denied"`.
- **#701** — Add the missing `conn.commit()` in `audit_repo._db_write` so `action_audit_log`
  rows actually persist (regression-tested).
- **#702** — Fix `_save_attempt` in `src/auto_apply.py` and `src/naukrigulf_apply.py` to
  `commit()` after upsert and `close()` in `finally`.
- **#703** — Acquire the connection before the `try` and `close()` in `finally` in
  `agent/identity/resolver._attempt_identity_merge` (read-only, no commit) so the connection
  is released on every path.
- **#705** — Sanitize the `job` dict in `/actions/run` by stripping the `_approved` key; only
  `/actions/execute` (which validates a `permission_id`) may inject the sentinel.
- AI_WORKSPACE is standardized as the task-flow control system for all agents (reinforces
  DEC-20260617-001).

#### Consequences
- Positive: closes a permission-replay vector and an approval-bypass vector; restores audit
  and application-attempt persistence; eliminates two connection leaks. All changes are
  backward compatible (unbound permissions still accept any job; empty key normalizes to
  unbound). Render backend redeploy verified live.
- Trade-off: job-key binding is stricter — any caller that previously relied on reusing a
  permission across jobs will now be rejected (intended).

#### Verification (2026-06-21)
- Render: "Your service is live"; Uvicorn up on port 10000; `rico_db_init OK`;
  `settings_migration OK`; `startup_check: critical tables present`;
  `migration_ok label=028_performance_indexes`.
- `/health` → 200; `/version` → 200 during deploy polling.
- Warning (non-blocking): SkillNER not installed; did not block startup.

#### Follow-up
- [x] Confirmed deployed commit: `/version.commit` = `d93bb25` (current `main` HEAD), so the
      merged hardening batch (#700–#704) is live in production. Note: the `/version.deployed_at`
      field reads `2026-05-23` — it is a static build-time constant, not the actual deploy time,
      so trust `commit` over `deployed_at`.
- [x] Merged #705 (pytest + playwright green; squash commit `da452f6` on `main`). #704 closed
      as superseded — the consolidated AI_WORKSPACE decision record already landed via #705.
- [x] #705 Render deploy verified LIVE (2026-06-21): `/version.commit` = `da452f6`
      (matches `main` HEAD); `/health` → 200. Approval-bypass fix is in production.

### DEC-20260618-001 — Close PR #601 as stale/superseded; merge docs PRs #608 and #566

Status: accepted
Date: 2026-06-18
Owner: Roben / Claude
Related task: TASK-20260618-014

#### Context
Three open PRs created backlog noise. #601 was a broad multi-batch feature PR (~1.3k LOC)
touching `src/rico_chat_api.py` on a stale base, still in draft, with an unchecked test plan
and a body/title mismatch. #608 and #566 were small, clean, docs-only additions.

#### Decision
Close #601 without merging and without opening a replacement PR. Merge the two docs-only PRs
(#608 localization pattern, #566 Gmail read-only connector design) after confirming they are
clean, docs-only, and Vercel-green. Re-cut #601's deterministic fast paths later as small,
focused PRs from current `main` only if still needed.

#### Consequences
- Positive: open PR backlog is clean (0 open PRs); design docs for localization and the
  Gmail connector (#356) are now on `main`; future fast-path work starts from a current base.
- Trade-off: the fast-path content in #601 must be re-authored against current `main` if still
  wanted — its existing diff is not reused.

#### Follow-up
- [ ] Re-cut #601 fast paths as small PRs from `main` if/when prioritised.
- [ ] Consider disabling the third-party "Continuous AI" bot checks (they error on every PR).

### DEC-20260617-001 — Use `AI_WORKSPACE/` as the shared AI source of truth

Status: accepted
Date: 2026-06-17
Owner: Roben / ChatGPT
Related task: TASK-20260617-001

#### Context
Multiple AI tools can plan, implement, review, and verify Rico work. Without a shared repo-native context, each tool can drift based on stale chat history.

#### Decision
All multi-model work must use `AI_WORKSPACE/` as the shared source of truth for project context, active tasks, handoff briefs, decisions, and verification evidence.

#### Consequences
- Positive: less context drift, clearer PR boundaries, easier review.
- Trade-off: every contributor must update the workspace files when task state changes.

#### Follow-up
- [ ] Use the handoff template for the next implementation task.
- [ ] Keep decisions short and tied to tasks.
