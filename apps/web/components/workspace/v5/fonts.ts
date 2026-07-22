import { Amiri, IBM_Plex_Mono, IBM_Plex_Sans_Arabic, Inter } from "next/font/google";

/**
 * Command Workspace UI fonts — the owner-supplied artifact's stack
 * (FONT_EN: Fraunces display / Inter sans / IBM Plex Mono;
 *  FONT_AR: Amiri display / IBM Plex Sans Arabic). Display serif stays
 * Fraunces via the shared atelier-kit loader (`atelierFraunces`) — do not
 * add a second Fraunces instance.
 *
 * Route-scoped by design: next/font only emits preload hints on routes that
 * actually render a component using these exports, so importing them here
 * changes nothing for routes outside the workspace island.
 *
 * The `variable` literals must stay in sync with V5_FONT in ./tokens.ts.
 */
export const v5Inter = Inter({
    subsets: ["latin"],
    display: "swap",
    variable: "--font-inter-v5",
});

export const v5PlexMono = IBM_Plex_Mono({
    subsets: ["latin"],
    weight: ["400", "500"],
    display: "swap",
    variable: "--font-plex-mono-v5",
});

export const v5Amiri = Amiri({
    subsets: ["arabic", "latin"],
    weight: ["400", "700"],
    display: "swap",
    // No preload: Arabic display glyphs load on demand (perf slice 2026-07-21).
    preload: false,
    variable: "--font-amiri-v5",
});

export const v5PlexArabic = IBM_Plex_Sans_Arabic({
    subsets: ["arabic", "latin"],
    weight: ["400", "500", "600", "700"],
    display: "swap",
    preload: false,
    variable: "--font-plex-arabic-v5",
});
