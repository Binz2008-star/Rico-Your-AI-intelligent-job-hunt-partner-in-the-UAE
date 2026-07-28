# Journey-1 D1 Production-Data Consolidation Assessment

## Task

- Task ID: `TASK-20260728-002`
- Repository baseline: `1bda90db0ed342b154dd5a02d81d314175f0ef4d`
- Runtime/application baseline: `383dcb6c6c72a849891e0b55c1af80f80d4f4865`
- Scope: production-data assessment only; no repair
- Evidence date: 2026-07-28

> **Privacy contract.** This report contains aggregate counts, cluster shapes, non-identifying dates/ranges, and labels minted only for this report. It contains no raw or linkable production identifier and no deterministic pseudonym. `Cluster A`–`Cluster D` expire with this document and must not be reused in another report.

## Executive finding

The ownership problem is broader than one account. The current production snapshot contains four connected ownership-signal clusters, 21 guest rows carrying a trusted identity field, and 74 guest rows carrying authenticated onboarding completion.

The current guards contain future writes, but production data does **not** prove the standing claim that they have stopped new bad rows: every observed residual row predates the complete guard set, and there is no post-deployment row sample from which to measure prevention.

The specific cluster behind `#1389` cannot be established under the public-output contract. The recorded claim that it consists of five non-guest resolver candidates does not reproduce on the current snapshot: the resolver-equivalent aggregate has one ambiguous email candidate set with three non-guest rows and no five-row non-guest set. A five-row connected email component exists, but it contains both guest and non-guest rows. Linking either shape to the affected account would require a production identifier, so the mapping remains unestablished and `#1389` remains on HOLD.

## Scope and write-safety proof

Every production query ran inside a PostgreSQL transaction with:

```sql
SET TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '15s';
SET LOCAL lock_timeout = '1s';
```

Only metadata reads, `SELECT`, and `WITH ... SELECT` statements were executed. There was no `INSERT`, `UPDATE`, `DELETE`, `MERGE`, DDL, temporary table, `COPY`, side-effecting function, `EXPLAIN ANALYZE`, schema change, Neon branch creation, or migration.

Two attempted aggregate reads failed before returning findings because of SQL expression errors. Their read-only transactions aborted. They were corrected and rerun; neither attempt could mutate data.

## Evidence reads

| Read | Purpose | Output class |
| --- | --- | --- |
| Q0A | Confirm database/schema, read-only mode, and live table inventory | Metadata only |
| Q0B | Confirm relevant columns, types, and ownership foreign keys | Metadata only |
| Q1 | Census duplicate identity-signal values and connected components | Aggregates only |
| Q2 | Classify guest/non-guest composition and trusted-identity residue | Aggregates only |
| Q3 | Compare row chronology with the fully deployed guard boundary | Dates/ranges only |
| Q4 | Remeasure guest rows carrying trusted identity fields | Aggregates only |
| Q5 | Remeasure guest rows carrying authenticated onboarding completion | Aggregates only |
| Q6 | Measure per-shape blast radius across career, CV, chat, onboarding, settings, subscriptions, and learning domains | Aggregates only |
| Q7 | Test whether the `#1389` state can be isolated without an identifier | Aggregate shape only |

## Production census

- `rico_users`: **239** rows.
- Guest/public principals: **90**.
- Non-guest principals: **149**.
- Rows missing `created_at`: **0**.
- Observed creation range: **2026-05-09 through 2026-07-22**.

### Guest trusted-identity residual

Exactly **21** guest rows carry at least one trusted identity field:

| Field-presence shape | Rows |
| --- | ---: |
| phone only | 14 |
| email + phone | 3 |
| email only | 2 |
| phone + Telegram chat | 1 |
| phone + Telegram username + Telegram chat | 1 |

Latest update among those 21 rows: **2026-06-13**.

This reproduces the previously recorded total of 21.

### Guest authenticated-onboarding residual

Exactly **74** guest rows carry `completed` onboarding state.

- Completion range: **2026-05-11 through 2026-06-12**.
- Latest update: **2026-06-12**.

This reproduces the previously recorded total of 74.

### Previously recorded “three latent mismatched rows”

That claim is not reproducible because the previous record does not define its query contract. Under the explicit current definition “non-guest email principal differs from the stored email” there are **4** rows; **2** are standalone rather than members of a duplicated-email component. Neither result is three. The old figure is therefore **unverified**, not silently carried forward.

## Connected ownership-signal clusters

The graph joins rows only when a normalized signal is duplicated. Categories reported here are `email`, `phone`, `Telegram`, or `user_id`; signal values never left the query.

| Label | Joined by | Rows | Guest | Non-guest | Creation range |
| --- | --- | ---: | ---: | ---: | --- |
| Cluster A | Telegram + phone | 22 | 16 | 6 | 2026-05-10 → 2026-05-31 |
| Cluster B | email | 5 | 2 | 3 | 2026-05-10 → 2026-05-12 |
| Cluster C | email + phone | 2 | 1 | 1 | 2026-05-11 → 2026-05-17 |
| Cluster D | phone | 2 | 0 | 2 | 2026-05-17 → 2026-05-31 |

### Signal structure

- Cluster A: one phone signal spans 22 rows; one Telegram username spans 3; one Telegram chat signal spans 2.
- Cluster B: one email signal spans 5 rows.
- Cluster C: one email and one phone signal each span 2 rows.
- Cluster D: one phone signal spans 2 rows.

The 22-row phone value is not an obvious repeated-single-digit or two-digit placeholder. That does **not** establish that all 22 rows belong to one person; it only rules out two simplistic placeholder tests. Its meaning remains unknown.

## Blast radius by cluster shape

### Cluster A — broad career-state fragmentation

- Profiles: 22; CV-grounded profiles: 21.
- Saved documents: 4; pending CV artifacts: 2; uploaded-document context rows: 1.
- Chat messages: 697; chat operations: 48.
- Job recommendation rows: 240; user job-context rows: 198.
- Onboarding rows: 19, all completed.
- Agent-settings rows: 3; legacy settings: 1; saved searches: 1.
- Subscription rows: 3.

**User-visible consequence:** data associated through shared phone/Telegram signals is spread across many rows and domains. The current phone-only mapper asks for confirmation rather than auto-merging, but duplicated Telegram ownership can still produce a fail-closed account conflict. Guest-held records are excluded from authenticated resolution, so they can remain inaccessible or fragmented rather than being selected automatically.

### Cluster B — current email ownership conflict

- Profiles: 5; CV-grounded profiles: 4.
- Chat messages: 1,463.
- Onboarding rows: 5, all completed.
- Agent-settings rows: 1; user job-context rows: 13.
- Four rows carry an email/principal mismatch under the assessment definition.

**User-visible consequence:** the current authenticated email resolver sees three non-guest candidates and must refuse to guess. Non-chat routes can surface the typed conflict; known chat residuals can still render generic retry-inviting text. Large chat history and CV grounding are split across rows, so selecting one row without a consolidation map risks hiding or misassigning data.

### Cluster C — guest/authenticated split

- Profiles: 2, both CV-grounded.
- One chat message.
- Onboarding rows: 2, both completed.
- User job-context rows: 5.

**User-visible consequence:** authenticated resolution excludes the guest row, so the account may resolve without ambiguity while part of the user’s apparent history remains attached to a guest principal. Automatic consolidation would still be unsafe because shared email/phone does not by itself prove common ownership.

### Cluster D — phone-only relation

- Two non-guest rows.
- One profile with CV grounding.
- One completed onboarding row.

**User-visible consequence:** the normal authenticated account resolver does not use phone alone, so this shape does not itself establish login ambiguity. On the Jotform identity path, phone-only matching now requires human confirmation. The data is incomplete across the two rows, but the assessment cannot infer that they belong to the same person.

## Guard chronology

All observed cluster rows were created by **2026-05-31**. The two broad residual sets were last updated by **2026-06-13**. The complete identity-containment stack is verified in the later runtime baseline served on 2026-07-28.

Therefore:

- Every observed residual predates the **complete** guard set.
- No observed `rico_users` row was created after the complete guard set became live.
- This means there is no post-guard sample. The claim “the guards stop new ones” is **not disproven**, but it is also **not established by production data**.
- Per-guard deployment-time classification was not attempted from merge dates. Merge time is not deployment time; any uncertain interval remains unknown.

## `#1389` HOLD state

The public assessment cannot bind the affected account to a cluster without using an account identifier.

What is established:

- Current resolver-equivalent aggregation finds one duplicated email value with **three non-guest candidate rows**.
- It finds **no** email resolver value with five non-guest candidates.
- A single five-row connected email component exists, but its composition is **three non-guest plus two guest rows**.
- The historical “five non-public rows” statement therefore does not reproduce on today’s snapshot.

What is not established:

- Whether the three-row resolver set is the account behind `#1389`.
- Whether the five-row connected component is the same historical account after guest exclusion.
- Which row, if any, is canonical.
- Which dependent records belong to one natural person.

Required conclusion:

> The specific `#1389` cluster could not be isolated under the public-output contract.

`#1389` remains Draft and on owner HOLD. This assessment does not authorize a rebase, edit, Ready transition, merge, or data repair.

## Repair options — all unauthorized

### Option 1 — Keep the HOLD and perform no repair

- **Risk:** affected users remain blocked or fragmented.
- **Why it is safe:** no chance of cross-account reassignment or data loss.
- **Missing precondition:** none for the no-op; owner must decide whether the continued product impact is acceptable.

### Option 2 — Targeted consolidation after secure row mapping (preferred)

Create an owner-approved secure evidence location outside the repository, identify the affected account through an authenticated support flow, map every dependent row, choose a canonical owner row, and simulate the complete reassignment/deletion plan on a temporary Neon branch before any production authorization.

- **Risks:** cross-account data exposure, orphaned foreign keys, lost chat/CV/application state, billing or subscription misassignment, non-reversible user harm if the canonical row is wrong.
- **Missing preconditions:** secure row-level mapping; verified account ownership; explicit canonical-row rule; per-domain reassignment matrix; temporary-branch rehearsal; backup/PITR confirmation; validation and rollback queries; separate owner authorization.

### Option 3 — Product-mediated account consolidation

Build a user-facing or support-mediated verification flow that proves control of the relevant identities before proposing consolidation.

- **Risks:** larger product/security scope, new identity-proof surface, support complexity, potential abuse.
- **Missing preconditions:** product decision record, threat model, proof mechanism, audit log, recovery process, tests, and separate roadmap authorization.

### Option 4 — Bulk cleanup across all four clusters

- **Recommendation:** do not authorize.
- **Risk:** the graph records shared signals, not proven common ownership. Cluster A alone spans 22 rows and several career domains. Bulk merging could combine unrelated users.
- **Missing preconditions:** row-level human adjudication for every component and a rule proving ownership stronger than a shared contact value.

No option authorizes direct production SQL, manual row deletion, or use of `#1389` as the repair branch.

## Unknowns and evidence limits

- Exact row-to-person mapping is intentionally absent.
- The affected account behind `#1389` is not publicly isolatable.
- Cluster A may represent shared contact data, legacy contamination, or multiple people; the aggregates cannot decide.
- The previous “three latent mismatches” metric has no reproducible definition.
- Guard effectiveness after deployment cannot be measured because no post-guard creation sample exists.
- The legacy `applications` table lacks an ownership key usable for this assessment, so it was not attributed to clusters.
- Text-based `user_id` tables use mixed identity forms; counts used both internal-row and external-principal joins where supported, but a future repair must validate each domain individually.
- A repair may require row-level evidence. Until an owner-approved secure location exists, that evidence is correctly recorded as missing.

## Acceptance criteria

- [x] Every claim traces to a named, reproducible read.
- [x] Zero production writes.
- [x] Zero raw or linkable production identifiers in this document or PR material.
- [x] Every cluster uses an ephemeral label local to this report.
- [x] Missing row-level evidence is listed as missing.
- [x] Every repair option is explicitly unauthorized and states its missing preconditions.
- [x] Unknowns are listed as unknowns.
- [x] `#1389` remains on HOLD.

## Verification

- Unit tests: n/a — no code change.
- Integration tests: n/a — no code change.
- Frontend build: n/a.
- Local smoke: n/a.
- Production/deploy smoke: n/a — this is an assessment, not a release.

## Risk

The assessment itself is low runtime risk because it is read-only and documentation-only. The principal risk is publication of linkable production information; the report avoids that by design and records unestablished claims rather than disclosing identifiers.

## Rollback

Before merge: close the assessment PR without merge. After merge: revert its documentation commit. There is no database, schema, migration, runtime, environment, or deployment rollback.

## Final status

`review`
