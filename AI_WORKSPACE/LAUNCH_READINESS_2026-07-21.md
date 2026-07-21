# Launch Readiness Report — 2026-07-21

Owner question: "هل المنتج جاهز للنشر؟" (Is the product ready for launch?)

**Verdict: LIVE STABLE OPEN BETA — NOT commercially launch-ready yet.**
The product is publicly reachable and technically healthy, but the owner's own
launch plan (`AI_WORKSPACE/LAUNCH_EXECUTION_PLAN.md`) has explicit gates that
remain open, the largest being billing activation. This report is the Phase-0
control-plane reconciliation that plan requires before a launch decision.

Prepared by: Claude (agent), owner-directed. Evidence date: 2026-07-21 (UTC).
Supersedes, for launch-readiness purposes, the 2026-07-18 snapshot in
`PROJECT_STATUS.md` (live GitHub state overrides stale prose per the canonical
source priority).

---

## 1. Verified live snapshot

| Fact | Evidence |
|---|---|
| `main` | `0b94c55` (2026-07-21) |
| Backend live on latest code | `Deploy Render Backend` success for every runtime merge today (latest verified `c626521f`); the workflow gates on `/version.commit` match — this IS live-backend proof |
| Frontend | Vercel deployments green on every push today |
| Public access | Site OPEN (teaser gate removed `96b7efd`); `/signup`, `/login`, email verification enforced before login |
| Billing | Paddle merged, **Sandbox**, `NEXT_PUBLIC_BILLING_MODE` NOT set in production → **no live revenue path**. USD 21.50/mo authoritative (`403c28b`); AED 79 display note. WhatsApp-assisted channel exists, flag OFF |
| Strategy | DEC-20260721-001 accepted: stabilize → daily loop → data moat → reach → employers. Stabilization slices 1–3 MERGED today (#1285 atomic ownership, #1293 ops observability, #1296 real-wrapper contract tests) |
| Direct URL probe | Not possible from this sandbox (egress proxy 403) — deploy-workflow gating used as evidence instead |

### Merged today (2026-07-21) — velocity context
Audit + test-truth repair (#1256), dead-stack removal −2,053 lines (#1260), CI
coverage widened (#1261), bilingual agent intent + replies (#1266, #1288),
apply-link trust-field fix (#1259), atomic operation ownership (#1285), admin
observability (#1293), contract tests (#1296), hedged provider cascade perf
(#1291), steps-to-apply search logic (#1294), CSP enforced (#1292), `/me` +
onboarding rate limits (#1283), smoke hardening (#1286, #1287), scheduled-search
program (#1249 series), records syncs (#1284, ledger closures).

---

## 2. Launch-plan gate status (LAUNCH_EXECUTION_PLAN.md sequence)

| # | Gate | Status | Evidence / blocker |
|---|---|---|---|
| 0 | Control-plane reconciliation | ✅ **THIS REPORT** + #1284 records sync | PROJECT_STATUS snapshot (07-18) now superseded here |
| 1 | Open-PR cleanup & ownership map | 🟡 Triage below (15 open) | Needs owner dispositions (§3) |
| 2 | Route/design parity | 🟡 Matrix below (§4) | Core surfaces live; owner visual smoke pending on recent merges |
| 3 | Launch-critical UI completion | 🟡 | Command v5 program in flight (TASK-20260720-004/005, ref #1238); `/dashboard` + `/command` live |
| 4 | AED 79/month billing | ⛔ **NOT ACTIVE** | Sandbox only; production activation + price decision (USD 21.50 vs AED 79) = owner action |
| 5 | Branded secure invitations | ⛔ Not started | Per plan; no code merged |
| 6 | Launch smoke + rollback readiness | 🟡 | Smoke workflows exist & hardened today (#1286/#1287, SMOKE-1197); owner end-to-end smoke evidence not recorded |
| 7 | Owner approval to open access | ⏸ | Site already open (beta); *commercial* open pends gates 4–6 |
| — | Security containment (posture 2026-07-16) | ❓ **UNVERIFIED** | Owner-side credential rotation of the exposed local env cannot be verified from the repo — owner must confirm before launch |
| — | Legal pages | 🟡 | `/privacy`, `/terms`, `/refund-policy` routes exist; legal-review sign-off not recorded |

---

## 3. Open-PR triage (15 open, snapshot 2026-07-21)

Classification per plan Phase 0: ACTIVE / REVIEW / HOLD / STALE-CLOSE / REFERENCE.

| PR | Title (short) | Class | Note |
|---|---|---|---|
| #1295 | security MEDIUM-4 Dockerfile production-safe | **ACTIVE** | Last of today's security series — merge candidate after CI |
| #1206 | auth: timing-enumeration oracle in /resend-verification | **ACTIVE** | Security; pre-launch merge candidate |
| #1138 | auth: per-user auth_version JWT invalidation (#1072) | **ACTIVE** | Security; 4 days old — needs rebase + re-CI |
| #1129 | erasure: wire all user erasure surfaces | **ACTIVE** | Privacy/compliance — should precede commercial launch |
| #1230 | chat: image attachments vs CV storage quota | REVIEW | Product fix; verify against today's main |
| #1224 | chat: Arabic "browse the market" runs real search | REVIEW | May interact with #1294 (steps-to-apply) — rebase check |
| #1241 | web test: chat-confirm-profile deterministic fix | REVIEW | Test-only; unblocks FE flake |
| #1124 | Settings theme dropdown (non-draft) | REVIEW | Small UI; only non-draft open PR |
| #1002 | settings honest "Discuss with Rico" labels | REVIEW→STALE? | 9 days old; re-validate against current settings |
| #988 | CI: hide noisy bot comments | REVIEW | Utility; low priority |
| #1177 | agent external reasoning layer | **HOLD** | Architecturally significant **+ migration collision: adds `047_reasoning_traces.sql` but `047_analytics_events.sql` already exists in main** — must renumber before any merge |
| #1025 | Memory Engine M1 | **HOLD** | Owner-frozen, flag OFF (unchanged) |
| #1238 | Command Workspace v5 art-direction handoff | REFERENCE | Design evidence for the v5 program |
| #1204 | applications stage accents (v4 reference) | STALE-CLOSE? | Likely superseded by v5 direction — owner call |
| #1136 | read-only reconciliation audit (07-17) | **STALE-CLOSE** | Superseded by #1284 + this report |

(#1055 Gmail M0 is no longer open — previously held/frozen; no longer on the board.)

---

## 4. Route matrix (from `apps/web/app/` + `next.config.js` redirects)

| Surface | Routes | State |
|---|---|---|
| Public | `/`, `/about`, `/contact`, `/faq` | Live |
| Legal | `/privacy`, `/terms`, `/refund-policy` | Routes live; legal sign-off not recorded |
| Auth | `/signup`, `/login`, `/forgot-password`, `/reset-password` | Live; email verification enforced |
| Onboarding | `/onboarding` | Live (CV persistence #963 done) |
| Workspace core | `/command` (primary chat surface), `/dashboard` (Shell C home), `/profile`, `/settings`, `/subscription` | Live; Command v5 reskin in flight |
| Career workflow | `/applications`, `/flow`, `/queue` | Live |
| Redirect-only (No-Dead-UI rule) | `/chat`, `/jobs`, `/signals`, `/archive`, `/saved-searches`, `/orchestrate` → `/command` | Compliant by design |
| Internal/preview | `/design-gallery`, `/design-preview`, `/rico-preview`, `/sandbox`, `/_atelier`, `/admin` | Not launch surfaces — confirm `/admin` + previews are auth-gated / excluded from marketing paths |

---

## 5. New anomalies found while compiling this report

1. **Duplicate migration number 050** in `main`: `050_chat_operations.sql` AND
   `050_user_avatars.sql`. Alphabetical application order keeps them working
   today, but the numbering invariant is broken — renumber one (e.g. 051) in a
   small PR before any further migration lands.
   **RESOLVED (owner-directed, 2026-07-21 — TASK-20260721-012):**
   `chat_operations` renumbered to **051** (user_avatars kept 050: earlier in
   git history AND created earlier in production per pg_class oid order —
   both tables verified present in production via read-only Neon check).
   All code/test/drift-guard/ledger references updated, and a permanent
   uniqueness test (`test_migration_numbers_are_unique`) now blocks this
   collision class in CI.
2. **#1177 migration collision** (047) — recorded in triage above.
3. `PROJECT_STATUS.md` "Verified control snapshot" still dated 2026-07-18 —
   this report supplies the current reconciliation; a PROJECT_STATUS refresh
   should ride the next control-plane docs PR (not edited here to avoid
   racing the other active sessions).

---

## 6. Owner decision list (the launch checklist, in order)

1. **Confirm credential rotation** from the 2026-07-16 containment posture
   (yes/no — unverifiable from the repo).
2. **Billing activation decision**: set production Paddle mode + confirm the
   price presentation (USD 21.50 authoritative vs AED 79 display).
3. **Disposition the PR board** per §3 (approve ACTIVE security merges #1295,
   #1206, #1138, #1129; close STALE; keep HOLDs frozen).
4. ~~**Renumber the duplicate 050 migration**~~ — DONE (TASK-20260721-012: chat_operations → 051; uniqueness now CI-enforced).
5. **Invitations workflow** go/no-go (Phase 5 of the plan — not started).
6. **Owner end-to-end smoke** on the live product (signup → onboarding → CV →
   search → apply-link → subscription page, EN + AR) — record the evidence.
7. **Legal sign-off** on `/privacy`, `/terms`, `/refund-policy`.
8. Then: launch approval (Phase 7).

**Bottom line:** الأساس التقني صلب وتحسّن كثيراً اليوم؛ ما يفصلك عن "الإطلاق"
ليس شيفرة ناقصة بل ثمانية قرارات/إجراءات مالك أعلاه — وأثقلها الفوترة (البند 2)
وتأكيد تدوير الأسرار (البند 1).
