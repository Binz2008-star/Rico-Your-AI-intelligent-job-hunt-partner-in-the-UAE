# Rico Agentic UI Action Layer — Architecture Plan

## Objective

Move Rico from a text-only chatbot experience to a modern agentic career assistant UI where Rico can present contextual actions, permission prompts, progress states, and approval queues inside the chat and related product surfaces.

The goal is to make Rico feel like a current AI product: guided, proactive, permission-aware, and execution-oriented, without sacrificing safety or user control.

## Product Principle

Rico should not only answer. Rico should propose the next safe action, explain what will happen, and ask for approval before high-impact work.

```text
User intent -> Rico interpretation -> suggested action -> user approval -> execution -> audit trail
```

## Design Targets

- Modern AI command experience comparable to current agentic products.
- Clear user control before apply/send/mutate actions.
- No hidden automation for high-impact actions.
- Fast, clickable flows instead of typed A/B/C/D replies.
- Mobile-first cards and buttons.
- Arabic and English support from the first implementation.
- Backward-compatible API response shape where possible.

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


class RicoAgenticUi(BaseModel):
    actions: list[RicoChatAction] = Field(default_factory=list)
    permission_request: RicoPermissionRequest | None = None
    progress: list[RicoProgressStep] = Field(default_factory=list)
```

Then existing chat responses can include:

```python
{
    "message": "I found 5 strong HSE roles in Dubai.",
    "type": "job_results",
    "agentic_ui": {
        "actions": [...],
        "permission_request": None,
        "progress": [...]
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
```

Expected rendering surfaces:

- Chat message footer for action cards.
- Message-level permission prompt for high-impact actions.
- Search/result messages for progress steps.
- Dashboard/sidebar/global drawer for approval queue.
- Empty states and profile banners for suggested commands.

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

## Phase Plan

### Phase 0 — Architecture and contracts

Scope:

- Add this architecture plan.
- Add task ledger entry.
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

### Phase 2 — Permission Prompt for Apply and Profile Mutation

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

### Phase 3 — Approval Queue

Scope:

- Add approval queue UI.
- Persist pending high-impact actions if existing tables can support it; otherwise propose a small migration.
- Show pending actions from chat and dashboard.

Verification:

- Queue shows pending apply/draft/reminder actions.
- Approve/reject updates state.
- Reload does not lose pending action if persistence is implemented.

### Phase 4 — Progress Steps and Streaming-like UX

Scope:

- Render progress steps for search and CV generation.
- Start with deterministic milestones.
- Later upgrade to event-driven progress if backend supports it.

Verification:

- Slow search shows visible progress/fallback.
- Timeout state gives recovery buttons.

### Phase 5 — Polish and Productization

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

## Files Likely Involved Later

Backend candidates:

- `src/rico_chat_api.py`
- `src/api/routers/rico_chat.py`
- `src/services/chat_service.py`
- `src/agent/runtime.py`
- `src/api/routers/actions.py`
- `src/rico_safety.py`
- `src/repositories/*`

Frontend candidates:

- `apps/web/app/chat/page.tsx`
- `apps/web/app/command/page.tsx`
- `apps/web/lib/api.ts`
- `apps/web/components/*`
- `apps/web/hooks/*`
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

## Non-goals for Phase 1

- No autonomous apply.
- No replacing the current chat engine.
- No new AI provider.
- No large redesign of the whole app.
- No persistent approval queue until a dedicated phase.
- No live third-party API calls in unit tests.

## Success Criteria

Rico should feel like an execution-capable assistant, not a text-only chatbot.

The first visible win is:

- A user searches for jobs.
- Rico returns job results with polished inline actions.
- The user can click next steps instead of typing commands.
- Any high-impact action requires a clear approval card.
