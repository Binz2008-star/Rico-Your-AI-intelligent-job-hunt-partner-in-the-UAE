"use client";

import { ApplicationsAtelier } from "@/components/applications/ApplicationsAtelier";
import { WorkspaceShell } from "@/components/workspace/WorkspaceShell";
import { useLanguage } from "@/contexts/LanguageContext";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { useTranslation } from "@/lib/translations";

export default function ApplicationsPage() {
  const { language } = useLanguage();
  const t = useTranslation(language);
  // Authenticated-only: a guest is redirected to /login?next=/applications by
  // the guard and sees a neutral loader (never the private workspace chrome,
  // and no private request fires). ApplicationsAtelier only mounts once
  // authorized. Same pattern as /settings.
  const { user, authorized } = useRequireAuth();

  if (!authorized || !user) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="flex min-h-screen items-center justify-center"
      >
        <span className="sr-only">{t("loading")}</span>
      </div>
    );
  }

  return (
    <WorkspaceShell>
      <ApplicationsAtelier />
    </WorkspaceShell>
  );
}
