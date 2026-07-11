"use client";

import { useLanguage } from "@/contexts/LanguageContext";
import { useTranslation } from "@/lib/translations";

/**
 * Neutral, full-viewport loading state shown by authenticated-only pages while
 * the session check is resolving or while a guest is being redirected to login.
 *
 * Deliberately NOT the app shell (no sidebar/topbar/nav) so the private
 * authenticated layout never renders for an unauthenticated visitor.
 */
export function AuthGate() {
  const { language } = useLanguage();
  const t = useTranslation(language);
  return (
    <div
      dir={language === "ar" ? "rtl" : "ltr"}
      className="flex min-h-[100dvh] w-full items-center justify-center bg-background"
      role="status"
      aria-live="polite"
    >
      <div className="flex flex-col items-center gap-3">
        <span
          className="h-6 w-6 animate-spin rounded-full border-2 border-rico-accent/30 border-t-rico-accent"
          aria-hidden="true"
        />
        <p className="text-sm text-text-secondary">{t("authChecking")}</p>
      </div>
    </div>
  );
}
