# Application Tracking

Rico tracks job applications across three sources. Each source produces a record in `Application Flow` with a distinct `source` label.

## Three Application Sources

### 1. Rico job cards (source: `rico`)

When a user opens a job's apply link through a Rico job card or clicks "Mark as applied" on a Rico job card, Rico creates or updates an application record automatically.

Required fields captured at apply time:
- `job_key` — internal Rico job identifier
- `title` — job title
- `company` — company name
- `apply_url` — direct application URL
- `source` — `rico`
- `status` — `applied`
- `applied_at` — timestamp

No user action needed beyond the apply/track click.

### 2. Manual past application entry (source: `manual`)

User explicitly adds a past application Rico does not know about.

Entry points:
- Chat: "Add past application" intent detected → Rico asks for company, role, date, and optional notes.
- UI: "Add past application" button in Application Flow page or the chat action panel.

Required fields:
- `title`
- `company`
- `applied_at` (approximate is acceptable)
- `source` — `manual`
- `status` — defaults to `applied` unless user specifies

**Implementation status: not yet implemented.** The backend endpoint and frontend form are pending. See Known Gaps.

### 3. Inbox / email import (source: `email_import`)

User connects their Gmail (or other inbox) with explicit OAuth permission. Rico scans only job/application-related messages.

Full design is in the Inbox Import section below.

---

## Inbox Import Pipeline

### Prerequisites

- User must explicitly trigger "Connect Gmail" and complete the OAuth flow.
- Rico must not access the inbox without this explicit user action.
- The OAuth access token must never be logged, displayed, or exposed to the frontend beyond the redirect callback.

### Scan scope

Rico scans only messages that match job/application patterns:

- Subject lines containing: application received, application confirmation, your application, we received your application, interview invitation, assessment, offer letter, unfortunately, moved forward, next steps, recruiter.
- Senders from known job portal domains (LinkedIn, Bayt, Naukrigulf, GulfTalent, Indeed, Glassdoor, Greenhouse, Lever, Workday, SmartRecruiters, etc.).

Do not scan all email. Do not store full message body unless a snippet alone is insufficient for extraction.

### Extraction targets

For each matched message, extract:

| Field | Source |
|---|---|
| `company` | sender domain, subject, or body snippet |
| `title` / `role` | subject or body snippet |
| `applied_at` | email received date |
| `source_platform` | inferred from sender domain |
| `status` | `applied`, `recruiter_reply`, `interview`, `assessment`, `rejected`, `offer`, `unknown` |
| `thread_id` | email thread reference (do not store message body beyond the snippet) |
| `snippet` | ≤ 280 chars from subject + opening line |

### Review screen

Before writing any records to the database, present the user with a review screen:

- List of detected applications with company, role, date, inferred status.
- User can select/deselect individual records.
- "Import selected" writes approved records to Application Flow.
- "Cancel" discards everything; no records written.

### Post-import

- Approved records appear in Application Flow with `source = email_import`.
- Duplicate detection: if an application with matching `company + title + applied_at` (within ±3 days) already exists, skip or prompt user.
- Status updates from later emails in the same thread (recruiter reply, interview, rejection) should update the existing record, not create a duplicate.

### Privacy rules

- Do not store full email body.
- Store `snippet` (≤ 280 chars) and `thread_id` only.
- Do not expose OAuth tokens or refresh tokens to the frontend.
- Revoke inbox access if user disconnects Gmail from settings.
- Do not re-scan the inbox on a schedule without a user-triggered or user-consented recurring import.

**Implementation status: not yet implemented.** OAuth flow, scan backend, and review screen are all pending. See Known Gaps.

---

## Rico Chat — Application Tracking Responses

### When user asks "why don't you have my past applications?"

Rico must respond with the three-source explanation:

> I automatically track applications opened through Rico job cards. For older or external applications, you have two options:
>
> - **Connect Gmail** — I'll scan your inbox for application confirmation emails, recruiter replies, and job portal messages, then show them for your review before adding anything.
> - **Add past application manually** — tell me the company and role and I'll record it now.
>
> Once your applications are in Rico, I can track statuses, remind you to follow up, and show you the full picture in Application Flow.

Rico must not suggest using a spreadsheet as the primary tracking solution.

### Current honest state

Until inbox import is live, Rico should tell the user:

> Inbox import is coming soon. For now, I can automatically track jobs you apply to through Rico, and you can also add past applications manually.

Show "Connect Gmail" as disabled or labelled "coming next" rather than as a broken live feature.

---

## Application Flow UI Actions

| Action | Label | Behavior |
|---|---|---|
| Open Rico jobs | "Open Application Flow" | Navigate to `/applications` |
| Add manually | "Add past application manually" | Open add-application form/chat flow |
| Connect inbox | "Connect Gmail" | Begin OAuth flow (disabled until implemented) |
| Import from inbox | "Import from inbox" | Trigger scan + review screen (disabled until implemented) |

---

## Known Gaps / Next PRs

1. **Manual application entry** — backend `POST /api/v1/applications` (manual) + frontend form.
2. **Inbox import** — Gmail OAuth, scan service, extraction, review screen, dedup logic.
3. **Status update from thread** — follow-on email in same thread updates existing record status.
4. **"Connect Gmail" UI state** — show disabled/"coming next" until OAuth is live; never show as a broken live feature.
