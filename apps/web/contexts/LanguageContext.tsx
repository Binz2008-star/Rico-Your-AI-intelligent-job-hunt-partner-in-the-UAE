"use client";

import { createContext, useContext, useEffect, useState } from "react";

export type Language = "en" | "ar";

interface LanguageContextType {
    language: Language;
    setLanguage: (language: Language) => void;
}

const LanguageContext = createContext<LanguageContextType | undefined>(
    undefined,
);

const LANGUAGE_STORAGE_KEY = "rico-language";

function readStoredLanguage(): Language | null {
    try {
        const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY);
        if (stored === "en" || stored === "ar") return stored;
    } catch {
        // Ignore localStorage errors
    }
    return null;
}

export function LanguageProvider({ children }: { children: React.ReactNode }) {
    // Start with "en" for SSR consistency. The useEffect below reads localStorage
    // after hydration so the stored preference is applied without a server mismatch.
    const [language, setLanguageState] = useState<Language>("en");

    useEffect(() => {
        void (async () => {
            const stored = readStoredLanguage();
            if (stored && stored !== language) setLanguageState(stored);
        })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        document.documentElement.lang = language;
        document.documentElement.dir = language === "ar" ? "rtl" : "ltr";
        try {
            localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
        } catch {
            // Ignore localStorage errors
        }
    }, [language]);

    const setLanguage = (newLanguage: Language) => {
        setLanguageState(newLanguage);
    };

    return (
        <LanguageContext.Provider value={{ language, setLanguage }}>
            {children}
        </LanguageContext.Provider>
    );
}

export function useLanguage() {
    const context = useContext(LanguageContext);
    if (context === undefined) {
        throw new Error("useLanguage must be used within a LanguageProvider");
    }
    return context;
}
