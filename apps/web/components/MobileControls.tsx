"use client";

import { useLanguage } from "@/contexts/LanguageContext";
import { useTheme } from "@/contexts/ThemeContext";
import { useState } from "react";

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

    const nextThemeLabel =
        theme === "dark" ? "Light" : theme === "light" ? "System" : "Dark";

    return (
        <div className="relative">
            <button
                type="button"
                aria-label="Open display and language settings"
                aria-expanded={isOpen ? "true" : "false"}
                onClick={() => setIsOpen((open) => !open)}
                className="flex h-8 w-8 items-center justify-center rounded-lg border border-border-subtle bg-surface/70 text-text-muted transition-all hover:bg-surface"
            >
                <span className="text-lg" aria-hidden="true">
                    ⚙
                </span>
            </button>

            {isOpen && (
                <>
                    <button
                        type="button"
                        aria-label="Close display and language settings"
                        className="fixed inset-0 z-40 cursor-default"
                        onClick={() => setIsOpen(false)}
                    />

                    <div className="absolute right-0 top-full z-50 mt-2 min-w-[150px] rounded-lg border border-border-subtle bg-surface p-2 shadow-xl backdrop-blur-xl">
                        <div className="flex flex-col gap-1">
                            <button
                                type="button"
                                onClick={() => {
                                    toggleTheme();
                                    setIsOpen(false);
                                }}
                                className="flex items-center gap-2 rounded px-3 py-2 text-left text-sm text-text-primary hover:bg-surface-muted"
                            >
                                <span className="text-base" aria-hidden="true">
                                    {theme === "dark" ? "☀" : theme === "light" ? "🖥" : "🌙"}
                                </span>
                                <span>{nextThemeLabel}</span>
                            </button>

                            <button
                                type="button"
                                onClick={() => {
                                    toggleLanguage();
                                    setIsOpen(false);
                                }}
                                className="flex items-center gap-2 rounded px-3 py-2 text-left text-sm text-text-primary hover:bg-surface-muted"
                            >
                                <span className="text-base" aria-hidden="true">
                                    🌐
                                </span>
                                <span>{language === "en" ? "العربية" : "English"}</span>
                            </button>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}
