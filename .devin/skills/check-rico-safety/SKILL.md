---
name: check-rico-safety
description: Audit Rico Hunt safety guardrails — rico_safety.py, agent runtime approval mode, and high-impact action protections. Read-only verification.
triggers:
  - user
  - model
allowed-tools:
  - read
  - grep
  - exec
---

# check-rico-safety

Audit Rico Hunt safety guardrails. This skill is **read-only** and verifies that the production safety rules are in place and not bypassed.

## What to verify

1. `src/rico_safety.py` is imported and used by action paths.
2. `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true` is the default.
3. `agent_runtime.handle_action()` is the only entry point for apply/save/skip/block/draft/why/remind.
4. No router or tool calls `applications_repo`, `jobs_repo`, or `user_repo` directly for actions.
5. Public chat sessions are prefixed as public and cannot collide with real users.
6. Admin routes use `admin_guard` and do not derive identity from request body `user_id`.

## Files to read

- `src/rico_safety.py` — guardrail functions
- `src/agent/runtime.py` — action dispatcher, approval mode, idempotency
- `src/api/routers/actions.py` — how actions are exposed
- `src/api/routers/agent.py` — natural-language chat actions
- `src/api/routers/rico_chat.py` — public chat prefixing
- `src/api/admin_guard.py` — admin route protection
- `src/api/auth.py` — signup forces `role="user"`

## Quick checks

```bash
# Confirm approval constant is enforced
grep -R "RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS" src/

# Confirm actions go through agent_runtime
grep -R "handle_action" src/api/routers/ src/agent/

# Confirm no direct repo mutation from routers
grep -R "applications_repo\.\|jobs_repo\.\|user_repo\." src/api/routers/

# Confirm public chat prefixing
grep -R "public_\|anonymous" src/api/routers/rico_chat.py src/services/chat_service.py
```

## Report format

For each check, report:
- **Status**: OK / WARNING / FAIL
- **Evidence**: file path and line number
- **Risk**: what could go wrong if bypassed

## Safety constraints

- Do not modify `src/rico_safety.py`, `src/agent/runtime.py`, or any guardrail code as part of this audit.
- If a bypass is found, report it immediately and ask for approval before proposing a fix.
