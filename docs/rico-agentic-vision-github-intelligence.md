# Rico Agentic Vision — GitHub Intelligence Report

**Date:** 2026-06-21  
**Branch:** `claude/practical-noether-7mikmr`  
**Status:** Spec / Research — no runtime code changes in this document  
**Scope:** GitHub landscape audit → feature gap map → agentic vision design → PR roadmap

---

## Executive Summary

The public GitHub ecosystem for AI-powered job search and application automation has matured rapidly in 2024–2026. The dominant pattern is a **6-stage pipeline**: discover → score → tailor resume → write cover letter → submit → track. The best systems add a **human-in-loop approval gate** before submission and a **browser automation layer** for form filling.

Rico already has several architectural advantages that most public repos lack:
- A production-grade approval model (`docs/agentic-ux-contract.md`, `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true`)
- A stateful agent with idempotency and audit logging (`src/agent/runtime.py`)
- A safety layer with role guardrails (`src/rico_safety.py`)
- UAE market specialization with Arabic/English identity

Rico's critical gaps are:
- **No CV tailoring per job** — the single most-requested feature across all top repos
- **No ATS scoring** — quantitative match analysis before applying
- **No cover letter generation** — tied to the tailoring pipeline
- **No browser automation for apply** — the gap between "queue approved" and "actually submitted"
- **The agentic action card system is specced but not implemented** (Phases 1–5 in `docs/architecture/agentic-ui-action-layer.md`)

This report maps the external landscape, identifies the top adoptable patterns, proposes a safe Rico Agentic Vision v1, and defines the implementation roadmap.

---

## Section 1 — GitHub Landscape

### 1.1 Repository Catalogue (Top 20 Relevant Repos)

The following repos were audited via GitHub search (queries: `auto-apply jobs AI agent`, `job search automation AI browser`, `browser-use job apply LinkedIn`, `resume tailoring ATS LLM`, `resume-tailoring topic`) and supplementary web research.

---

**REPO 01 — feder-cr/Jobs_Applier_AI_Agent_AIHawk**  
URL: https://github.com/feder-cr/Jobs_Applier_AI_Agent_AIHawk  
Stars: ~25,000 (largest job-apply AI repo on GitHub)  
License: AGPL-3.0 (copyleft — **incompatible with Rico commercial use**)  
Language: Python  
Last active: 2025–2026  

Core features:
- LinkedIn Easy Apply automation via Playwright
- GPT-powered resume/cover letter customization per job
- YAML-based profile/preferences configuration
- Multi-model support (GPT-4, Gemini, Ollama)
- Resume scoring against job descriptions
- Application blacklist and whitelist filters

Architecture patterns:
- Single user, runs locally from CLI
- Playwright for browser control
- GPT API for content generation
- YAML for user profile — no database
- No multi-user, no auth, no SaaS

Useful ideas for Rico:
- Resume customization prompt engineering patterns
- Job-description keyword extraction and matching
- Application filter logic (blacklist/whitelist companies)
- Score-threshold gating (only apply above X% match)

Risks/problems:
- YAML config is fragile and user-hostile
- No approval workflow — fires without confirmation
- LinkedIn ToS compliance is unclear
- Single-user only; no audit trail
- AGPL-3.0 license prevents adoption in Rico's commercial codebase

**Verdict: Ignore code entirely. Study pattern of GPT resume tailoring prompts as inspiration only.**

---

**REPO 02 — Pickle-Pixel/ApplyPilot**  
URL: https://github.com/Pickle-Pixel/ApplyPilot  
Stars: ~500+ (rapidly growing)  
License: Unlicensed / author-stated "Other" — **cannot import without permission**  
Language: Python  
Last active: 2026  

Core features:
- 6-stage pipeline: discover → score → tailor resume → write cover letter → submit → dashboard
- Scrapes 5 job boards + 48 Workday portals + 30 direct career sites
- AI scores every job 1–10 before touching it
- Resume rewritten per job (reorganized, keywords injected)
- Cover letter generated per job
- Playwright form-fill + CAPTCHA solving (hCaptcha, reCAPTCHA, Turnstile, FunCaptcha)
- SQLite conveyor-belt: each stage reads previous stage's output, writes new columns
- Live dashboard in real-time

Architecture patterns:
- Stage isolation: each stage is independently runnable
- Single database as state machine (stage columns on job rows)
- Claude Code launches Chrome for application submission
- CAPTCHA solving integrated (third-party service)

Useful ideas for Rico:
- The **6-stage pipeline as a mental model** maps cleanly onto Rico's Tailored Application Queue
- Stage isolation = Rico can run "tailor CV" without requiring "apply" in the same session
- SQLite conveyor-belt pattern → Rico's PostgreSQL job rows + application_status columns
- Score-gated apply: only propose apply action above a match threshold
- Cover letter as a separate, inspectable artifact before apply action

Risks/problems:
- CAPTCHA solving is legally and ethically questionable; violates most job portal ToS
- License is unclear — cannot import
- No approval gate — fires without user review
- No multi-user
- No UAE market targeting

**Verdict: Adopt the 6-stage mental model. Adapt the score-gate and stage-isolation pattern. Never adopt CAPTCHA solving or auto-submit. Cannot import code.**

---

**REPO 03 — eliornl/applypilot (different project, same name)**  
URL: https://github.com/eliornl/applypilot  
Stars: ~200+  
License: MIT (**permissive**)  
Language: Python  
Stack: FastAPI + PostgreSQL + Redis + Gemini  

Core features:
- Self-hosted, BYOK (bring your own key), no SaaS
- 5 AI agents run orchestrated pipeline in ~30 seconds per job
- Agents: role analyzer, fit scorer, company researcher, resume rewriter, cover letter writer
- Sequential where needed, parallel where possible (fit scoring + company research run in parallel)
- Application dashboard tracking all jobs processed
- Interview prep with mock sessions
- 6 career tools (salary negotiation, follow-ups, thank you notes, references, job comparison)
- Chrome extension for in-browser triggering

Architecture patterns:
- FastAPI async backend (same stack as Rico)
- PostgreSQL for persistence (same DB as Rico)
- Redis for caching, rate limiting, auth state
- 5 specialized agents with typed inputs/outputs
- Each agent has a single responsibility — no monolithic LLM blob
- Chrome extension as a separate entry point (interesting for Rico's multimodal intake)

Useful ideas for Rico:
- **The 5-agent decomposition is the best architectural reference for Rico's tailoring pipeline**
- Parallel fit scoring + company research reduces latency
- Each agent produces a typed output that the next agent consumes
- Interview prep is a natural P2 feature for Rico (gated behind subscription)
- Mock sessions + follow-up templates are low-risk, high-value features

Risks/problems:
- BYOK model (Gemini only) means it doesn't apply to Rico's provider routing
- Chrome extension introduces a separate security surface
- No approval gate — fires automatically

**Verdict: Strongly adopt the 5-agent decomposition pattern. MIT license permits studying code structure. Adapt for Rico's FastAPI stack and multi-user SaaS model. Never import code verbatim.**

---

**REPO 04 — browser-use/browser-use**  
URL: https://github.com/browser-use/browser-use  
Stars: 50,000+  
License: MIT (**permissive**)  
Language: Python  

Core features:
- Turns any LLM into a full browser automation agent
- Agent decides what to click/type/scroll/submit
- Supports vision models (screenshots) + DOM extraction
- Works with Playwright under the hood
- Task-level abstraction: "find this job and apply" → agent figures out the navigation

Architecture patterns:
- Agent loop: observe (screenshot or DOM) → reason → act → observe
- Action space: click, type, scroll, navigate, extract, submit
- Session persistence: browser state persists across agent steps
- Typed action outputs

Useful ideas for Rico:
- This is the cleanest way to build a browser automation layer for Rico's future **P3 apply actions**
- Vision + DOM gives the agent two strategies for resilient form navigation
- The task abstraction lets Rico say "navigate to this URL and submit this application" without encoding every site's DOM
- MIT license makes it a viable dependency in Rico's future automation layer

Risks/problems:
- Autonomous browser control is the highest-risk feature in any job platform
- Any bugs could submit forms the user didn't intend
- Session management (logged-in browser state) creates credential risk
- Job portal ToS may prohibit automated form submission
- **Must be locked behind P3 permission + explicit per-action approval before any use in Rico**

**Verdict: Candidate dependency for Rico's Phase 4–5 browser automation feature. Only usable behind full approval gate + P3 permission. MIT license compatible. Never use for auto-submit.**

---

**REPO 05 — microsoft/playwright-mcp** (inferred from Playwright MCP 34k stars result)  
URL: https://github.com/microsoft/playwright  
Stars: 34,000+ (MCP tool variant)  
License: Apache-2.0 (**permissive**)  
Language: TypeScript/Python  

Core features:
- Deterministic browser automation
- MCP server interface for AI agents
- Token-efficient (structured DOM, not full screenshots)
- Widely adopted for agentic browser workflows

Architecture patterns:
- MCP server: AI agent sends tool calls → Playwright executes → returns structured result
- Works in Claude Code, Cursor, and any MCP client
- Deterministic: same commands = same outcome (vs. browser-use's generative mode)

Useful ideas for Rico:
- For known form structures (e.g., LinkedIn Easy Apply), Playwright MCP is more reliable than browser-use
- Rico could encode UAE-specific job portal form patterns as Playwright scripts
- MCP interface makes it composable with Rico's existing MCP-compatible backend

Risks/problems:
- Still requires browser session management (credential handling)
- Site-specific scripts break when portals update their DOM
- Same ToS risks as browser-use

**Verdict: Candidate for Rico's P3 apply automation on known portals (Bayt, LinkedIn, Naukri UAE). More reliable than browser-use for deterministic flows. Only usable behind full approval gate.**

---

**REPO 06 — browserbase/stagehand**  
URL: https://github.com/browserbase/stagehand  
Stars: 10,000+  
License: MIT (**permissive**)  
Language: TypeScript  

Core features:
- SDK for browser agents with LLM steering
- Acts + observe primitives
- Cloud browser sessions (Browserbase platform)
- Cleaner API than raw Playwright for agent use cases

Architecture patterns:
- Act: "click the apply button" → Stagehand + LLM identifies the correct element
- Observe: "what are the form fields on this page?" → returns structured schema
- Built on Playwright internally

Useful ideas for Rico:
- `observe()` before `act()` is a useful pattern: Rico can first extract the form schema, present it to the user for review, then fill and submit after approval
- TypeScript-first — compatible with Rico's Next.js frontend if Rico ever wants browser control from the client side

Risks/problems:
- Cloud browser sessions require Browserbase account (cost + privacy implications for user credentials)
- Same apply-automation risks

**Verdict: Good pattern reference for observe-before-act workflow. MIT license. Lower priority than browser-use for Rico's Python-first backend. P2 candidate for a future TypeScript automation module.**

---

**REPO 07 — imon333/Job-apply-AI-agent**  
URL: https://github.com/imon333/Job-apply-AI-agent  
Stars: 160  
License: None — **cannot import**  
Language: Python  

Core features:
- n8n workflow + Selenium for LinkedIn/Indeed/StepStone
- OpenAI for CV and cover letter generation
- Google Sheets / Airtable for tracking
- Email alerts on application sent

Architecture patterns:
- n8n as orchestration layer (low-code)
- Selenium for browser automation
- External spreadsheet as state store

Useful ideas for Rico:
- n8n orchestration pattern shows that non-engineers can use workflow tools to wire up job pipelines — potential SaaS add-on idea for Rico (no-code automation flows)
- Spreadsheet tracking is the baseline that Rico's application tracker directly replaces
- Email alerts pattern = Rico's Telegram notification pattern

Risks/problems:
- n8n adds operational complexity
- Selenium is less reliable than Playwright
- No multi-user, no approval gate
- No license

**Verdict: Ignore as code reference. Confirms that Rico's application tracker is a viable replacement for manual spreadsheets.**

---

**REPO 08 — Liam-Frost/AutoApply**  
URL: https://github.com/Liam-Frost/AutoApply  
Stars: 99  
License: Other — **cannot import**  
Language: Python  
Topics: ai-agent, job-application, job-application-automation, job-application-management, job-search  

Core features:
- Personal job application AI Agent
- Job discovery + fit scoring + tailored materials + form filling
- **Human-gated submission** — this is the key differentiator
- Application tracking

Architecture patterns:
- Human gate before submission is architecturally aligned with Rico's approval model
- Fit scoring before presenting jobs to human gate
- "Tailored materials" suggests per-job CV/cover letter generation

Useful ideas for Rico:
- **The human-gated submission model is the closest public repo to Rico's intended UX**
- Confirms that the approval-gate approach is not just Rico's preference — it's a recognized best practice
- Could be used as a reference for how the approval gate integrates with material generation

Risks/problems:
- License is "Other" — cannot import or adapt code
- Stars are modest; likely early stage
- No multi-user SaaS

**Verdict: Study the approval-gate integration pattern. Cannot import code. Confirms Rico's UX direction is differentiated in the right direction.**

---

**REPO 09 — Rayyan9477/AutoApply-AI-Agentic-Browser-Automation-for-Job-Search**  
URL: https://github.com/Rayyan9477/AutoApply-AI-Agentic-Browser-Automation-for-Job-Search  
Stars: 37  
License: None  
Language: Python  
Topics: ai, ats, ats-friendly, automation, jobsearch, linkedin-scraper, resume-builder, resume-parser  

Core features:
- ATS-friendly resume building
- LinkedIn scraping
- AI resume/cover letter crafting
- Application submission assistance

Useful ideas for Rico:
- ATS-friendly output is a quality constraint Rico should embed in its tailoring pipeline
- Resume parser as a dedicated component (Rico already has `src/cv_parser.py`)

**Verdict: Ignore as code reference. ATS-friendly output is a useful quality bar to adopt as a Rico generation requirement.**

---

**REPO 10 — avinash1041/job-auto-apply (JobPilot)**  
URL: https://github.com/avinash1041/job-auto-apply  
Stars: 1  
License: None  
Language: Python  
Stack: FastAPI + Groq LLM + LangGraph + Playwright + ChromaDB  

Core features:
- LangGraph multi-agent architecture
- ChromaDB for semantic job-profile matching
- Playwright browser automation
- Dashboard UI

Architecture patterns:
- LangGraph state machine for multi-agent workflow
- Semantic embeddings for job-profile matching (not just keyword)
- ChromaDB for vector storage

Useful ideas for Rico:
- LangGraph's human-interrupt node is the cleanest existing pattern for Rico's approval gate in a multi-agent context
- Semantic similarity matching (embeddings) is superior to keyword matching for job scoring
- ChromaDB suggests a vector DB layer for job-profile similarity — Rico could add this without changing core architecture

**Verdict: Study LangGraph human-interrupt pattern. Not a code import candidate (no license, low quality). Semantic embedding for job scoring is a P1 architecture upgrade for Rico.**

---

**REPO 11 — gazitanbhir/JobBot**  
URL: https://github.com/gazitanbhir/JobBot  
Stars: 2  
License: None  
Language: Python  
Stack: FastAPI + LangChain + browser-use + Playwright  

Core features:
- LinkedIn search + apply using browser-use library
- LangChain for agent management
- FastAPI backend

Architecture patterns:
- FastAPI + browser-use is the same stack Rico would use for automation
- LangChain agent wraps browser-use actions

Useful ideas for Rico:
- Confirms FastAPI + browser-use as a viable combination
- LangChain agent as orchestrator over browser-use actions

**Verdict: No code import (no license). Architecture confirms the FastAPI + browser-use approach is straightforward to integrate.**

---

**REPO 12 — busycaesar/LLM-Powered_Resume_Optimizer**  
URL: https://github.com/busycaesar/LLM-Powered_Resume_Optimizer  
Stars: ~50  
License: MIT (**permissive**)  
Language: Python  
Stack: LangChain + OpenAI  

Core features:
- Resume enhancement against job descriptions
- ATS compatibility scoring
- Professional summary generation
- Cover letter generation

Architecture patterns:
- Separate chains: resume analysis, ATS scoring, cover letter generation
- LangChain for structured LLM outputs

Useful ideas for Rico:
- ATS scoring chain: input = (job_description, resume_text) → output = (score 0–100, keyword gaps, improvement suggestions)
- This is the core of what Rico's tailoring agent needs
- MIT license permits studying the prompt engineering patterns

**Verdict: Study prompt engineering patterns and chain decomposition. MIT license. Can use as a reference for Rico's tailoring agent design.**

---

**REPO 13 — olyaiy/resume-lm**  
URL: https://github.com/olyaiy/resume-lm  
Stars: ~300+  
License: MIT (**permissive**)  
Language: TypeScript  
Stack: Next.js 15 + React 19 + Tailwind  

Core features:
- AI resume builder
- ATS-optimized output
- Job-specific tailoring
- Claims 3x interview rate improvement

Architecture patterns:
- Next.js 15 (same version family as Rico's frontend)
- AI-driven form population vs. manual entry
- Tailwind styling (same as Rico)

Useful ideas for Rico:
- UI patterns for resume editing with AI suggestions embedded inline
- Diff view (before/after tailoring) as a UX pattern — Rico already has this in `ActionDiff` schema
- Next.js 15 + Tailwind integration patterns

**Verdict: Study UI patterns for AI-assisted resume editing. MIT license. Same tech stack as Rico frontend. UI reference only — no code import.**

---

**REPO 14 — NullSpace-BitCradle/ats-resume-agent**  
URL: https://github.com/NullSpace-BitCradle/ats-resume-agent  
Stars: ~20  
License: Unknown  
Language: Python  

Core features:
- Tailors resume to job descriptions with ATS optimization
- LaTeX PDF output
- Zero fabrication policy (every claim sourced from career document)
- Claude Code agent skill

Useful ideas for Rico:
- **Zero fabrication policy is directly aligned with Rico's safety model** — Rico must never invent facts about a user's career
- LaTeX/PDF output for tailored CVs is a premium feature Rico could offer
- The "every claim sourced from career document" rule is a constraint Rico should enforce in its tailoring prompt

**Verdict: Zero fabrication constraint is a must-adopt as a Rico safety rule. LaTeX PDF output is a P2 feature. License is unclear — cannot import code.**

---

**REPO 15 — devag7/linkedin-mcp**  
URL: https://github.com/devag7/linkedin-mcp  
Stars: 3  
License: MIT (**permissive**)  
Language: TypeScript  
Stack: MCP server + Playwright + stealth browser  

Core features:
- LinkedIn MCP server for AI assistants
- 22 tools: profiles, people search, job search, company search, feed, messaging
- Gated writes via LinkedIn's API
- Stealth browser engine (anti-detection)
- Safety layer (read operations unrestricted, write operations gated)

Architecture patterns:
- Read-first MCP server: all reads are safe, all writes require explicit tool call
- Stealth browser for scraping without immediate rate limits
- Structured JSON output from LinkedIn data

Useful ideas for Rico:
- LinkedIn job data as a structured feed into Rico's job pipeline (beyond JSearch/RapidAPI)
- MCP server pattern for platform-specific data connectors — Rico could have an `integrations/` layer with pluggable connectors per job board
- Gated writes (applying, messaging) as MCP tools behind Rico's approval gate

Risks/problems:
- LinkedIn ToS strictly prohibits scraping — stealth browser is explicitly against their terms
- Credential management for LinkedIn session is a security surface
- Anti-detection techniques are legally grey in most jurisdictions

**Verdict: Do not adopt scraping or stealth browser patterns. Study the MCP connector architecture as inspiration for Rico's integrations layer. MIT license permits studying the read/write gating pattern.**

---

**REPO 16 — ScrapeGraphAI/scrapegraph-py**  
URL: https://github.com/ScrapeGraphAI/scrapegraph-py  
Stars: 81  
License: MIT (**permissive**)  
Language: Python  

Core features:
- AI-powered web scraping SDK
- Smart scraping, search, crawling
- Structured data extraction
- Scheduled scraping jobs

Useful ideas for Rico:
- If Rico moves beyond JSearch/RapidAPI, ScrapeGraph is a permissive-license way to pull structured job data from portals that have no API
- UAE-specific portals (Bayt, Naukri UAE, GulfTalent) that JSearch doesn't cover well

**Verdict: Candidate dependency for Rico's UAE job data layer expansion. MIT license. Only implement after evaluating ToS of target portals.**

---

**REPO 17 — gl8410/job-hunting-agent**  
URL: https://github.com/gl8410/job-hunting-agent  
Stars: 2  
License: MIT (**permissive**)  
Language: TypeScript  

Core features:
- Job description parsing
- Company background checks
- Role alignment visualization
- Customized resume + cover letter generation
- Browser extension

Useful ideas for Rico:
- **Company research as an agent step** — Rico's tailoring pipeline could include a company research agent that runs in parallel with fit scoring (same as eliornl/applypilot)
- Role alignment visualization is a premium UX feature Rico could add to the match score card

**Verdict: Adopt company research as a parallel agent in Rico's tailoring pipeline. MIT license permits pattern study.**

---

**REPO 18 — ashmitb95/linkedin-leadgen**  
URL: https://github.com/ashmitb95/linkedin-leadgen  
Stars: 1  
License: None  
Language: TypeScript  
Stack: TypeScript + Claude AI + Playwright + SQLite  

Core features:
- Claude AI scoring across LinkedIn, Naukri, Hirist
- Dashboard with filtering, exports, outreach drafts

Useful ideas for Rico:
- Outreach draft (recruiter message) generation is a P1 feature for Rico's UAE market (many UAE recruiters work through WhatsApp/LinkedIn DM)
- Dashboard with filter/export confirms that Rico's application tracker needs filter + export features

**Verdict: Outreach draft generation is a high-value feature for UAE market. No code import (no license).**

---

**REPO 19 — Rishiikesh-20/Erflog**  
URL: https://github.com/Rishiikesh-20/Erflog  
Stars: 2  
License: MIT (**permissive**)  
Language: TypeScript  

Core features:
- Multi-agent orchestration for job search
- Semantic search for job matching
- Dynamic learning roadmaps
- Browser automation
- 24/7 autonomous operation

Useful ideas for Rico:
- Learning roadmap generation based on job description skill gaps is a differentiated feature for Rico's career coaching role
- "Skill gap → learning roadmap" connects Rico's career advice to actionable next steps

**Verdict: Skill gap → learning roadmap is a P2 feature for Rico's career coaching dimension. MIT license.**

---

**REPO 20 — Paramchoudhary/ResumeSkills (Claude Code skill)**  
URL: https://github.com/Paramchoudhary/ResumeSkills  
Stars: ~10  
License: MIT (**permissive**)  
Language: Python  

Core features:
- Claude Code skill for resume optimization
- ATS optimization
- Interview prep
- Strategic job search guidance

Useful ideas for Rico:
- This is architecturally similar to Rico's agent skills system
- Interview prep as a structured skill is a natural P1–P2 feature for Rico

**Verdict: Confirms Rico's direction. MIT license. No code import needed — Rico has a better architecture.**

---

### 1.2 Summary Table

| # | Repo | Stars | License | Key Pattern | Rico Action |
|---|---|---|---|---|---|
| 01 | feder-cr/AIHawk | ~25k | AGPL-3.0 ❌ | Resume tailoring + Playwright apply | Ignore code; study GPT prompts |
| 02 | Pickle-Pixel/ApplyPilot | ~500 | Unclear ❌ | 6-stage pipeline + SQLite conveyor | Adopt pipeline model only |
| 03 | eliornl/applypilot | ~200 | MIT ✅ | 5-agent decomposition + FastAPI | Adopt architecture pattern |
| 04 | browser-use/browser-use | 50k+ | MIT ✅ | LLM → browser agent | Future P3 dependency |
| 05 | microsoft/playwright-mcp | 34k+ | Apache-2.0 ✅ | Deterministic browser automation | Future P3 for known portals |
| 06 | browserbase/stagehand | 10k+ | MIT ✅ | Observe-before-act browser SDK | Pattern reference P2 |
| 07 | imon333/Job-apply-AI | 160 | None ❌ | n8n + Selenium + Sheets | Ignore code |
| 08 | Liam-Frost/AutoApply | 99 | Other ❌ | **Human-gated submission** | Study approval gate pattern |
| 09 | Rayyan9477/AutoApply | 37 | None ❌ | ATS-friendly resume builder | ATS quality bar reference |
| 10 | avinash1041/JobPilot | 1 | None ❌ | LangGraph + ChromaDB | Study LangGraph human-interrupt |
| 11 | gazitanbhir/JobBot | 2 | None ❌ | FastAPI + browser-use + LangChain | Architecture confirmation |
| 12 | busycaesar/Resume Optimizer | ~50 | MIT ✅ | LLM ATS scoring chain | Study prompt patterns |
| 13 | olyaiy/resume-lm | ~300 | MIT ✅ | AI resume builder (Next.js) | UI pattern reference |
| 14 | NullSpace-BitCradle/ATS agent | ~20 | Unclear ❌ | Zero fabrication safety rule | Adopt zero-fabrication policy |
| 15 | devag7/linkedin-mcp | 3 | MIT ✅ | LinkedIn MCP connector | Study connector architecture |
| 16 | ScrapeGraphAI/scrapegraph-py | 81 | MIT ✅ | AI-powered web scraping | Future UAE portal data layer |
| 17 | gl8410/job-hunting-agent | 2 | MIT ✅ | Company research agent | Adopt as parallel agent step |
| 18 | ashmitb95/linkedin-leadgen | 1 | None ❌ | Outreach draft generation | Outreach feature reference |
| 19 | Rishiikesh-20/Erflog | 2 | MIT ✅ | Skill gap → learning roadmap | P2 career coaching feature |
| 20 | Paramchoudhary/ResumeSkills | ~10 | MIT ✅ | Claude Code resume skills | Architecture confirmation |

---

## Section 2 — Competitive Feature Matrix

| Feature | AIHawk | ApplyPilot (PF) | eliornl/applypilot | Rico (current) | Rico (planned) |
|---|---|---|---|---|---|
| Job discovery | LinkedIn Playwright | 5+ boards + Workday | Manual paste | JSearch/RapidAPI | JSearch + UAE portals |
| Match scoring | GPT vs JD | AI 1–10 | Fit scorer agent | Basic keyword | Semantic similarity agent |
| CV tailoring per job | ✅ GPT rewrite | ✅ AI rewrite | ✅ Agent | ❌ Not implemented | P1 target |
| Cover letter per job | ✅ | ✅ | ✅ | ❌ Not implemented | P1 target |
| Company research | ❌ | ❌ | ✅ | ❌ | P2 target |
| ATS score | Partial | ❌ | ❌ | ❌ | P1 target |
| Browser auto-apply | ✅ Playwright | ✅ Playwright + CAPTCHA | ❌ | ❌ | P3 gate |
| Human approval gate | ❌ | ❌ | ❌ | ✅ specced | P1 target |
| Audit trail | ❌ | ❌ | ❌ | ✅ specced | P1 target |
| Multi-user SaaS | ❌ | ❌ | ❌ | ✅ | ✅ |
| Subscription gating | ❌ | ❌ | ❌ | Partial | P1 target |
| Arabic/English UX | ❌ | ❌ | ❌ | ✅ | ✅ |
| UAE market focus | ❌ | ❌ | ❌ | ✅ | ✅ |
| Application tracker | ❌ | Dashboard | Dashboard | Partial | Full |
| Interview prep | ❌ | ❌ | ✅ | ❌ | P2 target |
| Outreach drafts | ❌ | ❌ | ✅ | ❌ | P2 target |
| Skill gap roadmap | ❌ | ❌ | ❌ | ❌ | P2 target |
| Multimodal intake | ❌ | ❌ | ❌ | Specced | P2 target |

**Rico's unique moat:** Multi-user SaaS + approval gate + audit trail + Arabic/English + UAE focus. No public repo has all five.

---

## Section 3 — What Rico Should Adopt (as Ideas)

The following patterns are safe to implement in Rico as *inspired by* public repos. No code is being imported.

### 3.1 The 6-Stage Tailored Application Pipeline (from ApplyPilot / eliornl)

Adapted for Rico:

```
Stage 1: Job Discovery     → JSearch/RapidAPI + future UAE portal connectors
Stage 2: Fit Scoring       → Semantic similarity + keyword match (score 0–100)
Stage 3: CV Tailoring      → LLM rewrites CV sections targeting this JD (zero fabrication)
Stage 4: Cover Letter      → LLM generates tailored letter using CV + JD + user tone
Stage 5: Approval Queue    → User reviews all generated materials + approves or edits
Stage 6: Submission        → Manual link (Phase 1) → browser-assisted (Phase 3+)
```

Each stage is independent: user can use only Stage 2 (scoring) or only Stage 3+4 (tailoring) without committing to Stage 5–6.

### 3.2 The 5-Agent Decomposition (from eliornl/applypilot)

Adapted for Rico:

| Agent | Input | Output | Can run in parallel? |
|---|---|---|---|
| `JobAnalyzer` | Job description text | Structured: title, requirements, skills, culture | No — first |
| `FitScorer` | JD structured + user profile | Score 0–100, matched skills, gaps | Yes (parallel w/ CompanyResearcher) |
| `CompanyResearcher` | Company name + location | Summary, culture notes, UAE presence | Yes (parallel w/ FitScorer) |
| `CVTailor` | JD structured + user CV + fit score | Tailored CV sections (zero fabrication) | No — needs FitScorer output |
| `CoverLetterWriter` | JD structured + tailored CV + company notes + user tone | Cover letter draft | No — needs CVTailor + CompanyResearcher |

Total pipeline latency: ~20–40s depending on provider (FitScorer + CompanyResearcher run in parallel).

### 3.3 Score-Gate Before Proposing Actions (from AIHawk / ApplyPilot)

Rico should only propose apply actions when fit score ≥ configured threshold (default: 70/100). Below threshold, Rico should:
- Show the score and gaps
- Offer to improve the CV instead of applying
- Never auto-propose a low-match apply action

### 3.4 Zero Fabrication Safety Rule (from NullSpace-BitCradle)

Every tailoring prompt must include an explicit constraint: **all claims in the tailored CV must be sourced from the user's original career document. Rico must never invent job titles, dates, responsibilities, companies, or qualifications.** This constraint must be in the system prompt, not just in comments.

### 3.5 Observe-Before-Act Browser Pattern (from Stagehand)

When Rico's browser automation layer is built, it must first call `observe()` (extract form schema from the target page), present the filled-in form preview to the user for review, then call `act()` (submit). The user sees exactly what will be submitted before it is sent.

### 3.6 Company Research as a Parallel Agent Step (from gl8410, eliornl)

UAE-specific company research: Is this employer a known brand in the UAE? Does it have UAE sponsorship track record? Any known issues with salary payment delays or worker rights? These are UAE market-specific research signals that Rico can surface before the user applies.

### 3.7 Outreach Draft Generation (from ashmitb95)

Generate a recruiter outreach message (LinkedIn DM / WhatsApp) tied to a specific job. Rico should propose the draft, show it to the user, and only send after P3 approval.

### 3.8 Skill Gap → Learning Roadmap (from Erflog)

When fit score is below threshold, instead of just listing gaps, Rico should generate a short learning roadmap: "To improve match for QHSE Manager roles, you could: complete ISO 45001 Lead Auditor certification (3 months), add UAE site audit case studies to your CV." This turns rejection into a career coaching action.

---

## Section 4 — What Rico Must NOT Copy

| Pattern | Why it must be rejected |
|---|---|
| CAPTCHA solving (ApplyPilot) | Violates job portal ToS; legally questionable; exposes Rico to liability |
| Auto-submit without approval gate (AIHawk, most repos) | Violates Rico's core safety contract; breaches `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true` |
| LinkedIn scraping via stealth browser (linkedin-mcp) | LinkedIn ToS explicitly prohibits this; scraping employment data is legally sensitive in the UAE |
| YAML profile config (AIHawk) | User-hostile; creates support burden; Rico uses DB-backed profiles |
| AGPL code import (AIHawk) | AGPL requires open-sourcing Rico's entire codebase if incorporated |
| Autonomous bulk apply / 24/7 spray-and-pray (Erflog, ApplyPilot) | This is the opposite of Rico's value proposition of quality over quantity |
| Chrome credential storage for job portals | Rico must never store or manage users' third-party platform credentials |
| GPT-4 as hard-coded provider (most repos) | Rico's provider routing (DeepSeek → HF → keyword fallback) must be preserved |
| Fabricating job titles or responsibilities in tailored CVs | Rico's safety model and legal exposure require zero fabrication |

---

## Section 5 — Rico Agentic Vision v1

### 5.1 Operating Principles

1. **Quality over quantity.** Rico helps users apply to the right 3 jobs, not the wrong 100.
2. **Approval before action.** No external action (apply, email, contact recruiter) without explicit user approval.
3. **Transparency about what changed.** Every tailored CV or cover letter shows a diff from the original.
4. **Zero fabrication.** Tailoring only emphasizes and restructures; it never invents.
5. **UAE-first.** Company research, salary norms, visa requirements, and Arabic/English UX are built in.
6. **Audit trail.** Every action is logged. Users can see what Rico did, when, and why.
7. **Permission tiers.** As defined in `docs/agentic-ux-contract.md`: P0 (read) → P3 (external commit). P4 (bulk) remains locked.

### 5.2 Agent Roles

| Role | Name | Responsibility | Trigger | Output |
|---|---|---|---|---|
| Orchestrator | `RicoTailoringOrchestrator` | Manages pipeline state, stage sequencing, error handling | User action in chat or dashboard | Pipeline status events |
| Job Analyzer | `JobAnalyzerAgent` | Parses JD into structured schema | New job queued | `StructuredJobSpec` |
| Fit Scorer | `FitScorerAgent` | Scores user profile against job spec | After JobAnalyzer | `FitScore` (0–100 + gaps) |
| Company Researcher | `CompanyResearcherAgent` | UAE-specific company intelligence | After JobAnalyzer (parallel) | `CompanyProfile` |
| CV Tailor | `CVTailorAgent` | Rewrites CV sections for this job | After FitScorer | `TailoredCVDraft` |
| Cover Letter Writer | `CoverLetterAgent` | Generates tailored cover letter | After CVTailor + CompanyResearcher | `CoverLetterDraft` |
| Apply Agent | `ApplyAgent` | Browser-assisted form submission | **Only after explicit P3 approval** | `ApplicationReceipt` |
| Outreach Drafter | `OutreachDraftAgent` | Generates recruiter message | User request | `OutreachDraft` |
| Interview Prepper | `InterviewPrepAgent` | Generates mock Q&A for this role | User request after apply | `InterviewPrepPack` |

### 5.3 Full User Flow

```
User finds or saves a job (via Rico search or manual entry)
    ↓
Rico runs JobAnalyzer (extracts structured job spec)
    ↓
Rico runs FitScorer + CompanyResearcher in parallel
    ↓
Rico presents Action Card in chat:
    "Match score: 82/100. 3 skill gaps. Ready to tailor your CV?"
    [Tailor CV] [See gaps] [Research company] [Save for later]
    ↓
User clicks [Tailor CV]
    ↓
Rico runs CVTailor (generates tailored CV diff, zero fabrication)
    ↓
Rico runs CoverLetterAgent (generates cover letter draft)
    ↓
Rico presents Review Card:
    "Tailored application ready for: HSE Manager — Dutco Group"
    → CV diff (before/after sections)
    → Cover letter preview
    [Approve documents] [Edit CV] [Edit cover letter] [Reject]
    ↓
User approves documents
    ↓
Rico presents Action Card:
    "How would you like to apply?"
    [Copy application link] [Browser-assisted submit (P3)] [Mark as applied manually]
    ↓
If [Browser-assisted submit]:
    Rico requests P3 permission if not already granted
    Rico shows observe() preview: form filled with user data
    User sees exactly what will be submitted (read-only preview)
    User clicks [Confirm & Submit] or [Cancel]
    ↓
Submit executes → Receipt published → AuditEvent written
    ↓
Application appears in tracker with status "Applied"
    ↓
Rico proactively suggests follow-up timing:
    "Typical response window for UAE companies is 5–10 days.
     Should I remind you to follow up on June 28?"
    [Yes] [No]
```

### 5.4 Approval Flow Detail

All approvals follow the contract in `docs/agentic-ux-contract.md`:

| Action | Risk Class | Approval Type | Token TTL |
|---|---|---|---|
| Show job recommendation | safe | Auto | — |
| Generate CV tailor draft | low | Shown as draft, no approval | — |
| Generate cover letter draft | low | Shown as draft, no approval | — |
| Save tailored documents | medium | Inline confirmation | 5 min |
| Mark applied | medium | Inline confirmation | 5 min |
| Browser-assisted submit | high | Bottom sheet + preview | 5 min |
| Send recruiter outreach | high | Bottom sheet | 5 min |
| Bulk apply (≥3 in session) | critical | Bottom sheet + CONFIRM typed | 5 min |
| Autonomous bulk apply (P4) | **disabled** | Not available | — |

### 5.5 Policy Gate

The policy gate (`src/api/policy_gate.py` — to be built) enforces:

1. `ApprovalToken` signature verification (HMAC-SHA256)
2. Token not expired (`expires_at` check)
3. `user_id` matches authenticated session
4. `card_id` not previously executed (idempotency check in `agent_audit_log`)
5. User's permission tier covers the action's `risk_class`
6. `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true` is always re-checked regardless of token

### 5.6 Audit Trail

Every action writes an `AuditEvent` (schema in `docs/agentic-ux-contract.md`):
- Immutable, append-only
- Visible in user's Activity tab
- Exportable (for data portability compliance)
- Human-readable + expandable JSON
- Filterable by action type, date, approval state, external system

### 5.7 Browser Automation Boundary

```
Safe zone (P0–P2):
- Job search and display
- CV tailoring and cover letter generation
- Application tracker writes
- Profile/settings updates

Browser automation zone (P3 only):
- Form filling on known portals (after observe + preview + approval)
- Application submission
- Recruiter outreach via portal messaging (if supported)

Permanently disabled (P4):
- Bulk auto-apply
- Autonomous session (running without user present)
- CAPTCHA solving
- Credential storage for third-party portals
```

### 5.8 Failure Handling

| Failure | Behavior |
|---|---|
| JobAnalyzer fails to parse JD | Return raw text to user; offer to proceed with manual highlights |
| FitScorer returns < 50/100 | Show score prominently; offer skill gap roadmap; do not propose apply |
| CVTailor exceeds token limit | Tailor most-relevant sections only; note which sections were unchanged |
| Browser automation form error | Stop, show screenshot, ask user to proceed manually; log the failure |
| Provider timeout (DeepSeek → HF → keyword) | Follow existing Rico fallback chain; notify user of degraded quality |
| Approval token expired | Return "Proposal expired" — user must re-approve; old token invalidated |
| Idempotency key collision | Return receipt of prior execution; do not re-execute |

### 5.9 Subscription Gating

| Feature | Free | Pro | Premium |
|---|---|---|---|
| Job search + scoring | ✅ | ✅ | ✅ |
| CV tailoring per job | 1/week | 5/week | Unlimited |
| Cover letter per job | 1/week | 5/week | Unlimited |
| Company research | ❌ | ✅ | ✅ |
| Browser-assisted submit | ❌ | ❌ | ✅ (P3) |
| Interview prep | ❌ | ✅ | ✅ |
| Outreach drafts | ❌ | 5/month | Unlimited |
| Skill gap roadmap | ❌ | ✅ | ✅ |
| Priority provider routing | ❌ | ✅ | ✅ |

### 5.10 Observability

| Signal | How tracked |
|---|---|
| Fit scores per user/job | `agent_audit_log` + analytics table |
| Tailoring success rate | Did user approve or reject the tailored draft? |
| Cover letter quality | Did user edit before approving? |
| Apply conversion | Jobs scored → Jobs tailored → Jobs applied |
| Browser automation success/failure | Receipt vs. error in audit log |
| Pipeline stage latency | Per-agent timing recorded in orchestrator |
| Provider routing | Which provider was used for each tailoring call |

---

## Section 6 — Architecture Proposal

### 6.1 New Files / Modules

The following files are proposed. None exist yet unless noted.

```
src/
  agents/
    tailoring/
      orchestrator.py          # Pipeline state machine (LangGraph or custom)
      job_analyzer.py          # Parses JD → StructuredJobSpec
      fit_scorer.py            # Scores profile vs JD → FitScore
      company_researcher.py    # UAE company intelligence
      cv_tailor.py             # Rewrites CV sections (zero fabrication)
      cover_letter.py          # Generates cover letter draft
      outreach_drafter.py      # Recruiter message draft
      interview_prepper.py     # Mock interview Q&A
    models/
      tailoring_models.py      # Pydantic models: StructuredJobSpec, FitScore,
                               #   TailoredCVDraft, CoverLetterDraft, etc.
  api/
    policy_gate.py             # ApprovalToken validation (HMAC-SHA256)
    routers/
      tailoring.py             # POST /api/v1/tailoring/start, /status, /approve
  services/
    audit_writer.py            # Writes AuditEvent after every execution
    tailoring_service.py       # Orchestrates the 5-agent pipeline

migrations/
  YYYYMMDD_add_agent_audit_log.sql     # AuditEvent table
  YYYYMMDD_add_tailored_documents.sql  # TailoredCVDraft, CoverLetterDraft storage
  YYYYMMDD_add_tailoring_pipeline.sql  # Pipeline state tracking per user/job

apps/web/components/
  TailoringPipelineCard.tsx    # Shows pipeline progress (stages 1–5)
  CVDiffViewer.tsx             # Before/after diff for tailored CV
  CoverLetterPreview.tsx       # Editable cover letter card
  BrowserSubmitPreview.tsx     # observe() form preview before act()
  SkillGapRoadmap.tsx          # Skill gap → learning steps
```

### 6.2 Integration Points With Existing Architecture

| Existing component | How the new system integrates |
|---|---|
| `src/agent/runtime.py` | `ApplyAgent` calls `agent_runtime.handle_action()` — same idempotency scheme |
| `src/rico_safety.py` | All tailoring agents pass through safety guardrails before output |
| `src/api/routers/actions.py` | Apply action via browser goes through the same action router |
| `src/cv_parser.py` | `CVTailorAgent` reads from the already-parsed CV stored in DB |
| `src/repositories/*` | Tailored documents stored and retrieved via repository pattern |
| `apps/web/lib/api.ts` | New `startTailoring()`, `getTailoringStatus()`, `approveTailoredDocs()` methods |
| `docs/agentic-ux-contract.md` | `ActionCard` schema and `ApprovalToken` contract are reused exactly |

### 6.3 Data Model Additions

```sql
-- AuditEvent table
CREATE TABLE agent_audit_log (
  event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL,
  card_id TEXT NOT NULL,
  action_type TEXT NOT NULL,
  intent_summary TEXT NOT NULL,
  risk_class TEXT NOT NULL CHECK (risk_class IN ('safe','low','medium','high','critical')),
  approval_state TEXT NOT NULL CHECK (approval_state IN ('approved','rejected','expired')),
  policy_decision TEXT NOT NULL,
  target JSONB NOT NULL,
  data_used TEXT[] NOT NULL DEFAULT '{}',
  external_systems TEXT[] NOT NULL DEFAULT '{}',
  expected_effect TEXT NOT NULL,
  actual_effect TEXT,
  undo_used BOOLEAN DEFAULT FALSE,
  error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Tailored documents table
CREATE TABLE tailored_documents (
  doc_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL,
  job_id TEXT NOT NULL,
  doc_type TEXT NOT NULL CHECK (doc_type IN ('cv_tailored','cover_letter','outreach_draft')),
  content_original TEXT,
  content_tailored TEXT NOT NULL,
  diff_json JSONB,
  fit_score INTEGER CHECK (fit_score BETWEEN 0 AND 100),
  approval_state TEXT NOT NULL DEFAULT 'pending',
  approved_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Tailoring pipeline state
CREATE TABLE tailoring_pipeline (
  pipeline_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL,
  job_id TEXT NOT NULL,
  stage TEXT NOT NULL,  -- 'analyzing','scoring','researching','tailoring','writing','ready','approved','submitted'
  fit_score INTEGER,
  structured_job_spec JSONB,
  company_profile JSONB,
  error TEXT,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## Section 7 — Safety and Compliance Policy

### 7.1 Non-Negotiable Rules

These rules apply to any code that implements the agentic vision. They are not optional and cannot be overridden by subscription tier, user preference, or future PRs without explicit security review:

1. **`RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true` is always enforced**, regardless of any other config.
2. **Zero fabrication in tailoring**: Every LLM tailoring system prompt must include the constraint `"Every claim in the tailored CV must be sourced verbatim or summarized from the user's original career document. Do not invent job titles, companies, dates, responsibilities, qualifications, or skills."`.
3. **No credential storage**: Rico must never store or transmit users' job portal usernames or passwords. Browser automation uses the user's own authenticated browser session, which they manage.
4. **No CAPTCHA solving**: Any code path that attempts to bypass CAPTCHA is permanently blocked.
5. **No bulk auto-apply**: P4 actions remain disabled. Any PR that introduces bulk apply without explicit product review and legal sign-off must be rejected.
6. **Approval tokens are short-lived**: TTL is 5 minutes. No exceptions for "convenience."
7. **Audit events are immutable**: No UPDATE or DELETE on `agent_audit_log`. If a correction is needed, a correction event is appended.
8. **Safety guardrails in `src/rico_safety.py` apply to all tailoring agent outputs** — tailored CVs pass through the same safety check as chat messages.

### 7.2 UAE-Specific Compliance

- CV tailoring must respect UAE Labor Law norms: no fabricated qualifications or certifications.
- If the user's CV contains a professional license number (e.g., NEBOSH, engineering license, medical license), Rico must include it unmodified in the tailored version.
- Application tracking data is user-owned — must be exportable on request (PDPA readiness).
- Arabic content in tailored documents must be checked for cultural appropriateness and directional correctness (RTL).

### 7.3 ToS Considerations

- JSearch/RapidAPI: Rico's existing contract. No change needed.
- LinkedIn: Direct API access only through official LinkedIn Partner Program if implemented. No scraping, no stealth browser.
- Bayt, GulfTalent, Naukri UAE: ToS must be reviewed before any scraper is built. Default: use official APIs or JSearch coverage.
- Workday portals: browser automation on Workday is legally grey. Treat as P3 only with explicit user confirmation that they're interacting with the portal under their own account.

---

## Section 8 — Implementation Roadmap

Priorities: **P0** = blocks current users / critical gap, **P1** = next sprint, **P2** = next quarter, **P3** = future

### 8.1 Feature Gap Map

| Current Rico capability | Best external pattern | Recommended Rico implementation | Priority |
|---|---|---|---|
| Basic job search (JSearch) | 6-stage discovery | Add UAE portal connectors | P2 |
| Keyword match scoring | Semantic similarity (embeddings) | Add `FitScorerAgent` with embedding model | P1 |
| No CV tailoring | 5-agent decomposition | `CVTailorAgent` + zero fabrication prompt | P0 |
| No cover letter | Cover letter per job | `CoverLetterAgent` after CVTailor | P0 |
| No company research | Parallel company research agent | `CompanyResearcherAgent` (UAE-aware) | P1 |
| No ATS score | ATS scoring chain | ATS score as part of `FitScorerAgent` | P1 |
| Approval gate (specced, not built) | Human-gated submission (Liam-Frost) | Implement `docs/agentic-ux-contract.md` | P0 |
| No audit trail table | Audit log in all repos | `agent_audit_log` migration + `audit_writer.py` | P0 |
| Action cards (specced, not built) | Action card UI | Phase 1 of `docs/architecture/agentic-ui-action-layer.md` | P0 |
| No interview prep | eliornl/applypilot mock sessions | `InterviewPrepAgent` (subscription-gated) | P2 |
| No outreach drafts | LinkedIn leadgen outreach | `OutreachDraftAgent` (P2 permission) | P1 |
| No skill gap roadmap | Erflog learning roadmap | When fit score < 70, generate roadmap | P2 |
| No browser automation | browser-use + Playwright MCP | `ApplyAgent` (P3 permission, future) | P3 |
| Application tracker (partial) | ApplyPilot dashboard | Complete tracker with filter + export | P1 |
| Subscription gating (routing bug) | — | Fix Stripe routing bug (existing known gap) | P0 |
| Email follow-up reminders | n8n email alert pattern | Rico cron reminder sweep (Issue #355 exists) | P1 |

---

## Section 9 — PR Breakdown

### PR 1 — Audit Log Migration and Writer (P0)

**What:** Create `agent_audit_log` table and `audit_writer.py` service.  
**Files to add:**
- `migrations/YYYYMMDD_add_agent_audit_log.sql`
- `src/services/audit_writer.py`

**Files to change:**
- `src/agent/runtime.py` — call `audit_writer.write_event()` after every `handle_action()` execution

**Tests required:**
- Unit test: `audit_writer.write_event()` writes correct fields
- Unit test: second call with same `card_id` does not duplicate (idempotency)
- Unit test: `handle_action()` audit event has correct `approval_state`

**No frontend changes.**  
**No breaking changes to existing API.**

---

### PR 2 — Policy Gate Endpoint (P0)

**What:** `src/api/policy_gate.py` — validates `ApprovalToken` before high-risk actions.  
**Files to add:**
- `src/api/policy_gate.py`

**Files to change:**
- `src/api/routers/actions.py` — add policy gate check before apply action execution
- `src/api/app.py` — register policy gate middleware or dependency

**Tests required:**
- Unit test: valid token passes gate
- Unit test: expired token rejected
- Unit test: mismatched `user_id` rejected
- Unit test: previously-executed `card_id` rejected
- Unit test: `risk_class` mismatch rejected

---

### PR 3 — FitScorerAgent (P0–P1)

**What:** Score user profile against a job description (0–100 + skill gaps + ATS keyword list).  
**Files to add:**
- `src/agents/tailoring/job_analyzer.py`
- `src/agents/tailoring/fit_scorer.py`
- `src/agents/tailoring/models/tailoring_models.py`

**Files to change:**
- `src/api/routers/jobs.py` — add `?include_score=true` param that triggers FitScorer

**Tests required:**
- Unit test: `JobAnalyzerAgent` returns `StructuredJobSpec` for English JD
- Unit test: `JobAnalyzerAgent` returns `StructuredJobSpec` for Arabic JD
- Unit test: `FitScorerAgent` returns score 0–100 with gaps list
- Unit test: FitScorer below 50 does not propose apply action card
- Mock: LLM calls mocked — no live API calls in tests

---

### PR 4 — CVTailorAgent + CoverLetterAgent (P0)

**What:** Core tailoring agents. The zero-fabrication system prompt is the critical deliverable of this PR.  
**Files to add:**
- `src/agents/tailoring/cv_tailor.py`
- `src/agents/tailoring/cover_letter.py`

**Files to change:**
- `src/api/routers/tailoring.py` (new router) — `POST /api/v1/tailoring/start`
- `src/api/app.py` — register tailoring router

**Schema changes:**
- `migrations/YYYYMMDD_add_tailored_documents.sql`

**Tests required:**
- Unit test: tailored CV does not contain any text not present in original CV + JD (zero fabrication check)
- Unit test: tailored CV is not empty for any valid input
- Unit test: cover letter contains user name, target company, target role
- Unit test: Arabic JD produces bilingual or Arabic cover letter if user preference is Arabic
- Mock: LLM calls mocked

---

### PR 5 — Action Card Backend Response Schema (P0)

**What:** Wire `RicoAgenticUi` schema into chat responses. This is Phase 1 of `docs/architecture/agentic-ui-action-layer.md`.  
**Files to change:**
- `src/services/chat_service.py` — add `agentic_ui` field to response
- `src/rico_chat_api.py` — emit action cards for job search, fit score, tailor request intents

**Tests required:**
- Unit test: job search response includes `agentic_ui.actions` list
- Unit test: actions include correct `kind`, `impact`, `requires_confirmation` values
- Unit test: existing text-only response still works (backward-compatible)

**No frontend changes required in this PR** — frontend reads `agentic_ui` if present, ignores if absent.

---

### PR 6 — Action Card Frontend Renderer (P0–P1)

**What:** `ChatActionCard.tsx` renders action buttons in chat. Phase 1 UI.  
**Files to add:**
- `apps/web/components/ChatActionCard.tsx`
- `apps/web/components/PermissionPromptCard.tsx` (stub — wired in PR 8)

**Files to change:**
- `apps/web/app/chat/page.tsx` — render `agentic_ui.actions` from response

**Tests required:**
- `npm run build` passes
- Manual smoke: job search message renders action buttons
- Manual smoke: mobile viewport — buttons don't overlap composer
- Manual smoke: Arabic locale renders RTL buttons correctly

---

### PR 7 — CompanyResearcherAgent (P1)

**What:** UAE-specific company research running in parallel with FitScorer.  
**Files to add:**
- `src/agents/tailoring/company_researcher.py`

**Files to change:**
- `src/agents/tailoring/orchestrator.py` — run FitScorer + CompanyResearcher in parallel using `asyncio.gather()`

**Tests required:**
- Unit test: CompanyResearcher returns structured output for known UAE company name
- Unit test: CompanyResearcher degrades gracefully if company not found
- Unit test: Orchestrator runs FitScorer and CompanyResearcher in parallel (mock both)

---

### PR 8 — Approval Queue UI (P1)

**What:** `ApprovalQueueDrawer.tsx` + `CVDiffViewer.tsx` + `CoverLetterPreview.tsx`. Phase 4–5 of agentic UI plan.  
**Files to add:**
- `apps/web/components/ApprovalQueueDrawer.tsx`
- `apps/web/components/CVDiffViewer.tsx`
- `apps/web/components/CoverLetterPreview.tsx`

**Files to change:**
- `apps/web/app/chat/page.tsx` — open drawer when pending tailoring items exist
- `apps/web/lib/api.ts` — `approveTailoredDocs()`, `rejectTailoredDocs()`, `editTailoredDocs()`

**Tests required:**
- `npm run build` passes
- Manual smoke: approve tailored CV → receipt shown, audit event written
- Manual smoke: reject → no state mutation
- Manual smoke: edit → opens editable cover letter card

---

### PR 9 — OutreachDraftAgent (P1–P2)

**What:** Generate recruiter message for a specific job. P2 permission gate.  
**Files to add:**
- `src/agents/tailoring/outreach_drafter.py`

**Files to change:**
- `src/api/routers/tailoring.py` — `POST /api/v1/tailoring/outreach`

**Tests required:**
- Unit test: outreach draft contains user name, role, company
- Unit test: outreach draft does not exceed 300 words (LinkedIn DM constraint)
- Unit test: outreach draft requires P2 permission check

---

### PR 10 — Interview Prep Agent (P2)

**What:** Generate mock interview Q&A for a specific role. Subscription-gated.  
**Files to add:**
- `src/agents/tailoring/interview_prepper.py`

**Files to change:**
- `src/api/routers/tailoring.py` — `POST /api/v1/tailoring/interview-prep`
- `apps/web/components/InterviewPrepCard.tsx` (new)

**Tests required:**
- Unit test: generates 5 behavioral + 5 technical questions relevant to the JD
- Unit test: returns suggested answers grounded in user's CV
- Unit test: subscription gate blocks free tier

---

### PR 11 — Browser-Assisted Apply (P3 — Future)

**What:** `ApplyAgent` using browser-use. Locked behind P3 permission and explicit per-action approval.  
**Files to add:**
- `src/agents/tailoring/apply_agent.py`
- `apps/web/components/BrowserSubmitPreview.tsx`

**Files to change:**
- `src/api/routers/actions.py` — new apply path via `ApplyAgent`
- `src/api/policy_gate.py` — P3 permission check

**Dependencies to add:**
- `browser-use` (MIT) — to `requirements.txt` only after security review

**Tests required:**
- Unit test: apply agent will not fire without valid P3 approval token
- Unit test: apply agent logs failure gracefully on form error
- Integration test (mock browser): observe → preview → confirm → submit → receipt

**This PR cannot proceed until PRs 1–2 (audit + policy gate) are in production and battle-tested.**

---

## Section 10 — Test Plan

### Unit Testing Rules

- All agent tests mock LLM calls — never call live OpenAI, DeepSeek, or HuggingFace in unit tests
- All agent tests mock external HTTP (JSearch, company research APIs)
- Database tests use an isolated test schema or transaction rollback
- Zero fabrication tests use a fixture-based check: assert that every sentence in the tailored output overlaps with the source CV or JD

### Integration Testing

- Full pipeline test: JD input → FitScore + CompanyProfile → TailoredCV + CoverLetter → AuditEvent written
- Approval flow test: Action card issued → token issued → policy gate validates → action executed → receipt
- Expiry test: token issued → wait past TTL → execution rejected

### Frontend Build Tests

- `npm run build` must pass before any frontend PR merges
- Mobile viewport smoke (375px) for every new chat UI component
- Arabic RTL smoke for every user-visible string added

### Regression Tests

- Existing `/api/v1/rico/chat` endpoint must continue to return valid responses without `agentic_ui` (backward compat)
- Existing CV upload flow must continue to work
- Existing job save/skip/block actions through `agent_runtime.handle_action()` must be unaffected

---

## Appendix A — Key External Links

- AIHawk: https://github.com/feder-cr/Jobs_Applier_AI_Agent_AIHawk
- ApplyPilot (Pickle-Pixel): https://github.com/Pickle-Pixel/ApplyPilot
- ApplyPilot (eliornl): https://github.com/eliornl/applypilot
- browser-use: https://github.com/browser-use/browser-use
- Stagehand: https://github.com/browserbase/stagehand
- ResumeLM: https://github.com/olyaiy/resume-lm
- LLM Resume Optimizer: https://github.com/busycaesar/LLM-Powered_Resume_Optimizer
- ScrapeGraph: https://github.com/ScrapeGraphAI/scrapegraph-py
- LangGraph docs: https://www.langchain.com/langgraph

## Appendix B — Related Rico Docs

- `docs/agentic-ux-contract.md` — ActionCard schema, permission tiers, approval token contract
- `docs/architecture/agentic-ui-action-layer.md` — 8-phase UI implementation plan
- `docs/STATEFUL_AGENT_ARCHITECTURE.md` — request flow, agent components
- `docs/product/rico-product-model.md` — known gaps, workflow ownership
- `src/agent/runtime.py` — execution singleton, idempotency scheme
- `src/rico_safety.py` — safety guardrails
- `src/cv_parser.py` — existing CV parser

---

*Report generated: 2026-06-21. No runtime code was changed in this document.*
