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

RESULT_TOKENS = {
    "COMPLETE",
    "IDLE",
    "OWNER_GATE",
    "BLOCKED_CONFLICT",
    "INCOMPLETE_EVIDENCE",
}

# TASK-20260721-005 was duplicated on main before this guard existed
# (lines "Command v5 PR 3" and "Bilingual agent replies"). Renumbering merged
# history is an owner decision; the guard freezes the exception and rejects
# any NEW duplicate.
KNOWN_HISTORICAL_DUPLICATE_TASK_IDS = {"TASK-20260721-005": 2}


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
    text = TASKS.read_text(encoding="utf-8")
    ids = re.findall(r"^### (TASK-\d{8}-\d{3})\b", text, flags=re.MULTILINE)
    counts = Counter(ids)
    offenders = {
        task_id: n
        for task_id, n in counts.items()
        if n > 1 and KNOWN_HISTORICAL_DUPLICATE_TASK_IDS.get(task_id) != n
    }
    assert not offenders, (
        f"duplicate Task IDs in AI_WORKSPACE/TASKS.md: {offenders}. "
        "New tasks must take the next free TASK-YYYYMMDD-NNN."
    )


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
    ]:
        assert pattern in denied, f"secret-path denial missing: {pattern}"
    assert "Write(" not in denied, "Write(path) rules are no-ops; use Edit(path)"


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
