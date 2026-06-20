# Rico Agentic UX Contract

**Status:** Spec / Review — not yet implemented  
**Branch:** `docs/agentic-ux-contract`  
**Scope:** UX contract only. No backend execution. No DB changes. No auth, billing, job search, CV parsing, or application lifecycle.  
**Next PR:** `agent_audit_log` migration + backend audit writer + policy gate endpoint.

---

## Operating Model

Rico operates in **semi-autonomous mode** by default.

```
User intent
    │
    ▼
Rico plans → produces Action Card(s)
    │
    ▼
User reviews → Approves / Rejects / Edits
    │
    ▼
Backend executes (after approval token issued)
    │
    ▼
Receipt published → Audit event written
```

Rico **never executes a side-effecting action without explicit per-action user approval.**  
This is non-negotiable and extends the existing `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true` flag into a full contract.

---

## 1. Action Card Schema

Every action Rico proposes is represented as a typed Action Card. This is the single source of truth between Rico's planning layer and the frontend approval UI.

```typescript
interface ActionCard {
  // Identity
  card_id: string;               // UUID, unique per proposal
  idempotency_key: string;       // UUID, used for safe backend execution

  // Intent
  action_type: ActionType;       // see enum below
  intent_summary: string;        // human-readable: "Apply to Senior PM at Noon"
  why_now: string;               // Rico's reason: "Matches 4 of your top 5 skills"

  // Risk classification
  risk_class: RiskClass;         // safe | low | medium | high | critical
  reversible: boolean;           // can this be undone?
  undo_deadline_seconds?: number; // if reversible, how long the window is

  // Scope
  target: ActionTarget;          // what entity/resource is affected
  data_used: string[];           // ["cv_v3.pdf", "job_id:abc123", "user.email"]
  external_systems: string[];    // ["email_provider", "applicant_portal"] — empty if none

  // Approval state
  requires_approval: boolean;    // always true for risk_class >= low
  approval_state: ApprovalState; // pending | approved | rejected | expired
  approval_expires_at?: string;  // ISO 8601 — card expires if not acted on

  // Display
  expected_effect: string;       // "Your application will be submitted to Noon's portal"
  diff?: ActionDiff;             // before/after for profile updates or edits

  // Audit
  audit_ref?: string;            // populated after execution, links to audit event
  created_at: string;            // ISO 8601
}

type ActionType =
  | "job_recommendation"
  | "prepare_application"
  | "mark_applied"
  | "send_followup_email"
  | "update_profile";

type RiskClass = "safe" | "low" | "medium" | "high" | "critical";

type ApprovalState = "pending" | "approved" | "rejected" | "expired";

interface ActionTarget {
  entity_type: "job" | "application" | "email" | "profile" | "document";
  entity_id: string;
  label: string;        // human-readable: "Senior PM — Noon (Dubai)"
  url?: string;         // link to the entity if applicable
}

interface ActionDiff {
  field: string;
  before: string;
  after: string;
}
```

---

## 2. Permission Levels

Rico's permissions are **capability-scoped**, not integration-scoped. The user grants what Rico can *do*, not which system it connects to.

### Permission Tiers

| Level | Name | What Rico can do | Requires re-approval? |
|---|---|---|---|
| `P0` | Read-only | View jobs, read profile, generate suggestions | Never — silent |
| `P1` | Draft | Create drafts (cover letters, emails, notes) | Never — shows result |
| `P2` | Internal write | Mark applied, update profile fields, save to wishlist | Per-action confirmation |
| `P3` | External commit | Send emails, submit applications, contact recruiters | **Always** — explicit approval + audit |
| `P4` | Bulk external | Batch apply, bulk email, automated campaigns | **Disabled** in current version |

### Permission Rules

- Default permission on new account: **P0 only**.
- User explicitly grants P1–P3 in Settings → Rico Permissions.
- Each permission tier shows: what Rico will do, which external systems are involved, how to revoke.
- **P4 is locked** — not available until trust tier system is implemented.
- Revoking a permission tier immediately blocks all pending cards of that tier.
- No permission upgrade is silent — every grant/revoke is shown in the audit timeline.

### Risk Class ↔ Permission Tier Mapping

| Risk Class | Minimum Permission Required | Default Approval Behavior |
|---|---|---|
| `safe` | P0 | Auto — no user action needed |
| `low` | P1 | Shown in feed, dismiss to reject |
| `medium` | P2 | Inline confirmation required |
| `high` | P3 | Bottom sheet approval + explicit tap |
| `critical` | P3 | Bottom sheet + typed confirmation |

---

## 3. Approval Gate Behavior

### Desktop

1. Rico produces an Action Card.
2. Card appears in the **Rico Action Feed** (right panel or inline in chat).
3. Card shows: intent summary, why now, expected effect, risk badge, target, data used.
4. Primary CTA: **"Approve"** — secondary: **"Edit"** / **"Reject"**.
5. Approving issues a **short-lived signed approval token** (TTL: 5 minutes).
6. Token is sent with the execution request to the backend.
7. Backend validates token before executing — rejects if expired or mismatched.
8. After execution: card transitions to **Receipt state** with audit ref.

### Mobile (Bottom Sheet)

On mobile, all `medium`, `high`, and `critical` approvals use a **bottom sheet** — never a modal or full-page.

Bottom sheet anatomy:

```
┌─────────────────────────────────┐
│  ▔▔▔  (drag handle)             │
│                                 │
│  [Risk badge]  Action title     │
│  Why Rico is suggesting this    │
│                                 │
│  ─────────────────────────────  │
│  What will happen:              │
│  > "Application sent to Noon"   │
│  > "Using: cv_v3.pdf"           │
│  > "Sends to: careers@noon.com" │
│                                 │
│  Reversible: No                 │
│  External system: Email         │
│                                 │
│  ─────────────────────────────  │
│                                 │
│  [       Approve       ]  ← primary, full width, 52px height  │
│  [  Edit  ]  [  Reject  ]  ← secondary row, 44px height       │
│                                 │
└─────────────────────────────────┘
```

Rules:
- Bottom sheet slides up from bottom — never appears as a popup over content.
- Backdrop dims main content (opacity 0.4) but does not block scroll.
- Drag to dismiss = reject (with undo toast: "Dismissed — Undo").
- One action card per bottom sheet — no batching on mobile.
- Primary CTA is always a single tap — no swipe-to-confirm or double-tap.
- `critical` risk cards show a text field: "Type CONFIRM to proceed" before enabling Approve.

### Approval Token Contract

```typescript
interface ApprovalToken {
  card_id: string;
  user_id: string;
  action_type: ActionType;
  idempotency_key: string;
  risk_class: RiskClass;
  issued_at: string;   // ISO 8601
  expires_at: string;  // ISO 8601 — TTL: 5 minutes
  signature: string;   // HMAC-SHA256 signed server-side
}
```

The backend policy gate must:
1. Verify signature.
2. Verify `expires_at` is in the future.
3. Verify `user_id` matches the authenticated session.
4. Verify `card_id` has not been previously executed (idempotency).
5. Verify `risk_class` matches the user's current permission tier.
6. Only then: execute the action and write the audit event.

---

## 4. Audit Event Model

Every action card that reaches `approved` or `rejected` state produces an immutable audit event.

```typescript
interface AuditEvent {
  event_id: string;           // UUID
  user_id: string;
  card_id: string;
  action_type: ActionType;
  intent_summary: string;
  risk_class: RiskClass;
  approval_state: "approved" | "rejected" | "expired";
  policy_decision: string;    // "user_approved" | "user_rejected" | "policy_blocked" | "token_expired"
  target: ActionTarget;
  data_used: string[];
  external_systems: string[];
  expected_effect: string;
  actual_effect?: string;      // populated after execution
  undo_used?: boolean;
  error?: string;              // if execution failed
  created_at: string;          // ISO 8601, immutable
}
```

### Audit Timeline UI

- Every user has an **Activity** tab showing their audit timeline.
- Timeline entries are human-readable: "Rico applied to Senior PM at Noon — You approved — Jun 21, 2026 01:12 AM".
- Expandable: shows full `AuditEvent` JSON for power users.
- Filter by: action type, date, approval state, external system.
- Undo actions (where `reversible: true`) show an **Undo** button within the deadline window.
- No audit event is ever deleted or edited — append-only.

---

## 5. Mobile Bottom-Sheet Approval UX — Detailed Spec

### States

| State | Visual | User action |
|---|---|---|
| `pending` | Card in feed with pulsing teal dot | Tap to open bottom sheet |
| `sheet_open` | Bottom sheet slides up, backdrop dims | Approve / Edit / Reject |
| `approved` | Card turns green, checkmark animates in | None — auto-closes sheet |
| `rejected` | Card grays out, fades | None — dismiss |
| `expired` | Card shows "Expired" badge, faded | Tap to ask Rico to re-propose |
| `receipt` | Card shows audit ref, expandable | Tap to view full audit event |

### Gestures

- **Tap card** → open bottom sheet.
- **Swipe down on sheet** → reject (with undo toast, 4s window).
- **Swipe up** → expand to show full data_used + external_systems detail.
- **Long press Approve** → not used — single tap is sufficient with clear consequence display.

### Accessibility

- Bottom sheet has `role="dialog"`, `aria-modal="true"`, `aria-labelledby` pointing to the action title.
- Focus traps inside the sheet when open.
- Dismiss via `Escape` on keyboard (desktop).
- Minimum touch target: 44×44px for all buttons.
- Risk badge colors are never the only indicator — always paired with text label.

---

## 6. Worked Examples

### Example 1 — Job Recommendation

```json
{
  "card_id": "card_01jwx5k",
  "idempotency_key": "idem_01jwx5k",
  "action_type": "job_recommendation",
  "intent_summary": "Senior Product Manager — Noon (Dubai)",
  "why_now": "Matches 4 of your 5 target skills: product strategy, agile, Arabic, e-commerce. Posted 2 hours ago.",
  "risk_class": "safe",
  "reversible": true,
  "target": {
    "entity_type": "job",
    "entity_id": "job_noon_spm_01",
    "label": "Senior PM — Noon (Dubai)",
    "url": "https://noon.jobs/spm-01"
  },
  "data_used": ["user.skills", "user.target_roles", "user.location_preference"],
  "external_systems": [],
  "requires_approval": false,
  "approval_state": "approved",
  "expected_effect": "Job saved to your wishlist for review.",
  "created_at": "2026-06-21T01:05:00Z"
}
```

**UX behavior:** Appears inline in Rico's chat as a job card. No approval sheet — `safe` risk. Tap "Save" to wishlist or "Ignore". No backend write until Save is tapped.

---

### Example 2 — Prepare Application

```json
{
  "card_id": "card_01jwx6m",
  "idempotency_key": "idem_01jwx6m",
  "action_type": "prepare_application",
  "intent_summary": "Draft cover letter for Senior PM — Noon",
  "why_now": "You saved this job 10 minutes ago. Deadline is in 3 days.",
  "risk_class": "low",
  "reversible": true,
  "target": {
    "entity_type": "document",
    "entity_id": "draft_cl_noon_01",
    "label": "Cover letter draft — Noon Senior PM"
  },
  "data_used": ["cv_v3.pdf", "job_noon_spm_01", "user.tone_preference"],
  "external_systems": [],
  "requires_approval": false,
  "approval_state": "approved",
  "expected_effect": "A draft cover letter is created in your Documents. Nothing is sent.",
  "created_at": "2026-06-21T01:15:00Z"
}
```

**UX behavior:** Rico shows the draft inline. User can edit before doing anything with it. No sheet — `low` risk, internal write only.

---

### Example 3 — Mark Applied

```json
{
  "card_id": "card_01jwx7p",
  "idempotency_key": "idem_01jwx7p",
  "action_type": "mark_applied",
  "intent_summary": "Mark Senior PM — Noon as Applied",
  "why_now": "You opened the application portal link 3 times today.",
  "risk_class": "medium",
  "reversible": true,
  "undo_deadline_seconds": 300,
  "target": {
    "entity_type": "application",
    "entity_id": "app_noon_spm_01",
    "label": "Senior PM — Noon (Dubai)"
  },
  "data_used": ["app_noon_spm_01", "user.application_tracker"],
  "external_systems": [],
  "requires_approval": true,
  "approval_state": "pending",
  "expected_effect": "Application status updated to 'Applied' in your tracker. No external action.",
  "created_at": "2026-06-21T01:22:00Z"
}
```

**UX behavior:** Inline confirmation banner — "Mark as Applied?" with Confirm / Not yet. No bottom sheet (internal write, medium risk). Shows undo option for 5 minutes after confirmation.

---

### Example 4 — Follow-up Email

```json
{
  "card_id": "card_01jwx8r",
  "idempotency_key": "idem_01jwx8r",
  "action_type": "send_followup_email",
  "intent_summary": "Send follow-up to Noon recruiter — Sarah Al Mansoori",
  "why_now": "7 days since application. No response. Industry norm is 5–10 days.",
  "risk_class": "high",
  "reversible": false,
  "target": {
    "entity_type": "email",
    "entity_id": "email_draft_followup_01",
    "label": "Follow-up to Sarah Al Mansoori — sarah@noon.com"
  },
  "data_used": ["app_noon_spm_01", "user.name", "draft_cl_noon_01"],
  "external_systems": ["email_provider"],
  "requires_approval": true,
  "approval_state": "pending",
  "approval_expires_at": "2026-06-21T01:27:00Z",
  "expected_effect": "One email sent to sarah@noon.com from your connected address. Cannot be recalled.",
  "created_at": "2026-06-21T01:22:00Z"
}
```

**UX behavior:** Bottom sheet on mobile. Shows: recipient, subject preview, first 2 lines of body, "Sends from: your.email@gmail.com", "Cannot be undone." Approve CTA is full-width. 5-minute approval expiry shown as countdown.

---

### Example 5 — Profile Update

```json
{
  "card_id": "card_01jwx9t",
  "idempotency_key": "idem_01jwx9t",
  "action_type": "update_profile",
  "intent_summary": "Add 'Agile / Scrum' to your skills",
  "why_now": "Appears in 12 of your last 15 saved jobs. Not currently in your profile.",
  "risk_class": "medium",
  "reversible": true,
  "undo_deadline_seconds": 600,
  "target": {
    "entity_type": "profile",
    "entity_id": "user.skills",
    "label": "Skills section"
  },
  "data_used": ["user.skills", "user.saved_jobs[last_15]"],
  "external_systems": [],
  "requires_approval": true,
  "approval_state": "pending",
  "expected_effect": "'Agile / Scrum' added to your profile skills. Affects future job matching.",
  "diff": {
    "field": "skills",
    "before": "Product Strategy, Arabic, E-commerce, Data Analysis",
    "after": "Product Strategy, Arabic, E-commerce, Data Analysis, Agile / Scrum"
  },
  "created_at": "2026-06-21T01:30:00Z"
}
```

**UX behavior:** Inline diff card showing before/after. "Add skill" CTA. No bottom sheet — `medium` risk, internal write, reversible. 10-minute undo window shown after approval.

---

## What This Spec Does NOT Cover

The following are explicitly out of scope for this PR. They require separate PRs after this spec is reviewed:

- `agent_audit_log` table migration (SQL).
- Backend audit writer service.
- Policy gate endpoint implementation.
- Approval token issuance and verification logic.
- Permission settings UI implementation.
- Rico's planning layer changes.
- Auth, billing, job search, CV parsing, or application lifecycle changes.

---

## Next PR Checklist (after this spec is approved)

- [ ] `migrations/YYYYMMDD_add_agent_audit_log.sql`
- [ ] `src/services/audit_writer.py` — writes `AuditEvent` after every execution
- [ ] `src/api/policy_gate.py` — validates `ApprovalToken` before any `high`/`critical` action
- [ ] Unit tests for token validation, expiry, and idempotency
- [ ] Integration test: approve → execute → audit event written

---

*Spec authored: 2026-06-21. Review before implementation.*
