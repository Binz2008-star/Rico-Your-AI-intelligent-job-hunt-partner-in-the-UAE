"use client";

import { LanguageProvider } from "@/contexts/LanguageContext";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { captureSignupAttribution } from "@/lib/signupAttribution";
import { useEffect } from "react";

export function AppProviders({ children }: { children: React.ReactNode }) {
    useEffect(() => {
        captureSignupAttribution();
    }, []);

    return (
        <ThemeProvider>
            <LanguageProvider>
                {children}
            </LanguageProvider>
        </ThemeProvider>
    );
}
