# Design Handoffs

This directory stores design prototype handoffs from agents that do **not** have repo write access.

**Rule:** Nothing in this folder is production code. Every handoff must be reviewed before it can move into `apps/web/design-gallery/` or any production path.

## Workflow

```text
Agents without repo access
  → deliver a handoff package
  → save it in design-handoffs/incoming/
  → review
  → approve or reject
  → if approved, move to design-handoffs/approved-for-gallery/
  → only then add to /design-gallery via a small PR
```

## Folder Structure

```text
design-handoffs/
  README.md                 # this file
  incoming/                 # new, unreviewed handoffs
  reviewed/                 # reviewed but not yet approved
  approved-for-gallery/     # approved and ready to add to /design-gallery
  rejected/                 # rejected handoffs kept for reference
```

## Handoff Package Format

Each incoming handoff lives in its own folder:

```text
design-handoffs/incoming/
  2026-07-07-rico-alive-model-a/
    README.md               # required
    RicoAlivePrototype.tsx  # optional prototype component
    gallery-entry.md        # optional gallery integration notes
    notes.md                # optional extra notes
    screenshots/            # optional screenshots
```

### Required README.md

Every handoff must include a `README.md` with these sections:

1. **Prototype name**
2. **Design goal** — what problem this explores
3. **Screens/states covered**
4. **Visual direction** — how it fits Rico Nocturne identity
5. **Motion used** — animation approach and libraries
6. **Arabic/English behavior**
7. **Mobile behavior**
8. **Production-safe ideas** — what can be reused
9. **Prototype-only ideas** — what must stay in the prototype
10. **Risks** — performance, accessibility, dependencies, etc.

### Prototype Component Rules

If a `.tsx` component is included, it must follow these constraints:

- No package installs
- No CDN resources
- No backend/auth/billing/database assumptions
- Fake data must be labeled as **Sample** or **Demo**
- Use Rico Nocturne identity:
  - navy canvas (`rgb(11,13,28)`)
  - ember/gold accent
  - aura teal for intelligence/data
  - glass islands
  - honest AI action labels

## Review Checklist

Before a handoff can move to `approved-for-gallery/`, the reviewer must confirm:

- [ ] Files are included and follow the package format
- [ ] It follows Rico Nocturne identity
- [ ] It does not use forbidden packages or CDNs
- [ ] Fake data is marked as Sample/Demo
- [ ] It is safe to add to `/design-gallery`
- [ ] Prototype-only parts are clearly marked
- [ ] Recommended action is documented:
  - `reject`
  - `keep as inspiration`
  - `add to gallery`
  - `needs cleanup first`

## Restrictions

- **Do not** save handoffs directly into `apps/web/components/`, `apps/web/app/`, or `apps/web/app/design-gallery/`.
- **Do not** implement production changes from a handoff without review.
- **Do not** install packages or open PRs from a handoff until it is approved.
- **Do not** modify `/command` or other production pages from a handoff.

## For Agents Without Repo Access

You do not have repo write access, so deliver a handoff package only.

Do not claim you modified the repo.
Do not open PRs.
Do not assume your code is production-ready.

Deliver your files using the structure above and include the required `README.md`.
