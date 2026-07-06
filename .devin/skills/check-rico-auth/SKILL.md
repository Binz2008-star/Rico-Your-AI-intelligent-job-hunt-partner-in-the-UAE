---
name: check-rico-auth
description: Verify Rico Hunt authentication rules. Check JWT cookie usage, signup role enforcement, protected route isolation, and no request body user_id.
triggers:
  - user
  - model
allowed-tools:
  - read
  - grep
  - exec
---

# check-rico-auth

Verify Rico Hunt authentication rules. This skill is **read-only** and inspects code plus environment to confirm auth safety.

## What it verifies

1. Signup always forces `role="user"` and never creates admin accounts from public request body.
2. Protected routes derive identity from JWT cookie, not from request body `user_id`.
3. JWT is stored in an `httpOnly` cookie with correct secure settings.
4. `GET /api/v1/me` returns the current user.
5. Logout clears the JWT cookie.
6. `tests/test_jwt_user_isolation.py` passes.

## Quick checks

```bash
# Signup forces role=user
grep -n "role=\"user\"\|role=\"admin\"\|request.role" src/api/auth.py

# Protected routes use get_current_user from deps
grep -n "get_current_user\|current_user:" src/api/routers/*.py src/api/deps.py

# No request-body user_id for identity
grep -n "user_id" src/api/routers/*.py | grep -v "get_current_user"

# JWT cookie config
grep -n "httpOnly\|secure\|samesite\|JWT_TTL_HOURS\|JWT_SECRET" src/api/auth.py src/api/deps.py
```

## Run the auth test

```bash
python -m pytest tests/test_jwt_user_isolation.py -q
```

## Files to read

- `src/api/auth.py` — register, login, logout, forgot/reset password, `/me`
- `src/api/deps.py` — `get_current_user`, JWT dependencies
- `src/api/admin_guard.py` — admin route guard
- `tests/test_jwt_user_isolation.py` — auth isolation tests

## Safety constraints

- Do not create admin accounts in tests.
- Do not bypass `get_current_user()` by reading `user_id` from request bodies.
- Do not expose JWT secrets or test user credentials.
