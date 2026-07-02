# Rico — Career Operating System Vision

**Recorded:** 2026-06-28  
**Origin:** Owner's strategic direction — verbatim intent preserved below.  
**Status:** Vision / roadmap — not yet scoped into individual tasks.

---

## Owner's intent (original Arabic)

> "للعلم : إذا كان هدفي بناء Rico ليصبح أفضل مساعد توظيف بالذكاء الاصطناعي وليس مجرد موقع وظائف،
> فهذه هي المنظومة التي سأبنيها. ليست قائمة ميزات، بل نظام تشغيل (Operating System)."

Translation: *"If my goal is to build Rico to become the best AI employment assistant — not just
a jobs website — this is the system I will build. Not a feature list, but an Operating System."*

---

## The 10-layer Career OS

Priorities are ⭐⭐⭐⭐⭐ (critical foundation) → ⭐⭐ (advanced differentiation).

### Layer 1 — AI Orchestrator ⭐⭐⭐⭐⭐

Central command router. Every user message flows through a single intelligent dispatcher that
understands intent, state, and which tool/agent to call.

- Unified intent classification (job search / CV / follow-up / advice / reminder / delete / ...)
- Context-aware routing: same words mean different things in different conversation states
- Fallback chain: specialist agent → AI fallback → keyword template → capability-limitation response
- Never makes up actions it cannot perform (P0 trust guard — already live)

### Layer 2 — Memory System ⭐⭐⭐⭐⭐

Four memory levels — from ephemeral session state to durable long-term user intelligence.

| Level | Scope | Backend | Exists today? |
|---|---|---|---|
| Session | Current conversation turn | In-process dict | Partial |
| User | Cross-session preferences (roles, cities, filters, CV) | Neon PostgreSQL | Partial (#741) |
| Career | Job history, applications, saved searches, outcomes | Neon PostgreSQL | Partial (#749) |
| Long-term | Patterns across months: which roles got interviews, which companies responded | Neon / analytics | Not started |

**Gap:** Rico still asks "what role are you looking for?" across sessions for returning users.

### Layer 3 — Career Intelligence Graph ⭐⭐⭐⭐⭐

Structured knowledge of the UAE job market: which roles exist, what they pay, where they cluster,
which companies hire them, and how they relate to each other.

- Role taxonomy with synonyms and seniority levels (HSE Manager → QHSE Manager → Safety Officer)
- Salary bands per role × city × seniority (UAE market data)
- Company → industry → common roles mapping
- Skill → role demand mapping (what skills does HSE Manager actually need?)
- **Use:** surfaces proactive insights ("your CV targets Technical Product Owner but Dubai HSE
  roles are 3× more abundant this week")

### Layer 4 — Planning Engine ⭐⭐⭐⭐⭐

Rico knows where the user is in their job-hunt journey and plans the next best action.

```
Today → CV ready? → Search → Apply → Follow-up → Interview prep → Offer negotiation
```

- State machine: each user has a career-hunt phase
- Proactive nudges: "You saved 5 jobs 3 days ago — have you followed up?"
- Daily/weekly plan: "Here are your 3 recommended actions for today"
- Goal tracking: "You want to land a role by September — you're on track / behind"

### Layer 5 — Trust Layer ⭐⭐⭐⭐⭐

Every action Rico takes must be explainable, auditable, and reversible.

- **Permission system:** high-impact actions (apply, send message, delete) require explicit user
  confirmation with a clear preview of what will happen (partially live — `agent_runtime`)
- **Audit log:** every action stored with `user_id`, `action`, `job_key`, `timestamp`, `result`
  (live — `action_audit_log`)
- **Confirmation layer:** 2-turn flows for destructive actions (live for delete-saved-jobs — #770)
- **Explainability:** Rico explains why it recommended a role or action ("Based on your CV
  skills and your preferred Dubai location...")
- **Correction:** user can undo or override Rico's decisions ("No, I meant a different role")

### Layer 6 — Workflow & Automation Engine ⭐⭐⭐⭐

Rico executes multi-step job-hunt workflows autonomously, with user oversight.

- **Save → Score → Draft cover letter → Apply** in one conversation thread
- **Daily scan:** check new matching jobs at 8am → notify via Telegram with top 3
- **Follow-up reminder loop:** applied 7 days ago → draft a polite follow-up email
- **Interview prep:** "You have an interview with Gulf Corp on Thursday — here are 5 likely
  questions for this HSE Manager role"
- Backend: `agent_runtime.handle_action()` is the execution gate; each workflow step is an action

### Layer 7 — Search Intelligence ⭐⭐⭐⭐

Better search, not more search.

- **Ranking:** fit-score × recency × company quality × location preference (partially live — #679)
- **Duplicate detection:** same job posted by multiple aggregators → show once
- **Dead link detection:** `apply_link` returns 404 or redirect-to-login → mark as dead before
  surfacing to user (partially live — trust gate #747)
- **Role expansion:** "HSE Manager" also searches "QHSE Manager", "Safety Manager" unless user
  said "exact title only"
- **Negative feedback loop:** user skipped 10 roles at Acme → stop showing Acme roles

### Layer 8 — AI Evaluation + Prompt Versioning ⭐⭐⭐⭐

Rico's quality is only as good as its prompts. Changes need regression protection.

- **Prompt versioning:** each system prompt + intent template has a version ID
- **Regression suite:** T1–T9 production tests (live — `tests/test_*.py`) + expanding
- **Eval harness:** run T1–T19 against any prompt change before merging
- **Provider abstraction:** swap OpenAI ↔ DeepSeek ↔ HF without rewriting prompts
- **Quality metrics:** measure response type distribution (job_matches / clarification / error
  ratio) over time

### Layer 9 — Operations Dashboard ⭐⭐⭐⭐

Owner visibility into what Rico is doing and where it's failing.

- Real-time message volume, error rate, provider health (`/health` — partially live)
- Top failing intents: what are users asking that Rico can't handle?
- Slow-path alerts: responses > 5s → Telegram admin channel
- Provider quota burn rate: which provider is being used how much?
- Job provider health: Jooble / Adzuna / JSearch uptime + result counts

### Layer 10 — Business & Billing ⭐⭐⭐

Monetization layer when the product is ready.

- Free tier: N searches/month, basic CV feedback
- Pro tier: unlimited search, auto-apply, workflow automation, priority AI
- Payment: Stripe
- Seat limits: max active applications per tier
- Upgrade nudge: triggered when free-tier limit is hit mid-workflow (not as a modal interrupt)

---

## Advanced Agents (future, after Layers 1–5 are solid) ⭐⭐

Each is a specialist sub-agent called by the Orchestrator (Layer 1) when the intent matches.

| Agent | Responsibility |
|---|---|
| Personal Recruiter Agent | Proactive daily scan, shortlist, notify |
| CV Agent | Parse, score, improve, tailor per job description |
| Cover Letter Agent | Draft, refine, match tone to company |
| Interview Prep Agent | Role-specific questions, mock answers, company research |
| Negotiation Agent | Salary benchmarking, counter-offer scripts |

---

## Current state vs. vision

| Layer | What's live | What's missing |
|---|---|---|
| 1 — Orchestrator | Intent router, fallback chain, trust guard | Unified single dispatcher; context-state routing |
| 2 — Memory | Session dict, durable document context (#741), basic role/city prefs | Career-level history; long-term patterns |
| 3 — Career Intelligence | Role taxonomy (partial, #730), UAE city filtering | Salary data; company graph; skill→role map |
| 4 — Planning Engine | Daily job run (`run_daily.py`), follow-up reminders (stub) | State machine; proactive nudges; goal tracking |
| 5 — Trust Layer | `agent_runtime`, audit log, delete-confirm 2-turn (#770), P0 trust guard (#767) | Full explainability; correction flows |
| 6 — Workflow Engine | Manual step-by-step via chat | Chained multi-step automation |
| 7 — Search Intelligence | Fit-score (#679), provider cascade (#724), trust gate (#747) | Dedup; dead-link scan; negative feedback |
| 8 — Eval | T1–T19 regression tests, CI | Prompt versioning; eval harness; quality metrics |
| 9 — Ops Dashboard | `/health`, `/version`, Telegram admin channel | Top-failing-intents report; quota burn |
| 10 — Billing | Stripe wired (env) | Tier enforcement; upgrade nudges |

---

## Recommended sequencing for next sprints

Work in parallel tracks — each track is independent enough to ship without blocking the other.

**Track A — Foundation (Layers 1–2–5):**
1. Unify the intent dispatcher (reduce the 3-path split in `rico_chat_api.py`)
2. Durable role + search context across sessions (extend #741 pattern)
3. Permission prompts for apply / CV-replace (PR-F, already planned)

**Track B — Search quality (Layer 7):**
1. Duplicate detection on job results (dedup by `job_key` before surfacing)
2. Dead-link async scan (background check after first display)
3. Negative feedback loop (user skip → company suppression)

**Track C — Planning nudges (Layer 4 starter):**
1. "You saved 5 jobs — have you followed up?" (Telegram notification after 7 days)
2. Daily top-3 job briefing via Telegram
3. Session-opening nudge: "Since last time: 2 new matches for HSE Manager"

**Track D — Agent layer (Layer 1 + Advanced Agents):**
1. CV Agent: tailor CV to a specific job description in-chat
2. Cover Letter Agent: draft from CV + job description
3. Interview Prep Agent: role-specific questions from the job posting

---

## Implementation principles

- **Incremental, always shippable.** Every PR ships something live, never a 500-line WIP.
- **Trust before automation.** The permission + audit layer (Layer 5) must be solid before
  expanding automation (Layer 6) — no silent side effects.
- **Tests first for regressions.** T1–T19 run on every PR. New capabilities get their own test file.
- **No silent substitution.** Rico must never silently swap a role, city, or action the user
  didn't ask for. Always ask before broadening, narrowing, or substituting.
- **Arabic-first UX.** Every user-facing string has an Arabic variant. UAE-specific content
  (cities, visa types, salary ranges) is the default frame.
