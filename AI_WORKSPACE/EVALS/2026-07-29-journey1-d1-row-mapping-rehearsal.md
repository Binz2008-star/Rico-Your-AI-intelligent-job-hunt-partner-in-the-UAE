# Journey-1 D1 Row-Mapping and Consolidation Rehearsal

## Document contract

- **Why it exists:** records the public, non-identifying result of `TASK-20260728-003` after the secure row-level mapping and temporary-branch rehearsal.
- **Update when:** only if the evidence-branch snapshot is intentionally replaced or the owner authorizes and executes a separate production repair.
- **Source of truth:** this document for the completed evidence/rehearsal result; `PROJECT_STATUS.md` for current control state; live Neon and GitHub evidence override prose.
- **Owner:** Rico owner; evidence collected by the acting CTO session.

## Scope

Evidence and rehearsal only. All database calls explicitly targeted the owner-created Neon branch `d1-ownership-evidence-2026-07-28`. The first read confirmed the connection resolved to that non-default branch. No production database call or production mutation was made.

The public-output contract was preserved: this report contains aggregates and evidence classes only. It contains no raw or linkable user identifier, filename, contact value, deterministic pseudonym, credential, DSN, project ID, branch ID, or database endpoint. The evidence-branch name is retained because it is already part of the public control-plane record.

## Executive result

The ownership-data blocker above closed PR `#1389` is now mapped well enough to define a safe repair contract.

The snapshot contains exactly one email-linked shape with:

- five owner rows total;
- three non-guest resolver candidates;
- two guest rows;
- one unique row whose authenticated principal matches exactly;
- two non-guest rows that match through the mutable email field only.

### Canonical-row rule

The **unique exact authenticated-principal row** is canonical.

This rule is based on the ownership identifier presented by authentication. It is not based on recency, completeness, row order, chat volume, or a guessed natural person.

## Dependent-state matrix

| Domain | Observed state | Rehearsal ruling |
| --- | --- | --- |
| Identity owner rows | 5 rows | Reduce to the one exact authenticated-principal row |
| Profiles | 5 rows | Keep one canonical profile; add only non-conflicting career fields |
| Chat | 1,463 messages | Preserve all and reassign to the canonical UUID |
| Learning | 24 text-keyed signals | Preserve all and normalize to the canonical authenticated principal |
| Job context | 13 rows | Preserve all and normalize to the canonical authenticated principal |
| Onboarding | 5 completed rows | Collapse to one completed canonical state |
| Agent settings | 1 row on the canonical owner | Preserve unchanged |
| Saved documents | 0 rows | No document exists to reassign |
| Pending CV artifacts | 0 rows | No artifact exists to reassign |
| Application drafts | 0 rows | No rows to reassign |
| Subscriptions/billing | 0 rows for this shape | No rows to reassign |
| Legacy `applications` | No usable ownership key | Excluded; remains unresolved and must not be guessed |

## Profile evidence and CV truthfulness

The canonical profile contains current career preferences. Duplicate and guest profiles contain CV-derived career fields.

Across the five profiles:

- `skills`, `target_roles`, and `years_experience` have one non-null value each and are safe to carry when missing from the canonical profile;
- legacy CV filename claims conflict;
- no authoritative `user_documents` row exists;
- no pending CV artifact exists.

Therefore a repair must **not** carry `cv_filename` or `cv_status` into the canonical profile. Doing so would preserve a document claim that cannot be verified from the canonical document store.

## Rehearsal

A temporary private schema was created inside the evidence branch. Only the target rows and their dependent records were copied into rehearsal tables.

The rehearsal applied this sequence:

1. assert the five-row shape and the single exact authenticated principal;
2. retain the canonical owner row;
3. merge only non-conflicting career fields into the canonical profile;
4. remove legacy CV filename/status claims from the rehearsal profile;
5. reassign UUID-keyed chat and learning rows;
6. normalize text-keyed learning, onboarding, and job-context ownership;
7. remove duplicate owner/profile rows from the rehearsal copies;
8. validate ownership cardinality, counts, and orphan absence.

One first attempt stopped on an intentionally fail-closed conflict assertion because the assertion expression treated absent values incorrectly. The transaction rolled back. The assertion was corrected to compare only non-null values, then the full rehearsal passed.

### Validated post-state

- owner rows: **1**;
- profiles: **1**;
- chat messages: **1,463**, unchanged;
- text-keyed learning signals: **24**, unchanged;
- job-context rows: **13**, unchanged;
- completed onboarding states: **1**;
- stale CV claim rows: **0**;
- orphaned chat rows: **0**;
- orphaned learning rows: **0**;
- distinct learning owners: **1**;
- distinct job-context owners: **1**.

## Rollback proof

The temporary rehearsal schema was dropped after validation. A final read of the original evidence-branch tables confirmed they remained unchanged:

- five owner rows;
- five profiles;
- 1,463 chat messages;
- 24 learning signals;
- 13 job-context rows;
- five onboarding rows;
- no rehearsal schema remaining.

## Decision for `#1389`

The data blocker is characterized; the historical PR is not made mergeable by that result.

Against current `main`, `#1389` was substantially diverged and mixed backend, frontend, identity, artifact lifecycle, tests, and documentation. It was closed without merge. Its branch history remains available for selective salvage.

After a separately authorized production consolidation window completes, the pending-artifact objective must be recut from current `main` as one or more small PRs. No old commit or test result carries forward without re-verification.

## Not authorized

This document does not authorize:

- production SQL or production row mutation;
- deletion or reassignment on production;
- bulk cleanup of other ownership clusters;
- a production repair PR before the operational repair is separately approved;
- reuse of the closed `#1389` branch as the repair vehicle;
- treating shared email alone as proof of common ownership.

## Remaining gate

A production repair requires a separate owner-controlled maintenance approval after:

1. backup/PITR availability is confirmed;
2. the exact production target is re-identified at execution time;
3. the SQL plan and rollback queries are reviewed;
4. pre/post count assertions are fixed and fail closed;
5. the legacy `applications` limitation is explicitly accepted;
6. post-repair authenticated smoke is defined.

Until that approval is given, production remains untouched.
