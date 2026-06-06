#!/usr/bin/env bash
# check.sh — Read-only deployment verification for Rico.
#
# What it does:
#   1. Reads the latest commit on origin/main from the local git repo.
#   2. Calls https://rico-job-automation-api.onrender.com/version  (Render backend).
#   3. Calls https://rico-job-automation-api.onrender.com/health   (Render backend).
#   4. Calls https://ricohunt.com/proxy/health                     (Vercel → backend proxy).
#   5. Compares deployed commit with expected commit.
#   6. Reports whether Render is stale.
#   7. Prints safe next steps only.
#
# What it NEVER does:
#   - Deploys anything.
#   - Changes env vars.
#   - Touches Neon, Stripe, JotForm, or any production DB.
#   - Writes any file outside /tmp.
#
# Usage:
#   bash .claude/skills/deploy-rico/check.sh
#   bash .claude/skills/deploy-rico/check.sh --json   # machine-readable output

set -euo pipefail
JSON_MODE=0
[[ "${1:-}" == "--json" ]] && JSON_MODE=1

RENDER_API="https://rico-job-automation-api.onrender.com"
FRONTEND="https://ricohunt.com"

PASS="  OK  "
FAIL=" FAIL "
WARN=" WARN "
INFO=" INFO "

_log() { [[ $JSON_MODE -eq 0 ]] && echo "$1"; }

# ── Helpers ───────────────────────────────────────────────────────────────────

fetch_json() {
    local url=$1 timeout=${2:-10}
    curl -sS --max-time "$timeout" \
         -H "Accept: application/json" \
         -H "User-Agent: rico-deploy-check/1.0" \
         "$url" 2>/dev/null || true
}

http_status() {
    curl -sS -o /dev/null -w "%{http_code}" --max-time 10 \
         -H "User-Agent: rico-deploy-check/1.0" \
         "${1}" 2>/dev/null || echo "000"
}

jq_field() {
    # Lightweight JSON field extraction — no jq dependency required.
    python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    keys = '${2}'.split('.')
    for k in keys:
        d = d[k] if isinstance(d, dict) else None
    print(d if d is not None else '')
except Exception:
    print('')
" 2>/dev/null
}

# ── 1. Expected commit (origin/main) ─────────────────────────────────────────

REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel 2>/dev/null || echo "")"
EXPECTED_COMMIT=""
if [[ -n "$REPO_ROOT" ]]; then
    # Fetch quietly so we see the real remote state, not stale local refs.
    git -C "$REPO_ROOT" fetch origin main --quiet 2>/dev/null || true
    EXPECTED_COMMIT="$(git -C "$REPO_ROOT" rev-parse origin/main 2>/dev/null | cut -c1-7 || true)"
fi

_log ""
_log "═══════════════════════════════════════════════════"
_log "  Rico Deployment Verification"
_log "  $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
_log "═══════════════════════════════════════════════════"

# ── 2. Render /version ────────────────────────────────────────────────────────

_log ""
_log "── Render backend ($RENDER_API) ──"

VERSION_JSON="$(fetch_json "$RENDER_API/version" 15)"
DEPLOYED_COMMIT="$(echo "$VERSION_JSON" | jq_field - commit)"
DEPLOYED_ENV="$(echo "$VERSION_JSON"    | jq_field - environment)"
DEPLOYED_APP="$(echo "$VERSION_JSON"    | jq_field - app)"
DEPLOYED_AT="$(echo "$VERSION_JSON"     | jq_field - deployed_at)"

if [[ -n "$DEPLOYED_APP" ]]; then
    _log "[$PASS] GET /version  →  app=$DEPLOYED_APP  env=$DEPLOYED_ENV  commit=${DEPLOYED_COMMIT:-unknown}  deployed_at=${DEPLOYED_AT:-—}"
else
    _log "[$FAIL] GET /version  →  no response or parse error"
    DEPLOYED_COMMIT=""
fi

# ── 3. Render /health ─────────────────────────────────────────────────────────

HEALTH_JSON="$(fetch_json "$RENDER_API/health" 15)"
HEALTH_STATUS="$(echo "$HEALTH_JSON" | jq_field - status)"
HEALTH_CODE="$(http_status "$RENDER_API/health")"

if [[ "$HEALTH_CODE" == "200" && "$HEALTH_STATUS" == "ok" ]]; then
    _log "[$PASS] GET /health   →  HTTP $HEALTH_CODE  status=$HEALTH_STATUS"
elif [[ "$HEALTH_CODE" == "000" ]]; then
    _log "[$FAIL] GET /health   →  no response (Render may be sleeping)"
else
    _log "[$WARN] GET /health   →  HTTP $HEALTH_CODE  status=${HEALTH_STATUS:-?}"
fi

# ── 4. Frontend /proxy/health ─────────────────────────────────────────────────

_log ""
_log "── Vercel frontend ($FRONTEND) ──"

PROXY_CODE="$(http_status "$FRONTEND/proxy/health")"
PROXY_JSON="$(fetch_json "$FRONTEND/proxy/health" 15)"
PROXY_STATUS="$(echo "$PROXY_JSON" | jq_field - status)"

if [[ "$PROXY_CODE" == "200" && "$PROXY_STATUS" == "ok" ]]; then
    _log "[$PASS] GET /proxy/health  →  HTTP $PROXY_CODE  status=$PROXY_STATUS"
elif [[ "$PROXY_CODE" == "000" ]]; then
    _log "[$FAIL] GET /proxy/health  →  no response"
else
    _log "[$WARN] GET /proxy/health  →  HTTP $PROXY_CODE  status=${PROXY_STATUS:-?}"
fi

# Vercel frontend root
FRONTEND_CODE="$(http_status "$FRONTEND/")"
if [[ "$FRONTEND_CODE" == "200" ]]; then
    _log "[$PASS] GET /           →  HTTP $FRONTEND_CODE"
else
    _log "[$WARN] GET /           →  HTTP $FRONTEND_CODE"
fi

# ── 5. Commit comparison ──────────────────────────────────────────────────────

_log ""
_log "── Commit comparison ──"
_log "[$INFO] origin/main      →  ${EXPECTED_COMMIT:-unknown}"
_log "[$INFO] Render deployed  →  ${DEPLOYED_COMMIT:-unknown}"

STALE=0
NEXT_STEPS=()

if [[ -z "$DEPLOYED_COMMIT" || "$DEPLOYED_COMMIT" == "unknown" ]]; then
    _log "[$WARN] Cannot determine deployed commit — Render /version returned no commit field."
    NEXT_STEPS+=("Check Render dashboard to confirm the service deployed from the correct branch.")
elif [[ -z "$EXPECTED_COMMIT" ]]; then
    _log "[$WARN] Cannot determine expected commit — git fetch failed."
    NEXT_STEPS+=("Run: git fetch origin main && git rev-parse origin/main")
else
    # Compare the shorter of the two (Render may return a 7-char short SHA)
    SHORT_EXPECTED="${EXPECTED_COMMIT:0:7}"
    SHORT_DEPLOYED="${DEPLOYED_COMMIT:0:7}"
    if [[ "$SHORT_EXPECTED" == "$SHORT_DEPLOYED" ]]; then
        _log "[$PASS] Render is up to date with origin/main ($SHORT_DEPLOYED)"
    else
        STALE=1
        _log "[$FAIL] Render is STALE — expected $SHORT_EXPECTED, got $SHORT_DEPLOYED"
        NEXT_STEPS+=("Render deploy is behind origin/main.")
        NEXT_STEPS+=("To deploy: push to main then trigger a manual deploy from the Render dashboard.")
        NEXT_STEPS+=("Do NOT redeploy from this script — use the Render dashboard or Render CLI.")
    fi
fi

# ── 6. Summary and next steps ─────────────────────────────────────────────────

_log ""
_log "═══════════════════════════════════════════════════"
if [[ $STALE -eq 1 ]]; then
    _log "  STATUS: ⚠  Render backend is stale"
elif [[ "$HEALTH_CODE" != "200" || "$PROXY_CODE" != "200" ]]; then
    _log "  STATUS: ⚠  One or more checks did not pass"
else
    _log "  STATUS: ✓  All checks passed"
fi
_log "═══════════════════════════════════════════════════"

if [[ ${#NEXT_STEPS[@]} -gt 0 ]]; then
    _log ""
    _log "Next steps:"
    for step in "${NEXT_STEPS[@]}"; do
        _log "  • $step"
    done
fi
_log ""

# ── JSON output (--json flag) ─────────────────────────────────────────────────

if [[ $JSON_MODE -eq 1 ]]; then
    python3 - <<PYEOF
import json
data = {
    "expected_commit":  "${EXPECTED_COMMIT:-unknown}",
    "deployed_commit":  "${DEPLOYED_COMMIT:-unknown}",
    "stale":            ${STALE},
    "render_health":    "${HEALTH_STATUS:-error}",
    "render_health_code": "${HEALTH_CODE}",
    "proxy_health_code":  "${PROXY_CODE}",
    "proxy_health":       "${PROXY_STATUS:-error}",
    "frontend_code":      "${FRONTEND_CODE}",
    "deployed_env":       "${DEPLOYED_ENV:-unknown}",
    "deployed_at":        "${DEPLOYED_AT:-}",
}
print(json.dumps(data, indent=2))
PYEOF
fi

# Exit non-zero when stale or health check failed
if [[ $STALE -eq 1 ]] || [[ "$HEALTH_CODE" != "200" ]]; then
    exit 1
fi
