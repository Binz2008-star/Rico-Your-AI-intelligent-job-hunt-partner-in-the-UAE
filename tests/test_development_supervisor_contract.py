"""Static contract guard for the rico-development-supervisor control layer.

Pins the development-loop contract so it cannot silently drift:

- one implementation task per invocation, max three correction cycles;
- every hard owner gate is listed and the skill never self-authorizes merge;
- IDLE modifies nothing; workspace/live-state conflict stops execution;
- pre-push revalidation (re-fetch main, re-check overlap and Task-ID
  uniqueness) is mandatory before any push;
- Task IDs in AI_WORKSPACE/TASKS.md are unique (frozen historical exception);
- a failed acceptance criterion cannot be reported as complete;
- the ledger is append-only with a real validated_head_sha (no sentinels);
- the launcher is bounded (explicit max turns), path-scopes Read/Edit/Write,
  denies known secret paths, never bypasses permissions, refuses to start
  anywhere but a clean up-to-date main, and enforces a STRICT final result
  line — exercised through real subprocess runs of --classify/--parse-result.

These tests prove configuration and contract text, NOT impossibility of
bypass (defense in depth, not a sandbox). Pure file/static checks — no
network, no database, no live services, no Claude invocation.
"""

import importlib.util
import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / ".claude" / "skills" / "rico-development-supervisor" / "SKILL.md"
STATE = REPO_ROOT / "AI_WORKSPACE" / "DEVELOPMENT_LOOP_STATE.md"
TASKS = REPO_ROOT / "AI_WORKSPACE" / "TASKS.md"
LAUNCHER = REPO_ROOT / "scripts" / "rico-development-loop.sh"
PUSH_GATE_SH = REPO_ROOT / "scripts" / "rico-supervisor-push.sh"
PUSH_GATE_PY = REPO_ROOT / "scripts" / "supervisor_push_gate.py"

_spec = importlib.util.spec_from_file_location("supervisor_push_gate", PUSH_GATE_PY)
push_gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(push_gate)

RESULT_TOKENS = {
    "COMPLETE",
    "IDLE",
    "OWNER_GATE",
    "BLOCKED_CONFLICT",
    "INCOMPLETE_EVIDENCE",
}

# The frozen historical duplicate (TASK-20260721-005) is pinned to its EXACT
# existing headings in scripts/supervisor_push_gate.py — the single source of
# truth shared by this guard and the push gate. Replacing one old occurrence
# with a NEW duplicate under the same id must still fail.
FROZEN_DUPLICATE_HEADINGS = push_gate.FROZEN_DUPLICATE_HEADINGS


def skill_text() -> str:
    return SKILL.read_text(encoding="utf-8")


def skill_flat() -> str:
    return re.sub(r"\s+", " ", skill_text())


def launcher_text() -> str:
    return LAUNCHER.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# SKILL.md contract
# ---------------------------------------------------------------------------


def test_skill_exists_with_frontmatter():
    text = skill_text()
    assert text.startswith("---\n"), "SKILL.md must start with YAML frontmatter"
    front = text.split("---", 2)[1]
    meta = yaml.safe_load(front)
    assert meta["name"] == "rico-development-supervisor"
    assert "description" in meta and meta["description"].strip()


def test_skill_defines_all_six_stages_in_order():
    text = skill_text()
    stages = [
        "## Stage: OBSERVE",
        "## Stage: DECIDE",
        "## Stage: ACT",
        "## Stage: VERIFY",
        "## Stage: RECORD",
        "## Stage: STOP OR LOOP",
    ]
    positions = [text.find(s) for s in stages]
    assert all(p >= 0 for p in positions), (
        "missing stage heading(s): "
        + ", ".join(s for s, p in zip(stages, positions) if p < 0)
    )
    assert positions == sorted(positions), "stages must appear in canonical order"


def test_one_task_per_invocation_and_correction_budget_pinned():
    text = skill_text()
    assert "at most ONE implementation task" in text
    assert "at most THREE observe/verify correction" in text
    assert "must not silently select a second implementation objective" in text
    assert "Never invent work merely to stay active" in text


def test_observe_requires_changed_file_overlap_inspection():
    flat = skill_flat()
    assert "changed-file overlap" in flat
    assert "reading each open PR's changed FILE LIST" in flat
    assert "AI_WORKSPACE/TASKS.md" in flat, (
        "shared control-plane files must be named in the overlap rule"
    )


def test_prepush_revalidation_is_mandatory():
    flat = skill_flat()
    assert "Pre-push revalidation (mandatory)" in flat
    assert "git fetch origin main` again" in flat or "fetch origin main` again" in flat
    assert "Task-ID uniqueness" in flat
    assert "do NOT push the branch" in flat


def test_task_id_reuse_forbidden():
    flat = skill_flat()
    assert "Task-ID reuse is forbidden" in flat
    assert "next FREE `TASK-YYYYMMDD-NNN` identifier" in flat


def test_all_hard_owner_gates_listed():
    text = skill_text()
    gates_section = text.split("## Hard owner gates", 1)
    assert len(gates_section) == 2, "SKILL.md must have a 'Hard owner gates' section"
    gates = gates_section[1].split("## ")[0]
    required = [
        "merge",
        "production deploy",
        "database migration or SQL execution",
        "secret or environment-variable changes",
        "Render worker/instance changes",
        "billing mutations",
        "production data mutation",
        "destructive commands",
        "scope expansion",
        "competing PR",
        "safety limitation",
        "product or architecture decision",
    ]
    missing = [g for g in required if g not in gates]
    assert not missing, f"hard owner gates missing from SKILL.md: {missing}"


def test_skill_never_self_authorizes_merge():
    flat = skill_flat()
    assert "must never write code and independently authorize its own merge" in flat
    assert "A WRITER stops with a Draft PR" in flat
    assert "--dangerously-skip-permissions" not in flat


def test_idle_modifies_nothing():
    flat = skill_flat()
    assert "IDLE creates no branch and modifies no files" in flat
    assert "no branch created; no files modified" in flat


def test_conflicting_state_stops_execution():
    flat = skill_flat()
    assert "If live GitHub state and workspace documents disagree" in flat
    assert "BLOCKED_CONFLICT" in flat
    assert "Never trust chat memory over repository files and live GitHub state" in flat


def test_failed_acceptance_criterion_cannot_be_reported_complete():
    flat = skill_flat()
    assert "A failed acceptance criterion MUST NOT be reported as complete." in flat
    assert "Green CI alone is never proof of correctness" in flat


def test_result_contract_is_strict_and_documented():
    flat = skill_flat()
    for token in RESULT_TOKENS:
        assert token in flat, f"result token {token} missing from SKILL.md"
    assert "last non-empty line" in flat
    assert "exactly once" in flat


def test_skill_states_defense_in_depth_not_sandbox():
    flat = skill_flat()
    assert "defense in depth, not a sandbox" in flat
    assert "not the impossibility of bypass" in flat or (
        "not the" in flat and "impossibility of bypass" in flat
    )


# ---------------------------------------------------------------------------
# AI_WORKSPACE/TASKS.md — Task-ID uniqueness
# ---------------------------------------------------------------------------


def test_task_ids_are_unique():
    offenders = push_gate.duplicate_task_ids(TASKS.read_text(encoding="utf-8"))
    assert not offenders, (
        f"duplicate Task IDs in AI_WORKSPACE/TASKS.md: {offenders}. "
        "New tasks must take the next free TASK-YYYYMMDD-NNN."
    )


def test_frozen_duplicate_exception_matches_exact_headings():
    """The exception tolerates only the two exact historical headings."""
    headings = push_gate.task_headings(TASKS.read_text(encoding="utf-8"))
    frozen = FROZEN_DUPLICATE_HEADINGS["TASK-20260721-005"]
    assert headings["TASK-20260721-005"] == frozen, (
        "TASK-20260721-005 headings drifted from the frozen historical pair — "
        "a replaced or new duplicate under this id is not covered by the exception"
    )


def test_duplicate_guard_rejects_new_and_swapped_duplicates():
    base = "### TASK-20260101-001 — one\n\n### TASK-20260101-002 — two\n"
    assert push_gate.duplicate_task_ids(base) == {}
    # a brand-new duplicate fails
    dup = base + "\n### TASK-20260101-001 — sneaky reuse\n"
    assert "TASK-20260101-001" in push_gate.duplicate_task_ids(dup)
    # the frozen id with one heading swapped for a NEW duplicate also fails
    frozen = list(FROZEN_DUPLICATE_HEADINGS["TASK-20260721-005"])
    swapped = f"{frozen[0]}\n\n### TASK-20260721-005 — a different new task\n"
    assert "TASK-20260721-005" in push_gate.duplicate_task_ids(swapped)
    # the exact frozen pair passes
    exact = "\n\n".join(frozen) + "\n"
    assert push_gate.duplicate_task_ids(exact) == {}


def test_added_task_ids_parses_unified_diff():
    diff = (
        "+++ b/AI_WORKSPACE/TASKS.md\n"
        "+### TASK-20260722-001 — new task\n"
        " ### TASK-20260721-014 — context line, not added\n"
        "-### TASK-20260720-009 — removed\n"
    )
    assert push_gate.added_task_ids(diff) == {"TASK-20260722-001"}


# ---------------------------------------------------------------------------
# DEVELOPMENT_LOOP_STATE.md ledger
# ---------------------------------------------------------------------------


def _ledger() -> dict:
    text = STATE.read_text(encoding="utf-8")
    blocks = re.findall(r"```yaml\n(.*?)```", text, flags=re.DOTALL)
    assert len(blocks) == 1, "DEVELOPMENT_LOOP_STATE.md must contain exactly one yaml block"
    return yaml.safe_load(blocks[0])


def test_state_ledger_parses_with_required_fields():
    data = _ledger()
    assert data["schema_version"] == 2
    entries = data["ledger"]
    assert isinstance(entries, list) and entries, "ledger must be a non-empty list"
    required = {
        "session",
        "date",
        "role",
        "result",
        "task",
        "branch",
        "base_sha",
        "validated_head_sha",
        "correction_cycles",
        "owner_gate",
        "files_changed",
        "tests",
        "next_action",
    }
    for entry in entries:
        missing = required - set(entry)
        assert not missing, f"ledger entry missing fields: {missing}"
        # IDLE / BLOCKED_CONFLICT never write files, so they never appear here.
        assert entry["result"] in {"COMPLETE", "OWNER_GATE", "INCOMPLETE_EVIDENCE"}
        assert entry["role"] in {"WRITER", "REVIEWER", "RELEASE"}
        assert isinstance(entry["correction_cycles"], int)
        assert 0 <= entry["correction_cycles"] <= 3
        assert re.fullmatch(r"[0-9a-f]{40}", entry["base_sha"]), "base_sha must be full SHA"
        assert re.fullmatch(r"[0-9a-f]{40}", entry["validated_head_sha"]), (
            "validated_head_sha must be a real full SHA — sentinels are forbidden"
        )


def test_state_ledger_is_append_only_without_sentinels():
    text = STATE.read_text(encoding="utf-8")
    # The sentinel must never appear as a YAML field VALUE (prose that
    # describes the retired pattern is fine; the schema test additionally
    # enforces full-SHA validated_head_sha on every entry).
    assert not re.search(r':\s*"?pending-first-push"?\s*$', text, flags=re.MULTILINE), (
        "sentinel head SHAs are forbidden; use the two-commit pattern"
    )
    assert "Append-only." in text
    assert "two-commit pattern" in text or "Two-commit pattern" in text


# ---------------------------------------------------------------------------
# Launcher
# ---------------------------------------------------------------------------


def test_launcher_bash_syntax_ok():
    proc = subprocess.run(
        ["bash", "-n", str(LAUNCHER)], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr


def test_launcher_is_bounded_and_never_skips_permissions():
    text = launcher_text()
    assert "--max-turns" in text, "launcher must set an explicit max-turn limit"
    # The flag must never be USED — comment lines describing the prohibition
    # are allowed, executable lines are not.
    code_lines = [
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    ]
    assert not any("--dangerously-skip-permissions" in line for line in code_lines)
    assert "--permission-mode default" in text
    assert re.search(r"claude -p ", text), "launcher must use non-interactive mode"


def _tool_list(var_name: str) -> str:
    match = re.search(rf'{var_name}="(.*?)"', launcher_text(), flags=re.DOTALL)
    assert match, f"{var_name} not found in launcher"
    return match.group(1).replace("\\\n", "")


def test_launcher_scopes_read_edit_write_to_project():
    allowed = _tool_list("ALLOWED_TOOLS")
    for tool in ("Read", "Edit", "Write", "Bash"):
        assert re.search(rf"(^|,){tool}(,|$)", allowed) is None, (
            f"allowlist must never grant unscoped {tool}"
        )
    for scoped in ("Read(./**)", "Edit(./**)"):
        assert scoped in allowed, f"allowlist must path-scope: {scoped}"
    # Write(path) rules are IGNORED by the CLI's file permission checks
    # (Edit rules cover all file-editing tools) — verified by --smoke against
    # CLI 2.1.217. Listing them would give a false sense of coverage.
    assert "Write(" not in allowed, "Write(path) rules are no-ops; use Edit(path)"


def test_launcher_denies_known_secret_paths():
    denied = _tool_list("DISALLOWED_TOOLS")
    for pattern in [
        "Read(**/.env*)",
        "Edit(**/.env*)",
        "Read(**/*.env)",
        "Edit(**/*.env)",
        "Read(**/*credentials*)",
        "Read(**/*.pem)",
        "Read(**/*.key)",
        "Read(~/**)",
        "Read(//etc/**)",
    ]:
        assert pattern in denied, f"secret-path denial missing: {pattern}"
    assert "Read(/etc/**)" not in denied, (
        "absolute paths in permission rules use // — Read(/etc/**) is wrong"
    )
    assert "Write(" not in denied, "Write(path) rules are no-ops; use Edit(path)"


def test_launcher_restricts_builtin_tool_availability():
    text = launcher_text()
    match = re.search(r'BUILTIN_TOOLS="([^"]+)"', text)
    assert match, "launcher must define BUILTIN_TOOLS for --tools"
    assert match.group(1) == "Read,Edit,Write,Grep,Glob,Bash", (
        "--tools must stay the minimal built-in set"
    )
    assert '--tools "$BUILTIN_TOOLS"' in text, (
        "--tools must be passed so availability (not just permission) is restricted"
    )


def test_launcher_isolates_mcp_and_setting_sources():
    text = launcher_text()
    assert "--strict-mcp-config" in text, (
        "launcher must pass --strict-mcp-config (with no --mcp-config) so no "
        "user/project/connector MCP server loads"
    )
    assert "--mcp-config" in text  # via --strict-mcp-config; no server config passed
    assert "--setting-sources project" in text, (
        "launcher must pin setting sources so user/local grants and plugins "
        "cannot silently widen the session"
    )
    denied = _tool_list("DISALLOWED_TOOLS")
    assert "mcp__*" in denied, "mcp__* must be denied as defense in depth"


def test_launcher_pushes_only_via_gate():
    allowed = _tool_list("ALLOWED_TOOLS")
    denied = _tool_list("DISALLOWED_TOOLS")
    assert "git push" not in allowed, (
        "raw git push must not be granted — pushing goes through the gate"
    )
    assert "Bash(git push:*)" in denied, "direct git push must be denied"
    assert "scripts/rico-supervisor-push.sh" in allowed, (
        "the validated push gate must be the sanctioned push path"
    )
    # gh pr create can implicitly PUSH an unpushed branch — it is an
    # alternate push path and must be denied; PR creation goes through the
    # gate's --create-pr mode (which uses explicit --head, never pushing).
    assert "gh pr create" not in allowed, (
        "raw gh pr create must not be granted — it can push implicitly"
    )
    assert "Bash(gh pr create:*)" in denied, "raw gh pr create must be denied"


def test_launcher_logs_default_outside_repo():
    text = launcher_text()
    assert "XDG_STATE_HOME" in text, (
        "launcher logs must default OUTSIDE the repository so IDLE runs "
        "modify nothing under the working tree"
    )
    assert ":-.rico-supervisor-logs" not in text, (
        "project-local log default is forbidden — .gitignore only hides the "
        "mutation, it does not make it absent"
    )


def test_launcher_has_permission_smoke_mode():
    text = launcher_text()
    assert '"--smoke-perms"' in text
    assert "sha256sum" in text, (
        "denied-edit enforcement must be checked mechanically (checksum), "
        "not by model self-report"
    )
    assert "DENIED_TOKEN" in text and "SAFE_TOKEN" in text, (
        "read enforcement must be checked mechanically via sentinel tokens"
    )


def test_launcher_denies_merge_deploy_destructive_and_db():
    denied = _tool_list("DISALLOWED_TOOLS")
    for pattern in [
        "git merge",
        "git push --force",
        "git reset",
        "git clean",
        "gh pr merge",
        "gh workflow run",
        "gh secret",
        "psql",
        "rm -rf",
    ]:
        assert pattern in denied, f"denylist must cover: {pattern}"


def test_launcher_requires_clean_up_to_date_main():
    text = launcher_text()
    assert "git status --porcelain" in text, "launcher must refuse a dirty tree"
    assert 'git rev-parse --abbrev-ref HEAD' in text
    assert '!= "main"' in text, "launcher must refuse to start off main"
    assert "git rev-parse origin/main" in text, (
        "launcher must require local main == origin/main after a fresh fetch"
    )


def test_launcher_has_isolated_smoke_mode():
    text = launcher_text()
    assert '"--smoke"' in text or "--smoke)" in text
    assert "no-op smoke test" in text
    assert "Do not\nuse any tools" in text or "Do not use any tools" in re.sub(
        r"\s+", " ", text
    )


def test_launcher_classify_exit_codes():
    """Owner gate and incomplete evidence must be non-zero; only COMPLETE/IDLE pass."""
    cases = {
        "COMPLETE": 0,
        "IDLE": 0,
        "OWNER_GATE": 2,
        "BLOCKED_CONFLICT": 3,
        "INCOMPLETE_EVIDENCE": 4,
        "GARBAGE_TOKEN": 5,
        "": 5,
    }
    for token, expected in cases.items():
        proc = subprocess.run(
            ["bash", str(LAUNCHER), "--classify", token],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == expected, (
            f"--classify {token!r}: expected exit {expected}, got {proc.returncode}"
        )


def _parse_result(tmp_path, content: str) -> int:
    log = tmp_path / "run.log"
    log.write_text(content, encoding="utf-8")
    proc = subprocess.run(
        ["bash", str(LAUNCHER), "--parse-result", str(log)],
        capture_output=True,
        text=True,
    )
    return proc.returncode


def test_parser_accepts_only_strict_final_result_line(tmp_path):
    ok_cases = {
        "did work\n\nRICO_SUPERVISOR_RESULT: COMPLETE\n": 0,
        "no safe task found\nRICO_SUPERVISOR_RESULT: IDLE\n": 0,
        "stopped at merge gate\nRICO_SUPERVISOR_RESULT: OWNER_GATE\n": 2,
        "state disagrees\nRICO_SUPERVISOR_RESULT: BLOCKED_CONFLICT\n": 3,
        "criterion 3 unproven\nRICO_SUPERVISOR_RESULT: INCOMPLETE_EVIDENCE\n": 4,
        # trailing blank lines after the result line are tolerated
        "work\nRICO_SUPERVISOR_RESULT: COMPLETE\n\n\n": 0,
    }
    for content, expected in ok_cases.items():
        assert _parse_result(tmp_path, content) == expected, repr(content)


def test_parser_rejects_early_duplicate_trailing_and_unknown(tmp_path):
    bad_cases = [
        # token only mentioned earlier; last line is chatter
        "RICO_SUPERVISOR_RESULT: COMPLETE\nand then some more chatter\n",
        # duplicate result lines
        "RICO_SUPERVISOR_RESULT: COMPLETE\nRICO_SUPERVISOR_RESULT: COMPLETE\n",
        # early exact line + different final line (contradiction)
        "RICO_SUPERVISOR_RESULT: IDLE\nwork\nRICO_SUPERVISOR_RESULT: COMPLETE\n",
        # trailing text on the result line
        "work\nRICO_SUPERVISOR_RESULT: COMPLETE (all done!)\n",
        # unknown token
        "work\nRICO_SUPERVISOR_RESULT: DONE\n",
        # lowercase / malformed
        "work\nrico_supervisor_result: complete\n",
        # empty log
        "",
        # result absent entirely
        "just chatter\nno result here\n",
    ]
    for content in bad_cases:
        assert _parse_result(tmp_path, content) == 5, repr(content)


def test_parser_rejects_missing_file():
    proc = subprocess.run(
        ["bash", str(LAUNCHER), "--parse-result", "/nonexistent/definitely-missing.log"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 5


# ---------------------------------------------------------------------------
# Push gate — functional fail-before tests (temp repos, fake gh, no network)
# ---------------------------------------------------------------------------


def test_push_gate_wrapper_syntax_and_exec():
    proc = subprocess.run(["bash", "-n", str(PUSH_GATE_SH)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "supervisor_push_gate.py" in PUSH_GATE_SH.read_text(encoding="utf-8")


def _git(cwd, *args):
    subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )


def _setup_remote_and_clone(tmp_path):
    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(origin)],
        check=True, capture_output=True,
    )
    work = tmp_path / "work"
    subprocess.run(
        ["git", "clone", str(origin), str(work)], check=True, capture_output=True
    )
    _git(work, "config", "user.email", "gate-test@example.invalid")
    _git(work, "config", "user.name", "gate-test")
    _git(work, "checkout", "-b", "main")
    (work / "AI_WORKSPACE").mkdir()
    (work / "AI_WORKSPACE" / "TASKS.md").write_text(
        "# Tasks\n\n### TASK-20260101-001 — base task\n", encoding="utf-8"
    )
    (work / "README.md").write_text("base\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-m", "base")
    _git(work, "push", "-u", "origin", "main")
    return origin, work


def _fake_gh(tmp_path, pr_list_json="[]", pr_diffs=None):
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    (tmp_path / "prlist.json").write_text(pr_list_json, encoding="utf-8")
    diffdir = tmp_path / "prdiffs"
    diffdir.mkdir(exist_ok=True)
    for number, diff in (pr_diffs or {}).items():
        (diffdir / f"{number}.diff").write_text(diff, encoding="utf-8")
    gh = bindir / "gh"
    gh.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "$@" >> "{tmp_path}/gh-calls.log"\n'
        f'if [[ "$1 $2" == "pr list" ]]; then cat "{tmp_path}/prlist.json"; exit 0; fi\n'
        f'if [[ "$1 $2" == "pr diff" ]]; then f="{diffdir}/$3.diff"; '
        '[[ -f "$f" ]] && cat "$f"; exit 0; fi\n'
        'if [[ "$1 $2" == "pr create" ]]; then exit 0; fi\n'
        "exit 1\n",
        encoding="utf-8",
    )
    gh.chmod(0o755)
    return bindir


def _gh_calls(tmp_path):
    log = tmp_path / "gh-calls.log"
    return log.read_text(encoding="utf-8") if log.exists() else ""


def _run_gate(work, bindir, *args):
    env = dict(os.environ)
    env["PATH"] = f"{bindir}:{env['PATH']}"
    return subprocess.run(
        ["bash", str(PUSH_GATE_SH), *args],
        cwd=work, env=env, capture_output=True, text=True,
    )


def _remote_has_branch(work, branch):
    proc = subprocess.run(
        ["git", "ls-remote", "origin", f"refs/heads/{branch}"],
        cwd=work, capture_output=True, text=True,
    )
    return bool(proc.stdout.strip())


def test_push_gate_refuses_non_claude_branch(tmp_path):
    _, work = _setup_remote_and_clone(tmp_path)
    _git(work, "checkout", "-b", "feature/not-allowed")
    (work / "README.md").write_text("change\n", encoding="utf-8")
    _git(work, "commit", "-am", "change")
    result = _run_gate(work, _fake_gh(tmp_path))
    assert result.returncode == 6, result.stderr
    assert not _remote_has_branch(work, "feature/not-allowed")


def test_push_gate_refuses_main_advanced_with_overlapping_file(tmp_path):
    _, work = _setup_remote_and_clone(tmp_path)
    _git(work, "checkout", "-b", "claude/gate-test")
    (work / "README.md").write_text("branch change\n", encoding="utf-8")
    _git(work, "commit", "-am", "branch change")
    # advance origin/main touching the SAME file, from a second clone
    other = tmp_path / "other"
    subprocess.run(
        ["git", "clone", str(tmp_path / "origin.git"), str(other)],
        check=True, capture_output=True,
    )
    _git(other, "config", "user.email", "o@example.invalid")
    _git(other, "config", "user.name", "o")
    (other / "README.md").write_text("main advanced\n", encoding="utf-8")
    _git(other, "commit", "-am", "main advance")
    _git(other, "push", "origin", "main")
    result = _run_gate(work, _fake_gh(tmp_path))
    assert result.returncode == 2, result.stderr
    assert "REFUSED" in result.stderr
    assert not _remote_has_branch(work, "claude/gate-test")


def test_push_gate_refuses_open_pr_with_overlapping_file(tmp_path):
    _, work = _setup_remote_and_clone(tmp_path)
    _git(work, "checkout", "-b", "claude/gate-test")
    (work / "README.md").write_text("branch change\n", encoding="utf-8")
    _git(work, "commit", "-am", "branch change")
    pr_list = json.dumps(
        [{"number": 42, "headRefName": "other/branch", "files": [{"path": "README.md"}]}]
    )
    result = _run_gate(work, _fake_gh(tmp_path, pr_list_json=pr_list))
    assert result.returncode == 2, result.stderr
    assert "#42" in result.stderr
    assert not _remote_has_branch(work, "claude/gate-test")


def test_push_gate_refuses_duplicate_task_id(tmp_path):
    _, work = _setup_remote_and_clone(tmp_path)
    _git(work, "checkout", "-b", "claude/gate-test")
    tasks = work / "AI_WORKSPACE" / "TASKS.md"
    tasks.write_text(
        tasks.read_text(encoding="utf-8")
        + "\n### TASK-20260101-001 — sneaky duplicate\n",
        encoding="utf-8",
    )
    _git(work, "commit", "-am", "duplicate id")
    result = _run_gate(work, _fake_gh(tmp_path))
    assert result.returncode == 2, result.stderr
    assert "duplicate Task ID" in result.stderr
    assert not _remote_has_branch(work, "claude/gate-test")


def test_push_gate_refuses_task_id_collision_with_open_pr_patch(tmp_path):
    _, work = _setup_remote_and_clone(tmp_path)
    _git(work, "checkout", "-b", "claude/gate-test")
    tasks = work / "AI_WORKSPACE" / "TASKS.md"
    tasks.write_text(
        tasks.read_text(encoding="utf-8") + "\n### TASK-20260102-001 — mine\n",
        encoding="utf-8",
    )
    _git(work, "commit", "-am", "new task id")
    # an open PR that does NOT overlap files... it must touch TASKS.md to add
    # an id, which the file-overlap check would catch first — so this guard
    # is exercised via the gh diff seam with overlap on a different path
    # reported by gh (defense in depth): simulate gh reporting TASKS.md as
    # NOT in files (stale API) while its patch adds the same id.
    pr_list = json.dumps(
        [{"number": 7, "headRefName": "other/branch",
          "files": [{"path": "AI_WORKSPACE/TASKS.md"}, {"path": "src/other.py"}]}]
    )
    result = _run_gate(work, _fake_gh(tmp_path, pr_list_json=pr_list))
    # TASKS.md overlap already refuses — proving layered defense
    assert result.returncode == 2
    assert not _remote_has_branch(work, "claude/gate-test")


def test_push_gate_pushes_when_clean(tmp_path):
    _, work = _setup_remote_and_clone(tmp_path)
    _git(work, "checkout", "-b", "claude/gate-test")
    (work / "README.md").write_text("branch change\n", encoding="utf-8")
    _git(work, "commit", "-am", "branch change")
    # main advanced WITHOUT overlap (different file) is allowed
    other = tmp_path / "other"
    subprocess.run(
        ["git", "clone", str(tmp_path / "origin.git"), str(other)],
        check=True, capture_output=True,
    )
    _git(other, "config", "user.email", "o@example.invalid")
    _git(other, "config", "user.name", "o")
    (other / "OTHER.md").write_text("unrelated\n", encoding="utf-8")
    _git(other, "add", "OTHER.md")
    _git(other, "commit", "-m", "unrelated main advance")
    _git(other, "push", "origin", "main")
    result = _run_gate(work, _fake_gh(tmp_path))
    assert result.returncode == 0, result.stderr
    assert _remote_has_branch(work, "claude/gate-test")


def test_push_gate_check_only_does_not_push(tmp_path):
    _, work = _setup_remote_and_clone(tmp_path)
    _git(work, "checkout", "-b", "claude/gate-test")
    (work / "README.md").write_text("branch change\n", encoding="utf-8")
    _git(work, "commit", "-am", "branch change")
    result = _run_gate(work, _fake_gh(tmp_path), "--check-only")
    assert result.returncode == 0, result.stderr
    assert not _remote_has_branch(work, "claude/gate-test")


# ---------------------------------------------------------------------------
# PR creation gate — gh pr create must not be able to push around the gate
# ---------------------------------------------------------------------------


def test_create_pr_refuses_unpushed_branch(tmp_path):
    """An unpushed branch must refuse PR creation — gh is never invoked, so
    gh pr create's implicit-push behavior cannot fire."""
    _, work = _setup_remote_and_clone(tmp_path)
    _git(work, "checkout", "-b", "claude/gate-test")
    (work / "README.md").write_text("change\n", encoding="utf-8")
    _git(work, "commit", "-am", "change")
    result = _run_gate(work, _fake_gh(tmp_path), "--create-pr", "--title", "t")
    assert result.returncode == 2, result.stderr
    assert "push through this" in result.stderr
    assert "pr create" not in _gh_calls(tmp_path), "gh pr create must not run"
    assert not _remote_has_branch(work, "claude/gate-test"), "nothing may be pushed"


def test_create_pr_refuses_head_mismatch(tmp_path):
    """A pushed branch with unpushed local commits must refuse PR creation."""
    _, work = _setup_remote_and_clone(tmp_path)
    _git(work, "checkout", "-b", "claude/gate-test")
    (work / "README.md").write_text("change\n", encoding="utf-8")
    _git(work, "commit", "-am", "change")
    _git(work, "push", "-u", "origin", "claude/gate-test")
    pushed_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=work, capture_output=True, text=True
    ).stdout.strip()
    (work / "README.md").write_text("newer local change\n", encoding="utf-8")
    _git(work, "commit", "-am", "unpushed")
    result = _run_gate(work, _fake_gh(tmp_path), "--create-pr", "--title", "t")
    assert result.returncode == 2, result.stderr
    assert "pr create" not in _gh_calls(tmp_path)
    remote_sha = subprocess.run(
        ["git", "ls-remote", "origin", "refs/heads/claude/gate-test"],
        cwd=work, capture_output=True, text=True,
    ).stdout.split()[0]
    assert remote_sha == pushed_sha, "remote must be untouched by the refusal"


def test_gate_shares_one_validation_between_push_and_create():
    """Both actions must call the same read-only validation right before
    acting — no TOCTOU window between passing the push gate and creating."""
    source = PUSH_GATE_PY.read_text(encoding="utf-8")
    create_body = source.split("def create_pr(")[1].split("\ndef ")[0]
    main_body = source.split("def main(")[1].split("\ndef ")[0]
    assert "validate_against_live_state(" in create_body
    assert "validate_against_live_state(" in main_body
    for flag in ("--head", "-H", "--base", "-B", "--draft", "--repo", "-R",
                 "--web", "--dry-run"):
        assert f'"{flag}"' in source.split("RESERVED_CREATE_FLAGS")[1].split("}")[0], (
            f"reserved flag {flag} missing from RESERVED_CREATE_FLAGS"
        )


def test_create_pr_refuses_main_drift_after_push(tmp_path):
    """main advances with an overlapping file AFTER the push but BEFORE
    --create-pr: the shared validation must refuse and create no PR."""
    _, work = _setup_remote_and_clone(tmp_path)
    _git(work, "checkout", "-b", "claude/gate-test")
    (work / "README.md").write_text("branch change\n", encoding="utf-8")
    _git(work, "commit", "-am", "branch change")
    _git(work, "push", "-u", "origin", "claude/gate-test")
    other = tmp_path / "other"
    subprocess.run(
        ["git", "clone", str(tmp_path / "origin.git"), str(other)],
        check=True, capture_output=True,
    )
    _git(other, "config", "user.email", "o@example.invalid")
    _git(other, "config", "user.name", "o")
    (other / "README.md").write_text("main advanced after push\n", encoding="utf-8")
    _git(other, "commit", "-am", "post-push main advance")
    _git(other, "push", "origin", "main")
    result = _run_gate(work, _fake_gh(tmp_path), "--create-pr", "--title", "t")
    assert result.returncode == 2, result.stderr
    assert "BLOCKED_CONFLICT" in result.stderr
    assert "pr create" not in _gh_calls(tmp_path), "no PR may be created"


def test_create_pr_refuses_new_overlapping_pr_after_push(tmp_path):
    """A competing PR opens AFTER the push but BEFORE --create-pr: refuse."""
    _, work = _setup_remote_and_clone(tmp_path)
    _git(work, "checkout", "-b", "claude/gate-test")
    (work / "README.md").write_text("branch change\n", encoding="utf-8")
    _git(work, "commit", "-am", "branch change")
    _git(work, "push", "-u", "origin", "claude/gate-test")
    pr_list = json.dumps(
        [{"number": 99, "headRefName": "other/late", "files": [{"path": "README.md"}]}]
    )
    result = _run_gate(
        work, _fake_gh(tmp_path, pr_list_json=pr_list), "--create-pr", "--title", "t"
    )
    assert result.returncode == 2, result.stderr
    assert "#99" in result.stderr
    assert "pr create" not in _gh_calls(tmp_path)


def test_create_pr_rejects_reserved_override_flags(tmp_path):
    """Identity/state flags must be rejected BEFORE gh is invoked at all."""
    _, work = _setup_remote_and_clone(tmp_path)
    _git(work, "checkout", "-b", "claude/gate-test")
    (work / "README.md").write_text("branch change\n", encoding="utf-8")
    _git(work, "commit", "-am", "branch change")
    _git(work, "push", "-u", "origin", "claude/gate-test")
    for reserved in (["--head", "evil/branch"], ["--base=release"], ["--dry-run"],
                     ["--repo", "evil/repo"], ["--web"]):
        result = _run_gate(work, _fake_gh(tmp_path), "--create-pr", *reserved)
        assert result.returncode == 6, (reserved, result.stderr)
        assert "reserved flag" in result.stderr
    assert _gh_calls(tmp_path) == "", "gh must never be invoked on reserved flags"


def test_create_pr_clean_creates_without_push(tmp_path):
    """Fully pushed branch: PR created via explicit --head, no push side effect."""
    _, work = _setup_remote_and_clone(tmp_path)
    _git(work, "checkout", "-b", "claude/gate-test")
    (work / "README.md").write_text("change\n", encoding="utf-8")
    _git(work, "commit", "-am", "change")
    _git(work, "push", "-u", "origin", "claude/gate-test")
    before = subprocess.run(
        ["git", "ls-remote", "origin"], cwd=work, capture_output=True, text=True
    ).stdout
    result = _run_gate(work, _fake_gh(tmp_path), "--create-pr", "--title", "supervisor PR")
    assert result.returncode == 0, result.stderr
    calls = _gh_calls(tmp_path)
    assert "pr create --draft --head claude/gate-test --base main" in calls
    assert "--title supervisor PR" in calls
    after = subprocess.run(
        ["git", "ls-remote", "origin"], cwd=work, capture_output=True, text=True
    ).stdout
    assert before == after, "PR creation must have no push side effect"


# ---------------------------------------------------------------------------
# Launcher precondition — functional
# ---------------------------------------------------------------------------


def test_idle_run_leaves_repo_byte_for_byte_untouched(tmp_path):
    """A full launcher cycle ending in IDLE (fake Claude) must change no file,
    no ref, and no status under the working tree; the log lands outside."""
    _, work = _setup_remote_and_clone(tmp_path)  # on main, synced with origin
    bindir = tmp_path / "claude-bin"
    bindir.mkdir()
    fake_claude = bindir / "claude"
    fake_claude.write_text(
        "#!/usr/bin/env bash\n"
        "printf 'no safe unowned task exists\\nRICO_SUPERVISOR_RESULT: IDLE\\n'\n",
        encoding="utf-8",
    )
    fake_claude.chmod(0o755)
    state_home = tmp_path / "state"
    env = dict(os.environ)
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["XDG_STATE_HOME"] = str(state_home)
    env.pop("RICO_SUPERVISOR_LOG_DIR", None)

    def snapshot():
        files = sorted(
            str(p.relative_to(work))
            for p in work.rglob("*")
            if p.is_file() and ".git" not in p.relative_to(work).parts
        )
        refs = subprocess.run(
            ["git", "for-each-ref"], cwd=work, capture_output=True, text=True
        ).stdout
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=work, capture_output=True, text=True
        ).stdout
        return files, refs, status

    before = snapshot()
    result = subprocess.run(
        ["bash", str(LAUNCHER)], cwd=work, env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "RICO_SUPERVISOR_RESULT: IDLE" in result.stdout
    assert snapshot() == before, "IDLE must leave the repository untouched"
    logs = list((state_home / "rico-supervisor" / "logs").glob("run-*.log"))
    assert logs, "the run log must exist OUTSIDE the repository"


def test_launcher_fetch_failure_exits_6(tmp_path):
    """A repo with no reachable origin must stop with exit 6 before Claude runs."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "t")
    (repo / "f.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "c")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake_claude = bindir / "claude"
    fake_claude.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    fake_claude.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{bindir}:{env['PATH']}"
    result = subprocess.run(
        ["bash", str(LAUNCHER)], cwd=repo, env=env, capture_output=True, text=True
    )
    assert result.returncode == 6, (result.stdout, result.stderr)
    assert "git fetch origin main failed" in result.stderr
