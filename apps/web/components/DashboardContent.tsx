"use client";

import { DashboardStats } from "@/components/DashboardStats";
import { ProfileCompletionBanner } from "@/components/ProfileCompletionBanner";
import { ProfileReadinessCard } from "@/components/ProfileReadinessCard";
import { ProfileSummaryCard } from "@/components/ProfileSummaryCard";
import { SavedSearchesList } from "@/components/SavedSearchesList";
import { StatusCard } from "@/components/StatusCard";
import { useLanguage } from "@/contexts/LanguageContext";
import { useTranslation } from "@/lib/translations";

export function DashboardContent() {
    const { language } = useLanguage();
    const t = useTranslation(language);

    return (
        <div className="flex flex-col gap-10">
            <ProfileCompletionBanner />
            {/* Career Mission Header */}
            <section>
                <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-text-tertiary">
                    {t("dashboardSectionMission")}
                </h2>
                <StatusCard title={t("dashboardMissionTitle")} badge="live" href="/command">
                    <p className="text-sm text-text-tertiary">
                        {t("dashboardMissionDesc")}
                    </p>
                    <span className="mt-3 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-4 py-2 text-xs font-semibold text-primary transition-all hover:bg-primary/15">
                        {t("dashboardOpenCommand")}
                    </span>
                </StatusCard>
            </section>

            {/* Job Pipeline Summary */}
            <section>
                <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-text-tertiary">
                    {t("dashboardSectionPipeline")}
                </h2>
                <DashboardStats />
            </section>

            {/* Next Best Actions */}
            <section>
                <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-text-tertiary">
                    {t("dashboardSectionActions")}
                </h2>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    <StatusCard title={t("dashboardSearchTitle")} badge="live" href="/command">
                        <p className="text-sm text-text-tertiary">
                            {t("dashboardSearchDesc")}
                        </p>
                        <span className="mt-3 inline-flex text-[12px] font-semibold text-gold">
                            {t("dashboardSearchCta")}
                        </span>
                    </StatusCard>
                    <StatusCard title={t("dashboardMatchTitle")} badge="live" href="/jobs">
                        <p className="text-sm text-text-tertiary">
                            {t("dashboardMatchDesc")}
                        </p>
                        <span className="mt-3 inline-flex text-[12px] font-semibold text-gold">
                            {t("dashboardMatchCta")}
                        </span>
                    </StatusCard>
                    <StatusCard title={t("dashboardTuneTitle")} badge="live" href="/settings">
                        <p className="text-sm text-text-tertiary">
                            {t("dashboardTuneDesc")}
                        </p>
                        <span className="mt-3 inline-flex text-[12px] font-semibold text-gold">
                            {t("dashboardTuneCta")}
                        </span>
                    </StatusCard>
                </div>
            </section>

            {/* Profile Readiness */}
            <section>
                <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-text-tertiary">
                    {t("dashboardSectionReadiness")}
                </h2>
                <div className="grid gap-4 sm:grid-cols-2">
                    <ProfileSummaryCard />
                    <ProfileReadinessCard />
                </div>
            </section>

            {/* Application Momentum */}
            <section>
                <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-text-tertiary">
                    {t("dashboardSectionMomentum")}
                </h2>
                <div className="grid gap-4 sm:grid-cols-2">
                    <StatusCard title={t("dashboardFlowTitle")} badge="live" href="/flow">
                        <p className="text-sm text-text-tertiary">
                            {t("dashboardFlowDesc")}
                        </p>
                        <span className="mt-3 inline-flex text-[12px] font-semibold text-gold">
                            {t("dashboardFlowCta")}
                        </span>
                    </StatusCard>
                    <StatusCard title={t("dashboardPacingTitle")} badge="live" href="/settings">
                        <p className="text-sm text-text-tertiary">
                            {t("dashboardPacingDesc")}
                        </p>
                        <span className="mt-3 inline-flex text-[12px] font-semibold text-gold">
                            {t("dashboardPacingCta")}
                        </span>
                    </StatusCard>
                </div>
            </section>

            {/* Rico Activity */}
            <section>
                <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-text-tertiary">
                    {t("dashboardSectionActivity")}
                </h2>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    <SavedSearchesList />
                    <StatusCard title={t("dashboardSavedLeadsTitle")} badge="placeholder" href="/saved-searches">
                        <p className="text-sm text-text-tertiary">
                            {t("dashboardSavedLeadsDesc")}
                        </p>
                        <span className="mt-3 inline-flex text-[12px] font-semibold text-gold">
                            {t("dashboardSavedLeadsCta")}
                        </span>
                    </StatusCard>
                </div>
            </section>
        </div>
    );
}
