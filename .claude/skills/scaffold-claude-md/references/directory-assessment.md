# Directory Assessment Criteria

Guidance for evaluating whether a directory needs its own scoped CLAUDE.md. Used by `/scaffold-claude-md` Step 2.

**IMPORTANT**: These criteria supplement — not replace — the placement guidance in the current CLAUDE-MD-SOTA file. Always read the SOTA's file hierarchy and placement sections first (loaded in Step 0) and apply those rules alongside the criteria below.

---

## RECOMMEND — Directory needs its own CLAUDE.md

A directory should have its own CLAUDE.md when **any** of these apply:

- **Non-obvious conventions**: Contains 3+ source files with conventions, patterns, or constraints that aren't obvious from filenames alone.
- **Scripts or tools**: Has executable scripts or CLI tools with specific usage patterns, flags, or invocation requirements.
- **Mixed tracked/generated content**: Contains both git-tracked files and generated artifacts that need classification (what's safe to delete vs. what's authoritative).
- **Coherent sub-module**: Forms a self-contained sub-module with its own structure rules, entry points, or interfaces.
- **Skill/agent/plugin directory**: Contains Claude Code extension definitions (SKILL.md, agent definitions, plugin manifests) with their own conventions.
- **Test directory**: Has test files with specific framework setup, fixture locations, naming conventions, or run instructions distinct from the project root.

## SKIP — Directory does NOT need its own CLAUDE.md

A directory should be skipped when **any** of these apply:

- **Auto-generated or ephemeral**: Contents are entirely regenerated on demand (`.venv/`, `__pycache__/`, `node_modules/`, `.ruff_cache/`, `.pytest_cache/`, build output).
- **Covered by parent**: The parent's CLAUDE.md already fully documents this directory's purpose, contents, and conventions.
- **Trivially small**: Contains 1-2 files whose purpose is self-evident from their names.
- **IDE/editor config**: Dotfile directories for development tools (`.git/`, `.idea/`, `.cursor/`, `.vscode/`).
- **Empty or placeholder**: Directory exists for structure but has no meaningful content yet.

## OPTIONAL — Borderline cases

Present to the user for decision when:

- Directory has 2-3 files with some non-obvious conventions, but a single sentence in the parent CLAUDE.md might suffice.
- Directory is a leaf with no subdirectories and relatively simple contents.
- Contents are documented elsewhere (README, inline comments) but not in a CLAUDE.md.

When presenting OPTIONAL directories, include a brief rationale for and against.

---

## Content Scope for New CLAUDE.md Files

When generating content for a recommended directory, include:

1. **Purpose** — What this directory contains, in 1-2 sentences.
2. **Key files** — Table or list of important files and their roles (only if non-obvious).
3. **Directory-specific conventions** — Rules that apply here but not project-wide.
4. **Run/test instructions** — If this directory has its own commands distinct from the root.

Exclude:
- Content already in the root or parent CLAUDE.md.
- Standard conventions Claude already knows.
- File-by-file documentation (CLAUDE.md is for conventions, not a manifest).
