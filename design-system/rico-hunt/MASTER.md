# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** Rico Hunt
**Generated:** 2026-06-03 16:27:17
**Category:** Job Board/Recruitment

---

## Global Rules

### Color Palette

> **Source of truth:** `apps/web/app/globals.css` (`:root` = dark default, `.light`
> = WCAG-AA light theme). Semantic colors are RGB-channel CSS variables consumed
> through Tailwind tokens (`bg-background`, `text-text-secondary`, `text-gold`,
> `border-border-subtle`, …). Do **not** hardcode hex for semantic roles in
> components — use the token utilities so the `.light` theme keeps working.

| Role | Hex (dark) | Token / Tailwind |
|------|-----------|------------------|
| Canvas background | `#000000` (page surface `#0a0a1a`) | `--bg` / `bg-background` |
| Surface | `#0a0a0f` | `--surface` / `bg-surface` |
| Primary accent · CTA — **Gold/Amber** | `#f5a623` | `--gold` / `text-gold` `bg-gold` |
| Secondary — **Magenta** (energy/action) | `#ff2d8e` | `--magenta` / `text-magenta` |
| Tertiary — **Cyan** (data/intelligence) | `#00e5ff` | `--cyan` / `text-cyan` |
| Text primary | `#ffffff` | `--text-primary` / `text-text-primary` |
| Text secondary | `#b8b8b8` | `--text-secondary` / `text-text-secondary` |
| Text tertiary | `#7a7a7a` | `--text-tertiary` / `text-text-tertiary` |

**Color Notes:** Cinematic **dark** canvas with a gold/amber primary; magenta and
cyan are energy/data tertiaries. A WCAG-AA light theme ships via the `.light`
class (accents darkened for contrast). Contrast is gated by
`apps/web/scripts/check-contrast.mjs` — run `npm run check:contrast`.

### Typography

- **Heading / Display Font:** IBM Plex Sans (with Sora as the display fallback)
- **Body / UI Font:** IBM Plex Sans
- **Mono / labels:** Space Mono
- **Mood:** premium, modern, clean, sophisticated
- **Loaded in:** `apps/web/app/layout.tsx` via `next/font/google` (`IBM_Plex_Sans`,
  `Sora`, `Space_Mono`) — no CSS `@import` is used.

Tailwind families (see `tailwind.config.ts`):

- `font-display` / `font-headline` → `var(--font-ibm-plex-sans)`, `var(--font-sora)`
- `font-body` → `var(--font-ibm-plex-sans)`
- `font-mono` → `var(--font-space-mono)`

### Spacing Variables

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | `4px` / `0.25rem` | Tight gaps |
| `--space-sm` | `8px` / `0.5rem` | Icon gaps, inline spacing |
| `--space-md` | `16px` / `1rem` | Standard padding |
| `--space-lg` | `24px` / `1.5rem` | Section padding |
| `--space-xl` | `32px` / `2rem` | Large gaps |
| `--space-2xl` | `48px` / `3rem` | Section margins |
| `--space-3xl` | `64px` / `4rem` | Hero padding |

### Shadow Depths

| Level | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.05)` | Subtle lift |
| `--shadow-md` | `0 4px 6px rgba(0,0,0,0.1)` | Cards, buttons |
| `--shadow-lg` | `0 10px 15px rgba(0,0,0,0.1)` | Modals, dropdowns |
| `--shadow-xl` | `0 20px 25px rgba(0,0,0,0.15)` | Hero images, featured cards |

---

## Component Specs

### Buttons

```css
/* Primary Button — gold CTA, dark label, gold glow */
.btn-primary {
  background: #f5a623;
  color: #0a0a1a;
  padding: 12px 24px;
  border-radius: 9999px;
  font-weight: 600;
  box-shadow: 0 0 32px rgba(245, 166, 35, 0.28);
  transition: opacity 200ms ease;
  cursor: pointer;
}

.btn-primary:hover {
  opacity: 0.9;
}

/* Secondary Button — quiet glass on the dark canvas */
.btn-secondary {
  background: rgba(255, 255, 255, 0.04);
  color: #ffffff;
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 12px 24px;
  border-radius: 9999px;
  font-weight: 600;
  transition: background 200ms ease;
  cursor: pointer;
}

.btn-secondary:hover {
  background: rgba(255, 255, 255, 0.08);
}
```

### Cards

```css
/* Glass card on the dark canvas (see .glass-panel in globals.css for the
   elevated variant with backdrop-blur). */
.card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 12px;
  padding: 24px;
  transition: all 200ms ease;
}

.card:hover {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.12);
}
```

### Inputs

```css
.input {
  background: rgba(255, 255, 255, 0.03);
  color: #ffffff;
  padding: 12px 16px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  font-size: 16px;
  transition: border-color 200ms ease;
}

.input:focus {
  border-color: #f5a623;
  outline: none;
  box-shadow: 0 0 0 3px rgba(245, 166, 35, 0.20);
}
```

### Modals

```css
.modal-overlay {
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
}

.modal {
  background: linear-gradient(180deg, rgba(19, 19, 42, 0.92) 0%, rgba(10, 10, 24, 0.88) 100%);
  backdrop-filter: blur(36px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  padding: 32px;
  box-shadow: 0 20px 60px rgba(5, 5, 16, 0.5);
  max-width: 500px;
  width: 90%;
}
```

---

## Style Guidelines

**Style:** Cinematic dark — glassmorphism + premium gold accent

**Keywords:** dark canvas, glassmorphism, ambient radial glows, gold/magenta/cyan accents, framer-motion, bilingual + RTL-aware, premium, high-contrast

**Best For:** AI products, SaaS, premium landing pages, dashboards

**Key Effects:** Glass panels (`.glass-panel` / `.glass-island`, backdrop-blur), ambient radial glows, gold glow shadows on primary CTAs, framer-motion entrance animations wrapped in `MotionConfig reducedMotion="user"` (respects `prefers-reduced-motion`), subtle noise-grain overlay, transitions 150–300ms ease.

### Page Pattern

**Pattern Name:** Marketplace / Directory

- **Conversion Strategy:**  map hover pins,  card carousel, Search bar is the CTA. Reduce friction to search. Popular searches suggestions.
- **CTA Placement:** Hero Search Bar + Navbar 'List your item'
- **Section Order:** 1. Hero (Search focused), 2. Categories, 3. Featured Listings, 4. Trust/Safety, 5. CTA (Become a host/seller)

---

## Anti-Patterns (Do NOT Use)

- ❌ Outdated forms
- ❌ Hidden filters

### Additional Forbidden Patterns

- ❌ **Emojis as icons** — Use SVG icons (Heroicons, Lucide, Simple Icons)
- ❌ **Missing cursor:pointer** — All clickable elements must have cursor:pointer
- ❌ **Layout-shifting hovers** — Avoid scale transforms that shift layout
- ❌ **Low contrast text** — Maintain 4.5:1 minimum contrast ratio
- ❌ **Instant state changes** — Always use transitions (150-300ms)
- ❌ **Invisible focus states** — Focus states must be visible for a11y

---

## Pre-Delivery Checklist

Before delivering any UI code, verify:

- [ ] No emojis used as icons (use SVG instead)
- [ ] All icons from consistent icon set (Heroicons/Lucide)
- [ ] `cursor-pointer` on all clickable elements
- [ ] Hover states with smooth transitions (150-300ms)
- [ ] Light mode: text contrast 4.5:1 minimum
- [ ] Focus states visible for keyboard navigation
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive: 375px, 768px, 1024px, 1440px
- [ ] No content hidden behind fixed navbars
- [ ] No horizontal scroll on mobile
