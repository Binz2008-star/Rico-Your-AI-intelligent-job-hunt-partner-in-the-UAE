# Production Smoke Tests

Run smoke tests in this order. Do not skip ahead. Each tier gates the next.

## Tier 1 — Public Smoke (no auth required)

These checks verify the backend and frontend are reachable and the unauthenticated surface is functional.

```bash
# Backend health
curl -s https://rico-job-automation-api.onrender.com/health | python -m json.tool

# Expected: { "status": "ok", "provider": "...", "ready_for_<provider>": true, ... }
# Fail condition: connection refused, 502, or status != "ok"

# Backend version
curl -s https://rico-job-automation-api.onrender.com/version

# Frontend home page
curl -s -o /dev/null -w "%{http_code}" https://ricohunt.com/
# Expected: 200

# Public chat endpoint (unauthenticated)
curl -s -X POST https://rico-job-automation-api.onrender.com/api/v1/rico/chat/public \
  -H "Content-Type: application/json" \
  -d '{"message": "hello", "session_id": "smoke-test-001"}' | python -m json.tool
# Expected: { "response": "...", "session_id": "smoke-test-001" }
# Fail condition: 4xx, 5xx, or empty response field
```

Tier 1 pass criteria:
- `/health` returns `status: ok`.
- `/version` returns a version string.
- `ricohunt.com` returns HTTP 200.
- Public chat returns a non-empty response.

---

## Tier 2 — Targeted Authenticated Smoke

Run only after Tier 1 passes. Do not print passwords, cookies, tokens, or session values in logs or CI output.

```bash
# Register a smoke-test account (use a dedicated test address, not a real user)
# Replace SMOKE_EMAIL and SMOKE_PASS with values from your secrets store — never hardcode here
curl -s -X POST https://rico-job-automation-api.onrender.com/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$SMOKE_EMAIL\", \"password\": \"$SMOKE_PASS\", \"name\": \"Smoke Test\"}" \
  -c /tmp/smoke_cookies.txt | python -m json.tool
# Expected: { "email": "...", "role": "user" }
# role must be "user" — any other role value is a security failure

# Login (if account already exists)
curl -s -X POST https://rico-job-automation-api.onrender.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$SMOKE_EMAIL\", \"password\": \"$SMOKE_PASS\"}" \
  -c /tmp/smoke_cookies.txt -b /tmp/smoke_cookies.txt | python -m json.tool
# Expected: 200 with user object — cookie is set as httpOnly, not visible in response body

# /me check
curl -s https://rico-job-automation-api.onrender.com/api/v1/me \
  -b /tmp/smoke_cookies.txt | python -m json.tool
# Expected: { "email": "...", "role": "user", "authenticated": true, "guest": false }
# Fail condition: role != "user" or authenticated != true

# Authenticated chat
curl -s -X POST https://rico-job-automation-api.onrender.com/api/v1/rico/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "hello"}' \
  -b /tmp/smoke_cookies.txt | python -m json.tool
# Expected: { "response": "..." }

# Logout
curl -s -X POST https://rico-job-automation-api.onrender.com/api/v1/auth/logout \
  -b /tmp/smoke_cookies.txt
# Clean up
rm -f /tmp/smoke_cookies.txt
```

Tier 2 pass criteria:
- Registration returns `role: user`.
- `/me` returns the correct user and `role: user`.
- Authenticated chat returns a non-empty response.
- Logout succeeds without error.

---

## Tier 3 — Manual Product Smoke

Run after Tier 2 passes. This is a browser-based walkthrough, not automated.

| Step | Expected |
|---|---|
| Open `https://ricohunt.com` | Landing page loads; no console errors |
| Navigate to `/chat` | Public chat loads; Rico responds to "hello" |
| Navigate to `/signup` | Registration form loads |
| Register a new test account | Redirects to `/onboarding` or `/command` |
| Complete onboarding | Reaches `/command` |
| Ask Rico: "find jobs for Environmental Compliance Officer" | Rico returns job list with job cards |
| Click "Prepare application" on a job card | Rico responds with match reasoning for that specific job |
| Navigate to `/applications` | Application Flow loads; no "use a spreadsheet" text |
| Ask Rico: "why don't you have my past applications?" | Rico explains three sources; offers Add manually and "coming next" inbox import |
| Navigate to `/subscription` | Subscription page loads; packages visible |
| Click Pro package | Routes to Stripe Checkout (not `/command`) |
| Navigate to `/settings` | Settings page loads |
| Click logout | Session cleared; redirected to landing or `/login` |

Do not use real payment card data in manual smoke. Use Stripe test card `4242 4242 4242 4242`.

---

## Smoke Test Sequence Rule

```
Tier 1 (public) → PASS
    ↓
Tier 2 (authenticated) → PASS
    ↓
Tier 3 (manual product) → PASS
    ↓
System status: Green
```

If Tier 1 fails, stop. Backend or Render is down. Do not run Tier 2 or 3.

If Tier 1 passes but Tier 2 fails, the auth layer or database is degraded. Investigate `/me` and registration before running Tier 3.

---

## Privacy Rules for Smoke Tests

- Do not print cookie values, JWTs, or session tokens in CI logs.
- Do not hardcode real user passwords in this file or in test scripts.
- Use environment variables (`$SMOKE_EMAIL`, `$SMOKE_PASS`) sourced from a secrets store.
- Delete the `/tmp/smoke_cookies.txt` file after each run.
- Use a dedicated smoke test account, never a real user account.
