"use client";

import { SubscriptionAtelier } from "@/components/subscription/SubscriptionAtelier";
import { WorkspaceShell } from "@/components/workspace/WorkspaceShell";
import { useLanguage } from "@/contexts/LanguageContext";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { useTranslation } from "@/lib/translations";

export default function SubscriptionPage() {
  const { language } = useLanguage();
  const t = useTranslation(language);
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
      <SubscriptionAtelier user={user} />
    </WorkspaceShell>
  );
}
