# Rico Architecture V2 — Revised Read-Only Architecture Package

> **Status: READ-ONLY PACKAGE FOR OWNER REVIEW. No code, no branches, no migrations,
> no deployments.** Produced in response to the owner verdict
> *APPROVE WITH REQUIRED REDESIGN* on the 2026-07-25 plan.
>
> Supersedes the execution order in
> `AI_WORKSPACE/proposals/2026-07-25-architecture-v2-rebuild-blueprint.md`. That
> document's audit findings stand; its sequencing (AI agent loop first) is withdrawn.

- Date: 2026-07-25
- Author: Claude (acting CTO session)
- Verdict requested at end: §12

## Evidence classification used throughout

Every material claim is tagged:

| Tag | Meaning |
|---|---|
| **[V]** | Verified — I read the file/ran the command this session; `file:line` given |
| **[O]** | Owner-reported — stated by the owner or by an accepted `AI_WORKSPACE` decision |
| **[A]** | Assumption — reasoned inference, not directly verified |
| **[M]** | Missing evidence — cannot be determined from the repository |

---

## 0. Prior-work disclosure

Before the owner's revision arrived, acting on the previously approved plan, I pushed
one commit to `claude/website-api-restructure-5gtkpg`:

- `b2b85b9` — `src/agent/llm/tool_schemas.py` + `__init__.py` (the withdrawn PR #1,
  sub-slice 1) and the earlier blueprint document. **[V]**
- No pull request was opened. No production code imports the new module — verified by
  grep; it is unreachable at runtime. **[V]**
- The branch is now **2 commits behind `origin/main`** (`3c5879f`) and 1 ahead. **[V]**

Awaiting owner instruction: leave, delete the branch, or reset it to `main`. No further
commits will be made until the owner approves this package.

---

## 1. Reframed diagnosis (per owner instruction §1)

The earlier framing — "Rico's language model cannot act at all" — is withdrawn as
imprecise. The accurate statement:

> Rico has working action runtimes and tool implementations, but the primary
> conversational LLM path is not connected to one authoritative, security-controlled
> action orchestration layer. Several incomplete or dead tool systems coexist, while
> much of conversational routing remains deterministic and concentrated inside
> `RicoChatAPI`.

Supporting evidence, all **[V]**:

| Fact | Evidence |
|---|---|
| `agent_runtime.handle_action()` is a *working* dispatcher with idempotency, audit and admin gating | `src/agent/runtime.py:67`, idempotency `:112`, privileged gate `:130`, audit `:270` |
| The tool registry holds 12 *working* tools | `src/agent/registry/tool_registry.py:80-91` |
| Runtime dispatch is genuinely tested end-to-end through real tools | `tests/test_agent_runtime.py` `_run()` → `runtime.py:226,242` |
| The conversational path reaches the model at only 2 sites | `src/rico_chat_api.py:4745`, `:8064` |
| `class RicoChatAPI` spans lines 2156–23060: 313 methods, 1,691 `if`/`elif`, 259 regex | measured this session |
| A second tool-schema system is dead and in the wrong wire format | `src/rico_openai_agent.py:408 _tool_schemas()`, `:248 execute_tool()`; `src/rico_openai_runtime.py:10` documents "* No tools." |
| A third tool system has zero callers repo-wide and a `user_id == "default"` global-profile fallback | `src/rico_tool_registry.py:92`; zero callers verified by grep across `src/`, `tests/`, `scripts/` |

**Consequence for the plan:** the objective is *not* "replace rules with an LLM". Much
deterministic logic is correct and must stay deterministic — safety policy, state
transitions, transactional rules. The objective is one trusted orchestration layer in
which deterministic policy, domain use cases, and bounded AI reasoning cooperate.

---

## 8. Dependency graph (delivered early — it explains everything below)

Measured this session by parsing every `from src.*` / `import src.*` across `src/`. **[V]**

```
services      → root           109      root         → repositories   62
transport     → root            86      root         → services       56
transport     → services        72      repositories → root           63
repositories  → root            63      root         → agent          15
transport     → repositories    52      agent        → services       12
services      → repositories    21      repositories → services        7
```

### The central finding

`src/` **root is not a layer — it is a cycle hub.** It receives 258 inbound imports
(services 109 + transport 86 + repositories 63) *and* itself imports back into
repositories (62), services (56) and agent (15). Every architectural layer both depends
on the root modules and is depended upon by them.

This — not `rico_chat_api.py`'s line count — is the reason the monolith cannot be
decomposed incrementally today. Splitting a file inside a cycle relocates the cycle.

### Concrete inversions to fix (each is an ADR candidate)

| Inversion | Evidence | Why it matters |
|---|---|---|
| Repository enforces **billing entitlement** | `src/repositories/applications_repo.py:297,360` → `services.subscription_gating.enforce_saved_job_allowed` | A commercial policy lives in the data layer; no use case can own or test it |
| Repository enforces **domain validation** | `src/repositories/profile_repo.py:55,70` → `services.city_validation.sanitize_cities` | The city write-boundary rule — a repeated production incident — is enforced below the layer that should own it |
| Repository resolves **job links** | `src/repositories/jobs_repo.py:14` → `services.job_link.resolve_job_link` | Infrastructure depends on application logic |
| Repository composes **profile context** | `src/repositories/profile_repo.py:29,30` | Same |
| Service imports **transport** | `src/services/identity_merge_service.py:25,325` → `src.api.public_identity` | Guest-capability parsing (a transport concern) is a service dependency |
| Schemas import **domain/root** | `src/schemas/job_lifecycle.py:12`, `src/schemas/actions.py:11` | Schemas should be a leaf |
| Chat controller imported by services | `src/services/chat_service.py` (6 deferred imports), `src/rico_telegram_webhook.py:10`, `src/api/routers/rico_chat.py:59,831,957` | All are *deferred, in-function* imports — the classic circular-dependency workaround, and direct proof of the cycle |

Plus two duplications maintained by comment rather than by code:
`src/services/city_validation.py:76` "Keep in sync with `RicoChatAPI._CITY_REJECT_WORDS`"
and `src/services/application_board.py:39` "mirrors `RicoChatAPI._get_status_rank`". **[V]**

---

---

## 4. State machine inventory — Documents & CV (the first migration slice)

### 4.1 There are three CV state vocabularies in play, and two of them are correct

This is the single most important finding for the owner's Phase 2, because the revision
document proposes a *fourth*.

| # | Vocabulary | States | Defined at | Status |
|---|---|---|---|---|
| A | **CV content state** — what we know about the CV's *content* | `structured`, `text_extracted`, `metadata_only`, `parse_failed`, `uploaded`, `none` | `src/services/cv_state.py:9-15,35-38` | **[O] ACCEPTED today** as `DEC-20260725-001` (owner CTO decision) |
| B | **Artifact lifecycle** — where an upload sits in the pipeline | `pending`, `already_saved`, `expired`, `absent`, `unavailable` | `AI_WORKSPACE/PROJECT_STATUS.md` acceptance criteria; `src/services/cv_context_resolver.py:11,41` | **[O]** recorded as required-distinct in the #1391 acceptance list |
| C | **Availability reason** | `store_unavailable` vs `no_cv_on_file` | `src/services/cv_context_resolver.py:41` | **[V]** implemented |
| D | *Proposed in the revision* | `received → parsed → pending_review → confirmed → persisted` (+ `rejected`, `expired`, `already_saved`, `unavailable`, `failed`) | owner revision §Phase 2 | **conflicts with A and B** |

**A and B are orthogonal, not competing** — A describes content quality, B describes
pipeline position. A file can be `pending` (B) and `text_extracted` (A) at once. The
system needs both, and conflating them is a large part of the present confusion.

**Recommendation (ADR-001):** keep A exactly as accepted — `DEC-20260725-001` is one day
old, owner-signed, and its "derive state from stored content, never from a stored label"
rule is the right invariant. Adopt B as the *separate* artifact-lifecycle axis and give
it the one decision record the owner asked for. Do **not** adopt D as written: its
`parsed` state collides with the legacy `parsed` label that `DEC-20260725-001` §2
deliberately made read-only and non-promoting, and re-introducing it as a live state
would revive precisely the defect that decision closed.

### 4.2 The pending/saved distinction is structural, and that is good

There is no `status` column. The distinction is expressed by **table separation**:
`cv_upload_artifacts` (pending, TTL-bounded) vs `user_documents` (saved). **[V]**
`migrations/038_cv_upload_artifacts.sql:56-70`.

This satisfies the owner's rule "pending artifacts do not count as saved documents" at
the schema level rather than by convention — a stronger guarantee than a status column.
It also means **no migration is required** for the pending/saved semantics, which is
consistent with the Neon preview branch showing **zero schema diff** from production. **[O]**

### 4.3 Verified answers to the owner's Phase 2 data questions

| Requirement | Finding | Evidence |
|---|---|---|
| Artifact uniqueness / dedup | **MISSING — this is the amplification cause.** The table has a PK on `id` and one index on `(user_id, expires_at DESC)`; there is **no unique constraint on `(user_id, content_hash)`**, and the insert is a plain `INSERT` with no `ON CONFLICT`. Re-uploading identical content creates a new row **holding the full CV text** every time. | `migrations/038:56-70`; `src/repositories/cv_upload_artifact_repo.py:126-131` **[V]** |
| Purge ownership | **Implemented, and better than expected — not a gap.** Every `create_cv_upload_artifact` deletes a bounded batch of expired rows *in the same transaction*, wrapped in a `SAVEPOINT` so a purge failure can never abort a valid insert. There is no background worker on Render by design. | `cv_upload_artifact_repo.py:134-145` **[V]** |
| Retention / TTL | `expires_at TIMESTAMPTZ NOT NULL`, default 3h. | `migrations/038:65`; repo docstring **[V]** |
| Residual purge risk | Cleanup is amortized on *create*. If uploads stop, expired rows are not reclaimed until the next upload. Convergence assumes create-rate ≥ expiry-rate. | derived from the same code **[A]** |
| Atomic confirmation | Not yet traced end-to-end in this pass — the write-path investigation covers it. | **[M]** at time of writing |

**Consequence for sequencing:** the owner's instruction "do not redesign migration 038"
is correct and is now evidence-backed. The one schema change Phase 2 plausibly needs is
*additive*: a unique index on `(user_id, content_hash)` (or an `ON CONFLICT` upsert), which
would collapse duplicate amplification without touching the existing shape. That is a
new migration file, not an edit to 038 — exactly as `DEC-20260725-001` §4 requires.

**Privacy note:** because each duplicate row carries the full parsed CV text, dedup is
not only a storage concern — it multiplies copies of the most sensitive payload Rico
holds. This raises the priority of the unique-index fix above "cleanup". **[A]**

---

## 6. CI reality — the most important governance finding in this package

**`main` is not tested. Not red — *unverified*.** All **[V]**.

| Fact | Evidence |
|---|---|
| `qa-tests.yml` triggers on `pull_request` and `workflow_dispatch` **only** — not on push to `main` | `.github/workflows/qa-tests.yml` trigger block |
| Total QA Tests runs ever on branch `main`: **6**, all manual dispatch. Latest `2026-07-19`, head `946341c6` | GitHub Actions history |
| **No QA Tests run exists at current `main` HEAD `3c5879f`, or at any commit after 07-19** | same |
| The `pytest` job does **not** run `tests/`. It runs an allowlist: `tests/unit/`, `tests/decision_regression/`, and ~45 individually named files | `qa-tests.yml` |
| What *does* run on push to `main`: `Workflow Security Guards`, `Deploy to Production`, `Deploy Render Backend` | Actions history |

This resolves the 27-failure discrepancy I reported earlier: those failures are **real on
the full suite and simply outside CI's scope**. Merged PR #1386's own commit message
records the same measurement independently — full-suite baseline at `7037f06` was
"32 failed, 8605 passed", after that PR "27 failed, 8612 passed". **[V]**

**Implication for the whole program:** the exit criterion "CI green" currently means
"an allowlist passed on a PR head". It does not mean `main` works. Every milestone below
that says "green" must say *which* suite, and Milestone A must close this gap — otherwise
the architecture migration would be verified by a gate that does not watch the branch it
is migrating. Issue **#1393** already records the intended path (network isolation →
full suite as shadow → then Required); this package endorses that sequence and adds:
**run `qa-tests.yml` on push to `main`**, which is a one-line trigger change and is
independent of the network work.

---

## 7. Open work disposition

Live state at `main` = `3c5879f` (docs-only). **8 open PRs, 52 open issues.** **[V]**

### The CV work already exists as PR #1389 — and the owner has already blocked it

| Field | Value |
|---|---|
| PR | **#1389**, Draft, branch `claude/cv-pending-artifact-confirm`, head `c3effba` |
| Size | 13 files, **+2369 / −30**, 11 commits |
| CI | 9/9 green at head; Vercel preview Ready; Neon preview branch zero schema diff |
| Base | `e26548b` — 2 docs-only commits behind `main` |
| Owner review | Blocking comment `5079436796` (07-25 17:14): keep Draft; **`/profile` (`ProfileEditorial.tsx`) is not in the changed-file set** and still claims upload success before confirmation; repeated identical uploads still amplify retained full CV text; rebase and re-prove exact head |

The owner's Phase 2 instruction ("do not merge #1389 as-is; classify commit-by-commit")
is therefore already consistent with the owner's own review on the PR. The commit and
file inventory needed for that classification is in the investigation output and is
reproduced in §9's disposition table.

Two facts sharpen the owner's instruction:

- **The gap the owner identified is confirmed structurally**: `ProfileEditorial.tsx`
  appears nowhere in #1389's 13 changed files, so `/profile` cannot be using the new
  orchestration. **[V]**
- **The amplification cause is now known precisely** (§4.3): no unique index on
  `(user_id, content_hash)` in `cv_upload_artifacts`. #1389 does not add one — it
  explicitly excludes the retention-window change and the bounded purge. So the owner's
  blocking point is not fixable by rebase; it needs the additive index. **[V]**

### Issues that already own parts of this program

| Issue | Why it matters here |
|---|---|
| **#1391** | P0 CV state machine — owns #1389, explicitly forbids a competing implementation. **This program must work through #1391, not beside it.** |
| **#1094** | "carry trusted actor context into agent tools; close approval/global-state bypasses" — this is the *same* defect class I found independently at `rico_safety.py:68-76` vs `apply_job`. The agent-loop safety work has an existing owner. |
| **#1393** | CI network isolation, three-phase; gates making the full suite Required. |
| **#1211** | Chat operation ownership is in-process — a stated scaling blocker. |
| **#179**, **#654** | Standing "rebuild chat backend" and "session-aware intent routing + tool orchestration" trackers — the pre-existing homes for Milestone E. |
| **#712** | Known production migration drift (005, 011) — must be reconciled before any schema work. |

**Governance consequence:** this program should be expressed as sequencing over existing
issues (#1391 → #1094 → #654/#179) rather than as a new parallel plan. That is the
`AGENTS.md` "no competing branch when an active PR exists" rule applied at program level.

---

## 3. Source-of-truth matrix — schema has two competing authorities

**[V]** The most consequential structural finding after the dependency cycle:

| Fact | Evidence |
|---|---|
| **15 tables are created by runtime Python DDL and appear in no migration** | `src/rico_db.py:67,200,234`; `src/db.py:56`; incl. `rico_users`, `rico_profiles`, `rico_job_recommendations`, **`user_documents`** |
| Migrations start at **005**; 001–004 absent from the repo | `migrations/` listing **[M]** for what they contained |
| Migration numbers **039 and 042 are missing** | `migrations/` listing jumps 038→040, 041→043 |
| **No table is ever dropped** — `DROP TABLE` appears only in comments | `031:55-57`, `038:52`, `044:30`, `049:19`, `051:33` |
| One table is created lazily *inside a write path* | `src/repositories/search_context_repo.py:277-299` |
| `settings` has two creators with different column sets | `migrations/005:8` and `src/db.py:109` |
| Startup verifies only 6 tables exist | `src/api/app.py:141-148` |

**Critical for Phase 2:** `user_documents` is created by runtime DDL (`src/rico_db.py:201`)
but its **constraints live only in migration 037** — the dedupe index
`uq_user_documents_user_type_hash` and the single-primary index
`uq_user_documents_one_primary_per_type` (`037:72-79`). Any environment where 037 was
not applied has the table but **neither invariant**. Given #712 already records
production migration drift, this must be verified against production before the
Documents slice ships. **[V]** + **[A]** on the production state.

### Top contested tables (ranked by distinct writing modules)

| Rank | Table | Writers | Competing domains |
|---|---|---|---|
| 1 | **`rico_profiles`** | **~20** | Career Profile / Documents & Evidence / **Notifications** / Identity |
| 2 | `rico_users` | 7 | Identity / Career Profile / Application Ops / AI Orchestration |
| 3 | `user_job_context` | 8 | Job Intelligence / Application Ops |
| 4 | `action_audit_log` | 6 | Audit / AI Orchestration / Entitlements |
| 5 | `user_documents` | 4 | Documents & Evidence / AI Orchestration |

`rico_profiles` is the keystone: `src/services/email_notifications.py:77` and
`telegram_notifications.py:83` write **alert flags into the profile blob**, while
`files.py:376` and `rico_chat.py:2714` write **CV fields** into the same row. Those two
groups are separable today with no data migration — which makes profile-write
decomposition the cheapest high-value structural win available. **[V]**

### Retention reality

Only **two** tables have a real deletion path: `analytics_events` (180-day purge,
cron-invoked) and `cv_upload_artifacts` (opportunistic in-transaction purge). **[V]**

Unbounded, no purge of any kind: `action_audit_log`, `job_observations`,
`learning_signals`, `rico_learning_signals`, the three `*_audit` tables,
`gmail_audit_events`, `paddle_webhook_events`, `email_alert_log`, `telegram_alert_log`,
`chat_operations`, and others. `action_audit_log` and `job_observations` are the largest
liabilities — both append-only with **no unique key**. Note `action_audit_log`'s
idempotency is enforced **in application code only** (`audit_repo.is_duplicate`), with
**no backing DB constraint** — a concurrency risk the agent-loop work would amplify. **[V]**

---

## 5.0 SECURITY — withheld

**P1 HIGH-SEVERITY SECURITY HOLD, PRODUCTION REACHABILITY NOT YET VERIFIED**

Detail withheld from the public repository; held privately pending containment and owner
decision.

## 5. Three findings I re-verified personally (Evidence Auditor rule: no reliance on agent reports)

### 5.1 🔴 Pending-confirmation state is silently discarded in production — likely root cause of the four-times-recurring "typed YES" defect

```python
# src/rico_memory.py:27  — module import time
_JSON_WRITE_ENABLED = os.getenv("RICO_MEMORY_BACKEND", "json").lower().strip() != "postgres"

# src/rico_memory.py:319-321
def set_context(self, user_id: str, key: str, value: Any) -> None:
    if not _JSON_WRITE_ENABLED:
        return          # ← every pending-confirmation arm ends here
```

**[V]** Every armed pending state in chat — `confirm_set_active_cv`,
`confirm_profile_update`, `_pending_job_search`, `_pending_role_confirmation` — is stored
through `_store_recent_context` → `memory.set_context` (`src/rico_chat_api.py:13699-13709`).
Under `RICO_MEMORY_BACKEND=postgres`, **that write is a no-op**.

**Why this survived four separate fix attempts, and why tests never caught it:** the flag
is read at **module import time** with default `"json"`. Tests import with no env set, so
writes work and every pending-confirmation test passes. Production sets `postgres`, and
the same code path silently drops the state. The bug is invisible to the entire test
suite by construction. **[V]** on the mechanism; **[A]** on it being the root cause.

**MISSING EVIDENCE [M]:** the deployed value of `RICO_MEMORY_BACKEND` is not in
`render.yaml` or `docker-compose.yml`. **This single environment variable should be read
off Render before anything else in this program.** If it is `postgres`, this is the
highest-value defect found in the entire audit, and it is a small fix.

It also connects to the CI finding (§6): this is exactly the import-time env-read class
that merged PR #1386 began addressing. The remediation is the same pattern.

### 5.2 🔴 A decision signed today is already violated in code

`DEC-20260725-001` §2 and `src/services/cv_state.py:19-22` both state that `parsed`
"is never written by any path". **[O]**

```python
# src/api/routers/rico_chat.py:2481  — the confirm-CV handler
"cv_status": "parsed",
```

**[V]** Every CV confirmation writes exactly the value the decision forbids. This is not
drift — the decision is one day old and the write predates it. It means the "derive state
from content, never from a stored label" invariant is not yet true in the code, so
Phase 2 must *establish* it rather than assume it.

### 5.3 ⚠️ Correction to an agent finding — the REST apply route is **not** an approval bypass

An investigation reported `POST /api/v1/jobs/{id}/apply` as bypassing the approval gate
because it calls `apply_to_job(job, approved=True)`. **I read the code and that framing is
wrong**, so it does not enter this package as a safety finding:

```python
# src/api/routers/jobs.py:83-87
# This is an explicit, authenticated, per-job apply action initiated by the user
# (they POSTed to apply to this specific job), so it carries the approval the
# apply_to_job safety gate requires. Agent/automation paths never set approved=True.
result = apply_to_job(job, approved=True, user_id=user_id)
```

**[V]** The approval is the user's own authenticated POST, and the invariant that matters
— automation never sets `approved=True` — is explicitly preserved.

What **does** stand from that finding: this route reaches `apply_to_job` without passing
through `agent_runtime.handle_action()`, so it gets **no idempotency key and no
subscription-gate check** (`src/agent/runtime.py:155-163`, `:184-205`). That is a real
convergence gap for Milestone D — but it is a correctness and quota issue, not an
approval-safety issue. Recording it accurately matters more than recording it alarmingly.

### 5.4 Divergence summary for Milestones C and D

Highest blast radius first, all **[V]** by the write-path investigation:

| ID | Divergence | Consequence |
|---|---|---|
| D-J-1 | **Four different job-key derivations** write the same `(user_id, job_key)` unique slot — title\|company hash (`rico_chat_api.py:12931`), `source_job_id:` prefix (`job_save.py:81`), **link** hash (`jobs_service.py:277`), sha256 of title\|company\|location (`applications_repo.py:335`) | The same job saved from chat and from REST creates **two rows**, double-counts the saved-job quota, and chat read-back never sees the REST row |
| D-A-1/2/3 | No-downgrade rank is enforced on only **3 of 11+** application write paths; `PATCH /applications/{job_id}` (`applications.py:151`) and Gmail approve (`integrations_gmail.py:343`) can downgrade `offer` → `saved` | Application history can silently regress |
| — | **Five status vocabularies** that disagree, plus `"withdrawn"` (`rico_chat_api.py:9411`) which appears in none of them; `_get_status_rank` doesn't normalise case so `"Saved"` ranks 0 while `application_board` ranks it 10 | The "mirrors RicoChatAPI" comment at `application_board.py:39` is factually false |
| D-CV-1 | **Two CV upload entry points with incompatible contracts** — `/rico/upload-cv` classifies+parses+requires confirm; `POST /user/files` writes a `user_documents` row immediately with no parse and no profile linkage, yet both accept `doc_type="cv"` | A CV uploaded via the second path reports `metadata_only` forever — the user believes it was analysed |
| D-P-1 | Jotform webhook writes profiles via `db.upsert_profile` directly (`rico_jotform_webhook.py:279`), bypassing `profile_repo`'s field filtering and mirror | Only profile writer outside the chokepoint |
| D-P-2 | `require_db=False` (the default, used by all 17 chat write sites) **swallows DB failures and returns the memory mirror as success** (`profile_repo.py:546-553`) | Chat reports a saved profile that was never persisted |
| D-C-1 | Chat message persistence is a fire-and-forget daemon thread (`rico_chat_api.py:2417-2421`) — and it backs the AI-message quota (`subscription_gating.py:146-153`) | Lost messages silently under-count paid usage |

---

## 4b. Frontend state ownership — the owner's three failures, proven

**There is no CV state machine on the frontend. There are five independent upload
implementations, and only two of them ever confirm.** All **[V]**.

| Surface | File:line | Calls `confirmCVProfile`? | What it does with the authoritative response |
|---|---|---|---|
| `/upload` guest | `components/upload/GuestUploadAtelier.tsx:47` | **No** | `await uploadCV(...)` — **return value not assigned**; `preview` and `upload_id` discarded |
| `/upload` auth | `components/upload/UploadAtelier.tsx:376` | **No** | reads `cvResult.ok` only; `preview`/`upload_id` discarded |
| `/profile` | `components/profile/ProfileEditorial.tsx:943` | **No** | **return value not assigned**, and `ok` is not even checked |
| `/command` | `app/command/page.tsx:1753` → confirm at `:1859` | **Yes** | stored in the transcript as a `profile_preview` message |
| `/onboarding` | `app/onboarding/page.tsx:193` → confirm at `:273` | **Yes** | captured into `cvArtifact` |

`upload_id` is documented in the client as *"Opaque id for the matching confirm-cv-profile
call (#963)"* (`lib/api.ts:1305`). Three of five surfaces throw it away, so **confirmation
is structurally impossible from them.**

### The owner's failure #2, line by line

```js
// components/profile/ProfileEditorial.tsx:939-948
await uploadCV(file);                        // 943 — return value DISCARDED
notify(t("profileEdUploadDone"), "success"); // 944 — SUCCESS TOAST, before any confirm
await loadFiles();                           // 945 — listUserFiles()
```

`profileEdUploadDone` = **"CV uploaded — Rico is reading it."** (`lib/translations.ts:787`).
Because an unconfirmed CV only reaches `/user/files` *after* confirm — documented in the
codebase itself at `UploadAtelier.tsx:13` — line 945 **reliably returns the pre-upload
list**, and `:923-924` swallows failures silently. The result is a **success toast and an
empty document list in the same tick**. A hard backend rejection (`ok:false`) still fires
the success toast, because `ok` is never read.

### The owner's failure #1

The guest handoff is a **single query parameter**: `router.push("/command?cv=ready")`
(`GuestUploadAtelier.tsx:59`). No `preview`, no `upload_id`, no filename. The auth
surface is worse — its link is bare `href="/command"` (`UploadAtelier.tsx:481-488`),
carrying nothing at all. Both use a **client-side timed animation** (`ProcessingOverlay`)
as the "done" signal, not a server response.

### The owner's failure #3

`/command?cv=ready` selects welcome copy `cmdWelcomeCvReady` = **"Your CV is ready — I've
read it and built your profile."** (`lib/translations.ts:678`) — asserting a persisted
profile for a CV that was **never confirmed**. The panel's chips then route into the
**generic chat path**, which has no knowledge of any pending upload. That is failure #3
verbatim.

### Pending state cannot survive refresh anywhere — and on `/command` it is unrecoverable

- **Authenticated:** `parseHistoryContent` (`app/command/page.tsx:223-284`) has branches
  for `job_matches`, `options`/`help`, `application_status` and a text fallback — **no
  `profile_preview` branch**, and `preview`/`uploadId` are not fields it could reconstruct.
- **Guest:** `savePublicHistory` stores only `{role, text}` and filters
  `m.text && m.text.length > 0` (`:136`), while the preview message is created with
  `text: ""` (`:1792`) — so it is **silently dropped from localStorage**.

Reload on either audience: preview gone, Confirm button gone, `upload_id` gone.

### Two identity-label defects found while tracing **[V]**

1. Guest upload sends `user_id=public:web-…` while guest **chat** sends `session_id: "web-…"`
   **without the `public:` prefix** (`lib/api.ts:1710-1714`) — same guest, two correlation labels.
2. `app/command/page.tsx:1858-1859` computes `` `public:${getSessionId(...)}` ``
   **unconditionally** and passes it to `confirmCVProfile` **even when the user is
   authenticated** — the audience branch used at `:1751-1754` is not applied here.
   `app/onboarding/page.tsx:273` passes no userId for the same call.

### Schema validation turns success into visible failure

`validateShape` (`lib/api.ts:87-98`) throws a plain `Error`, **not an `ApiError`**, so it
carries no `statusCode` and every `err.statusCode === …` branch misses it. For
`ConfirmCVProfileResponseSchema` (`:1343`) this fires **after the server has already
written the profile**: the user sees `cmdCvProfileError` for a CV that was saved, the
preview is not transitioned, and they will click Confirm again. `PATCH /profile` has the
same false-negative class (`:1612` → "could not save" after a successful write).

### Two fully-built parallel truth stores, unreachable but one import away

| Store | Size | Contents | Importers |
|---|---|---|---|
| IndexedDB `rico-memory` (`lib/memory/index.ts`) | ~2,150 lines | longitudinal memory, trajectory history, recruiter interactions, **compensation targets**, strategic preferences | `lib/intelligence/*` only — which is imported by **nothing** |
| IndexedDB `rico-cache` (`lib/cache/index.ts`) | — | TTL cache **+ an offline write `sync_queue` with create/update/delete** | **zero** |

These are exactly the "parallel permanent state systems" the owner's revision forbids.
They are dead today; they must be deleted or quarantined before anyone wires them.

### No shared fetching layer

No SWR, no TanStack Query (`package.json:17-31`). 48 files import `lib/api` directly; 32
own their own `loading`/`error`/`data` triad. `GET /profile` has **8 independent call
sites**. Two hand-rolled 60s module caches exist (`useSidebarStatus`, `useMissionSummary`);
the only invalidator, `bustSidebarCache()`, is called from **one** place — the job-search
path (`app/command/page.tsx:1427`).

**Consequence for the P0:** a successful `confirmCVProfile` on `/command` **invalidates
nothing**. Navigating to `/profile` within 60s yields a screen whose header and body
disagree about whether the CV exists.

### `completeness_score` is interpreted on two different scales

`ProfileEditorial.tsx:85-89` and `useSidebarStatus.ts:57-61` accept 0–1 **or** 0–100;
`ProfileReadinessCard.tsx:74` and `lib/mission/today.ts:44` assume 0–1;
`ProfileCompletionBanner.tsx:40-43` **gates on 0–100 and displays on 0–1** — internally
contradictory under either scale. The schema is just `z.number().nullable().optional()`.
**[M]** which scale the backend actually emits — a backend question, and a required input
to Milestone C.

---

## 2. Target domain map

Ten logical domains **inside** the existing FastAPI/Next.js system. Not services, not
repositories, not deployment units. For each: the owner, the source of truth, and the
single hardest thing it must fix.

| # | Domain | Source of truth | Hardest problem it inherits |
|---|---|---|---|
| 1 | **Identity & Account** | `rico_users.id` (per `DEC-20260718-001`, gated on Study 2) | 4 identifier families; `rico_users` has 7 writers across 4 domains |
| 2 | **Career Profile** | `rico_profiles` | **~20 writers from 4 domains** — the keystone table |
| 3 | **Documents & Evidence** | `user_documents` (saved) + `cv_upload_artifacts` (pending) | 5 frontend upload paths, 2 backend upload contracts, no dedupe index |
| 4 | **Career Memory** | `rico_agent_settings._cm` + `search_context` | lost-update race on read-modify-write; second blocked-company store |
| 5 | **Job Intelligence** | `user_job_context` (discovery) | contested with Application Ops; 4 job-key derivations |
| 6 | **Application Operations** | `rico_job_recommendations` (per `DEC-20260718-001`) | 11+ write paths, 5 status vocabularies, no-downgrade on 3 of them |
| 7 | **AI Orchestration** | `rico_chat_history` + `chat_operations` | 3 disconnected tool systems; pending state discarded (§5.1) |
| 8 | **Entitlements & Billing** | `paddle_subscriptions` via `resolve_effective_user_plan` | 2 writers with different logic; all quota is live `COUNT(*)` |
| 9 | **Notifications & Integrations** | per-channel log tables | writes alert flags **into the profile blob** |
| 10 | **Audit & Observability** | `action_audit_log` | idempotency enforced in app code with **no DB constraint**; unbounded growth |

**Domain 2 is the keystone.** Notifications writing alert flags and Documents writing CV
fields into the same `rico_profiles` row is separable **today with no data migration** —
the cheapest structural win available, and a prerequisite for Milestone C owning anything.

## 9. Revised milestones

Each milestone states its exit criterion as a *provable* fact, not "CI green" — because
§6 shows `main` is not tested by CI at all.

| M | Milestone | Agents (owner's roster) | Exit criterion |
|---|---|---|---|
| **A** | Ground truth & governance | Governor, Evidence Auditor, Gatekeeper — **read-only** | This package approved; `RICO_MEMORY_BACKEND` read off Render (§5.1); `qa-tests.yml` runs on push to `main`; all 27 failures classified and owned |
| **B** | Application/domain contracts | Governor + **1** Backend | Dependency direction declared; advisory ratchet in CI; zero new violations; no behavior change |
| **C** | Documents / CV / Profile | Governor + Backend + Frontend (separate branches) + Gatekeeper | One server-authoritative pending contract used by **all five** upload surfaces; no `user_documents` row before confirm; pending survives refresh; unique index on `(user_id, content_hash)`; `cv_status="parsed"` write removed |
| **D** | Job / Application action boundary | Governor + Backend + Gatekeeper | **One** job-key derivation; no-downgrade enforced on every path; same audit + idempotency from UI, REST and chat |
| **E** | AI orchestration | Governor + AI + Backend + Gatekeeper | One tool path; approval provably server-side; hallucinated `job_ref` cannot dispatch; cost within envelope |
| **F** | Router & frontend decomposition | Governor + Backend or Frontend | Route table byte-identical before/after; `command/page.tsx` composition-only |
| **G** | Contract consolidation & legacy retirement | Governor + Gatekeeper + Release Captain | v2 only if a contract must break; legacy deleted only after telemetry proves zero callers |

**Milestone A contains one item that should not wait for anything: read
`RICO_MEMORY_BACKEND` off Render.** If it is `postgres`, a large class of production chat
defects has a small fix, and that changes the priority of everything below it.

## 10. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `main` is unverified and drifts further during the program | **High** — already true (§6) | High | Milestone A: run `qa-tests.yml` on push to `main` (one line) |
| Duplicate CV artifacts multiply full CV text | **Confirmed occurring** **[O]** | High — privacy, not just storage | Additive unique index; new migration, 038 untouched |
| Production `user_documents` lacks 037's constraints | Unknown **[M]** | High — silent dedupe loss | Verify against production before Milestone C; #712 already tracks drift |
| Chat reports saved profiles that were never persisted | **Confirmed** (`profile_repo.py:546-553`) | High — trust | Milestone C: make `require_db` uniform |
| Program competes with #1389/#1391 | Medium | High — the exact failure mode the owner forbids | Express milestones as sequencing over existing issues (§7) |
| Frontend and backend agents collide on shared contracts | Medium | Medium | Owner's rule: separate branches, contract approved before frontend starts |
| Agent reports accepted without re-verification | Medium | High | Owner's rule; already caught one overstatement (§5.3) |
| Dead IndexedDB stores get wired by a future change | Low | High | Delete or quarantine in Milestone F |
| Session loss destroys this package | **Live now** | Medium | **Owner decision pending** |

## 11. ADR list (to be written in Milestone A, one file each)

| ADR | Subject | Why it needs a decision |
|---|---|---|
| 001 | **CV state: two orthogonal axes, not one** | Content state (`DEC-20260725-001`) and artifact lifecycle are different machines; the revision's proposed vocabulary collides with the accepted one (§4.1) |
| 002 | Canonical job-key derivation | Four exist; one unique constraint (§5.4 D-J-1) |
| 003 | Application status vocabulary + no-downgrade ownership | Five vocabularies; `"withdrawn"` in none |
| 004 | `rico_profiles` decomposition | Notifications and Documents must stop writing the same row |
| 005 | Dependency direction + enforcement posture | Advisory ratchet first; no broad allowlists |
| 006 | Schema authority: migrations vs runtime DDL | 15 tables exist only in Python (§3) |
| 007 | Audit scope — state changes only, or model reads too | Owner question; blocked on §3's finding that idempotency has no DB constraint |
| 008 | Frontend server-state ownership | No shared fetching layer; 8 call sites for one endpoint |
| 009 | Retention policy for unbounded tables | Only 2 of ~30 tables have any deletion path |
| 010 | Guest ↔ authenticated identity labelling | Two correlation labels for one guest (§4b) |

## 12. Recommendation

```text
APPROVE WITH REQUIRED CHANGES
```

**On the owner's revision:** approve the sequencing (Documents/Profile → Job/Application
→ AI) without reservation. The audit supports it independently — the AI layer sits above
state that is not yet single-authority, so tools built now would be tools over the same
fragmentation.

**Three required changes to the revision itself:**

1. **Do not adopt the proposed CV state vocabulary** (`received → parsed → pending_review
   → confirmed → persisted`). Its `parsed` state collides with the legacy label that
   `DEC-20260725-001` §2 — signed one day ago — deliberately made read-only and
   non-promoting. Adopt instead the two orthogonal axes already in the codebase (§4.1) and
   give the artifact-lifecycle axis the one decision record the revision asks for.
2. **Add one item ahead of everything else:** read `RICO_MEMORY_BACKEND` off Render. If it
   is `postgres`, pending-confirmation state is being discarded in production (§5.1), and
   that is both the largest defect found and one of the smallest fixes.
3. **Make "CI green" a defined term before it is used as an exit criterion.** Today it
   means "an allowlist passed on a PR head" and `main` is never tested (§6).

**On Phase 0:** this package is the deliverable. It is incomplete in two areas —
identity/authorization and the 27-failure classification were still being audited when it
was written — and those gaps are marked, not papered over.

**Stopping here for owner review, as instructed.** No implementation PR, migration,
deployment, or environment change has been made. One evidence-preservation branch carrying
this document only was created on owner instruction (Directive 3 §1) — that is preservation,
**not** approval of this package.

---

# Part II — merged from the session plan file (Directive 3 §1: one artifact, no parallel status file)

## Phase 0 control state (owner-verified at `3c5879f`)

- 8 open PRs, **non-draft count 0** — the owner converted #1370 and #1359 to Draft to
  remove accidental-merge surface under the freeze. **[owner-reported]**
- `claude/website-api-restructure-5gtkpg`: 2 behind / 1 ahead, unchanged at `b2b85b9`,
  **EVIDENCE-HOLD**. Not to be extended, reset, rebased, or merged.
- Agent caps: max 4 active, max 2 code-writing overall, **0 code-writing during Phase 0**.
- Subagent output is evidence, never a verdict. The owner reviews from outside this session;
  no self-approval, no self-merge.

## Findings already filed externally by the owner — cite, do not re-derive

| Issue | Finding |
|---|---|
| **#1395** | Frontend calls `/api/v1/links/verify/batch`; backend registers `POST /verify-batch`; the e2e spec mocks the wrong path, so CI is **falsely green** |
| **#1396** | `/vision` unauthenticated and absent from robots.txt — low severity, **separate bounded PR, explicitly out of scope** for the migration |
| **#1397** | `execute_tool` unreachable; approval must never come from model arguments — **Milestone E precondition** |

These supersede the corresponding analysis in Part I §4b/§7 and Slice B; they are not
re-derived here.

## Milestone A — exit criteria

1. This architecture package accepted, with its acknowledged gaps.
2. `RICO_MEMORY_BACKEND` read off Render — **[missing evidence]**. The owner is reading it
   and running redacted aggregate-only Neon queries; this session does **not** query Neon
   and does **not** open the Render dashboard.
3. `qa-tests.yml` made to run on push to `main`. Today it triggers on `pull_request` /
   `workflow_dispatch` only, and its `pytest` job runs an **allowlist**, not `tests/` — so
   `main` is **unverified, not green**. **[verified]**
4. All 27 full-suite failures classified and owned — as failing regression tests, linked
   strict xfails, or clearly labelled characterization fixtures. **Known-wrong behavior is
   never pinned as an approved contract.** (In flight.)
5. Production `user_documents` confirmed to carry migration 037's constraints — the table
   is created by runtime DDL (`src/rico_db.py:201`) but its invariants live only in the
   migration, and #712 already records drift. **[missing evidence]**

## Binding sequencing (Directive 3 §6)

Close the identity/profile-row selection hole → verify containment → privately audit
affected data → **only then** fix pending-state persistence (the `RICO_MEMORY_BACKEND`
no-op) → resume the package.

**Rationale, restated because it is counter-intuitive:** fixing the memory no-op first
would *increase* reachability of the §5.0 hold. The ordering is a safety constraint, not a
preference.

## Reachability verification — withheld

Progress on the §5.0 reachability question is held privately pending containment and
owner decision.

## Deliverable 1 — Current Architecture Map (as-built)

All **[verified]** by measurement this session.

```
Vercel (apps/web)                      362 TS/TSX files · 50,770 lines
  app/           30+ route dirs        command/page.tsx 2,972 lines
  lib/api.ts     2,565 lines           93 hardcoded "/api/v1/" literals
  no shared fetch layer                48 files import lib/api directly
        │  next.config.js:53-64 — bare passthrough: /proxy/:path* → ${backendUrl}/:path*
        │  ("/api/v1" is NOT injected — the frontend supplies it everywhere)
        ▼
Render (src/api)                       24 routers · 123 route handlers
  routers/rico_chat.py  2,962 lines · 25 endpoints · 6 bounded contexts
        ▼
src/ ROOT  ── NOT A LAYER, A CYCLE HUB ──────────────────────────
  inbound 258 (services 109 + transport 86 + repositories 63)
  outbound back into every layer (repositories 62, services 56, agent 15)
  rico_chat_api.py 23,081 lines; class RicoChatAPI spans 2156–23060
        ▼
Neon                                   ~53 tables, TWO schema authorities:
  migrations/*.sql   (38 tables; numbering starts at 005; 039 & 042 absent)
  runtime Python DDL (15 tables in NO migration — incl. user_documents,
                      rico_profiles, rico_users, rico_job_recommendations)
```

### Three parallel agent stacks, none converged

| Stack | Reachable from | State |
|---|---|---|
| `src/agent/` — `tool_registry` (12 tools) + `runtime.handle_action` (idempotency, audit, admin gate) | `/api/v1/actions/run`, `/api/v1/agent/chat` | **Working, tested** — `tests/test_agent_runtime.py` drives real tools |
| `rico_openai_agent._tool_schemas` + `execute_tool` | nothing | **Dead** — see **#1397**; also wrong wire format for the production provider |
| `src/rico_tool_registry.get_rico_tools` | nothing (zero callers repo-wide) | **Dead**, and carries a `user_id == "default"` global-profile fallback (`:92`) — must never be connected |

### Convergence scorecard — the migration's actual target

| Domain | Write paths | Converged? |
|---|---|---|
| Applications | 11+ | **No** — no-downgrade on 3 of them |
| Job actions | 12 entry points, 4 job-key derivations | **No** |
| CV upload | 2 backend contracts, 5 frontend implementations | **No** — 3 of 5 discard `upload_id`, so confirm is structurally impossible from them |
| Profile | 26 call sites | **Mostly** — one chokepoint, one Jotform bypass, and `require_db=False` swallows DB failure on 17 chat sites |
| Chat messages | 1 DB writer | **Yes** — but fire-and-forget, and it backs the paid AI-message quota |
| Career memory | 1 writer | **Yes** — but read-modify-write with no locking |

**What the map explains:** splitting files inside the cycle relocates the cycle. That is
why Milestone B (declare the dependency direction; advisory ratchet; no behavior change)
must precede every structural slice — and why "the chat file is too big" was always the
symptom, not the disease.

## Study 2 — Identity, Authentication, Authorization & Session

Closes the study `DEC-20260718-001` names as the gate on its identity source-of-truth row.
**Recommendation: do not ratify that row until §5.0 is closed** — the decision picks a
canonical id, and today an unauthenticated party can write the column the resolver ranks on.

**What is strong** (protect it through the migration; all **[verified]**):

- Guest→account merge takes its source from the **signed token, never the request body**
  (`src/services/identity_merge_service.py:340,346-349`), serialises on a guest-scoped
  advisory lock (`:369-378`), enforces single ownership via the `guest_identity_claims` PK
  inside the same transaction (`:423-463`), and fails closed if the table is missing
  (`:434-441`). Best-built subsystem in the codebase.
- Guest capability: HMAC over a signed payload with an independent key
  (`src/api/public_identity.py:129-131`), constant-time verify, every field read from the
  signed payload (`:212-254`), 7-day expiry, fail-closed in production (`:134-137`).
- `auth_version` revocation checked in exactly one place (`src/api/deps.py:100-104`); the
  claims-only middleware hydration is deliberately **not** trusted (`:54-58`). No bypass found.
- Auth cookie httpOnly / secure (raises in production if explicitly false) / samesite=lax /
  24h; `JWT_SECRET` fail-closed for absent, short, or placeholder values
  (`src/api/auth.py:78-107`); login timing normalised with a precomputed dummy bcrypt hash.
- Admin role is re-read from the DB every request, never taken from the token claim.

**Hardening gaps** (ranked; none is §5.0):

| ID | Gap |
|---|---|
| B2 | Mutating/LLM routes with **no rate limiter**: `POST /api/v1/agent/chat` (`src/api/routers/agent.py:17-26`) and all four job actions (`src/api/routers/jobs.py:74,134,148,180`) — every other AI surface carries `LIMIT_CHAT` |
| B3 | Rate-limit storage resolved at **import time**, falling back to per-process `memory://` with a warning, never a failure (`src/api/rate_limit.py:70-93,143-147`). `render.yaml` declares neither `REDIS_URL` nor `RICO_REDIS_URL` — **[missing evidence]** whether set in the dashboard. If unset, `LIMIT_LOGIN="5/minute"` multiplies by worker count |
| B4 | With migration 045 unapplied, `update_password` **silently does not revoke sessions** (`src/repositories/users_repo.py:335-344`), while `/logout-all` correctly 503s. **[missing evidence]** that 045 is applied |
| B6 | `email_verified` enforced at login only, never per request (`src/api/deps.py:96-105`) — a revoked verification keeps its session until token expiry |
| B7 | Log-privacy AST guard covers **7 of 47** affected modules (`tests/test_1076_log_privacy.py:461-469`); the same scanner across `src/` yields **499 violations**. Worst: raw `ctx.user_id` on the **public** chat path (`src/api/routers/rico_chat.py:1226-1231,1240-1245`) and raw email-valued `auth_user_id` (`src/services/identity_merge_service.py:388,406,455,479,488`). #1388's ratchet is detection-only and fixes no call site |
| B1 | `/api/v1/rico/metrics` authenticated but **not admin**, and unrate-limited (`src/api/routers/rico_chat.py:1694-1707`) |
| B5 | Two paths skip the DB auth check: `auth=="env"` (pinned off in `render.yaml:23`, correct) and `not is_db_available()` — the latter keys off `DATABASE_URL` absence read at import, so a production boot with a dropped URL degrades to claims-only auth rather than 503 (`src/api/deps.py:77-86`) |

Two further non-deterministic identity resolvers exist in the same class as §5.0 but with
narrower blast radius. Detail withheld from the public repository.

**Naming hazard feeding all of it:** `deps.py:152-159` and `admin_subscribers.py:51-53`
call `users.id` "canonical", while `identity_merge_service.py:196-207` and `profile_repo`
call `rico_users.id` the "internal UUID". Two different columns, one word. → **ADR-011**.

## Test-execution posture (stated once for the whole classification batch)

Every run in the 27-failure classification batch targets a **disposable local Postgres or
no database at all — never Neon**, with **outbound network blocked**. Live Neon mutation
during development or tests is forbidden by `PROJECT_STATUS`.
