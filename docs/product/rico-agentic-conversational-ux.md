# Rico Agentic Conversational UX — Product Spec

**Version:** 1.0.0-draft  
**Author:** Roben Edwan  
**Status:** RFC — Awaiting review  
**Branch:** `feature/rico-agentic-conversational-ux`

---

## 1. Vision

Rico moves from a traditional dashboard to an **Agentic Conversational Workspace**.

The user doesn't navigate menus — they ask Rico a question.  
Rico understands intent, proposes an action plan, explains why, and waits for approval before executing anything meaningful.

> "Not a chatbot. Not a dashboard. A career agent you can trust."

---

## 2. Core UX Loop

```
User asks → Rico understands → Rico responds with structured cards
→ Rico explains reasoning → Rico proposes next actions
→ User approves → Rico executes safely → Rico logs the receipt
```

Every step is visible, legible, and reversible where possible.

---

## 3. Design Principles

| Principle | Implementation |
|---|---|
| **Question-first** | Large ask box is the primary UI element, always visible |
| **Progressive disclosure** | Options appear only when relevant; disappear after user acts |
| **Trust by design** | Every proposed action shows: what, why, which system, risk level |
| **Human-in-the-loop** | No execution without explicit approval (semi-autonomous mode) |
| **Contextual actions** | Action chips appear per-card, not globally |
| **Adaptive interface** | UI state evolves based on conversation context |
| **Mobile-first** | Thumb-reachable primary actions, bottom sheet approvals |
| **Minimal clutter** | One primary action per view; secondary actions on demand |

---

## 4. Component Architecture

### 4.1 Ask Box (Command Input)
- Full-width prominent input, always visible
- Placeholder rotates with contextual suggestions
- Voice input hook (future)
- Keyboard shortcut: `⌘K` / `Ctrl+K`

### 4.2 Suggested Prompt Chips
- 4–6 chips rendered below the ask box
- Context-aware: change based on current app state and conversation history
- Disappear when user starts typing; reappear when input is cleared
- Examples: "What jobs match my CV?", "Why wasn't I shortlisted?", "Improve my headline"

### 4.3 Answer Cards
- Structured response containers, not raw chat bubbles
- Each card has: `type`, `title`, `body`, `data` (optional), `actions`, `audit_ref`
- Card types: `insight`, `action_proposal`, `result`, `warning`, `receipt`
- Cards slide in with smooth enter animation
- Old cards fade/collapse when superseded

### 4.4 Contextual Action Buttons
- Rendered inside each card, not in a global toolbar
- Max 2 primary actions per card; secondary actions in overflow
- Risk-tiered: `safe` (auto-highlight), `moderate` (confirm), `destructive` (double-confirm)
- After approval: button transforms into status indicator, not a new screen

### 4.5 Rico Status Indicator
- Persistent, minimal — top of the conversation panel
- States: `idle`, `thinking`, `proposing`, `waiting_approval`, `executing`, `done`, `needs_attention`
- Animated dot + label; not intrusive

### 4.6 Approval Flow (Human-in-the-loop)
- Triggered on any `action_proposal` card
- Bottom sheet on mobile, inline expansion on desktop
- Shows: action summary, affected systems, risk class, undo availability
- Two buttons only: `Approve` and `Edit / Reject`
- On approval: emits structured `approval_record` (future backend contract)

---

## 5. Information Architecture

```
rico-agentic-workspace/
├── AskBox                    ← primary entry point
├── SuggestedPromptChips      ← contextual shortcuts
├── ConversationThread        ← stateful card stream
│   ├── InsightCard
│   ├── ActionProposalCard    ← triggers approval flow
│   ├── ResultCard
│   ├── ReceiptCard
│   └── WarningCard
├── RicoStatusBar             ← persistent status
├── ApprovalSheet             ← bottom sheet / inline
└── AuditDrawer               ← expandable history
```

---

## 6. Data Contracts (UI Layer)

### Message / Card Object
```typescript
interface RicoCard {
  id: string;
  type: 'insight' | 'action_proposal' | 'result' | 'receipt' | 'warning';
  title: string;
  body: string;
  reasoning?: string;          // why Rico is proposing this
  data?: Record<string, unknown>;
  actions: RicoAction[];
  risk_class: 'safe' | 'moderate' | 'destructive';
  undo_available: boolean;
  audit_ref?: string;
  created_at: string;
  status: 'pending' | 'approved' | 'rejected' | 'executed' | 'superseded';
}

interface RicoAction {
  id: string;
  label: string;
  variant: 'primary' | 'secondary' | 'ghost' | 'danger';
  risk_class: 'safe' | 'moderate' | 'destructive';
  requires_approval: boolean;
  target_system?: string;
  expected_effect?: string;
}
```

### Approval Record (emitted on approval)
```typescript
interface ApprovalRecord {
  action_id: string;
  actor_user_id: string;
  card_id: string;
  approved_at: string;
  risk_class: string;
  target_system: string;
  expected_effect: string;
  undo_available: boolean;
  idempotency_key: string;
}
```

---

## 7. Interaction States

| State | Rico shows | User can do |
|---|---|---|
| `idle` | Ask box + prompt chips | Type question |
| `thinking` | Status bar: "Thinking…" + shimmer | Wait or cancel |
| `proposing` | Action proposal card | Approve, Edit, Reject |
| `waiting_approval` | Approval sheet open | Approve or dismiss |
| `executing` | Execution progress in card | Watch; cancel if reversible |
| `done` | Receipt card | Ask follow-up |
| `needs_attention` | Warning card + retry action | Resolve or dismiss |

---

## 8. What This PR Excludes (Explicitly)

- No real autonomous execution
- No email sending
- No backend job logic changes
- No auth, billing, CV parsing changes
- No changes to `target_roles` or `applications` lifecycle
- No `localStorage` / `sessionStorage`

All data in this PR is mock/read-only. This PR proves the **interaction model**, not the automation power.

---

## 9. Success Criteria for This PR

- [ ] Ask box renders and accepts input
- [ ] Prompt chips appear and populate the ask box on click
- [ ] Rico "thinking" state is animated and legible
- [ ] At least 3 card types render correctly (insight, action_proposal, receipt)
- [ ] Approval flow is interactive (approve → card transforms)
- [ ] Status bar updates correctly across all states
- [ ] Full mobile layout at 375px — no overflow, no tiny tap targets
- [ ] Dark mode works correctly
- [ ] No layout shift on card entry animation
- [ ] Keyboard accessible (Tab, Enter, Escape)

---

## 10. Future Roadmap (Post This PR)

1. Connect ask box to real Rico AI backend
2. Implement policy gate for approval records
3. Add audit drawer with real event log
4. Add voice input to ask box
5. Add `⌘K` command palette as secondary entry point
6. Add permission matrix UI (scope management)
7. Implement contestability: Pause, Edit, Undo flows
