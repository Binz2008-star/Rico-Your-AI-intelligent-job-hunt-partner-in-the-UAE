import { Fraunces, Noto_Naskh_Arabic, Noto_Sans_Arabic } from "next/font/google";

/**
 * Fraunces = the reference serif display for the Atelier prospectus system.
 * next/font/google font loaders are safe to share: calling this once and
 * importing the result elsewhere reuses the same font, it does not refetch
 * or duplicate the asset. No new npm dependency (Inter + IBM Plex Mono are
 * already global via app/layout).
 *
 * The `variable` value below must stay an inline string literal — next/font
 * requires literal arguments at compile time (a referenced constant fails
 * the build with "Font loader values must be explicitly written literals").
 * It is kept in sync with `ATELIER_FRAUNCES_VAR` in `./tokens.ts` by a
 * same-file constant assertion, not by import.
 */
export const atelierFraunces = Fraunces({
    subsets: ["latin"],
    weight: ["400", "500", "600"],
    style: ["normal", "italic"],
    display: "swap",
    variable: "--font-fraunces-landing",
});

/**
 * Arabic companions for the Atelier pairing (2026-07-17 reply-experience
 * program): Fraunces carries Latin only, so Arabic glyphs previously fell
 * through to the system default. Noto Naskh Arabic gives the serif prose the
 * same editorial personality in Arabic; Noto Sans Arabic backs the UI body.
 * Latin rendering is untouched — these sit AFTER the Latin families in the
 * stacks (see ATELIER_FONT), so they only ever serve Arabic glyphs.
 */
export const atelierNaskhArabic = Noto_Naskh_Arabic({
    subsets: ["arabic"],
    weight: ["400", "500", "600", "700"],
    display: "swap",
    variable: "--font-naskh-arabic",
});

export const atelierSansArabic = Noto_Sans_Arabic({
    subsets: ["arabic"],
    weight: ["400", "500", "600", "700"],
    display: "swap",
    variable: "--font-sans-arabic",
});
