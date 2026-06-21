# Handoff: System Quality Audit — 2026-06-21

**Branch:** `claude/system-quality-audit-ikkamf`
**PR:** #717 (draft — CI green, awaiting merge)
**Commit:** `3c11717`
**CI status:** pytest ✅ playwright ✅ Vercel ✅ Neon ✅ (all 6 checks)

---

## Summary

Full-sweep codebase audit covering auth, DB layer, repositories, services, migrations,
and routers. Three production bugs fixed with tests; six larger issues documented for
separate PRs.

---

## Bugs fixed

### 1. `list_active_users()` missing `email_verified` column
**File:** `src/repositories/users_repo.py`

**Root cause:** The SELECT query in `list_active_users()` fetched 7 columns
(`id, email, password_hash, role, is_active, created_at, last_login_at`) but the `User`
dataclass has an 8th field `email_verified` (default `True`). Every returned User object
silently had `email_verified=True` regardless of what the database stored.

**Impact:** Any feature consuming `email_verified` from `list_active_users()` — including
the multi-user scheduler and admin subscription routes — would skip email-verification
checks silently.

**Fix:** Added `COALESCE(email_verified, TRUE)` as column index 7 to the SELECT and
updated the dataclass constructor call to read `email_verified=row[7]`.

---

### 2. `audit_repo.py` missing `List` import (typing NameError)
**File:** `src/repositories/audit_repo.py`

**Root cause:** `log_profile_hydration(hydration_sources: List[str], ...)` and
`_db_write_profile_hydration(hydration_sources: List[str], ...)` use `List` in their
type annotations. `List` was not in the `from typing import …` line. With
`from __future__ import annotations` (lazy evaluation), the module imports without
error — but any call to `typing.get_type_hints()` on these functions raises `NameError`.

**Fix:** Added `List` to `from typing import Any, Dict, List, Optional, Tuple`.

---

### 3. Duplicate `delete_cookie()` in `register()`
**File:** `src/api/auth.py`

**Root cause:** `register()` called `response.delete_cookie(settings.COOKIE_NAME, ...)` twice:
once at the normal login-after-register path (~line 482) and again with a comment
"Clear any existing session cookie before setting new one" (~line 580). The second call
was dead code — identical arguments, same cookie name, executed after the new JWT cookie
was already set.

**Impact:** None in practice (deleting a cookie that was just set and then re-set is a
no-op), but the dead code created confusion and the comment implied a safety intent that
wasn't needed.

**Fix:** Removed the second `delete_cookie()` call and its comment.

---

### 4. Test fixture rows updated for 8-column SELECT
**File:** `tests/test_users_scheduler.py`

**Root cause:** `TestListActiveUsersStub.test_list_active_users_returns_user_objects`
patched `list_active_users()` with 7-element mock rows. After fix #1 above added access to
`row[7]`, these rows caused `IndexError: tuple index out of range`.

**Fix:** Updated both mock rows from `(1, ..., None, None)` to `(1, ..., None, None, True)`.

---

## Issues documented (separate PRs required)

### D1 — Runtime DDL bypasses migration system
**File:** `src/repositories/audit_repo.py`
**Functions:** `_db_write_learning_signal`, `_db_write_profile_hydration`, `_db_write_permission_check`

Each function checks `SELECT EXISTS(... table_name = '<name>')` and issues
`CREATE TABLE IF NOT EXISTS` when the table is absent. This creates three tables
(`learning_signals_audit`, `profile_hydration_audit`, `permission_check_audit`) outside
the Neon migration ledger. Evidence: `migrations/025_learning_signals.sql` creates
`learning_signals` (not `learning_signals_audit`) — the audit table is completely untracked.

**Risk:** Schema drift, DDL blocking hot path, tables invisible to migration tooling.

**Recommended fix:** Write migrations 031/032/033 for these three tables; remove the
runtime `CREATE TABLE` blocks. Separate PR.

---

### D2 — `_DEDUP_CACHE` unbounded memory growth
**File:** `src/repositories/audit_repo.py`

`_DEDUP_CACHE: Dict[str, Tuple[float, str]]` accumulates entries on every `log_action()` call.
Stale entries are only evicted when `_mem_check_duplicate()` is called for the same
`action_id` and the TTL has expired. Under continuous action logging with varied
`action_id` values (MD5 hashes), entries accumulate without bound.

**Risk:** Memory leak in long-running workers.

**Recommended fix:** Add a periodic sweep (e.g. on `_mem_seed`, if `len(_DEDUP_CACHE) > 10000`,
evict all expired entries) or replace with `cachetools.TTLCache`. Separate PR.

---

### D3 — Safety pattern over-breadth
**File:** `src/rico_safety.py`

- `PRIVACY_RISK_PATTERNS` contains `r"password"` — matches "how do I reset my password?",
  "I forgot my password", etc.
- `HARASSMENT_OR_ILLEGAL_PATTERNS` contains `r"bypass"` — matches "bypass this section of
  my CV", "how to bypass the ATS system".

**Risk:** Legitimate user queries blocked, degraded UX, false safety signals.

**Recommended fix:** Narrow with word-boundary anchors and negative lookaheads; add a
regression test suite (`tests/test_safety_patterns.py`) with true-positive and
false-positive cases. Requires careful review — separate PR.

---

### D4 — No password complexity enforcement
**File:** `src/api/auth.py` (`register()`, `reset_password()`)

Registration and reset accept any non-empty password. A single-character password passes.

**Recommended fix:** Enforce minimum length (≥ 8 chars) and at least one non-alpha character
at the API boundary. Add a `_validate_password_strength()` helper. Separate PR.

---

### D5 — No JWT revocation after password reset
**File:** `src/api/auth.py`

After `reset_password()` succeeds, existing JWT sessions for the same user remain valid.
An attacker who obtained a session token before the reset can continue acting as the user.

**Recommended fix:** Track a per-user `jwt_family_id` (UUID, stored in DB, included in JWT
payload); increment it on password change. `get_current_user` rejects tokens whose
`jwt_family_id` does not match the current DB value. Separate PR.

---

### D6 — `mark_webhook_event_processed` type mismatch
**File:** `src/rico_db.py`

`mark_webhook_event_processed(event_id: str, user_id: Optional[str])` accepts any string
for `user_id`, but the `webhook_events` table column is a UUID FK referencing `users.id`.
Passing a non-UUID string silently fails the DB write with a `DataError` that is swallowed.

**Recommended fix:** Validate `user_id` is a valid UUID before the write, or change the
signature to `Optional[uuid.UUID]` and convert at the call site. Separate PR.

---

## Verification

```
pytest + playwright:  ✅ green (PR #717 CI run)
Vercel preview:       ✅ DEPLOYED (Vercel bot confirmed)
Neon branch:          ✅ created and verified
No DB migrations:     ✅ (zero schema changes in this PR)
No env changes:       ✅
```

## Changed files

- `src/repositories/users_repo.py` — `list_active_users()` SELECT + row mapping
- `src/repositories/audit_repo.py` — `List` added to typing import
- `src/api/auth.py` — duplicate `delete_cookie()` removed
- `tests/test_users_scheduler.py` — mock rows updated to 8-element tuples
- `AI_WORKSPACE/CURRENT_STATE.md` — audit section, carry-over backlog
- `AI_WORKSPACE/TASKS.md` — TASK-20260621-029
- `AI_WORKSPACE/START_HERE.md` — latest handoff pointer

## Rollback plan

Revert PR #717. No migrations, no Neon changes, no Render env changes — fully safe to revert.

## Open items for next session

1. Merge PR #717 (CI green, no review comments).
2. Pick one of D1–D6 to scope into a focused follow-up PR (D1 runtime DDL is highest risk).
3. TASK-013 Application Pipeline V1 (P1 product roadmap item) remains unstarted.
