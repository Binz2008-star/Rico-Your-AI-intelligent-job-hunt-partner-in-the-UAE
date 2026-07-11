import { Fraunces } from "next/font/google";

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
