# Journey-1 D1 Production Consolidation Runbook

## Document contract

- **Why it exists:** defines the final, fail-closed operating package for consolidating the single mapped D1 ownership cluster.
- **Update when:** the production fingerprint, database schema, PITR/branch capability, SQL package, or post-repair smoke changes.
- **Source of truth:** this runbook and its adjacent SQL files for this maintenance operation; `PROJECT_STATUS.md` for current authorization state; live GitHub, Neon, and production evidence override prose.
- **Owner:** Rico owner. Execution requires a separately recorded final approval after review of this package.

## Authorization boundary

The owner authorized **preparation only**.

Authorized now:

- produce and review the SQL, rollback, PITR/branch, and smoke package;
- test it on non-production Neon branches;
- open a docs-only PR containing the package.

Not authorized now:

- any SQL against the production branch, including a dry run;
- production row mutation, deletion, reassignment, schema change, or repair;
- reuse or reopening of closed PR `#1389`;
- bulk cleanup of any other ownership cluster.

A later approval must name the final package head and explicitly authorize the production preflight, transactional dry run, committed transaction, and post-repair smoke.

## Package files

1. `sql/2026-07-29-d1-preflight.sql` — read-only fingerprint and stop gates.
2. `sql/2026-07-29-d1-backup-export.sql` — private target export from the mandatory pre-repair Neon branch.
3. `sql/2026-07-29-d1-apply.sql` — serializable, fail-closed consolidation; defaults to rollback.
4. `sql/2026-07-29-d1-postcheck.sql` — aggregate post-state verification.
5. `sql/2026-07-29-d1-rollback.sql` — targeted restoration from the private export; defaults to rollback.

All scripts are parameterized. No production identifier is committed.

## Verified target fingerprint

The secure mapping and current-production rehearsal both reproduced one and only one qualifying cluster:

- owner rows: **5**;
- exact authenticated-principal rows: **1**;
- non-guest email-only rows: **2**;
- guest rows: **2**;
- profiles: **5**;
- chat messages: **1,463**;
- text-keyed learning signals: **24**;
- job-context rows: **13**;
- completed onboarding rows: **5**;
- agent-settings rows: **1**, already attached to the canonical owner;
- every other enumerated ownership-bearing domain: **0** for this cluster.

Any mismatch aborts before destructive statements.

## Canonical ownership rule

The unique row whose `external_user_id` exactly matches the authenticated principal is canonical.

The decision does not use:

- recency;
- completeness;
- row order;
- chat volume;
- shared email alone;
- a guessed natural person.

The operator supplies the authenticated principal privately through the `target_principal` psql variable. It must never be pasted into GitHub, logs, screenshots, or this repository.

## Profile merge rule

The canonical profile remains authoritative for current preferences.

Only these allowlisted career fields may be filled when the canonical value is absent or JSON null:

- `skills`;
- `target_roles`;
- `years_experience`.

Each field must have exactly one distinct non-null value across the five profiles. A disagreement aborts.

The repair deliberately removes unsupported CV claims:

- `profile.cv_filename`;
- `profile.cv_status`;
- `cv_file_url`;
- `cv_text`;
- non-empty `cv_structured`.

Reason: the mapped cluster has no authoritative `user_documents` row and no pending CV artifact. A legacy filename is not proof of a stored CV.

## Data movement

The committed transaction will:

1. lock and re-identify the exact five-row target;
2. merge only the three allowlisted, non-conflicting career fields;
3. reassign all 1,463 chat messages to the canonical UUID;
4. normalize all 24 text-keyed learning signals to the canonical authenticated principal;
5. normalize all 13 job-context rows to the canonical authenticated principal;
6. collapse five completed onboarding rows into one canonical completed row;
7. preserve the existing canonical agent-settings row;
8. delete the four duplicate profiles and four duplicate owner rows;
9. run exact postconditions before commit.

No schema or migration is part of the repair.

## Locking and transaction contract

- PostgreSQL isolation: `SERIALIZABLE`.
- Transaction-scoped advisory lock: one operation key for this repair.
- Lock timeout: short and fail-closed.
- Statement timeout: bounded.
- Target and dependent rows are locked before mutation.
- Any unexpected row, count, alias, conflict, or ownership-bearing domain aborts the transaction.
- The apply script defaults to `commit=false`; omission can never commit.

The account must remain inactive during the maintenance window. Do not run this while the affected user is using Rico.

## PITR and backup gate

The Neon connector currently reports a **24-hour history-retention window**. That is shorter than the required rollback holding period and is not sufficient by itself.

Before any production SQL:

1. create a fresh Neon branch from the exact current production head;
2. verify that the branch is `ready` and resolves to the expected database;
3. run the read-only preflight on both production and the backup branch and require identical fingerprints;
4. set or confirm a branch expiry beyond the rollback holding period;
5. execute `2026-07-29-d1-backup-export.sql` against the backup branch only;
6. store the exported files in an owner-controlled encrypted location outside the repository;
7. verify the manifest counts before proceeding.

The backup branch and encrypted export remain until seven days after successful production smoke. Their identifiers and credentials remain private.

## Execution sequence

### Gate A — exact package

- Confirm this PR's final head.
- Confirm all exact-head CI and independent review are green.
- Confirm the SQL files have not changed after review.
- Record final owner authorization naming the head SHA.

### Gate B — production and backup identity

- Read production `/version` and `/health`.
- Confirm the production database branch through the owner-controlled Neon console.
- Create the pre-repair backup branch.
- Run matching read-only preflights.
- Export the private target backup and verify its manifest.

### Gate C — non-committing production rehearsal

Only after final authorization:

- run the apply script with `commit=false`;
- require all assertions to pass and the transaction to roll back;
- rerun preflight and require the original five-row fingerprint unchanged.

Any mismatch stops the window. Do not change the SQL in place.

### Gate D — commit

Only after Gate C passes:

- run the same reviewed file with `commit=true`;
- capture only aggregate output;
- run the postcheck immediately;
- keep the account idle until application smoke passes.

## Expected post-state

- owner rows for the target email: **1**;
- canonical exact-principal row: **1**;
- profiles: **1**;
- chat messages on canonical UUID: **1,463**;
- learning signals on canonical principal: **24**;
- job-context rows on canonical principal: **13**;
- completed onboarding rows on canonical principal: **1**;
- canonical agent-settings rows: **1**;
- stale CV claims: **0**;
- rows on retired aliases in affected domains: **0**;
- orphaned UUID-owned rows: **0**.

## Application smoke

Use the affected account only after the database postcheck passes.

### Required authenticated checks

1. Login succeeds.
2. `GET /api/v1/me` returns **200**, not `ambiguous_account_ownership`.
3. `GET /api/v1/onboarding/status` returns **200** and the completed state.
4. Profile reads show the expected career fields.
5. Profile/file surfaces do **not** claim that a CV is stored when no authoritative document row exists.
6. Existing chat history remains visible; compare non-identifying first/last timestamps and total count where the API supports it.
7. Existing job context remains available.
8. Logout/login again and repeat identity/profile/onboarding reads.

### Explicit exclusions

- Do not re-upload a CV merely to test the repair.
- Do not use `/upload-cv` as the success criterion; its typed-error mapping is a separate small code objective.
- Do not combine the separate `#1432` Arabic-gratitude smoke with this account repair.

## Rollback decision

Rollback immediately when any of these occurs:

- database postcheck fails;
- identity still resolves ambiguously;
- profile/onboarding/history becomes unavailable;
- counts differ from the approved fingerprint;
- a false stored-CV claim remains;
- unexpected records or aliases appear.

The account remains idle. Run the targeted rollback package using the encrypted export. Do not restore the entire database branch over production because that could discard unrelated writes.

After rollback:

- rerun preflight and require the original five-row fingerprint;
- verify the row-level ownership mappings match the private export;
- confirm the previous fail-closed account behavior is restored;
- stop and investigate before another attempt.

## Rehearsal evidence

The package was tested on two disposable Neon branches created from the current production parent:

### Apply rehearsal

Validated post-state:

- one owner;
- one profile;
- 1,463 chat messages preserved;
- 24 learning signals preserved;
- 13 job-context rows preserved;
- one completed onboarding state;
- zero stale CV claims.

### Targeted rollback rehearsal

The original state was restored from private rehearsal backup tables:

- five owners restored;
- five profiles restored;
- five onboarding rows restored;
- one agent-settings row restored;
- chat ownership differences: zero;
- learning ownership differences: zero;
- job-context ownership differences: zero.

The disposable rehearsal branches are not production backups and must not be used during the real maintenance window.

## Final approval template

Use this only after the final PR head, checks, independent review, current production fingerprint, backup branch, and private export have all been verified:

> I approve production execution of the D1 single-cluster consolidation package at exact head `<SHA>`. This authorization covers the read-only preflight, backup verification, one `commit=false` production rehearsal, one `commit=true` production transaction only if all gates pass, the defined postcheck and authenticated smoke, and the targeted rollback only if a rollback condition is met. It does not authorize any other cluster, schema change, code deployment, CV upload, or bulk cleanup.
