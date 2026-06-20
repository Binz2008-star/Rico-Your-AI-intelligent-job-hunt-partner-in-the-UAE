# Session Handoff — 2026-06-20

## Session summary

Four PRs shipped and merged to main in sequence. All are now live in production.

| PR | Title | Status |
|---|---|---|
| #665 | Profile nudge synthetic guard | ✅ merged + live |
| #667 | render-audit.yml bug fixes | ✅ merged + live |
| #666 | AI workspace docs (profile nudge + Render rollout) | ✅ merged |
| #640 | Password complexity validation (register + reset) | ✅ merged + production smoke PASS |

---

## PR #665 — Profile nudge synthetic guard

**Branch:** `fix/profile-nudge-synthetic-guard`

**Problem:** The `rico-profile-nudge-daily` cron job was attempting to send nudge emails to synthetic/internal email addresses (seed accounts, test users, `@ricohunt.com` domain). These emails had no real users and were stamping `profile_nudge_sent_at`, meaning they would never be retried but were wasting API credits and polluting logs.

**Fix:**
- `src/services/profile_nudge_service.py` — added `_is_synthetic_email()` guard. Blocks `@ricohunt.com` domain and local parts matching: `test`, `test_user`, `dummy`, `demo`, `example`, `seed`, `fake`, `user_\d+` (case-insensitive, with optional suffix after `._+-`).
- `src/schemas/pipeline.py` — added `skipped_synthetic: int = 0` to `ProfileNudgeResponse`.
- Synthetic recipients get `profile_nudge_sent_at` stamped so the cron never retries them.

**Verification:** pytest green, Render health 200, cron at `0 5 * * *` scheduled normally.

---

## PR #667 — render-audit.yml bug fixes

**Branch:** `fix/render-audit-bugs`

**Bugs found during run #27866539268:**
1. Step 3 env-var query used `limit=200` — Render API returns HTTP 400 "invalid limit: too large" (max is 100). Fixed to `limit=100`.
2. Step 11 summary contained stale hardcoded text ("No cron jobs exist", "7 PR preview services: DELETED", "PR 462"). Rewrote to read live values from temp files.
3. Step 2 didn't save computed service status (suspended vs active) for use in summary.
4. Step 6 didn't extract the live deploy SHA from `/version` endpoint.
5. Step 9 cron count was computed but names/IDs were not listed.

**Fix:** Temp files (`/tmp/svc_status.txt`, `/tmp/deploy_sha.txt`, `/tmp/cron_count.txt`) written by each step and read by the summary. Status string uses `"suspended (idle — wakes on request)"` for Starter plan idle state vs `"active"`.

---

## PR #666 — AI workspace docs

**Branch:** docs-only. Recorded profile nudge + Render rollout state in `AI_WORKSPACE/CURRENT_STATE.md` and `AI_WORKSPACE/TASKS.md`.

---

## PR #640 — Password complexity validation

**Branch:** `feat/password-complexity`

**Problem (backend):** `POST /api/v1/auth/register` and `POST /api/v1/auth/reset-password` accepted any non-empty password. No complexity rules were enforced.

**Backend fix:**
- `src/schemas/auth.py` — `_check_password_complexity()` validator applied to `RegisterRequest.password` and `ResetPasswordRequest.new_password`.
- Rules: ≥8 chars, ≥1 uppercase, ≥1 lowercase, ≥1 digit or symbol.
- Returns FastAPI 422 with `detail` array: `[{type, loc, msg, input}]` where `msg = "Value error, Password must contain ..."`.

**Frontend fixes (added during PR review):**

Three bugs in frontend error surfacing found and fixed in same PR:

1. **`api.ts` `register()` — broken 422 display**: Was typing `detail` as `string`, so an array became `"[object Object]"`. Fixed to use existing `extractDetail()` helper. Added `.replace(/^Value error,\s+/i, "")` to strip Pydantic v2 prefix.

2. **`api.ts` `resetPassword()` — same problem**: Same array-vs-string mismatch. Fixed identically.

3. **`SignupForm.tsx` `mapSignupError()` — discarded error message**: For 400/422 codes, the original function returned a generic `checkDetails` translation key and discarded `err.message`. Fixed to pass `err.message` through for 400/422 (falls back to translated key only if message is empty).

**Static hint text added:** "Min 8 characters · uppercase · lowercase · digit or symbol" added below password field in both `SignupForm.tsx` and `reset-password/page.tsx`.

**Changed files:**
- `src/schemas/auth.py`
- `apps/web/lib/api.ts` — `register()` + `resetPassword()` error handling
- `apps/web/components/auth/SignupForm.tsx` — `mapSignupError()` + static hint
- `apps/web/app/reset-password/page.tsx` — static hint

**Production smoke (2026-06-20):**
- `weakpass` → rejected, complexity error message displayed clearly ✅
- `SecurePass1!` → accepted, account created ✅
- Verification email flow triggered ✅
- Reset-password page hint visible ✅

---

## Production state after session

- **main HEAD:** `0ecef2b` (feat(auth): password complexity validation, #640)
- **Lineage:** `0ecef2b` ← `6747b6d` (#666 docs) ← `58ab189` (#667 render-audit) ← `8200811` (#665 profile nudge)
- **Render:** auto-deploys from main; service `srv-d7vjljrbc2fs73ctkp8g`; health 200; 2 cron jobs active
- **Vercel:** auto-deploys from main; frontend live at `ricohunt.com`
- **Cron jobs:** `rico-profile-nudge-daily` (`0 5 * * *`) + `rico-followup-reminders` (`0 4 * * *`)

---

## Carry-over resolved this session

- **Password complexity validation** — was in backlog as carry-over engineering debt. Now done (PR #640).

## Still open carry-over

- JWT revocation after password reset (old sessions stay valid after reset)
- Per-user rate limiting on /apply endpoint
- Race condition in guest→auth identity merge
- Settings page keywords tag input (same UX fix as profile TagInputField — PR #638)
- **PR #638** (system overhaul v2) — still a draft PR, not yet merged to main

## Next roadmap

1. **PR #638** — merge system overhaul v1+v2 once CI green.
2. **#355 Follow-up Reminders** — Phase 1 merged (`a95c413`); owner must apply migration + set `RICO_CRON_SECRET` + wire Render Cron.
3. **#356 Inbox Intelligence** — design-only; connector design doc on `main`.
