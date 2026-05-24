# Chat Routing Contract

This document defines the expected Rico behavior for a representative set of user messages. It serves as the product specification for intent classification and workflow dispatch in `src/rico_chat_api.py`.

Use these examples to validate that chat responses are correct product behavior, not just plausible-sounding text.

---

## Contract Table

### "find live jobs for Environmental Compliance Officer"

**Intent:** `job_search`

**Expected Rico behavior:**
1. Call the jobs router with title query `Environmental Compliance Officer` and user's saved location/preferences.
2. Return a structured list of matching jobs with company, title, location, and match score.
3. Each job card should have actions: "Prepare application", "Save job", "Track this job", "Open apply link".

**Bad behavior:** Return a generic "I'm searching for jobs, please wait" without actually surfacing results. Return jobs in plain text with no actions attached.

---

### "save Environmental Manager as target role"

**Intent:** `profile_update` → `target_role`

**Expected Rico behavior:**
1. Call `POST /api/v1/user/profile` (or equivalent) to update `target_roles` with `Environmental Manager`.
2. Confirm: "I've saved Environmental Manager as a target role. I'll prioritize these jobs in your feed."
3. Optionally: "Do you want me to start a search now?"

**Bad behavior:** Acknowledge verbally without writing to the profile. Write to profile without confirming success. Ask the user to go to the profile page to update it themselves.

---

### "Prepare application — HSE Manager- Manufacturing at Renew"

**Intent:** `prepare_application`

**Context requirement:** The job card context (title: `HSE Manager- Manufacturing`, company: `Renew`) must be preserved from the job card that triggered this action. If the action was triggered from a job card, the job key must accompany the request.

**Expected Rico behavior:**
1. Retrieve job details (title, company, apply URL, job description if available).
2. Compare against user's CV/profile.
3. Return an application angle containing:
   - Match reasoning (what in the user's background aligns).
   - CV gaps or missing facts worth addressing in the cover note.
   - Suggested CV/application angle (1–2 sentences).
4. Actions offered:
   - "Open apply link" — opens the job's apply URL.
   - "Track this job" — creates/updates an application record with status `tracking`.
   - "Mark as applied" — updates application record to status `applied`.
   - "Save job" — adds to saved jobs list.

**Bad behavior:**
- Route this intent to Application Flow and show "You have no tracked applications yet."
- Return a generic application tips response without the specific job context.
- Lose the job title/company and respond as if this is a general application advice request.

---

### "how can i apply?"

**Intent:** `apply_guidance` (context-dependent)

**If a job is currently selected or was most recently discussed:**
1. Show the apply link for that specific job.
2. Offer: "Track this job", "Mark as applied after you submit".

**If no job context exists:**
1. Rico explains the application flow: find a job → click "Open apply link" → mark as applied → Rico tracks it.
2. Offer: "Search for jobs" → triggers job search.

**Bad behavior:** Show a generic help text about how applications work without checking for a current job context.

---

### "why don't you have my past applications?"

**Intent:** `application_tracking_explanation`

**Expected Rico behavior:**

> I automatically track applications opened through Rico job cards. For older or external applications, you have two options:
>
> - **Connect Gmail** — I'll scan your inbox for application confirmation emails, recruiter replies, and job portal messages, then show them for your review before adding anything.
> - **Add past application manually** — tell me the company and role and I'll record it now.
>
> Once your applications are in Rico, I can track statuses, remind you to follow up, and show you the full picture in Application Flow.

Actions offered:
- "Connect Gmail" (disabled / "coming next" until inbox import is live)
- "Import from inbox" (disabled / "coming next" until inbox import is live)
- "Add past application manually"
- "Open Application Flow"

**Bad behavior:**
- Tell the user to use a spreadsheet.
- Say "I can't access your email or job portals" with no further path forward.
- Pretend inbox import is available when it is not yet implemented.

---

## Routing Rules Summary

| User message pattern | Intent | Dispatcher target |
|---|---|---|
| "find jobs for X" / "search for X" | `job_search` | jobs router |
| "save X as target role" / "add X to my roles" | `profile_update` | user/profile router |
| "Prepare application — {title} at {company}" | `prepare_application` | jobs router + CV/profile context |
| "how can i apply?" | `apply_guidance` | jobs router (with context check) |
| "why don't you have my past applications?" | `application_tracking_explanation` | inline response + action panel |
| "track this job" / "mark as applied" | `application_action` | applications router |
| "upgrade to Pro" / "tell me about plans" | `subscription_info` | route to `/subscription` |
| "connect my email" / "import from inbox" | `inbox_import` | email import pipeline (or honest "coming next") |

---

## Context Preservation Rule

When a job card action (Prepare application, Track this job, Mark as applied, Open apply link) is triggered, the front end **must** pass the job context (`job_key`, `title`, `company`) in the chat payload. Rico's response must reference that specific job, not a generic response.

This is a required pending implementation. The frontend must pass job_context in the chat payload and Rico must use it for intent classification and response generation.

---

## Known Gaps / Next PRs

1. **Job action context fix** — front end must include `job_context` in chat payload when triggered from a job card; Rico must use it.
2. **"Prepare application" routing** — must not route to empty Application Flow; must produce match reasoning.
3. **Inbox import honest state** — "Connect Gmail" must show disabled/"coming next" until OAuth is live.
4. **`application_tracking_explanation` intent** — verify this intent class exists in `rico_chat_api.py` classification.
