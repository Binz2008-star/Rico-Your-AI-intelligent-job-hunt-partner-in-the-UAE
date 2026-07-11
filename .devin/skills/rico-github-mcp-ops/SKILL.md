---
name: rico-github-mcp-ops
description: Read-first GitHub MCP operations for Rico Hunt. Use for triage, PR/issue metadata, and explicit commands only.
triggers:
  - user
  - model
allowed-tools:
  - read
  - grep
  - mcp1
---

# rico-github-mcp-ops

## Purpose
Read GitHub state through the GitHub MCP server. Use read-first for every operation; mutate only when the user gives an explicit command. `AI_WORKSPACE` remains the source of truth; GitHub state is advisory.

## When to use
- Check PRs, issues, branches, commits, reviews, or labels.
- Add a comment or reaction when explicitly asked.
- Create a draft PR when explicitly asked.

## Inputs required
- Repository owner and name.
- PR/issue/branch number or name.
- Operation type (read vs explicit mutation).
- For mutations: the exact action and owner approval.

## Allowed actions
- `mcp1` list/read/search operations on PRs, issues, branches, commits, reviews, comments.
- Read `PROJECT_STATUS.md` and `TASKS.md` to reconcile with live GitHub state.
- Add comments/reactions only when explicitly asked.
- Create draft PRs only when explicitly asked.
- Report results with source and uncertainty.

## Forbidden actions
- Merge, close, label, approve, assign, or delete issues/PRs without explicit command.
- Push commits, create branches, or modify files directly.
- Read private user data beyond the repo.
- Act on a mutation request without explicit confirmation.
- Overwrite `AI_WORKSPACE` source of truth with GitHub state.

## Required output format
```markdown
### GitHub MCP operation report

- **Operation:** ...
- **Inputs:** owner/repo, number/branch, command
- **Result:** ...
- **Source:** live GitHub / cached
- **Uncertainties:** ...
- **Next action:** ...
- **Stop condition:** ...
```

## Stop conditions
- The user asks for a mutation without an explicit command.
- GitHub state conflicts with `PROJECT_STATUS.md`.
- The response would expose private user data or secrets.
- The rate limit or permission check fails.

## Example prompt
"Rico GitHub MCP ops: list open PRs and check if #963 already has a branch."
