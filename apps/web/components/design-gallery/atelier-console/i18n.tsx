"use client";

/**
 * Scoped i18n for the Atelier Console gallery entry.
 *
 * Isolation note: unlike the Lovable source (which toggled `.dark`, `lang`, and
 * `dir` on <html>), this provider keeps lang/theme entirely in React state and
 * applies them to the console's OWN wrapper element only (see index.tsx). The
 * gallery tab must never flip the whole app to RTL or dark. No localStorage,
 * no ThemeContext, no global document mutation.
 */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type Lang = "en" | "ar";
export type Theme = "light" | "dark";

type LangCtx = {
  lang: Lang;
  setLang: (l: Lang) => void;
  toggleLang: () => void;
  dir: "ltr" | "rtl";
};

type ThemeCtx = {
  theme: Theme;
  setTheme: (t: Theme) => void;
  toggleTheme: () => void;
};

const LangContext = createContext<LangCtx | null>(null);
const ThemeContext = createContext<ThemeCtx | null>(null);

export function ConsoleProviders({
  children,
  defaultLang = "en",
  defaultTheme = "light",
}: {
  children: ReactNode;
  defaultLang?: Lang;
  defaultTheme?: Theme;
}) {
  const [lang, setLangState] = useState<Lang>(defaultLang);
  const [theme, setThemeState] = useState<Theme>(defaultTheme);

  const setLang = useCallback((l: Lang) => setLangState(l), []);
  const setTheme = useCallback((t: Theme) => setThemeState(t), []);

  const langValue = useMemo<LangCtx>(
    () => ({
      lang,
      setLang,
      toggleLang: () => setLangState((p) => (p === "en" ? "ar" : "en")),
      dir: lang === "ar" ? "rtl" : "ltr",
    }),
    [lang, setLang],
  );

  const themeValue = useMemo<ThemeCtx>(
    () => ({
      theme,
      setTheme,
      toggleTheme: () => setThemeState((p) => (p === "light" ? "dark" : "light")),
    }),
    [theme, setTheme],
  );

  return (
    <LangContext.Provider value={langValue}>
      <ThemeContext.Provider value={themeValue}>{children}</ThemeContext.Provider>
    </LangContext.Provider>
  );
}

export function useLang(): LangCtx {
  const ctx = useContext(LangContext);
  if (!ctx) throw new Error("useLang must be used within ConsoleProviders");
  return ctx;
}

export function useTheme(): ThemeCtx {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ConsoleProviders");
  return ctx;
}

/* In-console toggles (rendered in the TopBar), styled to match the source. */

export function LangToggle({ className = "" }: { className?: string }) {
  const { lang, toggleLang } = useLang();
  return (
    <button
      onClick={toggleLang}
      aria-label="Toggle language"
      className={`px-2 py-1 rounded-md font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--ink-mute)] hover:text-[var(--ink)] hover:bg-[var(--paper-2)] transition-colors ${className}`}
    >
      {lang === "en" ? "عربي" : "EN"}
    </button>
  );
}

export function ThemeToggle({ className = "" }: { className?: string }) {
  const { theme, toggleTheme } = useTheme();
  return (
    <button
      onClick={toggleTheme}
      aria-label="Toggle theme"
      className={`px-2 py-1 rounded-md font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--ink-mute)] hover:text-[var(--ink)] hover:bg-[var(--paper-2)] transition-colors ${className}`}
    >
      {theme === "light" ? "☾" : "☀"}
    </button>
  );
}
