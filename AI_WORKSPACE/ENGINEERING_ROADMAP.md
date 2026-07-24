# Engineering Roadmap

> The top-level map from Rico's product vision to the next safe engineering
> increment. This roadmap records current sequencing, not every historical PR.
>
> `PROJECT_STATUS.md` and live repository/deployment evidence win whenever this
> file becomes stale.

## Verified roadmap snapshot

**Date:** 2026-07-25  
**Live `main`:** `97c5f6f62e863fb97ed0e08c9e88a7f57d167b67`  
**Current posture:** reliability, truthful execution, and control-plane cleanup
before new feature expansion.

## Roadmap hierarchy

```text
Vision          AI Career Operating System
   ↓
Architecture    FastAPI + Next.js + Neon + provider abstraction
   ↓
Roadmap         this file
   ↓
Epic            long-lived product outcome
   ↓
Milestone       shippable capability block
   ↓
Phase           ordered execution stage
   ↓
PR              one reviewable objective
   ↓
Task            concrete work tracked in TASKS.md
   ↓
Release         exact commit verified in production
```

Binding decisions live in `AI_WORKSPACE/DECISIONS.md`. Current operational truth
lives in `PROJECT_STATUS.md`; active work lives in `TASKS.md`.

## Product vision

Rico is an **AI Career Operating System**, not a generic chatbot and not a set of
disconnected job-search screens.

The system must improve:

- career memory and evidence;
- trustworthy job discovery;
- explainable matching;
- application lifecycle operations;
- user-controlled follow-up and career execution;
- UAE/GCC career intelligence;
- user trust through explicit provenance and persisted-state confirmation.

## Governing engineering principles

1. Production stability and user trust come before roadmap speed.
2. Never claim a save, approval, application, subscription, or external action
   succeeded unless canonical persisted state proves it.
3. One objective per PR, with exact-head tests and a rollback path.
4. Prefer current repository contracts over prototype code or stale documents.
5. No architecture drift: evolve FastAPI, Next.js, Neon, workers, and the AI
   provider abstraction rather than introducing parallel systems.
6. An open PR or design proposal is not authorization to merge or implement.
7. Deployment success is not equivalent to authenticated product smoke.

## Current phase map

Status legend: ✅ delivered · 🔵 active · 🟡 gated/planned · ⬜ deferred

### Phase 0 — Governance and control plane 🔵

**Goal:** keep AI_WORKSPACE, PR ownership, deployment evidence, and task
traceability synchronized.

**Delivered**

- Repository operating rules, decision records, task ledger, and PR governance.
- Trust-first CEO decision `DEC-20260723-001`.
- Current docs-only reconciliation of `PROJECT_STATUS.md` and this roadmap,
  supported by a dated evidence record.

**Current gap**

- `CURRENT_STATE.md` and the large historical `TASKS.md` still contain stale
  active-state headers. They are retained to avoid destructive history loss and
  require a dedicated append-only or structure-preserving reconciliation pass.
- Until then, `PROJECT_STATUS.md` is the mandatory current control panel.

**Exit gate**

- Docs reconciliation PR reviewed and merged.
- No unresolved conflict between live state and the mandatory control panel.
- Structure-preserving reconciliation of `CURRENT_STATE.md` and `TASKS.md`
  completed in a separate docs-only change.

---

### Phase 1 — Trust, provenance, and canonical context ✅

**Goal:** Rico must know where information came from and must not invent or
misattribute job, CV, attachment, or search state.

**Verified delivered work**

- `#1364` — latest-attachment-wins continuation and redemption guard.
- `#1365` — canonical latest-attachment context and type clarification.
- `#1366` — explicit per-attempt search provenance.
- `#1367` — job-result deduplication using canonical identity with source
  provenance retained.
- `#1368` — OCR content cannot independently trigger discrimination-safety
  refusals.

**Ongoing rule**

Any new search, CV, document, or reasoning feature must preserve source,
confidence, unknown/unverified handling, and user-visible honesty.

---

### Phase 2 — Application lifecycle truth 🔵

**Goal:** every user-visible lifecycle action resolves through the canonical
application state and only confirms what persistence proves.

**Verified delivered work**

- `#1369` — chat Save and Prepare route to canonical Applications persistence.
- `#1373` — Applications board and `/queue` accessibility polish.
- `#1373` — approval receipt is gated on explicit persisted backend status;
  ambiguous outcomes stay unconfirmed and do not repeat the mutation.

**Current work**

- Production verification remains narrower than the full lifecycle. A broad
  authenticated smoke of save → prepare → approve/reject → board visibility was
  not run in this reconciliation.

**Exit gate**

- Canonical application records are visible across chat and board surfaces.
- No false success language.
- Authenticated production smoke covers the full lifecycle.

---

### Phase 3 — Secure product access and operator surfaces 🔵

**Goal:** expose necessary account/operator views without weakening identity,
authorization, or billing truth.

**Verified delivered work**

- `#1372` — owner-only, read-only subscriber administration surface.
- Authorization is based on immutable canonical user id via
  `RICO_OWNER_USER_ID`, not email.

**Current blocker**

- The frontend reads `/api/v1/me`, while `#1372` exposed `is_owner` on
  `/api/v1/auth/me`.
- `#1375` is the focused activation fix for the canonical endpoint.

**Next exact milestone**

```text
Review #1375
→ authorized merge
→ deploy exact commit
→ owner /me.is_owner=true
→ Subscribers nav visible
→ /admin/subscribers loads
→ non-owner remains false and blocked
```

**Related gated work**

- `#1370` proposes a public, read-only `/pricing` route reusing the current
  authoritative plan catalog. It must be rebased to current `main`, rerun, and
  reviewed after the activation defect is closed.

---

### Phase 4 — Explainable career intelligence 🟡

**Goal:** explain matches, missing requirements, evidence, and uncertainty using
real profile/CV/job sources.

**Current state**

- Existing modules and provenance foundations support parts of this direction.
- `#1374` is a docs-only competitive-differentiation gap analysis.
- `#1374` is a proposal, not implementation authorization.

**Required first implementation contract**

When approved, the smallest safe slice should:

- extract required vs. preferred job requirements;
- compare against profile and active CV evidence;
- cite source text and confidence;
- mark unknown/unverified facts;
- avoid negative inference merely because evidence is absent;
- add one focused PR and evaluation set.

**Gate**

No implementation begins until the current reliability/control-plane queue is
resolved and the owner approves a scoped task.

---

### Phase 5 — UX and accessibility hardening 🔵

**Goal:** improve usability without changing business logic or introducing a
second design system.

**Current open work**

- `#1376` — focused Profile UX/accessibility polish.
- `#1362` — Command quick-action category hints; needs rebase and priority
  reassessment.
- `#1359` — warning contrast plus workspace theme persistence; mixed scope must
  be split or explicitly accepted before review.
- `#1371` — mixed design-reference branch; production Applications/queue work
  was extracted into merged `#1373`, so the branch must not merge as-is.

**Rules**

- Atelier/current production components remain authoritative.
- Design references may guide implementation but are not copied into runtime.
- No fabricated data, progress, agent steps, or capabilities.
- Accessibility and mobile/RTL evidence are part of acceptance, not polish after
  merge.

---

### Phase 6 — Notifications, inbox, and proactive follow-up ⬜

**Goal:** provide user-controlled reminders and job-related inbox intelligence
only after lifecycle truth and privacy controls are proven.

**Current state**

Not active in this roadmap snapshot. Historical Gmail/notification work exists,
but production activation and current feature-flag state were not verified here.
Do not resume or expand it from stale documentation.

**Required gates**

- explicit user consent;
- least-privilege read scopes;
- review-before-write behavior;
- duplicate/rate guards;
- clear retention and privacy contract;
- canonical application lifecycle integration.

---

### Phase 7 — Infrastructure evolution ⬜

**Goal:** evolve deployment, workers, queues, caching, and observability only
when measured product load requires it.

**Current verified facts**

- Vercel production is `READY` on `main` commit `97c5f6f`.
- GitHub reports successful Vercel and Railway service statuses.
- This reconciliation did not query the live backend `/version` or independently
  confirm the current production backend host.

**Decision**

No infrastructure migration or redesign is authorized by this roadmap snapshot.
Repository evidence and full production smoke must precede any change.

## Current milestones

| Epic | Milestone | State | Next evidence gate |
| --- | --- | --- | --- |
| Trust Engine | Search and attachment provenance | ✅ delivered | Preserve in every new feature |
| Career Operations | Canonical application lifecycle | 🔵 active | Full authenticated lifecycle smoke |
| Operations | Owner subscriber visibility | 🔵 blocked on `#1375` | Owner/non-owner production smoke |
| Commercial Surface | Public pricing transparency | 🟡 PR `#1370` gated | Current-main rebase, exact-head CI, owner review |
| Career Intelligence | Explainable matching and missing requirements | 🟡 proposal | Scoped owner-approved PR + eval set |
| Experience | Incremental UX/accessibility | 🔵 active | Small PRs, no mixed scope, EN/AR/mobile evidence |
| Proactive Operations | Inbox/notifications | ⬜ deferred | Consent/privacy/lifecycle gates |
| Infrastructure | Scaling evolution | ⬜ deferred | Measured need and production plan |

## Release record — latest verified `main` sequence

| Commit | PR | Release content |
| --- | ---: | --- |
| `97c5f6f` | `#1372` | Owner-only subscriber administration surface; activation defect tracked in `#1375` |
| `8ddc0f9` | `#1373` | Applications/queue accessibility and persisted approval proof |
| `8fd87e9` | `#1368` | OCR discrimination-safety trigger correction |
| `b84d527` | `#1365` | Attachment provenance slice 2 |
| `335fc24` | `#1364` | Attachment provenance slice 1 |
| `34f8cb1` | `#1369` | Canonical chat Save/Prepare persistence |
| `c044053` | `#1367` | Search deduplication and provenance |
| `7603c8e` | `#1366` | Per-attempt search provenance |

Vercel production is confirmed `READY` on `97c5f6f`. Broader authenticated
production behavior remains unverified in this reconciliation and must not be
inferred from this release table.

## Next execution sequence

```text
1. Merge this docs-only workspace reconciliation after review.
2. Review #1375 on exact head.
3. Obtain explicit merge authorization for #1375.
4. Deploy and perform owner/non-owner production smoke.
5. Triage #1371 as reference-only/superseded; do not merge as-is.
6. Rebase and review #1370, #1359, #1362, and #1376 independently.
7. Run the broader authenticated application/profile/CV/AR/mobile smoke gate.
8. Complete structure-preserving CURRENT_STATE.md and TASKS.md reconciliation.
9. Only then approve the next product capability or explainability slice.
```

## Roadmap maintenance contract

Update this file when:

- a phase materially changes;
- a milestone reaches production or becomes blocked;
- an owner decision changes priority;
- infrastructure or billing truth changes;
- a proposal becomes an approved task.

Do not add another contradictory active snapshot. Replace current state and rely
on Git history for historical versions.
