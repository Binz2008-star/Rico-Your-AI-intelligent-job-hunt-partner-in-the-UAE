"use client";

/**
 * DESIGN GALLERY ENTRY — Atelier Console (Lovable Reference)
 *
 * Standalone component for /design-gallery only. NOT linked from production
 * navigation, NOT /command, NOT /rico, NOT the homepage. ALL data is
 * SAMPLE/DEMO — no real AI calls, no real jobs, no real users. Every action is
 * disabled/reference-only (see ./prototype-notice).
 *
 * Ports the Lovable "Atelier" console (`src/routes/rico.tsx`) with the TanStack
 * route wrapper + server-fn chat stripped and replaced by a local scripted
 * walkthrough. Theme (light/dark), language (EN/AR), and direction (LTR/RTL) are
 * held in React state and applied to THIS wrapper only — never to <html> — so
 * the gallery tab cannot flip the rest of the app. Fonts load via next/font and
 * their CSS variables apply to this subtree only.
 *
 * Stack: react + lucide-react + Nocturne-adjacent scoped Atelier CSS. No shadcn,
 * no TanStack, no Vite.
 */

import { IBM_Plex_Sans } from "next/font/google";
import "./atelier-console.css";

// Route-scoped: IBM Plex Sans used to be a global layout font purely for this
// console; it now loads only when the gallery renders (perf slice 2026-07-21).
const consolePlexSans = IBM_Plex_Sans({
    subsets: ["latin"],
    weight: ["200", "300", "400", "500", "600", "700"],
    variable: "--font-ibm-plex-sans",
    display: "swap",
});
import { atelierFontVars } from "./fonts";
import { ConsoleProviders, useLang, useTheme } from "./i18n";
import { RicoChat } from "./RicoConsole";

function AtelierConsoleFrame() {
  const { theme } = useTheme();
  const { lang, dir } = useLang();

  const className = [
    "atelier-console",
    atelierFontVars,
    consolePlexSans.variable,
    theme === "dark" ? "dark" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={className} dir={dir} lang={lang}>
      <RicoChat />
    </div>
  );
}

export default function AtelierConsole() {
  return (
    <ConsoleProviders defaultLang="en" defaultTheme="light">
      <AtelierConsoleFrame />
    </ConsoleProviders>
  );
}
