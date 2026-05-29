"use client";

import { useLanguage } from "@/contexts/LanguageContext";
import { useTheme } from "@/contexts/ThemeContext";
import { useEffect } from "react";

export function LanguageHtmlAttributes() {
  const { language } = useLanguage();
  const { theme } = useTheme();

  useEffect(() => {
    // Update html lang attribute
    document.documentElement.lang = language;
    
    // Update html dir attribute for RTL support
    document.documentElement.dir = language === "ar" ? "rtl" : "ltr";
  }, [language]);

  useEffect(() => {
    // Update html className for theme
    if (theme === "light") {
      document.documentElement.classList.remove("dark");
      document.documentElement.classList.add("light");
    } else if (theme === "dark") {
      document.documentElement.classList.remove("light");
      document.documentElement.classList.add("dark");
    } else {
      // system theme - remove both classes
      document.documentElement.classList.remove("light", "dark");
    }
  }, [theme]);

  return null;
}
