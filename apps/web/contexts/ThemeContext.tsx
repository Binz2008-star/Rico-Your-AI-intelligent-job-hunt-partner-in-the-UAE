"use client";

import { createContext, useContext, useEffect, useState } from "react";

export type Theme = "dark" | "light" | "system";

interface ThemeContextType {
  theme: Theme;
  resolvedTheme: "dark" | "light";
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

const THEME_STORAGE_KEY = "rico-theme";

function getSystemTheme(): "dark" | "light" {
  if (typeof window === "undefined") return "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

// Default to "dark" (not "system") so production stays dark-only until light mode
// is explicitly QA'd and enabled. Users opt in via the theme control; their choice
// is then remembered. This prevents an unreviewed light theme auto-activating for
// visitors whose OS is set to light.
function getStoredTheme(): Theme {
  if (typeof window === "undefined") return "dark";
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === "dark" || stored === "light" || stored === "system") {
      return stored;
    }
  } catch (e) {
    // Ignore localStorage errors
  }
  return "dark";
}

function resolveTheme(theme: Theme): "dark" | "light" {
  if (theme === "system") return getSystemTheme();
  return theme;
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  // Initialize theme from localStorage on mount
  const [theme, setThemeState] = useState<Theme>(() => getStoredTheme());
  const [resolvedTheme, setResolvedTheme] = useState<"dark" | "light">(() =>
    resolveTheme(getStoredTheme()),
  );

  // Listen for system theme changes when in system mode
  useEffect(() => {
    if (theme !== "system") return;

    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handleChange = () => {
      setResolvedTheme(mediaQuery.matches ? "dark" : "light");
    };

    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, [theme]);

  const setTheme = (newTheme: Theme) => {
    setThemeState(newTheme);
    setResolvedTheme(resolveTheme(newTheme));

    try {
      localStorage.setItem(THEME_STORAGE_KEY, newTheme);
    } catch (e) {
      // Ignore localStorage errors
    }
  };

  // Apply theme to document
  useEffect(() => {
    const root = document.documentElement;

    // Remove all theme classes
    root.classList.remove("dark", "light");

    // Add resolved theme class
    root.classList.add(resolvedTheme);

    // Set data attribute for CSS selectors
    root.setAttribute("data-theme", resolvedTheme);
  }, [resolvedTheme]);

  return (
    <ThemeContext.Provider value={{ theme, resolvedTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

// Degrade gracefully when no provider is mounted (e.g. isolated unit tests or a
// stray render outside the tree): return a safe dark default with a no-op setter
// rather than throwing and crashing the whole page over a theme control.
const FALLBACK_THEME: ThemeContextType = {
  theme: "dark",
  resolvedTheme: "dark",
  setTheme: () => {},
};

export function useTheme() {
  const context = useContext(ThemeContext);
  return context ?? FALLBACK_THEME;
}
