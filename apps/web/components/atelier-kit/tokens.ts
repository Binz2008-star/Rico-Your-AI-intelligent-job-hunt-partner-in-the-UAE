/**
 * Shared Atelier "prospectus" design tokens — PR 0 of the /design-preview
 * migration (DEC-20260710-002, TASK-20260710-003).
 *
 * These are the exact color/font values verified pixel-for-pixel against the
 * /design-preview reference and shipped on the production landing
 * (LandingPageV2.tsx, #936/#937/#938). Extracted here, unchanged, so
 * subsequent per-route PRs (auth, support/legal restyle, onboarding,
 * workspace) can reuse them instead of re-declaring a local copy.
 *
 * Distinct from `apps/web/app/_atelier/atelier-tokens.css` (the earlier,
 * CSS-custom-property "Atelier V2" system already live on /terms, /privacy,
 * /refund-policy). This module is not merged into that file: those pages'
 * rendered output must not change without its own reviewed PR, since legal
 * copy/presentation changes require explicit sign-off.
 */

export const ATELIER = {
    bg: "#F1EADD",
    panel: "#F7F1E6",
    inset: "#EAE1D0",
    ink: "#1F1B15",
    ink70: "rgba(31,27,21,0.70)",
    ink55: "rgba(31,27,21,0.52)",
    ink40: "rgba(31,27,21,0.38)",
    hair: "rgba(31,27,21,0.16)",
    red: "#C6492E",
    footer: "#1A1712",
    footerInk: "#EFE7D6",
    footerInk60: "rgba(239,231,214,0.60)",
    footerHair: "rgba(239,231,214,0.20)",
} as const;

/* The Fraunces CSS variable name is kept identical to the one LandingPageV2
   already registers via next/font — reusing the same name means any route
   sharing this kit gets font caching/dedup for free with zero behavior
   change to the already-shipped landing page. */
export const ATELIER_FRAUNCES_VAR = "--font-fraunces-landing";

export const ATELIER_FONT = {
    serif: `var(${ATELIER_FRAUNCES_VAR}), Georgia, serif`,
    mono: "var(--font-mono), ui-monospace, monospace",
    /* Arabic mono/eyebrow fallback: system Arabic via the body stack (no new dep). */
    body: "var(--font-body), ui-sans-serif, system-ui, sans-serif",
} as const;
