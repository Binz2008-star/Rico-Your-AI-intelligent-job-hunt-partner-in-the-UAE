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

## Reconciliation — 2026-07-28 (post-`#1430`, evidence-environment phase)

**This is the current pass. The post-`#1426` section below is retained for its delivery detail and is superseded only where the two disagree — and they disagree in exactly two places, both corrected here: `#1430` is merged, and the owner ruling it was waiting on has been given.**

### Verified control snapshot

| Field | Value | How it was established |
| --- | --- | --- |
| `main` | `8c6c421f04931fd2df3b60b46b8c12615369efcd` | `git rev-parse HEAD` on a clean tree at this pass, matching the live `#1430` merge commit |
| `#1430` | **MERGED** — merged `2026-07-28T17:49:52Z`, merge commit `8c6c421f`, head `f504a37a` | `gh pr view 1430 --json number,isDraft,state,headRefOid,reviewDecision`, read live |
| `#1389` | **OPEN, Draft, head `4f2abe60`** — untouched, still on owner HOLD | `gh pr view 1389 --json number,isDraft,state,headRefOid`, read live |
| Application/runtime baseline | `383dcb6c` — **unchanged**; `main` is ahead of it by docs-only commits | `#1427`, `#1429` and `#1430` touch `AI_WORKSPACE/**` only, so no `src/**` deploy filter matched |
| Deployed backend `/version` | **`383dcb6c` — verified**, `started_at` `2026-07-28T14:15:33Z` | `/version` read directly from the public endpoint by this session |
| `/health` | **200 / ok** | Same read: `jooble`, `adzuna`, `jsearch` configured and non-degraded; `deepseek` configured, reachable, fallback available |

**`main` ahead of the deployed `/version` is expected divergence here, not deployment drift** — three docs-only merges. Do not chase parity and do not fire a deploy to manufacture it.

### The correction this pass exists to make

The post-`#1426` section recorded `#1430` as **Draft, in review**, and recorded the next action as an **owner ruling on whether to establish a secure row-level evidence location**. Both were true when written. **Both are now stale:**

1. **`#1430` merged** as `8c6c421f`, at the reviewed head `f504a37a` — nothing diverged between review and merge. The assessment deliverable is on `main` at `AI_WORKSPACE/EVALS/2026-07-28-journey1-d1-production-data-assessment.md`. `TASK-20260728-002` moves `review` → `done`.
2. **The owner ruling has been given.** The owner authorized a secure row-level evidence environment on 2026-07-28. That is the ruling the merged control plane was still pointing at as pending.

   **Owner-attested, not connector-verified** — every fact in this paragraph is the owner's statement, taken on trust. **No Neon connector was ever authenticated in this session, so none of it has been confirmed against Neon itself:** that the evidence branch **exists**; that its **name** is `d1-ownership-evidence-2026-07-28`; that its **parentage** is an LSN-pinned point-in-time clone of `production`; that it was **created** 2026-07-28 22:07:29 +04; and that its expiry was **extended** to 30 days on 2026-07-28, superseding the original 2026-08-04 auto-delete. **Re-verify each of these against the Neon Console before relying on any of them.**

The successor phase is opened as **`TASK-20260728-003`** in `TASKS.md`, carrying the owner's authorized scope verbatim. **It is an evidence and rehearsal phase. It is not a repair, and opening it authorizes no production mutation.**

### The evidence environment — what it does and does not permit

**Authorized, inside the Neon branch `d1-ownership-evidence-2026-07-28` only:** reading and analyzing row-level identifiers; creating temporary private mapping structures; rehearsing consolidation; producing a public report of aggregates and non-identifying conclusions.

**Not authorized, by this document or by anything the mapping or rehearsal finds:** any production mutation, schema change, deletion or reassignment; publishing identifiers anywhere; moving `#1389` off Draft/HOLD; reusing the D1 report's `Cluster A`–`Cluster D` labels; a production repair PR; exposing credentials.

**The public-output contract from `TASK-20260728-002` carries forward unchanged and binding**, including the no-deterministic-pseudonym and no-derived-hash rules, and the rule that the joining signal is reported as a category only. **`Cluster A`–`Cluster D` expired with the D1 report.** The successor report mints fresh ephemeral labels, which expire with it in turn.

### The successor phase is blocked, and the blocker is access, not authorization

Verified at this pass: **no Neon MCP server is authenticated**, `neonctl` is **not installed**, and **no `NEON_API_KEY` or Neon config exists** in the session environment. No row-level read has been taken and none can be until the owner connects a route.

**Containment gap — record it, because it does not go away once access exists.** The Neon MCP server is **not read-only**: it exposes `run_sql`, migration preparation and `delete_branch` against **every branch the credential can reach, including `production`**. A project-scoped API key limits *which project*, not *which branch*. **"Evidence-branch-only" is therefore a discipline an agent follows, not a wall the tooling enforces.** The hard guarantee is a Postgres role scoped to `d1-ownership-evidence-2026-07-28` with no access to `production`, created by the owner and wired into the MCP server's own config — an agent may not receive a DSN or an API key. Until that exists, every call must name the branch explicitly, and the first statement of every session must confirm which branch the connection actually resolves to and abort if it is `production`.

### Credential containment

`TASK-20260728-003` must not use production credentials.
See `ENGINEERING_ROADMAP.md` → Owner P0 credential rotation.

### Schedule constraint — cleared

**The owner extended the branch expiry to 30 days on 2026-07-28** (Owner-attested, not connector-verified — no Neon MCP was authenticated in this session to confirm the extension directly), superseding the original 2026-08-04 auto-delete; effective deletion lands on or about **2026-08-27 +04**, and the Neon Console holds the authoritative timestamp. Row-level mapping across seven domains plus a rehearsal with validation and rollback queries now fits comfortably, so **schedule pressure is no longer a reason to compress the work or to skip a verification step.**

What has not changed: **do not let the branch lapse mid-rehearsal, and do not silently re-create it** — a fresh branch is a different point-in-time snapshot and invalidates every mapping built against the current one. **Access, not time, is now the only blocker.**

## Reconciliation — 2026-07-28 (post-`#1426`)

### Verified control snapshot

| Field | Value | How it was established |
| --- | --- | --- |
| `main` | `383dcb6c6c72a849891e0b55c1af80f80d4f4865` | Fetched live from `origin/main` at the moment this section was written |
| Deployed backend `/version` | **`383dcb6c` — verified** | `/version.commit` read directly from the public endpoint by this reconciliation session |
| `/health` | **200 / ok** | Same read: `jooble`, `adzuna` and `jsearch` configured and **not** degraded; reasoning provider `deepseek` configured with a fallback available |
| Backend process `started_at` | `2026-07-28T14:15:33Z` | Same read — consistent with the `383dcb6c` deploy, not a stale process |
| Deploy Render Backend @ `383dcb6c` | run `30367283239` — **success** | Read live from the Actions API |
| Application/runtime baseline | `383dcb6c` — **equal to `main`** | `#1426` touches `src/rico_chat_api.py` and two `src/` modules, so the `src/**` deploy filter matched and the deploy fired on merge |
| Production evidence class | **automated endpoint read, taken by this session** | Real evidence of what is being served. **Still not a regression gate** — see "Production verification" below |
| Governing strategy | `DEC-20260723-001`: no new feature expansion until trust and execution reliability are repaired | Unchanged. `#1424`–`#1426` are trust repair, not expansion |

**`main` and the deployed `/version` are asserted equal at this pass**, and the equality is backed by a green `Deploy Render Backend` run for that exact commit rather than by inference from the merge.

The previous snapshot of this section recorded `c64aa99` as the baseline and instructed that the Journey-1 CV routing characterization was the immediate, **unstarted** action. **Both claims were stale at the moment this pass ran** and are corrected here: three PRs have merged since, and the characterization is delivered as `#1424`.

### One standing evidence claim is corrected

Earlier passes recorded that a `/version` read is "not reproducible from an agent container" and could only be owner/browser-verified. **That is no longer true and should not be repeated.** The reads above were taken by this session directly against the public endpoint. The correction is narrow: it changes *who can take the reading*, and nothing else. A `/version` + `/health` read still proves only which commit is being served and that the process is up. It does not exercise a single changed path, and it may never be cited as a substitute for a test.

### `#1424`, `#1425`, `#1426` — delivered

All three merged today, in this order, each squash-merged onto `main`.

**`#1424` — Journey-1 CV routing characterization (`594a4d3b`).** Tests only; one new file, `tests/unit/test_journey1_cv_routing_characterization.py`. It discharges `TASK-20260728-001` and satisfies the `ARCHITECTURE.md` rule that routing and side-effect order be captured on the untouched tree *before* any extraction. It drove the real dispatcher (`_handle_active_user_inner`) rather than re-implementing the cascade, and it recorded two findings the control plane did not previously hold: a filename reference does reach `_handle_stored_cv_reference`, and **"analyse my cv please" reached a job search and read no CV grounding at all.** No production code, and every defect it surfaced was deliberately left unfixed.

**`#1425` — My Files: unavailable store is not an empty inventory (`39b44696`).** `GET /api/v1/user/files` now answers **503** with a structured `files_unavailable` detail when `_db.available` is false or the inventory read raises, instead of `{"files": [], "total": 0}`. The 503 body carries no inventory claim and no exception text, DSN, identifier or filename. `UploadAtelier` gained a fourth state — **unavailable**, with an alert panel, truthful EN/AR copy and a manual Retry — so a failed read no longer renders as "No files yet — upload your CV to get started". Any failed read counts, not just the 404/500/503 the old code special-cased. The strict xfail `#1424` left behind was converted to a passing contract, not deleted.

**`#1426` — CV-analysis asks route to analysis, not job search (`383dcb6c`).** `_CV_ANALYSIS_RE` gained the analysis verbs (analyse/analyze/critique/assess/evaluate/appraise) bound to `cv` / `resume` / `curriculum vitae`, plus an Arabic arm requiring the `(ال)ذاتية` qualifier; `src/rico/intent/gates.py` gained `is_cv_analysis_request()`, which defers to the same `classify_intent` the CV-analysis branch keys on so the gate and the router cannot drift; and the upload-announce gate now skips analysis asks the way it already skipped explicit job-listing requests. Arabic CV-analysis asks previously answered `cv_upload_guidance` with `next_action="upload_cv"` **regardless of phrasing** — that is the Arabic/English verified-absence parity this closes on the active-user path. Negative fences are asserted in both languages: `assess my profile`, `review my LinkedIn profile`, `حلل سيرة الشركة` and `راجع سيرة المرشح` must not reach `cv_analysis`, with zero CV-context and zero document reads.

**These three are one delivery arc, not three unrelated merges:** characterize the path, then fix the two defects the characterization exposed. Full narratives live with the document that owns each fact — the forward sequence in `ENGINEERING_ROADMAP.md`, lane detail in `TASKS.md`, structural rules in `ARCHITECTURE.md` — and are deliberately not duplicated here.

| PR | Merge commit | What it is | Runtime paths |
| --- | --- | --- | --- |
| `#1424` | `594a4d3ba88a878b599dd9002515d9212d503094` | Journey-1 CV routing characterization | **tests only** — no deploy expected |
| `#1425` | `39b44696b2887194f1ec9de9604ee17da9231a48` | My Files: unavailable store distinguished from empty inventory | `src/` **and** `apps/web/` — backend deploy expected; Vercel separately |
| `#1426` | `383dcb6c6c72a849891e0b55c1af80f80d4f4865` | CV-analysis routing + Arabic/English verified-absence parity | `src/` — deploy fired; `/version` confirms |

### Production verification — what this evidence can and cannot carry

**No deliberate CV-store failure smoke was performed, and no CV-analysis routing smoke was performed.** The behaviour `#1425` and `#1426` change is therefore *not* covered by any production observation at this baseline — it is covered by unit and frontend tests only. Do not record or repeat the `/version` read as evidence that either path was exercised in production.

**`#1425` is the only frontend change in this window** (`apps/web/components/upload/UploadAtelier.tsx`, `apps/web/lib/translations.ts`, and a new test). **A backend `/version` read does not prove a frontend deploy** and must never be cited as though it does. What is established: the change is present on `main` at `383dcb6c` and its backend half is in the deployed tree. **No independent production frontend verification was taken in this pass** — no Vercel deployment read, and no browser check of the My Files unavailable state.

`#1424` touches no runtime path, so `main` moving ahead of a deployed `/version` on a tests-only merge is **expected divergence, not deployment drift**. Do not chase parity, and do not fire a deploy to manufacture it.

### Merged in the previous window (`#1417` → `#1422`) — retained record

Kept so the sequence is not lost when the section above is next replaced. Detail for each lives in `TASKS.md`.

| PR | Merge commit | What it is | Runtime paths |
| --- | --- | --- | --- |
| `#1405` | `20037d2c3adb5a372bd1355c7e1edbc8c4f01b1f` | ambiguous ownership mapped to 409 on onboarding status and CV upload | `src/` — deploy expected |
| `#1410` | `2757f53b554e15257fe298abd17a239916f8eeae` | central chat ownership resolver | `src/` — deploy expected |
| `#1418` | `b7e3aedc8d2c64624da335405a98190a40c87585` | session-switch/send race — **frontend only** | `apps/web/` — Vercel |
| `#1370` | `4f1af6bcba8680317d52dbf0ffc5e51711e84693` | public pricing page | `apps/web/` — Vercel |
| `#1419` | `1ea1d973161b261de9463d5a1434f3d5b4928874` | **PR2** — fail-closed job-search routing and buffered delivery | `src/` — deploy expected |
| `#1420` | `0d826b31396ba435d66f9a5dd0823fe86bb0756d` | `ci(tests): enforce identity email containment coverage` — supporting CI for the **identity-containment** track, **not** a PR2 artifact | CI-only — no deploy expected |
| `#1421` | `3f2805de4028451e316937a3c2b631c3bced1548` | degraded early-exit lifecycle state correction | `src/` — deploy expected |
| `#1422` | `c64aa99158695c78138e15ca4d6dfb57b5c762c7` | **Journey-1 D3** truthful CV read-failure handling | `src/` — deploy fired and was verified at that baseline |

**No per-commit deploy evidence is claimed for `#1405`, `#1410`, `#1419` or `#1421`** — each was superseded by the next merge before an individual verification was taken. **No independent frontend verification was ever taken for `#1418` or `#1370`.** Those claims stand unchanged; this pass did not re-verify them and does not extend today's reads backwards to cover them.

## Active PRs — read live at this pass

| Lane | PR | Branch | State |
| --- | --- | --- | --- |
| L2 CV and documents | `#1389` | `claude/cv-pending-artifact-confirm` | **Open, Draft, and on owner HOLD.** See below |
| L2 Journey-1 D1 assessment | `#1430` | `docs/journey1-d1-readonly-assessment` | **MERGED** as `8c6c421f` at head `f504a37a`. No longer an open PR; lease `RELEASED`. Its successor phase (`TASK-20260728-003`) has **no PR and no branch** — it is blocked on Neon access |
| L8 job-search contract | `#1431` | `claude/ricohunt-website-00969f` | **Open, READY, all checks green on `3b7572a3`. Not merged.** Thin-market search recovery — city-scope widening plus a labelled 3-card related tier. `TASK-20260728-004` |
| L9 Journey-1 CV truthfulness | `#1432` | `claude/gratitude-pending-search` | **Open, READY, all checks green on `d736380e`. Not merged.** A thank-you must not redeem an armed search. `TASK-20260728-005` |

**`#1431` and `#1432` were opened during the window this pass reconciles — after `#1430` merged — with no `TASKS.md` entry and no recorded lease.** `OPERATING_RULES.md` → Pull Request Audit Checklist item 11 therefore blocked both from merging: *no PR merges on a task with an empty or stale Continuity Block.* Blocks were reconstructed from the diffs and the live check runs as `TASK-20260728-004` and `TASK-20260728-005`; **they are reconciliation reconstructions, not lane reports.** Both PRs touch `src/rico_chat_api.py` **and** `.github/workflows/qa-tests.yml`, so **whichever merges second needs a rebase and a re-verified check run** — they are individually `MERGEABLE` against `main`, which is not the same as being mergeable after each other.

**Two open items belong to the owner before `#1431` merges**, and neither is an agent call: it adds **an extra provider call** on the thin-market path, and a code comment cites an **"owner directive 2026-07-28"** for the widening behaviour that **appears nowhere in the control plane**. A comment is not its own evidence.

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

The previous order is **spent**. Its first entry — the tests-only characterization — is delivered as `#1424`, and the two defects that characterization exposed are delivered as `#1425` and `#1426`.

There is **no queued merge** at this pass.

1. **The read-only Journey-1 D1 production-data consolidation assessment is delivered and merged** — `TASK-20260728-002`, PR `#1430`, merged `8c6c421f`. It read and reported, it proposed nothing for execution, and **no production Neon row mutation is authorized by it, by its findings, or by this document.** `TASK-20260728-002` is `done`.
2. **The owner ruling that assessment was waiting on has been given**, and the secure evidence environment exists as the Neon branch `d1-ownership-evidence-2026-07-28`. The successor phase is `TASK-20260728-003`: row-level mapping and a consolidation **rehearsal, inside that branch only**. **It is blocked on Neon access** — no MCP route is authenticated and no scoped credential exists — so it is authorized but **not startable**, which is not the same as queued. **No repair is queued**, and the rehearsal does not queue one however it turns out.
3. **PR3 is not the immediate next action** merely because PR2 is delivered. PR3 → PR5 remain planned and unauthorized; see `ENGINEERING_ROADMAP.md`.
4. `#1389` stays on HOLD. The D1 assessment **characterizes** the data problem sitting above that branch; it does not lift the HOLD, and only an owner ruling can.
5. Everything else stays deferred under `DEC-20260723-001`.

The forward engineering sequence (PR1 → PR5) lives in `ENGINEERING_ROADMAP.md` under Phase 2 — Hardening. It is **not** duplicated here: this file carries current control state, not forward plans. **PR1 is delivered as `#1416`; PR2 is delivered as `#1419`.**

Branch protection is enabled by the owner, with `trusted-ratchet` as the only Required status check.

## Open residuals — documented is not authorized

The following are known-open. **Recording one here does not authorize acting on it.** Each needs its own scoped, owner-authorized PR.

1. ~~**My Files still converts its own failed read into `files=[]`.**~~ **CLOSED by `#1425`** (`39b44696`). The endpoint answers 503 with a structured `files_unavailable` detail and the surface renders a distinct unavailable state. Kept visible, struck through, for one pass so the closure is legible against the list it was on; it will be dropped at the next reconciliation.
2. **Arabic and English CV routing still diverge at `_looks_like_cv_intent_no_file` — but narrowed by `#1426`, not closed.** What is delivered: on the active-user chat path, a CV-**analysis** ask in either language now reaches `cv_analysis` with authoritative grounding, so an Arabic user is no longer told to upload a CV they already have. What remains: the gate still runs *before* intent classification, and it has **two** call sites. `src/rico_chat_api.py:9319` (active user) now carries the `is_cv_analysis_request` exemption; **`src/rico_chat_api.py:8783`, on the `_process_message_inner` path taken by onboarding-incomplete users, carries no such exemption.** That asymmetry is a **code read taken during this reconciliation, not a test-proven defect** — the `#1424`/`#1426` suites drive `_handle_active_user_inner` only, so no test currently covers the second call site either way. Treat it as a lead to verify, not as an established bug, and **not** as authorization to edit either call site.
3. **English and Arabic reach different job-search terminals for the same intent** — `_target_role_search_response` vs `_handle_company_search`. Recorded by `#1424` as characterization: both satisfy the job-search contract, so this is an unexplained asymmetry rather than a known defect.
4. **Journey-1 D1** — ownership/data consolidation residuals, including the multi-row production account behind the `#1389` HOLD. **Assessed, not repaired.** `TASK-20260728-002` is delivered as `#1430` (**merged** `8c6c421f`) and its findings are in `AI_WORKSPACE/EVALS/2026-07-28-journey1-d1-production-data-assessment.md`. The snapshot holds four connected ownership-signal clusters, 21 guest rows carrying a trusted identity field and 74 guest rows carrying authenticated onboarding completion; every observed residual predates the complete guard set, so production data does **not** establish that the guards have stopped new bad rows — it merely fails to disprove it. **Being assessed is not being authorized for repair**, and the residual stays open.
5. **Journey-1 D2** — pending-artifact activation.
6. **Journey-1 D4** — mission/dashboard truth.
7. **Journey-1 D5** — first-useful-result activation.
8. **Stored-CV / CV-state logic remains spread across `src/rico_chat_api.py`**, answering "does the user have a CV?" from several independent gates. `#1424` characterized that spread; it did not reduce it, and no CV boundary is authorized.

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

Baseline is 383dcb6c, and production serves it. PR1 (#1416) and PR2 (#1419) are
delivered. Journey-1 D3 (#1422) is merged and deployed. The CV routing
characterization (#1424), the My Files unavailable-store fix (#1425) and the
CV-analysis routing / Arabic parity fix (#1426) are delivered. All their leases
are released and their write authorizations revoked.

The READ-ONLY Journey-1 D1 production-data consolidation ASSESSMENT is DELIVERED
and MERGED as #1430 (8c6c421f, at reviewed head f504a37a) — TASK-20260728-002 is
DONE. Do not re-run it and do not open a second assessment.

The owner ruling it was waiting on HAS BEEN GIVEN. A secure row-level evidence
environment is authorized and exists as the Neon branch
d1-ownership-evidence-2026-07-28. The successor phase is TASK-20260728-003:
row-level mapping and a consolidation REHEARSAL, INSIDE THAT BRANCH ONLY.

TASK-20260728-003 IS BLOCKED ON ACCESS, NOT ON AUTHORIZATION. Verified at this
pass: no Neon MCP server is authenticated, neonctl is not installed, and no
NEON_API_KEY or Neon config exists in the session environment. Do not improvise
a credential path, and DO NOT USE THE LOCAL PRODUCTION ENVIRONMENT CREDENTIAL
FOR THIS WORK — it resolves to production, which is the stop condition, not the
target.

Before the first row-level read, the OWNER must: (1) connect a Neon access route
with the credential held by the MCP server config, never passed to an agent;
(2) give an explicit go-ahead that acknowledges the containment gap recorded
above — Neon MCP is not read-only and reaches production, so branch confinement
is discipline, not a wall.

NO PRODUCTION NEON ROW MUTATION IS AUTHORIZED. Not by this document, not by
TASK-20260728-002, not by TASK-20260728-003, not by #1430, and not by anything
the assessment, the mapping, or the rehearsal finds. A finding is a finding;
repair needs its own owner authorization. NO PRODUCTION REPAIR PR.

PR3 is NOT authorized. #1389 is on owner HOLD and must not be rebased, edited,
reopened, marked Ready, merged, or used as an implementation branch — the D1
assessment characterizes the data problem above it and does not lift the HOLD.

No merge, no deploy, no database mutation, no real-CV upload, and no bulk Neon
branch deletion is authorized by this document.
```
