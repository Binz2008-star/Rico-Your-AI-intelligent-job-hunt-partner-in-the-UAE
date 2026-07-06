# Design System Archive

Static reference artifacts that are not production code.

Files here are kept for historical reference, offline review, or design inspiration. They are not linked from the Next.js app and do not create any routes.

## Contents

- `rico-hunt-v2-offline.html` — bundled offline design prototype with embedded assets. Profile data has been sanitized to a synthetic persona.
- `motion-lab-dc.html` — motion/animation exploration using external libraries (CDNs). Requires `support.js` for the minimal DC runtime stub.
- `support.js` — minimal DC runtime stub so `motion-lab-dc.html` can be opened directly for review. Not the full DC framework.

## Rules

- Do not import these files into `apps/web/` without review.
- CDN-heavy files should not be used in production as-is.
- If a reference artifact is promoted to a real gallery prototype, it must first move to `design-handoffs/incoming/` for review.
