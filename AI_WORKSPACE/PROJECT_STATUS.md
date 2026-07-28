# Project Status — Rico AI

> **Mandatory control panel.** Every agent must read this file before planning or writing.
>
> Live GitHub `main`, exact PR heads, CI, Vercel/Render deployment evidence, Neon state, and production smoke evidence override prose. When this file conflicts with live evidence, stop implementation and reconcile this file first.

## Document contract

- **Why it exists:** one current, evidence-backed operating snapshot for Rico.
- **Update when:** production, active ownership, launch blockers, or priority order changes materially.
- **Source of truth:** this file for current control state; `AI_WORKSPACE/DECISIONS.md` for binding decisions; `AI_WORKSPACE/TASKS.md` for lane-level continuity; `AI_WORKSPACE/ENGINEERING_ROADMAP.md` for the forward sequence; `AI_WORKSPACE/ARCHITECTURE.md` for structural rules.
- **Owner:** Rico owner, with the acting CTO/session responsible for evidence-backed reconciliation.
- **History:** prior snapshots remain preserved in Git history. This file intentionally keeps current truth ahead of historical narrative.
- **SHA rule:** never make this document self-stale by claiming its own commit is the permanent current `main`. Fetch `main` live. Record the application/runtime baseline separately from docs-only control commits.

## Rule of authority

Ranked, and not negotiable when they disagree:

1. GitHub `main`, PR heads, and the deployed `/version`.
2. This file.
3. The lane continuity blocks in `AI_WORKSPACE/TASKS.md`.
4. The latest dated handoff.
5. Everything else.

**Every SHA in this file is verified from the API before it is written.** A SHA copied from a message, a summary, or a previous session is not evidence. If live state and this file disagree, reconcile this file before starting anything else.

## Reconciliation — 2026-07-28 (post-`#1426`)

### Verified control snapshot

| Field | Value | How it was established |
| --- | --- | --- |
| `main` | `383dcb6c` | Fetched live from `origin/main` at the moment this section was written |
| Deployed backend `/version` | **Not re-verified at this pass** | The previous pass verified `c64aa99`; `#1424` is tests-only (no deploy), `#1425` and `#1426` touch `src/` and are expected to have deployed, but no independent `/version` read was taken for this pass |
| `/health` | **Not re-verified at this pass** | See above |
| Application/runtime baseline | `383dcb6c` — **expected equal to `main`** | `#1425` and `#1426` both touch `src/`, so the `src/**` deploy filter matched; no per-commit deploy evidence is claimed |
| Production evidence class | **Not claimed at this pass** | No browser smoke or `/version` read was taken; the previous pass's `c64aa99` evidence remains the most recent |
| Governing strategy | `DEC-20260723-001`: no new feature expansion until trust and execution reliability are repaired | Unchanged. `#1424`–`#1426` are trust repair, not expansion |

**`main` is `383dcb6c`.** The deployed `/version` was not re-verified at this pass. The previous pass's evidence at `c64aa99` remains the most recent production verification.

### `#1424` — merged (tests-only)

Journey-1 CV routing characterization. Squash-merged as `594a4d3b` onto base `c64aa99`. Tests-only: no production code, no runtime path, no deploy. Characterized nine CV-routing scenarios through the real dispatcher, including one strict xfail recording that "analyse my cv please" reaches job search. **`TASK-20260728-001` is done via this PR.**

### `#1425` — merged

My Files store-unavailable truth. Squash-merged as `39b44696` onto base `594a4d3b`. `GET /api/v1/user/files` now returns 503 with structured detail when the document store is unavailable or a read fails, instead of converting the failure into `files: []`. An empty `files` list always represents a verified empty inventory. Frontend shows an unavailable state with retry, not an empty vault. **The My Files unavailable-store residual is closed.**

### `#1426` — merged

CV-analysis intent routing. Squash-merged as `383dcb6c` onto base `39b44696`. "analyse / analyze / review / critique my CV" (English and Arabic) now classifies as `cv_analysis` and reaches grounded CV analysis with zero job-search provider calls. The fix extends `_CV_ANALYSIS_RE` with missing verbs/nouns and adds `is_cv_analysis_request()` to the upload-announce gate. **The active-user CV-analysis routing residual is closed.** A narrowed residual remains: the onboarding-incomplete path at `_process_message_inner` still passes through `_looks_like_cv_intent_no_file` without the `is_cv_analysis_request` exemption, so Arabic CV-analysis asks from users with incomplete onboarding may still receive upload guidance. This is recorded as an open residual below and is **not authorized for fix.**

### Merged since the previous control-plane reconciliation (`#1423`)

Listed in merge order. Full narratives live with the document that owns each fact — the forward sequence in `ENGINEERING_ROADMAP.md`, lane detail in `TASKS.md`, structural rules in `ARCHITECTURE.md` — and are deliberately not duplicated here.

| PR | Merge commit | What it is | Runtime paths |
| --- | --- | --- | --- |
| `#1424` | `594a4d3b` | Journey-1 CV routing characterization (tests only) | Tests-only — no deploy |
| `#1425` | `39b44696` | My Files store-unavailable truth (503 on failed read) | `src/` + `apps/web/` — deploy expected |
| `#1426` | `383dcb6c` | CV-analysis intent routing (analyse/review/critique → `cv_analysis`) | `src/` — deploy expected |

**No per-commit deploy evidence is claimed for `#1425` or `#1426`.** Both touch `src/` and are expected to have deployed via the `src/**` filter, but no independent `/version` read was taken at this pass. The previous pass's `c64aa99` verification remains the most recent production evidence.

For merges that touch no runtime path, `main` moving ahead of the deployed `/version` is **expected divergence, not deployment drift**. Do not chase parity, and do not fire a deploy to manufacture it.

## Active PRs — read live at this pass

| Lane | PR | Branch | State |
| --- | --- | --- | --- |
| L2 CV and documents | `#1389` | `claude/cv-pending-artifact-confirm` | **Open, Draft, and on owner HOLD.** See below |
| L8 job-search contract | — | — | No open PR. PR1 (`#1416`) and PR2 (`#1419`) are merged |
| L9 Journey-1 CV truthfulness | — | — | No open PR. `#1422`, `#1424`, `#1425`, `#1426` are merged |

**`#1389` is HOLD, not "unblocked".** The previous snapshot of this file said its blocker had cleared and that it "must rebase onto `dac8d8e7` before anything else". **That instruction is withdrawn.** The PR body carries an explicit owner HOLD ruling behind an upstream *production data* problem — several ownership rows for one account — which is not a code defect on that branch and is not cleared by any merge listed above.

Until the owner rules otherwise: **do not rebase, edit, reopen, mark Ready, merge, or use `#1389` as an implementation branch.** Nothing in this document resumes it, and its Draft state is not an invitation.

Other open Draft PRs at this reconciliation pass: `#1413`, `#1374`, `#1362`, `#1359`. Their presence is not authorization to resume, rebase, mark Ready or merge. Fetch each live before acting.

This inventory deliberately excludes the reconciliation PR that writes this section: it is not a backlog item and closes on merge.

**An open PR is not permission to merge.** Per-PR heads are deliberately not restated here — they move, and a head copied into this file is stale the moment a lane pushes. Fetch them live.

### CI evidence rule

**A passing job on a different commit is not exact-head evidence and may never be cited as one.** Transience is established by the failed run's own annotation, and settled only by a re-run recorded against the same head. A re-run that goes green with no content change is the clean form of that proof: it isolates infrastructure from the diff.

## Concurrency state

Caps are rules and are fixed. **Counts are read at the reconciliation pass that writes this section**, by applying the counting rules in `OPERATING_RULES.md` to the lane blocks in `TASKS.md` as they read at that moment. They are not carried forward from any earlier report.

| Measure | Cap | At this pass |
| --- | --- | --- |
| Active agents (`WRITING` or `REVIEWING`) | 4 | 1 — this docs-only reconciliation |
| Simultaneous code writers (`WRITING` + `AUTHORIZED` + executable scope) | 2 | 0 — this pass is docs-only and does not count against the cap |
| Writers per branch | 1 | 1 on every branch holding a lease |

Lease holders appear against branches in `TASKS.md`. **That is ownership, not activity** — see `OPERATING_RULES.md` → "Ownership is not activity". Reading those assignments as concurrent work in progress is the specific misreading the four-field lease model exists to prevent.

## Standing owner rulings

- **Render billing notice — deferred, non-blocking.** Render is operational *per the owner's standing ruling* — that is the owner's statement, not a reading taken by this reconciliation, which could not reach the host. The payment reminder is acknowledged by the owner and will be handled by the owner. It is **not** a blocker for work, reviews, merges, or the roadmap. **Do not restate or escalate it.** Raise Render again only on verified service degradation, suspension, failed deployment, health-check failure, or production impact.
- **`#1389` is on HOLD** behind a production data problem, as recorded above. This is an owner ruling and is not cleared by a control-plane pass.

## Merge order

The previous order is **spent**: `TASK-20260728-001` is done via `#1424`, and `#1425` and `#1426` followed it.

There is **no queued merge** at this pass.

1. **Next action is a D1 read-only production-data consolidation assessment** — ownership/data consolidation residuals, including the multi-row production account behind the `#1389` HOLD. Read-only: no mutation of any Neon row without separate owner delegation.
2. **PR3 is not the immediate next action** merely because PR2 is delivered. PR3 → PR5 remain planned and unauthorized; see `ENGINEERING_ROADMAP.md`.
3. `#1389` stays on HOLD.
4. Everything else stays deferred under `DEC-20260723-001`.

The forward engineering sequence (PR1 → PR5) lives in `ENGINEERING_ROADMAP.md` under Phase 2 — Hardening. It is **not** duplicated here: this file carries current control state, not forward plans. **PR1 is delivered as `#1416`; PR2 is delivered as `#1419`.**

Branch protection is enabled by the owner, with `trusted-ratchet` as the only Required status check.

## Open residuals — documented is not authorized

The following are known-open. **Recording one here does not authorize acting on it.** Each needs its own scoped, owner-authorized PR.

1. **Arabic onboarding-incomplete CV-analysis routing** — the onboarding-incomplete path at `_process_message_inner` still passes through `_looks_like_cv_intent_no_file` without the `is_cv_analysis_request` exemption. The active-user path was fixed by `#1426`, narrowing this residual to users with incomplete onboarding. **Still open. Not authorized for fix.**
2. **Journey-1 D1** — ownership/data consolidation residuals, including the multi-row production account behind the `#1389` HOLD.
3. **Journey-1 D2** — pending-artifact activation.
4. **Journey-1 D4** — mission/dashboard truth.
5. **Journey-1 D5** — first-useful-result activation.
6. **Stored-CV / CV-state logic remains spread across `src/rico_chat_api.py`**, answering "does the user have a CV?" from several independent gates.

> **Naming collision, stated so it cannot mislead.** The labels above are the **Journey-1 D1–D5** series. They are unrelated to the **security-audit D1–D5** rows in the audit table further down `TASKS.md`, which describe entirely different findings. Neither series is renumbered. **Always write "Journey-1 D1–D5" or "security-audit D1–D5" — never a bare `D3`.**

## Stop conditions

Stop and report instead of guessing when:

- another writer holds the lease on the same branch or objective;
- a branch contains commits not explained by its continuity record;
- a PR scope expands across unrelated objectives;
- a schema diff appears where no migration was approved;
- a check is green only because the relevant test is outside CI;
- production mutation, billing, access-control, secret, migration, merge, or deployment action lacks explicit owner authorization;
- a UI claim is not derived from a current server read;
- a user-data workflow would require another real upload merely to test an unverified fix;
- an instruction arrives without full attribution — see `OPERATING_RULES.md` → "Directive Authority".

## Next exact action

```text
Per lane, read the continuity block in AI_WORKSPACE/TASKS.md, confirm the lease is
yours, check write authorization, fetch the remote, and compare the remote head
against the expected head recorded there before any push.

Baseline is 383dcb6c. PR1 (#1416) and PR2 (#1419) are delivered. D3 (#1422) is
merged and owner-verified. #1424 (characterization), #1425 (My Files truth), and
#1426 (CV-analysis routing) are merged. All their leases are released and their
write authorizations revoked.

Next action: D1 read-only production-data consolidation assessment. No mutation
of any Neon row without separate owner delegation.

PR3 is NOT authorized. #1389 is on owner HOLD and must not be rebased, edited,
reopened, marked Ready, merged, or used as an implementation branch.

No merge, no deploy, no database mutation, no real-CV upload, and no bulk Neon
branch deletion is authorized by this document.
```
