"use client";

import { WorkspaceShell } from "@/components/workspace/WorkspaceShell";
import { ProfileAtelier } from "@/components/workspace/ProfileAtelier";
import { useLanguage } from "@/contexts/LanguageContext";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { useTranslation } from "@/lib/translations";

export default function ProfilePage() {
    const { language } = useLanguage();
    const t = useTranslation(language);
    // Authenticated-only: a guest is redirected to /login?next=/profile by the
    // guard. Until an identity is confirmed we render a neutral loader (no
    // workspace chrome, no private request) — ProfileAtelier only mounts, and
    // only then fetches the private profile, once authorized.
    const { authorized } = useRequireAuth();

    if (!authorized) {
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
            <ProfileAtelier />
        </WorkspaceShell>
    );
}
