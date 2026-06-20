# Rico Agentic UI Action Layer — Architecture Plan

## Objective

Move Rico from a text-only chatbot experience to a modern agentic career assistant UI where Rico can present contextual actions, permission prompts, progress states, approval queues, and multimodal document intelligence inside the chat and related product surfaces.

The goal is to make Rico feel like a current AI product: guided, proactive, permission-aware, document-aware, and execution-oriented, without sacrificing safety or user control.

## Product Principle

Rico should not only answer. Rico should propose the next safe action, explain what will happen, and ask for approval before high-impact work.

```text
User intent -> Rico interpretation -> suggested action -> user approval -> execution -> audit trail
```

The long-term product direction is conversation-first and multimodal: the chat becomes the primary control surface, users can bring screenshots/files/messages into the conversation, and traditional pages become supporting views that Rico can open, explain, and prefill through conversation.

## Product Positioning

Rico should not be presented as “another job-search tool.” Rico should be presented as a focused AI career entity for the UAE job market.

The user should feel:

- Rico understands career context, not just keywords.
- Rico can read what the user sees: screenshots, files, job posts, recruiter messages, CVs, and application material.
- Rico can turn messy real-world inputs into structured next actions.
- Rico asks before doing anything sensitive.
- Rico is specialized for job search, applications, profile improvement, career decisions, and UAE-market execution.

This positioning directly addresses the concern that users do not need another generic tool. Rico must become a specialized AI career operating system.

## Design Targets

- Modern AI command experience comparable to current agentic products.
- Clear user control before apply/send/mutate actions.
- No hidden automation for high-impact actions.
- Fast, clickable flows instead of typed A/B/C/D replies.
- Mobile-first cards and buttons.
- Arabic and English support from the first implementation.
- Backward-compatible API response shape where possible.
- Reduce manual form-filling by letting users configure profile, settings, searches, and application preferences through chat.
- Reduce sidebar/page dependence over time without removing deep links or fallback views too early.
- Accept screenshots and files beyond CVs, classify them, extract useful career context, and propose the next safe action.

## Core Concepts

### 1. Action Cards

Inline buttons/cards attached to Rico messages.

Examples:

- `Review jobs`
- `Save search`
- `Tailor CV`
- `Draft cover letter`
- `Complete profile`
- `Upload CV`
- `Analyze screenshot`
- `Extract job details`
- `Open application queue`

Action cards are low or medium impact. They may navigate, open a drawer, submit a safe action, or continue the chat with structured payload.

### 2. Permission Prompts

Explicit confirmation cards for high-impact actions.

Examples:

- Apply to a job.
- Send a cover letter or email.
- Save profile changes.
- Replace the active CV.
- Use a screenshot/file to update the user's profile.
- Enable recurring reminders or searches.

Permission prompts must show:

- What Rico wants to do.
- What data will be used.
- What will be saved or sent.
- Primary approval action.
- Secondary review action.
- Cancel action.

### 3. Progress Steps

Visible execution state for longer tasks.

Examples:

```text
Analyzing upload
✓ Detecting file type
✓ Reading screenshot text
✓ Extracting job details
• Preparing next actions
```

Progress can be optimistic in Phase 1 and event-driven later.

### 4. Approval Queue

A centralized list of pending high-impact actions.

Examples:

- Apply to HSE Manager at Dutco Group — waiting approval.
- Draft cover letter for voco Dubai Monaco — ready to review.
- Create saved search for QHSE Manager in Dubai — waiting approval.
- Improve CV for compliance roles — draft ready.
- Save extracted LinkedIn job as tracked opportunity — waiting approval.

The queue becomes the bridge between chat and real execution.

### 5. Conversation-First App Shell

Rico should eventually make the chat the main workspace and demote the sidebar from the primary navigation model to a lightweight context/status layer.

The user should be able to say:

- `غير المدينة لدبي والشارقة`
- `خلي الوظائف تكون HSE و QHSE فقط`
- `ارفع الحد الأدنى للراتب إلى 15000`
- `وقف التقديم التلقائي وخلي كل طلب بموافقتي`
- `ورجيني إعداداتي الحالية`
- `كمل بروفايلي من السي في`
- `حلل صورة إعلان الوظيفة هاي`
- `هاي رسالة recruiter، شو أرد؟`
- `هاي لقطة من LinkedIn، هل الوظيفة مناسبة؟`

Rico should respond with a structured review card instead of forcing the user to visit a settings page:

```text
Rico will update your job preferences:

- Cities: Dubai, Sharjah
- Target roles: HSE Manager, QHSE Manager
- Minimum salary: AED 15,000
- Application approval: Required

[Save changes] [Edit] [Cancel]
```

This does not mean deleting pages immediately. The safer model is:

1. Keep existing pages as fallback/deep-link/admin-friendly views.
2. Add conversational read/write flows for the same data.
3. Let action cards open focused panels/drawers only when visual review is needed.
4. Measure which pages become unnecessary after chat flows are reliable.
5. Remove or hide sidebar items only after equivalent chat-first flows exist and pass smoke tests.

### 6. Conversational Settings and Profile Editing

Manual forms should become optional, not required.

Target flows:

| Current page/manual action | Conversation-first replacement |
|---|---|
| Profile fields | Rico asks missing fields one by one, summarizes, asks to save |
| Settings filters | User states preferences naturally; Rico turns them into structured settings |
| Saved searches | User says what to monitor; Rico creates a saved search after approval |
| CV/profile sync | Rico extracts from CV, shows proposed changes, asks to confirm |
| Application preferences | Rico asks approval rules, salary, locations, excluded companies |
| Notifications/reminders | Rico proposes schedule/trigger and asks permission |

Every write must use a permission prompt or explicit confirmation summary.

### 7. Multimodal Career Intake

Rico must accept more than CV uploads. Users often have screenshots, recruiter messages, job posts, offer letters, LinkedIn comments, PDFs, Word documents, images, and partial information.

Supported intake categories should include:

| Input | Example user intent | Rico output |
|---|---|---|
| CV/resume | `حلل السي في` | Parsed profile, gaps, improvement actions |
| Job screenshot | Screenshot from LinkedIn/Indeed/company site | Extracted job title/company/location/requirements + fit estimate |
| Recruiter message | WhatsApp/email/LinkedIn DM screenshot | Suggested reply + action options |
| Job description file | PDF/DOCX/TXT | Fit analysis + tailored CV/cover letter actions |
| Application form screenshot | User stuck on a field | Guidance on what to fill, no fabricated data |
| Offer/contract document | Offer or salary package | Career-focused summary, risk flags, questions to ask |
| Certificate/license | Training or credential proof | Profile update proposal after confirmation |
| Company profile | Employer or target company document | Company summary + job-search relevance |
| Public comment/reply | Someone comments on Rico ad/post | Sentiment/objection analysis + suggested response |

The upload experience should be one universal entry point:

```text
Drop anything Rico should understand:
CV, job post, screenshot, recruiter message, certificate, offer, or application form.
```

Rico then classifies the input before deciding what to do.

## Multimodal Intake Flow

```text
User uploads screenshot/file
  -> Store raw file according to retention policy
  -> Detect file type and likely document purpose
  -> Extract text/metadata where possible
  -> Classify career intent
  -> Produce structured analysis
  -> Render action cards or proposed changes
  -> Ask confirmation before saving or executing
```

Example:

```text
User uploads LinkedIn job screenshot

Rico:
I found a job post in this screenshot.

Extracted:
- Role: QHSE Manager
- Company: Example Group
- Location: Dubai
- Key requirements: ISO 45001, site audits, UAE experience

Your likely fit: Strong, but salary is not visible.

[Save opportunity] [Compare to my CV] [Draft message] [Find similar jobs]
```

## Document Intelligence Rules

Rico should classify uploaded items before processing:

```text
cv_resume
job_post
recruiter_message
application_form
certificate
offer_letter
contract_or_legalish
company_profile
public_comment
unknown_document
```

Rules:

- Do not assume every upload is a CV.
- Do not save extracted profile changes without confirmation.
- Do not fabricate missing information for forms or applications.
- If the file appears legal/contractual, provide career-oriented observations and recommend qualified legal review when needed.
- If the file contains sensitive identity data, minimize retention and avoid unnecessary display.
- If OCR/extraction confidence is low, say so and ask the user to confirm.

## Proposed Backend Schema

Add a typed response extension without breaking existing `message`/`type` behavior.

```python
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field


class RicoActionKind(str, Enum):
    navigate = "navigate"
    submit = "submit"
    chat_continue = "chat_continue"
    open_drawer = "open_drawer"
    approve = "approve"
    cancel = "cancel"


class RicoActionImpact(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class RicoChatAction(BaseModel):
    id: str
    label: str
    kind: RicoActionKind
    impact: RicoActionImpact = RicoActionImpact.low
    requires_confirmation: bool = False
    endpoint: str | None = None
    href: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    tracking_key: str | None = None


class RicoPermissionRequest(BaseModel):
    id: str
    title: str
    summary: str
    risk_level: Literal["medium", "high"]
    data_used: list[str] = Field(default_factory=list)
    effects: list[str] = Field(default_factory=list)
    approve_action: RicoChatAction
    review_action: RicoChatAction | None = None
    cancel_action: RicoChatAction


class RicoProgressStep(BaseModel):
    id: str
    label: str
    status: Literal["pending", "running", "complete", "failed"]


class RicoProposedChange(BaseModel):
    field: str
    current_value: Any | None = None
    proposed_value: Any
    source: Literal["chat", "cv", "file", "screenshot", "system", "user_action"]


class RicoAttachmentPurpose(str, Enum):
    cv_resume = "cv_resume"
    job_post = "job_post"
    recruiter_message = "recruiter_message"
    application_form = "application_form"
    certificate = "certificate"
    offer_letter = "offer_letter"
    contract_or_legalish = "contract_or_legalish"
    company_profile = "company_profile"
    public_comment = "public_comment"
    unknown_document = "unknown_document"


class RicoAttachmentAnalysis(BaseModel):
    id: str
    filename: str | None = None
    mime_type: str | None = None
    purpose: RicoAttachmentPurpose
    confidence: float
    extracted_summary: str | None = None
    extracted_fields: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class RicoAgenticUi(BaseModel):
    actions: list[RicoChatAction] = Field(default_factory=list)
    permission_request: RicoPermissionRequest | None = None
    progress: list[RicoProgressStep] = Field(default_factory=list)
    proposed_changes: list[RicoProposedChange] = Field(default_factory=list)
    attachment_analysis: list[RicoAttachmentAnalysis] = Field(default_factory=list)
```

Then existing chat responses can include:

```python
{
    "message": "I found a job post in your screenshot.",
    "type": "document_analysis",
    "agentic_ui": {
        "actions": [...],
        "permission_request": None,
        "progress": [...],
        "proposed_changes": [...],
        "attachment_analysis": [...]
    }
}
```

## Frontend Components

Add these UI components under `apps/web` after confirming existing structure:

```text
ChatActionCard.tsx
PermissionPromptCard.tsx
ProgressSteps.tsx
ApprovalQueueDrawer.tsx
CommandSuggestionBar.tsx
ProposedChangesCard.tsx
ConversationPanel.tsx
AttachmentAnalysisCard.tsx
UniversalUploadDropzone.tsx
```

Expected rendering surfaces:

- Chat message footer for action cards.
- Message-level permission prompt for high-impact actions.
- Search/result messages for progress steps.
- Dashboard/sidebar/global drawer for approval queue.
- Empty states and profile banners for suggested commands.
- Proposed changes card for profile/settings/search preference updates.
- Attachment analysis card for uploaded screenshots/files.
- Focused drawer/panel for visual review when chat alone is not enough.

## Navigation Strategy

The target is not “no pages”; the target is “no forced manual pages.”

### Keep initially

- `/command` or main Rico chat surface.
- `/dashboard` as a status overview until chat can replace most dashboard tasks.
- `/jobs` as a visual results/review surface.
- `/applications` or approval queue view until queue is embedded well.
- `/profile` and `/settings` as fallback/manual correction surfaces.
- Existing upload/CV page if present, but reframe it as universal career intake rather than CV-only.

### Demote over time

- Sidebar becomes status + quick access, not the main workflow.
- Common actions move into chat action cards.
- Profile/settings pages become “advanced/manual edit” rather than required onboarding.
- File upload becomes part of the chat composer and onboarding conversation.
- Help/support moves to a floating or contextual affordance.

### Do not remove until

- Equivalent chat-first flow exists.
- Server-side validation exists.
- Permission prompt exists for writes.
- Mobile smoke passes.
- Arabic and English flows pass.
- Rollback path is clear.

## Safety Model

High-impact actions must never execute from a plain text reply alone.

High-impact action examples:

- Apply to a job.
- Send an email/message.
- Mutate profile preferences.
- Replace CV.
- Save extracted data from a file into profile/settings.
- Enable recurring cron-like behavior.

Rules:

1. Backend labels the action impact.
2. Frontend renders a permission prompt for high-impact actions.
3. Execution endpoint checks confirmation server-side.
4. Existing `agent_runtime.handle_action()` remains the execution boundary for job actions.
5. Existing `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true` remains mandatory.
6. Every approval/rejection should be auditable.
7. Profile/settings mutations must show a proposed-changes summary before saving.
8. Uploaded files must be purpose-classified before any write or downstream action.
9. Sensitive documents must not be used beyond the user's requested career workflow.

## Data Flow

### Low-impact action

```text
User message
  -> Rico backend intent handling
  -> Response with actions[]
  -> Frontend renders buttons
  -> User clicks action
  -> Navigate / continue chat / safe endpoint
```

### High-impact action

```text
User message
  -> Rico backend detects requested action
  -> Backend returns permission_request
  -> Frontend renders approval card
  -> User approves
  -> Frontend calls execution endpoint with permission id
  -> Backend validates permission + user identity
  -> agent_runtime executes
  -> Audit log records result
  -> Chat shows final state
```

### Conversational settings/profile update

```text
User states preference or profile change
  -> Rico extracts structured fields
  -> Backend validates fields and computes proposed_changes[]
  -> Frontend renders proposed changes card
  -> User approves, edits, or cancels
  -> Backend writes only approved changes
  -> Chat confirms saved state
```

### Screenshot/file analysis

```text
User uploads file or screenshot
  -> Backend stores/streams upload according to retention policy
  -> File classifier detects purpose
  -> Extractor reads text/metadata/visual context
  -> Rico returns attachment_analysis[] with confidence and warnings
  -> Rico proposes contextual actions
  -> User chooses next step
  -> Any save/send/apply action requires confirmation
```

## Phase Plan

### Phase 0 — Architecture and contracts

Scope:

- Add this architecture plan.
- No runtime changes.

Acceptance:

- Clear schema direction.
- Clear safety rules.
- Clear phased implementation.

### Phase 1 — Inline Action Cards for Chat

Scope:

- Add backend response extension for `agentic_ui.actions`.
- Add frontend renderer for action cards.
- Start with safe actions only:
  - Review jobs
  - Save search
  - Complete profile
  - Upload CV/file
  - Analyze screenshot
  - Draft cover letter prompt

Constraints:

- No automatic apply.
- No DB migration unless already needed by existing action path.
- Existing text-only responses must continue working.

Verification:

- Backend unit tests for response shape.
- Frontend build.
- Chat smoke: job search message renders action buttons.
- Mobile smoke.

### Phase 2 — Universal Multimodal Career Intake

Scope:

- Add upload handling that does not assume every file is a CV.
- Add purpose classification for CV, job post, recruiter message, application form, certificate, offer, company profile, public comment, and unknown document.
- Add `attachment_analysis` response support.
- Add frontend attachment analysis card.
- Start with screenshots and text/PDF/DOCX files already feasible in the current stack.

Constraints:

- No profile/settings writes from extracted data without confirmation.
- No fabricated answers for application forms.
- OCR/extraction confidence must be visible when low.
- Sensitive identity documents require conservative handling.

Verification:

- Uploading a CV still works.
- Uploading a job screenshot returns extracted job details and action cards.
- Uploading a recruiter message suggests a reply but does not send it.
- Uploading unknown document asks clarifying question.
- Arabic and English screenshots/messages are handled as well as extraction allows.

### Phase 3 — Conversational Profile and Settings Review Cards

Scope:

- Add `proposed_changes` support for profile/settings/search preferences.
- Let Rico summarize proposed changes before saving.
- Start with low-risk settings:
  - target roles
  - cities
  - salary expectation
  - language preference
  - search filters

Constraints:

- No silent profile/settings writes.
- Server-side validation required.
- Keep `/profile` and `/settings` as fallback views.

Verification:

- User can ask Rico to change a setting.
- Rico shows before/after values.
- Save only happens after approval.
- Cancel does not mutate state.
- Arabic and English commands work.

### Phase 4 — Permission Prompt for Apply and Profile Mutation

Scope:

- Add `permission_request` rendering.
- Add explicit approve/review/cancel actions.
- Wire first high-impact flow: job apply approval.
- Reuse existing approval/safety mechanisms where possible.

Constraints:

- Server-side confirmation required.
- No client-only safety.
- Must not bypass `agent_runtime.handle_action()`.

Verification:

- Apply cannot execute without confirmation.
- Cancel does not mutate state.
- Approved action records audit log.
- Arabic and English prompt copy render correctly.

### Phase 5 — Approval Queue

Scope:

- Add approval queue UI.
- Persist pending high-impact actions if existing tables can support it; otherwise propose a small migration.
- Show pending actions from chat and dashboard.

Verification:

- Queue shows pending apply/draft/reminder actions.
- Approve/reject updates state.
- Reload does not lose pending action if persistence is implemented.

### Phase 6 — Conversation-First App Shell

Scope:

- Make chat the default workspace for profile, settings, saved search, document analysis, and application workflows.
- Reduce sidebar prominence.
- Convert page navigation into contextual action cards and focused panels.
- Keep deep links and fallback pages until replacement flows are stable.

Verification:

- A new user can complete onboarding through chat without manually visiting settings.
- Existing users can update preferences through chat.
- A user can upload a non-CV screenshot/file and continue the workflow from chat.
- Main mobile workflow fits in the chat surface.
- Direct URLs still work for fallback/manual correction.

### Phase 7 — Progress Steps and Streaming-like UX

Scope:

- Render progress steps for search, upload analysis, and CV generation.
- Start with deterministic milestones.
- Later upgrade to event-driven progress if backend supports it.

Verification:

- Slow search/upload analysis shows visible progress/fallback.
- Timeout state gives recovery buttons.

### Phase 8 — Polish and Productization

Scope:

- Refined animations.
- Premium visual hierarchy.
- Empty-state suggestions.
- Command suggestion bar.
- Strong mobile presentation.

Verification:

- UI smoke on iPhone-sized viewport.
- No overlap with bottom nav/composer.
- Accessible keyboard/focus states.

## Initial UX Examples

### Job Search Result

```text
Rico found 7 HSE roles in Dubai.

Best match: HSE Manager — Dutco Group
Match: 87%

Recommended next step: tailor your CV before applying.

[View jobs] [Tailor CV] [Draft cover letter] [Save search]
```

### Apply Permission

```text
Rico wants to apply to HSE Manager — Dutco Group.

This will:
- Use your active CV
- Generate or attach a cover letter
- Save the application record
- Mark the job as applied

[Approve application] [Review first] [Cancel]
```

### Profile Completion

```text
Your profile is missing 4 items that affect match quality:
- Target role
- City
- Years of experience
- CV

[Complete profile] [Upload CV] [Skip for now]
```

### Settings Change Through Chat

```text
User: خلي بحثي على دبي والشارقة بس، والراتب أقل شي 15000.

Rico: I can update your search preferences.

Changes:
- Cities: Dubai, Sharjah
- Minimum salary: AED 15,000

[Save changes] [Edit] [Cancel]
```

### LinkedIn Screenshot Analysis

```text
User uploads screenshot from LinkedIn.

Rico: I found a comment on your Rico post.

Comment concern:
- The user thinks the market does not need another tool.
- They want a specialized AI entity for this career direction.

Recommended response:
Position Rico as a UAE-focused AI career entity, not a generic job board.

[Draft reply] [Save objection insight] [Create product task]
```

## Files Likely Involved Later

Backend candidates:

- `src/rico_chat_api.py`
- `src/api/routers/rico_chat.py`
- `src/services/chat_service.py`
- `src/agent/runtime.py`
- `src/api/routers/actions.py`
- `src/api/routers/settings.py`
- `src/api/routers/user.py`
- `src/rico_safety.py`
- `src/cv_parser.py`
- `src/repositories/*`

Frontend candidates:

- `apps/web/app/chat/page.tsx`
- `apps/web/app/command/page.tsx`
- `apps/web/app/profile/page.tsx`
- `apps/web/app/settings/page.tsx`
- `apps/web/lib/api.ts`
- `apps/web/components/*`
- `apps/web/hooks/*`
- `apps/web/components/layout/*`
- i18n/translation files used by the current app

Docs/workspace:

- `AI_WORKSPACE/TASKS.md`
- `AI_WORKSPACE/CURRENT_STATE.md`
- `AI_WORKSPACE/OPERATING_RULES.md`

## Risks

| Risk | Mitigation |
|---|---|
| Action buttons bypass backend safety | Server-side confirmation and `agent_runtime` boundary |
| UI becomes flashy but not useful | Start with job/profile/apply/upload flows only |
| Breaking existing chat responses | Add optional `agentic_ui`; keep old fields intact |
| Too much scope in one PR | Phase by contracts, low-impact actions, multimodal intake, high-impact permissions, queue |
| Arabic/English mismatch | Add i18n keys with every visible action label |
| Mobile composer overlap | Test mobile viewport before merge for UI phases |
| Removing pages too early breaks power users or recovery flows | Demote pages first; remove only after replacement flows are verified |
| Conversational settings mutate wrong data | Proposed-changes card, validation, and explicit save confirmation |
| Misclassifying uploaded files | Purpose classifier, confidence score, warnings, and clarifying questions |
| Sensitive documents over-retained or overused | Conservative retention, explicit consent, and purpose-limited processing |

## Non-goals for Phase 1

- No autonomous apply.
- No replacing the current chat engine.
- No new AI provider.
- No large redesign of the whole app.
- No deleting sidebar or existing pages in early phases.
- No persistent approval queue until a dedicated phase.
- No live third-party API calls in unit tests.
- No claiming legal review for contracts/offers; provide career-oriented observations only.

## Success Criteria

Rico should feel like an execution-capable assistant, not a text-only chatbot or a form-heavy dashboard.

The first visible win is:

- A user searches for jobs.
- Rico returns job results with polished inline actions.
- The user can click next steps instead of typing commands.
- Any high-impact action requires a clear approval card.

The second visible win is:

- A user can upload a screenshot or non-CV document.
- Rico classifies what it is.
- Rico extracts useful career context.
- Rico proposes the next action.
- Rico does not save/send/apply without approval.

The third visible win is:

- A user can update profile/settings/search preferences naturally through Rico.
- Rico summarizes the proposed changes.
- The user approves or cancels.
- Manual settings pages become fallback, not the primary workflow.
