# Curated Sources Registry

Sources for populating `docs/CLAUDE-MD-SOTA.md` via `/refresh-guidelines`. Organized by precedence tier. Each entry includes theme tags that `fetch-guidelines.py` uses to classify extracted content blocks.

## Source Precedence

Higher tier = higher precedence in conflict resolution.

| Tier | Description | Conflict precedence |
|------|-------------|---------------------|
| **T1** | Official Anthropic documentation | Highest — always wins |
| **T2** | Established community guides (named authors, proven track record) | Medium |
| **T3** | Community templates and examples (GitHub repos, blog posts) | Lowest |

---

## /insights Source (Automatic)

Extracted automatically from the user's Claude Code usage report by `parse-insights.py`. Ranks between T1 and T2 in source precedence. Not a web source — not fetched by `fetch-guidelines.py`.

### Sections Extracted

| Section | Source ID | Themes | Target Part |
|---------|-----------|--------|-------------|
| CLAUDE.md Recommendations | `insights-claudemd-rec` | content, behavioral | Parts 2, 4 |
| Friction Points | `insights-friction` | anti-patterns, behavioral | Parts 2, 4 |
| Working Workflows | `insights-wins` | behavioral | Part 4 |
| Feature Recommendations | `insights-features` | integration | Part 3 |
| Usage Patterns | `insights-patterns` | behavioral, maintenance | Parts 4, 5 |
| Future Workflows | `insights-horizon` | maintenance | Part 5 |
| Usage Narrative | `insights-usage` | behavioral | Part 4 |

### Staleness Policy

- **Fresh** (<= 7 days): Parse and integrate normally.
- **Stale** (> 7 days): Warn user, suggest re-running `/insights`, proceed if user confirms.
- **Missing**: Proceed without — web sources are sufficient.

### Supplementary Manual Tips

`docs/insights-raw.md` may contain additional manually-added tips that supplement (not replace) the parsed report. These are processed after the parsed data with the same `insights` precedence.

---

## Tier 1: Official Anthropic Documentation

### T1-001: Claude Code Memory Management
- **URL**: https://code.claude.com/docs/en/memory
- **Themes**: structural, content, integration, maintenance
- **Description**: CLAUDE.md file structure, memory hierarchy, imports, project vs user vs local memory.
- **Last verified**: 2026-02-12

### T1-002: Claude Code Best Practices
- **URL**: https://code.claude.com/docs/en/best-practices
- **Themes**: content, anti-patterns, integration, behavioral
- **Description**: Context management, verification criteria, explore-then-plan workflows, prompting techniques, environment configuration.
- **Last verified**: 2026-02-12

### T1-003: Using CLAUDE.md Files (Blog)
- **URL**: https://claude.com/blog/using-claude-md-files
- **Themes**: structural, content, behavioral, maintenance
- **Description**: Customizing Claude Code for your codebase — setup, best practices, advanced techniques.
- **Last verified**: 2026-02-12

### T1-004: Claude Code GitLab CI/CD Integration
- **URL**: https://code.claude.com/docs/en/gitlab-ci-cd
- **Themes**: integration, behavioral, maintenance
- **Description**: Official Anthropic documentation for integrating Claude Code into GitLab CI/CD pipelines — headless mode, MR automation, CLAUDE.md in pipeline context.
- **Last verified**: 2026-03-06

---

## Tier 2: Established Community Guides

### T2-001: HumanLayer — Writing a Good CLAUDE.md
- **URL**: https://www.humanlayer.dev/blog/writing-a-good-claude-md
- **Themes**: structural, content, anti-patterns
- **Description**: Practical tips on CLAUDE.md structure, what to include/exclude, common mistakes.
- **Last verified**: 2026-02-12

### T2-002: Builder.io — How I Use Claude Code
- **URL**: https://www.builder.io/blog/claude-code
- **Themes**: structural, content, behavioral
- **Description**: Comprehensive guide to using Claude Code effectively, including CLAUDE.md patterns.
- **Last verified**: 2026-02-12

### T2-003: Dometrain — Creating the Perfect CLAUDE.md
- **URL**: https://dometrain.com/blog/creating-the-perfect-claudemd-for-claude-code/
- **Themes**: structural, content, integration
- **Description**: Guide to creating the perfect CLAUDE.md for Claude Code with practical examples.
- **Last verified**: 2026-02-12

### T2-004: Tembo — How to Write a Great CLAUDE.md
- **URL**: https://www.tembo.io/blog/how-to-write-a-great-claude-md
- **Themes**: structural, behavioral, integration
- **Description**: Real-world patterns for CLAUDE.md in production projects.
- **Last verified**: 2026-02-12

### T2-005: Arize AI — CLAUDE.md Best Practices
- **URL**: https://arize.com/blog/claude-md-best-practices
- **Themes**: content, anti-patterns, maintenance
- **Description**: Best practices and anti-patterns from AI engineering teams.
- **Last verified**: 2026-02-12

### T2-006: Huikang — Writing CLAUDE.md for Mature Codebases
- **URL**: https://blog.huikang.dev/2025/05/31/writing-claude-md.html
- **Themes**: structural, content, behavioral, maintenance
- **Description**: Practical guide for writing CLAUDE.md in mature and monorepo codebases — token budgeting, scoped files, legacy patterns, and team ownership conventions.
- **Last verified**: 2026-03-06

### T2-007: Shrivu Shankar — How I Use Every Claude Code Feature
- **URL**: https://blog.sshh.io/p/how-i-use-every-claude-code-feature
- **Themes**: behavioral, integration, maintenance
- **Description**: Comprehensive walkthrough of Claude Code features — CLAUDE.md as team constitution, /clear cadence, custom workflows, multi-agent patterns.
- **Last verified**: 2026-03-06

### T2-008: Paige Niedringhaus — Getting the Most out of Claude Code
- **URL**: https://www.paigeniedringhaus.com/blog/getting-the-most-out-of-claude-code/
- **Themes**: structural, content, behavioral, integration
- **Description**: Hands-on guide covering CLAUDE.md setup, CI/CD integration patterns, context management, and prompting techniques for production codebases.
- **Last verified**: 2026-03-06

---

## Tier 3: Community Templates & Examples

### T3-001: ruvnet/claude-flow
- **URL**: https://raw.githubusercontent.com/ruvnet/claude-flow/main/CLAUDE.md
- **Themes**: structural, integration, behavioral
- **Description**: Example CLAUDE.md from the claude-flow project — multi-agent orchestration patterns.
- **Last verified**: 2026-02-12

### T3-002: abhishekray07/claude-md-templates
- **URL**: https://raw.githubusercontent.com/abhishekray07/claude-md-templates/main/README.md
- **Themes**: structural, content
- **Description**: Collection of CLAUDE.md templates for different project types.
- **Last verified**: 2026-02-12

---

## Theme Definitions

| Theme | Content scope |
|-------|---------------|
| `structural` | File size constraints, section organization, hierarchy, formatting rules |
| `content` | What to include, what to exclude, writing style |
| `anti-patterns` | Common mistakes, things to avoid, negative examples |
| `integration` | Hooks vs CLAUDE.md, skills vs CLAUDE.md, rules directory, settings.json |
| `behavioral` | Workflow rules, coding patterns, interaction preferences |
| `maintenance` | Review cadence, self-improving patterns, versioning, staleness |

## How fetch-guidelines.py Uses This File

The script parses this file to extract:
1. **Source ID** (e.g., `T1-001`) from the heading.
2. **URL** from the `- **URL**:` line.
3. **Themes** from the `- **Themes**:` line (comma-separated).
4. **Tier** from the section heading (`Tier 1` → 1, `Tier 2` → 2, `Tier 3` → 3).
5. **Source name** from the heading text after the ID and colon.

Failed fetches are skipped with warnings. The script follows redirects and handles both HTML and raw markdown content.
