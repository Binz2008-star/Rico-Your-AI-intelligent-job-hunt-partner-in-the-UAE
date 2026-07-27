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

## Where Rico is right now (2026-07-26)

> This snapshot is authoritative alongside `PROJECT_STATUS.md` (the control panel);
> if they ever disagree, `PROJECT_STATUS.md` + live `main` win. Snapshots dated
> 2026-07-16 and earlier are **historical** (superseded).
>
> **`main` `ca266366` (2026-07-26).** Production serves this commit: the Central
> Controller read `/version.commit` = `ca266366…` and `/health` = ok, with
> `jooble`, `adzuna` and `jsearch` configured and **not** degraded and the
> DeepSeek precheck reachable. That read is **verified by the Central Controller
> via browser, not reproducible from an agent container**, whose egress to the
> Render host is blocked.
>
> Landed since `fc2e107d`, in merge order: #1402 control-plane reconciliation
> (`805dd4d6`, docs-only), #1398 fail-closed on ambiguous account ownership
> (`70c2af7c`), #1404 never overwrite a stored `rico_users.email` on a generic
> upsert (`97af6ded`), #1406 identity-ownership boundary tests into the pytest
> gate (`42c3b976`, CI-only), #1408 roadmap truth restored (`1c13147f`,
> docs-only), #1412 a phone number is not proof of who someone is (`701939fa`),
> #1411 fail when a test file is run by no pytest invocation (`a610b696`,
> CI-only), #1414 a guest row is not a candidate on the email or Telegram path
> (`ca266366`).
>
> **The identity-ownership track is the substance of this stretch.** #1398
> established that ambiguous ownership fails closed; #1404 stopped a generic
> upsert overwriting a stored account email; #1412 and #1414 removed guest rows
> from candidacy on all three identity finders and stopped a phone number, on
> its own, from auto-attaching a Jotform submission to an account. #1411 closed
> the meta-gap those PRs kept exposing: a test file that no workflow runs.
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
| **Where is Rico?** | `main` `dac8d8e7` (head re-anchored 2026-07-27). `/command` is the full **Atelier** surface (paper + Atelier at Night, editorial serif replies) — `DEC-20260716-001` merged. #963 CV-persistence + Paddle #1008 shipped long ago (Paddle merged, NOT activated). |
| **Posture?** | **Trust-first**, per `DEC-20260723-001`: no new feature expansion until trust and execution reliability are repaired. Identity-ownership hardening has been the active track and its merged slices are listed above. The 2026-07-16 CONTAINMENT framing — security-first → #1068 source-of-truth unification → resume — is **historical and superseded**; #1068 is not the next action. |
| **What is blocked / frozen?** | New-integration activation is frozen. #1062 (Atelier job cards — HELD, has logged colour/AR/test gaps), #1055 Gmail M0 (**merged 2026-07-17**, `RICO_ENABLE_GMAIL_SYNC=false` — activation still gated on Google restricted-scope verification, Render env provisioning, migration 043, and a separate fleet-sweep PR), #1025 Memory M1 (Draft, flag OFF). Owner P0: rotate the exposed local `rico-job-automation-api.env` secrets. |
| **What is completed (recent)?** | Atelier `/command` (#1048/#1060/#1061), decision-regression harness (#1056), security hardening (#1058), attachment/SSE/transcript fixes, `DEC-20260716-001` (#1059), operational reconciliation (#1063). |
| **What comes next?** | **PR1 Chat Job Provenance Contract is delivered and released** (#1416, `dac8d8e7`). The next slice in the approved **PR1 → PR5** sequence under Phase 2 — Hardening below is **PR2 — fail-closed job-search routing and buffered delivery**, which is **planned and not started**; nothing here authorizes beginning it. The former answer (#1068 → owner secret rotation → #1066 + #1067) is **historical and no longer the execution order**; it is not deleted from the record, but it must not be read as the next action. |

Production is stable: Render backend healthy (`/health` ok, providers configured),
Vercel frontend up. The batch-row-isolation hardening fix (#887) is live.

Except for the head SHA, the posture row and the "what comes next" row — all
three re-verified at `ca266366` in this pass — the rows in this table are dated
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
- Next candidates: unify the legacy profile-CV rule across the files surface and CV
  resolution so one user gets one answer (its acceptance check is the strict xfail
  above); any gap surfaced by continued Audit Phase 2–9 verification.

#### Approved forward sequence — PR1 → PR5

Owner-approved execution order. It sits in **Phase 2 — Hardening** because every
slice is a correctness contract, not a feature; **Phase 3 — Chat Integration is
the consumer**, not the owner, of what these produce. Recorded here only: it is
deliberately absent from `PROJECT_STATUS.md` and `TASKS.md`, which carry current
lane state rather than forward plans.

**PR1 is delivered and released. PR2 → PR5 remain a plan, not a claim of work
done.**

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

**PR2 — fail-closed job-search routing and buffered delivery. ⬜ Next planned
slice — NOT started and NOT authorized by the PR1 release.** Routing refuses
rather than guesses, and delivery is buffered so a partial result is never
presented as a complete one.

**PR3 — remaining builder adoption, in small groups.** The other emit sites move
onto the PR1 contract a few at a time, each group independently revertable.

**PR4 — role and location extraction with one central UAE vocabulary.** One
vocabulary, one place; today the knowledge is scattered across call sites.

**PR5 — provenance persistence, with its own migration.** Last, because
persisting a contract before it has stabilised writes the wrong shape into the
database. Its migration is its own and is not folded into an earlier slice.

```text
EPIC        Career Operating System
  └ Milestone   Operational Memory
      └ Phase       Hardening (Phase 2)
          └ PR          #1399 — documents inventory contract (merged `fc2e107d`)
              └ Task        documents-inventory-contract
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

_Merged to `main` (`80e246b`), deploy verification pending: #885 (follow-ups
endpoint) and #891 (chat follow-up readiness). Promote each to a release row once
`/version.commit` on Render reads `80e246b…` and `/health` is ok._

_Add a row when a runtime change is deployed and verified (`/version.commit`
matches `main`, `/health` ok). Docs-only merges are not releases — #1402
(`805dd4d`) is docs-only and earns no row._

---

## How to update this file

- Move a phase to ✅ only when its milestone's PRs are merged **and** any runtime
  change is deployed + verified.
- When a phase becomes current, mark it 🔵 and list delivered PRs + next candidates.
- Record each production deploy in the Releases table.
- Keep phase names stable; this file is the map contributors trust.
