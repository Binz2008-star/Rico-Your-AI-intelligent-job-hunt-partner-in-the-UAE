/**
 * Rico Ascent fonts — loaded via next/font/google (build-time, no CDN, CSP-safe).
 *
 * Declared at module scope (next/font requirement); CSS variables are only
 * applied on this prototype's own wrapper element (see index.tsx), so
 * production routes and their font payloads are unaffected.
 *
 * Space Grotesk + Inter are Rico's ratified Nocturne display/body pairing —
 * re-declared here (rather than relying on layout.tsx's globals) so this
 * component stays self-contained inside the design-gallery sandbox.
 * IBM Plex Sans Arabic is the Arabic body counterpart, matching the mono
 * family already used for Rico's data/evidence surfaces.
 */
import {
  Space_Grotesk,
  Inter,
  IBM_Plex_Sans_Arabic,
  IBM_Plex_Mono,
} from "next/font/google";

export const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-ra-display",
  display: "swap",
});

export const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-ra-body",
  display: "swap",
});

export const plexArabic = IBM_Plex_Sans_Arabic({
  subsets: ["arabic"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-ra-arabic",
  display: "swap",
});

export const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-ra-mono",
  display: "swap",
});

export const ricoAscentFontVars = [
  spaceGrotesk.variable,
  inter.variable,
  plexArabic.variable,
  plexMono.variable,
].join(" ");
