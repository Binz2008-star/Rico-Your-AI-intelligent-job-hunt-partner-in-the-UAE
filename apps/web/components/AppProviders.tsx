"use client";

import { PWAUpdatePrompt } from "@/components/PWAUpdatePrompt";
import { LanguageProvider } from "@/contexts/LanguageContext";
import { ThemeProvider } from "@/contexts/ThemeContext";

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <LanguageProvider>
        {children}
        <PWAUpdatePrompt />
      </LanguageProvider>
    </ThemeProvider>
  );
}
