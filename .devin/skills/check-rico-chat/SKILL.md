---
name: check-rico-chat
description: Verify Rico Hunt chat flow. Inspect public chat session isolation, rate limits, authenticated chat routing, and public session prefixing.
triggers:
  - user
  - model
allowed-tools:
  - read
  - grep
  - exec
---

# check-rico-chat

Verify Rico Hunt chat flow. This skill is **read-only** and does not send abusive traffic. It may call the local public chat endpoint with a synthetic session ID for a smoke check.

## What it verifies

1. Public chat endpoint (`POST /api/v1/rico/chat/public`) is rate-limited and unauthenticated.
2. Public sessions are prefixed as public so they cannot collide with real JWT-authenticated users.
3. Authenticated chat uses `POST /api/v1/rico/chat` with JWT cookie.
4. `session_id` must be ≥ 8 characters (returns 422 otherwise).
5. Public chat falls back to templated responses when no AI provider keys are present (correct dev behavior).

## Quick checks

```bash
# Public vs authenticated routes
grep -n "chat/public\|def chat_public\|def chat" src/api/routers/rico_chat.py src/services/chat_service.py

# Public session prefixing
grep -n "public_\|anonymous\|session_id" src/api/routers/rico_chat.py src/services/chat_service.py

# Rate limiting
grep -n "rate_limit\|Limiter\|@limit" src/api/routers/rico_chat.py src/api/rate_limit.py

# Chat frontend entry
grep -n "sendChatPublic\|sendChat\|/api/v1/rico/chat" apps/web/lib/api.ts apps/web/app/command/page.tsx
```

## Local smoke check

If the backend is running on port 8000:

```bash
curl -X POST http://localhost:8000/api/v1/rico/chat/public \
  -H "Content-Type: application/json" \
  -d '{"message":"What jobs are available?","session_id":"smoke-session-001"}'
```

Expected: 200 OK with `response_source: "fallback"` when no AI keys are present.

## Files to read

- `src/api/routers/rico_chat.py` — chat routes
- `src/services/chat_service.py` — chat business logic
- `apps/web/lib/api.ts` — frontend API helper
- `apps/web/app/command/page.tsx` — public chat UI

## Safety constraints

- Do not use short `session_id` values (< 8 chars) in tests.
- Do not flood the chat endpoint with many requests.
- Do not impersonate real users or authenticated sessions in public chat tests.
