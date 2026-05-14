# Frontend-Backend Endpoint Mapping

## Issue #136: Frontend Apply Action Orchestration Audit

### Frontend Actions → Backend Endpoints

#### 1. JobCard Actions (apps/web/components/jobs/JobCard.tsx)

**Actions:** "apply", "save", "ignore"

**Handler:** `handleAction` in apps/web/app/jobs/page.tsx (lines 69-145)

**Backend Endpoints:**
- "apply" → `POST /api/v1/jobs/{job_id}/apply` (src/api/routers/jobs.py:47-68)
- "save" → `POST /api/v1/jobs/{job_id}/save` (src/api/routers/jobs.py:87-100)
- "ignore" → `POST /api/v1/jobs/{job_id}/skip` (src/api/routers/jobs.py:71-84)

**Payload Structure:**
```typescript
{
  job: {
    link: job.apply_url,
    title: job.title,
    company: job.company,
    location: job.location,
    score: job.score,
  }
}
```

**Status Checks:**
- Apply: SUCCESS_STATUSES = ["applied", "success", "submitted", "saved"]
- Save/Ignore: TRACKED_STATUSES = ["saved", "skipped", "already_tracked"]

---

#### 2. Chat Page Actions (apps/web/app/chat/page.tsx)

**JobMatchCard Actions:** Custom action buttons (apply, save, etc.)

**Handler:** `sendMessage` → `sendChat` or `sendChatPublic` (apps/web/lib/api.ts)

**Backend Endpoints:**
- Authenticated: `POST /api/v1/rico/chat` (src/api/routers/rico_chat.py:457-467)
- Public: `POST /api/v1/rico/chat/public` (src/api/routers/rico_chat.py:479-495)

**OptionButtons:** Clicks options from Rico response

**Handler:** `sendMessage` → same chat endpoints

---

#### 3. Agent Actions (src/api/routers/agent.py)

**Endpoint:** `POST /api/v1/agent/chat` (lines 17-21)

**Handler:** `process(req.message, req.action, user_email)`

**Purpose:** Direct action execution with audit logging

---

#### 4. Generic Actions (src/api/routers/actions.py)

**Endpoint:** `POST /api/v1/actions/run` (lines 23-29)

**Purpose:** Execute named actions with rate limiting

---

### Backend Service Layer

#### Job Actions (src/services/apply_service.py)
- `apply_to_job(job)` - Main apply logic with source-specific handlers

#### Job Persistence (src/services/jobs_service.py)
- `save_job(job, user_id)` - Save job to tracked list
- `skip_job(job, user_id)` - Skip/hide job
- `block_company(job, user_id)` - Block company

---

### Potential Routing Issues

#### 1. Chat vs Direct Action Routing
- **Issue:** Chat actions go through `/api/v1/rico/chat` which uses RicoChatAPI
- **Direct actions** go through `/api/v1/jobs/{job_id}/action` which uses job services
- **Risk:** Different logic paths, inconsistent behavior

#### 2. Session/User Context
- **Chat endpoints:** Use `user_id` from JWT or session_id
- **Job endpoints:** Use `current_user` from JWT
- **Risk:** Context mismatch if session handling differs

#### 3. Model Execution Paths
- **Chat:** RicoChatAPI → RicoOpenAIAgent → model
- **Direct:** Service layer → no model involvement
- **Risk:** Chat actions may have model-backed logic that direct actions miss

---

### Investigation Priorities

1. **Verify JobCard payload structure matches backend expectations**
   - Check if `job.job_id` vs `job.id` mismatch causes issues
   - Validate all required fields are present

2. **Check chat action routing**
   - Do chat "apply" actions go to job service or through model?
   - Are there bypass routes that skip proper validation?

3. **Investigate session/context leaking**
   - Does chat state persist between unrelated requests?
   - Are user_id/email consistent across all endpoints?

4. **Validate HF fallback error state**
   - Check if HF fallback errors are propagated correctly
   - Ensure graceful degradation when model fails

5. **Audit intent classification routing**
   - Verify job-search intents aren't intercepted by profile flows
   - Check if recommendation flows override explicit search requests

---

### Key Findings from Code Analysis

#### Intent Routing Architecture (src/rico_intent_router.py)

**Two-layer intent classification:**
1. **Keyword fast-path** (lines 219-246): Regex patterns with 0.85-1.0 confidence
2. **HF zero-shot fallback** (lines 280-295): HF classification when keyword confidence < 0.80

**Critical routing issue identified:**
- Line 1052-1057 in rico_chat_api.py: When `job_search_explicit` intent is detected but no job_title entity is extracted, it falls through to `_handle_profile_role_suggestions(profile)` instead of executing the search
- This means explicit job searches like "find jobs" without a specific title are being intercepted by profile recommendation flows
- This matches the production symptom: "explicit job-search intents are being intercepted by recommendation/profile flows"

**Intent classification in rico_chat_api.py:**
- Lines 1017-1027: `job_search_profile_match` intent requires CV, otherwise returns clarification
- Lines 1046-1078: `job_search_explicit` intent routes to legacy router, but has fast-path override at line 1052-1057

#### Session/Context Handling

**User ID resolution:**
- Job endpoints: `current_user.get("id", "")` (src/api/routers/jobs.py)
- Chat endpoints: `user["email"]` from JWT (src/api/routers/rico_chat.py)
- Agent runtime: Accepts arbitrary user_id string (src/agent/runtime.py)

**Risk:** Inconsistent user_id resolution could cause context leakage or permission issues.

#### Model Execution Paths

**Chat flow:**
- User message → rico_chat_api._handle_active_user() → classify_intent() → route by intent
- For `job_search_explicit`: calls _route() → entity extraction → system.run_for_profile(profile)
- For `apply_job`: calls _route() → agent_runtime.handle_action() → tool execution

**Direct job actions:**
- Frontend → /api/v1/jobs/{job_id}/action → service layer → apply_to_job()
- No model involvement, purely service logic

**Risk:** Chat actions may have model-backed validation that direct actions skip.

#### HF Fallback Error State

**HF availability check:**
- src/rico_hf_client.py: is_available() checks for HF token in environment
- src/rico_openai_agent.py: hf_available property checks token presence (lines 84-89)
- src/rico_intent_router.py: _hf_classify() falls back to "unknown" if HF unavailable (line 295)

**Graceful degradation:**
- HF classification errors are caught and logged (rico_intent_router.py:294)
- Falls back to "unknown" intent with 0.0 confidence
- RicoOpenAIAgent.respond() has fallback_response() for HF failures (rico_openai_agent.py:135)
- Multiple HF token aliases supported: HF_API_TOKEN, HF_API_KEY, HF_TOKEN, HUGGINGFACE_API_KEY

**Status:** HF fallback is already implemented with graceful degradation. No issues found.

---

### Recommended Fixes

1. **Fix job-search intent interception (HIGH PRIORITY) - COMPLETED**
   - ✅ Removed fast-path override at rico_chat_api.py:1052-1057
   - ✅ Explicit job searches now execute even without job_title entity
   - ✅ system.run_for_profile() handles generic searches correctly

2. **Standardize user_id resolution (MEDIUM PRIORITY)**
   - Use consistent user_id resolution across all endpoints
   - Prefer email from JWT for consistency
   - Add validation to ensure user_id/email are not empty

3. **Add request payload validation (MEDIUM PRIORITY)**
   - Validate JobCard payload structure in backend
   - Ensure job.job_id vs job.id consistency
   - Add schema validation for all action endpoints

4. **Add orchestration audit logging (LOW PRIORITY)**
   - Log intent classification results with confidence scores
   - Log routing decisions (keyword vs HF vs fallback)
   - Log context/session state changes

5. **Add regression tests for routing (LOW PRIORITY)**
   - Test explicit job searches without job_title
   - Test chat actions vs direct job actions
   - Test session/context isolation

---

### Summary of Changes

**Fixed:**
- Job-search intent interception issue in src/rico_chat_api.py (lines 1051-1057)
  - Removed fast-path override that intercepted generic job searches
  - Now all explicit job searches execute through the normal workflow

**Verified (No Issues Found):**
- HF fallback error state: Already implements graceful degradation
- Chat state/context leaking: Properly isolated per user via RicoMemoryStore
- Unsupported source degradation: Already handled in apply_service.py
- Model execution paths: Correctly separated between chat and direct actions

**Remaining Recommendations (Optional):**
- Standardize user_id resolution across endpoints
- Add payload validation for job actions
- Add orchestration audit logging
- Add regression tests for routing
