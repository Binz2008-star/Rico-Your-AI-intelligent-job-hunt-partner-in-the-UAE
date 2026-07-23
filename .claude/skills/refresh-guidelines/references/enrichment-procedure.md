# Enrichment Procedure

Defines the 3-phase merge algorithm Claude follows when running `/refresh-guidelines`. This ensures consistent, auditable, human-approved updates to `docs/CLAUDE-MD-SOTA.md`.

## Source Precedence

When content from multiple sources addresses the same topic, precedence determines the default winner:

| Rank | Source | Type | Rationale |
|------|--------|------|-----------|
| 1 (highest) | Tier 1: Official Anthropic docs | `T1` | Canonical authority |
| 2 | `/insights` data (parsed report + manual tips) | `insights` | Empirical data from real sessions — more authoritative than opinions |
| 3 | Tier 2: Established community guides | `T2` | Proven, named-author content |
| 4 (lowest) | Tier 3: Community templates | `T3` | Examples and patterns, not authoritative |

## Target Sections

CLAUDE-MD-SOTA.md is organized into these sections. Each incoming content block is assigned to one:

| Section | Primary sources |
|---------|----------------|
| Purpose & Scope | Generated — not source-populated |
| Part 1: Structural Standards | Web sources (T1, T2, T3) |
| Part 2: Content Guidelines | Web sources + /insights (claudemd-rec, friction) |
| Part 3: Integration Guidelines | Web sources (T1, T2) + /insights (features) |
| Part 4: Behavioral Patterns | /insights (claudemd-rec, wins, patterns, usage) + web sources |
| Part 5: Maintenance Guidelines | Web sources + /insights (patterns, horizon) |
| Source Attribution | Generated from merge metadata |

---

## Phase 1: Classification

For each incoming content block (from `guidelines-raw.json`, `insights-parsed.json`, or `insights-raw.md`), compare against the current CLAUDE-MD-SOTA.md and classify:

### Classification Labels

| Label | Condition | Action |
|-------|-----------|--------|
| **Novel** | No semantically equivalent content exists in the current document | Propose insertion into the appropriate section |
| **Duplicate** | Semantically equivalent content already present (same meaning, possibly different wording) | Skip — do not propose |
| **Reinforcing** | Supports existing content with additional evidence, examples, or nuance | Propose merge: strengthen existing content, add citation |
| **Conflicting** | Directly contradicts existing content | Flag for human decision — never auto-resolve |

### Classification Rules

1. **First run** (blank document): ALL content is classified as **novel**. Skip classification comparison.
2. **Semantic comparison**: Compare meaning, not exact wording. "Keep CLAUDE.md under 500 lines" and "Limit file size to ~500 lines" are duplicates.
3. **Scope matters**: A general statement ("use hooks for automation") and a specific one ("use hooks for pre-commit linting") are NOT duplicates — the specific one is reinforcing.
4. **Theme matching**: Use the theme tags from `curated-sources.md` to route content to the correct target section.

### Content Block Processing

For each source entry in `guidelines-raw.json`:
1. Read the `content_blocks` array.
2. For each block, identify its `theme` tag.
3. Map theme to target section: `structural` → Part 1, `content` → Part 2, `anti-patterns` → Part 2, `integration` → Part 3, `behavioral` → Part 4, `maintenance` → Part 5.
4. Compare block against existing content in that section.
5. Assign classification label.

For `/insights` parsed data in `insights-parsed.json`:
1. Read the `entries` array. Each entry has `source_id`, `tier: "insights"`, `themes`, and `content_blocks`.
2. Use the pre-assigned `theme` on each content block for section mapping.
3. Route by `source_id`:

| source_id | Primary Target | Secondary Target |
|---|---|---|
| `insights-claudemd-rec` | Part 4 (behavioral) | Part 2 (content) |
| `insights-friction` | Part 2 (anti-patterns) | Part 4 (behavioral) |
| `insights-wins` | Part 4 (behavioral) | — |
| `insights-features` | Part 3 (integration) | — |
| `insights-patterns` | Part 4 (behavioral) | Part 5 (maintenance) |
| `insights-horizon` | Part 5 (maintenance) | — |
| `insights-usage` | Part 4 (behavioral) | — |

4. Compare each block against existing content in the target section and classify.

For supplementary `/insights` tips in `insights-raw.md`:
1. Parse each tip (separated by `---` or heading boundaries).
2. Infer theme from content (behavioral patterns, workflow rules, etc.).
3. Map to target section (most /insights content maps to Part 4: Behavioral Patterns).
4. Compare and classify as above.

---

## Phase 2: Conflict Resolution

### Conflict Identification

A conflict exists when:
- Two sources make contradictory claims about the same topic.
- A new source contradicts content already in CLAUDE-MD-SOTA.md.
- An /insights tip contradicts a web-sourced guideline.

### Resolution Rules

1. **Conflicts are NEVER auto-resolved.** Always present both sides to the human.
2. **Default recommendation**: Higher-precedence source wins (per the precedence table above).
3. **Presentation format** (in the enrichment report):

```
| # | Existing Content | Incoming Content | Source | Default Winner | Recommendation |
|---|------------------|------------------|--------|----------------|----------------|
| 1 | "Keep under 500 lines" | "No hard limit, use imports" | T1-001 (T1) | Incoming (T1 > T2) | Accept incoming — official docs updated guidance |
```

4. The human can override the default recommendation in any direction.

### Edge Cases

- **Same-tier conflict**: Present both options, no default winner. Ask human to choose.
- **Partial overlap**: One source says "A and B", another says "only A". Present as conflict — human decides if B should be kept.
- **/insights vs T2 conflict**: /insights wins by default (rank 2 > rank 3), but present both.

---

## Phase 3: Integration

### Two-File Output Model

After human approval of the enrichment report, produce **two files**:

1. **Seed file** (`docs/CLAUDE-MD-SOTA.md`, git-tracked) — web-sourced content only (Tiers 1-3). No `/insights` material.
2. **Enriched file** (`docs/CLAUDE-MD-SOTA.enriched.md`, gitignored) — seed content + approved `/insights` additions. Only produced if `/insights` data is available.

### Producing the Seed File

After human approval:

1. **Start from current seed** (or blank template on first run).
2. **Apply approved web-sourced insertions** in section order.
3. **Apply approved web-sourced merges** — integrate reinforcing content into existing paragraphs/bullets.
4. **Apply approved conflict resolutions** for web-sourced conflicts — replace or adjust as directed.
5. **Skip rejected changes** and all `/insights`-sourced changes — these go to the enriched file only.
6. **Update Source Attribution** — list web sources only:
   - Web sources: `| T1-001 | T1 | https://code.claude.com/docs/en/memory | Parts 1, 2, 3, 5 | 2026-02-12 |`

### Producing the Enriched File

1. **Start from the seed file** (just written above).
2. **Apply approved `/insights` insertions** into the appropriate sections.
3. **Apply approved `/insights` merges** — integrate reinforcing content inline.
4. **Apply approved conflict resolutions** for `/insights` conflicts.
5. **Update Source Attribution** — include both web sources and `/insights` references:
   - /insights: `| /insights (parsed) | insights | ~/.claude/usage-data/report.html | Parts 2, 3, 4, 5 | 2026-02-12 |`

If no `/insights` data was available, skip this step entirely (no enriched file produced).

### First Run (Blank Seed)

When CLAUDE-MD-SOTA.md is blank, build the seed from scratch:

1. Create the 7-section skeleton (Purpose & Scope, Parts 1–5, Source Attribution).
2. Write Purpose & Scope section (static — describes the document's role and seed/enriched model).
3. Populate Parts 1–5 from approved **web-sourced** novel content only, grouped by section.
4. Within each section, order content by precedence tier (T1 first, then T2, then T3).
5. Write Source Attribution with web sources and dates.
6. Then produce the enriched file by layering `/insights` content on top (see above).

### Subsequent Runs

1. Preserve all existing seed content that was not modified.
2. Insert novel web-sourced content at the end of the relevant section.
3. Merge reinforcing web-sourced content inline with existing bullets/paragraphs.
4. Replace or adjust conflicting content per human decisions.
5. Update Source Attribution with new sources and current date.
6. Regenerate enriched file from updated seed + current `/insights` data.

### Size Constraint

The final document must stay **under 300 lines**. If the approved changes would exceed this:

1. Prioritize by tier (keep T1 content, consider trimming T3).
2. Consolidate redundant bullets into denser paragraphs.
3. Move detailed examples or elaborations to inline notes rather than full sections.
4. Report the constraint to the human and ask for guidance on what to trim.

### Quality Checks

Before writing the final document, verify:
- [ ] All 7 sections are present (Purpose & Scope, Parts 1–5, Source Attribution).
- [ ] No duplicate content within or across sections.
- [ ] All content has source attribution (no invented content).
- [ ] Under 300 lines total.
- [ ] Conflict resolutions match human decisions.
- [ ] Source Attribution lists every contributing source with tier and date.
- [ ] No references to internal dev docs — sub-products must be self-contained.