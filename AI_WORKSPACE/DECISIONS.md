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

## Proposed decisions

### DEC-20260718-001 — Canonical Neon data-architecture source-of-truth matrix

Status: proposed (owner approval required; acceptance = owner approval of the
Stage 1 audit PR plus explicit sign-off on each row below)
Date: 2026-07-18
Owner: Roben (evidence prepared by Claude, Stage 1 DB audit)
Related task: TASK-20260718-007; audit:
`AI_WORKSPACE/AUDITS/2026-07-18-neon-data-architecture-audit.md`

#### Context

The 2026-07-18 read-only audit of Neon production (`robenjob` /
`br-restless-cherry-amq6wj7o`) verified identity fragmentation across four
identifier families, a three-way application-lifecycle contradiction,
confirmed migration drift (043 absent, 034 partial), an owner-role/no-RLS
access model, and an orphaned `leads` table. Remediation cannot start until
one source of truth per domain is decided.

#### Decision (proposed matrix)

| Domain | Source of truth | Evidence |
|---|---|---|
| Authenticated identity spine | `rico_users.id` (UUID), mapped from `users`/JWT email; text-keyed tables link via a mapping layer, not a rewrite | audit §4 |
| Application lifecycle | `rico_job_recommendations` (already canonical in code via `applications_repo` + `RicoDB._CANONICAL_APPS_CTE`) | audit §5 |
| `user_job_context` role | discovery/conversation context ONLY — never an application ledger | audit §5 |
| Legacy `applications` table | frozen legacy-pipeline artifact; no new writes; structurally single-tenant (no `user_id`, global `UNIQUE(job_link)`); retire in Phase 7 | audit §5, §12 |
| Billing entitlement | `paddle_subscriptions` via `resolve_effective_user_plan` (`src/subscription_plans.py:90`); Stripe-era tables read-only legacy; `subscription_intents` = manual-mode lead capture, never entitlement | audit §6 |
| Legacy tables policy | classify (active / transitional / legacy / dormant / orphaned), freeze, isolate — never delete without proven code-path absence AND owner data-ownership confirmation (`leads` has zero code paths but unconfirmed ownership) | audit §12 |
| Production DB access model | least-privilege runtime role for FastAPI (replace BYPASSRLS owner); revoke blanket `authenticated` CRUD; RLS policies designed and cross-user-denial-tested on a non-production branch before any production flip | audit §8 |

> **Study-2 gate:** the authenticated identity-spine row (first row above)
> cannot move to ACCEPTED until **Study 2 — Identity, Authentication,
> Authorization & Session Architecture Audit** verifies or revises that
> decision. The remaining rows may be accepted independently on owner
> approval.

#### Consequences

- Positive: every remediation phase (TASK-20260718-008…014) inherits one
  unambiguous target per domain; ends email-vs-UUID drift in new code.
- Negative/trade-off: a mapping layer must be built and maintained for the
  text-keyed tables; Phase 2 role migration carries a production change
  window.

#### Follow-up

- [ ] Phase 1 branch protection (TASK-20260718-008, slice 1A) proceeds on
      explicit owner approval alone — it is NOT gated on this matrix, on
      Neon Data API status, or on the Render runtime role
- [ ] Neon Data API status and Render `DATABASE_URL` runtime-role
      verification happen exclusively in Phase 2 slice 2A
      (TASK-20260718-009); they decide whether the P0 conditional in
      audit §8 is live
- [ ] `leads` data ownership confirmation gates only slice 7A
      (TASK-20260718-014)
- [ ] Identity-spine row: stays PROPOSED until Study 2 (Identity/Auth/
      Session architecture audit) verifies or revises it; on owner approval
      the remaining rows may move to Accepted independently

## Accepted decisions

### DEC-20260719-003 — WhatsApp-assisted subscription restored as a SECONDARY assisted channel; Paddle stays the primary automated provider; entitlement boundary unchanged

Status: accepted
Date: 2026-07-19
Owner: Roben (owner directive, 2026-07-19) — recorded by Claude

#### Decision

Restore a WhatsApp-assisted subscription path alongside Paddle, amending the
Paddle-only posture of #1143 (2026-07-17) for the ASSISTED-channel scope
only. Binding rules:

1. Paddle remains the primary automated payment provider; its behavior,
   plans, prices, and currencies are unchanged (Rico Monthly — USD
   21.50/month). No Stripe.
2. WhatsApp is an assisted/manual subscription CHANNEL, not a payment
   processor. Opening WhatsApp, sending a message, or uploading a payment
   screenshot NEVER grants entitlement.
3. The ONLY entitlement activation path for this channel is the existing
   admin-only manual mechanism (`POST /api/v1/admin/subscriptions/activate`)
   after the owner verifies payment out-of-band. Approval is authenticated,
   auditable, idempotent, server-side.
4. The channel is server-configured and fail-closed:
   `WHATSAPP_SUBSCRIPTIONS_ENABLED` (default false) +
   `WHATSAPP_SUBSCRIPTION_NUMBER` (validated E.164). Missing/invalid config
   hides the CTA and 503s the request endpoint; Paddle is unaffected either
   way.
5. Requests are server-owned rows (`whatsapp_subscription_requests`,
   migration 049): opaque `RICO-…` reference, authenticated user_id,
   server-side plan/price/currency snapshot, status pending→approved/
   rejected, one pending request per user (idempotent clicks). The
   prefilled message carries reference/plan/price only — never JWTs,
   emails, phone, CV data, DB ids, or credentials.

Difference from the pre-#1143 implementation (and why that one stays
removed): the old flow was client-built (`buildWhatsAppUpgradeUrl`), put the
user's EMAIL in the message, labeled the price AED, and had no server-side
request record — none of that returns. #1143's removal of the client-side
manual-payment path remains in force; this decision adds a server-owned
assisted flow, not a revival of the old code.

Rollback: set `WHATSAPP_SUBSCRIPTIONS_ENABLED=false` (CTA disappears,
endpoint 503s, pending rows preserved for audit); Paddle unaffected; no
entitlement change for existing customers.

Implementation: PR (draft) from `feat/whatsapp-assisted-subscription`;
handoff `HANDOFFS/2026-07-19-whatsapp-assisted-subscription.md`; ledger
TASK-20260719-015.

### DEC-20260719-002 — Command Workspace v4 is the adopted frozen design reference; modes map to routes; the /command design freeze remains active

Status: accepted
Date: 2026-07-19
Owner: Roben (owner rulings, 2026-07-19) — recorded by Claude
Related task: TASK-20260719-006; handoff:
`design-handoffs/reviewed/2026-07-19-command-workspace-v4/README.md`

#### Context

The owner approved `Rico Command Workspace v4.dc.html` (1,859 lines,
165,606 bytes, full verification PASS matrix) as the design direction for the
authenticated workspace (Career OS). A read-only repository audit mapped the
reference onto the current architecture and the owner issued explicit rulings
on scope and boundaries. A durable record is required so future work cannot
misread the prototype as an architecture mandate or as implementation
authorization.

#### Decision

- **`Rico Command Workspace v4.dc.html` is a frozen approved design
  reference.** The raw artifact stays uncommitted (obsidian-v4 precedent);
  the reviewed handoff README is the committed record of its contracts.
- **Modes map to existing routes** (Overview → `/dashboard`, Search →
  `/command`, Applications → `/applications`, Documents → `/upload`). No
  single-page mode switcher is built; the shared `WorkspaceShell`
  architecture (DEC-20260717-001) stands.
- **Production Ctrl/Cmd+K behavior remains unchanged** (focuses the
  `/command` composer). The prototype's ⌘K-toggles-copilot contract is not
  adopted.
- Production tokens only (`WORKSPACE_THEME`, `atelier-kit`); the reference's
  palette/fonts are composition guidance, never a token source.
- **Memory, Interview, Learning, Activity, embedded Copilot, and per-mode
  transcripts remain deferred** until the corresponding real capabilities
  exist. No fake states: blocks without a real data source are omitted, not
  stubbed.
- **The `/command` design freeze remains active.** Every future `/command`
  PR requires its own separate, recorded, one-PR-only freeze lift naming
  that PR; lifts are never blanket and expire on merge/close.
- **This adoption does not authorize any implementation work**, and **no
  implementation tasks are created in advance** — each implementation PR
  creates its own task entry at cut time.

#### Consequences

- Positive: one canonical record of the approved direction and its
  boundaries; prototype contracts (default-open policy, responsive
  breakpoints, trust/action vocabulary, context-source labels) are preserved
  for future implementation PRs without freezing them into code prematurely.
- Negative/trade-off: the reference and production will visibly diverge
  until implementation PRs are individually approved; contributors must read
  the handoff boundaries before quoting the prototype.

#### Follow-up

- [ ] Implementation PRs proceed only under their own owner approval,
      sequenced per the recorded plan (dashboard Overview parity first).
- [ ] Any future `/command` slice: obtain a one-PR-only freeze lift before
      cutting the branch.

### DEC-20260719-001 — Analytics retention: fixed 180-day window, never caller-controlled; cron-secret endpoint + GitHub Actions scheduler; two-gate rollout

Status: accepted
Date: 2026-07-19
Owner: Roben (audit prepared by Claude; owner ruling "Approve with minor refinements")
Related task: TASK-20260719-004

#### Context

Migration 047 shipped `analytics_events` with a 180-day retention contract
and `purge_expired()` as the policy's single implementation point, but no
scheduled invocation ("wired in a LATER change"). A read-only audit of the
repository confirmed: the proven scheduling architecture is GitHub Actions
scheduled workflows calling `X-Cron-Secret`-guarded pipeline endpoints
(weekly-admin-digest precedent); no Render cron, worker service, Celery, or
DB-side scheduling exists or is approved; `purge_expired()`'s bounds accept
`retention_days=1`, so exposing retention to any caller would allow a
near-total purge.

#### Decision

1. The retention window is the `RETENTION_DAYS = 180` constant in
   `src/repositories/analytics_events_repo.py` — NEVER an API input (no
   query parameter, no body field, no override for any caller including
   authenticated cron) and never an env var. Changing it is a reviewed code
   change plus a DECISIONS.md update.
2. The scheduled path is `POST /api/v1/pipeline/analytics-purge`
   (cron-secret pattern) called by `.github/workflows/analytics-purge.yml`.
   No new infrastructure.
3. Dry-run and delete share one predicate string
   (`_EXPIRED_PREDICATE_SQL`) so they cannot drift.
4. Two-gate rollout: `RICO_ENABLE_ANALYTICS_PURGE` defaults OFF
   (fail-closed 200 no-op), and the workflow schedule ships commented out.
   Enable order: 047 applied to production → emitters live → baseline
   starts → merge (inert) → flag on → dry-run verification → schedule on.
5. Batching is deliberately deferred — at daily cadence each run deletes
   roughly one day of events; revisit only if a real backlog materialises.

#### Consequences

- Positive: retention becomes enforced product behavior, not a comment;
  privacy exposure of pseudonymous events is time-bounded; the purge is
  independently disableable at three levels (workflow, flag, revert) with
  no deploy needed for the first two.
- Negative/trade-off: purged rows are unrecoverable by design (mitigated by
  the fixed constant, dry-run-first verification, and Neon PITR for
  disasters); account deletion still leaves pseudonymous analytics rows
  inside the window — the time-based purge is the operative control there
  (any actor-level erasure would be a separate decision).

#### Follow-up

- [ ] Owner applies 047 to production per the runbook (separate gate).
- [ ] Owner sets `RICO_ENABLE_ANALYTICS_PURGE=true` on Render after
      baseline is established; dry-run dispatch verification.
- [ ] Follow-up change uncomments the workflow schedule.

### DEC-20260717-001 — `/command` is unified with the shared WorkspaceShell; light-first default, dark by choice (implements DEC-20260716-001 for `/command`)

Status: accepted
Date: 2026-07-17
Owner: Roben (owner directive 2026-07-17)
Related task/PR: TASK-20260717-008 / PR #1145

#### Context

Under DEC-20260716-001, Atelier V3 is the sole product-wide visual system and
"Atelier at Night" is its dark **mode**. The authenticated `/command` route,
however, still shipped as a separate island: a copied `COMMAND_ATELIER` palette
with drifted token values, a `/command`-only **forced-dark default**, bespoke
canvas layers, and a duplicated top bar re-implementing chrome that every other
page gets from `WorkspaceShell`. This kept `/command` off the shared token
source and off the site-wide light-first default.

#### Decision

`/command` composes the shared `WorkspaceShell` (`variant="app"`) and draws all
core colors from the single `WORKSPACE_THEME` source:

1. **Light-first default, dark by user choice** — `/command` defaults light like
   every other workspace surface; dark is "Atelier at Night" via the same shared
   sidebar toggle, not a route-forced default. This retires the `/command`-only
   forced-dark default aspect of the prior implementation while keeping DEC-001's
   Atelier V3 / Atelier-at-Night model intact.
2. **Single token source** — the copied `commandAtelierTheme.ts` is deleted; the
   reply-surface CSS-var layer is derived from the active shared palette.
3. **Shared chrome** — sidebar, brand, EN/عربي, and theme toggle come from
   `WorkspaceShell` (identical to Profile/Applications/Upload/Settings/
   Subscription). Only genuinely route-scoped controls remain (console status
   bar, Sessions rail, desktop logout menu).

Scope is visual/system unification only — **zero** chat behavior, endpoint,
payload, streaming, persistence, auth, or quota change. The Sessions-rail
position (owner correction 2026-07-16) is preserved. `MobileCommandHeader` /
`MobileBottomNav` are intentionally out of scope (shared with public/legacy
surfaces; a separate follow-up).

#### Consequences

- Positive: one coherent product surface; `/command` no longer drifts from the
  shared palette or the site-wide default; future theme changes propagate.
- Trade-off: users used to `/command` opening dark now see light first (dark is
  one shared-toggle click away).
- Rollback: revert the single PR #1145 commit (restores the copied theme + prior
  shell); frontend-only, no state/API/config change.

### DEC-20260716-002 — My Files uses a parsed-record model (Option 2), not raw file storage; deleting a CV purges its grounding

Status: accepted
Date: 2026-07-16
Owner: Roben (owner) — delegated this pass's choice to Claude
Related task: TASK-20260716-003 (#1083)

#### Context

#1083 found that "My Files" persists metadata rows, not uploaded bytes, and that
deletion left CV-derived data still grounding Rico (a privacy/trust defect). The
issue required choosing one honest model **before** implementation: (1) real
encrypted object storage with an owner-approved retention/threat model, or (2) a
parsed-record model that stops promising raw file storage. Rico is in low-cost
MVP mode (Render Hobby; no new paid infra without owner approval), so
provisioning per-user encrypted object storage is out of scope now.

#### Decision

Adopt **Option 2 (parsed-record model)**: Rico retains parsed/derived content,
not the original uploaded files. CV-deletion retention rule: deleting the
active/primary CV (or the synthetic `profile-cv` card) purges the raw CV
grounding — `cv_text`, `cv_file_url`, `cv_structured`, and the
`profile.cv_filename` / `profile.cv_extracted_at` keys — so a deleted CV no
longer grounds matching/chat and cannot resurrect as an undeletable card. The
user's structured profile facts (skills, experience, current role) are retained
as the editable profile and cleared separately in Settings.

This PR implements only the model-independent, privacy-critical slice (deletion
completeness + no resurrection). The user-facing/legal parts below need owner
ratification before they ship.

#### Consequences

- Positive: users can actually delete their CV data; a deleted CV stops grounding
  chat/matching; the "cannot delete my CV" defect is fixed; no new paid storage.
- Negative/trade-off: originals are genuinely not retrievable — UI copy and quota
  language must stop implying raw "file storage" (owner-ratified follow-up).

#### Follow-up (owner ratification required — NOT in this PR)
- [ ] Reject or clearly mark cover-letter/"other" uploads whose bytes are
      discarded; stop charging storage quota for a metadata-only shell.
- [ ] UI disclosure: state originals are not retained; disclose retained derived
      facts and offer a separate deletion/correction action.
- [ ] Atomic CV switch: clear fields absent from the newly activated CV rather
      than inheriting stale values (COALESCE in `upsert_profile`), with explicit
      user confirmation.
- [ ] Align quota/export/account-deletion language to this model; link legal copy
      in #920.

### DEC-20260716-001 — Atelier V3 is the sole production-wide visual system (marketing, auth, workspace, /command); "Atelier at Night" is its dark mode

Status: accepted
Date: 2026-07-16
Owner: Roben (owner)
Related task: TASK-20260714-001 (Atelier full-site migration)

#### Context

Two prior decisions split Rico's visual identity and then held it in a
two-system limbo: `DEC-20260708-003` scoped **Atelier to marketing and Nocturne
to the authenticated workspace** and explicitly forbade merging them;
`DEC-20260709-006` accepted Atelier Console as the *candidate* workspace
direction but for **preview/exploration only**, keeping Nocturne in production
and Rico carrying two workspace design languages. Since then the Atelier system
has matured to **V3** and the owner has decided Rico ships as **one coherent
product**, not a collection of separately-styled surfaces. This decision
retires the split and the preview-only limbo. It is a **design-system
reconciliation only** — no production API, auth, upload, billing, persistence,
streaming, or agent contract changes, and it authorizes no UI code by itself
(Stage 1 is documentation; implementation follows the migration order below in
separately-reviewed PRs).

#### Decision

1. **Atelier V3 is the single, sole current visual system across the entire
   product** — public marketing, auth, the authenticated Career Workspace, and
   **/command**. There is no longer a per-surface-class design split.
2. **Dark mode is "Atelier at Night"** — the same Atelier V3 **semantic tokens**
   rendered dark, not a separate design language. Any dark surface derives from
   the shared token set; no parallel dark palette is authored.
3. **This supersedes `DEC-20260708-003`** (the Atelier/marketing ÷
   Nocturne/workspace boundary) and **supersedes `DEC-20260709-006`** (the
   preview-only, two-systems-coexist stance). The "authenticated workspace =
   Nocturne" boundary and the "Atelier is preview-only" limitation no longer
   apply.
4. **/command remains the canonical conversation route.** `/rico-preview`,
   `/design-gallery`, and `/design-preview` remain **internal reference only**
   (`noindex`, demo/sample data, actions disabled, not linked from production
   navigation) — reference surfaces, never production.
5. **Nocturne is historical/archive.** All Nocturne references (dark navy / gold
   / aura tokens and classes) are marked historical; they are removed only in the
   final migration step, one-for-one with the Atelier-at-Night replacement so
   reverts stay clean (No Dead UI rule). Duplicate reference archives are
   recorded (see below) so no live surface silently depends on them.
6. **Migration order (foundation-first, /command last):**
   1. **Foundation** — Atelier V3 semantic tokens + "Atelier at Night" dark set
      as the single source of truth (`apps/web/app/_atelier/atelier-tokens.css`
      and the workspace-theme context).
   2. **Shared shell & controls** — the app shell, nav, and shared control
      primitives adopt the V3 tokens.
   3. **Low-risk workspace routes** — settings/profile/applications/jobs and
      similar, per-route, smallest-PR-each.
   4. **/command last** — the highest-traffic, highest-risk conversation surface
      migrates only after the rest is stable. The in-flight `/command` slices
      keep their **structure and behavior** and are **re-skinned** from Obsidian
      acid-lime to the Atelier Console tokens (paper light + Atelier at Night,
      sun-red) — a visual token swap, not a functional rebuild (see note).
   5. **Visual QA** — EN/AR + RTL, light/dark, desktop/mobile parity pass across
      all migrated routes.
   6. **Remove legacy Nocturne tokens** — delete the archived Nocturne token set
      once no surface references it.
7. **Every production contract is preserved.** API, auth, upload, billing,
   persistence, streaming, and agent-action contracts are unchanged by any step;
   this is a visual-token migration only. Lovable / design-gallery / rico-preview
   are **visual reference only** and never a source of behavior.

**Duplicate reference archives (recorded, reference-only — not production):**
`apps/web/app/design-gallery/` (+ `design-gallery/atelier/atelier.css`,
`components/design-gallery/atelier-console/`), `apps/web/app/rico-preview/`,
`apps/web/app/design-preview/`, and the design handoffs under
`design-handoffs/reviewed/` (`rico-design-reference`, `command-concept-sandbox`,
`2026-07-16-command-obsidian-v4`). These are internal `noindex` reference
surfaces / handoff material; no production route may depend on them.

**The Command Obsidian program (C1–C6) → Atelier re-skin (owner decision,
2026-07-16):** the owner reviewed the Atelier design package (`/design-preview`)
and decided **`/command` uses the Atelier Console skin** — the same paper +
sun-red tokens as the rest of the product, with **Atelier at Night** for dark
mode. **Obsidian's dark acid-lime is historical reference only.** The completed
`/command` work is **preserved**: C1 (route-scoped token foundation), C2 (real
event/transcript adapter), C3 (composer parity), and C4 (job intelligence MATCH
cards) keep their **structure and behavior** — this is a **visual token re-skin,
not a functional rebuild**. Because C1 already routes `/command` through the
shared workspace-theme token context, the re-skin is primarily a token-value
swap (Obsidian acid-lime / dark-canvas → Atelier paper light + Atelier-at-Night
sun-red), sourced from the existing Atelier Console (`/rico-preview`,
`/design-gallery`). **C4–C6 do not continue under Obsidian styling.** "Command
Obsidian" as a visual identity is retired to historical reference; the program
continues as the `/command` step of the Atelier V3 migration.

#### Consequences

- Positive: one coherent product identity end-to-end; a single semantic-token
  source of truth; "merge the two systems" is now the goal, not a rejected
  proposal; dark mode is derived, not duplicated.
- Negative/trade-off: a real migration cost across every production route, and a
  transition window where migrated (Atelier V3) and not-yet-migrated (legacy
  Nocturne) routes coexist until the order completes.

#### Follow-up

- [ ] Execute the migration order above as separately-reviewed, smallest-PR-each
      changes (Stage 2+). This decision authorizes no UI code.
- [x] Confirm the `/command` skin — **owner decided 2026-07-16: Atelier Console
      (paper + Atelier at Night, sun-red); Obsidian acid-lime is historical
      reference only.** The completed C2/C3/C4 structure is preserved and
      re-skinned via tokens.
- [ ] Remove the archived Nocturne token set in the final step once unreferenced.

### DEC-20260713-005 — Replace Stripe with Paddle Billing; single-plan Rico Monthly USD 21.50/month

Status: accepted
Date: 2026-07-13
Owner: Roben (owner)
Related PR: #1008 (`feat/paddle-billing`)

#### Context

Production billing was dormant — `BILLING_MODE` defaulted to `manual` (WhatsApp-assisted).
Stripe code existed but was never activated. Owner provided Paddle API keys and asked for
a full Stripe→Paddle swap. Two parallel implementations were produced (#1008, #1011);

# 1008 was chosen as the base (standard Paddle.js overlay checkout, matches existing

idempotency patterns); #1011's server-owned checkout identity-attribution pattern was
ported in to fix three production-breaking bugs found in #1008.

#### Decision

- Full Stripe removal (no dual-provider). `stripe` dependency deleted.
- Single plan: **Rico Monthly, USD 21.50/month** (Pro/Premium two-tier collapsed). Paddle does
  not support AED as a billing currency. AED 79 is displayed as an approximate reference only.
  The authoritative displayed and charged price is USD 21.50 in all API responses, UI, and AI copy.
- Server-owned checkout attribution: `POST /billing/paddle/checkout-session` issues an
  opaque `session_token`; webhook resolves user identity via that token, not `custom_data.user_id`.
- 7-day past-due grace period (migration 041) per the refund policy already shown to users.
- Customer portal `POST /api/v1/billing/customer-portal` is fully implemented (not 501).
  It remains unverified against live sandbox until the smoke test step 9 is completed.
- `BILLING_MODE` stays `manual` until owner explicitly sets `BILLING_MODE=paddle` on Render.
- Migrations 040 + 041 must be applied to Neon **with explicit owner approval** before activation.

#### Consequences

- Positive: clean single-provider billing, secure identity attribution, grace period honoured.
- Negative/trade-off: customer portal is implemented but unverified against live sandbox.
  Manual/WhatsApp mode remains the fallback until `BILLING_MODE=paddle` is set.

#### Follow-up

- [ ] Paddle Sandbox smoke test (10-step checklist in `AI_WORKSPACE/HANDOFFS/paddle_billing_setup_rollback.md`)
- [ ] Independent code review (Codex / second reviewer)
- [ ] Owner explicit approval to apply migrations 040 + 041 to Neon production DB
- [ ] Owner explicit approval to set `BILLING_MODE=paddle` on Render

### DEC-20260710-004 — `/onboarding` is the real authenticated first-run setup flow (supersedes "chat is the app" routing for `/onboarding` only)

Status: accepted
Date: 2026-07-10
Owner: Roben (owner) / Claude
Related task: Onboarding restoration + Atelier migration (branch `claude/onboarding-restore-atelier`)

#### Evidence correction (2026-07-10) — supersedes the completion-signal claims below

The original evidence in this decision named `ProfileResponse.profile_exists` as the
"canonical persisted onboarding-completion signal." **That is incorrect and is corrected
here.** The prose below is kept verbatim for traceability; where it conflicts with this
note, **this note wins.**

1. **`profile_exists` means career data exists — it does NOT mean onboarding is complete.**
   It is `True` whenever *any* career-profile data is present (a partial profile, a
   merged-guest profile, one skill, one target role, or CV evidence). It is not a
   completion signal.
2. **Persisted onboarding status is the primary completion signal.** The repository
   already has the real system: table `rico_onboarding_states` (statuses
   `pending` / `in_progress` / `completed`) with `get_onboarding_state(user_id)`,
   `is_onboarding_complete(user_id)`, and `set_onboarding_status(user_id, status)`.
3. **The backend minimum-profile gate is the canonical readiness evaluation.**
   `src/services/profile_context_resolver.py::evaluate_minimum_profile` is the single
   source of truth for "is this profile ready." `POST /api/v1/onboarding/submit` already
   runs this gate and persists `completed` or `in_progress` accordingly.
4. **No frontend duplication of `evaluate_minimum_profile` is allowed.** Next.js must NOT
   re-implement completion rules. It reads the decision from the backend.
5. **Exposed signal:** `GET /api/v1/onboarding/status` (read-only, authenticated) returns
   `{status, complete, source, missing_fields, profile_exists, profile_completeness}`.
   Legacy/merged users with no `rico_onboarding_states` row are resolved via the gate and
   reported with `source: "derived_legacy"` (a GET never backfills status).
6. **Filename correction:** the redirect lives in **`apps/web/next.config.js`** (this
   decision and the handoff originally wrote `next.config` / `next.config.mjs`).

#### Context

`apps/web/next.config` 307-redirects `/onboarding → /command`, grouped with other "deprecated user-facing routes redirect to /command (chat is the app)" routes (`/dashboard`, `/jobs`, `/signals`, `/archive`, `/saved-searches`, `/orchestrate`). This made the real, working 466-line `apps/web/app/onboarding/page.tsx` (CV upload → profile confirm → done, wired to `uploadCV` / `submitOnboarding` / `fetchMe`) unreachable dead-UI. The approved `/design-preview` direction requires a real onboarding flow, directly conflicting with the redirect. Owner reviewed the evidence and chose to re-enable + migrate onboarding.

#### Decision

This decision supersedes the "chat is the app" routing deprecation **for `/onboarding` only**:

- `/onboarding` becomes the real authenticated first-run setup flow.
- `/command` remains Rico's primary application after onboarding. **This does NOT authorize any `/command` redesign.**
- Remove **only** the `/onboarding → /command` redirect from `next.config`. **Keep all other deprecated-route redirects unchanged.**

Required user flow:

1. Create account → 2. verify email (where required) → 3. sign in → 4. if onboarding/profile setup is **incomplete**, route to `/onboarding` → 5. if setup is **already complete**, route directly to `/command` → 6. after successful onboarding, route to `/command` → 7. "Skip for now" also routes to `/command` **without** falsely claiming profile completion → 8. returning completed users must **not** be forced through onboarding again.

Completion signal (from repo evidence): `GET /api/v1/rico/profile` → `ProfileResponse.profile_exists` is the canonical persisted signal. `GET /api/v1/me` (`MeResponse`: email/role/authenticated/guest/name) carries **no** onboarding flag. **Do not invent a new completion flag or schema** unless no reliable existing state exists; `profile_exists` is the existing signal.

#### Consequences

- Positive: delivers the approved onboarding design; real flow + APIs already exist (low restore risk).
- Trade-off: changes post-signup routing behavior; must gate on `profile_exists` so completed users skip onboarding.
- The misleading `/dashboard?skip=1` completion/skip destinations in `onboarding/page.tsx` (3 usages) must become `/command` (`/dashboard` itself redirects to `/command`, and `?skip=1` falsely implies completion).

#### Follow-up

- [ ] One focused PR: restore `/onboarding` reachability + migrate to Atelier + fix routing (see handoff `2026-07-10-fe-onboarding-restore-atelier.md`).
- [ ] Do NOT begin workspace/dashboard migration until this PR is merged and production-verified.

### DEC-20260710-003 — Landing rates section stays omitted; `/subscription` is the single pricing source of truth

Status: accepted
Date: 2026-07-10
Owner: Roben (decision) / Claude (recorded)
Related task: landing content completion follow-up to #936/#937/#938/#939

#### Context

The approved `/design-preview` prospectus (see `DEC-20260710-002`) includes an on-page
"Rates" section using **editorial** plan names — **Reader / Correspondent / Editor** (AED
0 / 29 / 49) from `rico-lovable-source.zip → src/lib/landing-content.ts → EN.rates`. The
live product prices those same tiers under **billing-facing** names — **Free / Pro /
Premium** — defined in the backend (`src/schemas/subscription.py` `PlanTier`; Stripe price
IDs keyed to `pro`/`premium` in `src/services/subscription_webhook_service.py`) and
rendered by `apps/web/app/subscription/page.tsx` (+ `apps/web/lib/translations.ts`
`planProName`/`planPremiumName`). Prices align exactly; only the **names** differ. The
production landing (`apps/web/components/LandingPageV2.tsx`) currently has **no** on-page
rates section and routes nav "Rates" → `/subscription`.

#### Decision

**Option D — keep the landing rates section omitted for now.**

- Do not add an on-page rates section to the landing.
- Landing "Rates" navigation continues to route to `/subscription`.
- `/subscription` remains the **single source of truth** for pricing and plan names.
- Do not mix editorial names (Reader / Correspondent / Editor) with billing-facing names
  (Free / Pro / Premium) anywhere user-facing.
- If an on-page rates teaser is ever added, it **must** use the billing-facing names
  (Free / Pro / Premium) — or explicitly map to them — and only after owner approval and a
  follow-up decision record.

#### Consequences

- Positive: no duplicated pricing content; no editorial-vs-billing name mismatch at
  checkout; no pricing/name drift risk; user trust and billing integrity protected; one
  canonical pricing surface.
- Trade-off: the landing has no on-page rates teaser (the reference intended one); revisit
  only if the owner wants it, under the naming constraint above.

#### Follow-up

- [ ] Revisit an on-page rates teaser only on owner request, using billing-facing names.
- [ ] Any future rates work is YELLOW (pricing/rates naming, billing-facing copy) and must
      not read/alter live billing data without owner approval.

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

#### Why this supersedes the narrower Phase 1 interpretation

`DEC-20260710-001` was read as "visual-only, landing below-the-fold first," and #933 was built
that way. The owner has stated that reading **under-scoped the approved target**: the goal was
never partial landing polish or an "inspired-by" restyle. This decision **supersedes that
narrower interpretation** and sets the target to **full `/design-preview` parity**. The
delivery *mechanism* from `DEC-20260710-001` (small per-route PRs, per-phase owner visual
approval, single-revert rollback) is kept; only the *scope* is corrected — from a landing
paint job to reproducing the whole package's shape, content, sections, routes, and flows.

#### Decision

1. **`/design-preview` is the approved production target for shape, content, and flows** — not
   merely palette/typography, and not partial landing polish. This **supersedes the narrower
   Phase 1 reading of** `DEC-20260710-001` and expands it. Concretely the target includes:
   - visual language (paper/ink/one-red; Fraunces · Inter · IBM Plex Mono)
   - content structure and sections
   - routes and page flows
   - EN/AR coverage where applicable
   - desktop/mobile behavior
   - **missing production pages/sections are designed and built to match the approved package.**
   The phased, per-route, owner-gated delivery model from `DEC-20260710-001` is retained.
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
   kit → PR 1 public landing (full parity) → PR 2 auth → PR 3 support/legal (preserve legal
   copy) → PR 4 onboarding (after the hybrid-state fix) → PR 5 workspace read surfaces → PR 6
   workspace action surfaces (billing-gated) → PR 7 command/chat (own DEC).
5. **PR #933** (landing below-the-fold cream) does **not** merge as a partial below-the-fold
   polish PR. Exactly one of these must be chosen by the owner (pending):
   - **(a) revise #933 into full public-landing parity** (masthead + hero + content) — requires
     unfreezing the landing hero (under the #871 freeze) and ruling on draft #899 (hero polish); or
   - **(b) close #933 and start a clean full-parity PR** off the shared Atelier kit (PR 0); or
   - **(c) keep #933 as a draft reference only** (does not merge).
   Recommendation: (a) revise-in-place if the hero is unfrozen, else (c).

#### Guardrails (binding for every migration PR)

- `/design-preview` (live + repo source) is the **single source of truth**.
- **No improvising a separate theme; no "inspired-by" implementation** — match the package.
- **One objective per PR**; no mixed concerns.
- **Owner visual approval required per phase**, before each merge.
- **No backend/auth/billing/Neon/schema changes without explicit approval.**
- **No fake live actions** — actions keep their existing path or are visibly disabled.
- **Sample/demo data must be labelled or removed** (wired to existing endpoints or clearly marked).
- **Legal copy cannot change without legal review** (`/privacy`, `/refund-policy`, `/terms`).
- **Command/chat requires a separate DEC** before any production redesign.
- No shadcn/ui without its own DEC — rebuild on the existing Tailwind stack.

#### Acceptance criteria (per migration PR)

- Side-by-side with its `/design-preview` reference, the route matches shape + content +
  sections + flow (not just palette); EN/AR where the package ships it; desktop + mobile.
- `npm run build` passes; no new test failures vs the known baseline; 0 app console errors;
  no horizontal scroll on mobile.
- Diff stays within the PR's one objective; guardrails above all hold.
- Owner approves the Vercel preview before merge; post-merge production smoke on the route.

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

Status: superseded (by DEC-20260716-001)
Date: 2026-07-09
Owner: Roben
Related task: Atelier Console gallery reference (#924)

> **Superseded by DEC-20260716-001 (2026-07-16):** this decision's
> preview/exploration-only stance — Atelier as *candidate* workspace direction
> while Nocturne stays in production and Rico carries two workspace design
> languages — is retired. Atelier V3 is now the sole production-wide system
> (dark mode "Atelier at Night"), production `/command` and the authenticated
> workspace included. Retained for history only. (`/design-gallery` and
> `/rico-preview` remain internal reference-only, as this decision already
> required.)

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

# 899/#872/#873/#908/#909/#446 Stage 2, does not close any issue, and does not reprioritize the

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

Status: superseded (by DEC-20260716-001)
Date: 2026-07-08
Owner: Roben
Related task: design-handoffs review (command-concept-sandbox)

> **Superseded by DEC-20260716-001 (2026-07-16):** the Atelier/marketing ÷
> Nocturne/workspace split below is retired. **Atelier V3 is now the sole
> production-wide visual system** across marketing, auth, the authenticated
> workspace, and `/command`; dark mode is "Atelier at Night" on the same
> semantic tokens; Nocturne is historical/archive. This decision is retained for
> history only.
>
> (Was previously amended for preview/exploration only by DEC-20260709-006,
> which is itself now superseded by DEC-20260716-001.)

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

- `agent_runtime.handle_action()` + `POST /api/v1/actions/{action}` (idempotent,
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
