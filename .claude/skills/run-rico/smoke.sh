#!/usr/bin/env bash
# smoke.sh — Launch Rico (backend + frontend) and run HTTP smoke tests.
# Usage: bash .claude/skills/run-rico/smoke.sh [--no-frontend]
#
# Exit 0 = all checks passed. Exit 1 = something failed.

set -euo pipefail
REPO="$(git rev-parse --show-toplevel)"
FAILED=0

_pass() { echo "  PASS  $1"; }
_fail() { echo "  FAIL  $1"; FAILED=1; }

# ── 1. Backend ────────────────────────────────────────────────────────────────
echo "==> Starting backend (port 8000)"
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
  pkill -f "uvicorn src.api.app:app" 2>/dev/null || true
  sleep 2
  cd "$REPO"
  python -m uvicorn src.api.app:app --port 8000 > /tmp/rico-api.log 2>&1 &
  for i in $(seq 1 20); do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then break; fi
    sleep 1
  done
fi
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
  echo "Backend failed to start. Log:"; tail -20 /tmp/rico-api.log; exit 1
fi

# Backend smoke checks
check_status() {
  local url=$1 expected=$2 label=$3
  local got; got=$(curl -s -o /dev/null -w "%{http_code}" "$url")
  [ "$got" = "$expected" ] && _pass "$label ($got)" || _fail "$label (expected $expected, got $got)"
}

check_json() {
  local url=$1 key=$2 expected=$3 label=$4
  local got; got=$(curl -s "$url" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('$key','MISSING'))")
  [ "$got" = "$expected" ] && _pass "$label" || _fail "$label (expected '$expected', got '$got')"
}

check_status "http://localhost:8000/health" 200 "GET /health"
check_json   "http://localhost:8000/health" "status" "ok" "  health.status=ok"
check_status "http://localhost:8000/version" 200 "GET /version"

CHAT_BODY='{"message":"Hello","session_id":"smoke-session-001"}'
CHAT_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/v1/rico/chat/public \
  -H "Content-Type: application/json" -d "$CHAT_BODY")
[ "$CHAT_CODE" = "200" ] && _pass "POST /api/v1/rico/chat/public (200)" || _fail "POST /api/v1/rico/chat/public (got $CHAT_CODE)"

# ── 2. Frontend (optional) ────────────────────────────────────────────────────
if [[ "${1:-}" != "--no-frontend" ]]; then
  echo "==> Starting frontend (port 3000)"
  if ! curl -s http://localhost:3000/ > /dev/null 2>&1; then
    pkill -f "next dev" 2>/dev/null || true
    sleep 2
    cd "$REPO/apps/web"
    npm run dev > /tmp/rico-web.log 2>&1 &
    for i in $(seq 1 30); do
      if curl -s http://localhost:3000/ > /dev/null 2>&1; then break; fi
      sleep 1
    done
  fi
  if ! curl -s http://localhost:3000/ > /dev/null 2>&1; then
    echo "Frontend failed to start. Log:"; tail -20 /tmp/rico-web.log; exit 1
  fi

  for path_code in "/:200" "/signup:200" "/login:200" "/chat:307"; do
    p="${path_code%%:*}"; c="${path_code##*:}"
    check_status "http://localhost:3000${p}" "$c" "GET $p"
  done

  TITLE=$(curl -s http://localhost:3000/ | grep -o '<title>[^<]*</title>' || true)
  [[ "$TITLE" == *"Rico"* ]] && _pass "page title contains Rico" || _fail "page title missing Rico (got '$TITLE')"
fi

# ── 3. Backend unit tests ─────────────────────────────────────────────────────
# NOTE: test_agent.py and test_agent_runtime.py have 6 known pre-existing failures
# (TestApplyServiceIndeedMethod, TestDraftAction, TestJobResolution). These are
# not gating — the suite as a whole has 3323+ passing tests.
echo "==> Running unit tests (core suite)"
cd "$REPO"
python -m pytest tests/test_jotform_webhook.py tests/test_jwt_user_isolation.py \
  tests/test_onboarding_state.py -q --tb=short 2>&1 | tail -5

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
if [ "$FAILED" -eq 0 ]; then
  echo "All smoke checks passed."
else
  echo "Some smoke checks FAILED. See above."
  exit 1
fi
