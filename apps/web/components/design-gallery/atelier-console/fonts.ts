/**
 * Atelier Console fonts — loaded via next/font/google (build-time, no CDN, CSP-safe).
 *
 * These are declared at module scope (next/font requirement) but their CSS
 * variables are only APPLIED on the console's own wrapper element (see
 * index.tsx), so production routes are unaffected — the browser fetches a
 * family only where its variable-backed font-family is actually used.
 *
 * Fraunces  → editorial display serif (EN headings)
 * Amiri     → Arabic display serif (AR headings)
 * IBM Plex Sans Arabic → Arabic sans body
 * (Inter + IBM Plex Mono already load app-wide; re-declared here so the console
 *  is self-contained and its --font-* vars resolve without touching layout.tsx.)
 */
import {
  Fraunces,
  Amiri,
  IBM_Plex_Sans_Arabic,
  Inter,
  IBM_Plex_Mono,
} from "next/font/google";

export const fraunces = Fraunces({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  style: ["normal", "italic"],
  variable: "--font-atl-fraunces",
  display: "swap",
});

export const amiri = Amiri({
  subsets: ["arabic"],
  weight: ["400", "700"],
  variable: "--font-atl-amiri",
  display: "swap",
});

export const plexArabic = IBM_Plex_Sans_Arabic({
  subsets: ["arabic"],
  weight: ["300", "400", "500", "600"],
  variable: "--font-atl-plex-ar",
  display: "swap",
});

export const inter = Inter({
  subsets: ["latin"],
  variable: "--font-atl-inter",
  display: "swap",
});

export const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-atl-mono",
  display: "swap",
});

export const atelierFontVars = [
  fraunces.variable,
  amiri.variable,
  plexArabic.variable,
  inter.variable,
  plexMono.variable,
].join(" ");
