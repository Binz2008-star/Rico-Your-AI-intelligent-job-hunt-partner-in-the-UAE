# Rico Agentic Conversational UX

> A Perplexity-inspired AI career agent workspace for the UAE job market.

## Vision

Rico is not a chatbot. It is not a dashboard. It is an intelligent career agent that:

1. **Understands** what you are trying to accomplish
2. **Explains** its reasoning transparently
3. **Proposes** actions as reviewable cards before executing anything
4. **Executes** only with explicit user approval
5. **Logs** every action as an immutable audit trail

The interface should feel alive, adaptive, and trustworthy — not like a form wizard or an admin panel.

---

## Core UX Loop

```
User asks → Rico understands → Rico answers with cards →
Rico explains why → Rico suggests next action →
User approves → Rico executes safely → Rico logs result
```

Every step is visible. Nothing happens silently.

---

## Interaction Model

### Empty State — Question First

When the user arrives, they see a single centered ask box. No clutter, no dashboard widgets, no sidebar dominating the view.

- Large, focused input ("What would you like to work on?")
- 4–6 suggested prompt chips below the input
- Rico status indicator (idle: soft pulse)
- No message history visible yet

**Philosophy:** Force the question first. The interface is built around asking, not browsing.

### Thinking State

After the user submits a question:

- The input slides gracefully to the bottom (anchored, stays visible)
- A thinking card appears at the top with Rico's status dot (animated)
- Text: "Rico is analyzing your question…"
- Estimated time appears after 2s if response is slow

### Answer State — Structured Cards

Rico's answer is displayed as a structured card, not a chat bubble.

Each answer card has:

| Zone | Content |
|------|---------|
| **Header** | What Rico understood + risk class badge |
| **Body** | Structured answer (job cards, advice, analysis) |
| **Reasoning strip** | "Why I suggested this" — transparent, collapsible |
| **Action bar** | Contextual action buttons relevant to this answer |

### Progressive Disclosure

- Only actions relevant to the current answer appear
- After a user acts on an option, that option disappears
- Completed actions are replaced by a receipt card ("Applied", "Saved", "Sent")
- Old answers scroll up as new answers appear below

### Action Chips (Contextual)

After a job recommendation, Rico shows:

```
[ Prepare application ]  [ Save for later ]  [ Explain match ]  [ Skip ]
```

After a career advice answer:

```
[ Explore related roles ]  [ Update profile ]  [ Find matching jobs ]
```

After a profile gap analysis:

```
[ Fix this gap ]  [ Ask how ]  [ See all gaps ]
```

Chips are never the same between different answer types. They are always contextually generated.

---

## Answer Card Schema

```typescript
interface AgenticAnswerCard {
  id: string;
  type: AnswerType;
  title: string;
  summary: string;           // 1-2 sentence answer summary
  reasoning: string;         // why Rico suggests this (transparency)
  risk_class: RiskClass;     // safe | low | medium | high | critical
  reversible: boolean;
  external_systems: string[]; // [] for internal-only answers
  items: AnswerItem[];        // job cards, advice points, profile gaps, etc.
  actions: ContextualAction[];
  created_at: string;
  correlation_id: string;     // links to audit log
}

type AnswerType =
  | "job_recommendation"
  | "career_advice"
  | "profile_analysis"
  | "application_status"
  | "action_complete"
  | "approval_required";

type RiskClass = "safe" | "low" | "medium" | "high" | "critical";

interface ContextualAction {
  id: string;
  label: string;
  icon: string;                 // material icon name
  kind: ActionKind;
  risk_class: RiskClass;
  requires_approval: boolean;
  idempotency_key: string;      // prevents double execution
  payload?: Record<string, unknown>;
}

type ActionKind =
  | "chat_continue"   // sends a follow-up message
  | "navigate"        // client-side navigation
  | "approve"         // high-impact gate: requires approval card
  | "dismiss";        // removes this card from view
```

---

## Approval Gate UX

### When Approval is Required

Any action with `risk_class >= medium` or `requires_approval: true` triggers the approval gate:

**Desktop:**  A full-width approval banner slides in above the action bar:
```
┌─────────────────────────────────────────────────────────┐
│ ⚠ Rico wants to prepare a draft application             │
│ for Senior HSE Manager at ADNOC Group                   │
│                                                         │
│ This will:                                              │
│  • Create a draft cover letter                          │
│  • Pre-fill the application form                        │
│  • NOT submit anything externally                       │
│                                                         │
│  [ Review draft ]   [ Approve & continue ]   [ Cancel ] │
│                                                         │
│ Token expires in  4:45  ────────────────────            │
└─────────────────────────────────────────────────────────┘
```

**Mobile:**  A bottom sheet slides up from the screen bottom (gesture-dismissible):
- Drag handle at top
- Same content as desktop but in single-column layout
- Primary CTA fills the full width
- Cancel is a text link above the CTA

### Approval Token

Each approval request issues a time-limited token:

```typescript
interface ApprovalToken {
  token_id: string;           // UUID
  hmac_signature: string;     // HMAC-SHA256, secret from env
  user_id: string;
  card_id: string;
  idempotency_key: string;
  risk_class: RiskClass;
  permission_level: PermissionLevel;
  expires_at: string;         // ISO-8601, default TTL: 5 minutes
}

type PermissionLevel = "read" | "write" | "external" | "irreversible";
```

**Token validation rules (enforced server-side):**
1. Valid HMAC-SHA256 signature
2. Not expired (`expires_at > now()`)
3. Not already used (`used_at IS NULL`)
4. Not invalidated (`invalidated = false`)
5. `user_id` matches authenticated session
6. `card_id` matches the card being acted on
7. `idempotency_key` matches the pending action
8. `risk_class` is allowed by the user's permission tier

### Countdown Timer

The approval card shows a live countdown. At 0:

- The approval button disables
- The card shows: "This approval has expired. Request again."
- A new token is issued if the user clicks "Request again"

---

## Rico Status Indicator

A small animated node shows Rico's current state in the top-left of the interface:

| State | Visual | Label |
|-------|--------|-------|
| `idle` | Soft gold pulse, slow | "Rico ready" |
| `thinking` | Rotating arc, faster | "Rico is thinking…" |
| `responding` | Streaming dots | "Rico is writing…" |
| `acting` | Amber pulse | "Rico is working…" |
| `waiting` | Static dot | "Waiting for your approval" |
| `error` | Red pulse | "Something went wrong" |

The status never shows internal error messages — only human-readable states.

---

## Mobile-First Layout

### Breakpoints

| Breakpoint | Layout |
|------------|--------|
| < 640px | Single column, full-width input, bottom sheet approvals |
| 640–1024px | Centered column (max-w-2xl), floating input |
| > 1024px | Centered column (max-w-3xl), persistent sidebar optional |

### Mobile Patterns

- **Input:** Always visible at bottom, expands upward when focused
- **Answers:** Full-width cards, vertically stacked
- **Action chips:** Horizontally scrollable, show 2 chips + overflow indicator
- **Approvals:** Bottom sheet, not modal (can be dismissed by swipe)
- **Long answers:** Collapse to summary by default, expand on tap

### Touch Targets

All interactive elements ≥ 44×44px (Apple HIG minimum).

---

## Example Flows

### 1. Job Recommendation (safe — no approval)

```
User: "Find me HSE jobs in Abu Dhabi"

Rico [answer card]:
  Title: "Found 3 matches for HSE roles in Abu Dhabi"
  Risk: safe  |  No approval needed

  ┌─ Job Card 1 ──────────────────────────────────────────┐
  │ Senior HSE Manager · ADNOC Group · Abu Dhabi           │
  │ Match: 94%  ·  AED 28,000–32,000/mo  ·  Posted 2d ago │
  │ Why: Your 8yr HSE background matches 6/7 requirements  │
  └───────────────────────────────────────────────────────┘

  Reasoning: "Your CV lists ISO 45001 certification and 8 years
  of HSE experience. This role specifically requires both."

  Actions:
  [ Prepare application ]  [ Save for later ]  [ Explain match ]  [ Skip ]
```

### 2. Prepare Application (low — draft only, no external)

```
User clicks: [ Prepare application ]

Rico [approval card]:
  "Rico will draft an application for you"
  Risk: low  ·  Creates a draft only  ·  Nothing sent externally

  [ Review draft ]  [ Approve draft ]  [ Cancel ]

After approval:
  Rico shows the draft cover letter
  Actions: [ Send application ]  [ Edit ]  [ Save draft ]
```

### 3. Mark Applied (medium — database write)

```
User clicks: [ Send application ]

Rico [approval card]:
  "Mark application as submitted?"
  Risk: medium  ·  Records this in your tracker

  Before state:  Status: draft
  After state:   Status: applied · Date: today

  [ Confirm ]  [ Cancel ]

After confirmation:
  Receipt card: "✓ Application recorded · ADNOC Group · HSE Manager"
  Action buttons disappear, replaced by:
  [ Set follow-up reminder ]  [ View all applications ]
```

### 4. Send Follow-up Email (high — external commit)

```
User: "Send a follow-up email to ADNOC for my application"

Rico [answer card]:
  Risk: high  ·  ⚠ This will send an email externally

  Preview of email shown
  To: recruiter@adnoc.ae
  Subject: Following up — HSE Manager Application

  [ Review full email ]

Rico [approval card — prominent warning]:
  "This will send an email to a real recipient"
  Reversible: NO — once sent, cannot be recalled

  [ Send email ]  [ Edit first ]  [ Cancel ]
```

### 5. Profile Update (medium — internal write with diff)

```
User: "Update my experience to include my recent ISO 45001 renewal"

Rico [proposed change card]:
  Before: "ISO 45001:2018 certified (2019)"
  After:  "ISO 45001:2018 certified (2019, renewed 2025)"

  Risk: medium  ·  Updates your profile only

  [ Apply change ]  [ Edit ]  [ Dismiss ]

After approval:
  Receipt card: "✓ Profile updated · Experience section"
```

---

## Audit Trail

Every action generates an immutable audit event. Rico can answer:

- "Why did you suggest this job?" → `action_created` event + reasoning field
- "Who approved this?" → `approval_granted` event + user_id
- "What changed?" → `before_state` / `after_state` JSONB diff
- "Was anything sent externally?" → `external_systems` field
- "Can this be undone?" → `reversible` + `undo_window_sec`

Users can see their own audit trail in Settings > Activity Log.

---

## Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Question first** | Empty state = single centered ask box |
| **Transparent** | Every answer includes "why I suggest this" |
| **Progressive disclosure** | Options appear only when relevant |
| **Stateful** | Interface remembers where you are in a flow |
| **Mobile first** | Layout designed for 390px, scaled up |
| **Trust by design** | Risk level always visible, approval always explicit |
| **Agentic, not chatty** | Answers are structured cards, not paragraphs |
| **Alive** | Status indicator, smooth transitions, framer-motion |

---

## Implementation Phases

| Phase | Branch | Scope |
|-------|--------|-------|
| **Phase 0** (complete) | `docs/agentic-ux-contract` | Spec and contract |
| **Phase 1** (this PR) | `feat/agentic-conversational-ux` | UI shell with mock data |
| **Phase 2** | `feat/agent-audit-policy-gate` | Audit log + approval token backend |
| **Phase 3** | TBD | Wire Phase 1 UI to Phase 2 backend |
| **Phase 4** | TBD | Real job recommendations via backend |
