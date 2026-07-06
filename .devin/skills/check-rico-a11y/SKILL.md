---
name: check-rico-a11y
description: Accessibility audit for Rico Hunt. Run contrast checks and review alt text, focus states, ARIA labels, and keyboard navigation in frontend code.
triggers:
  - user
  - model
allowed-tools:
  - read
  - grep
  - exec
---

# check-rico-a11y

Accessibility audit for Rico Hunt. This skill is **read-only** and runs checks that do not require a browser.

## Contrast check

Run the existing script:

```bash
cd apps/web && npm run check:contrast
```

This uses `apps/web/scripts/check-contrast.mjs` to flag color-contrast failures against the shipped Nocturne palette.

## Code checks

Search the frontend for common accessibility issues:

```bash
# Missing alt text on images (img without alt)
grep -R "<img" apps/web/app --include="*.tsx" | grep -v "alt="

# Icon-only buttons without aria-label
grep -R "aria-label" apps/web/app --include="*.tsx" -l

# Focus rings disabled
grep -R "outline-none" apps/web/app --include="*.tsx" -l

# prefers-reduced-motion usage
grep -R "reduced-motion\|prefersReducedMotion" apps/web/app --include="*.tsx" -l
```

## What to report

For each issue:
- File path and line number
- Severity: critical / warning / suggestion
- Suggested fix

## Safety constraints

- Read-only; do not change colors or remove outlines unless the user approves a fix.
- Do not run Playwright or browser-based audits in this container (no browser available).
