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

## Reconciliation — 2026-07-28 (post-`#1422`)

### Verified control snapshot

| Field | Value | How it was established |
| --- | --- | --- |
| `main` | `c64aa99158695c78138e15ca4d6dfb57b5c762c7` | Fetched live from `origin/main` at the moment this section was written |
| Deployed backend `/version` | **`c64aa99` — verified** | `/version.commit` matched `c64aa99` |
| `/health` | **200 / ok** | Same read: `jooble`, `adzuna` and `jsearch` configured and **not** degraded |
| Application/runtime baseline | `c64aa99` — **equal to `main`** | `#1422` touches `src/rico_chat_api.py`, so the `src/**` deploy filter matched and the deploy fired on merge |
| Production evidence class | **owner/browser-verified** | Not an automated artifact, and not a regression gate — see "Production verification" below |
| Governing strategy | `DEC-20260723-001`: no new feature expansion until trust and execution reliability are repaired | Unchanged. `#1422` is trust repair, not expansion |

**`main` and the deployed `/version` are asserted equal at this pass.**

The previous snapshot of this section recorded `dac8d8e7` as the baseline and stated that PR2 had not started. **Both claims were stale at the moment this pass ran** and are corrected here: eight PRs have merged since, and PR2 is delivered.

### `#1422` — merged, deployed, owner-verified

D3 truthful CV read-failure handling. Approved head `f8073ad28fac798eb44828f98d8d8f7f3c4c63ff`, squash-merged as `c64aa99158695c78138e15ca4d6dfb57b5c762c7` onto base `3f2805de`.

**The invariant it establishes: READ FAILURE != VERIFIED ABSENCE.**

Delivered behaviour — a failed CV grounding or document read no longer becomes any of:

- "no CV";
- "no stored CV";
- unreadable-document blame;
- upload or re-upload guidance;
- `next_action="upload_cv"`.

English and Arabic are both covered. A genuine successful empty read remains a genuine absence, and a genuine `no_readable_content` remains a content problem — only a *failed read* is reclassified. The exception remains contained inside the chat turn. No route, migration, schema or frontend change.

**Structural consequence** — the invariant, the boundary it implies, and the migration rules that follow from it are recorded in `AI_WORKSPACE/ARCHITECTURE.md`, not restated here.

### Production verification — what this evidence can and cannot carry

The `/version` and `/health` reads above were taken by the owner through a browser session. **That is real evidence of live behaviour and it is not a regression gate.** Nothing may cite it as a substitute for a test.

**No deliberate CV-store failure smoke was performed.** The behaviour `#1422` changes is therefore *not* covered by any production observation at this baseline — it is covered by its unit tests only. Do not record or repeat this smoke as evidence that the D3 path was exercised in production.

### Merged since the previous control-plane reconciliation (`#1417`)

Listed in merge order. Full narratives live with the document that owns each fact — the forward sequence in `ENGINEERING_ROADMAP.md`, lane detail in `TASKS.md`, structural rules in `ARCHITECTURE.md` — and are deliberately not duplicated here.

| PR | Merge commit | What it is | Runtime paths |
| --- | --- | --- | --- |
| `#1405` | `20037d2c3adb5a372bd1355c7e1edbc8c4f01b1f` | ambiguous ownership mapped to 409 on onboarding status and CV upload | `src/` — deploy expected |
| `#1410` | `2757f53b554e15257fe298abd17a239916f8eeae` | central chat ownership resolver | `src/` — deploy expected |
| `#1418` | `b7e3aedc8d2c64624da335405a98190a40c87585` | session-switch/send race | `src/` — deploy expected |
| `#1370` | `4f1af6bcba8680317d52dbf0ffc5e51711e84693` | public pricing page | `apps/web/` — Vercel |
| `#1419` | `1ea1d973161b261de9463d5a1434f3d5b4928874` | **PR2** — fail-closed job-search routing and buffered delivery | `src/` — deploy expected |
| `#1420` | `0d826b31396ba435d66f9a5dd0823fe86bb0756d` | CI enumeration coverage correction | CI-only — no deploy expected |
| `#1421` | `3f2805de4028451e316937a3c2b631c3bced1548` | degraded early-exit lifecycle state correction | `src/` — deploy expected |
| `#1422` | `c64aa99158695c78138e15ca4d6dfb57b5c762c7` | **D3** truthful CV read-failure handling | `src/` — deploy fired; `/version` confirms |

Only the final commit in this sequence carries a `/version` read. The intermediate runtime merges were superseded by the next merge before any independent per-commit deployment verification was taken, so **no per-commit deploy evidence is claimed for `#1405`, `#1410`, `#1418`, `#1419` or `#1421`.** They are in `main` and in the deployed tree at `c64aa99`; that is the whole of the claim.

For merges that touch no runtime path, `main` moving ahead of the deployed `/version` is **expected divergence, not deployment drift**. Do not chase parity, and do not fire a deploy to manufacture it.

## Active PRs — read live at this pass

| Lane | PR | Branch | State |
| --- | --- | --- | --- |
| L2 CV and documents | `#1389` | `claude/cv-pending-artifact-confirm` | **Open, Draft, and on owner HOLD.** See below |
| L8 job-search contract | — | — | No open PR. PR1 (`#1416`) and PR2 (`#1419`) are merged |
| L9 Journey-1 CV truthfulness | — | — | No open PR. `#1422` is merged |

**`#1389` is HOLD, not "unblocked".** The previous snapshot of this file said its blocker had cleared and that it "must rebase onto `dac8d8e7` before anything else". **That instruction is withdrawn.** The PR body carries an explicit owner HOLD ruling behind an upstream *production data* problem — several ownership rows for one account — which is not a code defect on that branch and is not cleared by any merge listed above.

Until the owner rules otherwise: **do not rebase, edit, reopen, mark Ready, merge, or use `#1389` as an implementation branch.** Nothing in this document resumes it, and its Draft state is not an invitation.

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

The previous order is **spent**, and its final entry was wrong: it named `#1389` as the next executable item, which the owner HOLD forbids.

There is **no queued merge** at this pass.

1. **Immediate execution is a tests-only characterization of Journey-1 CV routing** — recorded as `TASK-20260728-001` in `TASKS.md`. It is a separate PR, it is not started, and it is not started in the same PR as this reconciliation.
2. **PR3 is not the immediate next action** merely because PR2 is delivered. PR3 → PR5 remain planned and unauthorized; see `ENGINEERING_ROADMAP.md`.
3. `#1389` stays on HOLD.
4. Everything else stays deferred under `DEC-20260723-001`.

The forward engineering sequence (PR1 → PR5) lives in `ENGINEERING_ROADMAP.md` under Phase 2 — Hardening. It is **not** duplicated here: this file carries current control state, not forward plans. **PR1 is delivered as `#1416`; PR2 is delivered as `#1419`.**

Branch protection is enabled by the owner, with `trusted-ratchet` as the only Required status check.

## Open residuals — documented is not authorized

The following are known-open. **Recording one here does not authorize acting on it.** Each needs its own scoped, owner-authorized PR.

1. **My Files still converts its own failed read into `files=[]`** — the same defect class `#1422` fixed on the chat path, still live on an adjacent surface.
2. **Arabic and English CV routing diverge** at `_looks_like_cv_intent_no_file`, which intercepts Arabic CV phrasing before intent classification.
3. **D1** — ownership/data consolidation residuals, including the multi-row production account behind the `#1389` HOLD.
4. **D2** — pending-artifact activation.
5. **D4** — mission/dashboard truth.
6. **D5** — first-useful-result activation.
7. **Stored-CV / CV-state logic remains spread across `src/rico_chat_api.py`**, answering "does the user have a CV?" from several independent gates.

> **Naming collision, stated so it cannot mislead.** These `D1`–`D5` labels are the **Journey-1 defect series**. They are unrelated to the older `D1`–`D5` rows in the security-audit table further down `TASKS.md`, which describe entirely different findings. Always qualify the series when citing one.

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

Baseline is c64aa99. PR1 (#1416) and PR2 (#1419) are delivered. D3 (#1422) is
merged, deployed and owner-verified. All their leases are released and their
write authorizations revoked.

After this reconciliation PR is reviewed and merged: open a SEPARATE, tests-only
characterization PR for Journey-1 CV routing — TASK-20260728-001 in TASKS.md.
It changes tests only. It is not started here.

PR3 is NOT authorized. #1389 is on owner HOLD and must not be rebased, edited,
reopened, marked Ready, merged, or used as an implementation branch.

No merge, no deploy, no database mutation, no real-CV upload, and no bulk Neon
branch deletion is authorized by this document.
```
