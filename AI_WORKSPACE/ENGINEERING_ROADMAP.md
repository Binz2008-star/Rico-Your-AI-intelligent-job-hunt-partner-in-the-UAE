# Engineering Roadmap

The single map of the whole project: where Rico is, where it is going, what is
blocked, what is completed, and what comes next. Any agent or contributor should
be able to read this file and orient in under a minute.

This is the **top-level spine**. It sits above the other workspace docs:

```text
Vision          AI_WORKSPACE/PROJECT_BRIEF.md · CAREER_OS_VISION.md
   ↓
Architecture    AI_WORKSPACE/ARCHITECTURE.md  (how the system is / will be built)
   ↓
Roadmap         THIS FILE                     (phases 0–7, status, what's next)
   ↓
Epics           long-lived product themes (below)
   ↓
Milestones      shippable capability blocks
   ↓
PRs             one reviewable change each (GitHub)
   ↓
Releases        what actually reached production
```

Decisions that shape the roadmap live in `AI_WORKSPACE/DECISIONS.md`. The task
ledger lives in `AI_WORKSPACE/TASKS.md`. The near-term execution gate is
`AI_WORKSPACE/AUDITS/2026-07-08-production-hardening-audit.md` — read it before
starting any feature, redesign, worker, notification, or infrastructure work.

---

## Where Rico is right now (2026-07-28)

> This snapshot is authoritative alongside `PROJECT_STATUS.md` (the control panel);
> if they ever disagree, `PROJECT_STATUS.md` + live `main` win. Snapshots dated
> 2026-07-16 and earlier are **historical** (superseded).
>
> **`main` `383dcb6c` (2026-07-28).** Production serves this commit: `/version.commit`
> matched `383dcb6c` and `/health` returned 200 / ok, with `jooble`, `adzuna` and
> `jsearch` configured and **not** degraded. `Deploy Render Backend` run
> `30367283239` is green for that exact commit, and the backend process
> `started_at` is `2026-07-28T14:15:33Z` — so this is the new process, not a stale
> one. Evidence class is an **automated endpoint read taken by the reconciliation
> session**; the earlier claim that such a read is "not reproducible from an agent
> container" is withdrawn. It is still **not a regression gate**. **No deliberate
> CV-store failure smoke and no CV-analysis routing smoke were performed**, so the
> paths changed by #1425 and #1426 have unit/frontend-test coverage only in
> production terms.
>
> Landed since `dac8d8e7`, in merge order: #1417 control-plane reconciliation
> (`1592162e`, docs-only), #1405 ambiguous ownership mapped to 409 on onboarding
> status and CV upload (`20037d2c`), #1410 central chat ownership resolver
> (`2757f53b`), #1418 session-switch/send race (`b7e3aedc`, **`apps/web/`
> frontend only**), #1370 public pricing page (`4f1af6bc`, `apps/web/`), #1419
> **PR2** fail-closed job-search routing and buffered delivery (`1ea1d973`),
> #1420 identity email containment coverage enforced in CI (`0d826b31`, CI-only,
> identity-containment track), #1421 degraded early-exit lifecycle state
> correction (`3f2805de`), #1422 **Journey-1 D3** truthful CV read-failure
> handling (`c64aa99`), #1423 control-plane reconciliation (`4ce4add8`,
> docs-only), #1424 Journey-1 CV routing characterization (`594a4d3b`, **tests
> only**), #1425 My Files unavailable-store truthfulness (`39b44696`, `src/` +
> `apps/web/`), #1426 CV-analysis routing and Arabic/English verified-absence
> parity (`383dcb6c`).
>
> **Three things define this stretch.** The approved forward sequence advanced by a
> whole slice — **PR2 is delivered as #1419**. The CV surface gained a truthfulness
> invariant in #1422: **READ FAILURE != VERIFIED ABSENCE.** And that invariant was
> then **characterized and extended**: #1424 pinned what the Journey-1 CV paths
> actually do before any extraction, and the two defects it exposed were fixed in
> their own scoped PRs — #1425 stopped My Files rendering an unreadable store as an
> empty account, and #1426 stopped CV-analysis asks routing to job search, which is
> also what closed the Arabic verified-absence gap on the active-user path. The
> identity-ownership track continued onto the chat and onboarding paths in #1405
> and #1410.
>
> The per-PR narrative and lane authority live in `PROJECT_STATUS.md`
> and `TASKS.md`, which this file does not duplicate.
> The paragraph below is the **historical** 2026-07-18 snapshot, kept for
> continuity and not re-verified at this head.
>
> **`main` `4ce678b` (2026-07-18, historical).** Job-Seeker-Workspace batch merged + deployed since #1145
> (Phase 5 surfaces): #1153 English CV-vs-search routing (`14b2b2e`), #1152 `/profile`
> editorial rebuild + **visual** section rail (`cee1d63`), #1156 profile-warning
> **contrast** (`25f1944`), #1155 **Arabic** search routing (`6b62a11`, Render #389
> verified), #1151 structured `/command` replies + motion (`965dd64`), #1157
> plain-language terminology EN+AR (`4ce678b`). Per-PR detail: `TASKS.md`
> TASK-20260718-001…006. **Owner production visual smoke pending** for #1155/#1151/#1157.
> **Profile *true* section navigation is COMPLETE** — #1161 (`76e52984`, Profile
> Phase 3). **Profile *actionable* warning workflow is COMPLETE** — #1164 Phase 4A
> severity contract (`63e976d0`) + #1165 Phase 4B actionable UI (`ab707594`); plus
> #1166 numeric-field clearing (`0da1c3e2`) and #1167 route-exit dirty-state
> protection (`ae656787`) close the Profile Hardening track (2026-07-18).
> **Still open — do NOT read as complete:**
> the *full* cross-route authenticated audit (only the English routing defect fixed),
> Command Workspace, Applications/Documents/Cover-letter workspaces, Dashboard #14,
> `Sessions → Conversations`. Claude Design's UX prototype is design-only, not
> repository/runtime-verified.

| Question | Answer |
| --- | --- |
| **Where is Rico?** | `main` `8c6c421f` (docs-only, re-anchored 2026-07-28 after `#1430`); **runtime baseline `383dcb6c`**, which production serves — the gap is three docs-only merges, not deploy drift. `/command` is the full **Atelier** surface (paper + Atelier at Night, editorial serif replies) — `DEC-20260716-001` merged. #963 CV-persistence + Paddle #1008 shipped long ago (Paddle merged, NOT activated). |
| **Posture?** | **Trust-first**, per `DEC-20260723-001`: no new feature expansion until trust and execution reliability are repaired. Identity-ownership hardening has been the active track and its merged slices are listed above. The 2026-07-16 CONTAINMENT framing — security-first → #1068 source-of-truth unification → resume — is **historical and superseded**; #1068 is not the next action. |
| **What is blocked / frozen?** | New-integration activation is frozen. #1062 (Atelier job cards — HELD, has logged colour/AR/test gaps), #1055 Gmail M0 (**merged 2026-07-17**, `RICO_ENABLE_GMAIL_SYNC=false` — activation still gated on Google restricted-scope verification, Render env provisioning, migration 043, and a separate fleet-sweep PR), #1025 Memory M1 (Draft, flag OFF). **Owner P0: rotate the exposed local environment credentials — still open, and load-bearing again as of 2026-07-28. Not agent-actionable.** This is the canonical reference; other workspace documents point here rather than repeating details. |
| **What is completed (recent)?** | Atelier `/command` (#1048/#1060/#1061), decision-regression harness (#1056), security hardening (#1058), attachment/SSE/transcript fixes, `DEC-20260716-001` (#1059), operational reconciliation (#1063). |
| **What comes next?** | **PR1 (#1416, `dac8d8e7`) and PR2 (#1419, `1ea1d973`) are both delivered and released.** The Journey-1 CV routing characterization is **delivered as #1424**, and the two defects it exposed are delivered as **#1425** and **#1426**. The immediate next action is **not** PR3. **The read-only Journey-1 D1 production-data consolidation assessment is delivered and merged as `#1430`** (`8c6c421f`) — `TASK-20260728-002` in `TASKS.md`, now `done`. It read and reported. **The owner ruling that followed it has been given:** a secure row-level evidence environment is authorized and exists as a temporary Neon branch, and the successor is `TASK-20260728-003` — mapping and a **rehearsal inside that branch only**, currently `blocked` on Neon access, not on authorization. **No production Neon row mutation is authorized by any of it, and no repair is queued.** PR3 → PR5 remain planned and are **not** authorized by the PR2 release; following PR2 in sequence is not the same as being cleared to start. The former answer (#1068 → owner secret rotation → #1066 + #1067) is **historical and no longer the execution order**; it is not deleted from the record, but it must not be read as the next action. |

Production is stable: Render backend healthy (`/health` ok, providers configured),
Vercel frontend up. The batch-row-isolation hardening fix (#887) is live.

Except for the head SHA, the posture row and the "what comes next" row — all
three re-verified at `383dcb6c` in this pass — the rows in this table are dated
2026-07-16 and were **not** re-verified. Treat any other claim in them as
historical until it is re-checked.

---

## The hierarchy (how work is organized)

Rico work nests so every PR traces up to a product reason:

```text
EPIC        Career Operating System
  └ Milestone   Operational Memory
      └ Phase       Lifecycle
          └ PR          #885 — follow-up endpoint
              └ Task        list applied jobs ready for follow-up
```

- **Epic** — a long-lived product theme (months). Rarely changes.
- **Milestone** — a shippable capability block within an epic.
  No Documents milestone exists; documents work is filed under Operational
  Memory until a documents capability block is actually scoped.
- **Phase** — an ordered stage of hardening/build within a milestone (maps to the 0–7 phases below).
- **PR** — one reviewable change on GitHub. Small, single-objective.
- **Task** — the concrete unit inside a PR, tracked in `TASKS.md`.

Naming/branch/PR governance: see `AI_WORKSPACE/OPERATING_RULES.md` and
`AI_WORKSPACE/PR_QUALITY_GATE_RULES.md`.

---

## Phases 0–7

Status legend: ✅ completed · 🔵 in progress · ⬜ planned (not started)

### Phase 0 — Architecture & Governance ✅

The workspace, roadmap, audit gate, operational-memory strategy, branch/PR
governance, and naming standards that let multiple agents work without drift.

- Delivered: AI Workspace, `ARCHITECTURE.md`, DEC-20260707-001, the 2026-07-08
  production hardening audit gate, this roadmap.
- PRs: #881 (roadmap + audit reconciliation, merged).

### Phase 1 — Operational Memory Foundation ✅

Rico must never forget what it found, opened, applied to, or needs to follow up.

- Delivered: `user_job_context` persistence (migrations 018–022), operational
  memory readiness helper, follow-up readiness selection, read-only lifecycle
  follow-ups endpoint, Audit Phase 2 verification (persistence proven sound).
- PRs: #883 (readiness helper, merged), #885 (follow-ups endpoint, merged).

### Phase 2 — Hardening 🔵 (current)

Not features, not UI. Robustness, resilience, regression protection, operational
safety. Each finding becomes a small, scoped hardening PR — verify-first, and
fix only proven gaps (synthetic data only).

- Delivered: #887 — batch-row-isolation in `upsert_matches` (one malformed row
  no longer drops the whole apply-link batch); proven against real Postgres.
- Delivered, awaiting release verification: #969/#960 exact document dedupe and #975/#963
  onboarding confirmation persistence with real-Postgres coverage.
- **Delivered and released: #1399** — documents inventory contract
  (`src/domain/documents`): one statement of which documents a user has and which
  one is the active CV, adopted at a single wiring site
  (`src/api/routers/files.py`) with no behaviour change. Merged as `fc2e107d`,
  deployed and verified — see the Releases table. Milestone: Operational Memory,
  because the Career OS vision already files durable document context under
  Layer 2 Memory (`CAREER_OS_VISION.md:159`), so documents work needs no new
  milestone. Two known divergences over the legacy profile-CV rule are recorded as
  characterisation tests plus one strict xfail
  (`tests/unit/test_document_inventory_contract.py`); unifying that rule is a later
  slice and has not started.
- **Delivered and released: the identity-ownership track** — #1398 fail closed on
  ambiguous ownership (`70c2af7c`), #1404 never overwrite a stored
  `rico_users.email` on a generic upsert (`97af6ded`), #1412 a phone number is
  not proof of who someone is (`701939fa`), #1414 a guest row is not a candidate
  on the email or Telegram path (`ca266366`). Supporting CI: #1406 and #1411.
- **Delivered and released: #1416** — PR1 Chat Job Provenance Contract, the first
  slice of the approved PR1 → PR5 sequence below. Merged as `dac8d8e7`, deployed
  and production-smoked — see the Releases table.
- **Delivered and released: #1419** — PR2 fail-closed job-search routing and
  buffered verified delivery, the second slice of that sequence. Merged as
  `1ea1d973`. Its one follow-on behaviour correction is **#1421** degraded
  early-exit lifecycle state (`3f2805de`).
- **Delivered and released: the identity-ownership continuation** — #1405
  ambiguous ownership mapped to 409 on onboarding status and CV upload
  (`20037d2c`) and #1410 the central chat ownership resolver (`2757f53b`).
  Supporting CI for the identity-containment track: **#1420**
  `ci(tests): enforce identity email containment coverage` (`0d826b31`), which
  enrolled `tests/test_identity_email_overwrite_containment.py` into the required
  CI pytest invocation and removed it from `FROZEN_BASELINE` in
  `scripts/check_test_enumeration.py`. **It is not a PR2 artifact.**
- **Delivered and released: #1422** — Journey-1 D3 truthful CV read-failure
  handling (`c64aa99`), establishing **READ FAILURE != VERIFIED ABSENCE** on the
  chat CV path in English and Arabic. The structural rule it implies is owned by
  `ARCHITECTURE.md`, not by this roadmap.
- **Delivered: #1424** — Journey-1 CV routing characterization (`594a4d3b`),
  **tests only**. It satisfies the `ARCHITECTURE.md` requirement that routing and
  side-effect order be captured on the untouched tree before any extraction, and
  it is what turned two suspected problems into evidence.
- **Delivered and released: #1425** — My Files distinguishes an unavailable store
  from an empty inventory (`39b44696`): a failed inventory read answers 503 with a
  structured `files_unavailable` detail instead of `{"files": [], "total": 0}`, and
  the surface renders a distinct unavailable state with a manual Retry. This is the
  invariant above applied to the second surface that violated it. **The backend half
  is deployed; the `apps/web/` half has no independent production verification.**
- **Delivered and released: #1426** — CV-analysis asks route to `cv_analysis` with
  authoritative grounding rather than to job search (`383dcb6c`), in English and
  Arabic. It also closes the Arabic verified-absence gap on the active-user path:
  an Arabic analysis ask previously answered `cv_upload_guidance` with
  `next_action="upload_cv"` regardless of phrasing.
- Next candidates: unify the legacy profile-CV rule across the files surface and CV
  resolution so one user gets one answer — **note that its former acceptance check,
  the strict xfail in the characterization file, was converted to a passing contract
  by #1425, so this candidate now needs a new acceptance check before it is
  actionable**; the second `_looks_like_cv_intent_no_file` call site
  (`src/rico_chat_api.py:8783`), which carries no analysis-ask exemption and is
  covered by no test either way; the characterized EN/AR job-search terminal
  asymmetry; any gap surfaced by continued Audit Phase 2–9 verification.

#### Approved forward sequence — PR1 → PR5

Owner-approved execution order. It sits in **Phase 2 — Hardening** because every
slice is a correctness contract, not a feature; **Phase 3 — Chat Integration is
the consumer**, not the owner, of what these produce. Recorded here only: it is
deliberately absent from `PROJECT_STATUS.md` and `TASKS.md`, which carry current
lane state rather than forward plans.

**PR1 and PR2 are delivered and released. PR3 → PR5 remain a plan, not a claim of
work done.**

> **Position in the sequence is not authorization.** PR3 follows PR2 in this list;
> that does not make it the next action, and nothing in the PR2 release starts it.
> **The Journey-1 CV routing characterization that used to sit here is delivered**
> as #1424 (`594a4d3b`), together with the two fixes it justified, #1425 and #1426.
> The `ARCHITECTURE.md` precondition — "characterize routing and side-effect order
> before moving code" — is therefore **satisfied for the Journey-1 CV paths**, and
> for those paths only. **Satisfying it does not authorize an extraction:** no CV
> boundary is approved, and none is created by a characterization landing.
> **The read-only Journey-1 D1 production-data consolidation assessment is
> delivered and merged as `#1430`** (`8c6c421f`) — `TASK-20260728-002` in
> `TASKS.md`, now `done`. It **does not hand off to PR3.** It read and reported;
> the owner ruling it asked for has since been given, and the successor is
> `TASK-20260728-003` — row-level mapping and a consolidation **rehearsal inside
> an owner-created Neon evidence branch**, currently `blocked` on Neon access.
> **No production Neon row mutation is authorized by either task, and no repair
> is queued.** **PR3 → PR5 remain unauthorized** — neither the assessment
> merging nor the successor being authorized changes their status.

**PR1 — Chat Job Provenance Contract ✅ delivered and released**

The problem it closed: a job card could reach a user without a provable statement
of where the listing came from. Provenance is now a value the code carries, not a
convention it observes.

Shipped as **#1416**, squash-merged as **`dac8d8e7`** onto base `1c75f4d6` —
7 files, +1232/−27. Deployed and production-smoked; see the Releases table.

- Three types live **outside `src/rico_chat_api.py`**, in `src/domain/job_search`:
  `SearchExecutionEvidence`, `VerifiedJobListing`, `VerifiedJobSearchBundle`.
- `job_integrity.filter_listings` runs **exactly once, before the bundle is
  built**, in `src/services/verified_job_search.py`. It now has exactly one call
  site in the repository, so a caller never receives raw provider items.
- **Exactly one adopted consumer: `_target_role_search_response`** — one of
  **eleven** `job_matches` builders. The other ten still name jobs without a
  bundle; that is PR3, and this slice does not claim otherwise.
- **Operation identity is owned by the lifecycle store.**
  `_begin_job_search_operation` normalizes the incoming id **before** the
  lifecycle write — empty or whitespace-only becomes `None`, a valid id is
  preserved unchanged — and the store is the sole generator. No second UUID
  exists downstream. The persisted id is reused by lifecycle state,
  provider-search logging, `SearchExecutionEvidence`, the response
  `operation_id`, `search_evidence.operation_id`, and completion/cancellation.
  A store returning no id fails closed.
- **Status and listing invariants are enforced at construction**, not by caller
  discipline: `PROVIDER_UNAVAILABLE`, `CANCELLED` and `EMPTY` each require
  `accepted_result_count == 0`; `COMPLETED` requires `accepted_result_count > 0`.
- **On the adopted `_target_role_search_response` path, no verified bundle means
  no emitted matches and no job cards.** The contract target is repository-wide,
  but PR1 enforces it at exactly one consumer; the remaining builders are
  deferred to PR3. Proven fail-first — the tests failed on the base tree before
  the contract existed.
- **No feature flag.** The guarantee ships in the configuration that runs.

**PR2 — fail-closed job-search routing and buffered verified delivery ✅
delivered and released.** Routing refuses rather than guesses, and delivery is
buffered so a partial result is never presented as a complete one.

Shipped as **#1419**, merged as **`1ea1d973161b261de9463d5a1434f3d5b4928874`**.
**One** follow-on correction belongs to this slice's record: **#1421**
(`3f2805de`), which corrected the degraded early-exit lifecycle state. `#1420`
merged in the same window but belongs to the identity-containment track, not to
PR2, and is recorded there.

The previous text here described PR2 as planned and unimplemented. That was
stale from the moment `#1419` merged and is corrected, not stacked beneath.

**PR3 — remaining builder adoption, in small groups. ⬜ planned, NOT authorized.**
The other emit sites move onto the PR1 contract a few at a time, each group
independently revertable. **Do not treat this as the next action** — see the
note above the sequence.

**PR4 — role and location extraction with one central UAE vocabulary. ⬜ planned,
NOT authorized.** One vocabulary, one place; today the knowledge is scattered
across call sites.

**PR5 — provenance persistence, with its own migration. ⬜ planned, NOT
authorized.** Last, because persisting a contract before it has stabilised writes
the wrong shape into the database. Its migration is its own and is not folded
into an earlier slice.

```text
EPIC        Career Operating System
  └ Milestone   Operational Memory
      └ Phase       Hardening (Phase 2)
          └ PR          #1399 — documents inventory contract (merged `fc2e107d`)
              └ Task        documents-inventory-contract
```

#### Epic: AI Response Reliability & Performance 🔵 (started 2026-07-30)

An owner-approved, phased program. It exists because a production reply asserted
**"Your CV filename hints at a banking background."** A filename is not career
evidence. Investigation found the model was told (`content_available: true`) that
it held the user's CV while the payload carried no CV content at all, and the
only career-shaped string in reach was a filename injected without any untrusted
marker. The reply was the context working as built.

Each phase is **one PR, one objective**, in order. A later phase is not
authorized by the merge of an earlier one.

| Phase | Branch | Objective | State |
| --- | --- | --- | --- |
| 1 | `fix/ai-grounding-contract` | Grounding and evidence integrity across **every provider and prompt path**: isolate all document metadata as `*_untrusted`, load bounded verified CV evidence, make `content_available` truthful, split verified fact / market context / missing evidence, and carry the same contract onto the HuggingFace fallback leg | **MERGED** `41a95ad` (#1464) — **NOT VERIFIED**, production smoke pending — `TASK-20260730-001` |
| 1b | *(next — not started, no branch cut)* | **Context preservation under combined pressure.** Reproduce the long-conversation + large-CV case where `career_memory` (the blocked-companies constraint) is evicted from the 4000-char window; guarantee blocked-company constraints survive context assembly; define a deterministic priority order across transcript, verified evidence, career memory, profile facts and lower-priority metadata; and restore coverage for text-only CV users (`cv_text` present, `cv_structured` absent, who currently receive no evidence block). **Completes before F-3.1.** | ⬜ awaiting approval |
| 2 | `perf/ai-critical-path-latency` (F-3.1 first) | Redundant profile/document reads; cap the HuggingFace classifier where routing already proves the request is AI-bound; measure route/context/TTFT/completion | ⬜ not started |
| 3 | `feat/ai-provider-parameter-policy` | Measured parameter baseline, then `temperature` policy with a bounded env override across supported call sites | ⬜ not started |
| 4 | `feat/ai-request-tracing` | `operation_id` across request → routing → context → provider → persistence → stream; stage timing, TTFT, no PII | ⬜ not started |
| 5 | `perf/database-connection-pooling` | Re-enable pooling safely | ⛔ **BLOCKED** — requires DB-consumer audit, incident review, Neon connection-limit review, acquire/release analysis, load tests, canary plan, rollback proof. Not to be implemented in any earlier phase |
| 6 | `fix/interactive-job-search-delivery-budget` | JSearch 429 handling, interactive retry budget, partial results, stream heartbeat, persisted-vs-visible consistency. Kept **separate** from AI provider work | ⬜ not started |

Phase 1 deliberately excludes — and Phase 1's PR must not contain — HuggingFace
timeouts, provider parameters, connection pooling, tracing, JSearch, routing
logic, duplicate-read optimisation, RAG/vector storage, validator LLMs, response
post-filters, schema changes, and any deployment.

```text
EPIC        AI Response Reliability & Performance
  └ Milestone   Grounded AI responses
      └ Phase       Hardening (Phase 2)
          └ PR          Phase 1 — AI grounding and evidence contract
              └ Task        TASK-20260730-001
```

### Phase 3 — Chat Integration 🔵 (current)

Wire chat to what is already persisted — almost no new logic, just connection.

- Delivered: #891 — "what should I follow up?" / "which jobs are due for
  follow-up?" (EN + AR) → reuses the merged readiness logic
  (`get_by_status("applied")` → `select_revisit_candidates`).
- Already in chat before this phase: "show my applications", "show saved jobs",
  "what did I open but not apply to?", follow-up timing advice.
- Next candidates: a combined job-search status digest; any other lifecycle view
  not yet reachable from chat.
- Constraint: reuse existing lifecycle reads; verify-first; synthetic data only.
- **Consumer of the PR1 → PR5 sequence, not its owner.** Those slices are filed
  under Phase 2 because they are correctness contracts; chat is where their
  output becomes visible. Read the sequence in Phase 2 above before starting any
  chat-side job-provenance work, and do not re-plan it here.

### Phase 4 — Lifecycle Intelligence 🔵 (Gmail M0 merged, activation gated)

Rico stops being only a keeper and starts following up with the user, e.g.
"You applied 6 days ago — prepare a follow-up email?" / "You opened this job
three times — want to apply?"

- Merged 2026-07-17, **not activated**: **#1055** — Gmail read-only connector M0 (first-party OAuth,
  `gmail.readonly` scope, Fernet-encrypted refresh tokens, bounded inbox sync,
  propose-only review items, `RICO_ENABLE_GMAIL_SYNC=false`).
  Design doc: `docs/integrations/gmail-readonly-connector.md`.
  Milestone: Email Integration. M1 = AI-drafted follow-ups (no `gmail.compose`).
  M2 = Outlook via Microsoft Graph.

```text
EPIC        Career Operating System
  └ Milestone   Email Integration
      └ Phase       Lifecycle Intelligence (Phase 4)
          └ PR          #1055 — Gmail read-only connector M0
              └ Task        Gmail-M0-connector
```

### Phase 5 — UX Facelift ⬜

Only after the system is stable. Atelier, Rico Alive, Nocturne, and the new
design language. (Corresponds to DEC-20260707-001 "UI redesign / PR G".)
The approved target is `/design-preview` per DEC-20260710-002; migration remains
per-route and owner-gated, and resumes after the #963 release gate.

### Phase 6 — Notifications ⬜

After lifecycle exists: email, WhatsApp, reminders, weekly reports. Must honor
the Telegram audience rules (admin/dev vs user channels).

### Phase 7 — Infrastructure Evolution ⬜ (last)

Not now. Railway, worker split, queue, Redis, background processing. Render
stays the production backend until a Railway target passes full production
smoke. (Corresponds to DEC-20260707-001 PRs D/E.)

---

## How this maps to the other roadmaps

This product-level roadmap (phases 0–7) and the architecture-level roadmap in
`DECISIONS.md` → DEC-20260707-001 (PRs A–G) are two lenses on the same work,
not competing plans:

| Engineering phase | Architecture-level (DEC-20260707-001) |
| --- | --- |
| 1 Operational Memory Foundation | PR A (persist job context + apply links) |
| 2 Hardening | robustness layer over PR A/B (verify-first) |
| 3 Chat Integration | consumes persisted lifecycle (no infra change) |
| 4 Lifecycle Intelligence | builds on PR B (application lifecycle) |
| 5 UX Facelift | PR G (UI redesign) |
| 6 Notifications | notifications-only layer |
| 7 Infrastructure Evolution | PRs D/E (worker separation, Render→Railway) |

The 2026-07-08 production hardening audit remains the **near-term execution
gate**: it controls immediate stabilization (Phases 1–2) and must be read
before feature/redesign/worker/notification/infra work.

---

## What the deploy workflows actually prove

A standing property of the pipeline, not a story about any one PR. Both workflows
fire on a push to `main` that touches a runtime path — `src/**`, `migrations/**`,
`requirements.txt`, `render.yaml`, `Dockerfile.backend`, and the workflow file
itself (`.github/workflows/deploy-render.yml:8-22`); Deploy to Production adds
`apps/web/**` (`.github/workflows/deploy-production.yml:3-17`).

- **Deploy Render Backend is the commit-equality proof.** It fires the Render
  deploy hook (`deploy-render.yml:42`), then polls `/version` and requires the
  deployed `.commit` to equal the pushed SHA, failing the run if it never matches
  within ~8 minutes (`:51`, assertion at `:67`, failure at `:73-77`), then requires
  `/health` 200 (`:79`). A green run proves Render is serving *that* commit.
- **Deploy to Production does not assert the deployed SHA.** It waits a fixed 30s
  (`deploy-production.yml:30-31`), then checks backend `/health` 200 (`:33`),
  `https://ricohunt.com` 200 (`:43`), and proxy pass-through
  `https://ricohunt.com/proxy/health` 200 (`:52`). Its green is therefore
  consistent with the *previous* build still being served: it proves the stack is
  reachable and healthy, not that the new commit is live.
- **Neither workflow runs an authenticated functional smoke.** Those stay manual
  owner checks and are never a regression gate.
- **Vercel** production deployment is expected from the connected Git integration
  but is not proven by repository configuration (the repo carries no
  `ignoreCommand` and no build path filter; any dashboard-level ignored-build-step
  is not visible here), so it is verified separately after merge.

Consequence for the table below: a row is earned by a green **Deploy Render
Backend** run for that commit, not by a green Deploy to Production run alone.

---

## Releases (what reached production)

| Date | Commit | What went live |
| --- | --- | --- |
| 2026-07-28 | `383dcb6c` | #1426 — CV-analysis asks route to `cv_analysis` with authoritative CV grounding instead of to job search, in English and Arabic. `_CV_ANALYSIS_RE` gained the analysis verbs bound to `cv`/`resume`/`curriculum vitae` plus an Arabic arm requiring the `(ال)ذاتية` qualifier; `is_cv_analysis_request()` defers to the same `classify_intent` the router keys on; the upload-announce gate skips analysis asks. It also closes the **Arabic verified-absence gap on the active-user path** — an Arabic analysis ask previously answered `cv_upload_guidance` with `next_action="upload_cv"` regardless of phrasing. `Deploy Render Backend` run `30367283239` green; `/version.commit` = `383dcb6c`, process `started_at` `2026-07-28T14:15:33Z`, `/health` 200 / ok with `jooble`, `adzuna` and `jsearch` configured and not degraded. **Evidence class: automated endpoint read taken by the reconciliation session — not a regression gate, and no CV-analysis routing smoke was performed, so the changed path was not exercised in production.** This row also carries the **backend** half of #1425 (`39b44696`, My Files unavailable-store truthfulness), which reached production inside the same rolling sequence without an individual `/version` read; **no per-commit deploy evidence is claimed for it.** #1425's `apps/web/` half (`UploadAtelier.tsx`, `translations.ts`) is **present on `main`** and **not** covered by this row: a backend `/version` read does not prove a frontend deploy, and **no independent production frontend verification was taken.** #1424 (`594a4d3b`) is **tests-only and earns no release row.** |
| 2026-07-28 | `c64aa99` | #1422 — D3 truthful CV read-failure handling on the chat CV path: a failed grounding or document read is no longer rendered as "no CV", "no stored CV", unreadable-document blame, upload/re-upload guidance, or `next_action="upload_cv"`, in English and Arabic. A successful empty read is still an absence and `no_readable_content` is still a content problem. No route, migration, schema or frontend change. `/version.commit` matched `c64aa99` and `/health` returned 200 / ok with `jooble`, `adzuna` and `jsearch` configured and not degraded. **Evidence class: owner/browser-verified — not an automated artifact and not a regression gate. No deliberate CV-store failure smoke was performed, so the changed path itself was not exercised in production.** This row also carries the intermediate **backend** merges that reached production inside the same rolling sequence without an individual `/version` read of their own — #1405 (`20037d2c`), #1410 (`2757f53b`), #1419 (`1ea1d973`, PR2) and #1421 (`3f2805de`). **No per-commit deploy evidence is claimed for any of them.** The `apps/web/` frontend merges in the same window — #1418 (`b7e3aedc`, session-switch/send race, two files under `apps/web/` and explicitly no backend change) and #1370 (`4f1af6bc`, public pricing page) — are **present on `main`** and are **not** covered by this row's evidence: a backend `/version` read does not prove a frontend deploy, and **no independent production frontend verification was taken in this pass.** |
| 2026-07-27 | `dac8d8e7` | #1416 — PR1 Chat Job Provenance Contract: the verified job-search contract (`src/domain/job_search`) plus its seam (`src/services/verified_job_search.py`), adopted at exactly one consumer (`_target_role_search_response`). `/version.commit` = `dac8d8e7`, process start `2026-07-27T01:00:26Z`, `/health` ok with `jooble`, `adzuna` and `jsearch` configured and not degraded. Production-smoked on one synthetic non-PII named-role search: non-empty 39-character operation id, response `operation_id` identical to `search_evidence.operation_id`, 5 matches shown against `accepted_result_count` 10, exactly one `provider_cascade` attempt for the deliberate search turn, and execution metadata carrying no listing content. |
| 2026-07-26 | `ca266366` | #1414 — a guest row is not a candidate on the email or Telegram path (`find_profiles_by_email` and `find_profiles_by_telegram_username`, SQL predicate plus independent Python re-check, both memory fallbacks guarded). Central Controller read `/version.commit` = `ca266366` and `/health` ok, with `jooble`, `adzuna`, `jsearch` configured and not degraded and the DeepSeek precheck reachable. Browser-verified by the Controller; not reproducible from an agent container. Owner functional smoke not claimed. |
| 2026-07-26 | `a610b696` | #1411 — CI-only: fail when a test file is run by no pytest invocation, with a frozen 212-file baseline that may only shrink. No runtime path touched, so no deploy expected. |
| 2026-07-26 | `701939fa` | #1412 — a phone number is not proof of who someone is: phone removed from the signals sufficient to auto-attach a Jotform submission, and guest rows excluded from phone candidacy. Deploy fired on merge (`src/**` filter matched). Owner functional smoke not claimed. |
| 2026-07-26 | `1c13147f` | #1408 — docs-only roadmap truth restoration. No runtime path touched, so no deploy expected. |
| 2026-07-26 | `42c3b976` | #1406 — CI-only: identity-ownership boundary tests added to the pytest gate. No runtime path touched, so no deploy expected. |
| 2026-07-26 | `97af6ded` | #1404 — never overwrite a stored `rico_users.email` on a generic upsert. Deploy Render Backend `30205559710` verified `/version.commit` = `97af6ded`; Deploy to Production `30205559713` green. Owner functional smoke not claimed. |
| 2026-07-26 | `70c2af7c` | #1398 — fail closed on ambiguous account ownership. Deploy Render Backend `30184733967` verified `/version.commit` = `70c2af7c`; Deploy to Production `30184733970` green. Owner functional smoke not claimed. |
| 2026-07-26 | `fc2e107d` | #1399 — documents inventory contract (`src/domain/documents`) + one behaviour-preserving wiring site. Deploy Render Backend `30180474833` verified `/version.commit` = `fc2e107d`; Deploy to Production `30180474830` green. The authenticated documents-inventory smoke is a manual owner step and was not run. |
| 2026-07-18 | `4ce678b` | #1157 — plain-language terminology in user-facing copy (EN+AR). Deploy-to-Production #997 green; **owner visual smoke pending** |
| 2026-07-18 | `965dd64` | #1151 — structured safe-markdown `/command` replies + motion. Deploy-to-Production #996 green; **owner visual smoke pending** |
| 2026-07-18 | `6b62a11` | #1155 — explicit Arabic job search reaches the search router. Render backend deploy #389 verified serving `6b62a11`; **owner AR smoke pending** |
| 2026-07-18 | `25f1944` | #1156 — profile guardrail-warnings contrast/legibility (editorial `/profile`) |
| 2026-07-18 | `cee1d63` | #1152 — `/profile` editorial rebuild + real-data wiring (visual section rail only) |
| 2026-07-18 | `14b2b2e` | #1153 — English "find jobs that match my CV" routed to job search (not job-doc scoring) |
| 2026-07-08 | `7d167dd` | #887 — batch-row-isolation hardening (apply-link batch resilience) |

*Merged to `main` (`80e246b`), deploy verification pending: #885 (follow-ups
endpoint) and #891 (chat follow-up readiness). Promote each to a release row once
`/version.commit` on Render reads `80e246b…` and `/health` is ok.*

*Add a row when a runtime change is deployed and verified (`/version.commit`
matches `main`, `/health` ok). Docs-only merges are not releases — #1402
(`805dd4d`) is docs-only and earns no row.*

---

## How to update this file

- Move a phase to ✅ only when its milestone's PRs are merged **and** any runtime
  change is deployed + verified.
- When a phase becomes current, mark it 🔵 and list delivered PRs + next candidates.
- Record each production deploy in the Releases table.
- Keep phase names stable; this file is the map contributors trust.
