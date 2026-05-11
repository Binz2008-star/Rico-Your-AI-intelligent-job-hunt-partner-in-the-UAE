"use client";

import { StatusCard } from "@/components/StatusCard";
import { ApiError } from "@/lib/client";
import { getApplications, getApplicationStats } from "@/services/applications";
import { getJobs } from "@/services/jobs";
import { getSettings } from "@/services/settings";
import { useEffect, useState } from "react";

interface Stats {
  jobsTotal: number;
  appsTotal: number;
  applied: number;
  interview: number;
  offer: number;
  rejected: number;
  minScore: number;
  maxDaily: number;
}

export function DashboardStats() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<"auth" | "other" | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);

    Promise.all([
      getJobs(1, 1).catch(() => null),
      getApplications(undefined, 1, 1).catch(() => null),
      getApplicationStats().catch(() => null),
      getSettings().catch(() => null),
    ])
      .then(([jobsRes, appsRes, statsRes, settingsRes]) => {
        if (!jobsRes && !appsRes && !statsRes && !settingsRes) {
          setError("other");
          return;
        }
        setStats({
          jobsTotal: jobsRes?.total ?? 0,
          appsTotal: appsRes?.total ?? 0,
          applied: statsRes?.applied ?? 0,
          interview: statsRes?.interview_scheduled ?? 0,
          offer: statsRes?.offer_extended ?? 0,
          rejected: statsRes?.rejected ?? 0,
          minScore: settingsRes?.min_score ?? 0,
          maxDaily: settingsRes?.max_daily_applies ?? 0,
        });
      })
      .catch((err) => {
        const is401 = err instanceof ApiError && err.statusCode === 401;
        setError(is401 ? "auth" : "other");
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-24 rounded-xl bg-zinc-900/60 border border-zinc-800 animate-pulse" />
        ))}
      </div>
    );
  }

  if (error === "auth") {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <p className="text-sm text-zinc-400">Session expired — please log in again.</p>
      </div>
    );
  }

  if (error === "other") {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <p className="text-sm text-zinc-400">Could not load dashboard stats. The backend may be unavailable.</p>
      </div>
    );
  }

  if (!stats) return null;

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <StatusCard title="Job matches" badge="live" value={String(stats.jobsTotal)} href="/jobs">
        <p className="text-sm text-zinc-500">
          {stats.jobsTotal === 0 ? "No matches yet — Rico will scan soon." : "Active job recommendations"}
        </p>
      </StatusCard>
      <StatusCard title="Applications tracked" badge="live" value={String(stats.appsTotal)} href="/applications">
        <p className="text-sm text-zinc-500">
          {stats.applied > 0 && `${stats.applied} applied`}
          {stats.interview > 0 && ` · ${stats.interview} interview`}
          {stats.offer > 0 && ` · ${stats.offer} offer`}
        </p>
      </StatusCard>
      <StatusCard title="Daily limit" badge={stats.maxDaily > 0 ? "live" : "placeholder"} value={`${stats.maxDaily}`} href="/settings">
        <p className="text-sm text-zinc-500">
          Max {stats.maxDaily} auto-applies per day
        </p>
      </StatusCard>
    </div>
  );
}
