# Rico Agentic UI Action Layer — Architecture Plan

## Objective

Move Rico from a text-only chatbot experience to a modern agentic career assistant UI where Rico can present contextual actions, permission prompts, progress states, and approval queues inside the chat and related product surfaces.

The goal is to make Rico feel like a current AI product: guided, proactive, permission-aware, and execution-oriented, without sacrificing safety or user control.

## Product Principle

Rico should not only answer. Rico should propose the next safe action, explain what will happen, and ask for approval before high-impact work.

```text
User intent -> Rico interpretation -> suggested action -> user approval -> execution -> audit trail
```

The long-term product direction is conversation-first: the chat becomes the primary control surface, and traditional pages become supporting views that Rico can open, explain, and prefill through conversation.

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
- `Open application queue`

Action cards are low or medium impact. They may navigate, open a drawer, submit a safe action, or continue the chat with structured payload.

### 2. Permission Prompts

Explicit confirmation cards for high-impact actions.

Examples:

- Apply to a job.
- Send a cover letter or email.
- Save profile changes.
- Replace the active CV.
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
Searching jobs
✓ Reading profile
✓ Searching UAE roles
✓ Filtering by fit
• Ranking matches
```

Progress can be optimistic in Phase 1 and event-driven later.

### 4. Approval Queue

A centralized list of pending high-impact actions.

Examples:

- Apply to HSE Manager at Dutco Group — waiting approval.
- Draft cover letter for voco Dubai Monaco — ready to review.
- Create saved search for QHSE Manager in Dubai — waiting approval.
- Improve CV for compliance roles — draft ready.

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
    source: Literal["chat", "cv", "system", "user_action"]


class RicoAgenticUi(BaseModel):
    actions: list[RicoChatAction] = Field(default_factory=list)
    permission_request: RicoPermissionRequest | None = None
    progress: list[RicoProgressStep] = Field(default_factory=list)
    proposed_changes: list[RicoProposedChange] = Field(default_factory=list)
```

Then existing chat responses can include:

```python
{
    "message": "I found 5 strong HSE roles in Dubai.",
    "type": "job_results",
    "agentic_ui": {
        "actions": [...],
        "permission_request": None,
        "progress": [...],
        "proposed_changes": [...]
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
```

Expected rendering surfaces:

- Chat message footer for action cards.
- Message-level permission prompt for high-impact actions.
- Search/result messages for progress steps.
- Dashboard/sidebar/global drawer for approval queue.
- Empty states and profile banners for suggested commands.
- Proposed changes card for profile/settings/search preference updates.
- Focused drawer/panel for visual review when chat alone is not enough.

## Navigation Strategy

The target is not “no pages”; the target is “no forced manual pages.”

### Keep initially

- `/command` or main Rico chat surface.
- `/dashboard` as a status overview until chat can replace most dashboard tasks.
- `/jobs` as a visual results/review surface.
- `/applications` or approval queue view until queue is embedded well.
- `/profile` and `/settings` as fallback/manual correction surfaces.

### Demote over time

- Sidebar becomes status + quick access, not the main workflow.
- Common actions move into chat action cards.
- Profile/settings pages become “advanced/manual edit” rather than required onboarding.
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
- Enable recurring cron-like behavior.

Rules:

1. Backend labels the action impact.
2. Frontend renders a permission prompt for high-impact actions.
3. Execution endpoint checks confirmation server-side.
4. Existing `agent_runtime.handle_action()` remains the execution boundary for job actions.
5. Existing `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true` remains mandatory.
6. Every approval/rejection should be auditable.
7. Profile/settings mutations must show a proposed-changes summary before saving.

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
  - Upload CV
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

### Phase 2 — Conversational Profile and Settings Review Cards

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

### Phase 3 — Permission Prompt for Apply and Profile Mutation

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

### Phase 4 — Approval Queue

Scope:

- Add approval queue UI.
- Persist pending high-impact actions if existing tables can support it; otherwise propose a small migration.
- Show pending actions from chat and dashboard.

Verification:

- Queue shows pending apply/draft/reminder actions.
- Approve/reject updates state.
- Reload does not lose pending action if persistence is implemented.

### Phase 5 — Conversation-First App Shell

Scope:

- Make chat the default workspace for profile, settings, saved search, and application workflows.
- Reduce sidebar prominence.
- Convert page navigation into contextual action cards and focused panels.
- Keep deep links and fallback pages until replacement flows are stable.

Verification:

- A new user can complete onboarding through chat without manually visiting settings.
- Existing users can update preferences through chat.
- Main mobile workflow fits in the chat surface.
- Direct URLs still work for fallback/manual correction.

### Phase 6 — Progress Steps and Streaming-like UX

Scope:

- Render progress steps for search and CV generation.
- Start with deterministic milestones.
- Later upgrade to event-driven progress if backend supports it.

Verification:

- Slow search shows visible progress/fallback.
- Timeout state gives recovery buttons.

### Phase 7 — Polish and Productization

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
| UI becomes flashy but not useful | Start with job/profile/apply flows only |
| Breaking existing chat responses | Add optional `agentic_ui`; keep old fields intact |
| Too much scope in one PR | Phase by contracts, low-impact actions, high-impact permissions, queue |
| Arabic/English mismatch | Add i18n keys with every visible action label |
| Mobile composer overlap | Test mobile viewport before merge for UI phases |
| Removing pages too early breaks power users or recovery flows | Demote pages first; remove only after replacement flows are verified |
| Conversational settings mutate wrong data | Proposed-changes card, validation, and explicit save confirmation |

## Non-goals for Phase 1

- No autonomous apply.
- No replacing the current chat engine.
- No new AI provider.
- No large redesign of the whole app.
- No deleting sidebar or existing pages in early phases.
- No persistent approval queue until a dedicated phase.
- No live third-party API calls in unit tests.

## Success Criteria

Rico should feel like an execution-capable assistant, not a text-only chatbot or a form-heavy dashboard.

The first visible win is:

- A user searches for jobs.
- Rico returns job results with polished inline actions.
- The user can click next steps instead of typing commands.
- Any high-impact action requires a clear approval card.

The second visible win is:

- A user can update profile/settings/search preferences naturally through Rico.
- Rico summarizes the proposed changes.
- The user approves or cancels.
- Manual settings pages become fallback, not the primary workflow.
