---
name: refresh-guidelines
description: Enriches CLAUDE.md generation guidelines from curated Anthropic docs, community guides, and /insights session data. Produces docs/CLAUDE-MD-SOTA.md (web sources) and docs/CLAUDE-MD-SOTA.enriched.md (/insights merged). Invoke explicitly; has file-write and network side effects.
disable-model-invocation: true
allowed-tools: Bash, Read, WebSearch, WebFetch, Write
---

# /refresh-guidelines

Populate or update the CLAUDE.md generation reference from dual sources: web-sourced best practices and `/insights` tips. Produces two files:

- **`docs/CLAUDE-MD-SOTA.md`** (seed, git-tracked) — Web-sourced content only (Tiers 1-3). Shipped with the repo.
- **`docs/CLAUDE-MD-SOTA.enriched.md`** (gitignored) — Seed + `/insights` data merged. User-specific, produced locally.

Use the enriched version when writing CLAUDE.md files; fall back to the seed when unavailable.

## When to Use

- **First run**: Seed is blank — populates the full 5-part structure from web sources.
- **Subsequent runs**: Merges new content from updated sources, deduplicates, and flags conflicts.
- **After running `/insights`**: When the user has fresh `/insights` data to integrate into the enriched version.
- **After adding manual tips**: When `docs/insights-raw.md` has new supplementary entries.

## Prerequisites

- Python 3.10+ available on PATH.
- Network access for fetching web sources (partial results on failure).
- `~/.claude/usage-data/` accessible (for `/insights` report parsing — optional, script degrades gracefully if missing).

## Procedure

Follow these steps in order. Do NOT skip steps or auto-approve — human review is required.

### Step -1 (optional): Preview mode

If the user invoked the skill with `--preview` (e.g., `/refresh-guidelines --preview`):

1. Run the fetch script in dry-run mode:

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/fetch-guidelines.py" --dry-run --docs-dir docs
```

This prints the full list of sources that would be fetched (IDs, URLs, themes) without making any network requests or writing any files.

2. Run the insights parser in dry-run mode:

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/parse-insights.py" --dry-run --docs-dir docs
```

This summarises the `/insights` report (age, section count) without writing `docs/insights-parsed.json`.

3. Present the summaries in conversation:

```
## /refresh-guidelines Preview

### Sources to fetch (N total)
| ID | Source | Tier | Themes |
|----|--------|------|--------|
| T1-001 | Claude Code Memory Management | 1 | structural, content |
| ...

### /insights report
Report age: {N} days | Sections available: {N}

No files would be written. Invoke `/refresh-guidelines` (without --preview) to proceed.
```

4. **Stop. No files are written.** Inform the user they can re-invoke without `--preview` to proceed with the full pipeline.

### Step 0: Source freshness check

Run the freshness checker to identify stale or broken sources:

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/fetch-guidelines.py" --check-freshness --docs-dir docs
```

This checks each source in `curated-sources.md` for:
- **Staleness**: "Last verified" date is >30 days old or missing.
- **Reachability**: URL returns HTTP error or is unreachable.

Read `docs/freshness-report.json` and present a summary table:

```
## Source Freshness Report

| ID | Source | Last Verified | Status | Issue |
|----|--------|---------------|--------|-------|
| T1-001 | Claude Code Memory Management | 2026-02-12 | OK | — |
| T2-003 | Dometrain Guide | 2025-12-15 | STALE | 64 days since verification |
| T3-002 | Templates repo | — | BROKEN | HTTP 404 |

**Action needed**: {N} sources require attention.
```

If no sources need attention, report "All sources fresh and reachable" and proceed to Step 1.

If sources need attention:
1. For **broken** sources: Use WebSearch to find replacement URLs covering the same themes. Propose replacements with the same tier and ID.
2. For **stale but reachable** sources: Mark for "Last verified" date update after the full fetch succeeds in Step 1.
3. Present all proposed changes to `curated-sources.md` and **wait for human approval**.
4. On approval, update `curated-sources.md` with:
   - Replacement URLs and descriptions (for broken sources).
   - Updated "Last verified" dates (set to today) for successfully verified sources.
5. If the user rejects all changes, proceed with existing sources (some fetches may fail).

### Step 1: Fetch web content

Run the fetch script to collect raw content from curated web sources:

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/fetch-guidelines.py" --docs-dir docs
```

This reads `$CLAUDE_PLUGIN_ROOT/references/curated-sources.md` for URLs, fetches each source, and writes structured output to `docs/guidelines-raw.json`.

Report: number of sources fetched, any failures/warnings.

### Step 2: Parse /insights report

Run the insights parser to extract structured data from the user's `/insights` report:

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/parse-insights.py" --docs-dir docs
```

This reads `~/.claude/usage-data/report.html` (and supporting `facets/*.json` + `session-meta/*.json`), extracts 7 actionable sections (CLAUDE.md recommendations, friction points, working workflows, feature recommendations, usage patterns, future workflows, usage narrative), and writes structured output to `docs/insights-parsed.json`.

If the report is missing, inform the user and proceed with web sources only.

If the report is stale (>7 days old), warn the user: "Your /insights report is {N} days old. For the most accurate behavioral patterns, consider running `/insights` first, then re-running `/refresh-guidelines`. Proceed with current report? [y/N]"

Report: report age, number of sections parsed, any warnings.

### Step 3: Read web source data

Read `docs/guidelines-raw.json`. This contains themed content blocks extracted from each web source, organized by tier and theme.

### Step 4: Read /insights data

Read `docs/insights-parsed.json`. This contains themed content blocks extracted from the user's `/insights` report, organized by section type (CLAUDE.md recommendations, friction points, working workflows, feature recommendations, usage patterns, future workflows, usage narrative).

Also read `docs/insights-raw.md` if it exists and has content beyond the instructions header — manual tips supplement the parsed report.

If neither source has data, proceed without /insights — the document can be fully populated from web sources alone.

### Step 5: Read current CLAUDE-MD-SOTA.md

Read `docs/CLAUDE-MD-SOTA.md`. On first run this will be blank. On subsequent runs it contains the existing 6-part structure.

### Step 6: Classify incoming content

For each incoming content block from **all** sources (web + /insights parsed + /insights manual), classify against the current document using the procedure in `references/enrichment-procedure.md`:

- **Novel**: New information not present in the current document. Action: propose insertion.
- **Duplicate**: Already present (same meaning, possibly different wording). Action: skip.
- **Reinforcing**: Supports existing content with additional evidence or examples. Action: propose merge with citation.
- **Conflicting**: Contradicts existing content. Action: flag for human decision.

On first run with a blank document, all content is classified as **novel**.

Apply **source precedence** (highest to lowest):
1. Tier 1 official Anthropic docs
2. `/insights` data (source type `"insights"` — parsed report + manual tips)
3. Tier 2 community guides
4. Tier 3 community templates

See `references/enrichment-procedure.md` for the full classification and conflict resolution algorithm.

### Step 7: Produce enrichment report

Present a structured report to the user showing ALL proposed changes:

```
## Enrichment Report

### Summary
- Sources processed: {count web} web + {count insights} /insights blocks
- Novel: {count} | Duplicate: {count} | Reinforcing: {count} | Conflicting: {count}

### Proposed Changes by Section

#### Purpose & Scope
| # | Change | Source | Classification | Content Summary |
|---|--------|--------|----------------|-----------------|
| 1 | INSERT | code.claude.com/docs/en/memory (T1) | novel | ... |

#### Part 1: Structural Standards
...

#### Part 2: Content Guidelines
...

#### Part 3: Integration Guidelines
...

#### Part 4: Behavioral Patterns
...

#### Part 5: Maintenance Guidelines
...

### Conflicts Requiring Decision
| # | Existing Content | Incoming Content | Source | Recommendation |
|---|------------------|------------------|--------|----------------|
```

### Step 8: Human approval

Present the enrichment report and WAIT for explicit human approval. The user may:
- Approve all proposed changes.
- Approve selectively (accept some, reject others).
- Reject all changes.
- Request modifications before approval.

**Never auto-approve. Never merge conflicting content without explicit human decision.**

### Step 9: Apply approved changes — two-file output

On approval, write **two files**:

#### 9a. Seed file: `docs/CLAUDE-MD-SOTA.md` (git-tracked)

Contains only web-sourced content (Tiers 1-3). No `/insights` material. The target structure (under 300 lines):

- **Purpose & Scope**: Role of this document, seed/enriched model, how to use it when writing CLAUDE.md files.
- **Part 1: Structural Standards**: Size constraints, recommended sections, file hierarchy strategy, formatting rules.
- **Part 2: Content Guidelines**: What to include, what to exclude, anti-patterns.
- **Part 3: Integration Guidelines**: Hooks vs CLAUDE.md, Skills vs CLAUDE.md, Rules directory.
- **Part 4: Behavioral Patterns**: Workflow rules, coding patterns, interaction preferences.
- **Part 5: Maintenance Guidelines**: Review cadence, self-improving pattern, versioning.
- **Source Attribution**: Web URLs only, last-verified dates.

#### 9b. Enriched file: `docs/CLAUDE-MD-SOTA.enriched.md` (gitignored)

Starts from the seed content, then merges approved `/insights` content into the appropriate sections. Includes:
- All seed content.
- `/insights`-sourced additions (clearly attributed with `/insights` source tags).
- Source Attribution includes both web URLs and `/insights` references.

If no `/insights` data is available, the enriched file is not produced (the seed is sufficient).

### Step 10: Update Source Attribution

Update the Source Attribution section in both files:
- **Seed**: Web source URLs only (with tier label) + date.
- **Enriched**: Web sources + `/insights` references + date.

## References

- `$CLAUDE_PLUGIN_ROOT/references/curated-sources.md` — Tiered web source registry with URLs and theme tags.
- `$CLAUDE_PLUGIN_ROOT/references/enrichment-procedure.md` — Full classification and merge algorithm.
- `$CLAUDE_PLUGIN_ROOT/scripts/fetch-guidelines.py --check-freshness --docs-dir docs` — Produces `docs/freshness-report.json` with per-source staleness and reachability status.
- `$CLAUDE_PLUGIN_ROOT/scripts/parse-insights.py --docs-dir docs` — Extracts structured data from `/insights` report into `docs/insights-parsed.json`.

## Constraints

- Both seed and enriched files must stay **under 300 lines** each.
- All content must be **source-attributed** — nothing is invented or hardcoded.
- The **seed file** (`CLAUDE-MD-SOTA.md`) must contain **only web-sourced content** (Tiers 1-3). No `/insights` material.
- The **enriched file** (`CLAUDE-MD-SOTA.enriched.md`) merges seed + `/insights`. It is **gitignored**.
- Conflicts are **never auto-resolved** — always presented for human decision.
- The process must be **idempotent** — running /refresh-guidelines again deduplicates and merges, never duplicates.
- `docs/insights-parsed.json` is **gitignored** — regenerated on each run from the user's local `/insights` report.
- Both files are **application sub-products** — they must **never** contain hyperlinks or references to internal dev docs. Sub-products may only reference other sub-products.