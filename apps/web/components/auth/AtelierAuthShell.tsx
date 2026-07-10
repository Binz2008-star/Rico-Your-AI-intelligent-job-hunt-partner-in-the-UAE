"use client";

/**
 * AtelierAuthShell — shared chrome for the auth surfaces (login, signup,
 * forgot-password, reset-password, verify-email) in the approved
 * `/design-preview` Atelier direction.
 *
 * It is a self-contained light-first "island" rendered under the otherwise dark
 * (Nocturne) app, following the same pattern as the shipped /terms and /privacy
 * pages: everything is wrapped in `.atelier` and styled through the scoped token
 * layers (app/_atelier/atelier-tokens.css + atelier-auth.css). Nothing global is
 * touched.
 *
 *  - Language comes from the existing global useLanguage() (LanguageContext);
 *    dir/lang are mirrored onto the `.atelier` wrapper so RTL is self-contained.
 *  - Theme is LOCAL to the island (defaults to light, matching the approved
 *    reference). We deliberately do NOT read/write the global ThemeContext or
 *    localStorage here, so the dark app default is never changed.
 */

import { useLanguage } from "@/contexts/LanguageContext";
import { useTranslation } from "@/lib/translations";
import Link from "next/link";
import { useState } from "react";
import "../../app/_atelier/atelier-tokens.css";
import "../../app/_atelier/atelier-auth.css";

export function AtelierAuthShell({ children }: { children: React.ReactNode }) {
  const { language, setLanguage } = useLanguage();
  const t = useTranslation(language);
  const isAr = language === "ar";
  const [dark, setDark] = useState(false);

  return (
    <div
      className="atelier atl-auth"
      data-atl-theme={dark ? "dark" : "light"}
      dir={isAr ? "rtl" : "ltr"}
      lang={isAr ? "ar" : "en"}
    >
      <header className="atl-auth-header">
        <Link href="/" className="atl-auth-brand" aria-label="Rico">
          {t("atlBrand")}
        </Link>
        <div className="atl-auth-controls">
          <div className="atl-seg" role="group" aria-label="Language">
            <button
              type="button"
              className="atl-seg-btn"
              aria-pressed={!isAr}
              onClick={() => setLanguage("en")}
            >
              EN
            </button>
            <button
              type="button"
              className="atl-seg-btn"
              aria-pressed={isAr}
              onClick={() => setLanguage("ar")}
            >
              عربي
            </button>
          </div>
          <button
            type="button"
            className="atl-icon-toggle"
            aria-label={dark ? t("atlToLight") : t("atlToDark")}
            aria-pressed={dark}
            onClick={() => setDark((v) => !v)}
          >
            {dark ? (
              // Sun
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
                <circle cx="12" cy="12" r="4" />
                <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
              </svg>
            ) : (
              // Moon
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
              </svg>
            )}
          </button>
        </div>
      </header>

      <main className="atl-auth-main">
        <div className="atl-auth-col">{children}</div>
      </main>
    </div>
  );
}
