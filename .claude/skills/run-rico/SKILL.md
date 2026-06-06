---
name: run-rico
description: Run, start, launch, build, test, screenshot, verify, smoke-test Rico Hunt — the FastAPI backend and Next.js frontend. Use when asked to run the app, start the server, confirm a change works, or check that a feature is live.
---

# run-rico

Rico Hunt is a UAE job-search platform. The backend is FastAPI (`src/api/app.py`) served on port 8000; the frontend is Next.js 14 (`apps/web`) served on port 3000. No browser is available in this container — all verification is done via `curl`.

The primary agent path is `.claude/skills/run-rico/smoke.sh`. It starts both services (reusing any already-running ones), hits every key HTTP endpoint, and runs the core unit test suite. Exit 0 = everything OK.

---

## Prerequisites

```bash
# Python deps (already installed if backend was ever started)
pip install -r requirements.txt --ignore-installed

# Node deps (already installed if frontend was ever built)
cd apps/web && npm install
```

---

## Build

```bash
# Verify frontend builds cleanly (catches TypeScript / import errors)
cd apps/web && npm run build
```

Build output lists every route. Expected: no errors, many ○ (static) and ƒ (dynamic) entries.

---

## Run (agent path) — smoke.sh

```bash
bash .claude/skills/run-rico/smoke.sh
```

What it does:
1. Starts backend on port 8000 (skips start if already up)
2. Starts frontend on port 3000 via `npm run dev` (skips if already up)
3. Checks: `GET /health`, `GET /version`, `POST /api/v1/rico/chat/public`
4. Checks: `GET /`, `/signup`, `/login`, `/chat` (expects 200/307)
5. Verifies page `<title>` contains "Rico"
6. Runs `tests/test_jotform_webhook.py`, `test_jwt_user_isolation.py`, `test_onboarding_state.py`

Pass `--no-frontend` to skip the Next.js startup (faster, backend only):

```bash
bash .claude/skills/run-rico/smoke.sh --no-frontend
```

---

## Run (manual path)

```bash
# Backend
python -m uvicorn src.api.app:app --reload --port 8000

# Frontend (separate terminal)
cd apps/web && npm run dev
```

`/chat` redirects (307) to the onboarding flow for unauthenticated users. `/signup` and `/login` render at 200.

---

## Direct API calls

```bash
# Health check
curl http://localhost:8000/health

# Public chat (session_id must be ≥ 8 chars)
curl -X POST http://localhost:8000/api/v1/rico/chat/public \
  -H "Content-Type: application/json" \
  -d '{"message":"What jobs are available?","session_id":"smoke-session-001"}'
```

---

## Full test suite

```bash
# Core integration tests only (94 tests, ~2s, all pass)
python -m pytest tests/test_jotform_webhook.py tests/test_jwt_user_isolation.py \
  tests/test_onboarding_state.py -q

# Full suite (3323+ passing, ~69s)
python -m pytest tests/ -q --tb=short
```

---

## Gotchas

- **`session_id` must be ≥ 8 characters** on the public chat endpoint — 422 if shorter.
- **`/chat` returns 307**, not 200 — it redirects unauthenticated users. This is expected.
- **Auth requires a live DB** (`DATABASE_URL`). `POST /auth/register` returns "Registration unavailable" without it.
- **AI providers all absent in dev** — public chat falls back to keyword/templated responses (`response_source: "fallback"`). This is correct behavior without API keys.
- **pip install conflicts**: `cryptography` is system-installed. Use `--ignore-installed` to override.
- **`test_agent.py` and `test_agent_runtime.py` have 6 pre-existing failures** (`TestApplyServiceIndeedMethod`, `TestDraftAction`, `TestJobResolution`) — not gating, pre-date this skill.
- **`npm run build` is the fastest correctness check** — it runs TypeScript compilation and catches import errors in ~30s without needing a browser.
- **Playwright e2e tests require a browser** — `npx playwright install chromium` fails in this container (no download access). Use `smoke.sh` instead.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Backend failed to start` | Check `/tmp/rico-api.log` — usually a missing import or port conflict. Kill with `pkill -f "uvicorn src.api.app"` then retry. |
| `Frontend failed to start` | Check `/tmp/rico-web.log`. Usually a build error — run `npm run build` first to surface it. |
| `422 on /chat/public` | `session_id` too short (< 8 chars). |
| `cryptography uninstall error` | Add `--ignore-installed` to pip install. |
| Port already in use | `lsof -ti:8000 | xargs kill -9` or `:3000` for frontend. |
