"use client";

import { useLanguage } from "@/contexts/LanguageContext";

export function LanguageSwitcher() {
    const { language, setLanguage } = useLanguage();

    const languages = [
        { value: "en" as const, label: "EN" },
        { value: "ar" as const, label: "AR" },
    ];

    return (
        <div className="flex items-center gap-2">
            {languages.map((lang) => (
                <button
                    key={lang.value}
                    onClick={() => setLanguage(lang.value)}
                    className={`relative flex items-center justify-center w-10 h-10 rounded-lg transition-all duration-300 ${language === lang.value
                            ? "bg-primary/20 text-primary border border-primary/30 scale-105 shadow-[0_0_20px_rgba(0,229,255,0.15)]"
                            : "bg-surface-glass text-text-secondary border border-border-subtle hover:bg-surface-glass/80 hover:scale-105 active:scale-95"
                        }`}
                    title={lang.label}
                >
                    <span className="text-sm font-bold">{lang.label}</span>
                    {language === lang.value && (
                        <span className="absolute -top-1 -right-1 w-2 h-2 bg-primary rounded-full animate-pulse" />
                    )}
                </button>
            ))}
        </div>
    );
}
