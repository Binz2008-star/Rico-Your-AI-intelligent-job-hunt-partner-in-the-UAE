# Audit — Read-Only Reconciliation of the Seven-Issue Local Workspace

**Date:** 2026-07-17
**Author:** Rico AI agent session (branch `claude/read-only-reconciliation-7r2hkl`)
**Status:** Read-only reconciliation. No code changed, no revert performed, no issue closed.

---

## ⚠️ ADDENDUM (2026-07-17, later the same day) — this document is a point-in-time snapshot, NOT current state

Written against `main` @ `1b6ee1c`. The same day, AFTER this audit was written, `main` moved
substantially — do not treat the sections below as the present situation:

- **#1076 is no longer "docs-only/not started": PR #1140 merged** (`907b404`), remediating it
  repo-wide with `src/log_privacy.py` (server-keyed fingerprints, Sentry scrubbing, production
  boot enforcement, repo-wide static guard). The parallel PR #1137 from this session was
  **closed without merge as superseded**; the residual chat-stream/exception-log delta was
  extracted into a small follow-up PR built on the merged helper (PR #1148).
- **#1077 remediated: PR #1142 merged** (`6e95fd9`) — the user-callable paid-provider smoke
  probe was removed.
- **#1084 remediated: PR #1134 merged**; **#1070 hardening: PR #1135 merged**.
- Remediation PRs for #1080/#1092/#1072/#1086 were opened from this session
  (#1139/#1144/#1138/#1146) and follow the owner's per-PR review queue.

The Decision Records this audit called for (DEC-20260717-001/-002) remain valid — #1096 and
#1102 are still open. Everything else below reflects the pre-merge morning state only.

---
**Input:** An owner-supplied reconciliation report describing 21 uncommitted modified files on a
local `main` checkout, mapped to issues #1080, #1072, #1076, #1096, #1086, #1102, #1092.
**Ground truth used:** GitHub `main` @ `1b6ee1c` (fresh clone), GitHub issue/PR state on 2026-07-17.

---

## 1. Where the work actually lives

**None of the described work exists on GitHub.** Verified on a fresh clone of `main` @ `1b6ee1c`:

- `src/api/upload_limits.py`, `migrations/009_add_auth_version.sql`,
  `tests/test_upload_limits_bounded_reading.py`, `tests/test_jwt_auth_version_invalidation.py`,
  and `src/logging/` do not exist.
- Repo-wide search finds no `auth_version`, `logout_all`, `SubscriptionOutcome`, or
  `read_file_bounded` anywhere in `src/`.
- `apps/web/package.json` on `main` still has `next ^14.2`, `axios 1.16.1`, `postcss ^8`.
- All seven issues are **open**. No open PR references any of them (open PRs: #1135, #1134,
  #1129, #1125-adjacent work, #1124, #1025, #1002, #988 — none overlap these seven issues'
  scope except a minor CI-file adjacency noted in §4).

Conclusion: the 21-file diff is uncommitted local state on one machine. If that machine is lost,
the work is lost. Nothing has been reviewed, tested in CI, or deployed.

## 2. Critical finding the local report missed: migration collision / stale base

- `migrations/009_saved_searches.sql` **already exists on `main`**, and migrations currently run
  through `044_guest_identity_claims.sql`. The local `009_add_auth_version.sql` collides with an
  existing migration number; the next free number is **045**.
- This strongly suggests the local work was authored against a **stale base**. Supporting
  evidence: `src/api/routers/rico_chat.py` and `src/api/deps.py` are in the local diff, and both
  were modified on `main` yesterday by the merged #1070 security work (PRs #1132, #1133 — guest
  identity binding and SID redaction).
- **Risk:** committing the local 21-file diff as-is (or resolving conflicts carelessly) can
  silently revert the just-merged guest-identity security fixes. Before any extraction, the local
  machine must `git fetch` and rebase/diff each file against current `origin/main`.

## 3. Per-issue reconciliation (corrected matrix)

| Issue | Local report's verdict | Reconciled verdict |
|---|---|---|
| #1080 upload limits | "Complete" | **Unverifiable, not mergeable.** Work exists only locally; tests were created but never run. Issue additionally requires bounded-chunk reads proven for missing/false/chunked `Content-Length`, temp-file cleanup on rejection, and no classifier/parser/quota call on rejection — none evidenced. |
| #1072 JWT invalidation | "Complete", flags normal `logout` not bumping `auth_version` as a gap | **Partially misjudged.** The issue explicitly requires *distinct* semantics for "logout this device" vs "logout all devices" — normal logout NOT bumping `auth_version` is per-spec, not a gap. The real spec violation the report itself describes: fail-open on user routes during DB unavailability, while the issue requires **fail closed for admin and mutation routes**. Also blocked by the 009→045 migration renumber (§2). |
| #1076 PII logging | "Partial — docs only" | **Confirmed incomplete.** SECURITY.md text plus an empty `src/logging/` dir. Issue requires code changes to `profile_repo`/`rico_chat`, a shared redaction helper, `caplog` sentinel tests, and a static regression guard. |
| #1096 fail-closed quotas | "Complete", flags 503-on-outage as a risk needing grace period | **Direction is per-spec, report's risk framing is off.** The issue *mandates* retryable 503 / unknown-state responses and forbids coercing unknown usage to 0 or unknown plan to Free. A last-known-entitlement cache is the issue's own optional mitigation (signed, TTL-bounded, never broadening automation) — a design decision to record in DECISIONS.md, not a defect. Still not mergeable: no tests run, and the issue's concurrency/reservation tests (exactly one durable mutation at the last quota unit) are not evidenced. |
| #1086 CI unification | "Complete" | **Unverifiable, likely under-scoped.** Disabling the legacy schedule + deploy path filters covers containment items 1 and 4 only. Items 2 (fail-closed cross-workflow lock), 3 (dashboard publication off `main`), 5 (publish only on success, no swallowed push failures) are not described in the local diff. Acceptance evidence list in the issue is broader than what the report claims. |
| #1102 Next.js / Axios | "Complete", flags Next 15.5.20 as **architecture drift** | **Report is wrong on the drift claim.** Issue #1102 *explicitly requires* upgrading to the patched Next 15 line, "currently 15.5.20", and already verified Axios has no imports in source. The upgrade target is correct. What actually blocks merge is the issue's close gate: full frontend tests/typecheck/build on the exact lockfile, browser regression (login, guest/auth `/command`, Arabic/RTL, Paddle sandbox), `/proxy/*` smuggling tests, and a reachability decision for the nested `postcss 8.4.31` (bumping the *top-level* `postcss` pin does not replace Next's nested copy without an override). None of that ran. |
| #1092 pagination | "Complete", then self-contradicts ("response format change only") | **Confirmed incomplete.** Issue requires DB-boundary filtering/paging/counting, a stable cursor or documented offset, direct-by-ID lookup for PATCH (`find_by_job_id` must stop scanning 200 rows), DB-side stats, and real-Postgres tests with 451+ seeded records. Changing `get_all()`'s return shape plus 6 call sites does not meet that bar. |

## 4. Process findings (confirmed)

1. Seven independent P1 issues developed in one working tree on local `main` violates
   `OPERATING_RULES.md` ("one branch per task", "one writer per branch") and makes per-issue
   review/rollback impossible.
2. Zero tests were executed for any of the seven changes. Test files were authored but never run.
3. `#1092` and `#1096` share `subscription_gating.py` / `applications_repo.get_all()` — they must
   be extracted in a coordinated order (land #1092's repo contract first, then #1096's typed
   outcomes on top, or vice versa — pick one and record it).
4. CI-file adjacency: open PR #1134 (workflow credential containment, #1084) touches
   `.github/workflows/render-*.yml` and adds `workflow-guards.yml` with static workflow checks.
   The local #1086 edits (`daily.yml`, `daily-job-bot.yml`, `deploy-*.yml`) touch different files
   but will be linted by #1134's new guard once it merges — extract #1086 after #1134 lands.
5. No Decision Records exist for the two decisions that need one: #1096 fail-closed semantics
   (503 vs cache grace) and the #1102 Next 15 major upgrade + nested-postcss risk acceptance.

## 5. Verdict and recommended sequence

The local report's bottom line is **correct**: the current local state must not be committed to
`main` or merged as one unit. Corrected recovery plan, in order:

1. On the local machine: `git fetch origin` and confirm the base SHA of the 21-file diff. Do not
   commit anything to local `main`. Stash or `git diff > seven-issue.patch` to preserve the work.
2. Rebase the working tree onto current `origin/main`; manually verify `rico_chat.py` and
   `deps.py` hunks do not undo the merged #1070 guest-identity fixes.
3. Extract per-issue branches (one branch, one PR, one issue), each with its tests **actually
   executed** locally and in CI:
   - #1072: renumber migration to `045_add_auth_version.sql`; make user-mutation routes fail
     closed per spec; keep per-device logout semantics as designed.
   - #1102: keep the Next 15.5.20 target (it is per-spec); run the full close gate before
     review; decide the nested-postcss override explicitly.
   - #1092 then #1096 (or the reverse, once): coordinate the shared
     `get_all()`/gating contract.
   - #1086: extract after PR #1134 merges; cover containment items 2, 3, 5, not just 1 and 4.
   - #1080: run the bounded-reading tests; add the missing rejection-path assertions.
   - #1076: this is currently docs-only; treat it as **not started** and implement the
     redaction helper + caplog tests from scratch.
4. Record two entries in `AI_WORKSPACE/DECISIONS.md` (fail-closed billing semantics; Next 15
   major upgrade with postcss risk decision) before the corresponding PRs are opened.

Nothing in this reconciliation closes, relabels, or reprioritizes any of the seven issues.
