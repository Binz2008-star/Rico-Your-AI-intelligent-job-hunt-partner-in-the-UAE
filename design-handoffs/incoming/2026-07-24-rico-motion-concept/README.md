# Rico — Motion Concept · Spotlight Reveal + Career-Transformation Scrub

**Date:** 2026-07-24 · **Branch:** `claude/command-visual-polish-51dq2z` · **Status:** design + interaction reference (not wired to production)

Two motion references were supplied as **technique** studies — a Lithos cursor-spotlight reveal
and a Mainframe pointer-scrub video + typewriter. Neither is built. The interaction principles
are extracted and reinterpreted in Rico's **Atelier** identity (warm paper, ink, clay), using
Rico's real logo (interlocking motion rings) and voice (*"AI Career OS — Search. Apply. Track.
Follow up."*). No geology, no neon, no glassmorphism, no agency copy.

Nothing here touches `apps/web` production or the frozen landing page.

## Deliverables

| # | Deliverable | Where |
| --- | --- | --- |
| 1 | Inspiration analysis (Lithos + Mainframe) | `rico-motion-concept.html` → Analysis |
| 2 | Rico reinterpretation principles | Analysis |
| 3 | Landing hero before/after | Before / After |
| 4 | Desktop version | Hero (live spotlight) |
| 5 | Mobile version | Frames |
| 6 | Arabic / RTL version | Frames |
| 7 | Reduced-motion version | Frames |
| 8 | Pointer-scrub storyboard | Scrub |
| 9 | Static fallback | Frames + Scrub |
| 10 | Typewriter behaviour spec | Typewriter |
| 11 | Action-pill interaction states | Typewriter |
| 12 | Reusable component map | Components + `./components/*` |
| 13 | Performance & accessibility notes | Perf · A11y |
| 14 | Original Rico media / asset board | Assets |

Plus the **Command empty-state ContextReveal** and the **soft-reveal job/document cards**.

## Two artefacts

- **`rico-motion-concept.html`** — one self-contained, CSP-safe reference with **live** prototypes
  of all five mechanics (spotlight hero, pointer-scrub, typewriter + pills, Command context-reveal,
  soft-reveal cards). Opens in any browser; doubles as a Claude Artifact page. Header carries a
  motion switch and a light/dark ("Atelier at Night") toggle.
- **`./components/`** — the reusable **React 18 + TypeScript** kit (typechecks clean under `strict`):

  `useReducedMotion` · `useFineHover` · `useSmoothPointer` · `MotionSafe` · `CursorSpotlight` ·
  `MaskedReveal` · `LayeredAsset` · `HeroEntrance` · `ScrubbedMedia` · `HeroTypewriter` ·
  `HeroActionPills` · `ContextReveal` · `MobileNavigation` · `CareerTransformationHero`.

  Each owns its cleanup (RAF, listeners), pointer-events (not mouse-only), reduced-motion + touch
  fallbacks, and is SSR-safe for Next.js. The spotlight uses a **CSS radial-gradient mask driven by
  custom properties** — never `canvas.toDataURL()` per frame. `ScrubbedMedia` keeps a raw target, an
  eased current, one active seek, and the latest target queued (no seek-flooding).

## The core technique

```css
/* MaskedReveal — moved by useSmoothPointer via CSS custom properties */
mask-image: radial-gradient(
  circle var(--spotlight-r) at var(--spotlight-x) var(--spotlight-y),
  #000 0%, #000 40%, rgba(0,0,0,.75) 60%,
  rgba(0,0,0,.4) 75%, rgba(0,0,0,.12) 88%, transparent 100%);
```

## Truth constraints (enforced)

No fake job counts, employers, application statuses, verification, providers, or progress; no
automatic employer submission. The spotlight reveals **clarity** (active CV, verified matches,
structured board), not a decorative image. Every sample carries **"Sample scenario — not live
account data."** Command actions map to real routes/intents (`/jobs`, `/profile`, `/applications`,
`/upload`, chat) — the six starting actions live in `RICO_STARTING_ACTIONS`.

## Production notes (do before shipping)

- **Fonts:** use Rico's approved Atelier stack (Fraunces / Inter / mono). Do **not** import the
  Lithos/Mainframe example webfonts (Playfair, Helvetica Now) without licence verification.
- **Media:** the scrub "footage" here is an SVG keyframe transform. Any real video needs confirmed
  licensing, optimisation, a local fallback, a static poster, and acceptable mobile performance.
- **Assets:** all original inline SVG in the Atelier palette — no photos, no stock, no external media.
- Composition-only reference; wiring into a route is a separate, owner-approved step (landing page
  is frozen).

## Viewing

Open the HTML, or render it — verified in Chromium (spotlight hero, scrub, typewriter + pills,
Command context-reveal, cards) with zero console errors; the component kit passes `tsc --strict`.
