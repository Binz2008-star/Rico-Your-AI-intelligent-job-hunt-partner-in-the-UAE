# Eval: Rico Hunt Chat — Full Live QA (2026-07-03)

- Surface: `ricohunt.com/command` (public chat), live
- Method: 12 manual test cases against a real profile (Operations Manager, ~20y, ESG/ISO/Compliance)
- Backend: `rico-job-automation-api.onrender.com` (Render free tier)
- Related tasks: TASK-20260703-038 … -043

## Summary

Core chat loop has real defects. The most severe cluster is a **single root cause** — the
intent dispatcher in `src/rico_chat_api.py` over-routes to `job_search` on the presence of a
company/role token, regardless of the sentence's verb. Relevance/scoring and i18n are separate
layers with their own issues.

Two corrections to the raw report's root-cause claims (verified against code):

1. **TC-7 is not a missing feature.** An `application_tracking` intent handler already exists
   (`rico_chat_api.py:4462`). The bug is that structured text ("Position: X. Company: Y. Track it")
   is not *classified into* that intent (or the extraction step drops it) — a classifier/extractor
   gap, not "tracking only works via a UI button."
2. **TC-9 may be a regression.** The Arabic guard was recently moved to run *after* `classify_intent`
   (#813). Per-message language detection is the fix; confirm TC-9 is not a side effect of that move.

## Findings (severity-ranked)

### 🔴 Critical
- **TC-8 — Intent misfire:** "prepare me for an interview … at Richemont" → job search instead of
  interview coaching. Router keys off company/role tokens, ignores verb.
- **TC-7 — Plain-text tracking fails:** structured "Position/Company/Track it" not saved; same
  session tracked a job from conversational context, so it's a classify/extract gap (see correction 1).
- **TC-6 — OCR entities not consumed:** screenshot OCR extracted `Operations Manager, UAE Expo Office
  at YOSH` but the tracking tool call re-ran extraction and failed; the LLM context already had the answer.

### 🟠 High
- **TC-1 — Nationality-gated roles unflagged:** "UAE nationals" role returned with no eligibility badge.
- **TC-2 — Relevance broken:** ESG/Compliance profile → ServiceNow Developer, Field Service Engineer,
  HR Administrator. Ranking is title-keyword matching, not function/seniority/skills.
- **TC-10 — Non-deterministic search:** two identical "search again" calls → disjoint result sets, no
  session cache, no dedup against already-shown jobs.
- **TC-9 — Language session-sticky:** stayed Arabic after 2 English messages (see correction 2).

### 🟡 Medium
- **TC-4 — Stale target gate:** after in-session target update (Ops → ESG/Compliance), first search
  used old targets and did not confirm.
- **TC-5 — Ambiguous "ابحث" resolves silently:** with target ambiguity explicitly raised, a bare
  "search" should re-ask; instead fired immediately.
- **TC-3 — Duplicate-render risk masked:** non-determinism prevents reproducing the earlier double-render;
  render path likely needs an idempotency key.
- **TC-11 — Profile query flickers to search:** "what is my profile?" briefly showed "Searching…" before
  correcting. Add a distinct profile-query intent.
- **TC-12 — "What can you do?" not onboarding-safe:** answers from session context; a cold-start/first
  message user gets no capability overview.

### Positive
- Cold-start timeout UX (progressive "still searching…" → graceful timeout + action buttons) is good.
  Underlying cause is Render free-tier spin-up (~90s) — paid tier or keep-alive ping would remove it.

## Fix grouping (→ tasks)

| Layer | Cases | Task |
|---|---|---|
| Intent router over-triggers `job_search` | TC-8, TC-11, contributes TC-4/5 | 038 (P0) |
| Tracking classify/extract from text + OCR | TC-7, TC-6 | 039 (P0) |
| Relevance scoring + nationality filter | TC-2, TC-1 | 040 (P1) |
| Search session cache + dedup + render idempotency | TC-10, TC-3 | 041 (P1) |
| Per-message language detection | TC-9 | 042 (P1) |
| Conversational UX gates | TC-4, TC-5, TC-12 | 043 (P2) |

## Product-readiness note

These defects gate the 90-day plan's Phase 1 "CV upload → Fit Score → Matched Role" demo: the demo
cannot be recorded honestly while TC-2 returns irrelevant roles. See
`docs/strategy/rico-hunt-90-day-plan-2026-07-03.md` (Phase 1 now includes the P0 product fixes).

## Final Status

`review` — findings logged; remediation tracked in TASK-20260703-038…-043. No code changed by this eval.
