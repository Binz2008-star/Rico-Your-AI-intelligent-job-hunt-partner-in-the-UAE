# Gmail Read-Only Connector Design

Status: proposal only. This document does not implement runtime code, database migrations, OAuth routes, settings UI, token storage, pipeline changes, or production database changes.

## 1. Current `src/gmail_importer.py` Audit

`src/gmail_importer.py` is an existing single-user Gmail import utility for job-application response intelligence. Its current behavior is:

- Uses the Gmail API with the read-only scope `https://www.googleapis.com/auth/gmail.readonly`.
- Authenticates through `_get_gmail_service()`, reading `credentials.json` and `token.json` from the repository root.
- Starts an installed-app desktop OAuth flow with `InstalledAppFlow.from_client_secrets_file(...).run_local_server(port=0)` when no valid token exists.
- Stores the refreshed OAuth credential back into root-level `token.json`.
- Searches Gmail with a broad inbox query for job-related terms such as application, interview, recruiter, offer, shortlisted, position, and unfortunately.
- Fetches message metadata and full payloads, deduplicating by Gmail thread ID.
- Extracts plain-text bodies recursively from Gmail MIME payloads.
- Extracts headers, links, sender/company hints, and a short body snippet.
- Classifies emails with deterministic keyword rules, not an LLM.
- Maps detected outcomes into statuses such as `applied`, `interview_scheduled`, `rejected`, and `offer_extended`.
- Filters obvious false positives from blocked senders and blocked subject patterns.
- Matches classified emails against existing tracked applications by company hint, links, and subject-title token overlap.
- Applies high-confidence matches through the legacy application update path.
- Queues medium-confidence or unmatched useful emails into `data/gmail_review_queue.json`.
- Exposes a CLI: `python -m src.gmail_importer --dry-run` and `python -m src.gmail_importer --apply`.
- Exposes `run_import(dry_run, lookback_days)` for the daily pipeline path to call.

The useful reusable parts are the Gmail query, message extraction, deterministic classification, matching heuristics, and import report shape. The production connector should preserve these parts where possible, but separate them from local single-user OAuth, local token files, and legacy application storage.

## 2. Current Limitations

The current importer is not a production SaaS connector.

- Local credentials: it requires root-level `credentials.json` and `token.json`.
- Single-user design: one server-side token represents one Gmail account, not the authenticated Rico user.
- Desktop OAuth flow: `run_local_server(port=0)` opens a local browser/callback and is designed for a developer machine.
- Not Render-ready: Render cannot rely on local interactive browser OAuth, local token files, or per-process mutable credential files.
- No per-user disconnect: there is no route that deletes a user's token or revokes Google access.
- No JWT user isolation: `run_import()` reads and writes through the legacy application path without a required `user_id`.
- No production audit trail: sync attempts, consent changes, token revocation, and imported message decisions are not persisted in a user-scoped audit table.
- Review queue is local JSON: queued Gmail review items are written to `data/gmail_review_queue.json`, not to a per-user database table.
- Status mapping needs normalization: current classifier emits `interview_scheduled` and `offer_extended`, while the SaaS application API uses statuses such as `interview` and `offer`.

## 3. Production Architecture

The production connector should be explicitly read-only and user-scoped.

### OAuth and Permissions

- Use a per-user OAuth web flow initiated from the authenticated settings page.
- Derive Rico identity exclusively from the existing JWT-authenticated user context.
- Request only `https://www.googleapis.com/auth/gmail.readonly`.
- Do not request Gmail send, delete, label modification, mailbox settings, compose, or full mail modification scopes.
- Use web OAuth redirect URIs registered for the Render backend domain.
- Store OAuth state server-side or in a signed short-lived state value so callback requests cannot be forged or attached to the wrong user.
- Store provider account email and granted scopes after callback so the UI can show what is connected.

### Token Storage

- Store one Gmail connection per Rico user.
- Store refresh tokens encrypted at rest.
- Fernet is a practical first choice because `cryptography` already exists in `requirements.txt`.
- Use a dedicated encryption key environment variable for token encryption, separate from `JWT_SECRET`.
- Never log raw access tokens, refresh tokens, authorization codes, or decrypted token payloads.
- Access tokens should be short-lived and recreated from the encrypted refresh token on demand.
- Token refresh failures should mark the connection as requiring re-authentication without deleting useful audit history.

### Disconnect and Revoke

- Provide a disconnect action that:
  - Deletes or tombstones the encrypted token record.
  - Calls Google's token revoke endpoint when a token is available.
  - Records an audit event for user-requested disconnect.
  - Leaves imported application history intact.
- The disconnect endpoint must be authenticated and must ignore request-body `user_id`.

### Sync Modes

- Manual sync:
  - User starts a read-only sync from settings or a future inbox intelligence surface.
  - The backend creates a sync run record.
  - The sync fetches only recent messages or messages after the last successful cursor.
  - Results are summarized for the user without exposing raw email bodies unnecessarily.

- Daily sync:
  - Disabled by default behind a new environment flag proposed during implementation planning.
  - Runs only for users with an active Gmail connection and an opt-in sync setting.
  - Uses rate limits and backoff so one user's mailbox does not block others.
  - Writes a sync run record for success, partial failure, or skipped states.

### Audit Logging

Audit events should cover:

- OAuth connect started.
- OAuth callback succeeded or failed.
- Token refresh succeeded or failed.
- Manual sync requested.
- Daily sync started and completed.
- Message classified.
- Application status update proposed or applied.
- Review item queued.
- User disconnected Gmail.
- Google token revoke succeeded or failed.

Audit logs must not include full email body text, OAuth tokens, auth codes, or secrets.

### Application and Inbox Intelligence Boundary

- Gmail data should not bypass existing application safety rules.
- High-confidence status updates can be proposed first, then later applied once product behavior is approved.
- Medium-confidence messages should go into a user-scoped review queue.
- Imported metadata should be minimal: Gmail message ID, thread ID, subject snippet, sender, date, classification, confidence, matched application, and decision.
- Raw bodies should not be stored unless there is a specific privacy-reviewed product requirement.

## 4. Proposed DB Tables Only

No migration should be added in this docs PR. The following tables are proposed for a future DB foundation PR.

### `gmail_connections`

Purpose: one current Gmail account connection per Rico user.

Proposed columns:

- `id UUID PRIMARY KEY`
- `user_id TEXT NOT NULL`
- `provider TEXT NOT NULL DEFAULT 'gmail'`
- `provider_account_email TEXT`
- `scopes TEXT[] NOT NULL`
- `encrypted_refresh_token TEXT NOT NULL`
- `token_encryption_key_version TEXT`
- `status TEXT NOT NULL DEFAULT 'active'`
- `last_connected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `last_refresh_at TIMESTAMPTZ`
- `last_sync_at TIMESTAMPTZ`
- `last_error TEXT`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

Suggested constraints and indexes:

- Unique active connection per `user_id, provider`.
- Index on `status`.
- Index on `last_sync_at`.

### `gmail_sync_runs`

Purpose: immutable record of manual and scheduled sync attempts.

Proposed columns:

- `id UUID PRIMARY KEY`
- `user_id TEXT NOT NULL`
- `connection_id UUID NOT NULL`
- `mode TEXT NOT NULL`
- `status TEXT NOT NULL`
- `started_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `finished_at TIMESTAMPTZ`
- `lookback_days INTEGER`
- `messages_fetched INTEGER DEFAULT 0`
- `messages_classified INTEGER DEFAULT 0`
- `messages_skipped INTEGER DEFAULT 0`
- `updates_applied INTEGER DEFAULT 0`
- `queued_for_review INTEGER DEFAULT 0`
- `error_code TEXT`
- `error_message TEXT`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

Suggested indexes:

- `user_id, started_at DESC`
- `connection_id, started_at DESC`
- `status`

### `gmail_review_items`

Purpose: user-scoped replacement for `data/gmail_review_queue.json`.

Proposed columns:

- `id UUID PRIMARY KEY`
- `user_id TEXT NOT NULL`
- `sync_run_id UUID`
- `gmail_message_id TEXT NOT NULL`
- `gmail_thread_id TEXT`
- `subject_snippet TEXT`
- `sender TEXT`
- `received_at TIMESTAMPTZ`
- `classified_status TEXT`
- `classification_confidence NUMERIC`
- `company_hint TEXT`
- `matched_job_id TEXT`
- `matched_company TEXT`
- `matched_title TEXT`
- `match_confidence NUMERIC`
- `match_reason TEXT`
- `proposed_status TEXT`
- `review_status TEXT NOT NULL DEFAULT 'pending'`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

Suggested constraints and indexes:

- Unique `user_id, gmail_message_id` to avoid duplicate review items.
- Index on `user_id, review_status, created_at DESC`.

### `gmail_audit_events`

Purpose: connector-specific audit trail without secrets.

Proposed columns:

- `id UUID PRIMARY KEY`
- `user_id TEXT NOT NULL`
- `connection_id UUID`
- `sync_run_id UUID`
- `event_type TEXT NOT NULL`
- `status TEXT NOT NULL`
- `metadata JSONB`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

Suggested indexes:

- `user_id, created_at DESC`
- `event_type, created_at DESC`

## 5. Proposed API Routes Only

No API routes should be implemented in this docs PR.

Proposed authenticated routes:

- `GET /api/v1/integrations/gmail/status`
  - Returns whether the current JWT user has an active Gmail connection, connected email, scopes, last sync time, and whether re-authentication is required.

- `GET /api/v1/integrations/gmail/connect`
  - Starts OAuth web flow for the current JWT user.
  - Returns or redirects to the Google authorization URL.
  - Requests `gmail.readonly` only.

- `GET /api/v1/integrations/gmail/callback`
  - Handles Google OAuth callback.
  - Validates state.
  - Exchanges code for tokens.
  - Stores encrypted refresh token.
  - Redirects back to settings with success or error state.

- `POST /api/v1/integrations/gmail/disconnect`
  - Revokes Google token when possible.
  - Removes or tombstones the user's encrypted refresh token.
  - Records audit event.

- `POST /api/v1/integrations/gmail/sync`
  - Starts a manual sync for the current JWT user.
  - Returns a sync run summary.
  - Does not accept request-body `user_id`.

- `GET /api/v1/integrations/gmail/sync-runs`
  - Lists recent sync attempts for the current JWT user.

- `GET /api/v1/integrations/gmail/review-items`
  - Lists pending review items for the current JWT user.

- `POST /api/v1/integrations/gmail/review-items/{id}/approve`
  - Future route to approve a proposed application status update.

- `POST /api/v1/integrations/gmail/review-items/{id}/dismiss`
  - Future route to dismiss a low-confidence item.

All routes must use existing JWT dependencies and must not accept a user identity from request body or query string.

## 6. Proposed Settings UI Only

No settings UI should be implemented in this docs PR.

Proposed settings page behavior:

- Add an "Email connections" or "Gmail read-only sync" section to `/settings`.
- Show connection state:
  - Not connected.
  - Connected as `<provider_account_email>`.
  - Needs re-authentication.
  - Last synced timestamp.
- Primary action when disconnected: "Connect Gmail".
- Primary action when connected: "Sync now".
- Secondary destructive action when connected: "Disconnect".
- Explain the permission plainly: Rico can read matching Gmail messages for application tracking, but cannot send, delete, label, archive, or modify email.
- Show that daily sync is opt-in and may be disabled until the production flag is enabled.
- Surface Google verification limitations if the app is still in testing mode.
- Avoid showing raw email contents in settings; link to a review queue or applications surface instead.

## 7. Google Restricted-Scope Verification and CASA Risk

`gmail.readonly` is a Google restricted scope. For public users on `ricohunt.com`, this creates product and compliance risk:

- Google OAuth app verification is required before broad public use.
- Restricted Gmail scopes can require a third-party security assessment, commonly referred to as CASA.
- Verification and assessment can take weeks.
- Security assessment can create recurring cost and annual renewal work.
- Before verification, Google testing mode is limited to configured test users.
- Public copy, privacy policy, data retention language, deletion behavior, and support contact information must align with the requested Gmail scope.
- The product should be ready to explain exactly what email data is read, why it is read, where it is stored, and how users revoke access.

This risk argues for building the connector behind internal/tester gates first, and for shipping lower-risk alternatives in parallel.

## 8. Alternatives

### Forwarding Alias

Give each user a unique inbound address such as `user-token@mail.ricohunt.com`. The user creates a Gmail filter that forwards job-related emails to that address.

Pros:

- No Google restricted-scope OAuth verification.
- Works across email providers.
- Easier user-level revocation by disabling the forwarding rule.

Cons:

- User setup is manual.
- Requires inbound email infrastructure and parsing.
- Forwarded content arrives in Rico, so privacy and retention still need clear handling.

### Microsoft Graph `Mail.Read`

Offer Outlook/Microsoft 365 connection through Microsoft Graph with `Mail.Read`.

Pros:

- Useful for many UAE corporate users.
- May be operationally easier for some business accounts.
- Similar architecture can reuse connection, sync run, review item, and audit tables.

Cons:

- Still requires OAuth consent and provider-specific review.
- Enterprise tenants can block user consent.
- Requires separate provider implementation and support path.

### Manual Email Import

Allow users to paste or upload individual job-response emails for classification.

Pros:

- No mailbox OAuth.
- Lowest compliance risk.
- Good validation step for classifier behavior before mailbox sync.

Cons:

- Manual workflow.
- Does not keep application status automatically fresh.
- Lower long-term product value than a real connector.

## 9. Phased Implementation Plan

### PR 1: DB/encryption foundation

- Add migrations for proposed Gmail connection, sync run, review item, and audit tables.
- Add token encryption/decryption utilities using Fernet.
- Add repository methods with tests using mocks or isolated test DB fixtures only.
- Do not add OAuth routes or UI in this PR.

### PR 2: OAuth connect/disconnect routes

- Add authenticated connect, callback, status, and disconnect routes.
- Implement Google OAuth web flow with `gmail.readonly` only.
- Store encrypted refresh tokens.
- Implement Google revoke on disconnect.
- Add audit logging for connect, callback, and disconnect.
- Use route tests with mocked Google token exchange and revoke calls.

### PR 3: settings UI

- Add settings page Gmail connection card.
- Add frontend API helpers and state handling.
- Show connect, sync now, disconnect, last sync, connected account, and re-auth required states.
- Do not add daily pipeline behavior.

### PR 4: manual sync

- Refactor reusable parts of `src/gmail_importer.py` so a per-user service can use the same classification and matching logic.
- Add manual sync endpoint for the current JWT user.
- Use encrypted refresh token to build Gmail credentials at request time.
- Write sync run summaries and review items.
- Keep writes conservative: queue proposals unless high-confidence auto-update behavior is explicitly approved.

### PR 5: daily sync

- Add scheduled sync support behind an environment flag defaulting off.
- Sync only connected users who opted in.
- Add rate limiting, backoff, partial failure handling, and per-user isolation.
- Record sync runs and audit events.
- Keep production rollout gated until Google verification status is clear.

### PR 6: applications/inbox intelligence integration

- Surface Gmail-derived status updates in `/applications`.
- Add user review actions for proposed updates.
- Add inbox intelligence summaries where useful.
- Connect approved outcomes to learning signals only after product behavior is reviewed.
- Add privacy-preserving retention and deletion behavior for review items.

## Explicit Non-Goals for This Docs PR

- No runtime code changes.
- No migrations.
- No OAuth routes.
- No settings UI.
- No token storage.
- No pipeline changes.
- No production DB changes.
- No changes to `src/gmail_importer.py`.
- No changes to `src/run_daily.py`.
- No auth runtime changes.
