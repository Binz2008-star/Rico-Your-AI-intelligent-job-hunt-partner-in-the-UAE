"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { DashboardStats } from "@/components/DashboardStats";
import { ProfileCompletionBanner } from "@/components/ProfileCompletionBanner";
import { ProfileReadinessCard } from "@/components/ProfileReadinessCard";
import { ProfileSummaryCard } from "@/components/ProfileSummaryCard";
import { MissionTodayCard } from "@/components/mission/MissionTodayCard";
import { MaterialIcon } from "@/components/ui/MaterialIcon";
import { useLanguage } from "@/contexts/LanguageContext";
import { fetchProfile, type ProfileResponse } from "@/lib/api";
import { useTranslation } from "@/lib/translations";

// ── 🎯 Current Mission header ─────────────────────────────────────────────────

const headerClass =
  "rico-card relative overflow-hidden rounded-2xl border border-gold/20 bg-surface-elevated/70 p-5 md:p-6 shadow-sm";

function CurrentMissionHeader() {
  const { language } = useLanguage();
  const t = useTranslation(language);
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  const load = useCallback(async () => {
    try {
      setProfile(await fetchProfile());
      setState("ready");
    } catch {
      setState("error");
    }
  }, []);

  useEffect(() => {
    const id = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(id);
  }, [load]);

  if (state === "loading") {
    return (
      <div className={headerClass} aria-busy="true">
        <div className="animate-pulse space-y-3 motion-reduce:animate-none">
          <div className="h-3 w-32 rounded bg-white/5" />
          <div className="h-5 w-56 rounded bg-white/5" />
          <div className="h-1.5 rounded-full bg-white/5" />
        </div>
      </div>
    );
  }

  const role = profile?.target_roles?.[0] ?? null;
  const city = profile?.preferred_cities?.[0] ?? null;
  const salary = profile?.salary_expectation_aed ?? null;
  const hasMission = state === "ready" && Boolean(profile?.profile_exists) && Boolean(role || city || salary);

  // No mission yet (or profile failed to load) → invite the user to set one.
  if (!hasMission) {
    return (
      <div className={headerClass}>
        <div className="flex flex-col gap-1.5">
          <span className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-text-secondary">
            <MaterialIcon icon="rocket_launch" size={15} className="text-gold" />
            {t("missionCurrentMission")}
          </span>
          <p className="text-[15px] font-semibold text-rico-text">{t("missionSetTitle")}</p>
          <p className="text-[12px] text-text-tertiary">{t("missionSetDesc")}</p>
        </div>
        <Link
          href="/profile"
          className="mt-3 inline-flex self-start rounded-full border border-gold/30 bg-gold/10 px-4 py-2 text-[12px] font-semibold text-gold transition-colors hover:bg-gold/15 rico-focus-strong"
        >
          {t("missionSetCta")}
        </Link>
      </div>
    );
  }

  const pct = Math.round(Math.min(100, Math.max(0, (profile?.completeness_score ?? 0) * 100)));

  return (
    <div className={headerClass}>
      <div
        className="pointer-events-none absolute -right-10 -top-10 h-36 w-36 rounded-full bg-gold/[0.08] blur-2xl"
        aria-hidden="true"
      />
      <div className="relative flex flex-col gap-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <span className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-text-secondary">
              <MaterialIcon icon="rocket_launch" size={15} className="text-gold" />
              {t("missionCurrentMission")}
            </span>
            <p className="mt-1 break-words text-[18px] font-bold leading-tight text-rico-text md:text-[20px]">
              {role ?? t("missionRoleLabel")}
            </p>
          </div>
        </div>

        {/* Mission facts — only rendered when the profile actually supplied them */}
        <div className="flex flex-wrap gap-2">
          {city && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-border-subtle/60 bg-surface-glass px-3 py-1 text-[12px] text-text-secondary">
              <MaterialIcon icon="business" size={13} className="text-text-tertiary" />
              {city}
            </span>
          )}
          {salary != null && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-border-subtle/60 bg-surface-glass px-3 py-1 text-[12px] text-text-secondary">
              <MaterialIcon icon="workspace_premium" size={13} className="text-text-tertiary" />
              {t("missionSalaryLabel")}: {salary.toLocaleString()} AED
            </span>
          )}
        </div>

        {/* Progress — transparently labelled as a profile-completeness proxy, not a fake mission % */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between gap-3">
            <span className="text-[11px] font-medium text-text-tertiary">{t("missionProgressLabel")}</span>
            <span className="text-[12px] font-semibold tabular-nums text-gold">{pct}%</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-overlay/12">
            <div
              className="h-full rounded-full bg-gold transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className="text-[10px] text-text-tertiary">{t("missionProgressBasis")}</span>
        </div>
      </div>
    </div>
  );
}

// ── Ask Rico entry point ──────────────────────────────────────────────────────

const ASK_CHIPS: { labelKey: "missionAskChip1" | "missionAskChip2" | "missionAskChip3"; q: string }[] = [
  { labelKey: "missionAskChip1", q: "Find UAE jobs that match my CV and experience." },
  { labelKey: "missionAskChip2", q: "Based on my profile and experience, what's the best next step in my job search?" },
  { labelKey: "missionAskChip3", q: "Review my CV for gaps and tell me the highest-impact improvements I can make." },
];

function AskRicoCard() {
  const { language } = useLanguage();
  const t = useTranslation(language);

  return (
    <div className="rico-card rounded-2xl border border-border-soft bg-surface-elevated/70 p-5 md:p-6 shadow-sm">
      <div className="flex flex-col gap-3">
        <div className="flex items-start gap-3">
          <span
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-gold/20 bg-gold/10 text-gold"
            aria-hidden="true"
          >
            <MaterialIcon icon="auto_awesome" size={18} filled />
          </span>
          <div className="min-w-0">
            <p className="text-[14px] font-semibold text-rico-text">{t("missionAskRicoTitle")}</p>
            <p className="mt-0.5 text-[12px] text-text-tertiary">{t("missionAskRicoDesc")}</p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {ASK_CHIPS.map((chip) => (
            <Link
              key={chip.labelKey}
              href={`/command?q=${encodeURIComponent(chip.q)}`}
              className="rounded-full border border-border-subtle/60 bg-surface-glass px-3 py-1.5 text-[12px] text-text-secondary transition-colors hover:border-gold/30 hover:text-rico-text rico-focus-strong"
            >
              {t(chip.labelKey)}
            </Link>
          ))}
        </div>

        <Link
          href="/command"
          className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-gold/30 bg-gold/10 px-4 py-2.5 text-[13px] font-semibold text-gold transition-colors hover:bg-gold/15 rico-focus-strong sm:w-auto sm:self-start"
        >
          <MaterialIcon icon="auto_awesome" size={16} />
          {t("missionAskRicoCta")}
        </Link>
      </div>
    </div>
  );
}

// ── Mission Control surface ───────────────────────────────────────────────────

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-text-tertiary">{children}</h2>
  );
}

export function MissionControl() {
  const { language } = useLanguage();
  const t = useTranslation(language);

  return (
    <div className="flex flex-col gap-10">
      <ProfileCompletionBanner />

      {/* 🎯 Current Mission */}
      <CurrentMissionHeader />

      {/* Today's Actions */}
      <section>
        <SectionHeading>{t("missionSectionToday")}</SectionHeading>
        <MissionTodayCard />
      </section>

      {/* Ask Rico */}
      <section>
        <SectionHeading>{t("missionSectionAsk")}</SectionHeading>
        <AskRicoCard />
      </section>

      {/* Job Pipeline Summary */}
      <section>
        <SectionHeading>{t("dashboardSectionPipeline")}</SectionHeading>
        <DashboardStats />
      </section>

      {/* Profile / CV Readiness */}
      <section>
        <SectionHeading>{t("dashboardSectionReadiness")}</SectionHeading>
        <div className="grid gap-4 sm:grid-cols-2">
          <ProfileSummaryCard />
          <ProfileReadinessCard />
        </div>
      </section>
    </div>
  );
}
