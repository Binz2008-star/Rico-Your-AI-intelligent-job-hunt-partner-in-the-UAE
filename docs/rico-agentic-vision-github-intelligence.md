# Rico Agentic Vision — GitHub Intelligence Report

**Date:** 2026-06-21  
**Branch:** `main` (docs only — no runtime code changes)  
**Scope:** Intelligence audit of public GitHub agentic job-search ecosystem, converted into a production-safe Agentic Vision for RicoHunt.  
**Next action:** Read this before opening `feat/agent-audit-policy-gate`.

---

## Executive Summary

The public GitHub ecosystem for AI-powered job search has matured rapidly in 2025–2026. The dominant pattern is no longer blind auto-apply spam; it has shifted toward **semi-autonomous agents with mandatory human approval gates** — exactly the model Rico's `docs/agentic-ux-contract.md` already specifies.

Three categories of repos were found:

| Category | Examples | Stars | Risk for Rico |
|---|---|---|---|
| Raw auto-apply bots | AIHawk, Auto_job_applier_linkedIn, EasyApplyJobsBot | 29k–2.4k | High — no approval, spam risk |
| Approval-first agents | career-ops, AutoApply AI (Rayyan), ApplyPilot | 54k–small | Low — safe reference |
| Safety/governance toolkits | Microsoft Agent Governance Toolkit, GitHub Agentic Workflows | 4.4k | Low — direct inspiration |

**Rico's strategic position:** Rico is ahead of most repos in its safety design (`rico_safety.py`, `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS`, idempotent agent runtime). Rico is behind in three areas: **resume tailoring per job**, **browser-side form filling**, and **structured agent audit memory**.

**Top recommendation:** Implement the `feat/agent-audit-policy-gate` backend next, using Microsoft's governance toolkit as the architectural reference (MIT license). Do not implement browser automation until subscription gating, approval tokens, and audit log are fully live.

---

## 1. GitHub Landscape — Repository Inventory

### Tier 1 — High Value (Study Deeply)

---

#### R1 · `santifer/career-ops`
- **URL:** https://github.com/santifer/career-ops
- **Stars:** 54,955 (reached 53k+ in one week — viral April 2026)
- **Language:** JavaScript / Claude Code Skills
- **License:** MIT ✅
- **Description:** AI-powered job search system built on Claude Code. 14 skill modes, Go dashboard, PDF generation, batch processing.
- **Architecture:**
  - Skill-based modular architecture (15 CLAUDE.md skill modes)
  - Claude Code as the reasoning brain per offer
  - Multi-dimensional canonical rubric for offer evaluation
  - Preflight gate: verifies posting is still live before drafting
  - Draft-in-chat approval gate (never auto-submits)
  - A4 PDF generation via HTML + Playwright pipeline
  - Cover letter with 4 interactive angle prompts (why / problems / approach / tone)
- **Useful ideas for Rico:**
  - Preflight freshness check (verify job still live before generating cover letter)
  - Canonical scoring rubric per job evaluation
  - Skill-as-mode architecture for different agent personas
  - The "system never submits — you always have final call" philosophy is Rico's exact model
  - Batch processing queue concept directly maps to Rico's Tailored Application Queue
- **Risks:** Built as a personal CLI tool, not a SaaS. No multi-user isolation, no auth.
- **Verdict:** **ADAPT** — ideas and philosophy, not code. Closest to Rico's model.

---

#### R2 · `microsoft/agent-governance-toolkit`
- **URL:** https://github.com/microsoft/agent-governance-toolkit
- **Stars:** 4,427 (April 2026 release)
- **Language:** Python / TypeScript
- **License:** MIT ✅
- **Description:** AI Agent Governance Toolkit — Policy enforcement, zero-trust identity, execution sandboxing, and reliability engineering for autonomous AI agents. Covers 10/10 OWASP Agentic Top 10.
- **Architecture:**
  - Runtime policy enforcement layer (middleware)
  - Zero-trust identity with DID-based behavioral trust scoring
  - Execution sandboxing with resource limits
  - Semantic intent classifier detects dangerous goals regardless of phrasing
  - Circuit breakers and SLO enforcement
  - Approval workflows with quorum logic
  - Full OWASP Agentic Top 10 coverage
- **OWASP coverage mapped to Rico risks:**
  | OWASP Risk | Rico Equivalent | Toolkit Pattern |
  |---|---|---|
  | Goal hijacking | User prompt → auto-apply without approval | Semantic intent classifier |
  | Tool misuse | Agent calls apply() directly | Capability sandboxing |
  | Identity abuse | Forged user_id in requests | JWT isolation (already done in Rico) |
  | Memory poisoning | Corrupted profile data sent to LLM | Cross-model verification |
  | Cascading failures | One bad action triggers chain | Circuit breakers |
  | Human-agent trust exploitation | Fake approval tokens | Approval workflows + quorum |
- **Useful ideas for Rico:**
  - Policy enforcement at middleware layer (not inside each router)
  - Approval workflow with quorum logic (maps to Rico's per-action approval token)
  - Circuit breakers for AI provider failures (maps to Rico's fallback chain)
  - Sub-millisecond policy enforcement (deterministic, not LLM-dependent)
- **Risks:** MIT license is clean. Overkill for Rico's current scale, but architectural patterns are directly applicable.
- **Verdict:** **ADOPT patterns** — the policy gate, approval workflow, and audit trail designs are the direct blueprint for `feat/agent-audit-policy-gate`.

---

#### R3 · `Rayyan9477/AutoApply-AI-Agentic-Browser-Automation-for-Job-Search`
- **URL:** https://github.com/Rayyan9477/AutoApply-AI-Agentic-Browser-Automation-for-Job-Search
- **Stars:** ~200 (active 2025–2026)
- **Language:** Python (FastAPI backend + React frontend)
- **License:** MIT ✅
- **Description:** Full-stack platform: job discovery across LinkedIn/Indeed/Glassdoor/Exa, ATS resume scoring, LLM-powered tailoring, human-in-the-loop review, browser-use + Playwright automation.
- **Architecture:**
  - FastAPI REST + WebSocket backend (very similar to Rico's stack)
  - React + MUI frontend with real-time progress
  - Human-in-the-loop review workflow
  - Batch processing queue
  - ATS scoring engine (multi-factor keyword analysis)
  - browser-use + Playwright for form submission
  - LiteLLM for multi-provider LLM routing (OpenAI/Groq/Gemini/OpenRouter)
- **Useful ideas for Rico:**
  - ATS score before/after resume tailoring (Rico has no ATS scoring yet)
  - WebSocket for real-time agent status (Rico uses polling)
  - Application status lifecycle tracking (maps to Rico's applications table)
  - The review-before-submit batch queue is exactly Rico's planned Tailored Application Queue
  - Multi-provider LLM routing via LiteLLM mirrors Rico's fallback chain
- **Risks:** browser-use is inherently risky for production — session hijacking, bot detection, ToS violations. Rico must gate this behind explicit permission tier.
- **Verdict:** **ADAPT** — queue architecture and ATS scoring patterns. Browser automation: future P2 only.

---

### Tier 2 — Useful Reference

---

#### R4 · `feder-cr/Jobs_Applier_AI_Agent_AIHawk`
- **URL:** https://github.com/feder-cr/Jobs_Applier_AI_Agent_AIHawk
- **Stars:** 29,926 (archived August 2024 — June 2026)
- **Language:** Python
- **License:** AGPL-3.0 ⛔
- **Description:** Most starred auto-apply repo. Selenium-based LinkedIn Easy Apply automation with LLM-tailored resume/cover letter. Now archived.
- **Architecture:**
  - `secrets.yaml` / `work_preferences.yaml` / `plain_text_resume.yaml` config
  - Resume tailoring per job description using `plain_text_resume.yaml` as base
  - Selenium browser automation for form filling
  - LLM integration for answer generation in application forms
- **Useful ideas for Rico:**
  - YAML-based profile as the "canonical resume source of truth" — maps to Rico's `rico/profile` endpoint
  - Per-job tailoring from a base profile: the pattern is applicable (without the Selenium part)
  - Form field answer generation (LLM fills in "describe your experience in X" prompts)
- **Risks:**
  - AGPL-3.0: cannot import any code into Rico without open-sourcing Rico
  - Archived and unmaintained
  - No approval gate — fully automatic spam
  - ToS violation risk for LinkedIn
- **Verdict:** **IGNORE code. Study patterns only.** The profile-as-YAML concept is already implemented in Rico's DB-backed profile.

---

#### R5 · `GodsScion/Auto_job_applier_linkedIn`
- **URL:** https://github.com/GodsScion/Auto_job_applier_linkedIn
- **Stars:** 2,469 (active June 2026)
- **Language:** Python
- **License:** GPL-3.0 ⛔
- **Description:** Auto-apply LinkedIn jobs with Selenium + undetected-chromedriver.
- **Architecture:**
  - Config-driven job filtering (title, location, experience level)
  - undetected-chromedriver to evade bot detection
  - Automatic form-filling for Easy Apply
  - No AI integration — pure rule-based
- **Useful ideas for Rico:**
  - Job filter criteria UX (location, seniority, job type) — Rico already has this via JSearch params
  - undetected-chromedriver pattern documents the anti-detection challenge Rico would face
- **Risks:** GPL-3.0 incompatible. Fully automated, no approval, high ToS risk. Uses stealth tactics that violate platform ToS.
- **Verdict:** **IGNORE.** Demonstrates what Rico must NOT do.

---

#### R6 · `wodsuz/EasyApplyJobsBot`
- **URL:** https://github.com/wodsuz/EasyApplyJobsBot
- **Stars:** 787
- **Language:** Python
- **License:** Not specified ⚠️
- **Description:** Auto-apply to LinkedIn/Glassdoor Easy Apply jobs. Auto login, auto fill, auto apply.
- **Architecture:** Selenium, config-based, no LLM.
- **Useful ideas for Rico:** None beyond what R4/R5 already cover.
- **Risks:** Unknown license. Fully automated spam. No approval gate.
- **Verdict:** **IGNORE.**

---

#### R7 · `surapuramakhil-org/Job_search_agent`
- **URL:** https://github.com/surapuramakhil-org/Job_search_agent
- **Stars:** 156
- **Language:** Python
- **License:** Apache-2.0 ✅
- **Description:** AI job search agent that searches and applies to jobs, creating tailored applications.
- **Architecture:**
  - Poetry-based Python project
  - AI-driven job matching
  - Tailored application generation
  - Topics: agent, ai-agents, gpt, job-search, tailored-application
- **Useful ideas for Rico:**
  - Apache-2.0 license is clean for reference
  - Tailored application concept per job
- **Risks:** Limited documentation available. Smaller project.
- **Verdict:** **REFERENCE** — license is clean, monitor for architecture patterns.

---

#### R8 · `mshen1019/Argus`
- **URL:** https://github.com/mshen1019/Argus
- **Stars:** 111 (January 2026, active)
- **Language:** Python
- **License:** Not specified ⚠️
- **Description:** AI-powered job search agent that crawls company career pages and matches jobs based on user preferences.
- **Architecture:**
  - Career page crawler (direct scraping, not job board API)
  - Preference-based matching against scraped listings
  - AI analysis of job descriptions vs user profile
- **Useful ideas for Rico:**
  - Direct career page crawling bypasses job board API rate limits
  - For UAE market: Bayt, Dubizzle, LinkedIn UAE, ADNOC careers, etc. — could be crawled
  - Preference matching pattern is similar to Rico's scoring system
- **Risks:** Unknown license. Career page scraping can break when sites update. ToS risk.
- **Verdict:** **STUDY** — the direct career page crawl concept is valuable for UAE-specific sites not covered by JSearch.

---

#### R9 · `beatwad/LinkedIn-AI-Job-Applier-Ultimate`
- **URL:** https://github.com/beatwad/LinkedIn-AI-Job-Applier-Ultimate
- **Stars:** 113
- **Language:** Python
- **License:** MIT ✅
- **Description:** Playwright + LLM. Applies to ALL job types (not just Easy Apply). Custom resumes, skill statistics, Telegram reporting.
- **Architecture:**
  - Playwright for browser automation (not Selenium)
  - Applies to both Easy Apply and full external application forms
  - Generates custom resumes per application
  - Telegram integration for status reporting
  - Skill statistics dashboard
- **Useful ideas for Rico:**
  - Telegram reporting for agent actions (Rico already has Telegram, maps naturally)
  - Skill statistics: which skills appear most in saved/applied jobs — Rico could surface this
  - Playwright preference over Selenium (modern, more stable)
- **Risks:** MIT license is clean. But fully automated application submission is exactly what Rico must not do without explicit approval.
- **Verdict:** **ADAPT skill statistics idea.** Browser automation patterns: future reference only.

---

#### R10 · `imon333/Job-apply-AI-agent`
- **URL:** https://github.com/imon333/Job-apply-AI-agent
- **Stars:** 160
- **Language:** Python
- **License:** Not specified ⚠️
- **Description:** n8n + Selenium + OpenAI. Scrapes LinkedIn/Indeed/StepStone, generates CV + cover letter, auto-applies. Google Sheets/Airtable integration + email alerts.
- **Architecture:**
  - n8n workflow orchestration
  - Selenium scraping
  - OpenAI for CV and cover letter generation
  - Google Sheets as application tracker
  - Email alert system
- **Useful ideas for Rico:**
  - n8n workflow orchestration concept — Rico could expose webhook triggers for external automation
  - Google Sheets as an export format for application tracking (user request)
- **Risks:** Unknown license. Fully automated. n8n adds operational complexity.
- **Verdict:** **IGNORE code. Note the Sheets export idea.**

---

#### R11 · `srbhr/Resume-Matcher`
- **URL:** https://github.com/srbhr/Resume-Matcher
- **Stars:** ~5,000+ (established project)
- **Language:** Python
- **License:** Apache-2.0 ✅
- **Description:** Analyze resume vs job description with match score, keyword highlighting, and improvement suggestions.
- **Architecture:**
  - KeyBERT for keyword extraction from JD and resume
  - Semantic similarity scoring
  - Before/after ATS match score
  - Export tailored resume + cover letter as PDF
- **Useful ideas for Rico:**
  - Keyword gap analysis between user CV and specific job description
  - Match score per job (Rico has overall profile scoring but not per-JD scoring)
  - The "which keywords are you missing" insight is high-value for Rico users in UAE market
- **Risks:** Apache-2.0 compatible. KeyBERT adds a dependency — Rico can replicate with LLM-based analysis.
- **Verdict:** **ADAPT concept with LLM.** Do not import KeyBERT — use Rico's existing LLM providers to produce keyword gap analysis inline.

---

#### R12 · `JaimeYeung/Resume-Tailor-AI`
- **URL:** https://github.com/JaimeYeung/Resume-Tailor-AI
- **Stars:** ~100+
- **Language:** Python
- **License:** MIT ✅
- **Description:** ATS keyword coverage optimization. Weighted keyword scoring (hard skills 2x). Before → after score shown to user.
- **Architecture:**
  - Hard skills weighted 2x vs soft skills
  - Before/after ATS match score
  - Identifies still-missing keywords after tailoring
- **Useful ideas for Rico:**
  - Weighted keyword scoring (technical skills > soft skills) is a useful UX signal
  - Show user "your CV covers 7/10 key requirements for this role"
  - "Still missing" keywords after tailoring is actionable
- **Risks:** MIT compatible.
- **Verdict:** **ADAPT** — the weighted scoring and before/after UX pattern.

---

#### R13 · `varunr89/resume-tailoring-skill` (Claude Code skill)
- **URL:** https://github.com/varunr89/resume-tailoring-skill
- **Stars:** ~30
- **Language:** Markdown / Claude Code Skill
- **License:** MIT ✅
- **Description:** Claude Code skill for tailored resume generation. Batch processing, deep company research, experience discovery, confidence-scored content with gap identification.
- **Architecture:**
  - Claude Code skill format (CLAUDE.md-based)
  - Multi-job batch processing
  - Company culture research per application
  - Confidence-scored content selection
  - Transparent gap identification
  - Factual integrity enforcement (no fabrication)
- **Useful ideas for Rico:**
  - Factual integrity constraint: Rico must never fabricate experience (already in safety layer)
  - Confidence scoring on tailored content ("I'm 90% sure this skill is relevant")
  - Company research as part of the tailoring context (role + company + culture)
  - Batch processing architecture maps to Rico's Tailored Application Queue
- **Risks:** MIT compatible.
- **Verdict:** **ADAPT** — the confidence scoring and batch tailoring patterns.

---

#### R14 · `github/gh-aw` — GitHub Agentic Workflows
- **URL:** https://github.com/github/gh-aw
- **Stars:** N/A (official GitHub repo)
- **License:** GitHub ToS
- **Description:** GitHub's own agentic workflow system for AI agents operating on repositories.
- **Architecture:**
  - Layered security model: sandbox → scoped permissions → gated outputs → audit log
  - Integrity filtering: content filtered by author trust + merge status before agent sees it
  - `gh aw audit` command: detailed post-run audit report
  - Write operations run in isolated jobs with minimum required permissions
  - Human approval gate via GitHub Environment protection rules
  - Network + API proxy logs every agent action at trust boundary
- **Useful ideas for Rico:**
  - "Integrity filtering before the agent sees content" → Rico should sanitize job descriptions before passing to LLM (prompt injection via JD)
  - Layered logging at every trust boundary (not just after execution)
  - Minimum permissions per action (not blanket agent permissions)
  - The `audit` command pattern → Rico's audit trail viewer
- **Risks:** Not open-source in a reusable sense.
- **Verdict:** **ADOPT architectural patterns.** Direct blueprint for Rico's policy gate and audit trail.

---

#### R15 · `Pickle-Pixel/ApplyPilot`
- **URL:** https://github.com/Pickle-Pixel/ApplyPilot
- **Stars:** ~50
- **Language:** Not specified
- **License:** Not specified ⚠️
- **Description:** AI agent that applies to jobs on any site, any form.
- **Architecture:** Universal form-filling agent using LLM + browser automation.
- **Useful ideas for Rico:** Universal form-filling is the hardest problem in job automation. Documents the failure modes.
- **Risks:** Unknown license. Full auto-apply with no stated approval gate.
- **Verdict:** **IGNORE.** Risk profile incompatible with Rico.

---

### Tier 3 — Context / Governance Reference

---

#### R16 · Microsoft OWASP Agentic Top 10 (2026)

OWASP published the first formal taxonomy of risks specific to autonomous AI agents in December 2025. The 10 risks directly relevant to Rico:

| # | Risk | Rico Mitigation Required |
|---|---|---|
| 1 | Goal Hijacking | Semantic intent classifier in policy gate |
| 2 | Tool Misuse | Capability sandboxing per permission tier |
| 3 | Identity Abuse | JWT isolation (done); approval token per action |
| 4 | Supply Chain Risk | Signed/trusted job data sources only |
| 5 | Code Execution | Rico never executes arbitrary code |
| 6 | Memory Poisoning | Profile validation before LLM context injection |
| 7 | Insecure Communications | HTTPS only, cookie-secure already set |
| 8 | Cascading Failures | Circuit breakers on AI provider calls |
| 9 | Human-Agent Trust Exploitation | Approval tokens with TTL + HMAC signature |
| 10 | Rogue Agents | Permission tier system, P4 locked |

---

## 2. Competitive Feature Matrix

| Feature | AIHawk | career-ops | AutoApply AI | Rico (current) | Rico (target) |
|---|---|---|---|---|---|
| CV parsing | ✅ YAML | ✅ PDF | ✅ PDF | ✅ PDF+DB | ✅ |
| Job matching score | ❌ | ✅ rubric | ✅ ATS | ✅ JSearch | ✅ + ATS gap |
| Resume tailoring per JD | ✅ | ✅ | ✅ | ❌ | ✅ P1 |
| Cover letter generation | ✅ | ✅ angles | ✅ | ❌ | ✅ P1 |
| ATS keyword gap analysis | ❌ | ❌ | ✅ | ❌ | ✅ P1 |
| Approval gate | ❌ | ✅ draft-only | ✅ review | ✅ env flag | ✅ token-based |
| Audit trail | ❌ | ❌ | partial | partial | ✅ P0 |
| Browser form-filling | ✅ Selenium | ✅ Playwright | ✅ browser-use | ❌ | P3 (gated) |
| Multi-user SaaS | ❌ | ❌ | ❌ | ✅ | ✅ |
| Auth / JWT isolation | ❌ | ❌ | ❌ | ✅ | ✅ |
| Subscription gating | ❌ | ❌ | ❌ | ✅ | ✅ tiered |
| Arabic/English UX | ❌ | ❌ | ❌ | ✅ | ✅ |
| UAE job market focus | ❌ | ❌ | ❌ | ✅ | ✅ |
| Policy gate endpoint | ❌ | ❌ | ❌ | ❌ | ✅ P0 |
| Telegram notifications | ❌ | ❌ | ❌ | ✅ | ✅ |
| Idempotent action runtime | ❌ | ❌ | ❌ | ✅ | ✅ |
| Permission tiers (P0-P3) | ❌ | ❌ | ❌ | partial | ✅ P1 |
| Skill gap analysis | ❌ | ❌ | partial | ❌ | ✅ P2 |
| Interview prep | ❌ | ✅ | ❌ | ❌ | P3 |
| Salary benchmarking | ❌ | ❌ | ❌ | ❌ | P3 |

---

## 3. What Rico Should Copy as Ideas

### From career-ops (R1)
- **Preflight freshness check:** Before generating a cover letter or tailoring CV, verify the job is still active. Prevents wasted compute and user frustration.
- **Canonical scoring rubric:** Each job evaluation uses the same dimensions (skills match, location, seniority, company fit). Produces consistent, explainable scores.
- **Skill-mode architecture:** Different agent personas for different tasks (cover letter mode, interview prep mode, salary negotiation mode). Maps to Rico's intent classification.
- **Draft-in-chat approval:** The output of the agent is always a reviewable draft before any action. Never silently execute.

### From Microsoft Agent Governance Toolkit (R2)
- **Policy middleware layer:** Enforce rules before any action reaches the execution layer. Not inside each router, but as a cross-cutting middleware.
- **Semantic intent classifier:** Before executing an action, classify the intent. If the classified intent doesn't match the stated intent, reject.
- **Approval workflows with TTL:** Tokens expire. Re-approval required after expiry. Already in `docs/agentic-ux-contract.md`.
- **Circuit breakers on AI calls:** If DeepSeek fails 3 times in 60 seconds, don't hammer it — trip the breaker, fall back, notify.

### From AutoApply AI (R3)
- **ATS score per job:** Before and after tailoring, show the user a percentage match score. Makes the value of tailoring concrete and visible.
- **WebSocket for agent status:** Real-time progress as Rico works on a batch. Maps to Rico's Telegram notifications but adds in-app visibility.
- **Batch processing queue:** A queue of pending applications with status per item. This is Rico's Tailored Application Queue vision.

### From Resume-Matcher (R11) and Resume-Tailor-AI (R12)
- **Keyword gap analysis:** "Your CV covers 6/10 key skills for this role. Missing: Python, Agile, Arabic proficiency."
- **Weighted scoring:** Hard skills (certifications, tools, languages) count more than soft skills in UAE market.
- **Before/after comparison:** Show user what changed when Rico tailors their CV for a specific job.

### From GitHub Agentic Workflows (R14)
- **Integrity filtering on LLM inputs:** Sanitize job descriptions before they enter Rico's LLM context. A malicious job posting could contain prompt injection. Rico should strip or escape known injection patterns before passing JD text to the LLM.
- **Trust boundary logging:** Log at every boundary — not just after execution. "Rico received action request → policy gate evaluated → approved → executed → audit written."
- **Minimum permissions per action:** A "save job" action should not have the same capability scope as a "send email" action.

---

## 4. What Rico Must NOT Copy

| Pattern | Source | Why Not |
|---|---|---|
| Fully automated form submission | AIHawk, GodsScion, wodsuz | No approval gate. ToS violation. Spam risk. Legal risk. |
| `secrets.yaml` credential storage | AIHawk | Never store user credentials in files. Rico uses JWT + httpOnly cookie. |
| Selenium / undetected-chromedriver | GodsScion | Stealth tactics violate ToS. Fragile. Blocked by modern platforms. |
| AGPL-3.0 licensed code (any line) | AIHawk | Would force open-sourcing Rico's entire codebase. |
| Bulk batch apply without per-job approval | Any auto-apply bot | RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true is non-negotiable. |
| Storing LinkedIn/platform passwords | Any bot | Rico must never store third-party platform credentials. |
| "Apply to 100 jobs in one click" UX | AIHawk, EasyApplyJobsBot | Spam. Ruins Rico's reputation. Violates UAE professional norms. |

---

## 5. Rico Agentic Vision v1

### Guiding Principles

1. **Semi-autonomous by default.** Rico plans and proposes. Users approve and execute.
2. **Per-action approval.** No bulk approvals. Each consequential action has its own token and receipt.
3. **Transparent reasoning.** Every Action Card shows `why_now`, `data_used`, `expected_effect`, `risk_class`.
4. **Reversible where possible.** Internal writes can be undone within a deadline window. External sends cannot.
5. **UAE-first context.** Job scoring, cultural fit, Emiratisation, salary benchmarks are all UAE-calibrated.
6. **No browser automation until P3.** The safety layer must be fully live before any form-filling capability.

### Agent Roles

```
┌─────────────────────────────────────────────────────────┐
│                    Rico Agent System                     │
│                                                         │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────┐  │
│  │ Scout Agent  │   │ Tailor Agent │   │ Apply Agent│  │
│  │              │   │              │   │  (P3 only) │  │
│  │ Finds jobs   │   │ CV + CL per  │   │ Form fill  │  │
│  │ Scores match │   │ specific JD  │   │ after user │  │
│  │ Filters UAE  │   │ ATS gap      │   │ approves   │  │
│  │ Ranks queue  │   │ analysis     │   │ each form  │  │
│  └──────┬───────┘   └──────┬───────┘   └─────┬──────┘  │
│         │                  │                 │          │
│         └──────────────────┼─────────────────┘          │
│                            ▼                            │
│                   ┌────────────────┐                    │
│                   │  Policy Gate   │                    │
│                   │  (middleware)  │                    │
│                   │                │                    │
│                   │ · intent check │                    │
│                   │ · risk class   │                    │
│                   │ · permission   │                    │
│                   │   tier check   │                    │
│                   │ · token valid  │                    │
│                   └───────┬────────┘                    │
│                           │                             │
│                    passes │ fails                       │
│                    ───────┼──────                       │
│                    ▼      │      ▼                      │
│             ┌──────────┐  │  ┌─────────┐               │
│             │ Execute  │  │  │ Blocked │               │
│             │ + Audit  │  │  │ + Log   │               │
│             └──────────┘  │  └─────────┘               │
└─────────────────────────────────────────────────────────┘
```

### User Flow

```
User opens /ask or /jobs
        │
        ▼
Rico Scout finds 3–5 matching jobs (P0 — silent, read-only)
        │
        ▼
Rico presents job cards with match scores + ATS gap (P0)
        │
User saves a job
        ▼
Rico Tailor proposes: "Draft cover letter + tailor CV?" (P1 — shows Action Card)
        │
User reviews Action Card → Approves
        │
Approval Token issued (HMAC-SHA256, TTL 5 min)
        │
        ▼
Rico Tailor generates:
  · Tailored CV delta (which sections changed)
  · Cover letter draft
  · ATS score before → after
        │
User reviews drafts in /ask or /jobs detail
        │
        ▼ (P2)
"Mark as Applied" → inline confirmation → audit event written
        │
        ▼ (P3 — premium only, future)
"Send Application via Browser" → bottom sheet → approve → browser agent fills form
```

### Approval Flow Detail

```
Action Card shown to user
        │
User taps "Approve"
        │
Frontend: POST /api/v1/policy-gate/issue-token
  body: { card_id, action_type, idempotency_key, risk_class }
  auth: JWT cookie
        │
Backend:
  1. Verify JWT → extract user_id
  2. Check permission tier for risk_class
  3. Check idempotency (card not already executed)
  4. Issue ApprovalToken:
     { card_id, user_id, action_type, idempotency_key,
       risk_class, issued_at, expires_at, signature (HMAC-SHA256) }
        │
Frontend receives token (5-min TTL)
User sees countdown in UI
        │
User confirms (Approve CTA)
        │
Frontend: POST /api/v1/actions/{action}
  body: { approval_token, card_id, idempotency_key, ...payload }
        │
Policy Gate (middleware):
  1. Verify HMAC signature
  2. Check expires_at > now()
  3. Check user_id matches JWT
  4. Check card_id not in audit log (idempotency)
  5. Check risk_class ≤ user permission tier
  If all pass → execute action
        │
After execution:
  audit_writer.write_event(AuditEvent{...})
  Return receipt to frontend
```

### Policy Gate Rules (Non-Negotiable)

```python
# Enforced in src/api/policy_gate.py
POLICY_RULES = [
    # P4 is always blocked
    ("risk_class == 'critical' AND user.permission_tier < P3",  "BLOCK"),

    # External actions require P3
    ("action.external_systems != [] AND user.permission_tier < P3", "BLOCK"),

    # Bulk apply always blocked (P4 locked)
    ("action.action_type == 'bulk_apply'", "BLOCK"),

    # Auto-apply without token always blocked
    ("action.action_type in APPLY_TYPES AND NOT approval_token_valid", "BLOCK"),

    # Expired tokens always rejected
    ("approval_token.expires_at < now()", "BLOCK"),

    # Token user must match session user
    ("approval_token.user_id != session.user_id", "BLOCK"),

    # RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS must be respected
    ("env.RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS == 'true' AND NOT approval_token_valid", "BLOCK"),
]
```

### Audit Trail

Every action that passes or fails the policy gate produces an immutable `agent_audit_events` record:

```sql
-- migrations/YYYYMMDD_add_agent_audit_log.sql
CREATE TABLE agent_audit_events (
    event_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id),
    card_id         TEXT NOT NULL,
    action_type     TEXT NOT NULL,
    intent_summary  TEXT NOT NULL,
    risk_class      TEXT NOT NULL,
    approval_state  TEXT NOT NULL,  -- 'approved' | 'rejected' | 'expired' | 'blocked'
    policy_decision TEXT NOT NULL,  -- 'user_approved' | 'policy_blocked' | 'token_expired' | etc.
    target_entity   JSONB,
    data_used       JSONB,
    external_systems JSONB,
    expected_effect TEXT,
    actual_effect   TEXT,
    error           TEXT,
    idempotency_key TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Idempotency index
CREATE UNIQUE INDEX agent_audit_events_idem_key
    ON agent_audit_events(user_id, idempotency_key);

-- Never allow DELETE or UPDATE on this table in application code
-- Enforced by: row-level security or application policy
```

### Browser Automation Boundary

Browser automation is explicitly **not in scope** for the current Agentic Vision. When it becomes relevant (P3 / premium tier), the boundary rules are:

- **Gate 1:** User must be on a paid subscription tier that explicitly grants browser automation permission.
- **Gate 2:** Each browser session requires a fresh approval token per form per job.
- **Gate 3:** Browser agent never stores third-party platform credentials. Uses OAuth or session cookies provided by user.
- **Gate 4:** Browser agent reports every field it filled and every button it clicked in the audit log.
- **Gate 5:** User can see a live "what is Rico doing right now" feed during automation.
- **Gate 6:** One-click abort at any point before final submit.
- **Never:** Rico auto-submits without a final "Submit this application now" explicit approval from user.

### Failure Handling

| Failure | Detection | Response |
|---|---|---|
| LLM provider timeout | `asyncio.wait_for` TTL | Fall back to next provider in chain; notify user |
| Approval token expired | `expires_at < now()` check in middleware | Reject with 401; prompt user to re-approve |
| Duplicate action | `idempotency_key` in audit log | Return existing receipt; do not re-execute |
| Job no longer active (preflight fail) | HTTP 404 or "not found" from JSearch | Remove from queue; notify user "job closed" |
| LLM hallucination in tailored CV | Factual integrity check | Compare generated content against original CV; flag unsupported claims |
| Policy gate block | Policy evaluation | Write blocked event to audit log; return 403 with reason |
| Browser form fill failure | Playwright exception | Abort session; write failure to audit log; notify user |

### Subscription Gating

| Tier | Permission Level | Capabilities | Rico Action |
|---|---|---|---|
| Free | P0 (read-only) | Job recommendations, profile view, chat guidance | Silent — no approval needed |
| Free | P1 (draft) | Cover letter draft, CV tailoring preview | Show Action Card; no approval token |
| Starter | P2 (internal write) | Mark applied, save jobs, update profile | Per-action approval, internal only |
| Pro | P3 (external commit) | Send follow-up email, future: submit application | Bottom sheet + HMAC token + audit |
| P4 (bulk external) | — | Locked — not available in any tier | Always blocked |

### Observability

Every agent action produces three artifacts:

1. **User-visible:** Receipt card in `/ask` or `/jobs` UI showing what happened.
2. **Audit log:** Immutable row in `agent_audit_events` with full context.
3. **Telegram notification:** Digest to admin chat on high-risk or failed actions.

Metrics to monitor (add to `/health` or a future `/metrics` endpoint):
- `agent_actions_total` by `action_type`, `approval_state`, `risk_class`
- `policy_gate_blocks_total` by `policy_decision`
- `approval_token_expired_total`
- `llm_fallback_total` by `provider`
- `audit_write_latency_ms`

---

## 6. Architecture Proposal

### File Map for `feat/agent-audit-policy-gate`

```
src/
  api/
    policy_gate.py          # NEW: middleware + token issuance
    routers/
      policy_gate.py        # NEW: POST /api/v1/policy-gate/issue-token
  services/
    audit_writer.py         # NEW: writes AuditEvent after execution
    approval_token.py       # NEW: HMAC-SHA256 token issue/verify
  models/
    audit_event.py          # NEW: AuditEvent Pydantic model
    approval_token.py       # NEW: ApprovalToken Pydantic model

migrations/
  YYYYMMDD_add_agent_audit_log.sql   # NEW: agent_audit_events table

tests/
  test_policy_gate.py        # NEW: policy rule evaluation tests
  test_approval_token.py     # NEW: token issue, verify, expiry, HMAC tests
  test_audit_writer.py       # NEW: audit event write + idempotency tests
  test_agent_audit_events.py # NEW: DB integration tests (mock DB)
```

### Integration Points with Existing Code

```
src/agent/runtime.py
  └── handle_action()
        ├── [EXISTING] idempotency check
        ├── [NEW] policy_gate.evaluate(action, user, approval_token)
        ├── [EXISTING] execute action
        └── [NEW] audit_writer.write_event(event)

src/api/routers/actions.py
  └── POST /api/v1/actions/{action}
        ├── [EXISTING] JWT auth → user_id
        ├── [NEW] extract approval_token from request body
        ├── [NEW] policy_gate.validate_token(token, user_id)
        └── [EXISTING] agent_runtime.handle_action()

src/api/app.py
  └── [NEW] add_middleware(PolicyGateMiddleware)
        or register policy_gate as a FastAPI dependency
```

### Approval Token Schema

```python
# src/services/approval_token.py
import hmac
import hashlib
import json
from datetime import datetime, timedelta
from uuid import UUID

APPROVAL_TOKEN_TTL_SECONDS = 300  # 5 minutes, per agentic-ux-contract.md

def issue_token(card_id: str, user_id: str, action_type: str,
                idempotency_key: str, risk_class: str,
                secret: str) -> dict:
    issued_at = datetime.utcnow()
    expires_at = issued_at + timedelta(seconds=APPROVAL_TOKEN_TTL_SECONDS)
    payload = {
        "card_id": card_id,
        "user_id": user_id,
        "action_type": action_type,
        "idempotency_key": idempotency_key,
        "risk_class": risk_class,
        "issued_at": issued_at.isoformat(),
        "expires_at": expires_at.isoformat(),
    }
    signature = hmac.new(
        secret.encode(), json.dumps(payload, sort_keys=True).encode(),
        hashlib.sha256
    ).hexdigest()
    return {**payload, "signature": signature}

def verify_token(token: dict, user_id: str, secret: str) -> tuple[bool, str]:
    sig = token.pop("signature", None)
    expected = hmac.new(
        secret.encode(), json.dumps(token, sort_keys=True).encode(),
        hashlib.sha256
    ).hexdigest()
    if not sig or not hmac.compare_digest(sig, expected):
        return False, "invalid_signature"
    if token["user_id"] != user_id:
        return False, "user_mismatch"
    if datetime.fromisoformat(token["expires_at"]) < datetime.utcnow():
        return False, "token_expired"
    return True, "ok"
```

---

## 7. Safety and Compliance Policy

### Hard Rules (Cannot Be Disabled by Config)

1. **No auto-apply without explicit user approval.** `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true` is the floor, not the ceiling.
2. **No external sends (email, form submit) without a valid, unexpired approval token.**
3. **No third-party credential storage.** Rico never stores LinkedIn, Bayt, Glassdoor, or any portal passwords.
4. **P4 (bulk external) is locked.** No configuration, no feature flag, no override can enable it.
5. **Every consequential action writes an immutable audit event.** No silent execution.
6. **LLM-generated CV content must not fabricate experience.** Factual integrity check against original CV before presenting to user.
7. **Job description content must be sanitized before LLM injection.** Prompt injection via malicious job postings is a real attack vector.

### Soft Rules (Enforced by Default, Can Be Changed by Explicit User Permission Grant)

8. **P2 actions (internal writes) require per-action confirmation.** Can be relaxed to "auto-approve P2" in user settings (future premium tier).
9. **Cover letter must show confidence score on tailored content.** "I added 'ISO 45001 proficiency' — confidence: high based on your CV line 3."
10. **Agent stops and asks if job description is ambiguous.** No guessing on unclear requirements.

### License Compliance

| What | Rule |
|---|---|
| AGPL-3.0 code (AIHawk) | Zero lines imported into Rico |
| GPL-3.0 code (GodsScion) | Zero lines imported into Rico |
| Unknown-license code | Zero lines imported into Rico |
| MIT code (career-ops, Microsoft toolkit, Resume-Tailor-AI) | Can use as idea reference; code can be reimplemented from scratch |
| Apache-2.0 code (Resume-Matcher, Job_search_agent) | Can use as idea reference; derivatives acceptable with attribution |

---

## 8. Rico Feature Gap Map

| Gap | Current Rico | Best External Pattern | Recommended Rico Implementation | Priority |
|---|---|---|---|---|
| Approval token backend | `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS` env flag | Microsoft toolkit approval workflow + HMAC token | `src/services/approval_token.py` + `src/api/policy_gate.py` | **P0** |
| Agent audit log | Partial (agent_runtime audit log in memory/Telegram) | GitHub gh-aw `audit` command + immutable DB log | `agent_audit_events` table + `audit_writer.py` | **P0** |
| Policy gate endpoint | None | Microsoft toolkit policy middleware | `POST /api/v1/policy-gate/issue-token` | **P0** |
| CV tailoring per job | None | career-ops Tailor agent, AIHawk resume builder | LLM call with (base CV + JD) → diff output | **P1** |
| Cover letter generation | None | career-ops 4-angle prompt, varunr89 skill | LLM with (CV + JD + company context) → draft | **P1** |
| ATS keyword gap analysis | None | Resume-Matcher KeyBERT, Resume-Tailor-AI weighted score | LLM extracts keywords from JD, gaps from CV | **P1** |
| Job preflight check | None | career-ops preflight gate | Check JSearch for job still active before tailoring | **P1** |
| Permission tier system | Partial (admin/user roles only) | Microsoft toolkit P0-P3 | `user.permission_tier` field + tier enforcement in policy gate | **P1** |
| Skill gap statistics | None | beatwad/LinkedIn-AI-Job-Applier-Ultimate skill stats | Aggregate most-requested skills across saved/applied jobs | **P2** |
| Tailored Application Queue | None (planned) | AutoApply AI batch queue, career-ops batch mode | `/queue` page + backend queue table | **P2** |
| Prompt injection protection | None | GitHub gh-aw integrity filtering | Sanitize JD text before LLM context injection | **P1** |
| WebSocket agent status | None (Telegram only) | AutoApply AI WebSocket | SSE or WebSocket for in-app agent progress | **P2** |
| ATS-optimized PDF export | None | Resume-Matcher PDF export | Playwright HTML→PDF per tailored CV | **P2** |
| Direct career page crawler | None | Argus | Playwright scraper for UAE-specific job boards not on JSearch | **P2** |
| Company research context | None | varunr89 skill, career-ops | LLM research call: company + role + culture → tailor context | **P2** |
| Interview prep agent | None | career-ops skill mode | Rico chat mode: practice Q&A for specific job | **P3** |
| Salary benchmarking | None | None found (gap in market) | UAE salary data + LLM analysis per role + level | **P3** |
| Browser form filling | None | AIHawk Selenium, beatwad Playwright | Playwright agent (P3, premium only, per-form approval) | **P3** |
| Arabic CV generation | None | None found (gap in market) | Bilingual CV tailoring: Arabic + English sections | **P3** |

---

## 9. Implementation Roadmap

### Phase 0 — Safety Foundation (current sprint)
- ✅ PR #683 — Agentic UX Contract documented
- ✅ PR #688 — `/ask` UI prototype (auth guard added, Ready for Review)
- 🔲 `feat/agent-audit-policy-gate` — **open next**

### Phase 1 — Policy Gate + Audit Backend

**PR: `feat/agent-audit-policy-gate`**

Scope: Backend only. No UI changes. No frontend wiring.

Deliverables:
- `migrations/YYYYMMDD_add_agent_audit_log.sql`
- `src/services/approval_token.py` (issue + verify + HMAC)
- `src/services/audit_writer.py` (write AuditEvent to DB)
- `src/api/policy_gate.py` (middleware + policy rules)
- `src/api/routers/policy_gate.py` (POST `/api/v1/policy-gate/issue-token`)
- Wire policy gate into `src/api/routers/actions.py`
- Wire audit writer into `src/agent/runtime.py`
- Tests: token, expiry, HMAC, idempotency, policy rules, DB write

### Phase 2 — Wire /ask to Real Backend

**PR: `feat/ask-wire-backend`**

Scope: Connect `/ask` frontend to real API. No browser automation.

Deliverables:
- Replace `getMockAnswer()` in `mockData.ts` with real API calls
- `GET /api/v1/rico/ask` — intent classification + Action Card response
- `POST /api/v1/policy-gate/issue-token` wired from frontend
- Action Card approval → token → action execution
- Receipt shown after execution
- Audit event visible in future activity tab

### Phase 3 — Resume Tailoring + ATS Gap

**PR: `feat/resume-tailoring`**

Scope: Per-job CV tailoring and cover letter generation. No browser automation.

Deliverables:
- `POST /api/v1/rico/tailor` — accepts job_id, returns tailored CV delta + ATS score
- `POST /api/v1/rico/cover-letter` — accepts job_id, returns draft cover letter
- Preflight job freshness check before tailoring
- Factual integrity check: compare tailored content vs original CV
- Frontend: tailored CV diff view, cover letter editor, ATS score before/after

### Phase 4 — Application Queue + Statistics

**PR: `feat/tailored-application-queue`**

Scope: Batch queue for pending tailored applications. Skill statistics.

Deliverables:
- `applications_queue` table
- `/queue` page — list of pending tailored applications per user
- Batch approve / single approve UX
- Skill gap statistics: top requested skills across user's saved jobs
- Email/Telegram digest of queue status

### Phase 5 — Browser Automation (Premium Only)

**PR: `feat/browser-agent` (future, not planned yet)**

Scope: Playwright-based form filling for job applications. Premium tier only. Per-form approval. Full audit logging.

Gating requirements before this phase can begin:
- Phases 1–4 must be live and stable in production
- Subscription tier system must be live
- Legal review of ToS for target platforms (LinkedIn UAE, Bayt.com)
- Per-form approval UI must be implemented

---

## 10. PR Breakdown

| PR | Branch | Scope | Files | Tests | Depends On |
|---|---|---|---|---|---|
| 1 | `feat/agent-audit-policy-gate` | Policy gate + approval tokens + audit log | 8 new files | 4 test files | None — independent backend |
| 2 | `feat/ask-wire-backend` | Wire /ask to real API | 3 frontend + 1 backend | API integration tests | PR 1 |
| 3 | `feat/resume-tailoring` | CV tailoring + ATS gap + cover letter | 3 backend + 2 frontend | Tailoring + integrity tests | PR 1 |
| 4 | `feat/tailored-application-queue` | Batch queue + skill stats | 2 backend + 2 frontend | Queue + stats tests | PR 1, PR 2 |
| 5 | `feat/browser-agent` | Playwright form fill (premium) | TBD | TBD | PRs 1–4 + subscription system |

---

## 11. Test Plan

### Policy Gate Tests (`tests/test_policy_gate.py`)

```python
# Must cover:
def test_safe_action_passes_without_token(): ...
def test_low_risk_action_requires_p1_tier(): ...
def test_external_action_blocked_below_p3(): ...
def test_bulk_apply_always_blocked(): ...
def test_apply_without_token_blocked(): ...
def test_expired_token_rejected(): ...
def test_wrong_user_token_rejected(): ...
def test_tampered_token_rejected(): ...  # HMAC signature check
def test_already_executed_idempotency_key_rejected(): ...
def test_policy_decision_written_to_audit_log(): ...
```

### Approval Token Tests (`tests/test_approval_token.py`)

```python
def test_token_issue_contains_all_fields(): ...
def test_token_verify_valid(): ...
def test_token_verify_expired(): ...
def test_token_verify_wrong_user(): ...
def test_token_verify_tampered_signature(): ...
def test_token_verify_missing_signature(): ...
def test_token_ttl_is_300_seconds(): ...
```

### Audit Writer Tests (`tests/test_audit_writer.py`)

```python
def test_approved_action_writes_audit_event(): ...
def test_blocked_action_writes_blocked_event(): ...
def test_audit_event_is_immutable(): ...  # no update allowed
def test_duplicate_idempotency_key_raises(): ...
def test_audit_event_contains_user_id_and_card_id(): ...
```

### Resume Tailoring Tests (future — `tests/test_resume_tailoring.py`)

```python
def test_tailor_returns_diff_not_full_cv(): ...
def test_tailor_does_not_fabricate_experience(): ...
def test_ats_score_improves_after_tailoring(): ...
def test_cover_letter_contains_company_name(): ...
def test_preflight_check_rejects_closed_job(): ...
def test_factual_integrity_flag_raised_on_unsupported_claim(): ...
```

---

## Appendix A — License Compatibility Summary

| Repo | License | Can Reference Ideas | Can Import Code |
|---|---|---|---|
| feder-cr/AIHawk | AGPL-3.0 | ✅ ideas only | ❌ never |
| GodsScion/Auto_job_applier | GPL-3.0 | ✅ ideas only | ❌ never |
| wodsuz/EasyApplyJobsBot | Unknown | ✅ ideas only | ❌ never |
| santifer/career-ops | MIT | ✅ | ✅ with attribution |
| microsoft/agent-governance-toolkit | MIT | ✅ | ✅ with attribution |
| Rayyan9477/AutoApply-AI | MIT | ✅ | ✅ with attribution |
| beatwad/LinkedIn-AI-Applier-Ultimate | MIT | ✅ | ✅ with attribution |
| surapuramakhil/Job_search_agent | Apache-2.0 | ✅ | ✅ with attribution |
| srbhr/Resume-Matcher | Apache-2.0 | ✅ | ✅ with attribution |
| JaimeYeung/Resume-Tailor-AI | MIT | ✅ | ✅ with attribution |
| varunr89/resume-tailoring-skill | MIT | ✅ | ✅ with attribution |
| mshen1019/Argus | Unknown | ✅ ideas only | ❌ never |
| imon333/Job-apply-AI-agent | Unknown | ✅ ideas only | ❌ never |
| Pickle-Pixel/ApplyPilot | Unknown | ✅ ideas only | ❌ never |

---

## Appendix B — UAE Market Gaps Not Found in Any Public Repo

The following capabilities are not implemented in any public GitHub repository and represent Rico's genuine differentiation opportunity:

1. **Arabic CV generation and tailoring** — No public repo handles Arabic-language CVs or bilingual tailoring.
2. **UAE-specific job board scraping** — Bayt.com, Dubizzle, Gulf Talent, GCC Job Portal are not supported in any repo reviewed.
3. **Emiratisation-aware scoring** — No repo accounts for UAE Emiratisation targets in job matching.
4. **UAE salary benchmarking** — No structured UAE salary database integration found.
5. **MOHRE compliance guidance** — No repo helps users understand UAE labor law compliance for job applications.
6. **Visa status matching** — No repo filters jobs by visa requirements or sponsorship availability.

These gaps are Rico's competitive moat. They should be prioritized after the safety foundation (Phase 0–1) is stable.

---

*Report generated: 2026-06-21. Next action: open `feat/agent-audit-policy-gate`. Read this document before writing any code in that branch.*
