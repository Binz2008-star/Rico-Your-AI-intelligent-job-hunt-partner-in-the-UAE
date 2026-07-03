#!/bin/bash
# SessionStart hook — bootstraps the Rico dev environment so tests and linters
# work in Claude Code on the web. Mirrors .github/workflows/qa-tests.yml so a
# web session lands in the same state CI runs in.
set -euo pipefail

# Only run in the remote (Claude Code on the web) environment. Local machines
# manage their own venv/node_modules.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$PROJECT_DIR"

echo "[session-start] Installing Python dependencies (requirements + dev)..."
# Best-effort pip upgrade; a system-managed pip (Debian) may refuse to
# self-uninstall, which is fine — the installs below don't require it.
python -m pip install --upgrade pip >/dev/null 2>&1 || true
# First try a normal install. On a Debian base image some deps (e.g. blinker)
# are OS-managed and pip refuses to uninstall them ("RECORD file not found");
# retry with --ignore-installed so pip overlays into the user site instead.
if ! pip install -r requirements.txt -r requirements-dev.txt; then
  echo "[session-start] Retrying with --ignore-installed (Debian-managed packages present)..."
  pip install --ignore-installed -r requirements.txt -r requirements-dev.txt
fi

echo "[session-start] Installing frontend dependencies (apps/web)..."
if [ -f apps/web/package.json ]; then
  # npm install (not ci) so the cached container layer is reused across sessions.
  (cd apps/web && npm install --no-audit --no-fund)
fi

# Persist the env vars CI relies on so pytest behaves the same here:
# - PYTHONPATH so `src` imports resolve from the repo root.
# - REDIS_URL empty so slowapi falls back to memory:// instead of a real Redis.
{
  echo 'export PYTHONPATH="."'
  echo 'export REDIS_URL=""'
} >> "${CLAUDE_ENV_FILE:-/dev/null}"

echo "[session-start] Environment ready."
