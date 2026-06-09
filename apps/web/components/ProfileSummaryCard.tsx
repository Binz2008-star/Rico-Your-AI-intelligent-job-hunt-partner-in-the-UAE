"use client";

import { StatusCard } from "@/components/StatusCard";
import { useLanguage } from "@/contexts/LanguageContext";
import { useTranslation } from "@/lib/translations";
import { fetchProfile, type ProfileResponse } from "@/lib/api";
import { useCallback, useEffect, useState } from "react";

export function ProfileSummaryCard() {
    const [profile, setProfile] = useState<ProfileResponse | null>(null);
    const [status, setStatus] = useState<"loading" | "error" | "ready">("loading");
    const { language } = useLanguage();
    const t = useTranslation(language);

    const loadProfile = useCallback(async () => {
        try {
            const data = await fetchProfile();
            setProfile(data);
            setStatus("ready");
        } catch (err) {
            console.error("Profile Load Error:", err);
            setStatus("error");
        }
    }, []);

    useEffect(() => {
        const timeoutId = window.setTimeout(() => {
            void loadProfile();
        }, 0);
        return () => window.clearTimeout(timeoutId);
    }, [loadProfile]);

    const handleRetry = useCallback(() => {
        setStatus("loading");
        void loadProfile();
    }, [loadProfile]);

    const displayRoles = profile?.target_roles?.length
        ? profile.target_roles.slice(0, 3).join(", ")
        : null;

    if (status === "loading") {
        return (
            <StatusCard title={t("profileSummaryTitle")} badge="pending">
                <div className="animate-pulse space-y-2">
                    <div className="h-4 w-24 bg-white/5 rounded transition-all duration-300" />
                    <div className="h-3 w-32 bg-white/5 rounded transition-all duration-300" />
                </div>
            </StatusCard>
        );
    }

    if (status === "error") {
        return (
            <StatusCard title={t("profileSummaryTitle")} badge="error">
                <p className="mb-2 text-sm text-on-surface-variant">{t("profileSummaryErrLoad")}</p>
                <button
                    onClick={handleRetry}
                    className="text-xs text-primary underline transition-colors hover:text-on-surface"
                >
                    {t("profileSummaryRetry")}
                </button>
            </StatusCard>
        );
    }

    if (!profile?.profile_exists) {
        return (
            <StatusCard title={t("profileSummaryTitle")} badge="pending">
                <p className="text-[13px] leading-relaxed text-on-surface-variant">
                    {t("profileSummaryEmpty")}
                </p>
            </StatusCard>
        );
    }

    return (
        <StatusCard title={t("profileSummaryTitle")} badge="live">
            <div className="space-y-1.5">
                <p className="text-[16px] font-semibold tracking-tight text-on-surface">
                    {profile.name ?? profile.email ?? "—"}
                </p>

                {displayRoles && (
                    <p className="text-[13px] text-on-surface-variant">
                        {t("profileSummaryTargeting")} <span className="text-on-surface">{displayRoles}</span>
                    </p>
                )}

                <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2">
                    {profile.years_experience != null && (
                        <p className="text-[12px] text-on-surface-variant">
                            {t("profileSummaryExperience")} <span className="font-medium text-on-surface">{profile.years_experience} {t("profileSummaryYrs")}</span>
                        </p>
                    )}

                    {profile.visa_status && (
                        <p className="text-[12px] text-on-surface-variant">
                            {t("profileSummaryVisa")} <span className="font-medium text-on-surface">{profile.visa_status}</span>
                        </p>
                    )}
                </div>
            </div>
        </StatusCard>
    );
}
