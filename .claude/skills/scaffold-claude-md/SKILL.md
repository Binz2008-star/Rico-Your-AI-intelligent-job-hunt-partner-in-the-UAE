---
name: scaffold-claude-md
description: Scans project subdirectories, identifies which need CLAUDE.md files, and generates appropriate scoped content based on current CLAUDE-MD-SOTA guidelines. Uses enriched guidelines when available, falls back to seed.
disable-model-invocation: true
allowed-tools: Bash, Read, Write, Glob, Grep
---

# /scaffold-claude-md

Scan a project's directory tree, identify directories that would benefit from a scoped `CLAUDE.md`, and generate content following the current CLAUDE-MD-SOTA placement and content guidelines.

## When to Use

- After initial project setup to establish scoped CLAUDE.md files across the tree.
- When new directories have been added (new skills, modules, test suites).
- After running `/refresh-guidelines` to align existing scoped files with updated SOTA.
- When existing scoped CLAUDE.md files have drifted or been deleted.

## Prerequisites

- At least one guidelines file must exist: `docs/CLAUDE-MD-SOTA.enriched.md` (preferred) or `docs/CLAUDE-MD-SOTA.md` (seed fallback).
- A root `CLAUDE.md` must exist (provides project-wide context for scoping decisions).

## Procedure

Follow these steps in order. Do NOT skip steps or auto-approve — human review is required.

> **Scan-only mode**: If invoked with `--scan-only` (e.g., `/scaffold-claude-md --scan-only`), execute Steps 0–2 only. Present the directory assessment table and stop. Skip Steps 3–6 (draft and write). This is useful when you want to see which directories would receive CLAUDE.md files before reviewing full content drafts.

### Step 0: Load guidelines

Determine which guidelines file to use:

1. Check if `docs/CLAUDE-MD-SOTA.enriched.md` exists and is non-empty.
2. If yes, use it. If no, use `docs/CLAUDE-MD-SOTA.md` (seed).
3. Report to the user: "Using **[enriched/seed]** guidelines dated [file mtime]."

If neither file exists, abort: "No guidelines file found. Run `/refresh-guidelines` first."

Read the selected SOTA file and extract the placement and hierarchy rules — specifically the guidance on:
- File hierarchy (which levels of CLAUDE.md exist and their roles)
- Placement decisions (what scope belongs at which level)
- What content belongs in child-directory CLAUDE.md vs. root CLAUDE.md

### Step 1: Scan project

List all directories in the project tree, excluding:
- Version control (`.git/`)
- IDE/editor config (`.idea/`, `.cursor/`, `.vscode/`)
- Build artifacts (`.venv/`, `__pycache__/`, `node_modules/`, `.ruff_cache/`, `.pytest_cache/`)
- Any directories matched by `.gitignore` patterns

For each directory, note:
- Whether it already has a `CLAUDE.md`
- Number and types of files it contains
- Whether it has subdirectories

Present a summary table:

```
## Directory Scan

| Directory | Has CLAUDE.md | Files | Subdirs | Notes |
|-----------|---------------|-------|---------|-------|
| `/` | Yes | ... | ... | Root |
| `/docs/` | Yes | ... | ... | — |
| `/.claude-plugin/` | No | 4 | 0 | Plugin manifest |
```

### Step 2: Assess directories

For each directory that does NOT have a CLAUDE.md, evaluate whether it needs one using the criteria in `$CLAUDE_PLUGIN_ROOT/references/directory-assessment.md`.

Classify each as:
- **RECOMMEND** — Would meaningfully benefit from a scoped CLAUDE.md.
- **SKIP** — Covered by parent, too small, or ephemeral.
- **OPTIONAL** — Borderline; present to user for decision.

### Step 3: Read existing CLAUDE.md files

Read all existing CLAUDE.md files in the project to understand:
- What scope each currently covers.
- Whether any existing files already document child directories (making a new child CLAUDE.md redundant).
- Cross-referencing patterns in use.

### Step 4: Generate proposals

For each RECOMMEND and OPTIONAL directory, draft CLAUDE.md content:

- Follow the content guidelines extracted from the current SOTA in Step 0.
- Keep each file focused on its directory's specific concerns.
- Avoid duplicating content already present in the root or parent CLAUDE.md.
- Use the same formatting conventions as existing CLAUDE.md files in the project.
- Include: purpose (1-2 sentences), key files, conventions specific to this directory.

### Step 5: Present proposals

Present all recommendations with content previews:

```
## Scaffold Proposals

### Summary
| Directory | Assessment | Reason |
|-----------|------------|--------|
| `/.claude-plugin/` | RECOMMEND | 4 files with plugin-specific conventions |
| `/.claude/skills/` | SKIP | Covered by individual skill CLAUDE.md files |

### Proposed: `.claude-plugin/CLAUDE.md`

[full content preview]

---

### Proposed: [next directory]

[full content preview]
```

**Wait for explicit human approval.** The user may:
- Approve all proposals.
- Approve selectively (accept some, reject others).
- Request modifications to content before writing.
- Reject all proposals.

**Never auto-approve. Never write files without explicit confirmation.**

### Step 6: Write approved files

On approval:

1. Write each approved CLAUDE.md file.
2. If the root CLAUDE.md has a Project Structure section that references subdirectory CLAUDE.md files, update it to include newly created files.
3. Report what was written:

```
## Files Written

| File | Lines | Status |
|------|-------|--------|
| `.claude-plugin/CLAUDE.md` | 24 | Created |
| Root `CLAUDE.md` Project Structure | — | Updated |
```

## References

- `$CLAUDE_PLUGIN_ROOT/references/directory-assessment.md` — Criteria for evaluating whether a directory needs its own CLAUDE.md.
- `docs/CLAUDE-MD-SOTA.md` — Seed guidelines (web sources only, git-tracked).
- `docs/CLAUDE-MD-SOTA.enriched.md` — Enriched guidelines (seed + /insights, gitignored).

## Constraints

- Each generated CLAUDE.md must be **focused and concise** — scoped files should be shorter than the root.
- **Never duplicate** content already present in the root or parent CLAUDE.md.
- All content must follow the **current SOTA guidelines** — not memorized or hardcoded rules.
- The process must be **idempotent** — running again skips directories that already have adequate CLAUDE.md files.
- **Never overwrite** existing CLAUDE.md files — only create new ones. Use `/refactor-claude-md` to update existing files.
