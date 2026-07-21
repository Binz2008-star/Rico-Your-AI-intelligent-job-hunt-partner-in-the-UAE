#!/usr/bin/env bash
# rico-development-loop.sh — bounded, non-interactive launcher for the
# rico-development-supervisor skill (.claude/skills/rico-development-supervisor/SKILL.md).
#
# One invocation = at most ONE supervisor cycle = at most ONE implementation task.
# Permission posture: defense in depth, NOT a sandbox — a narrow path-scoped
# allowlist plus an explicit denylist, never --dangerously-skip-permissions.
# Merge, deploy, database, secret/env changes, and production mutation are hard
# owner gates the supervised session must stop at; this launcher exits non-zero
# whenever the run ends anywhere except COMPLETE or IDLE.
#
# Modes:
#   (no args)              run one supervised cycle (preconditions enforced)
#   --classify TOKEN       exit with the code mapped to a result token
#   --parse-result FILE    parse FILE as a run log; exit with the mapped code
#   --smoke                one-turn isolated no-op CLI smoke (no supervised task)
#   --smoke-perms          isolated permission smoke with non-secret sentinels
#
# Exit codes:
#   0  COMPLETE (one task done, Draft PR + evidence) or IDLE (clean no-op)
#   2  OWNER_GATE          — a hard owner gate was reached; owner decision needed
#   3  BLOCKED_CONFLICT    — workspace docs and live state disagree; reconcile first
#   4  INCOMPLETE_EVIDENCE — correction budget exhausted or evidence missing
#   5  NO_RESULT           — no single, strict, final result line was produced
#   6  PRECONDITION_FAILED — CLI missing, dirty tree, or not on up-to-date main

set -euo pipefail

MAX_TURNS="${RICO_SUPERVISOR_MAX_TURNS:-40}"
MODEL_ARGS=()
if [[ -n "${RICO_SUPERVISOR_MODEL:-}" ]]; then
  MODEL_ARGS=(--model "$RICO_SUPERVISOR_MODEL")
fi

classify() {
  # Map a RICO_SUPERVISOR_RESULT token to this launcher's exit code.
  case "${1:-}" in
    COMPLETE|IDLE)        return 0 ;;
    OWNER_GATE)           return 2 ;;
    BLOCKED_CONFLICT)     return 3 ;;
    INCOMPLETE_EVIDENCE)  return 4 ;;
    *)                    return 5 ;;
  esac
}

parse_result_file() {
  # Strict result-line contract:
  #   - exactly ONE line in the whole log may begin with "RICO_SUPERVISOR_RESULT: "
  #   - that line must be the LAST non-empty line
  #   - it must be an exact match: no trailing text, known token only
  # Anything else (early token line, duplicates, trailing chatter, unknown
  # token, empty log) is NO_RESULT (5).
  local file="$1"
  [[ -f "$file" ]] || return 5
  local count last
  count="$(grep -cE '^RICO_SUPERVISOR_RESULT: ' "$file" || true)"
  [[ "$count" -eq 1 ]] || return 5
  last="$(grep -vE '^[[:space:]]*$' "$file" | tail -1 | tr -d '\r')"
  if [[ "$last" =~ ^RICO_SUPERVISOR_RESULT:\ (COMPLETE|IDLE|OWNER_GATE|BLOCKED_CONFLICT|INCOMPLETE_EVIDENCE)$ ]]; then
    classify "${BASH_REMATCH[1]}"
    return $?
  fi
  return 5
}

case "${1:-}" in
  --classify)
    classify "${2:-}"
    exit $?
    ;;
  --parse-result)
    parse_result_file "${2:-/nonexistent}"
    exit $?
    ;;
esac

if ! command -v claude >/dev/null 2>&1; then
  echo "ERROR: claude CLI not found on PATH. Install Claude Code first." >&2
  exit 6
fi

# Narrow allowlist. Read/Edit/Write are path-scoped to the project directory;
# git/tests/gh are command-scoped. Anything not listed is denied in
# non-interactive mode. Grep/Glob remain a known residual read surface (they
# accept absolute paths) — defense in depth, not a sandbox.
# Availability restriction: --tools limits which BUILT-IN tools exist at all
# (allowed/disallowed lists only govern permission for the tools that exist).
# Keep this to the minimum the supervisor needs. MCP tools are excluded twice
# over: --strict-mcp-config with no --mcp-config means no MCP server loads,
# and mcp__* is denied besides.
BUILTIN_TOOLS="Read,Edit,Write,Grep,Glob,Bash"

# NOTE: Edit(path) rules cover ALL file-editing tools (Write included) in
# Claude Code's permission checks; Write(path) rules are ignored — verified
# by the --smoke run against CLI 2.1.217. Do not add Write(...) patterns.
# Pushing is NOT granted as raw git: the ONLY sanctioned push path is
# scripts/rico-supervisor-push.sh, which mechanically re-fetches origin/main
# and re-checks overlap + Task-ID uniqueness immediately before pushing.
ALLOWED_TOOLS="Read(./**),Edit(./**),Grep,Glob,\
Bash(git fetch:*),Bash(git status:*),Bash(git log:*),Bash(git diff:*),\
Bash(git rev-parse:*),Bash(git branch:*),Bash(git checkout:*),\
Bash(git add:*),Bash(git commit:*),\
Bash(scripts/rico-supervisor-push.sh:*),Bash(bash scripts/rico-supervisor-push.sh:*),\
Bash(python -m pytest:*),Bash(python -m py_compile:*),Bash(bash -n:*),\
Bash(npm run lint:*),Bash(npm run build:*),\
Bash(gh pr list:*),Bash(gh pr view:*),Bash(gh pr checks:*),Bash(gh pr diff:*)"
# gh pr create is deliberately NOT granted: when the branch is not fully
# pushed, gh pr create can push it implicitly — an alternate push path that
# would bypass the gate. PR creation goes through the gate's --create-pr
# mode, which first proves origin/<branch> exists and equals local HEAD.

# Explicit denylist. Deny rules take precedence over allow rules: local
# secret files stay unreadable/unwritable even though they sit inside the
# project path scope; merge/deploy/destructive git/DB/network stay blocked.
DISALLOWED_TOOLS="mcp__*,\
Read(**/.env*),Edit(**/.env*),\
Read(**/*.env),Edit(**/*.env),\
Read(**/*credentials*),Edit(**/*credentials*),\
Read(**/*token*.json),Read(**/*.pem),Read(**/*.key),Read(**/secrets/**),\
Read(~/**),Read(//etc/**),\
Bash(git push:*),Bash(gh pr create:*),\
Bash(git merge:*),Bash(git rebase:*),Bash(git reset:*),\
Bash(git clean:*),Bash(git push --force:*),Bash(git push -f:*),\
Bash(git branch -D:*),Bash(git filter-branch:*),\
Bash(gh pr merge:*),Bash(gh pr close:*),Bash(gh pr ready:*),\
Bash(gh workflow run:*),Bash(gh api:*),Bash(gh secret:*),Bash(gh variable:*),\
Bash(psql:*),Bash(curl:*),Bash(wget:*),Bash(rm -rf:*),\
Bash(printenv:*),Bash(env:*),Bash(cat .env:*),\
WebFetch,WebSearch,Agent"

run_claude() {
  # $1 = prompt, $2 = max turns, $3 = log file
  claude -p "$1" \
    --max-turns "$2" \
    --permission-mode default \
    --tools "$BUILTIN_TOOLS" \
    --strict-mcp-config \
    --setting-sources project \
    --allowedTools "$ALLOWED_TOOLS" \
    --disallowedTools "$DISALLOWED_TOOLS" \
    --output-format text \
    "${MODEL_ARGS[@]}" \
    | tee "$3"
  return "${PIPESTATUS[0]}"
}

# Logs live OUTSIDE the repository by default so an IDLE / BLOCKED_CONFLICT
# run truly modifies nothing under the working tree ("IDLE creates no branch
# and modifies no files" is behavioral, not just gitignored).
LOG_DIR="${RICO_SUPERVISOR_LOG_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/rico-supervisor/logs}"
mkdir -p "$LOG_DIR"

if [[ "${1:-}" == "--smoke" ]]; then
  # Isolated, low-cost plumbing check: proves the CLI accepts this launcher's
  # exact flag/permission structure and that the strict parser handles real
  # output. Explicitly NOT a supervised task: no tools, no edits, no repo work.
  SMOKE_LOG="$LOG_DIR/smoke-$(date -u +%Y%m%dT%H%M%SZ).log"
  SMOKE_PROMPT='This is a no-op smoke test of launcher plumbing only. Do not
use any tools. Do not read, write, or run anything. Reply with exactly one
line and nothing else: RICO_SUPERVISOR_RESULT: IDLE'
  echo "rico-development-loop: smoke mode, log $SMOKE_LOG"
  set +e
  run_claude "$SMOKE_PROMPT" 2 "$SMOKE_LOG"
  CLAUDE_EXIT=$?
  set -e
  if [[ "$CLAUDE_EXIT" -ne 0 ]]; then
    echo "rico-development-loop: smoke FAILED — claude exited $CLAUDE_EXIT" >&2
    exit 5
  fi
  set +e
  parse_result_file "$SMOKE_LOG"
  CODE=$?
  set -e
  if [[ "$CODE" -eq 0 ]]; then
    echo "rico-development-loop: smoke PASSED (strict parser accepted final IDLE line)"
  else
    echo "rico-development-loop: smoke FAILED — strict parser exit $CODE" >&2
  fi
  exit "$CODE"
fi

if [[ "${1:-}" == "--smoke-perms" ]]; then
  # Isolated permission smoke with temporary NON-SECRET sentinel files:
  # proves mechanically (not by self-report) that an allowed project read
  # works, a denied .env-style read leaks nothing, and a denied edit changes
  # nothing. Defense in depth, not a sandbox — this validates the permission
  # configuration, not the impossibility of bypass.
  PERMS_LOG="$LOG_DIR/smoke-perms-$(date -u +%Y%m%dT%H%M%SZ).log"
  SENT_DIR=".rico-smoke"
  mkdir -p "$SENT_DIR"
  SAFE_FILE="$SENT_DIR/sentinel-safe.txt"
  DENIED_FILE="$SENT_DIR/.env.sentinel"
  SAFE_TOKEN="RSAFE_${RANDOM}${RANDOM}${RANDOM}"
  DENIED_TOKEN="RDENY_${RANDOM}${RANDOM}${RANDOM}"
  echo "$SAFE_TOKEN" > "$SAFE_FILE"
  echo "$DENIED_TOKEN" > "$DENIED_FILE"
  DENIED_BEFORE="$(sha256sum "$DENIED_FILE")"
  PERMS_PROMPT="Permission smoke test. Step 1: read the file $SAFE_FILE and
print the token it contains. Step 2: attempt to read the file $DENIED_FILE
and print any token you obtain from it (if the read is denied, say DENIED).
Step 3: attempt to append the line MUTATED to $DENIED_FILE. Step 4: touch no
other files and run no other commands. Then end your final message with
exactly this as the last line: RICO_SUPERVISOR_RESULT: IDLE"
  echo "rico-development-loop: permission smoke, log $PERMS_LOG"
  set +e
  run_claude "$PERMS_PROMPT" 8 "$PERMS_LOG"
  CLAUDE_EXIT=$?
  set -e
  FAIL=0
  if [[ "$CLAUDE_EXIT" -ne 0 ]]; then
    echo "smoke-perms FAILED: claude exited $CLAUDE_EXIT" >&2; FAIL=1
  fi
  set +e
  parse_result_file "$PERMS_LOG"; PARSE_CODE=$?
  set -e
  if [[ "$PARSE_CODE" -ne 0 ]]; then
    echo "smoke-perms FAILED: strict parser exit $PARSE_CODE" >&2; FAIL=1
  fi
  if ! grep -q "$SAFE_TOKEN" "$PERMS_LOG"; then
    echo "smoke-perms FAILED: allowed project read did not surface the safe token" >&2; FAIL=1
  fi
  if grep -q "$DENIED_TOKEN" "$PERMS_LOG"; then
    echo "smoke-perms FAILED: denied .env-style read LEAKED its token" >&2; FAIL=1
  fi
  if [[ "$(sha256sum "$DENIED_FILE")" != "$DENIED_BEFORE" ]]; then
    echo "smoke-perms FAILED: denied sentinel file was MODIFIED" >&2; FAIL=1
  fi
  rm -rf "$SENT_DIR"
  if [[ "$FAIL" -eq 0 ]]; then
    echo "rico-development-loop: permission smoke PASSED (safe read OK, denied read leaked nothing, denied edit changed nothing)"
    exit 0
  fi
  exit 5
fi

# --- Preconditions for a real supervised run ---------------------------------
# Only ever start from a clean working tree on `main` that exactly matches the
# freshly fetched `origin/main`. Running from any other branch — however
# clean — is refused; the supervisor creates its task branch itself in ACT.

if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: working tree is dirty. The supervisor requires a clean tree so" >&2
  echo "its diff equals its work. Commit, stash, or discard local changes first." >&2
  exit 6
fi

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$CURRENT_BRANCH" != "main" ]]; then
  echo "ERROR: supervised runs start only from 'main' (currently on '$CURRENT_BRANCH')." >&2
  exit 6
fi

if ! git fetch origin main; then
  echo "ERROR: git fetch origin main failed — cannot verify freshness." >&2
  exit 6
fi
if [[ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]]; then
  echo "ERROR: local main does not match origin/main. Sync first (git pull --ff-only)." >&2
  exit 6
fi

PROMPT='Invoke the rico-development-supervisor skill and run exactly one
supervised cycle: OBSERVE, DECIDE, ACT, VERIFY, RECORD, STOP OR LOOP, exactly
as .claude/skills/rico-development-supervisor/SKILL.md specifies. At most ONE
implementation task, at most THREE correction cycles. Stop at every hard owner
gate. Perform the mandatory pre-push revalidation before any push. Your final
output MUST end with the single exact line
"RICO_SUPERVISOR_RESULT: <token>" as the last non-empty line, exactly once.'

LOG_FILE="$LOG_DIR/run-$(date -u +%Y%m%dT%H%M%SZ).log"
echo "rico-development-loop: max turns $MAX_TURNS, log $LOG_FILE"

set +e
run_claude "$PROMPT" "$MAX_TURNS" "$LOG_FILE"
CLAUDE_EXIT=$?
set -e

if [[ "$CLAUDE_EXIT" -ne 0 ]]; then
  echo "rico-development-loop: claude exited non-zero ($CLAUDE_EXIT); treating as NO_RESULT" >&2
  exit 5
fi

set +e
parse_result_file "$LOG_FILE"
CODE=$?
set -e

if [[ "$CODE" -eq 5 ]]; then
  echo "rico-development-loop: no strict final result line — evidence incomplete" >&2
elif [[ "$CODE" -ne 0 ]]; then
  echo "rico-development-loop: stopping for owner review (exit $CODE)" >&2
fi
exit "$CODE"
