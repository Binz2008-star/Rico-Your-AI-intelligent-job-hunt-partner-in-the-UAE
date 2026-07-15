# ADR-002 — Command multi-session conversation history

- **Status: PROPOSED — requires separate owner approval. Do NOT implement
  inside PR #1043 or any C1–C6 design slice.**
- Date: 2026-07-16
- Context owner: Command Obsidian program
  (`design-handoffs/reviewed/2026-07-16-command-obsidian-v4/`)

## Context

The canonical `/rico` recording shows a Sessions rail listing multiple past
conversations. Repository evidence confirms Rico production has exactly one
conversation per user: `GET /api/v1/rico/chat/history` (read, limit-paged) and
`DELETE /api/v1/rico/chat/history` (clear). There are no list/create/select/
rename/delete session APIs and no session dimension in storage. C1 therefore
ships a truthful single-conversation rail; the multi-session experience is a
**backend capability gap**, not a styling task. Fabricating session lists is
prohibited.

## Proposal (when approved)

### Data model (Neon)

- `chat_sessions` table: `id` (uuid pk), `user_id` (fk, indexed),
  `title` (text, derived from first user turn; renameable), `created_at`,
  `updated_at`, `archived_at` (nullable).
- `chat_messages` gains `session_id` (fk → `chat_sessions.id`, indexed).
  Existing rows: see migration.
- Per-user isolation: every query keyed by the JWT-derived `user_id`
  (existing `deps.py` pattern); session ids are unguessable uuids and always
  ownership-checked. Public/guest sessions stay out of scope (localStorage
  mirror remains their only history, unchanged).

### APIs (FastAPI, `src/api/routers/rico_chat.py` or a new `sessions.py`)

- `GET    /api/v1/rico/chat/sessions` — list (id, title, updated_at, message_count)
- `POST   /api/v1/rico/chat/sessions` — create (becomes the active session)
- `GET    /api/v1/rico/chat/sessions/{id}/history` — paged messages
- `PATCH  /api/v1/rico/chat/sessions/{id}` — rename / archive
- `DELETE /api/v1/rico/chat/sessions/{id}` — delete one session
- Existing `GET/DELETE /api/v1/rico/chat/history` remain as aliases for the
  **latest active session** (backward compatibility for current clients);
  chat send endpoints accept an optional `session_id`, defaulting to the
  active session.

### Migration

- Migration NNN (Neon, expand–contract): create `chat_sessions`; backfill one
  session per user owning existing history rows; add nullable `session_id`,
  backfill, then enforce NOT NULL. No destructive change to existing rows;
  reversible by dropping the new column/table (rollback below).

### Frontend

- `CommandConversationRail` swaps its single-conversation body for the real
  session list (same truthful loading/error/empty states already shipped);
  select/rename/delete wired to the new APIs; `+ new` switches from local
  reset to `POST /sessions` when available (feature-detected, so the UI works
  against both old and new backends during rollout).

### Tests

- Backend: session CRUD + isolation (user A cannot read/rename/delete user
  B's sessions), alias behavior of the legacy history endpoints, migration
  backfill unit test with synthetic rows.
- Frontend: rail list/select/rename/delete against network fixtures; C1
  no-regression suite must keep passing unchanged.

### Rollback plan

- Feature-flag the new endpoints (`RICO_ENABLE_CHAT_SESSIONS`, default off).
- Frontend feature-detects; flag off ⇒ exact current single-conversation
  behavior. DB rollback: legacy endpoints never stop reading the active
  session, so reverting the frontend or disabling the flag restores today's
  UX without data loss; the migration is reversible (drop column/table) if
  abandoned before GA.

## Consequences

Until approved and shipped, the Sessions rail remains single-conversation and
every design slice must keep stating that limitation honestly.
