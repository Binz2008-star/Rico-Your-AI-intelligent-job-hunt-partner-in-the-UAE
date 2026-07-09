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

import "./atelier-console.css";
import { atelierFontVars } from "./fonts";
import { ConsoleProviders, useLang, useTheme } from "./i18n";
import { RicoChat } from "./RicoConsole";

function AtelierConsoleFrame() {
  const { theme } = useTheme();
  const { lang, dir } = useLang();

  const className = [
    "atelier-console",
    atelierFontVars,
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
