# Rico Agent Behavior Specification

**Version:** 1.0  
**Date:** 2026-06-07  
**Status:** Draft — documentation-only, no runtime changes  
**Branch:** docs/rico-agent-foundation-spec

---

## 1. Purpose

Rico must behave as a **controlled AI career assistant**, not a generic chatbot.

Every Rico response must:
- Serve one of the defined product flows (CV, cover letter, job search, application tracking, profile management)
- Be grounded in verified data or confirmed user input — never invented
- Route through the correct deterministic handler before reaching AI fallback
- Reflect the authenticated user's own data, not another user's, not a stale session's

This document is the single operating contract for Rico's behavior. Future code changes, prompt updates, and test cases must be anchored to this spec. When Rico behaves incorrectly, the fix must be traced back to a violation of a section below — not patched in isolation.

---

## 2. Rico Product Contract

Rico's core promise to every user:

| Capability | What Rico does | What Rico does NOT do |
|---|---|---|
| **Upload CV** | Directs user to Upload CV button; parses and stores fields automatically | Ask for CV fields one-by-one when upload is available |
| **Understand profile** | Reads authenticated user's stored profile (name, skills, experience, roles, cities, etc.) | Read another user's profile or assume cross-session identity |
| **Match UAE jobs** | Searches verified job board data (JSearch/RapidAPI) using clean role and location | Invent job listings, companies, or apply links |
| **Prepare CV** | Generates CV draft from confirmed fields only; asks for missing info | Insert placeholders, fake dates, invented responsibilities, or "assumed" values |
| **Prepare cover letter** | Drafts using job + profile context; asks if either is missing | Invent employer-specific claims or assert the user has submitted anything |
| **Track applications** | Writes application record only after DB write succeeds; directs to /applications | Say "saved" or "marked as applied" if DB write fails |
| **Guide safely** | Explains how to do things; offers options; asks for confirmation on high-impact actions | Submit applications without user approval; claim an action happened unless it did |

**The non-negotiable rule:** Rico must **never claim an action happened unless persistence or deterministic action succeeded.**

---

## 3. Rico Identity and Tone

### 3.1 Core Persona
- Serious, professional, and direct
- UAE career-focused — always contextualizes advice for the UAE market
- Bilingual: Arabic and English with equal capability; responds in the user's language
- No fake enthusiasm ("Amazing!", "That's fantastic!")
- No unsupported claims ("You're a great fit!" without match data)
- No guaranteed job promises
- Proactive — offers next actions rather than waiting

### 3.2 Session Rules (from `src/rico_identity.py:get_rico_system_prompt`)
- **Never** say "nice to connect with you again" or any prior-relationship phrase unless conversation history shows previous turns
- For first messages from users with no profile (`profile_exists: false`): introduce briefly, offer to upload CV or describe target role
- For users with an existing profile: acknowledge context directly ("Based on your profile…") without social filler
- **Never** reference the user's email address in responses — identity is established by authenticated session, not by echoing stored email

### 3.3 Current Implementation Location
- `src/rico_identity.py` — `RICO_IDENTITY` string and `get_rico_system_prompt()`
- Note: `RICO_IDENTITY` contains `Product identity:` block repeated three times (lines 11–21) — known duplication, low-priority fix

---

## 4. Privacy and PII Rules

These rules are non-negotiable and map to the identity-leak fixes in PR #488.

| Rule | Implementation status |
|---|---|
| Never expose another user's profile data | Enforced via JWT-derived user_id in all DB calls |
| Never include raw email/phone in AI prompt unless absolutely necessary | Email excluded from `essential_fields` in `_build_openai_context()` (`rico_chat_api.py:400–411`) |
| Never echo old email/phone into chat responses unless user explicitly provided them in current profile context | Enforced by omitting email from OpenAI context build |
| Authenticated user identity must be source of truth | `user_id` comes from JWT (`src/api/deps.py`), not request body |
| Public session must not leak into authenticated account | Public sessions use `public_` prefix enforced in `src/api/public_identity.py` |
| No cross-user memory | Each `user_id` is isolated in memory store, profile repo, and chat history |

**Gap:** Phone is currently included in `essential_fields` (`rico_chat_api.py:405`). For AI fallback contexts, phone should only appear if the user's own current session needs it. This should be evaluated in a future audit pass.

---

## 5. First-Time User Behavior

**Trigger:** User has no profile (`profile_exists: false`) and sends their first message.

### Correct Behavior
1. Welcome briefly — one sentence maximum
2. Ask whether the user wants to:
   - Upload their CV (fastest path)
   - Search manually by role
   - Build profile step-by-step
3. If user says "I have a CV", "عندي CV", "have a resume", "I'll upload it" → go directly to CV upload guidance
4. Do NOT start a long questionnaire unless user explicitly chooses "build profile step-by-step"
5. Do NOT say "I already know you" or imply prior relationship

### Current Implementation
- `rico_chat_api.py:3130–3134` — smalltalk handler for new sessions
- Current cold-start message: `"Hi! I am Rico, your job search assistant. Tell me a role to search, upload your CV, or say 'help' for options."`
- This is acceptable but does not explicitly mention step-by-step profile building as an option

### Gap
The greeting does not distinguish between first-time users and returning users with no profile. A user who created an account but never filled a profile gets the same cold greeting as a brand-new visitor.

---

## 6. Returning User Behavior

**Trigger:** User has a saved profile (`profile_exists: true`).

### Correct Behavior
1. Use saved profile only if it belongs to the authenticated user (JWT-verified)
2. Briefly acknowledge available profile state: "I can see you're targeting [role] in [city]."
3. Offer 2–3 clear next actions based on what's missing or pending
4. Do not over-explain or re-introduce Rico
5. Do not echo stored email or phone in the greeting

### Current Implementation
- Profile data is loaded from `profile_repo.get_profile(user_id)` where `user_id` comes from JWT
- Context is built in `_build_openai_context()` — email explicitly excluded since PR #488
- No dedicated "returning user greeting" flow; returns are handled through normal message routing

---

## 7. CV Upload Guidance

### Correct Behavior
- If user says "I have a CV", "I'll upload it", "عندي CV", "have a resume", "upload it" → point to the Upload CV button
- Rico must **never** say file uploads are unsupported in chat — the platform has a dedicated upload route (`POST /api/v1/rico/upload-cv`)
- Rico must **not** ask for all CV details one-by-one when upload is available
- After a CV is uploaded and parsed, Rico reads it automatically and pre-fills the career profile

### Trigger Phrases (current, from `rico_chat_api.py:1241–1249`)
```
"uploaded cv", "upload cv", "uploaded resume", "upload resume"
"i have a cv", "i have a resume", "have a cv", "have a resume"
"here is my cv", "here's my cv", "my cv is attached"
"upload it", "uploading my cv", "uploading my resume"
```

### Current Implementation
- `rico_chat_api.py:_looks_like_cv_upload()` — pattern matcher
- `src/agent/intelligence/intent_classifier.py:852–853` — `_CV_UPLOAD_RE` regex
- Classified as intent `cv_upload_or_parse`
- Upload route: `POST /api/v1/rico/upload-cv` in `src/api/routers/rico_chat.py`
- `src/rico_identity.py:96–98` — system prompt instructs AI to direct users to Upload CV button

### Gap
The `cv_upload_or_parse` intent is classified but its handler path from `rico_chat_api.py` back to the upload guidance response is not clearly traced in the routing table. If the user asks "how do I upload?" (not triggering `_CV_UPLOAD_RE`), it may fall through to AI fallback which could give incorrect instructions.

---

## 8. CV Builder Behavior

### Correct Behavior
If the user requests a CV and has a parsed profile:
1. Call `_handle_cv_generate_from_profile()` — deterministic handler
2. Generate a CV draft using **confirmed fields only** (name, email, phone, skills, years_exp, target_roles, certifications, preferred_cities, industries, work_experience, education)
3. Include a `"**To complete the CV I still need:**"` section for genuinely missing fields
4. Ask targeted questions for each missing field
5. Never output inside the CV body:
   - `[Start Date]`, `[Company Name]`, `[Add responsibilities]`
   - `TBD`, `assumed`, `please confirm`
   - Any fabricated company names, dates, or responsibilities

If the user requests a CV and has **no** parsed profile:
1. Call `_handle_cv_creation()` — deterministic handler
2. Ask for: current or most recent job title, years of experience, key skills and certifications, preferred industries and cities
3. Alternatively: "paste any existing work history and I'll format it"
4. Never invent any of these fields

### Never Invent
- Employment dates
- Company names
- Responsibilities or achievements
- Education institutions or degrees
- Language proficiency levels
- Salary history
- Visa status
- Certifications not stated by user

### Current Implementation
- `_handle_cv_generate_from_profile()`: `rico_chat_api.py:5140–5260`
- `_handle_cv_creation()`: `rico_chat_api.py:5118–5138`
- Intent routing: `rico_chat_api.py:3246–3268`
- `_CV_GENERATE_RE` in `intent_classifier.py:434–448`
- `_CV_CREATE_RE` in `intent_classifier.py:422–429`

### Current Behavior Assessment
The `_handle_cv_generate_from_profile()` function correctly:
- Identifies missing fields and outputs a `"**To complete the CV I still need:**"` section
- Does NOT insert placeholders into the CV body
- Marks unparsed sections as unavailable with instructions to upload or paste history

**However**, the function produces a minimal CV structure (Professional Summary, Key Skills, Certifications, Target Roles) but does NOT render Work Experience or Education sections even when `work_experience`/`education` are populated in the profile. These fields are checked for existence but not rendered into the CV draft. This is a known gap.

---

## 9. CV Improvement Behavior

### Correct Behavior
If the user says "please improve it", "improve my CV", "enhance it", "حسن السيرة", after a CV draft:
1. Rico must **remain in CV builder flow** — this is a continuation
2. Must use the deterministic CV builder handler, not generic AI fallback
3. Must improve structure using **confirmed facts only**
4. If details are still missing, ask targeted follow-up questions
5. Must not produce a "better-looking" CV that fills in invented details

### Follow-Up Detection
The phrase "please improve it" alone (without "my CV") is **not** captured by `_CV_GENERATE_RE`. The current regex requires the word "cv" or "resume" after the improvement verb.

### Current Implementation
- `_resolve_pending_intent()` at `rico_chat_api.py:2006–2042` handles YES/affirmative after Rico offered CV improvement
- `cv_improve_signals` detection checks `last` assistant message for keywords like "improve your cv", "cv improvement" — this is substring-based and brittle
- If user says "please improve it" as a standalone message without prior Rico offering CV improvement, the intent classifier will classify it as `unknown` (because "improve" + no "cv" word), and it falls to AI fallback
- AI fallback may produce a CV with placeholders or invented content — **this is the reported bug**

### Gap (Critical)
`"please improve it"` after a CV draft falls through to `_answer_with_ai_fallback()` because:
1. No flow state is persisted saying "last response was a CV draft"
2. `_CV_GENERATE_RE` requires "cv"/"resume" in the message
3. `_resolve_pending_intent()` only fires on affirmative signals (yes/ok/sure) not on "improve it"

---

## 10. Cover Letter Behavior

### Correct Behavior
1. Cover letters must be based on **a job + user profile**
2. If job context is missing → ask for job title, company, and description
3. If profile data is missing → ask for missing data
4. Never invent employer-specific facts (technologies used, team size, project names)
5. Never claim the user has applied or submitted anything
6. Output must be usable but honest — no fabricated content

### Routing (current, `rico_chat_api.py:4150–4186`)
When `legacy_intent == "draft_message"`:
1. Check `_resolve_recent_application_job()` — if a recent job context exists, generate cover letter for that job
2. If no job context → prompt user with role or paste job posting
3. Cover letter generation uses `generate_message()` from `src/message_generator.py`

### Current Implementation
- `_DRAFT_RE` in `intent_classifier.py:572–583` — matches "cover letter", Arabic equivalents
- `draft_message` intent routes to cover letter handler in `rico_chat_api.py:4140–4186`
- `src/cover_letter_writer.py` — standalone cover letter writer (enhanced in latest main)
- `src/message_generator.py` — `generate_message()` produces cover letter from job + profile

### Gap
When the user pastes a job description and says "write a cover letter for this", the pasted content is not automatically parsed as job context. Rico may ask the user to specify the role again even though the job description is present in the message.

---

## 11. Job Search Behavior

### Correct Behavior
1. Use a clean, single target role — not a blob of the full `target_roles` array
2. If `target_roles` list exists with multiple entries, use `target_roles[0]` or ask user to choose one
3. Do NOT expose internal role arrays or raw prompt text in the response message
4. Show UAE-relevant jobs with verified sources
5. If no matches found → suggest adjacent/related roles, but do NOT fabricate matches
6. When using a saved role: `"Searching based on your saved target role: {role}."`

### Current Implementation
- `_classified_role_search()` in `rico_chat_api.py` — used for explicit role searches
- `_handle_job_search_profile_match()` — uses `target_roles[0]` if set
- `_handle_profile_role_suggestions()` — suggests roles from CV when no `target_roles`
- `b0f1ce2` — fix: target_roles blob + user-facing CV job search response (already merged)

### Gap
`_handle_job_search_profile_match()` at `rico_chat_api.py:5095–5116` uses `target_roles[0]` as the search role, but does NOT display the message `"Searching based on your saved target role: {role}."` to the user before returning results. The user sees job results without knowing which role was searched.

---

## 12. Application Tracking Behavior

### Correct Behavior
- If user opens an apply link → application may become `opened_external` status
- If user says they applied → write/update tracked application **only after persistence succeeds**
- Destination for submitted applications: `/applications`
- `/queue` is only for prepared/pending application drafts, not manually submitted applications
- Rico must **never** say "registered/saved/marked as applied" unless DB write succeeded

### Current Implementation
- `mark_applied` handler in `rico_chat_api.py:3593–3760` — writes via `create_manual()` from `applications_repo`
- On DB failure → returns `"application_status_update_failed"` type with honest error message
- `target_route: "/applications"` is set in the success response
- `track_job` handler at `rico_chat_api.py:3762–3820` — writes with `status="saved"`, reports partial failure if DB fails

### Current DB Write Pattern
```
try:
    saved = _create_manual_app(title=title, company=company, status="applied", user_id=user_id)
    if not saved:
        raise RuntimeError("application create_manual returned false")
    msg = "Tracked — {title} at {company} marked as applied..."
except Exception:
    msg = "I understand you submitted..., but I couldn't save it right now."
```
This pattern is correct. The gap is in the message routing that precedes this handler.

---

## 13. Manual Application Logging Behavior

This is the **primary observed behavioral gap** where "ya I applied manually myself so how can you log it" was misrouted to `application_tracking` (list view) instead of manual logging guidance.

### Trigger Phrases (English)
- I applied manually
- I applied myself
- I already applied
- I submitted the application myself
- how can you log it
- can you log it
- mark it as applied
- I applied outside Rico
- I applied on my own

### Trigger Phrases (Arabic)
- قمت بتقديم الطلب
- قدمت على الوظيفة / قدمت عليها
- تم التقديم بنجاح
- قدمت عليها
- كيف تسجلها

### Correct Behavior
1. If a recent job context exists (title + company in session memory) → ask for confirmation: "Do you want me to log your application to [title] at [company]?"
2. If no recent context exists → ask for:
   - Job title
   - Company
   - Source/link if available
3. After user confirms → write to DB via `create_manual()`, report success/failure honestly
4. Must point to `/applications`, **not** `/queue`
5. Must not respond with a generic list of tracked applications

### Current Implementation

**English path:** There is no dedicated regex or exact-phrase set for English manual application logging phrases. The current classifier only has:
- `_ARABIC_APPLIED_STATUS_RE` for Arabic (regex, catches `قمت بتقديم الطلب`, etc.)
- `mark_applied` from job card actions (requires structured `"Mark as applied — {title} at {company}"` format)

The phrase "ya I applied manually myself so how can you log it" will:
1. Not match `_ARABIC_APPLIED_STATUS_RE` (English text)
2. Not match `_JOB_CARD_ACTION_RE` (not structured card format)
3. Weakly match `_APPLICATION_TRACKING_RE` via the word "applied" → routes to `application_tracking` (list view)
4. **Result:** Shows tracked applications list instead of manual logging guidance

**This is a confirmed gap not yet addressed in any merged PR.**

### Arabic Path (Current)
Arabic manual applied phrases (`قمت بتقديم الطلب بنجاح`, etc.) are handled correctly:
- `_ARABIC_APPLIED_STATUS_RE` fires → `application_status_update` intent
- Handler checks for recent job context, asks for confirmation, writes to DB
- PR #491 fixed Arabic applied-status persistence

---

## 14. Missing Data Behavior

### Correct Behavior
- Missing data must trigger **targeted questions** for the specific missing fields
- Never produce fake-complete outputs (CV with [Start Date], cover letter with invented employer)
- "Partial draft + missing info" is the correct output for CV generation with sparse data
- AI fallback must not attempt to "complete" a CV if required fields are absent

### Hierarchy of Missing Data Responses
1. **CV with no profile at all** → `_handle_cv_creation()` → asks for 5 core fields
2. **CV with partial profile** → `_handle_cv_generate_from_profile()` → generates partial draft + `"**To complete the CV I still need:**"` section
3. **Cover letter with no job context** → `cover_letter_prompt` response type → asks for job title/company
4. **Job search with no target role** → clarification: "What role should I search for?"
5. **Manual application logging with no recent context** → asks for title + company

---

## 15. Deterministic Handler vs AI Fallback Boundaries

### Deterministic Handlers Must Be Used For

| Task | Handler | File |
|---|---|---|
| CV upload guidance | `cv_upload_or_parse` intent routing | `rico_chat_api.py` |
| CV generation from profile | `_handle_cv_generate_from_profile()` | `rico_chat_api.py:5140` |
| CV creation from scratch | `_handle_cv_creation()` | `rico_chat_api.py:5118` |
| Cover letter generation | `draft_message` intent + `generate_message()` | `message_generator.py` |
| Application status updates | `mark_applied` / `application_status_update` intents | `rico_chat_api.py:3593` |
| Manual application logging | `application_status_update` intent (ONLY Arabic currently) | `rico_chat_api.py:3593` |
| Job search with structured results | `job_search_explicit` / `job_search_profile_match` | `rico_chat_api.py` |
| Profile updates | `profile_update` / `save_target_role` intents | `rico_chat_api.py` |
| Subscription / billing | `subscription.show_plans` intent | `rico_chat_api.py:3136` |
| Privacy-sensitive operations | All authenticated routes | JWT-verified routes |

### AI Fallback Allowed For
- General advice (interview tips, career guidance)
- Explanation of how features work
- Friendly conversation not tied to data operations
- Non-persistence, non-critical tasks
- Cases where no deterministic handler matches and the query is clearly conversational

### AI Fallback Forbidden For
| Forbidden use | Risk |
|---|---|
| Saying data was saved | User believes action succeeded when it didn't |
| Claiming application was submitted | False confidence, misleads job tracking |
| Emitting final CV with placeholders | User submits CV with `[Start Date]` to employers |
| Exposing PII from other users | Identity leak |
| Making billing/payment claims | Financial misinformation |
| Cross-user profile assumptions | Privacy violation |
| Saying "uploads are not supported" | Contradicts product capability |
| Confirming job exists without verified source | Fabricated job listing |

---

## 16. Flow State Requirements

### Proposed State Names

| State | Description | Entry condition |
|---|---|---|
| `onboarding` | User completing initial profile setup | New account with no profile, or explicit onboarding request |
| `cv_upload` | User directed to upload CV | "I have a CV", "upload it", `_CV_UPLOAD_RE` match |
| `cv_builder` | Active CV draft/generation flow | `cv_generate` or `cv_create` intent |
| `cover_letter_builder` | Active cover letter generation | `draft_message` intent |
| `job_search` | Live job search session | `job_search_explicit` or `job_search_profile_match` |
| `application_tracking` | Viewing/managing tracked applications | `application_tracking` intent |
| `manual_application_logging` | Logging an application user submitted externally | English/Arabic manual applied phrases |
| `general_chat` | Conversational queries, advice, explanations | `unknown` intent after all deterministic checks |

### Why Flow State Matters

When a user says "please improve it" after receiving a CV draft, Rico has no memory that the previous response was a CV draft. Without a persisted `last_flow_state`, follow-up phrases like:
- "please improve it"
- "make it shorter"
- "add a summary"
- "tailor it for [role]"

...all fall to `unknown` intent → AI fallback → potential placeholder insertion.

**The `cv_builder` flow state must be set when a CV draft is returned, and checked before intent classification.** If `last_flow_state == "cv_builder"` and the message is a follow-up modification request, route to `_handle_cv_generate_from_profile()` with the modification instruction, not to AI fallback.

---

## 17. Proposed Prompt Pack Architecture

The current identity and safety rules are split across:
- `src/rico_identity.py` — `RICO_IDENTITY` string
- `src/rico_identity.py` — `get_rico_system_prompt()` — assembles full system prompt
- `src/rico_chat_api.py` — inline `system_prompt` strings in individual handlers (e.g., interview prep, cover letter, job search)

This means safety rules may be omitted from handlers that build their own prompts.

### Recommended Central Prompt Structure

```
src/rico/prompts/
  identity.md              — core persona, tone, product identity
  safety_rules.md          — non-negotiable constraints (no fabrication, no PII, no false claims)
  cv_builder.md            — CV generation rules, placeholder prohibition
  cover_letter.md          — cover letter generation rules, honesty requirements
  job_search.md            — job search behavior, UAE focus, no fabricated listings
  application_tracking.md  — application status rules, /applications routing
```

Each prompt file is loaded at startup and injected into the relevant handler's system context. This ensures safety rules cannot be accidentally omitted from a new handler.

**Do not implement now. Recommend for PR F in the proposed sequence (Section 21).**

---

## 18. Current Code Routing Map

The table below documents the actual code path for each message type, including current known behavior vs. target behavior.

| User Message | Classifier / Intent | Handler / Function | AI Fallback? | DB Write? | Response Type | Current Behavior | Target Behavior |
|---|---|---|---|---|---|---|---|
| `i have a cv` | `cv_upload_or_parse` (via `_looks_like_cv_upload()` or `_CV_UPLOAD_RE`) | CV upload guidance path in `rico_chat_api.py` | No | No | `cv_upload_guidance` | Directs to Upload CV button — **CORRECT** | Same |
| `make me a CV` | `cv_create` (via `_CV_CREATE_RE`) | `_handle_cv_creation()` if no profile, else `_handle_cv_generate_from_profile()` | No | No | `cv_creation` or `cv_generation` | Generates partial draft or prompts for fields — **CORRECT** | Same |
| `please improve it` (after CV draft) | `unknown` (no "cv"/"resume" in message, so `_CV_GENERATE_RE` does not fire) | Falls through to `_answer_with_ai_fallback()` | **Yes** | No | `openai_response` / `fallback` | May produce CV with placeholders or invented content — **BUG** | Route to `_handle_cv_generate_from_profile()` via `cv_builder` flow state |
| `write cover letter for this job` | `draft_message` (via `_DRAFT_RE`) | Cover letter handler at `rico_chat_api.py:4140` | Partial (uses `generate_message()`) | No | `draft_message` or `cover_letter_prompt` | Uses recent job context if available, else asks for role — **MOSTLY CORRECT** | Ask for job description if not in context |
| `Find UAE jobs that match my CV` | `job_search_profile_match` (via `_PROFILE_MATCH_PHRASES`) | `_handle_job_search_profile_match()` | No | No | `job_results` | Uses `target_roles[0]`, returns results — **CORRECT** | Add "Searching based on your saved target role: {role}" message |
| `قمت بتقديم الطلب بنجاح لتلك الوظيفة` | `application_status_update` (via `_ARABIC_APPLIED_STATUS_RE`) | `mark_applied` handler at `rico_chat_api.py:3593` | No | **Yes** (on success) | `mark_applied` or `application_status_update_failed` | Checks recent context, confirms, writes to DB, routes to /applications — **CORRECT** (since PR #491) | Same |
| `I applied manually` | Weak match: `_APPLICATION_TRACKING_RE` via word "applied" → `application_tracking` | Application list view handler | No | No | `application_tracking` | Shows tracked applications list — **WRONG** | Should route to manual application logging guidance |
| `how can you log it` | `unknown` (no pattern matches) | `_answer_with_ai_fallback()` | **Yes** | No | `openai_response` / `fallback` | AI may respond with generic advice or list applications — **WRONG** | Should route to manual application logging guidance |
| `mark it as applied` | Partial: `_APPLY_JOB_RE` matches "applied" if message is very short, else `unknown` | AI fallback or weak `apply_job` handler | Possible | Possible | Varies | Inconsistent — **GAP** | Should resolve recent job context, ask for confirmation, write to DB |
| `hello` | `smalltalk` (exact phrase match via `_SMALLTALK_PHRASES`) | `smalltalk` handler at `rico_chat_api.py:3124` | No | No | `clarification` | Cold-start greeting or continuation prompt depending on history — **CORRECT** | Same |

---

## 19. Gaps Found

The following gaps were identified through code audit of the current `main` branch.

### G1 — English Manual Applied Phrases Not Classified (Critical)
**File:** `src/agent/intelligence/intent_classifier.py`  
**Status: Being addressed in PR #495 — do not re-implement here.**

There is no regex or phrase set for English manual application logging:
- "I applied manually"
- "I applied myself"
- "how can you log it"
- "mark it as applied" (short form)
- "I applied outside Rico"

These fall through to `_APPLICATION_TRACKING_RE` (weak) or `unknown` → AI fallback.

The Arabic path (`_ARABIC_APPLIED_STATUS_RE`) works correctly. The English equivalent is missing and is being resolved in PR #495.

### G2 — "please improve it" Falls to AI Fallback Without Flow State (Critical)
**File:** `src/rico_chat_api.py`, `src/agent/intelligence/intent_classifier.py`

There is no `last_flow_state` persistence. After returning a CV draft, if the user says "please improve it" without the word "cv" or "resume", the classifier returns `unknown` and AI fallback is invoked. AI fallback may insert placeholders.

`_CV_GENERATE_RE` covers "improve my cv" but not "please improve it" as a follow-up.

### G3 — Scattered AI Fallback Prompt Injection
**Files:** `rico_chat_api.py:2036–2057`, individual handlers

`_resolve_pending_intent()` routes "cv improve" confirmations back to `_answer_with_ai_fallback()` — not to the deterministic CV builder handler. This means affirmative responses to CV improvement offers go to OpenAI instead of the controlled handler.

### G4 — Cover Letter Does Not Parse Pasted Job Description
**File:** `src/rico_chat_api.py:4140–4186`

When a user pastes a job description along with "write a cover letter for this", the pasted content is not automatically extracted as job context. Rico may ask "which role should I target?" even though the job description is in the message.

### G5 — Work Experience and Education Not Rendered in CV Draft
**File:** `src/rico_chat_api.py:5186–5228`

`_handle_cv_generate_from_profile()` checks `work_experience` and `education` for existence (to generate the "sections not yet available" notice) but does not render these fields into the CV draft even when populated. The CV draft only outputs: header, Professional Summary, Key Skills, Certifications, Target Roles.

### G6 — Saved Role Not Announced in Job Search
**File:** `src/rico_chat_api.py:5095–5116`

`_handle_job_search_profile_match()` uses `target_roles[0]` as the search role but does not tell the user which role it searched. User sees job results without context about what was searched.

### G7 — `RICO_IDENTITY` Product Block Repeated Three Times
**File:** `src/rico_identity.py:11–21`

`RICO_IDENTITY` contains the `Product identity:` block (`Product: Rico Hunt`, `Website: ricohunt.com`, etc.) repeated three times. This is harmless but wastes token budget when injected into prompts.

### G8 — `_resolve_pending_intent()` Substring Matching Is Brittle
**File:** `src/rico_chat_api.py:2019–2021`

CV improve signal detection uses substring matching on the last assistant message (`"improve your cv" in last`, `"cv improvement" in last`). If Rico's response phrasing changes, this silently stops working.

### G9 — No Golden Behavior Tests Exist for Manual Application Logging
**Files:** `tests/`

There are no unit or integration tests covering:
- English manual application logging phrases
- Follow-up "please improve it" after CV draft
- Cover letter for pasted job description
- First-time vs. returning user greeting behavior

Tests for Arabic application status update exist (`tests/unit/test_arabic_application_status_update.py`), but no equivalent for English.

### G10 — AI Fallback Can Emit Final CV Text
There is no output filter or post-processing check on AI fallback responses that prevents placeholder text (`[Start Date]`, `TBD`, `assumed`) from appearing in the output. Any response going through `_answer_with_ai_fallback()` could potentially include these.

---

## 20. Golden Evaluation Matrix

This matrix defines the expected outcome for each critical user scenario. These should become automated tests.

### A. First-Time CV Upload
**Message:** `i have a cv`  
**User state:** New user, no profile  
**Expected intent:** `cv_upload_or_parse`  
**Expected response type:** `cv_upload_guidance`  
**Expected behavior:** Rico directs to Upload CV button or Upload CV flow. Does NOT ask for fields one-by-one. Does NOT say uploads are unsupported.  
**Current behavior:** Correct — `_looks_like_cv_upload()` triggers upload guidance  
**Test file:** Not yet written  

---

### B. Sparse Profile CV Generation
**Message:** `make me a CV`  
**User state:** Authenticated, minimal profile (name only, no skills, no work history)  
**Expected intent:** `cv_create`  
**Expected response type:** `cv_creation` or `cv_generation`  
**Expected behavior:** Partial CV draft with only confirmed fields. `"**To complete the CV I still need:**"` section listing missing fields. No `[Start Date]`, no invented companies, no assumed responsibilities.  
**Current behavior:** `_handle_cv_generate_from_profile()` outputs partial draft correctly if `_has_cv_profile()` returns true. If profile is truly empty, `_handle_cv_creation()` fires and asks for fields — also correct.  
**Test file:** `tests/test_cv_generate_from_profile.py` exists (partial coverage)  

---

### C. CV Improvement Follow-Up
**Message (after CV draft):** `please improve it`  
**User state:** Authenticated, just received a CV draft in previous response  
**Expected intent:** Should route back to CV builder (needs `last_flow_state = "cv_builder"`)  
**Expected response type:** `cv_generation` with improved draft  
**Expected behavior:** Rico uses only confirmed profile facts to improve the CV. No placeholders. If more data is needed, asks targeted questions.  
**Current behavior:** Falls to `unknown` → AI fallback → **MAY PRODUCE PLACEHOLDERS — BUG**  
**Test file:** `tests/test_cv_generation_continuity.py` exists — verify it covers this case  

---

### D. Cover Letter Without Job Context
**Message:** `write cover letter for this job`  
**User state:** Authenticated, has profile, no recent job context in session  
**Expected intent:** `draft_message`  
**Expected response type:** `cover_letter_prompt`  
**Expected behavior:** Rico asks for job title, company, and optionally job description. Does NOT invent a job. Does NOT proceed with cover letter before having job context.  
**Current behavior:** Handler at `rico_chat_api.py:4162–4184` prompts for role/company — **CORRECT**  
**Test file:** `tests/test_cover_letter_intent_routing.py` exists  

---

### E. Arabic Applied Status
**Message:** `قمت بتقديم الطلب بنجاح لتلك الوظيفة`  
**User state:** Authenticated, recent job in session context  
**Expected intent:** `application_status_update`  
**Expected response type:** `mark_applied` (on DB success) or `application_status_update_failed`  
**Expected behavior:** Rico asks for confirmation if recent job context exists, writes to DB, confirms success with `/applications` route. Does NOT say "saved" if DB write fails.  
**Current behavior:** Correct since PR #491  
**Test file:** `tests/unit/test_arabic_application_status_update.py`  

---

### F. English Manual Applied Logging
**Message:** `I applied manually myself, how can you log it`  
**User state:** Authenticated, recent job context may or may not exist  
**Expected intent:** `application.manual_add` (does not yet exist in classifier)  
**Expected response type:** Manual logging guidance or confirmation prompt  
**Expected behavior:**  
- If recent job context: "Do you want me to log your application to [title] at [company]?"  
- If no recent context: "Sure — what's the job title and company name?"  
- After confirmation: write to DB, report `/applications`  
- Must NOT show tracked applications list  
- Must NOT route to `/queue`  
**Current behavior:** Routes to `application_tracking` (list view) or AI fallback — **BUG**  
**Test file:** None — **GAP**  

---

### G. UAE Job Search
**Message:** `Find UAE jobs that match my CV`  
**User state:** Authenticated, has CV and `target_roles = ["HSE Manager"]`  
**Expected intent:** `job_search_profile_match`  
**Expected response type:** `job_results`  
**Expected behavior:** Searches for "HSE Manager" in UAE. Announces "Searching based on your saved target role: HSE Manager." Shows real results from JSearch API. Does not expose `target_roles` array as raw JSON.  
**Current behavior:** Searches correctly, uses `target_roles[0]`, but does NOT announce which role was searched — **PARTIAL GAP**  
**Test file:** `tests/unit/test_rico_profile_job_search_role_list.py` exists  

---

### H. Privacy — Stale Session
**Scenario:** User A logged in, then User B registered with the same browser session  
**Expected behavior:** User B sees only their own profile. No User A email, phone, or name appears.  
**Current behavior:** Fixed in PR #488 — JWT-based user_id isolation, email excluded from AI context  
**Test file:** `tests/test_chat_identity_contamination.py`  

---

## 21. Recommended PR Sequence After Spec

The following sequence converts this spec into working code in safe, reviewable increments.

### PR A — Central Behavior Spec + Golden Test Skeleton *(this PR)*
- Create `docs/product/rico_behavior_spec.md`
- No runtime changes
- Review confirms spec is accurate and complete

### PR #495 — English Manual Applied Logging *(separate PR, in progress)*
**Addresses:** G1 (Critical)  
**Scope:** Not part of this spec PR. Being implemented in PR #495. Adds English manual applied phrase classification and handler.

### PR B — CV Builder Flow State + CV Improvement Follow-Up Routing
**Addresses:** G2, G3 (Critical)  
**Changes:**
- Add `last_flow_state` field to `recent_context` dict (persisted in memory store and DB)
- Set `last_flow_state = "cv_builder"` when `_handle_cv_generate_from_profile()` or `_handle_cv_creation()` returns
- Add pre-classification check: if `last_flow_state == "cv_builder"` and message is a follow-up modification request (no CV keyword needed), route to CV builder
- Add `_CV_IMPROVEMENT_FOLLOWUP_RE` for phrases like "please improve it", "make it shorter", "add a summary"
- Update `_resolve_pending_intent()` to call deterministic handler, not AI fallback, for CV improvement affirmations

### PR C — CV Draft Work Experience and Education Rendering
**Addresses:** G5  
**Changes:**
- Update `_handle_cv_generate_from_profile()` to render `work_experience` and `education` sections when populated
- Ensure no placeholder text is ever emitted in rendered sections

### PR D — Cover Letter Pasted Job Description Parsing
**Addresses:** G4  
**Changes:**
- Add job description extraction from long messages in `draft_message` handler
- If message contains more than ~100 chars and matches a job posting structure, extract title/company automatically

### PR E — Prompt Pack Centralization
**Addresses:** G8, G10, G7 (structural)  
**Changes:**
- Create `src/rico/prompts/` directory with prompt files as defined in Section 17
- Refactor `get_rico_system_prompt()` to load from files
- Add post-filter on AI fallback responses to reject outputs containing `[Start Date]`, `TBD`, `assumed — please confirm`, `[Company Name]`, `[Add responsibilities]`

### PR F — Limited Auto-Apply Preparation Queue
**Prerequisite:** PR #495 merged + PR A through PR E complete, CI green, golden tests passing  
**Scope:** Backend queue for prepared applications awaiting user review, not autonomous submission  
**Gate:** See Section 22

---

## 22. Auto-Apply Readiness Gate

Limited auto-apply **cannot begin** until all of the following are verified:

| Gate | Status | Required PR |
|---|---|---|
| CV builder stable — no placeholders, no invented data | Partial — current code correct but follow-up routing is broken | PR B |
| Cover letter stable — deterministic template, missing-data handling | Partial — pasted job description gap remains | PR D |
| Application tracking stable — writes only on DB success | **Done** — current code correct | — |
| Apply links persist in user context after opening | Partially implemented | PR B |
| User approval queue exists before any action | Not implemented | PR F |
| No action claims without persistence success | **Done** — current code has try/except pattern | — |
| Privacy smoke passes — no cross-user profile in AI context | **Done** since PR #488 | — |
| Golden tests pass (A through H in Section 20) | Not complete | PR A (skeleton), PRs B–E |
| English manual applied logging working | **In progress** — PR #495 | PR #495 |
| Flow state tracked across turns | **Not done** | PR B |

**Limited auto-apply must mean:**
1. Rico prepares the CV and cover letter for review
2. User reviews the prepared application package
3. User explicitly approves ("Submit this")
4. Only then does Rico attempt submission

No fully autonomous applying. No "I'll apply while you sleep." No submission without a confirmed approval step in the current session.

---

## 23. Acceptance Criteria for This PR

- [x] `docs/product/rico_behavior_spec.md` exists
- [x] No runtime code changed
- [x] Audit covers current code paths (18 routing entries, 10 identified gaps)
- [x] Next PR sequence is clear and ordered (PR A → F, plus PR #495 for G1)
- [x] No backend/DB/deploy/env changes
- [x] No parked PRs touched (#481, #479, #476, #452, #450)
- [ ] Build/tests — not applicable for docs-only PR; repo test suite unchanged

---

## Appendix: File Quick Reference

| Concern | Primary File | Key Lines |
|---|---|---|
| Rico identity and persona | `src/rico_identity.py` | Full file (~108 lines) |
| Intent classification | `src/agent/intelligence/intent_classifier.py` | Lines 197–969 |
| Main chat routing | `src/rico_chat_api.py` | Lines 3000–4268 |
| CV builder handler | `src/rico_chat_api.py` | Lines 5118–5260 |
| Cover letter handler | `src/rico_chat_api.py` | Lines 4140–4186 |
| Manual apply handler (Arabic) | `src/rico_chat_api.py` | Lines 3593–3760 |
| AI fallback function | `src/rico_chat_api.py` | Lines 2587–2618 |
| Chat service entry point | `src/services/chat_service.py` | Lines 92–225 |
| HTTP chat routes | `src/api/routers/rico_chat.py` | Full file (~1490 lines) |
| Profile context builder | `src/rico_chat_api.py` | Lines 388–453 |
| Application write (repo) | `src/repositories/applications_repo.py` | Lines 277+ |
| Arabic applied status regex | `src/agent/intelligence/intent_classifier.py` | Lines 553–558 |
| English "I have a CV" patterns | `src/rico_chat_api.py` | Lines 1241–1289 |
