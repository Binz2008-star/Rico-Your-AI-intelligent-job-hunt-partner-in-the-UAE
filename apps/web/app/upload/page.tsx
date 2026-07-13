"use client";

import { GuestUploadAtelier } from "@/components/upload/GuestUploadAtelier";
import { UploadAtelier } from "@/components/upload/UploadAtelier";
import { WorkspaceShell } from "@/components/workspace/WorkspaceShell";
import { useLanguage } from "@/contexts/LanguageContext";
import { fetchMe } from "@/lib/api";
import { useTranslation } from "@/lib/translations";
import { useEffect, useState } from "react";

/**
 * /upload is intentionally dual-mode and public-capable:
 *  - a GUEST uploads a CV under the `public:*` identity and continues to
 *    /command?cv=ready (GuestUploadAtelier, in the public AtelierAuthShell) —
 *    no login is forced and no authenticated navigation is exposed.
 *  - an AUTHENTICATED user gets the "My files" manager inside WorkspaceShell
 *    (Shell C), the same workspace chrome as /dashboard, /settings, /profile.
 * Auth is detected with fetchMe() (not useRequireAuth) so the guest flow keeps
 * working exactly as before.
 */
export default function UploadPage() {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const [isAuth, setIsAuth] = useState<boolean | null>(null);

    useEffect(() => {
        fetchMe()
            .then(me => setIsAuth(me.authenticated))
            .catch(() => setIsAuth(false));
    }, []);

    if (isAuth === null) {
        return (
            <div role="status" aria-live="polite" className="flex min-h-[100dvh] w-full items-center justify-center">
                <span className="sr-only">{t("loading")}</span>
                <span className="h-6 w-6 animate-spin rounded-full border-2 border-rico-accent/30 border-t-rico-accent" aria-hidden="true" />
            </div>
        );
    }

    if (isAuth) {
        return (
            <WorkspaceShell>
                <UploadAtelier />
            </WorkspaceShell>
        );
    }

    return <GuestUploadAtelier />;
}
