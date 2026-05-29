"use client";

import { useState } from "react";
import { useTheme } from "@/contexts/ThemeContext";
import { useLanguage } from "@/contexts/LanguageContext";

export function MobileControls() {
  const { theme, setTheme } = useTheme();
  const { language, setLanguage } = useLanguage();
  const [isOpen, setIsOpen] = useState(false);

  const toggleTheme = () => {
    if (theme === "dark") setTheme("light");
    else if (theme === "light") setTheme("system");
    else setTheme("dark");
  };

  const toggleLanguage = () => {
    setLanguage(language === "en" ? "ar" : "en");
  };

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center justify-center w-8 h-8 rounded-lg bg-white/5 text-text-muted border border-white/10 hover:bg-white/10 transition-all"
        title="Settings"
      >
        <span className="text-lg">settings</span>
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />
          <div className="absolute right-0 top-full mt-2 z-50 bg-surface-glass border border-border-subtle rounded-lg p-2 min-w-[140px] backdrop-blur-xl">
            <div className="flex flex-col gap-1">
              <button
                onClick={() => {
                  toggleTheme();
                  setIsOpen(false);
                }}
                className="flex items-center gap-2 px-3 py-2 rounded hover:bg-white/10 text-left text-sm"
              >
                <span className="text-base">
                  {theme === "dark" ? "light_mode" : theme === "light" ? "desktop_windows" : "dark_mode"}
                </span>
                <span>
                  {theme === "dark" ? "Light" : theme === "light" ? "System" : "Dark"}
                </span>
              </button>
              <button
                onClick={() => {
                  toggleLanguage();
                  setIsOpen(false);
                }}
                className="flex items-center gap-2 px-3 py-2 rounded hover:bg-white/10 text-left text-sm"
              >
                <span className="text-base">language</span>
                <span>{language === "en" ? "العربية" : "English"}</span>
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
