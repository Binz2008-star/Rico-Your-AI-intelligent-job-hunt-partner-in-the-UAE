# Neon Data Architecture Audit — 2026-07-18

Stage 1 of the Neon database architecture remediation program:
**database architecture audit + canonical source-of-truth decision record.**

Read-only for production. Docs-only for the repository. No DDL, no DML, no
migration application, no privilege change, no branch protection change was
performed. Every production observation below came from `SELECT`/catalog
queries executed on 2026-07-18; every code claim cites `file:line` on `main`.

## 1. Executive verdict

**ORANGE.** The database works, core Rico records are internally consistent
(zero NULL owners, zero orphan profiles, zero duplicate job keys), and there
is no evidence of data corruption or active compromise. But five structural
gaps are real and verified:

1. The production Neon branch is **unprotected** (P0 operational risk).
2. The access model is **owner-role + zero RLS policies + blanket CRUD grants
   to `authenticated`** — safe only as long as no non-owner path (Data API)
   is exposed (P0 conditional / defense-in-depth gap).
3. **Identity is fragmented across four identifier families** and the
   advertised identity merge is not implemented (P1).
4. **Application lifecycle state contradicts itself across three tables**
   (P1).
5. **Migration drift is confirmed**: 043 absent, 034 only partially applied
   (P1).

The biggest risk is not size or speed. It is that the same user and the same
application can hold more than one identity and more than one source of truth.

## 2. Verified scope and evidence

### Ground truth at audit time

| Item | Value |
|---|---|
| Repository `main` SHA | `4ce678b6400889ebfb838e00079c7dfa86fcaf7c` (2026-07-18) |
| Working tree | clean; audit branch created from this SHA |
| Migration files | `005` … `044` (039 and 042 are not on `main`; 042 exists only on PR #1025's branch; PR #1138 carries an unapplied 045) |
| Highest migration on `main` | `044_guest_identity_claims.sql` |
| Neon project | `robenjob` (`old-frog-88141983`), org `Roben` |
| Production branch | `production` (`br-restless-cherry-amq6wj7o`) — **primary: yes, default: yes, protected: NO** |
| Database / PostgreSQL | `neondb` / PostgreSQL 17.10 |
| Branch population | 219 branches: 194 Vercel previews, 22 GitHub previews, 3 console (`production`, `backup-pre-044-20260717`, `vercel-dev`); **0 protected** |
| Neon Data API | Not determinable read-only (see §14); PostgREST-style roles `authenticator`/`authenticated`/`anonymous` exist in `pg_roles` |
| Runtime DB role | Repo: single `DATABASE_URL`, no role logic (`src/db.py:20,34`; `src/rico_db.py:280`). Live `pg_stat_activity` at scan time showed only `neondb_owner` sessions. `neondb_owner` has `BYPASSRLS` |

### Open PRs affecting schema/identity/applications/billing/Gmail/memory

| PR | Impact |
|---|---|
| #1138 (draft, deferred) | Migration 045 `users.auth_version` — change-window only; **not applied** (verified live: column absent) |
| #1025 (draft, frozen) | Migration 042 career-memory tables — branch-only; **not in production** (verified live: `career_memory_events` absent) |
| #1129 (draft, stacked on #1025) | Erasure wiring; no new schema |
| #1136 (draft) | Docs-only reconciliation audit |
| #1159 (merged to `main` 2026-07-18, `197d946`) | Gmail UI + recurring-sync consent readiness — frontend-only; feature remains disabled (flag OFF); no migration, no OAuth activation. Any future activation still requires 043 first (§7, §9) |

### Method

- Repo evidence: direct reads of `main` (files cited inline).
- Production evidence: aggregate-only `SELECT`/catalog queries on branch
  `br-restless-cherry-amq6wj7o`. No emails, names, tokens, CV text, or
  message content was selected or is reproduced here.

## 3. Database inventory

45 base tables + 1 view (`latest_pipeline_run`) in `public`, plus the
`neon_auth` schema (9 tables — Neon Auth provisioned; `neon_auth."user"` has
exactly 1 row). `pg_stat_statements` is installed.

Row counts (live, 2026-07-18):

| Table | Rows | Table | Rows |
|---|---:|---|---:|
| `users` | 65 | `user_subscriptions` (Stripe-era) | 3 |
| `rico_users` | 226 | `subscription_events` (Stripe-era) | 10 |
| `neon_auth."user"` | 1 | `subscription_intents` (manual) | 34 |
| `rico_profiles` | 141 | `paddle_customers` | 2 |
| `rico_onboarding_states` | 265 | `paddle_subscriptions` | 2 |
| `guest_identity_claims` | 0 | `paddle_checkout_sessions` | 13 |
| `user_documents` | 16 | `applications` (legacy) | 3 |
| `user_job_context` | 198 | `application_drafts` | 0 |
| `uploaded_document_context` | 5 | `rico_job_recommendations` | 195 |
| `rico_chat_history` | 3,505 | `leads` (orphaned) | 8 |

## 4. Identity map

### Identifier families in live use

| Family | Type | Used by (verified live column types) |
|---|---|---|
| Auth account id | `users.id` int4, keyed by `email` | `users` (JWT auth store) |
| JWT subject | email as TEXT — `sub` claim IS the canonical text user_id (`src/api/deps.py:37,47`) | all authenticated routes |
| Rico canonical UUID | `rico_users.id` uuid | `rico_profiles.user_id`, `rico_chat_history.user_id`, `rico_job_recommendations.user_id`, `guest_identity_claims.claimed_by_user_id` |
| External text id | `rico_users.external_user_id` TEXT (email, `public:*`, `telegram_chat:*`) | `rico_onboarding_states.user_id`, `user_job_context.user_id`, `uploaded_document_context.user_id`, `user_documents.user_id`, `application_drafts.user_id`, `user_subscriptions.user_id`, `paddle_*.user_id`, `subscription_intents.user_id`, gmail tables per migration 043 header (L18–20) |
| Guest session id | `public:<sid>` TEXT (`src/agent/identity/resolver.py:107,113`) | onboarding, chat context, guest claims |

### Translation layers

- `src/agent/identity/resolver.py` — resolves inbound signals to a canonical
  id and **claims** merge capability, but `_attempt_identity_merge()`
  (resolver.py:194–219) only probes `rico_users` by email and **always
  returns `False`** — identity merge is described, not implemented.
- `src/repositories/applications_repo.py:120–159` — provisions/resolves the
  text JWT id into a `rico_users` UUID on demand (`_provision_db_user_id`).
- Migration 044 `guest_identity_claims` (applied; 0 rows) — DB-enforced
  single-owner guest→account claim; merges fail closed if absent.
- `src/repositories/search_context_repo.py` — self-declared **DORMANT**;
  `search_context` exists with a `canonical_user_id` key but no active code
  path.

### Live fragmentation evidence (aggregate-only)

| Metric | Value |
|---|---:|
| Emails present in BOTH `users` and `rico_users` (different id spaces by construction: int vs uuid) | **38** |
| Duplicate-email groups inside `rico_users` | **3** |
| `rico_users` rows without any email | **125** / 226 |
| `rico_onboarding_states` rows not linkable to any `rico_users` row (by external id, email, or uuid) | **121** / 265 (95 of the 265 are `public:*` guest sessions) |
| `user_job_context` rows not linkable to `rico_users` | **12** / 198 |
| `uploaded_document_context` rows not linkable | **2** / 5 |
| `guest_identity_claims` rows | 0 (mechanism live since 2026-07-17, unused so far) |

Correction vs. the earlier informal audit: the `users`∩`rico_users` email
overlap is **38**, not 42.

### Safest canonical identity target

`users` (auth) → mapping → **`rico_users.id` (UUID)** → all product data.
The UUID column already anchors profiles, chat, and recommendations with zero
NULLs and zero orphans (§10), and 044 gives guest claims a durable owner key
pointing at it. The text-keyed tables need a mapping layer, not a rewrite.
Formalized as proposed decision DEC-20260718-001 in `DECISIONS.md`; that
identity-spine row stays PROPOSED until Study 2 — Identity, Authentication,
Authorization & Session Architecture Audit — verifies or revises it.

## 5. Application lifecycle map

### Write/read paths on `main`

- SaaS canonical: `src/repositories/applications_repo.py` — statuses
  `_VALID_STATUSES` (applications_repo.py:168–171): `saved, opened,
  opened_external, prepared, applied, interview, rejected, offer,
  decision_made, follow_up_due`; reads via `RicoDB._CANONICAL_APPS_CTE`
  (`src/rico_db.py:1296`) over `rico_job_recommendations`; writes via
  `upsert_recommendation` (`src/rico_db.py:1424`) with the partial unique
  index on `(user_id, job_key)`.
- Discovery/conversation context: `src/repositories/user_job_context_repo.py`
  (docstring L1–6) — persists JSearch matches so links survive chat turns;
  not an application ledger.
- Legacy pipeline: `applications` — **no `user_id` column at all**, global
  `UNIQUE (job_link)` (verified live: `applications_job_link_unique`), so two
  users can never track the same job. Structurally unusable for SaaS.
- `application_drafts` — generated drafts only (0 rows).
- Gmail M0 (PR-gated) consumes `applications_repo._VALID_STATUSES` for its
  review-approve route (applications_repo.py:166–167).

### Live status distributions (2026-07-18)

| `rico_job_recommendations` | n | `user_job_context` | n | `applications` | n |
|---|---:|---|---:|---|---:|
| opened | 176 | seen | 172 | applied | 2 |
| follow_up_due | 10 | saved | 9 | interview_scheduled | 1 |
| opened_external | 3 | opened_external | 7 | | |
| saved | 3 | **applied** | **5** | | |
| prepared | 2 | discussed | 4 | | |
| offer | 1 | prepared | 1 | | |
| **applied** | **0** | | | | |

### Verified contradiction

The canonical table records **zero** applied applications while the context
table records **5** and the legacy table records **2 (+1 interview)**. Of the
5 `user_job_context` rows with `status='applied'`, **4 have no matching
`rico_job_recommendations` row** for the same resolved user (matched
heuristically by apply-URL or title+company — the two tables share no job
key, which is itself part of the finding). All live statuses fall inside the
code vocabularies; no unknown status values exist.

### Verdict

`rico_job_recommendations` is the only structurally valid application ledger.
`user_job_context` must remain discovery/conversation context.
`applications` cannot be promoted (no user scoping) and should be frozen as
legacy-pipeline-only pending Phase 7. A one-time reconciliation of the 5
context-`applied` records into the canonical table is required (Phase 4) —
not a blind table merge.

## 6. Billing map

Three billing generations coexist:

| Generation | Tables | Live rows | Code role |
|---|---|---|---|
| Stripe-era | `user_subscriptions`, `subscription_events` | 3 / 10 | **Not consulted for entitlement** — legacy data only |
| Paddle | `paddle_customers`, `paddle_subscriptions`, `paddle_checkout_sessions`, `paddle_webhook_events` | 2 / 2 / 13 / — | **Entitlement source of truth**: `resolve_effective_user_plan` (`src/subscription_plans.py:90–119`) reads ONLY `paddle_subscriptions` via `get_paddle_subscription_by_user` and falls back to Free |
| Manual | `subscription_intents` | 34 | Lead capture for WhatsApp-assisted activation; `BILLING_MODE` defaults to `manual` (`src/billing_mode.py:12–16`) |

Answers the earlier open questions: entitlement is decided by
`paddle_subscriptions` regardless of `BILLING_MODE`; `BILLING_MODE` only
selects the checkout path; Stripe tables are read-only legacy; one plan per
user is enforced by `paddle_subscriptions_user_id_key` (unique, verified
live). Duplicate-plan risk across generations is handled by the resolver
consulting only one table.

## 7. Gmail / memory readiness

- **Gmail (migration 043): NOT applied.** All four tables
  (`gmail_connections`, `gmail_sync_runs`, `gmail_review_items`,
  `gmail_audit_events`) verified absent. The migration header
  (043_gmail_connections.sql L7–11) requires manual apply BEFORE deploying
  connector code; code degrades safely while `RICO_ENABLE_GMAIL_SYNC=false`.
  Gmail must not be enabled before 043 is applied and drift-verified.
- **Memory engine (migration 042): branch-only** (PR #1025, frozen). Verified
  absent in production. Correct state; nothing to remediate yet.
- **Guest claims (migration 044): applied 2026-07-17** (backup branch
  `backup-pre-044-20260717` exists; table present, 0 rows).

## 8. Access and RLS findings

All live-verified:

- Connection role for this audit and (by repo evidence) the runtime:
  `neondb_owner`, which has **`rolbypassrls = true`**.
- **`pg_policies` is empty — zero RLS policies in the entire database.**
- **17 tables have RLS ENABLED with no policy** (`action_audit_log`,
  `applications`, `auto_apply_attempts`, `jobs`, `password_reset_tokens`,
  `rico_agent_settings`, `rico_alerts`, `rico_chat_history`,
  `rico_job_recommendations`, `rico_learning_signals`,
  `rico_onboarding_states`, `rico_profiles`, `rico_saved_searches`,
  `rico_users`, `rico_webhook_events`, `settings`, `users`) — meaning
  non-owner roles are fully denied on them, while the owner bypasses RLS
  entirely. The remaining sensitive tables (`user_documents`,
  `uploaded_document_context`, `cv_upload_artifacts`,
  `email_verification_tokens`, all billing tables, `application_drafts`,
  `guest_identity_claims`, `user_job_context`, `leads`) have **RLS disabled**.
- **`authenticated` holds SELECT/INSERT/UPDATE/DELETE on 44 public tables.**
  `anonymous` and `authenticator` roles exist (PostgREST/Data API trio).

Classification (as required — no exploitability claim without a verified
path):

- **Confirmed exposure: none.** No non-owner access path was verified as
  reachable.
- **Conditional exposure:** IF the Neon Data API endpoint is (or becomes)
  enabled and reachable, the `authenticated` blanket grants + zero policies
  make cross-user reads/writes possible on RLS-disabled tables. Data API
  status could not be read via read-only tooling — this is the single most
  important owner verification (§14).
- **Defense-in-depth weakness (unconditional):** the runtime uses a
  BYPASSRLS owner role, so no database-level isolation backs the
  application-level `user_id` filtering; a single application bug or leaked
  owner connection string exposes everything. Remediation is Phase 2 (least-
  privilege runtime role built and tested on a non-production branch first).

## 9. Migration drift

Verified object-by-object against production:

| Migration | Expected | Live state | Verdict |
|---|---|---|---|
| 034 (DROP 6 redundant indexes, manual/owner-gated per header L23–27) | 6 indexes absent | 4 dropped; **`idx_rico_job_recommendations_user_job_key` and `idx_rico_profiles_user_id` still present** | **PARTIALLY APPLIED** |
| 043 (Gmail, manual-apply) | 4 tables + index + constraint + column | **all absent** | **NOT APPLIED** (acceptable only while Gmail stays flag-off) |
| 044 (guest claims) | table present | present, 0 rows | applied |
| 042 (memory engine) | not expected on `main` | absent | correct (branch-only) |
| 045 (auth_version, PR #1138) | not expected yet | `users.auth_version` absent | correct (deferred change window) |

Detector coverage (`scripts/check_migration_drift.py:28–80`): signature
checks exist for 005–044 **including all seven 043 objects** — so the
detector, if scheduled, is currently reporting 043 drift. Migration 034 is
deliberately excluded as DROP-only
(`tests/unit/test_migration_drift_checks.py:46`), which means **DROP-only
migrations can remain silently unapplied with green checks** — exactly what
happened to 034's two remaining indexes. Phase 5 must add absence checks for
DROP-only migrations. Whether the drift job actually runs on a schedule and
alerts was not verified from this session (§14).

## 10. Data integrity findings

All verified live, aggregate-only:

- `rico_profiles.user_id` NULLs: **0**. `rico_job_recommendations.user_id`
  NULLs: **0**. `rico_chat_history.user_id` NULLs: **0**.
- Orphaned `rico_profiles` (user_id not in `rico_users`): **0**.
- Duplicate `(user_id, job_key)` in `rico_job_recommendations`: **0**.
- All live lifecycle statuses fall within the code vocabulary; none unknown.
- Constraint gaps (schema permits future corruption the code currently
  prevents): `rico_profiles.user_id`, `rico_job_recommendations.user_id`,
  `rico_chat_history.user_id` are **nullable**; `status` columns on
  `rico_job_recommendations`, `user_job_context`, `paddle_subscriptions`
  have **no CHECK constraint**. Phase 4/6 hardening:
  `CHECK … NOT VALID → VALIDATE → SET NOT NULL` (no table rewrite).
- `leads` quality: `last_contacted_date` is TEXT; `created_at`/`updated_at`
  are timestamp-without-timezone; no `user_id`; no updated-at trigger.

## 11. Performance findings

No urgent bottleneck; total sizes are tiny (largest heaps: `jobs` 3.9 MB,
`rico_chat_history` 960 KB). Notable signals:

- **Sequential-scan hotspots** (cumulative since stats reset): `rico_users`
  161,711; `rico_agent_settings` 114,029; `rico_profiles` 114,021. Tables are
  small so current impact is negligible, but the pattern suggests per-request
  identity/profile/settings resolution scanning; revisit after Phase 3, not
  before.
- **Redundant-index inventory — 21 signature-identical pairs** (identical key
  columns + predicate) found via `pg_index`, then classified live by
  uniqueness and constraint ownership (`pg_index.indisunique`,
  `pg_constraint.conindid`):
  - **Class A — truly identical non-unique twins (2 pairs):**
    `application_drafts` (`idx_application_drafts_user_status` /
    `idx_application_drafts_user_id`, both non-unique on
    `(user_id, status)`) and `telegram_alert_log` (`idx_tal_user_sent` /
    `idx_telegram_alert_log_user_sent`). Safest drop candidates — still
    EXPLAIN-verified first, and drift-signature membership checked before
    choosing which twin survives.
  - **Class B — non-unique shadow covered by a constraint-owned unique index
    (19 pairs):** e.g. `idx_rico_job_recommendations_user_job_key` (the 034
    leftover) shadowing `rico_job_recommendations_user_id_job_key_key`;
    `idx_rico_profiles_user_id` shadowing `rico_profiles_user_id_key`;
    `idx_applications_job_link` shadowing `applications_job_link_unique`;
    plus shadows on `paddle_customers` ×2, `paddle_subscriptions` ×2,
    `paddle_webhook_events`, `paddle_checkout_sessions`,
    `user_subscriptions`, `subscription_events`, `password_reset_tokens`,
    `email_verification_tokens`, `email_unsubscribe_tokens`, `jobs`,
    `rico_agent_settings`, `rico_webhook_events`, `search_context`,
    `auto_apply_attempts`. Only the non-unique shadow is ever a drop
    candidate.
  - **Class C — overlapping/partial indexes (not signature-identical):**
    require per-index EXPLAIN + code-path evidence before any judgement.
    Known example: the full unique
    `rico_job_recommendations_user_id_job_key_key` overlaps the partial
    unique `idx_rico_recommendations_user_job_unique`
    (`WHERE job_key IS NOT NULL`), which powers the `ON CONFLICT` upsert —
    **DO NOT DROP** (migration 034 header L9–14). Full Class C inventory is
    remediation slice 6A.
  - **Class D — constraint-owned indexes (19, the `*_key` members of Class
    B):** back live UNIQUE constraints and **must never be dropped
    directly**; changing them means an `ALTER TABLE … DROP CONSTRAINT`
    decision, which is out of scope for index cleanup.

  The cleanup goal is NOT zero overlapping signatures — it is the removal of
  independently proven redundant indexes only, without touching constraint
  support or useful planner paths. Write-amplification examples:
  `rico_job_recommendations` 72 KB heap / 256 KB indexes;
  `user_subscriptions` 8 KB / 112 KB.
- Dead tuples are modest (max 479 on `jobs`); autovacuum has run on the hot
  tables.
- `pg_stat_statements` had been recently reset — the top entry was this
  audit's own count query — so **no meaningful application-query ranking is
  available**; treat statement-level analysis as unresolved (§14).
- **No index may be dropped on `idx_scan=0` or duplicate-listing evidence
  alone**: each candidate needs `EXPLAIN` verification on a non-production
  branch, then `DROP INDEX CONCURRENTLY` per the 034 procedure.

Expired temporary records with no cleanup job (all verified live):

| Table | Expired / total | Older than 30 days |
|---|---|---|
| `password_reset_tokens` | 16 / 16 | 11 |
| `email_verification_tokens` | 130 / 132 | 106 |
| `cv_upload_artifacts` | 2 / 2 | 0 |
| `paddle_checkout_sessions` | 13 / 13 | 0 |

Tokens are stored hashed (good), but retention without need enlarges blast
radius and keeps operational tables dirty. Phase 6 adds a scheduled sweep +
documented retention policy.

## 12. Legacy-table classification

| Class | Tables | Basis |
|---|---|---|
| **Active core** | `users`, `rico_users`, `rico_profiles`, `rico_chat_history`, `rico_job_recommendations`, `rico_onboarding_states`, `user_documents`, `user_job_context`, `uploaded_document_context`, `guest_identity_claims`, `cv_upload_artifacts`, token tables, `settings`, `rico_agent_settings`, audit/log tables, `jobs`, `pipeline_runs` | live code paths |
| **Active billing** | `paddle_*`, `subscription_intents` | entitlement resolver + manual mode |
| **Transitional / read-only legacy** | `user_subscriptions`, `subscription_events` (Stripe-era) | not consulted for entitlement (`src/subscription_plans.py:90–119`); retain read-only pending #1066-style retirement |
| **Legacy pipeline** | `applications`, `auto_apply_attempts`, `weekly_reports` | single-tenant era; `applications` has no user scoping |
| **Dormant** | `search_context` | repo docstring declares DORMANT (`src/repositories/search_context_repo.py:5–7`) |
| **Orphaned / product drift** | `leads` (8 rows, B2B-CRM shape) | **zero references anywhere in repo code** (verified by full-repo search for any SQL touching `leads`); a separate Neon project `eco-technology-leads` exists in the same org — strong evidence the table belongs to a different product. Do NOT delete: identify data owner, then isolate (move to a `legacy_crm` schema or export to its own project) in Phase 7 |

## 13. Risks ranked

| Rank | Risk | Evidence |
|---|---|---|
| **P0** | Production branch unprotected — accidental delete/reset of live data possible from console/API/integration; 216 auto-created preview branches churn in the same project | §2 |
| **P0 (conditional)** | If Data API is enabled: cross-user read/write via `authenticated` blanket grants + zero policies | §8 |
| **P1** | Runtime uses BYPASSRLS owner role — no DB-level isolation behind app bugs | §8 |
| **P1** | Identity fragmentation: 4 identifier families, merge unimplemented, 121+12+2 unlinkable rows, 3 duplicate-email groups | §4 |
| **P1** | Application lifecycle contradiction: canonical table shows 0 applied vs 5 (context) + 2 (legacy); legacy table structurally single-tenant | §5 |
| **P1** | Migration drift: 043 absent (blocks Gmail), 034 partial, DROP-only migrations invisible to detector | §9 |
| **P1** | Orphaned `leads` table with third-party PII inside the production DB, RLS disabled | §12 |
| **P2** | 100% expired token/checkout records with no cleanup | §11 |
| **P2** | Redundant indexes (2 identical twins + 19 constraint-shadow pairs; Class C overlaps uninventoried); nullable owner columns; unconstrained status columns | §10, §11 |
| **P3** | Seq-scan hotspots on identity/profile/settings; three billing generations awaiting formal retirement docs | §6, §11 |

## 14. Assumptions and unresolved evidence

1. **Neon Data API status** — not readable via read-only tooling from this
   session. The role trio exists; whether the HTTP endpoint is enabled must
   be verified in the Neon console before Phase 2 (it decides whether the P0
   conditional is live).
2. **Render's actual `DATABASE_URL` role** — secret not readable (correctly).
   Repo shows a single URL with no role management; the only live sessions
   observed were `neondb_owner`. Treat "runtime = owner role" as highly
   probable, owner-confirmable in one glance at the Render env.
3. **Drift-detector scheduling** — 043 checks exist in the script; whether a
   scheduled CI job runs it against production and alerts was not verified.
4. **`user_job_context` → `rico_job_recommendations` match heuristic** — the
   tables share no job key, so the "4 of 5 applied rows unmatched" figure
   used apply-URL / title+company matching. The absence of a shared key is
   itself a Phase 4 work item.
5. **`pg_stat_statements` horizon** — stats were recently reset; application
   query rankings unavailable at scan time.
6. **`leads` data ownership** — no code path and a sibling CRM project
   strongly suggest non-Rico ownership, but the owner must confirm before any
   isolation step.

## 15. Recommended phased remediation (document only — nothing executed)

**A Phase is an umbrella milestone, not a PR.** The unit of execution is the
lettered slice: each slice below is exactly one PR / one change window with
one objective, owner-approved, verified on a non-production Neon branch
before production. Dangerous or logically separate operations are never
combined in one slice. Traceable tasks: TASK-20260718-008 … -014 in
`AI_WORKSPACE/TASKS.md` (one subtask per slice).

**Phase 1 — Protect and document production** (single-slice milestone)
- **1A** Enable protection on `br-restless-cherry-amq6wj7o` after confirming
  preview-branch automation (Vercel/GitHub create children of production —
  216 live examples) is unaffected; document the branch/backup model.
  Depends only on explicit owner approval, that preview-branch verification,
  and a documented toggle-off rollback — NOT on Data API status, the Render
  runtime role, or acceptance of the DEC-20260718-001 matrix (those
  verifications are slice 2A).

**Phase 2 — Database access boundary and least privilege**
- **2A** Verify Data API status and inventory every runtime access path
  (read-only; closes unresolved-evidence items 1–2 in §14).
- **2B** Create and smoke-test a limited runtime role on a non-production
  Neon branch (full backend test suite under the new role).
- **2C** Cut Render to the limited role (one env change window; instant
  rollback = previous connection string).
- **2D** Revoke unnecessary `authenticated` grants (44-table CRUD), verified
  against 2A's access-path inventory.
- **2E** Introduce tested RLS policies incrementally (per table group, each
  with cross-user denial tests; never a bulk flip).

**Phase 3 — Canonical identity reconciliation**
- **3A** Identity mapping report (read-only; every identifier family mapped).
- **3B** Duplicate-email resolution plan for the 3 groups (dry-run first).
- **3C** Orphan/guest classification and reconciliation of the 121/12/2
  unlinkable rows.
- **3D** Implement the real guest/auth identity merge (today
  `_attempt_identity_merge` always returns False — resolver.py:194–219).
- **3E** Add identity constraints (`NOT VALID → VALIDATE → SET NOT NULL`).

**Phase 4 — Application lifecycle reconciliation**
- **4A** Lifecycle reconciliation dry-run report (each of the 5 context-
  `applied` + 2+1 legacy rows resolved explicitly; no bulk matching).
- **4B** Reconcile the approved records into `rico_job_recommendations`.
- **4C** Freeze legacy `applications` writes (repo-layer guard).
- **4D** Introduce shared job identity/linkage between `user_job_context`
  and `rico_job_recommendations`.
- **4E** Status CHECK constraints + full lifecycle smoke
  (search → open → prepared → applied → follow-up → interview).

**Phase 5 — Migration drift resolution**
- **5A** Gmail 043 change window (additive DDL; before any
  `RICO_ENABLE_GMAIL_SYNC=true`).
- **5B** Finish migration 034: the two remaining
  `DROP INDEX CONCURRENTLY` statements.
- **5C** Add DROP/absence drift detection to `check_migration_drift.py` so
  DROP-only migrations can no longer stay silently unapplied.
- **5D** Verify scheduled drift alerting actually runs and reaches the
  admin channel.

**Phase 6 — Index and retention cleanup**
- **6A** Index classification: complete the Class A–D inventory of §11,
  including the Class C overlap/partial cases, with per-index EXPLAIN
  evidence and drift-signature membership.
- **6B** Small concurrent index-drop batches — only indexes independently
  proven redundant in 6A; never Class D constraint-owned indexes.
- **6C** Retention policy documented (tokens, artifacts, checkout sessions,
  webhook/audit logs).
- **6D** Cleanup worker/schedule implementing 6C (feature-flagged, with
  metrics).

**Phase 7 — Legacy isolation or retirement** (four independent decisions —
never one PR)
- **7A** `leads`: owner ownership confirmation, then export/isolation out of
  the Rico production DB.
- **7B** Stripe-era retirement (`user_subscriptions`,
  `subscription_events`) — aligns with #1066; read-only freeze first.
- **7C** Legacy `applications` pipeline trio retirement plan (after 4B/4C).
- **7D** `search_context`: delete-or-wire decision (dormant per repo
  docstring).

## 16. Rollback and production-safety principles

- Production is modified only inside owner-approved change windows, one
  migration per window, preceded by a Neon backup branch
  (`backup-pre-<nnn>-<date>`, pattern proven by `backup-pre-044-20260717`).
- Every schema change ships with: drift-detector signature, rollback SQL (or
  documented additive-harmless status), and a smoke checklist.
- Constraint hardening uses `NOT VALID → VALIDATE → SET NOT NULL` to avoid
  rewrites/locks; index drops use `DROP INDEX CONCURRENTLY` outside
  transactions.
- No RLS enablement on production before policies + runtime role are proven
  on a non-production branch with cross-user denial tests (a policy-less RLS
  flip against a non-owner runtime role would take the product down).
- Data reconciliation (identity, lifecycle) is executed from reviewed,
  idempotent scripts with a dry-run report first; never ad-hoc SQL.
- Any step that fails its verification stops the window and restores from
  the backup branch; partial application is recorded in TASKS.md before the
  session ends.
