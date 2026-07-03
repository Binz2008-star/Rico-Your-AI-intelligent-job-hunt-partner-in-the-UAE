# Rico Hunt — Next 90 Days

**To:** Team / Stakeholders · **From:** Founder · **Date:** 2026-07-03 · **Status:** Execution Directive

> This document merges the strategy memo and the execution tracker, and adds two guardrails:
> (1) a **product-readiness gate** tied to the 2026-07-03 live chat QA
> (`AI_WORKSPACE/EVALS/2026-07-03-chat-live-qa.md`), and (2) an **Evidence Type** column so no
> initiative can drift into "marketed but not real."

---

## Current State

We are past the "landing page" phase. The site articulates UAE focus, bilingual support
(Arabic + English), user-controlled applications, transparent pricing (Free–AED 49/mo), and founder
attribution (Roben Edwan / Eco Technology L.L.C).

**The core problem is no longer positioning — it is trust density and conversion velocity.**

**Critical caveat (new):** trust density is not only legal pages and testimonials — it is *the product
doing what it claims*. The 2026-07-03 live QA found the core chat loop failing on core tasks:
relevance scoring returns irrelevant roles for the user's function (TC-2), "prepare me for an
interview" misroutes to a job search (TC-8), and pasted/screenshotted applications don't get tracked
(TC-7, TC-6). **A broken core loop destroys trust faster than any trust page builds it.** These P0/P1
fixes are therefore folded into Phase 1, not deferred.

## The Decision

- **No rebrand** unless a direct trademark conflict or branded-search confusion proves otherwise.
- **No mobile app** in this window. Web activation and retention first.
- **No paid ads until Phase 3.** Leaking traffic is wasted capital.
- **Employer page = signal, not product.** A landing page to capture interest, not a B2B workflow.

## The 3-Phase Roadmap

### Phase 1 — Trust, Conversion & Core-Loop Correctness (Weeks 1–3) · P0
*Objective: make the "real company," "you approve," and "verified matches" claims irrefutable —
including in the product itself.*

- **Fix the P0 product bugs (QA 2026-07-03):** intent router misrouting (TASK-038) and
  application tracking from text/OCR (TASK-039). These block the demo below — the "Matched Role"
  and tracking steps must actually work before they are filmed or advertised.
- **Ship trust layer:** Privacy Policy, Terms, About, Contact, FAQ, Data Security overview; linked in
  header/footer.
- **Add product demo:** 30-second recording above the fold — CV upload → Fit Score → Matched Role,
  with the explicit "you approve" step visible. *Do not record until TASK-038/039 and the relevance
  fix (TASK-040) are green — otherwise the demo either stages a result (overclaim) or films the bug.*
- **Add visual proof:** 3–5 screenshots of the command center, match explanations, tracking views.
- **Publish social proof:** beta quotes + legitimate usage metrics only. No vanity stats.
- **Launch employer signal page:** "For Hiring Partners" waitlist capture. No B2B backend.

### Phase 2 — Product Depth & Retention (Weeks 4–8) · P1
*Objective: convert curious visitors into active, returning users.*

- **Relevance + i18n hardening:** ship scoring/nationality fix (TASK-040), search cache + dedup
  (TASK-041), and per-message language detection (TASK-042) — the retention blockers from QA.
- **Feature detail pages:** CV parsing logic, match explanation, tracking workflow, bilingual flow.
- **Activation UX:** "Top 3 Matches" immediately after upload; push "You approve every application"
  into the core loop (not just homepage copy).
- **Ship one net-new retention feature:** recommend **Interview Prep (AI mock Q&A)**. Do *not* build
  salary insights yet (data-quality risk). **Follow-up reminders are already implemented**
  (`src/services/followup_service.py` + the #355 cron sweep) — this is a *surface-and-verify* task,
  not a new build; make the Premium promise visibly true in-product.

### Phase 3 — Acquisition Scaling (Weeks 8–12) · P2
*Objective: turn the engine on once the funnel — and the product — are trustworthy.*

- **UAE content engine:** 10–15 high-intent articles (CV guides, hiring trends, interview prep).
- **LinkedIn primary channel:** 3×/week in 3 lanes — Market Insights, Product Walkthroughs,
  Candidate Stories.
- **Paid tests:** small LinkedIn ad tests *only* after Phase 1 is complete and baseline conversion
  (CV upload rate) has visibly improved.

## Critical Risk Management

- **Premature scaling:** building features 3/4/5 while ignoring trust *and core-loop correctness*
  burns dev hours and ad spend at once. Hold the priority table.
- **Overclaiming:** "data never sold," "human control," "verified matches" must be provable. The
  biggest current overclaim risk is not the copy — it is the product (QA 2026-07-03). Do not publish
  metrics unless current and defensible.

## Success KPIs (End of 90 Days)

*(Record baselines in Week 0, before changes ship.)*

- Trust pages (About/Privacy/Terms/Security) visited by a materially higher share of new users vs baseline.
- CV upload rate increases ~25% vs Phase 0 baseline.
- Active retention (Week-2 return rate) > 10%.
- **Core-loop correctness:** the QA P0/P1 cases (TC-1, TC-2, TC-6, TC-7, TC-8, TC-9, TC-10) pass on a
  re-run before Phase 3 acquisition starts.

> If a task does not improve trust, proof, activation, retention, measured acquisition efficiency,
> **or core-loop correctness**, it is out of scope for this 90-day window.

---

## Execution Tracker

`Evidence Type` = `marketed` (promised on the public site) · `implemented` (actually live) ·
`measured` (backed by data). The goal is to move every row rightward.

| Priority | Initiative | Owner | Timeline | Evidence Type (now) | Definition of Done |
|---|---|---|---|---|---|
| P0 | Fix intent-router misrouting (QA TASK-038) | [Assign] | Wk 1–2 | implemented (buggy) | "prepare for interview" → coaching; profile query no search flash |
| P0 | Fix text/OCR application tracking (QA TASK-039) | [Assign] | Wk 1–2 | implemented (buggy) | Pasted/screenshotted application saves to pipeline |
| P0 | Ship trust layer (Privacy, Terms, About, Contact, FAQ, Security) | [Assign] | Wk 1–2 | not started | Pages live in header/footer; security overview explains CV data flow |
| P0 | 30-second homepage demo video | [Assign] | Wk 2–3 | not started | Loads fast, muted; CV → fit → match; *only after TASK-038/039/040 green* |
| P1 | Relevance scoring + nationality filter (QA TASK-040) | [Assign] | Wk 3–5 | implemented (buggy) | ESG profile stops returning SWE roles; national-gated roles badged |
| P1 | Search cache + dedup + render idempotency (QA TASK-041) | [Assign] | Wk 4–6 | not started | Repeat search is stable; no re-shown jobs; no double render |
| P1 | Per-message language detection (QA TASK-042) | [Assign] | Wk 4–5 | implemented (buggy) | English mid-session → English replies; Arabic guard preserved |
| P1 | Add screenshots & feature proof | [Assign] | Wk 2–3 | not started | ≥5 screenshots of Command, Fit Scoring, Tracking |
| P1 | Publish early testimonials / case studies | [Assign] | Wk 3 | not started | ≥3 real beta quotes + 1 written success story live |
| P1 | Employer signal page (waitlist) | [Assign] | Wk 3 | not started | Page live; email capture; measured by sign-ups, not "page exists" |
| P2 | Feature detail pages (parsing, matching, tracking, bilingual) | [Assign] | Wk 4–6 | not started | 4 sub-pages, each ≥200 words |
| P2 | In-product activation flow | [Assign] | Wk 5–7 | marketed | "Top 3 matches" post-upload; approval control visible in UX |
| P2 | Surface follow-up reminders (promise fulfilment) | [Assign] | Wk 5–6 | implemented, not surfaced | Premium reminder promise visibly true in-product |
| P2 | Ship 1 net-new retention feature (Interview Prep) | [Assign] | Wk 6–8 | not started | Live and used by ≥15% of active users |
| P3 | UAE content engine (10 articles) | [Assign] | Wk 8–10 | not started | 10 articles; ≥3 shared on LinkedIn |
| P3 | LinkedIn distribution cadence | [Assign] | Wk 9–12 | not started | 3 posts/week; ≥3% avg engagement |
| P3 | Small paid ad test (LinkedIn) | [Assign] | Wk 10–12 | not started | ~AED 700 / $200 test; CAC tracked vs CV-upload conversion |

## Employer page — real success measure

The employer signal page must have a measure (sign-ups or conversations initiated), not "page exists,"
or it drifts into cosmetic work.
