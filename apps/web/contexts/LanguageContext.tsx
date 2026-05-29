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

function getStoredLanguage(): Language | null {
    if (typeof window === "undefined") return null;
    try {
        const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY);
        if (stored === "en" || stored === "ar") return stored;
    } catch (e) {
        // Ignore localStorage errors
    }
    return null;
}

function detectBrowserLanguage(): Language {
    if (typeof window === "undefined") return "en";
    const browserLang = navigator.language.toLowerCase();
    if (browserLang.startsWith("ar")) return "ar";
    return "en";
}

export function LanguageProvider({ children }: { children: React.ReactNode }) {
    const [language, setLanguageState] = useState<Language>(
        () => getStoredLanguage() ?? "en"
    );

    const setLanguage = (newLanguage: Language) => {
        setLanguageState(newLanguage);
        try {
            localStorage.setItem(LANGUAGE_STORAGE_KEY, newLanguage);
        } catch (e) {
            // Ignore localStorage errors
        }
    };

    // Update lang and dir attributes on document
    useEffect(() => {
        document.documentElement.lang = language;
        document.documentElement.dir = language === "ar" ? "rtl" : "ltr";
    }, [language]);

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
