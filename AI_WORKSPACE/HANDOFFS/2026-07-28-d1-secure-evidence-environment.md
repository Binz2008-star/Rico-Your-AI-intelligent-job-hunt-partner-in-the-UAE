# Handoff — Journey-1 D1 secure row-level evidence environment

> **Two corrections applied when this handoff was committed, both verified live against
> GitHub on 2026-07-28:**
>
> 1. The original draft carried a banner saying *"do not commit this file to `#1430`"*
>    because that PR was Draft and closed to scope growth. **`#1430` has since merged**
>    (`8c6c421f`, at its reviewed head `f504a37a`), so the banner has no referent and is
>    removed. This file is committed on its own branch, as the banner intended.
> 2. The original acceptance criterion *"`#1430` is still Draft at `f504a37a` and
>    unmerged"* is **void** and is struck below rather than silently dropped.
>
> **Neon infrastructure identifiers — branch ID, compute ID, project ID — are deliberately
> absent from this file.** They are operational-only and live with the owner. The Neon
> *branch name* is recorded because the work is unperformable without it and it is not a
> production data identifier.

Task record: `TASK-20260728-003` in `AI_WORKSPACE/TASKS.md`.

## Task

Perform secure row-level ownership mapping and consolidation **rehearsal** for the
Journey-1 D1 findings and the `#1389` HOLD, entirely inside a temporary Neon branch, and
produce a public report containing aggregates and non-identifying conclusions only.

**This task produces evidence and a rehearsal. It does not produce a production repair,
and completing it does not authorize one.**

## Owner authorization — verbatim scope

The owner authorized a secure row-level evidence environment on 2026-07-28.

**Authorized:**

- Read and analyze row-level identifiers **only inside the temporary Neon branch**.
- Create temporary private mapping structures **inside that branch**.
- Rehearse consolidation **inside that branch only**.
- Produce a public report using aggregates and non-identifying conclusions only.

**Not authorized:**

- Any production mutation.
- Any production schema change.
- Any deletion or reassignment on production.
- Publishing identifiers in GitHub, `AI_WORKSPACE`, chat, logs, screenshots, or PRs.
- Moving `#1389` from Draft/HOLD.
- Reusing the D1 public cluster labels as permanent identifiers.
- Creating a production repair PR.
- Exposing credentials.

## Context

- Repository: `Rico-Your-AI-intelligent-job-hunt-partner-in-the-UAE`
- **`#1430` — MERGED** as `8c6c421f`, at head `f504a37a`, 2026-07-28T17:49:52Z. Branch
  `docs/journey1-d1-readonly-assessment`. Nothing diverged between review and merge.
- `main` at this handoff: `8c6c421f` (docs). **Runtime baseline unchanged: `383dcb6c`**,
  and production serves it — three docs-only merges do not move the deployed commit.
- Prior deliverable — **read this first, do not re-derive it:**
  `AI_WORKSPACE/EVALS/2026-07-28-journey1-d1-production-data-assessment.md`
- Predecessor task: `TASK-20260728-002`, now `done`.
- Binding rules: `AI_WORKSPACE/OPERATING_RULES.md`, `CLAUDE.md` → Product Generalization
  Rule, and the public-output contract reproduced below.

### The evidence environment

The owner created this branch manually in the Neon Console on 2026-07-28. **Do not create
another one.**

- **Branch name:** `d1-ownership-evidence-2026-07-28`
- **Parent:** `production`, LSN-pinned point-in-time clone
- **Created:** 2026-07-28 22:07:29 +04
- **Expiry — EXTENDED to 30 days by the owner on 2026-07-28**, superseding the original
  2026-08-04 auto-delete. Effective deletion on or about **2026-08-27 +04**; the branch
  overview in the Neon Console holds the authoritative timestamp.

**The schedule constraint is cleared** — the original seven-day window would not have fit
mapping plus a full rehearsal, and it no longer applies. **Re-read the live expiry before
starting a long session** rather than trusting this line. Do not let the branch lapse
mid-rehearsal and do not silently re-create it; a fresh branch would be a different
point-in-time snapshot and would invalidate every mapping built against the old one.

## Tooling state — read before you plan

Verified 2026-07-28: **no Neon MCP server is authenticated**, `neonctl` is **not
installed**, and **no `NEON_API_KEY` or Neon config** exists in the session environment.
Two setup routes exist — hosted OAuth at `https://mcp.neon.tech/mcp`, or the local
`@neondatabase/mcp-server-neon` with a project-scoped API key. **Confirm which one is live
before planning any read.** If neither is connected, stop and say so rather than looking
for a credential.

**The credential is held by the MCP server's own config. An agent may not receive a DSN or
an API key.**

### The containment gap — state this to the owner before the first row-level read

The Neon MCP server is **not read-only**. It exposes `run_sql`, migration preparation, and
`delete_branch` against **every branch the credential can reach, including `production`**.
A project-scoped key limits *which project*, not *which branch*.

**Therefore "evidence-branch-only" is a discipline you follow, not a wall the tooling
enforces.** Practical consequences:

1. **Assert the target branch on every single call.** Never rely on a default. If a tool
   call does not let you name the branch explicitly, do not make that call.
2. **Verify before you write anything.** The first statement of any session must confirm
   which branch the connection is actually on. If it resolves to `production`, stop.
3. A hard guarantee exists if the owner wants one: a Postgres role scoped to
   `d1-ownership-evidence-2026-07-28` with no access to `production`. The owner must
   create it and wire it into the MCP config.

### A second production path exists, and it is not the target

`rico-job-automation-api.env` at the repository root holds a **production** DSN — the only
database credential reachable from a shell on the owner's machine. **It must not be used
for this task:** it resolves to `production`, which is a stop condition, not the target.
Any agent session with shell access can reach production with full write privileges
through it. Rotation is tracked as the open **Owner P0** in `ENGINEERING_ROADMAP.md` and is
**not agent-actionable**.

## Constraints — the binding ones

- **Production is untouchable.** No `UPDATE`, `DELETE`, `INSERT`, `MERGE`, DDL, migration,
  or schema change against the `production` branch, under any justification, including a
  "trivially safe" one-row correction and including anything the rehearsal proves correct.
- **Writes are permitted inside `d1-ownership-evidence-2026-07-28` only**, and only for
  temporary mapping structures and rehearsal. That branch is disposable; treat every
  object created in it as expiring with it.
- **`#1389` stays untouched** — not rebased, edited, reopened, marked Ready, merged, or
  used as an implementation branch. This task characterizes and rehearses; it does not
  lift the HOLD. Only an owner ruling can.
- **No production repair PR.** Not as a draft, not "for review", not as a migration file.
- **No `src/`, no `apps/web/`, no tests, no workflows, no environment variables.**
- **No credentials in chat, files, logs, commit messages, or PR text.**

### Public-output contract — unchanged and binding

**The repository deliverable MAY contain:** aggregate counts; cluster shapes; dates and
ranges where non-identifying; **ephemeral labels only**.

**The repository deliverable MUST NOT contain any raw or linkable production identifier**,
including `user_id`, row or database IDs, UUIDs, account IDs, document or CV IDs, operation
IDs, email addresses, phone numbers, Telegram handles, names, IP addresses, filenames, CV
content, authentication identifiers, or **hashes and tokens derived from any of those
values**.

- **No deterministic pseudonyms and no deterministic hashes.** A label that lets the same
  row be tracked across two reports is a linkable identifier however it was generated.
- **Row-level mapping lives in the Neon branch and nowhere else.** It does not go into
  `AI_WORKSPACE`, a PR body, a PR comment, a commit message, a log, a screenshot, or a
  build artifact.
- **The joining signal is reported as a category only** — `email` / `phone` / `Telegram` /
  `user_id` — never its value.
- **`Cluster A`–`Cluster D` expired with the D1 report.** Mint fresh ephemeral labels for
  the new report and state that they too expire with it. Reusing the old letters to mean
  the same clusters is exactly what the owner prohibited.

## What the D1 assessment already established — do not re-derive

Read the EVAL for the full record. Established on the 2026-07-28 snapshot:

- `rico_users`: 239 rows — 90 guest/public principals, 149 non-guest. No missing
  `created_at`. Observed creation range 2026-05-09 → 2026-07-22.
- Four connected ownership-signal clusters, joined by category only: 22 rows
  (Telegram + phone), 5 rows (email), 2 rows (email + phone), 2 rows (phone).
- 21 guest rows carry at least one trusted identity field; latest update 2026-06-13.
- 74 guest rows carry `completed` onboarding; completion range 2026-05-11 → 2026-06-12.
- Every observed residual **predates** the complete guard set, and no row was created
  after it went live. So there is **no post-guard sample**: "the guards stop new ones" is
  neither established nor disproven by production data. Do not upgrade that to "verified".
- The earlier "three latent mismatched rows" figure is **unreproducible** — no query
  contract was recorded. Under the current explicit definition it is 4, of which 2 are
  standalone. Do not carry the old number forward.

### What remains unestablished — this is the actual work

- The `#1389` cluster could not be bound to an account without a production identifier.
  The resolver-equivalent aggregate found **one duplicated email value with three
  non-guest rows**, and **no five-row non-guest set**. A five-row connected email
  component exists but is **three non-guest plus two guest**. The historical "five
  non-public rows" claim does not reproduce.
- Which row, if any, is canonical.
- Which dependent records belong to one natural person.
- Whether the 22-row shared phone value represents one person, shared contact data,
  legacy contamination, or several unrelated people. Two simplistic placeholder tests were
  ruled out; that is all.

## What this task must establish

1. **Row-level mapping, inside the branch only** — for each cluster, which rows exist,
   which dependent records hang off each, and what evidence bears on common ownership.
2. **A canonical-row rule**, stated explicitly, with the evidence that justifies it — not
   "most recent" or "most complete" asserted as self-evident.
3. **A per-domain reassignment matrix** covering career state, CV/documents, chat,
   onboarding, settings, subscriptions, and learning — plus the legacy `applications`
   table, which the D1 assessment could not attribute because it lacks a usable ownership
   key. Resolve or record that gap.
4. **A rehearsed consolidation inside the branch**, with validation queries proving the
   post-state and rollback queries proving reversibility, and an explicit count of what
   the rehearsal touched.
5. **Whether the `#1389` account can now be identified** with row-level access — and if it
   can, what the correct repair would be, stated as an unauthorized option.
6. **What still cannot be determined**, recorded as unknown rather than estimated.

Apply the Product Generalization Rule: the fix must be global and user-agnostic. If a
proposed consolidation only helps one account, it is invalid. State explicitly whether
each finding affects one user, one profile state, one locale, one provider, or all users.

## Acceptance criteria

- [ ] Zero production writes — demonstrable from the commands run.
- [ ] Every row-level read and write is provably scoped to
      `d1-ownership-evidence-2026-07-28`, with the branch asserted per call.
- [ ] Zero raw or linkable production identifiers in the report, the PR body, PR comments,
      commit messages, screenshots, logs, and build artifacts.
- [ ] Fresh ephemeral labels; the D1 report's `Cluster A`–`D` are not reused.
- [ ] A canonical-row rule is stated with its justifying evidence.
- [ ] A per-domain reassignment matrix exists, including the `applications` gap.
- [ ] The rehearsal ran inside the branch with validation and rollback queries recorded.
- [ ] Every repair option is marked unauthorized with its missing preconditions.
- [ ] Unknowns are listed as unknowns.
- [ ] `#1389` is still Draft and on HOLD, and the deliverable says so.
- [x] ~~`#1430` is still Draft at `f504a37a` and unmerged.~~ **VOID.** `#1430` merged as
      `8c6c421f` at that exact head on 2026-07-28, before this task was opened. The
      criterion existed to stop scope growth into a PR under review; that PR is merged, so
      it has no referent. **The successor report goes on its own fresh branch and PR.**

## Required verification

```bash
gh pr view 1430 --json number,isDraft,state,headRefOid,reviewDecision
```

```bash
gh pr view 1389 --json number,isDraft,state,headRefOid
```

No unit tests, integration tests, frontend build, or deploy smoke apply — this is an
assessment and a rehearsal, not a release.

## Stop conditions

Stop and ask the owner when:

- no Neon MCP or equivalent scoped access is connected;
- a connection resolves to `production` rather than the evidence branch;
- a read or rehearsal step would require touching production;
- a claim cannot be established without exposing or publishing a production identifier —
  **record it as unestablished and stop there**;
- the branch expiry is approaching and the work is not complete;
- a finding appears to require immediate corrective action. **"It looked urgent" is not
  authorization to mutate a row.**

## Rollback plan

- Inside the branch: nothing to preserve — the branch is disposable and auto-deletes.
- Production: nothing to roll back, because production is never written.
- Documentation: revert the report commit, or close its PR unmerged.

## Next exact action

```text
1. Confirm which Neon access route is live. If none, stop and report.
2. Confirm the connection resolves to d1-ownership-evidence-2026-07-28, not production.
3. Ask the owner to extend the branch expiration past 2026-08-04 22:07 +04 before
   starting long work.
4. Read AI_WORKSPACE/EVALS/2026-07-28-journey1-d1-production-data-assessment.md in full.
5. Restate the containment gap to the owner and get an explicit go-ahead for the first
   row-level read.

LEAVE #1389 DRAFT AND ON HOLD.
NO PRODUCTION MUTATION IS AUTHORIZED — not by this handoff, not by the owner
authorization above, and not by anything the mapping or rehearsal finds.
NO PRODUCTION REPAIR PR.
```
