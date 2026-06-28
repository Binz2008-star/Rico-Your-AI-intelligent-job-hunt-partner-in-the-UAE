"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { MaterialIcon } from "@/components/ui/MaterialIcon";
import { useLanguage } from "@/contexts/LanguageContext";
import {
  fetchProfile,
  getApplicationQueue,
  getFollowUpReminders,
  getJobs,
} from "@/lib/api";
import {
  buildMissionToday,
  type MissionAction,
  type MissionActionKind,
} from "@/lib/mission/today";
import { useTranslation, type TranslationKey } from "@/lib/translations";

const ACTION_META: Record<
  MissionActionKind,
  { icon: string; title: TranslationKey; desc: TranslationKey }
> = {
  approve_draft: {
    icon: "task_alt",
    title: "missionActionApproveDraft",
    desc: "missionActionApproveDraftDesc",
  },
  follow_up: {
    icon: "send",
    title: "missionActionFollowUp",
    desc: "missionActionFollowUpDesc",
  },
  complete_profile: {
    icon: "account_circle",
    title: "missionActionCompleteProfile",
    desc: "missionActionCompleteProfileDesc",
  },
  review_matches: {
    icon: "work",
    title: "missionActionReviewMatches",
    desc: "missionActionReviewMatchesDesc",
  },
};

type LoadState = "loading" | "ready" | "error";

const cardClass =
  "rico-card rounded-2xl border border-border-soft bg-surface-elevated/70 p-5 md:p-6 flex flex-col gap-4 shadow-sm transition-all duration-300";

export function MissionTodayCard() {
  const { language } = useLanguage();
  const t = useTranslation(language);
  const [actions, setActions] = useState<MissionAction[]>([]);
  const [state, setState] = useState<LoadState>("loading");

  const load = useCallback(async () => {
    setState("loading");
    // Each feed loads independently — one failure degrades that tile only and
    // never blocks the rest of Mission Control.
    const [queueR, followR, profileR, jobsR] = await Promise.allSettled([
      getApplicationQueue(),
      getFollowUpReminders(),
      fetchProfile(),
      getJobs(1, 1, 0),
    ]);

    // Only surface a retryable error when every feed is down.
    if ([queueR, followR, profileR, jobsR].every((r) => r.status === "rejected")) {
      setState("error");
      return;
    }

    const pendingDrafts =
      queueR.status === "fulfilled"
        ? queueR.value.filter((d) => d.status === "pending").length
        : 0;
    const followUpsDue = followR.status === "fulfilled" ? followR.value.length : 0;
    const completenessScore =
      profileR.status === "fulfilled"
        ? profileR.value.profile_exists
          ? profileR.value.completeness_score ?? 0
          : 0
        : null;
    const newMatches = jobsR.status === "fulfilled" ? jobsR.value.total : 0;

    setActions(
      buildMissionToday({ pendingDrafts, followUpsDue, completenessScore, newMatches }),
    );
    setState("ready");
  }, []);

  useEffect(() => {
    const id = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(id);
  }, [load]);

  if (state === "loading") {
    return (
      <div className={cardClass} aria-busy="true">
        <div className="animate-pulse space-y-3 motion-reduce:animate-none">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-12 rounded-xl bg-white/5" />
          ))}
        </div>
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className={cardClass}>
        <p className="text-[13px] text-text-tertiary">{t("missionTodayError")}</p>
        <button
          type="button"
          onClick={() => void load()}
          className="self-start text-[12px] font-semibold text-gold hover:underline rico-focus-strong"
        >
          {t("retry")}
        </button>
      </div>
    );
  }

  if (actions.length === 0) {
    return (
      <div className={cardClass}>
        <div className="flex items-center gap-3">
          <span
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-emerald-400/25 bg-emerald-500/10 text-emerald-300"
            aria-hidden="true"
          >
            <MaterialIcon icon="check_circle" size={18} />
          </span>
          <p className="text-[13px] text-text-secondary">{t("missionTodayCaughtUp")}</p>
        </div>
        <Link
          href="/command"
          className="self-start rounded-full border border-gold/30 bg-gold/10 px-4 py-2 text-[12px] font-semibold text-gold transition-colors hover:bg-gold/15 rico-focus-strong"
        >
          {t("missionAskRicoCta")}
        </Link>
      </div>
    );
  }

  return (
    <div className={cardClass}>
      <ul className="flex flex-col gap-2">
        {actions.map((action) => {
          const meta = ACTION_META[action.kind];
          return (
            <li key={action.kind}>
              <Link
                href={action.href}
                aria-label={`${t(meta.title)}${action.count > 0 ? ` (${action.count})` : ""}`}
                className="group flex items-center gap-3 rounded-xl border border-border-subtle/60 bg-surface-glass px-3 py-2.5 transition-colors hover:border-gold/30 hover:bg-surface-elevated/70 rico-focus-strong"
              >
                <span
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-gold/20 bg-gold/10 text-gold"
                  aria-hidden="true"
                >
                  <MaterialIcon icon={meta.icon} size={18} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-[13px] font-semibold text-rico-text">
                    {t(meta.title)}
                  </span>
                  <span className="block text-[11px] text-text-tertiary">
                    {t(meta.desc)}
                  </span>
                </span>
                {action.count > 0 && (
                  <span className="shrink-0 rounded-full bg-gold/15 px-2 py-0.5 text-[11px] font-bold tabular-nums text-gold">
                    {action.count}
                  </span>
                )}
                <MaterialIcon
                  icon="chevron_right"
                  size={18}
                  className="shrink-0 text-text-tertiary transition-transform group-hover:translate-x-0.5"
                />
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
