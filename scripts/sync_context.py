"""Build a deterministic Rico AI context bundle for model handoffs.

This script prints the shared AI workspace files in a stable order so the same
context can be pasted into ChatGPT, Claude, Codex, Perplexity, or PR notes.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

WORKSPACE_FILES: tuple[str, ...] = (
    "AI_WORKSPACE/PROJECT_BRIEF.md",
    "AI_WORKSPACE/ARCHITECTURE.md",
    "AI_WORKSPACE/CURRENT_STATE.md",
    "AI_WORKSPACE/TASKS.md",
    "AI_WORKSPACE/DECISIONS.md",
    "AI_WORKSPACE/PROMPT_CONTRACT.md",
    "AI_WORKSPACE/HANDOFFS/TEMPLATE.md",
    "AI_WORKSPACE/EVALS/TEMPLATE.md",
)


def read_file(relative_path: str) -> str:
    """Read a UTF-8 workspace file."""
    path = ROOT / relative_path
    if not path.exists():
        return f"<!-- Missing: {relative_path} -->\n"
    return path.read_text(encoding="utf-8")


def build_bundle() -> str:
    """Build a single markdown context bundle."""
    sections: list[str] = ["# Rico AI Context Bundle\n"]
    for relative_path in WORKSPACE_FILES:
        sections.append(f"\n---\n\n## {relative_path}\n")
        sections.append(read_file(relative_path))
    return "\n".join(sections).rstrip() + "\n"


def main() -> None:
    """Print the context bundle to stdout."""
    print(build_bundle(), end="")


if __name__ == "__main__":
    main()
