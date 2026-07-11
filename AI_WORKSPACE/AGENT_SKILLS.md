# Rico Agent Skills Pack

> `AI_WORKSPACE/` is the source of truth for Rico. Claude memory, Obsidian, and other external notes are advisory only.
> This pack lives in `.devin/skills/rico-*` and is used by Claude, Devin, Codex, Windsurf, and GitHub MCP.

## Skills

| Skill | File | When to use |
| --- | --- | --- |
| `rico-pre-implementation-audit` | `.devin/skills/rico-pre-implementation-audit/SKILL.md` | Before any implementation; read-only audit and plan |
| `rico-writer-branch` | `.devin/skills/rico-writer-branch/SKILL.md` | Single-writer implementation; one branch, one PR, one objective |
| `rico-code-review-gate` | `.devin/skills/rico-code-review-gate/SKILL.md` | Review a PR/diff for correctness and safety |
| `rico-local-qa` | `.devin/skills/rico-local-qa/SKILL.md` | Run focused build/tests/lint without live APIs |
| `rico-release-captain` | `.devin/skills/rico-release-captain/SKILL.md` | Verify merge/release readiness |
| `rico-memory-handoff` | `.devin/skills/rico-memory-handoff/SKILL.md` | Persist task state to `AI_WORKSPACE` |
| `rico-github-mcp-ops` | `.devin/skills/rico-github-mcp-ops/SKILL.md` | Read-first GitHub MCP operations |

## Global rules

- **Source of truth:** `AI_WORKSPACE/` documents override chat history, Claude memory, Obsidian, and external notes.
- **One branch, one PR, one objective:** every implementation skill enforces this.
- **No ownerless merge/release:** no skill may authorize merge, production mutation, Neon access, env changes, or issue closure without explicit owner approval.
- **Reviewer hygiene:** every reviewer skill must label findings as `verified`, `assumption`, or `suggestion`.
- **Release hygiene:** every release skill must verify CI, changed files, reviews, rollback, and production impact.
- **MCP read-first:** the GitHub MCP skill reads before mutating and mutates only on explicit command.
- **No runtime changes:** these skills are prompts/docs; they do not modify runtime code, tests, workflows, or create automation.

## How to invoke

Use the skill name in your agent prompt, e.g.:

> "Rico writer branch for #963: implement canonical CV persistence and open a draft PR."

## Maintenance

When a skill's output is wrong, update the `SKILL.md` file in this pack and this `AI_WORKSPACE/AGENT_SKILLS.md` index. Do not override the source-of-truth `AI_WORKSPACE` documents with external notes.
